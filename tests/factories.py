"""Фабрики factory_boy. Пароли — случайные (secrets), литералов паролей в тестах нет."""

import secrets
from decimal import Decimal

from factory.declarations import LazyAttribute, LazyFunction, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.helpers import post_generation

from accounts.models import User
from accounts.roles import ensure_managers_group
from catalog.models import Category, Product
from orders.models import Order, OrderItem, OrderStatus


def random_password() -> str:
    return secrets.token_urlsafe(16)


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = Sequence(lambda n: f"user{n}@example.test")
    first_name = "Иван"
    last_name = Sequence(lambda n: f"Покупатель{n}")
    password = LazyFunction(random_password)

    @classmethod
    def _create(cls, model_class: type[User], *args: object, **kwargs: object) -> User:
        password = str(kwargs.pop("password"))
        email = str(kwargs.pop("email"))
        return model_class.objects.create_user(email, password, **kwargs)


class ManagerFactory(UserFactory):
    is_staff = True
    first_name = "Менеджер"

    @post_generation
    def managers_group(obj: User, create: bool, extracted: object, **kwargs: object) -> None:  # noqa: N805
        if create:
            obj.groups.add(ensure_managers_group())


class CategoryFactory(DjangoModelFactory[Category]):
    class Meta:
        model = Category
        django_get_or_create = ("slug",)

    name = Sequence(lambda n: f"Категория {n}")
    slug = Sequence(lambda n: f"category-{n}")
    description = "Описание категории."


class ProductFactory(DjangoModelFactory[Product]):
    class Meta:
        model = Product

    category = SubFactory(CategoryFactory)
    name = Sequence(lambda n: f"Товар {n}")
    slug = Sequence(lambda n: f"product-{n}")
    description = LazyAttribute(lambda o: f"{o.name} — описание товара.")
    price = Decimal("1000.00")
    stock = 10
    is_active = True


class OrderFactory(DjangoModelFactory[Order]):
    class Meta:
        model = Order

    user = SubFactory(UserFactory)
    status = OrderStatus.NEW
    total = Decimal("1000.00")
    customer_name = "Иван Петров"
    customer_email = LazyAttribute(lambda o: o.user.email)
    customer_phone = "+7 900 123-45-67"
    address = "г. Москва, ул. Тверская, д. 1"


class OrderItemFactory(DjangoModelFactory[OrderItem]):
    class Meta:
        model = OrderItem

    order = SubFactory(OrderFactory)
    product = SubFactory(ProductFactory)
    product_name = LazyAttribute(lambda o: o.product.name)
    price = LazyAttribute(lambda o: o.product.price)
    quantity = 1
