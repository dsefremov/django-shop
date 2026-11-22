from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import TemplateView

from catalog.models import Product

from .cart import Cart, CartError
from .forms import AddToCartForm, UpdateCartForm


class CartView(TemplateView):
    template_name = "cart/index.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        lines = cart.lines()
        context.update(
            lines=lines,
            total=sum((line.total for line in lines), 0),
            has_stock_problem=any(line.exceeds_stock for line in lines),
        )
        return context


def _back(request: HttpRequest, default: str) -> str:
    url = request.POST.get("next", "")
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}):
        return url
    return default


class AddToCartView(View):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, product_id: int) -> HttpResponse:
        product = get_object_or_404(Product.objects.active(), pk=product_id)
        form = AddToCartForm(request.POST)
        back = _back(request, product.get_absolute_url())
        if not form.is_valid():
            messages.error(request, "Укажите количество от 1.")
            return HttpResponseRedirect(back)
        try:
            Cart(request).add(product, form.cleaned_data["quantity"])
        except CartError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"«{product.name}» добавлен в корзину.")
        return HttpResponseRedirect(back)


class UpdateCartView(View):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, product_id: int) -> HttpResponse:
        product = get_object_or_404(Product, pk=product_id)
        form = UpdateCartForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Неверное количество.")
        else:
            qty = Cart(request).update(product, form.cleaned_data["quantity"])
            if qty < form.cleaned_data["quantity"]:
                messages.warning(request, f"Доступно только {qty} шт. «{product.name}».")
            else:
                messages.success(request, "Корзина обновлена.")
        return HttpResponseRedirect(reverse("cart:index"))


class RemoveFromCartView(View):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, product_id: int) -> HttpResponse:
        product = get_object_or_404(Product, pk=product_id)
        Cart(request).remove(product)
        messages.success(request, f"«{product.name}» удалён из корзины.")
        return HttpResponseRedirect(reverse("cart:index"))
