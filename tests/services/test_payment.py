from collections.abc import Callable
from decimal import Decimal

import pytest

from accounts.models import User
from catalog.models import Product
from orders.models import Order, OrderStatus
from orders.payments import PaymentResult
from orders.services import OrderError, cancel, pay, set_status

pytestmark = pytest.mark.django_db


def test_pay_marks_order_paid_and_logs_attempt(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    order, result = pay(order, approve=True)
    assert result.succeeded
    order.refresh_from_db()
    assert order.status == OrderStatus.PAID
    assert order.paid_at is not None
    attempt = order.payment_attempts.get()
    assert attempt.succeeded
    assert attempt.amount == Decimal("5990.00")
    assert attempt.reference.startswith(f"FAKE-{order.pk}-")


def test_decline_keeps_reserve_and_retry_succeeds(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 2))
    order, result = pay(order, approve=False)
    assert not result.succeeded
    order.refresh_from_db()
    product.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_DECLINED
    assert order.paid_at is None
    assert order.is_payable
    assert product.stock == 13  # резерв сохранён

    # второй отказ тоже допустим и пишется в историю
    pay(order, approve=False)
    order, result = pay(order, approve=True)
    assert result.succeeded
    order.refresh_from_db()
    product.refresh_from_db()
    assert order.status == OrderStatus.PAID
    assert product.stock == 13
    assert list(order.payment_attempts.values_list("succeeded", flat=True)) == [False, False, True]


@pytest.mark.parametrize("status", [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED])
def test_paid_or_later_order_cannot_be_paid_again(
    customer: User, product: Product, make_order: Callable[..., Order], status: str
) -> None:
    order = make_order(customer, (product, 1))
    pay(order, approve=True)
    if status != OrderStatus.PAID:
        set_status(order, status)
    with pytest.raises(OrderError, match="нельзя оплатить"):
        pay(order, approve=True)
    assert order.payment_attempts.count() == 1


def test_cancelled_order_cannot_be_paid(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    cancel(order)
    with pytest.raises(OrderError):
        pay(order, approve=True)
    assert order.payment_attempts.count() == 0


def test_custom_gateway_is_used(customer: User, product: Product, make_order: Callable[..., Order]) -> None:
    calls: list[tuple[int, Decimal, bool]] = []

    class RecordingGateway:
        def charge(self, order_id: int, amount: Decimal, *, approve: bool) -> PaymentResult:
            calls.append((order_id, amount, approve))
            return PaymentResult(True, "REC-1", "ok")

    order = make_order(customer, (product, 1))
    pay(order, approve=False, gateway=RecordingGateway())
    assert calls == [(order.pk, Decimal("5990.00"), False)]
    order.refresh_from_db()
    assert order.status == OrderStatus.PAID  # решение принимает шлюз
