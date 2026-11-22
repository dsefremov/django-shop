from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField("название", max_length=120, unique=True)
    slug = models.SlugField("адрес (slug)", max_length=140, unique=True, allow_unicode=False)
    description = models.TextField("описание", blank=True)
    image = models.ImageField("картинка", upload_to="categories/", blank=True)
    position = models.PositiveIntegerField("порядок", default=100)
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:category", kwargs={"slug": self.slug})


class ProductQuerySet(models.QuerySet["Product"]):
    def active(self) -> ProductQuerySet:
        return self.filter(is_active=True)

    def in_stock(self) -> ProductQuerySet:
        return self.filter(stock__gt=0)


class Product(models.Model):
    category = models.ForeignKey(
        Category, verbose_name="категория", on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField("название", max_length=200)
    slug = models.SlugField("адрес (slug)", max_length=220, unique=True)
    description = models.TextField("описание", blank=True)
    price = models.DecimalField(
        "цена, ₽",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    stock = models.PositiveIntegerField("остаток, шт.", default=0)
    image = models.ImageField("фото", upload_to="products/", blank=True)
    is_active = models.BooleanField("показывать в каталоге", default=True)
    created_at = models.DateTimeField("добавлен", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ("name",)
        indexes = [models.Index(fields=["price"]), models.Index(fields=["name"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="product_price_positive"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:product", kwargs={"slug": self.slug})

    @property
    def in_stock(self) -> bool:
        return self.stock > 0
