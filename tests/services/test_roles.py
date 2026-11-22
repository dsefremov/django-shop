import pytest
from django.contrib.auth.models import Group

from accounts.models import User
from accounts.roles import MANAGERS_GROUP, ensure_managers_group

pytestmark = pytest.mark.django_db


def test_managers_group_created_by_migrate_with_model_permissions_only() -> None:
    group = Group.objects.get(name=MANAGERS_GROUP)
    perms = {f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.all()}
    assert perms == {
        "catalog.view_category", "catalog.add_category", "catalog.change_category",
        "catalog.delete_category", "catalog.view_product", "catalog.add_product",
        "catalog.change_product", "catalog.delete_product", "orders.view_order",
        "orders.change_order", "orders.view_orderitem", "orders.view_paymentattempt",
    }  # fmt: skip
    assert not any(p.startswith(("auth.", "accounts.")) for p in perms)


def test_ensure_group_is_idempotent_and_repairs_permissions() -> None:
    group = ensure_managers_group()
    group.permissions.clear()
    assert ensure_managers_group().permissions.count() == 12
    assert Group.objects.filter(name=MANAGERS_GROUP).count() == 1


def test_manager_has_shop_permissions(manager: User) -> None:
    assert manager.has_perm("catalog.change_product")
    assert manager.has_perm("orders.change_order")
    assert not manager.has_perm("orders.delete_order")
    assert not manager.has_perm("orders.add_order")
    assert not manager.has_perm("accounts.view_user")
    assert not manager.has_perm("auth.change_group")
