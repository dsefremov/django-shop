"""Фильтры каталога (django-filter): поиск, цена, наличие, сортировка — всё в GET-параметрах."""

from decimal import Decimal
from typing import Any

import django_filters
from django import forms
from django.db.models import Q, QuerySet

from .models import Product

SORT_CHOICES = (
    ("name", "По названию"),
    ("price", "Сначала дешевле"),
    ("-price", "Сначала дороже"),
    ("-created", "Сначала новые"),
)


class ProductFilter(django_filters.FilterSet):  # type: ignore[misc]  # у django-filter нет типов
    q = django_filters.CharFilter(
        label="Поиск",
        method="search",
        widget=forms.SearchInput(attrs={"placeholder": "Поиск по названию и описанию"}),
    )
    price_min = django_filters.NumberFilter(
        field_name="price", lookup_expr="gte", label="Цена от, ₽", min_value=Decimal(0)
    )
    price_max = django_filters.NumberFilter(
        field_name="price", lookup_expr="lte", label="до, ₽", min_value=Decimal(0)
    )
    in_stock = django_filters.BooleanFilter(
        label="Только в наличии",
        method="filter_in_stock",
        widget=forms.CheckboxInput,
    )
    ordering = django_filters.OrderingFilter(
        label="Сортировка",
        fields=(("name", "name"), ("price", "price"), ("created_at", "created")),
        choices=SORT_CHOICES,
        empty_label=None,
        null_label=None,
    )

    class Meta:
        model = Product
        fields: list[str] = []

    def search(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

    def filter_in_stock(
        self, queryset: QuerySet[Product], name: str, value: bool | None
    ) -> QuerySet[Product]:
        return queryset.filter(stock__gt=0) if value else queryset

    @property
    def qs(self) -> QuerySet[Product]:
        queryset: QuerySet[Product] = super().qs
        # Сортировка по умолчанию — по названию; второй ключ делает порядок стабильным.
        if not self.form.cleaned_data.get("ordering"):
            queryset = queryset.order_by("name", "pk")
        else:
            queryset = queryset.order_by(*queryset.query.order_by, "pk")
        return queryset


def sanitize(
    data: Any, filterset_class: type[django_filters.FilterSet], queryset: QuerySet[Any]
) -> dict[str, Any]:
    """Неизвестные или неверные параметры молча отбрасываются (как в других магазинах)."""
    clean = {k: v for k, v in data.items() if k in filterset_class.base_filters}
    probe = filterset_class(data=clean, queryset=queryset.none())
    if probe.is_valid():
        return clean
    return {k: v for k, v in clean.items() if k not in probe.form.errors}
