"""Фильтры «Моих заказов»: поиск по номеру и товару, статус, даты, сортировка."""

import django_filters
from django import forms
from django.db.models import Q, QuerySet

from .models import Order, OrderStatus

ORDER_SORT_CHOICES = (
    ("-created", "Сначала новые"),
    ("created", "Сначала старые"),
    ("-total", "Сначала дороже"),
    ("total", "Сначала дешевле"),
)


class OrderFilter(django_filters.FilterSet):  # type: ignore[misc]  # у django-filter нет типов
    q = django_filters.CharFilter(
        label="Поиск",
        method="search",
        widget=forms.SearchInput(attrs={"placeholder": "№ заказа или товар"}),
    )
    status = django_filters.ChoiceFilter(
        label="Статус", choices=OrderStatus.choices, empty_label="Все статусы"
    )
    date_from = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte",
        label="С даты",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte",
        label="По дату",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ordering = django_filters.OrderingFilter(
        label="Сортировка",
        fields=(("created_at", "created"), ("total", "total")),
        choices=ORDER_SORT_CHOICES,
        empty_label=None,
        null_label=None,
    )

    class Meta:
        model = Order
        fields: list[str] = []

    def search(self, queryset: QuerySet[Order], name: str, value: str) -> QuerySet[Order]:
        value = value.strip().lstrip("№#").strip()
        if not value:
            return queryset
        condition = Q(items__product_name__icontains=value)
        if value.isdigit():
            condition |= Q(pk=int(value))
        return queryset.filter(condition).distinct()

    @property
    def qs(self) -> QuerySet[Order]:
        queryset: QuerySet[Order] = super().qs
        if not self.form.cleaned_data.get("ordering"):
            return queryset.order_by("-created_at", "-pk")
        return queryset.order_by(*queryset.query.order_by, "-pk")
