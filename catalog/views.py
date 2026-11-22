from typing import Any

from django.conf import settings
from django.db.models import Count, Max, Min, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from cart.forms import AddToCartForm

from .filters import SORT_CHOICES, ProductFilter, sanitize
from .models import Category, Product


class CatalogView(ListView[Product]):
    """Каталог: все товары или одна категория; фильтры и сортировка — в GET-параметрах."""

    template_name = "catalog/index.html"
    context_object_name = "products"
    paginate_by = settings.CATALOG_PAGE_SIZE

    def get_base_queryset(self) -> QuerySet[Product]:
        queryset = Product.objects.active().select_related("category")
        self.category: Category | None = None
        if slug := self.kwargs.get("slug"):
            self.category = get_object_or_404(Category, slug=slug)
            queryset = queryset.filter(category=self.category)
        return queryset

    def get_queryset(self) -> QuerySet[Product]:
        base = self.get_base_queryset()
        self.base_queryset = base
        data = sanitize(self.request.GET, ProductFilter, base)
        self.filterset = ProductFilter(data=data, queryset=base)
        self.filterset.is_valid()
        return self.filterset.qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        active = Q(products__is_active=True)
        context.update(
            category=self.category,
            categories=Category.objects.annotate(product_count=Count("products", filter=active)).order_by(
                "position", "name"
            ),
            all_count=Product.objects.active().count(),
            filter=self.filterset,
            sort_choices=SORT_CHOICES,
            current_sort=self.filterset.form.cleaned_data.get("ordering") or ["name"],
            price_range=self.base_queryset.aggregate(min=Min("price"), max=Max("price")),
            has_filters=any(
                self.filterset.form.cleaned_data.get(k) not in (None, "", False, [])
                for k in ("q", "price_min", "price_max", "in_stock")
            ),
        )
        return context


class ProductDetailView(DetailView[Product]):
    template_name = "catalog/product.html"
    context_object_name = "product"

    def get_queryset(self) -> QuerySet[Product]:
        return Product.objects.active().select_related("category")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["form"] = AddToCartForm(product=self.object)
        return context
