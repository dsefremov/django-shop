from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import Category, Product


class StockFilter(admin.SimpleListFilter):
    title = "наличие"
    parameter_name = "stock"

    def lookups(self, request: HttpRequest, model_admin: object) -> list[tuple[str, str]]:
        return [("in", "В наличии"), ("out", "Нет в наличии")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Product]) -> QuerySet[Product]:
        if self.value() == "in":
            return queryset.filter(stock__gt=0)
        if self.value() == "out":
            return queryset.filter(stock=0)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin[Category]):
    list_display = ("name", "slug", "position", "products_count")
    list_editable = ("position",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request: HttpRequest) -> QuerySet[Category]:
        return super().get_queryset(request).annotate(products_total=Count("products"))

    @admin.display(description="товаров", ordering="products_total")
    def products_count(self, obj: Category) -> int:
        return int(getattr(obj, "products_total", 0))


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin[Product]):
    list_display = ("thumb", "name", "category", "price", "stock", "is_active")
    list_display_links = ("thumb", "name")
    list_editable = ("price", "stock", "is_active")
    list_filter = ("category", StockFilter, "is_active", "created_at")
    list_select_related = ("category",)
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    date_hierarchy = "created_at"
    list_per_page = 20
    readonly_fields = ("created_at", "updated_at", "preview")
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "description")}),
        ("Цена и остаток", {"fields": ("price", "stock", "is_active")}),
        ("Фото", {"fields": ("image", "preview")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )
    actions = ("make_active", "make_inactive")

    @admin.display(description="")
    def thumb(self, obj: Product) -> SafeString | str:
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" alt="" width="40" height="40" style="border-radius:6px">', obj.image.url
        )

    @admin.display(description="предпросмотр")
    def preview(self, obj: Product) -> SafeString | str:
        if not obj.image:
            return "—"
        return format_html('<img src="{}" alt="" width="160" style="border-radius:8px">', obj.image.url)

    @admin.action(description="Показывать в каталоге", permissions=["change"])
    def make_active(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Показаны в каталоге: {updated}.")

    @admin.action(description="Скрыть из каталога", permissions=["change"])
    def make_inactive(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Скрыты из каталога: {updated}.")
