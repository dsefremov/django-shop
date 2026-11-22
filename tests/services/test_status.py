from collections.abc import Callable

import pytest

from accounts.models import User
from catalog.models import Product
from orders.models import Order, OrderStatus
from orders.services import OrderError, cancel, pay, set_status

from ..factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_cancel_returns_stock_exactly_once(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    other = ProductFactory.create(stock=4)
    order = make_order(customer, (product, 2), (other, 3))
    product.refresh_from_db()
    other.refresh_from_db()
    assert (product.stock, other.stock) == (13, 1)

    cancel(order)
    cancel(order)  # повторная отмена — без изменений
    set_status(order, OrderStatus.CANCELLED)

    order.refresh_from_db()
    product.refresh_from_db()
    other.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert order.stock_returned_at is not None
    assert (product.stock, other.stock) == (15, 4)


def test_cancel_paid_order_returns_stock(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    pay(order, approve=True)
    set_status(order, OrderStatus.PROCESSING)
    cancel(order)
    product.refresh_from_db()
    assert product.stock == 15


def test_cancel_after_decline_returns_stock(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 3))
    pay(order, approve=False)
    cancel(order)
    product.refresh_from_db()
    assert product.stock == 15


def test_stock_returned_once_even_if_product_deleted(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    gone = ProductFactory.create(stock=2)
    order = make_order(customer, (product, 1), (gone, 1))
    gone.delete()
    cancel(order)
    product.refresh_from_db()
    assert product.stock == 15
    assert order.items.count() == 2  # снимок позиций остался


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ((), OrderStatus.PROCESSING),
        ((), OrderStatus.COMPLETED),
        (("pay", OrderStatus.COMPLETED), OrderStatus.PROCESSING),
        (("pay", OrderStatus.COMPLETED), OrderStatus.CANCELLED),
        (("cancel",), OrderStatus.PROCESSING),
    ],
)
def test_forbidden_transitions(
    customer: User,
    product: Product,
    make_order: Callable[..., Order],
    path: tuple[str, ...],
    target: str,
) -> None:
    order = make_order(customer, (product, 1))
    if "pay" in path:
        pay(order, approve=True)
        set_status(order, path[1])
    if "cancel" in path:
        cancel(order)
    before = Order.objects.get(pk=order.pk).status
    with pytest.raises(OrderError, match="нельзя перейти"):
        set_status(order, target)
    assert Order.objects.get(pk=order.pk).status == before


def test_unknown_status_rejected(customer: User, product: Product, make_order: Callable[..., Order]) -> None:
    order = make_order(customer, (product, 1))
    with pytest.raises(OrderError, match="Неизвестный статус"):
        set_status(order, "teleported")


def test_paid_to_processing_to_completed(
    customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    pay(order, approve=True)
    assert set_status(order, OrderStatus.PROCESSING).status == OrderStatus.PROCESSING
    assert set_status(order, OrderStatus.COMPLETED).status == OrderStatus.COMPLETED
    product.refresh_from_db()
    assert product.stock == 14
