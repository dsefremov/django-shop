import json
import secrets
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django.fixtures import Settings

from accounts.models import User
from accounts.roles import MANAGERS_GROUP
from catalog.demo import CATALOG
from catalog.models import Category, Product
from orders.models import Order, OrderStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo_users(settings: Settings, tmp_path: Path) -> dict[str, dict[str, str]]:
    users = {
        key: {"email": f"{key}@django-shop.test", "password": secrets.token_urlsafe(12)}
        for key in ("manager", "customer", "maria")
    }
    path = tmp_path / "demo-users.json"
    path.write_text(json.dumps(users), encoding="utf-8")
    settings.DEMO_USERS_FILE = path
    return users


def test_seed_loads_same_dataset_as_other_shops(demo_users: dict[str, dict[str, str]]) -> None:
    call_command("seed_demo", verbosity=0)
    call_command("seed_demo", verbosity=0)  # повторный запуск — то же состояние

    assert list(Category.objects.values_list("name", flat=True)) == list(CATALOG)
    assert Product.objects.count() == 24
    aero = Product.objects.get(slug="besprovodnye-naushniki-aero")
    assert aero.price == Decimal("5990.00")
    assert aero.stock == 14  # 15 по данным, 1 шт. в выполненном демо-заказе
    assert aero.image.name.endswith(".png")
    assert Product.objects.filter(stock=0).count() == 3

    customer = User.objects.get(email="customer@django-shop.test")
    assert customer.get_full_name() == "Иван Петров"
    assert customer.check_password(demo_users["customer"]["password"])
    manager = User.objects.get(email="manager@django-shop.test")
    assert manager.is_staff
    assert not manager.is_superuser
    assert manager.groups.filter(name=MANAGERS_GROUP).exists()

    assert Order.objects.count() == 5
    assert sorted(customer.orders.values_list("status", flat=True)) == sorted(
        [OrderStatus.COMPLETED, OrderStatus.PAID, OrderStatus.NEW]
    )
    maria = User.objects.get(email="maria@django-shop.test")
    assert sorted(maria.orders.values_list("status", flat=True)) == sorted(
        [OrderStatus.PAID, OrderStatus.PAYMENT_DECLINED]
    )
    assert Order.objects.filter(status=OrderStatus.PAID).count() == 2


def test_seed_requires_credentials_file(settings: Settings, tmp_path: Path) -> None:
    settings.DEMO_USERS_FILE = tmp_path / "missing.json"
    with pytest.raises(CommandError, match=r"secrets\.sh"):
        call_command("seed_demo", verbosity=0)


def test_ensure_superuser_reads_password_file(settings: Settings, tmp_path: Path) -> None:
    secret = secrets.token_urlsafe(12)
    path = tmp_path / "admin-password"
    path.write_text(secret + "\n", encoding="utf-8")
    settings.ADMIN_PASSWORD_FILE = path
    call_command("ensure_superuser", verbosity=0)
    call_command("ensure_superuser", verbosity=0)
    admin = User.objects.get(email="admin@django-shop.test")
    assert admin.is_superuser
    assert admin.is_staff
    assert admin.check_password(secret)
    settings.ADMIN_PASSWORD_FILE = tmp_path / "nope"
    with pytest.raises(CommandError):
        call_command("ensure_superuser", verbosity=0)
