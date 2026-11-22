from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from catalog.models import Product


class OrderStatus(models.TextChoices):
    NEW = "new", "Новый"
    PAID = "paid", "Оплачен"
    PAYMENT_DECLINED = "payment_declined", "Оплата отклонена"
    PROCESSING = "processing", "В работе"
    COMPLETED = "completed", "Выполнен"
    CANCELLED = "cancelled", "Отменён"


PAYABLE_STATUSES = frozenset({OrderStatus.NEW, OrderStatus.PAYMENT_DECLINED})
CANCELLABLE_BY_CUSTOMER = PAYABLE_STATUSES

# Разрешённые переходы статусов (оплата и отказ — только через PaymentService).
TRANSITIONS: dict[str, frozenset[str]] = {
    OrderStatus.NEW: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.PAYMENT_DECLINED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.PROCESSING, OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.PROCESSING: frozenset({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="покупатель",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        "статус", max_length=20, choices=OrderStatus.choices, default=OrderStatus.NEW, db_index=True
    )
    total = models.DecimalField("сумма, ₽", max_digits=12, decimal_places=2)
    customer_name = models.CharField("имя и фамилия", max_length=150)
    customer_email = models.EmailField("эл. почта")
    customer_phone = models.CharField("телефон", max_length=32)
    address = models.CharField("адрес доставки", max_length=255)
    comment = models.TextField("комментарий", blank=True)
    created_at = models.DateTimeField("оформлен", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)
    paid_at = models.DateTimeField("оплачен", null=True, blank=True)
    stock_returned_at = models.DateTimeField(
        "остаток возвращён", null=True, blank=True, help_text="Ставится один раз при отмене."
    )

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ("-created_at", "-pk")
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"Заказ №{self.pk}"

    def get_absolute_url(self) -> str:
        return reverse("orders:detail", kwargs={"pk": self.pk})

    @property
    def is_payable(self) -> bool:
        return self.status in PAYABLE_STATUSES

    @property
    def can_cancel(self) -> bool:
        return self.status in CANCELLABLE_BY_CUSTOMER

    def can_transition_to(self, status: str) -> bool:
        return status in TRANSITIONS.get(self.status, frozenset())


class OrderItem(models.Model):
    """Позиция заказа со снимком названия и цены на момент оформления."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, verbose_name="товар", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    product_name = models.CharField("название", max_length=200)
    price = models.DecimalField("цена, ₽", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("количество")

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "позиции заказа"
        ordering = ("pk",)
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="order_item_qty_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.product_name} × {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return self.price * self.quantity


class PaymentAttempt(models.Model):
    """История оплаты: каждая попытка (успешная или отклонённая) — отдельная запись."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payment_attempts")
    succeeded = models.BooleanField("успешно")
    amount = models.DecimalField("сумма, ₽", max_digits=12, decimal_places=2)
    reference = models.CharField("идентификатор платежа", max_length=64)
    message = models.CharField("результат", max_length=255)
    created_at = models.DateTimeField("время", auto_now_add=True)

    class Meta:
        verbose_name = "попытка оплаты"
        verbose_name_plural = "история оплаты"
        ordering = ("created_at", "pk")

    def __str__(self) -> str:
        return f"{self.reference}: {self.message}"
