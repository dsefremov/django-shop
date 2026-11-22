"""
Корзина. У гостя — в сессии ({product_id: quantity}), у вошедшего — в таблице CartItem,
чтобы корзина переживала выход и другие устройства. При входе корзина гостя сливается
с корзиной покупателя (сигнал user_logged_in). Количество всегда ограничено остатком.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.http import HttpRequest

from accounts.models import User
from catalog.models import Product

from .models import CartItem

SESSION_KEY = "cart"


class CartError(Exception):
    pass


@dataclass(frozen=True)
class CartLine:
    product: Product
    quantity: int

    @property
    def total(self) -> Decimal:
        return self.product.price * self.quantity

    @property
    def exceeds_stock(self) -> bool:
        return self.quantity > self.product.stock


def _user(request: HttpRequest) -> User | None:
    user = request.user
    return user if isinstance(user, User) and user.is_authenticated else None


class Cart:
    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user = _user(request)

    # --- хранилище -------------------------------------------------------------------------
    def _raw(self) -> dict[int, int]:
        if self.user is not None:
            return dict(CartItem.objects.filter(user=self.user).values_list("product_id", "quantity"))
        stored = self.request.session.get(SESSION_KEY, {})
        return {int(pid): int(qty) for pid, qty in stored.items()}

    def _set(self, product_id: int, quantity: int) -> None:
        if self.user is not None:
            if quantity > 0:
                CartItem.objects.update_or_create(
                    user=self.user, product_id=product_id, defaults={"quantity": quantity}
                )
            else:
                CartItem.objects.filter(user=self.user, product_id=product_id).delete()
            return
        stored = dict(self.request.session.get(SESSION_KEY, {}))
        if quantity > 0:
            stored[str(product_id)] = quantity
        else:
            stored.pop(str(product_id), None)
        self.request.session[SESSION_KEY] = stored

    # --- операции --------------------------------------------------------------------------
    def quantity_of(self, product: Product) -> int:
        return self._raw().get(product.pk, 0)

    def add(self, product: Product, quantity: int = 1) -> int:
        """Добавляет товар; итоговое количество не больше остатка. Возвращает количество в корзине."""
        if quantity < 1:
            raise CartError("Количество должно быть не меньше 1.")
        if not product.is_active or product.stock < 1:
            raise CartError("Товара нет в наличии.")
        current = self.quantity_of(product)
        if current >= product.stock:
            raise CartError(f"В корзине уже весь остаток: {product.stock} шт.")
        new_qty = min(current + quantity, product.stock)
        self._set(product.pk, new_qty)
        return new_qty

    def update(self, product: Product, quantity: int) -> int:
        """Задаёт количество (0 — удалить), не больше остатка."""
        if quantity < 0:
            raise CartError("Количество не может быть отрицательным.")
        new_qty = min(quantity, product.stock) if product.is_active else 0
        self._set(product.pk, new_qty)
        return new_qty

    def remove(self, product: Product) -> None:
        self._set(product.pk, 0)

    def clear(self) -> None:
        if self.user is not None:
            CartItem.objects.filter(user=self.user).delete()
        else:
            self.request.session.pop(SESSION_KEY, None)

    def lines(self) -> list[CartLine]:
        raw = self._raw()
        if not raw:
            return []
        products = Product.objects.select_related("category").in_bulk(list(raw))
        lines = []
        for pid, qty in raw.items():
            product = products.get(pid)
            if product is None or not product.is_active:
                continue
            lines.append(CartLine(product, qty))
        return sorted(lines, key=lambda line: line.product.name)

    def count(self) -> int:
        return sum(self._raw().values())

    def total(self) -> Decimal:
        return sum((line.total for line in self.lines()), Decimal(0))


def merge_session_cart_into_user(request: HttpRequest, user: User) -> None:
    """Сливает корзину гостя из сессии с корзиной покупателя: количества суммируются (≤ остатка)."""
    stored = request.session.pop(SESSION_KEY, None)
    if not stored:
        return
    guest = {int(pid): int(qty) for pid, qty in stored.items()}
    with transaction.atomic():
        existing = {
            item.product_id: item
            for item in CartItem.objects.select_for_update().filter(user=user, product_id__in=list(guest))
        }
        for product in Product.objects.active().filter(pk__in=list(guest)):
            qty = min(
                guest[product.pk] + (existing[product.pk].quantity if product.pk in existing else 0),
                product.stock,
            )
            if qty <= 0:
                continue
            CartItem.objects.update_or_create(user=user, product=product, defaults={"quantity": qty})
