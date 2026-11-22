from collections.abc import Callable
from decimal import Decimal

import pytest
from django.test import Client

from accounts.models import User
from catalog.models import Product
from orders.models import Order
from orders.services import CheckoutData, place_order

from .factories import CategoryFactory, ManagerFactory, ProductFactory, UserFactory, random_password


@pytest.fixture
def customer_password() -> str:
    """Случайный пароль покупателя для входа через форму (литералов паролей в тестах нет)."""
    return random_password()


@pytest.fixture
def customer(db: None, customer_password: str) -> User:
    return UserFactory.create(
        first_name="Иван", last_name="Петров", email="ivan@example.test", password=customer_password
    )


@pytest.fixture
def other_customer(db: None) -> User:
    return UserFactory.create(first_name="Мария", last_name="Соколова", email="maria@example.test")


@pytest.fixture
def manager(db: None) -> User:
    return ManagerFactory.create(email="manager@example.test")


@pytest.fixture
def product(db: None) -> Product:
    category = CategoryFactory.create(name="Электроника", slug="elektronika")
    return ProductFactory.create(
        category=category,
        name="Беспроводные наушники Aero",
        slug="besprovodnye-naushniki-aero",
        price=Decimal("5990.00"),
        stock=15,
    )


@pytest.fixture
def customer_client(client: Client, customer: User) -> Client:
    client.force_login(customer)
    return client


@pytest.fixture
def checkout_data() -> CheckoutData:
    return CheckoutData(
        customer_name="Иван Петров",
        customer_email="ivan@example.test",
        customer_phone="+7 900 555-12-34",
        address="г. Москва, ул. Арбат, д. 10",
    )


@pytest.fixture
def make_order(checkout_data: CheckoutData) -> Callable[..., Order]:
    def _make(user: User, *lines: tuple[Product, int]) -> Order:
        return place_order(user, [(p.pk, q) for p, q in lines], checkout_data)

    return _make
