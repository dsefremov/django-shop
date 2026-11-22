from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseBase, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from accounts.models import User
from cart.cart import Cart
from catalog.filters import sanitize

from .filters import ORDER_SORT_CHOICES, OrderFilter
from .forms import CheckoutForm, PaymentForm
from .models import Order, OrderItem
from .services import CheckoutData, OrderError, cancel, pay, place_order


def current_user(request: HttpRequest) -> User:
    """Вошедший пользователь (представления защищены LoginRequiredMixin)."""
    user = request.user
    if not isinstance(user, User):
        raise PermissionDenied
    return user


class CheckoutView(LoginRequiredMixin, FormView[CheckoutForm]):
    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if request.user.is_authenticated and not Cart(request).lines():
            messages.info(request, "Корзина пуста — добавьте товары из каталога.")
            return HttpResponseRedirect(reverse("cart:index"))
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self) -> dict[str, Any]:
        user = current_user(self.request)
        last = user.orders.order_by("-created_at").first()
        return {
            "customer_name": user.get_full_name(),
            "customer_email": user.email,
            "customer_phone": last.customer_phone if last else "",
            "address": last.address if last else "",
        }

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        lines = Cart(self.request).lines()
        context.update(lines=lines, total=sum((line.total for line in lines), 0))
        return context

    def form_valid(self, form: CheckoutForm) -> HttpResponse:
        cart = Cart(self.request)
        lines = [(line.product.pk, line.quantity) for line in cart.lines()]
        try:
            order = place_order(current_user(self.request), lines, CheckoutData(**form.cleaned_data))
        except OrderError as exc:
            messages.error(self.request, str(exc))
            return HttpResponseRedirect(reverse("cart:index"))
        cart.clear()
        messages.success(self.request, f"Заказ №{order.pk} оформлен. Оплатите его на этой странице.")
        return HttpResponseRedirect(order.get_absolute_url())


class OrderListView(LoginRequiredMixin, ListView[Order]):
    template_name = "orders/list.html"
    context_object_name = "orders"
    paginate_by = settings.ORDERS_PAGE_SIZE

    def get_queryset(self) -> QuerySet[Order]:
        base = Order.objects.filter(user=current_user(self.request)).prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.order_by("pk"))
        )
        self.filterset = OrderFilter(data=sanitize(self.request.GET, OrderFilter, base), queryset=base)
        self.filterset.is_valid()
        self.has_any = base.exists()
        return self.filterset.qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        cleaned = self.filterset.form.cleaned_data
        context.update(
            filter=self.filterset,
            sort_choices=ORDER_SORT_CHOICES,
            current_sort=cleaned.get("ordering") or ["-created"],
            has_any=self.has_any,
            has_filters=any(cleaned.get(k) for k in ("q", "status", "date_from", "date_to")),
        )
        return context


class OrderDetailView(LoginRequiredMixin, DetailView[Order]):
    template_name = "orders/detail.html"
    context_object_name = "order"

    def get_queryset(self) -> QuerySet[Order]:
        # Чужой заказ — 404, а не 403: номер чужого заказа не раскрывается.
        return Order.objects.filter(user=current_user(self.request)).prefetch_related(
            "items", "payment_attempts"
        )


class PayOrderView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        order = get_object_or_404(Order, pk=pk, user=current_user(request))
        form = PaymentForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Неизвестное действие оплаты.")
            return HttpResponseRedirect(order.get_absolute_url())
        try:
            order, result = pay(order, approve=form.cleaned_data["decision"] == "pay")
        except OrderError as exc:
            messages.error(request, str(exc))
        else:
            if result.succeeded:
                messages.success(request, "Оплата прошла успешно.")
            else:
                messages.error(request, "Оплата отклонена. Можно попробовать ещё раз.")
        return HttpResponseRedirect(order.get_absolute_url())


class CancelOrderView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        order = get_object_or_404(Order, pk=pk, user=current_user(request))
        if not order.can_cancel:
            messages.error(request, "Этот заказ уже нельзя отменить.")
        else:
            try:
                cancel(order)
            except OrderError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Заказ №{order.pk} отменён, товар вернулся на склад.")
        return HttpResponseRedirect(order.get_absolute_url())
