from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from cart.models import CartItem
from catalog.models import Product
from orders.models import Order, OrderStatus
from orders.services import pay

from ..factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_checkout_redirects_empty_cart(customer_client: Client) -> None:
    response = customer_client.get(reverse("orders:checkout"), follow=True)
    assert response.redirect_chain[-1][0] == reverse("cart:index")
    assert "Корзина пуста" in response.content.decode()


def test_full_purchase_with_decline_and_retry(
    client: Client, customer: User, product: Product, customer_password: str
) -> None:
    # гость собирает корзину, входит, оформляет
    client.post(reverse("cart:add", args=[product.pk]), {"quantity": 2})
    response = client.get(reverse("orders:checkout"))
    assert response["Location"].startswith(reverse("accounts:login"))
    client.post(reverse("accounts:login"), {"username": customer.email, "password": customer_password})

    response = client.get(reverse("orders:checkout"))
    form = response.context["form"]
    assert form.initial["customer_name"] == "Иван Петров"
    assert form.initial["customer_email"] == customer.email
    assert 'data-testid="checkout-total">11\u00a0980\u00a0₽<' in response.content.decode()

    response = client.post(
        reverse("orders:checkout"),
        {
            "customer_name": "Иван Петров",
            "customer_email": customer.email,
            "customer_phone": "+7 900 555-12-34",
            "address": "г. Москва, ул. Арбат, д. 10",
        },
        follow=True,
    )
    order = Order.objects.get(user=customer)
    assert response.redirect_chain[-1][0] == order.get_absolute_url()
    assert f"Заказ №{order.pk} оформлен" in response.content.decode()
    assert not CartItem.objects.filter(user=customer).exists()
    product.refresh_from_db()
    assert product.stock == 13

    # отказ
    response = client.post(reverse("orders:pay", args=[order.pk]), {"decision": "decline"}, follow=True)
    content = response.content.decode()
    assert "Оплата отклонена. Можно попробовать ещё раз." in content
    assert 'data-testid="payment-declined"' in content
    assert "Оплатить ещё раз" in content
    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_DECLINED

    # повтор
    response = client.post(reverse("orders:pay", args=[order.pk]), {"decision": "pay"}, follow=True)
    content = response.content.decode()
    assert "Оплата прошла успешно." in content
    assert 'data-testid="pay-button"' not in content
    assert content.count('data-testid="payment-attempt"') == 2
    order.refresh_from_db()
    assert order.status == OrderStatus.PAID


def test_checkout_validation_keeps_cart(customer_client: Client, customer: User, product: Product) -> None:
    customer_client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1})
    response = customer_client.post(
        reverse("orders:checkout"),
        {"customer_name": "", "customer_email": "bad", "customer_phone": "12", "address": ""},
    )
    assert response.status_code == 200
    assert set(response.context["form"].errors) == {
        "customer_name",
        "customer_email",
        "customer_phone",
        "address",
    }
    assert Order.objects.count() == 0
    assert CartItem.objects.filter(user=customer).count() == 1


def test_checkout_conflict_when_stock_bought_meanwhile(customer_client: Client, product: Product) -> None:
    customer_client.post(reverse("cart:add", args=[product.pk]), {"quantity": 3})
    Product.objects.filter(pk=product.pk).update(stock=1)
    response = customer_client.post(
        reverse("orders:checkout"),
        {
            "customer_name": "Иван",
            "customer_email": "ivan@example.test",
            "customer_phone": "+7 900 555-12-34",
            "address": "Москва",
        },
        follow=True,
    )
    assert "Недостаточно на складе: Беспроводные наушники Aero." in response.content.decode()
    assert Order.objects.count() == 0


