from collections.abc import Callable
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import User
from catalog.models import Product
from orders.models import Order, OrderStatus
from orders.services import pay

from ..factories import CategoryFactory, ProductFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager_client(client: Client, manager: User) -> Client:
    client.force_login(manager)
    return client


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:index",
        "admin:catalog_product_changelist",
        "admin:catalog_product_add",
        "admin:catalog_category_changelist",
        "admin:orders_order_changelist",
    ],
)
def test_manager_sees_shop_admin(manager_client: Client, url_name: str) -> None:
    assert manager_client.get(reverse(url_name)).status_code == 200


@pytest.mark.parametrize(
    "url_name",
    ["admin:accounts_user_changelist", "admin:auth_group_changelist", "admin:orders_order_add"],
)
def test_manager_has_no_user_management_or_order_creation(manager_client: Client, url_name: str) -> None:
    assert manager_client.get(reverse(url_name)).status_code == 403


def test_admin_index_lists_only_shop_models_for_manager(manager_client: Client) -> None:
    content = manager_client.get(reverse("admin:index")).content.decode()
    assert "Товары" in content
    assert "Заказы" in content
    assert "Пользователи" not in content
    assert "Группы" not in content


def test_customer_and_guest_cannot_enter_admin(client: Client, customer: User) -> None:
    url = reverse("admin:catalog_product_changelist")
    assert client.get(url)["Location"].startswith(reverse("admin:login"))
    client.force_login(customer)
    assert client.get(url)["Location"].startswith(reverse("admin:login"))


def test_superuser_sees_users(client: Client) -> None:
    admin = User.objects.create_superuser("root@example.test", password=None)
    client.force_login(admin)
    assert client.get(reverse("admin:accounts_user_changelist")).status_code == 200


def test_product_changelist_search_and_filters(manager_client: Client) -> None:
    kitchen = CategoryFactory.create(name="Дом и кухня", slug="dom")
    ProductFactory.create(category=kitchen, name="Набор ножей «Шеф»")
    ProductFactory.create(category=kitchen, name="Набор контейнеров, 6 шт.", stock=0)
    ProductFactory.create(name="Френч-пресс 1 л")
    url = reverse("admin:catalog_product_changelist")
    response = manager_client.get(url, {"q": "Набор"})
    assert response.context["cl"].result_count == 2
    assert manager_client.get(url, {"stock": "out"}).context["cl"].result_count == 1
    assert manager_client.get(url, {"category__id__exact": kitchen.pk}).context["cl"].result_count == 2


def test_manager_creates_and_edits_product(manager_client: Client) -> None:
    category = CategoryFactory.create()
    response = manager_client.post(
        reverse("admin:catalog_product_add"),
        {
            "category": category.pk,
            "name": "Новый товар",
            "slug": "novyy-tovar",
            "description": "Описание",
            "price": "1490.00",
            "stock": "7",
            "is_active": "on",
        },
    )
    assert response.status_code == 302, response.context["adminform"].form.errors if response.context else ""
    product = Product.objects.get(slug="novyy-tovar")
    assert (product.price, product.stock) == (Decimal(1490), 7)
    response = manager_client.post(
        reverse("admin:catalog_product_change", args=[product.pk]),
        {
            "category": category.pk,
            "name": "Новый товар",
            "slug": "novyy-tovar",
            "description": "",
            "price": "0",
            "stock": "-1",
        },
    )
    assert response.status_code == 200
    assert {"price", "stock"} <= set(response.context["adminform"].form.errors)


def test_order_changelist_filters_and_sorting(
    manager_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    cheap = make_order(customer, (product, 1))
    pricey = make_order(customer, (product, 3))
    make_order(customer, (product, 1))
    pay(cheap, approve=True)
    pay(pricey, approve=True)
    url = reverse("admin:orders_order_changelist")
    response = manager_client.get(url, {"status__exact": "paid", "o": "-5"})
    assert [o.pk for o in response.context["cl"].result_list] == [pricey.pk, cheap.pk]
    response = manager_client.get(url, {"status__exact": "paid", "o": "5"})
    assert [o.pk for o in response.context["cl"].result_list] == [cheap.pk, pricey.pk]
    assert "17\u00a0970\u00a0₽" in response.content.decode()
    assert manager_client.get(url, {"q": "наушники"}).context["cl"].result_count == 3
    assert manager_client.get(url, {"q": str(cheap.pk)}).context["cl"].result_count == 1


def test_order_detail_is_read_only_status(
    manager_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    response = manager_client.get(reverse("admin:orders_order_change", args=[order.pk]))
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert "status" not in form.fields  # статус меняется только действиями
    assert "Беспроводные наушники Aero" in response.content.decode()


def test_admin_actions_change_status_and_return_stock_once(
    manager_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    paid = make_order(customer, (product, 2))
    pay(paid, approve=True)
    fresh = make_order(customer, (product, 1))
    url = reverse("admin:orders_order_changelist")

    response = manager_client.post(
        url, {"action": "mark_processing", "_selected_action": [paid.pk, fresh.pk]}, follow=True
    )
    content = response.content.decode()
    assert "Статус «В работе»: 1" in content
    assert "нельзя перейти" in content
    paid.refresh_from_db()
    assert paid.status == OrderStatus.PROCESSING

    for _ in range(2):
        manager_client.post(url, {"action": "mark_cancelled", "_selected_action": [paid.pk, fresh.pk]})
    product.refresh_from_db()
    assert product.stock == 15
    assert set(Order.objects.values_list("status", flat=True)) == {OrderStatus.CANCELLED}

    response = manager_client.post(
        url, {"action": "mark_completed", "_selected_action": [paid.pk]}, follow=True
    )
    assert "нельзя перейти" in response.content.decode()


def test_manager_cannot_delete_orders(
    manager_client: Client, customer: User, product: Product, make_order: Callable[..., Order]
) -> None:
    order = make_order(customer, (product, 1))
    assert manager_client.get(reverse("admin:orders_order_delete", args=[order.pk])).status_code == 403
    actions = (
        manager_client.get(reverse("admin:orders_order_changelist"))
        .context["action_form"]
        .fields["action"]
        .choices
    )
    assert "delete_selected" not in [value for value, _ in actions]
