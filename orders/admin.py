from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from catalog.templatetags.shop import rub

from .models import Order, OrderItem, OrderStatus, PaymentAttempt
from .services import OrderError, set_status


class OrderItemInline(admin.TabularInline[OrderItem, Order]):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("product_name", "product", "price", "quantity", "line_total")
    readonly_fields = fields

    def has_add_permission(self, request: HttpRequest, obj: Order | None = None) -> bool:
        return False

    @admin.display(description="сумма, ₽")
    def line_total(self, obj: OrderItem) -> str:
        return f"{obj.line_total:.2f}"


class PaymentAttemptInline(admin.TabularInline[PaymentAttempt, Order]):
    model = PaymentAttempt
    extra = 0
    can_delete = False
    fields = ("created_at", "succeeded", "amount", "reference", "message")
    readonly_fields = fields

    def has_add_permission(self, request: HttpRequest, obj: Order | None = None) -> bool:
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin[Order]):
    # Порядок колонок важен для сортировки по номеру колонки (?o=-5 — по сумме по убыванию).
    list_display = ("__str__", "created_at", "customer", "status", "total_rub", "paid_at")
    list_display_links = ("__str__",)
    list_filter = ("status", "created_at", "paid_at")
    search_fields = ("customer_name", "customer_email", "customer_phone", "items__product_name")
    date_hierarchy = "created_at"
    list_per_page = 20
    show_full_result_count = True
    inlines = (OrderItemInline, PaymentAttemptInline)
    # Статус меняется только действиями (через сервис): так остаток возвращается ровно один раз.
    readonly_fields = (
        "user",
        "status",
        "total",
        "created_at",
        "updated_at",
        "paid_at",
        "stock_returned_at",
    )
    fieldsets = (
        (None, {"fields": ("user", "status", "total")}),
        (
            "Получатель",
            {"fields": ("customer_name", "customer_email", "customer_phone", "address", "comment")},
        ),
        ("Даты", {"fields": ("created_at", "updated_at", "paid_at", "stock_returned_at")}),
    )
    actions = ("mark_processing", "mark_completed", "mark_cancelled")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        return super().get_queryset(request).select_related("user")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @admin.display(description="покупатель", ordering="customer_name")
    def customer(self, obj: Order) -> SafeString:
        return format_html("{}<br><small>{}</small>", obj.customer_name, obj.customer_email)

    @admin.display(description="сумма", ordering="total")
    def total_rub(self, obj: Order) -> str:
        return rub(obj.total)

    def get_search_results(
        self, request: HttpRequest, queryset: QuerySet[Order], search_term: str
    ) -> tuple[QuerySet[Order], bool]:
        # «123» или «№123» — поиск по номеру заказа, без совпадений в телефоне и т. п.
        number = search_term.strip().lstrip("№#").strip()
        if number.isdigit():
            return queryset.filter(pk=int(number)), False
        return super().get_search_results(request, queryset, search_term)

    def _apply(self, request: HttpRequest, queryset: QuerySet[Order], status: str) -> None:
        done, failed = 0, []
        for order in queryset.order_by("pk"):
            try:
                set_status(order, status)
                done += 1
            except OrderError as exc:
                failed.append(str(exc))
        label = OrderStatus(status).label
        if done:
            self.message_user(request, f"Статус «{label}»: {done} заказ(ов).", messages.SUCCESS)
        for text in failed:
            self.message_user(request, text, messages.WARNING)

    @admin.action(description="Статус «В работе»", permissions=["change"])
    def mark_processing(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        self._apply(request, queryset, OrderStatus.PROCESSING)

    @admin.action(description="Статус «Выполнен»", permissions=["change"])
    def mark_completed(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        self._apply(request, queryset, OrderStatus.COMPLETED)

    @admin.action(description="Отменить (вернуть остаток)", permissions=["change"])
    def mark_cancelled(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        self._apply(request, queryset, OrderStatus.CANCELLED)