def test_foreign_order_is_404(
    client: Client, other_customer: User, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(other_customer, (product, 1))
    client.force_login(customer)
    assert client.get(order.get_absolute_url()).status_code == 404
    assert client.post(reverse("orders:pay", args=[order.pk]), {"decision": "pay"}).status_code == 404
    assert client.post(reverse("orders:cancel", args=[order.pk])).status_code == 404
    order.refresh_from_db()
    assert order.status == OrderStatus.NEW


def test_pay_bad_decision_and_paid_order(
    customer_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    response = customer_client.post(
        reverse("orders:pay", args=[order.pk]), {"decision": "steal"}, follow=True
    )
    assert "Неизвестное действие оплаты." in response.content.decode()
    pay(order, approve=True)
    response = customer_client.post(reverse("orders:pay", args=[order.pk]), {"decision": "pay"}, follow=True)
    assert "нельзя оплатить" in response.content.decode()


def test_customer_cancels_unpaid_order_and_stock_returns(
    customer_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 2))
    response = customer_client.post(reverse("orders:cancel", args=[order.pk]), follow=True)
    assert "отменён" in response.content.decode()
    customer_client.post(reverse("orders:cancel", args=[order.pk]))
    product.refresh_from_db()
    assert product.stock == 15
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED


def test_paid_order_cannot_be_cancelled_by_customer(
    customer_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    pay(order, approve=True)
    response = customer_client.post(reverse("orders:cancel", args=[order.pk]), follow=True)
    assert "уже нельзя отменить" in response.content.decode()


@pytest.fixture
def history(customer: User, other_customer: User, make_order: Callable[..., Order]) -> list[Order]:
    cheap = ProductFactory.create(name="Скакалка скоростная", price=590, stock=50)
    pricey = ProductFactory.create(name="Смарт-часы Pulse 2", price=12490, stock=50)
    orders = [
        make_order(customer, (cheap, 1)),
        make_order(customer, (pricey, 1)),
        make_order(customer, (cheap, 2), (pricey, 1)),
    ]
    make_order(other_customer, (cheap, 1))
    pay(orders[1], approve=True)
    now = timezone.now()
    for order, days in zip(orders, (10, 3, 1), strict=True):
        Order.objects.filter(pk=order.pk).update(created_at=now - timedelta(days=days))
    return orders


def rows(response: Any) -> list[int]:
    return [o.pk for o in response.context["orders"]]


def test_my_orders_only_own_newest_first(customer_client: Client, history: list[Order]) -> None:
    response = customer_client.get(reverse("orders:list"))
    assert rows(response) == [history[2].pk, history[1].pk, history[0].pk]
    assert response.content.decode().count('data-testid="order-row"') == 3


def test_my_orders_filters(customer_client: Client, history: list[Order]) -> None:
    url = reverse("orders:list")
    assert rows(customer_client.get(url, {"status": "paid"})) == [history[1].pk]
    assert rows(customer_client.get(url, {"q": "часы"})) == [history[2].pk, history[1].pk]
    assert rows(customer_client.get(url, {"q": f"№{history[0].pk}"})) == [history[0].pk]
    date_from = (timezone.localdate() - timedelta(days=5)).isoformat()
    assert rows(customer_client.get(url, {"date_from": date_from, "ordering": "-total"})) == [
        history[2].pk,
        history[1].pk,
    ]
    assert rows(customer_client.get(url, {"ordering": "total"}))[0] == history[0].pk
    response = customer_client.get(url, {"q": "нет такого"})
    assert 'data-testid="no-results"' in response.content.decode()
    # неверные параметры молча отбрасываются
    assert len(rows(customer_client.get(url, {"status": "evil", "date_to": "xx", "ordering": "pk"}))) == 3


def test_my_orders_pagination(
    customer_client: Client, customer: User, make_order: Callable[..., Order]
) -> None:
    item = ProductFactory.create(stock=100)
    for _ in range(12):
        make_order(customer, (item, 1))
    url = reverse("orders:list")
    assert len(rows(customer_client.get(url))) == 10
    assert len(rows(customer_client.get(url, {"page": 2}))) == 2


def test_order_detail_shows_items_and_payment(
    customer_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 2))
    content = customer_client.get(order.get_absolute_url()).content.decode()
    assert f"Заказ №{order.pk}" in content
    assert 'data-testid="order-status">Новый<' in content
    assert 'data-testid="order-total">11\u00a0980\u00a0₽<' in content
    assert 'data-testid="pay-button"' in content
    assert 'data-testid="decline-button"' in content
