from django.conf import settings
from django.db import models

from catalog.models import Product


class CartItem(models.Model):
    """Строка корзины вошедшего покупателя. Корзина гостя хранится в сессии."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField("количество")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "строка корзины"
        verbose_name_plural = "строки корзины"
        ordering = ("added_at", "pk")
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="cart_item_unique_product"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="cart_item_qty_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.product} × {self.quantity}"
