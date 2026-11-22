from collections.abc import Callable
from decimal import Decimal

import pytest

from accounts.models import User
from catalog.models import Product
from orders.models import Order, OrderStatus
from orders.services import CheckoutData, OrderError, OutOfStockError, place_order

from ..factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_place_order_reserves_stock_and_snapshots_prices(
    customer: User, product: Product, checkout_data: CheckoutData
) -> None:
    book = ProductFactory.create(name="Книга", price=Decimal("690.00"), stock=3)
    order = place_order(customer, [(product.pk, 2), (book.pk, 1)], checkout_data)

    assert order.status == OrderStatus.NEW
    assert order.total == Decimal("12670.00")
    assert order.customer_phone == "+7 900 555-12-34"
    items = list(order.items.order_by("product_name"))
    assert [(i.product_name, i.price, i.quantity) for i in items] == [
        ("Беспроводные наушники Aero", Decimal("5990.00"), 2),
        ("Книга", Decimal("690.00"), 1),
    ]
    product.refresh_from_db()
    book.refresh_from_db()
    assert (product.stock, book.stock) == (13, 2)


def test_snapshot_survives_price_change(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    Product.objects.filter(pk=product.pk).update(price=Decimal("1.00"), name="Переименован")
    item = order.items.get()
    assert (item.product_name, item.price) == ("Беспроводные наушники Aero", Decimal("5990.00"))


def test_duplicate_lines_are_summed(customer: User, product: Product, checkout_data: CheckoutData) -> None:
    order = place_order(customer, [(product.pk, 1), (product.pk, 2)], checkout_data)
    assert order.items.get().quantity == 3
    product.refresh_from_db()
    assert product.stock == 12


def test_not_enough_stock_creates_nothing(
    customer: User, product: Product, checkout_data: CheckoutData
) -> None:
    other = ProductFactory.create(stock=1)
    with pytest.raises(OutOfStockError) as exc:
        place_order(customer, [(product.pk, 1), (other.pk, 2)], checkout_data)
    assert other.name in str(exc.value)
    assert Order.objects.count() == 0
    product.refresh_from_db()
    other.refresh_from_db()
    assert (product.stock, other.stock) == (15, 1)


def test_inactive_or_missing_product_is_rejected(customer: User, checkout_data: CheckoutData) -> None:
    hidden = ProductFactory.create(is_active=False, stock=5)
    with pytest.raises(OutOfStockError):
        place_order(customer, [(hidden.pk, 1)], checkout_data)
    with pytest.raises(OutOfStockError, match="товар #999999"):
        place_order(customer, [(999999, 1)], checkout_data)


def test_empty_cart_is_rejected(customer: User, checkout_data: CheckoutData) -> None:
    with pytest.raises(OrderError, match="Корзина пуста"):
        place_order(customer, [], checkout_data)
    with pytest.raises(OrderError, match="Корзина пуста"):
        place_order(customer, [(1, 0)], checkout_data)


def test_exact_last_items_can_be_bought(customer: User, checkout_data: CheckoutData) -> None:
    last = ProductFactory.create(stock=2)
    place_order(customer, [(last.pk, 2)], checkout_data)
    last.refresh_from_db()
    assert last.stock == 0
    with pytest.raises(OutOfStockError):
        place_order(customer, [(last.pk, 1)], checkout_data)
