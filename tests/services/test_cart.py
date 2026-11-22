import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest
from django.test import RequestFactory

from accounts.models import User
from cart.cart import SESSION_KEY, Cart, CartError, merge_session_cart_into_user
from cart.models import CartItem
from catalog.models import Product

from ..factories import ProductFactory

pytestmark = pytest.mark.django_db


def make_request(user: User | None = None) -> HttpRequest:
    request = RequestFactory().get("/")
    request.session = SessionStore()
    request.user = user or AnonymousUser()
    return request


def test_guest_cart_lives_in_session(product: Product) -> None:
    request = make_request()
    cart = Cart(request)
    assert cart.add(product, 2) == 2
    assert cart.add(product, 1) == 3
    assert request.session[SESSION_KEY] == {str(product.pk): 3}
    assert cart.count() == 3
    assert cart.total() == product.price * 3
    assert CartItem.objects.count() == 0


def test_quantity_capped_by_stock(product: Product) -> None:
    cart = Cart(make_request())
    assert cart.add(product, 100) == 15
    with pytest.raises(CartError, match="весь остаток"):
        cart.add(product, 1)
    assert cart.update(product, 40) == 15
    assert cart.update(product, 0) == 0
    assert cart.lines() == []


def test_out_of_stock_and_inactive_cannot_be_added() -> None:
    cart = Cart(make_request())
    with pytest.raises(CartError, match="нет в наличии"):
        cart.add(ProductFactory.create(stock=0))
    with pytest.raises(CartError, match="нет в наличии"):
        cart.add(ProductFactory.create(is_active=False))
    with pytest.raises(CartError, match="не меньше 1"):
        cart.add(ProductFactory.create(), 0)


def test_lines_skip_hidden_products_and_flag_stock_problems(product: Product) -> None:
    cart = Cart(make_request())
    hidden = ProductFactory.create(name="Скрытый")
    cart.add(product, 5)
    cart.add(hidden, 1)
    Product.objects.filter(pk=hidden.pk).update(is_active=False)
    Product.objects.filter(pk=product.pk).update(stock=3)
    lines = cart.lines()
    assert [line.product.pk for line in lines] == [product.pk]
    assert lines[0].exceeds_stock


def test_logged_in_cart_is_stored_in_db(customer: User, product: Product) -> None:
    cart = Cart(make_request(customer))
    cart.add(product, 2)
    assert CartItem.objects.get(user=customer).quantity == 2
    # новая «сессия» того же покупателя видит ту же корзину
    assert Cart(make_request(customer)).count() == 2
    cart.remove(product)
    assert not CartItem.objects.exists()


def test_merge_on_login_sums_and_caps(customer: User, product: Product) -> None:
    other = ProductFactory.create(stock=3)
    CartItem.objects.create(user=customer, product=product, quantity=10)
    request = make_request()
    guest = Cart(request)
    guest.add(product, 8)
    guest.add(other, 2)

    merge_session_cart_into_user(request, customer)

    assert SESSION_KEY not in request.session
    stored = dict(CartItem.objects.filter(user=customer).values_list("product_id", "quantity"))
    assert stored == {product.pk: 15, other.pk: 2}


def test_merge_with_empty_guest_cart_keeps_customer_cart(customer: User, product: Product) -> None:
    CartItem.objects.create(user=customer, product=product, quantity=1)
    merge_session_cart_into_user(make_request(), customer)
    assert CartItem.objects.get(user=customer).quantity == 1


def test_clear(customer: User, product: Product) -> None:
    guest_request = make_request()
    Cart(guest_request).add(product)
    Cart(guest_request).clear()
    assert Cart(guest_request).count() == 0
    cart = Cart(make_request(customer))
    cart.add(product)
    cart.clear()
    assert cart.count() == 0
