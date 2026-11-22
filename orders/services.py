"""
Бизнес-операции с заказами. Всё, что меняет остаток, — в транзакции с блокировкой строк
(SELECT … FOR UPDATE), поэтому два покупателя не могут купить последний товар одновременно.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import User
from catalog.models import Product

from .models import Order, OrderItem, OrderStatus, PaymentAttempt
from .payments import PaymentGateway, PaymentResult, get_gateway


class OrderError(Exception):
    """Ошибка бизнес-правила; сообщение показывается пользователю."""


class OutOfStockError(OrderError):
    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__("Недостаточно на складе: " + ", ".join(names) + ".")


@dataclass(frozen=True)
class CheckoutData:
    customer_name: str
    customer_email: str
    customer_phone: str
    address: str
    comment: str = ""


def place_order(user: User, lines: Iterable[tuple[int, int]], data: CheckoutData) -> Order:
    """
    Оформляет заказ в одной транзакции: блокирует строки товаров в порядке id, проверяет
    остаток, резервирует его (списывает со склада) и сохраняет снимок названий и цен.
    """
    wanted: dict[int, int] = {}
    for product_id, quantity in lines:
        if quantity > 0:
            wanted[product_id] = wanted.get(product_id, 0) + quantity
    if not wanted:
        raise OrderError("Корзина пуста.")

    with transaction.atomic():
        products = list(Product.objects.select_for_update().filter(pk__in=list(wanted)).order_by("pk"))
        found = {p.pk: p for p in products}
        missing = [
            found[pid].name if pid in found else f"товар #{pid}"
            for pid, qty in wanted.items()
            if pid not in found or not found[pid].is_active or found[pid].stock < qty
        ]
        if missing:
            raise OutOfStockError(missing)

        total = sum((found[pid].price * qty for pid, qty in wanted.items()), Decimal(0))
        order = Order.objects.create(
            user=user,
            status=OrderStatus.NEW,
            total=total,
            customer_name=data.customer_name,
            customer_email=data.customer_email,
            customer_phone=data.customer_phone,
            address=data.address,
            comment=data.comment,
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                product=found[pid],
                product_name=found[pid].name,
                price=found[pid].price,
                quantity=qty,
            )
            for pid, qty in sorted(wanted.items())
        )
        for pid, qty in wanted.items():
            Product.objects.filter(pk=pid).update(stock=F("stock") - qty)
    return order


def _locked(order_id: int) -> Order:
    return Order.objects.select_for_update().get(pk=order_id)


def pay(order: Order, *, approve: bool, gateway: PaymentGateway | None = None) -> tuple[Order, PaymentResult]:
    """
    Попытка оплаты через шлюз. Успех → «Оплачен»; отказ → «Оплата отклонена», резерв
    остаётся, можно повторить. Каждая попытка записывается в историю оплаты.
    """
    gateway = gateway or get_gateway()
    with transaction.atomic():
        locked = _locked(order.pk)
        if not locked.is_payable:
            raise OrderError(f"Заказ №{locked.pk} нельзя оплатить в статусе «{locked.get_status_display()}».")
        result = gateway.charge(locked.pk, locked.total, approve=approve)
        PaymentAttempt.objects.create(
            order=locked,
            succeeded=result.succeeded,
            amount=locked.total,
            reference=result.reference,
            message=result.message,
        )
        if result.succeeded:
            locked.status = OrderStatus.PAID
            locked.paid_at = timezone.now()
        else:
            locked.status = OrderStatus.PAYMENT_DECLINED
        locked.save(update_fields=["status", "paid_at", "updated_at"])
    return locked, result


def set_status(order: Order, status: str) -> Order:
    """Смена статуса по таблице переходов; отмена возвращает остаток ровно один раз."""
    if status not in OrderStatus.values:
        raise OrderError(f"Неизвестный статус: {status}.")
    with transaction.atomic():
        locked = _locked(order.pk)
        if locked.status == status:
            return locked
        if not locked.can_transition_to(status):
            raise OrderError(
                f"Заказ №{locked.pk}: нельзя перейти из «{locked.get_status_display()}» "
                f"в «{OrderStatus(status).label}»."
            )
        locked.status = status
        fields = ["status", "updated_at"]
        if status == OrderStatus.CANCELLED and locked.stock_returned_at is None:
            _return_stock(locked)
            locked.stock_returned_at = timezone.now()
            fields.append("stock_returned_at")
        locked.save(update_fields=fields)
    return locked


def cancel(order: Order) -> Order:
    return set_status(order, OrderStatus.CANCELLED)


def _return_stock(order: Order) -> None:
    returns: dict[int, int] = {}
    for product_id, quantity in order.items.filter(product__isnull=False).values_list(
        "product_id", "quantity"
    ):
        if product_id is not None:
            returns[product_id] = returns.get(product_id, 0) + quantity
    # Блокируем товары в том же порядке, что и оформление, — без взаимных блокировок.
    list(Product.objects.select_for_update().filter(pk__in=list(returns)).order_by("pk"))
    for product_id, quantity in sorted(returns.items()):
        Product.objects.filter(pk=product_id).update(stock=F("stock") + quantity)
