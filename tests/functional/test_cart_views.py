import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import User
from cart.models import CartItem
from catalog.models import Product

from ..factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_guest_adds_to_cart_with_stock_cap(client: Client, product: Product) -> None:
    response = client.post(reverse("cart:add", args=[product.pk]), {"quantity": 2}, follow=True)
    content = response.content.decode()
    assert "добавлен в корзину" in content
    assert 'data-testid="cart-count">2<' in content

    client.post(reverse("cart:add", args=[product.pk]), {"quantity": 50})
    response = client.get(reverse("cart:index"))
    assert response.context["lines"][0].quantity == 15
    response = client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1}, follow=True)
    assert "весь остаток" in response.content.decode()


def test_add_redirects_back_to_safe_next_only(client: Client, product: Product) -> None:
    response = client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1, "next": "/?page=1"})
    assert response["Location"] == "/?page=1"
    response = client.post(
        reverse("cart:add", args=[product.pk]), {"quantity": 1, "next": "https://evil.example/"}
    )
    assert response["Location"] == product.get_absolute_url()


def test_invalid_quantity_and_out_of_stock(client: Client, product: Product) -> None:
    response = client.post(reverse("cart:add", args=[product.pk]), {"quantity": 0}, follow=True)
    assert "Укажите количество" in response.content.decode()
    empty = ProductFactory.create(stock=0)
    response = client.post(reverse("cart:add", args=[empty.pk]), {"quantity": 1}, follow=True)
    assert "нет в наличии" in response.content.decode().lower()
    assert client.get(reverse("cart:add", args=[product.pk])).status_code == 405


def test_update_and_remove(client: Client, product: Product) -> None:
    client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1})
    response = client.post(reverse("cart:update", args=[product.pk]), {"quantity": 40}, follow=True)
    assert "Доступно только 15" in response.content.decode()
    assert response.context["lines"][0].quantity == 15
    response = client.post(reverse("cart:update", args=[product.pk]), {"quantity": 3}, follow=True)
    assert response.context["total"] == product.price * 3
    response = client.post(reverse("cart:remove", args=[product.pk]), follow=True)
    assert "Корзина пуста" in response.content.decode()


def test_cart_page_totals(client: Client, product: Product) -> None:
    client.post(reverse("cart:add", args=[product.pk]), {"quantity": 2})
    content = client.get(reverse("cart:index")).content.decode()
    assert 'data-testid="cart-total">11\u00a0980\u00a0₽<' in content
    assert 'data-testid="cart-qty">2<' in content


def test_guest_cart_merges_into_customer_cart_on_login(
    client: Client, customer: User, product: Product, customer_password: str
) -> None:
    other = ProductFactory.create(stock=5)
    CartItem.objects.create(user=customer, product=other, quantity=4)
    client.post(reverse("cart:add", args=[product.pk]), {"quantity": 2})
    client.post(reverse("cart:add", args=[other.pk]), {"quantity": 3})

    response = client.post(
        reverse("accounts:login"),
        {"username": customer.email, "password": customer_password},
    )
    assert response.status_code == 302
    stored = dict(CartItem.objects.filter(user=customer).values_list("product_id", "quantity"))
    assert stored == {product.pk: 2, other.pk: 5}
    assert client.get(reverse("cart:index")).context["cart_count"] == 7

    # после выхода корзина гостя пуста, после повторного входа — снова корзина покупателя
    client.post(reverse("accounts:logout"))
    assert client.get(reverse("cart:index")).context["cart_count"] == 0
    client.force_login(customer)
    assert client.get(reverse("cart:index")).context["cart_count"] == 7


def test_csrf_is_enforced(product: Product) -> None:
    csrf_client = Client(enforce_csrf_checks=True)
    response = csrf_client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1})
    assert response.status_code == 403
