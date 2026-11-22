"""Гонка за последний товар: два покупателя одновременно оформляют заказ на последнюю штуку."""

import threading
from decimal import Decimal

import pytest
from django.db import connection

from accounts.models import User
from orders.models import Order
from orders.services import CheckoutData, OutOfStockError, place_order

from ..factories import ProductFactory, UserFactory


@pytest.mark.django_db(transaction=True)
def test_only_one_buyer_gets_the_last_item() -> None:
    last = ProductFactory.create(name="Последний", price=Decimal("100.00"), stock=1)
    buyers: list[User] = [
        UserFactory.create(),
        UserFactory.create(),
        UserFactory.create(),
        UserFactory.create(),
    ]
    barrier = threading.Barrier(len(buyers))
    results: list[str] = []
    lock = threading.Lock()

    def buy(user: User) -> None:
        try:
            barrier.wait(timeout=10)
            data = CheckoutData(user.get_full_name(), user.email, "+7 900 000-00-00", "Москва")
            place_order(user, [(last.pk, 1)], data)
            outcome = "ok"
        except OutOfStockError:
            outcome = "out"
        finally:
            connection.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=buy, args=(u,)) for u in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(results) == ["ok", "out", "out", "out"]
    last.refresh_from_db()
    assert last.stock == 0
    assert Order.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_parallel_buyers_never_oversell() -> None:
    item = ProductFactory.create(stock=5)
    buyers = [UserFactory.create() for _ in range(8)]
    barrier = threading.Barrier(len(buyers))
    ok = []
    lock = threading.Lock()

    def buy(user: User) -> None:
        try:
            barrier.wait(timeout=10)
            place_order(user, [(item.pk, 1)], CheckoutData("Имя", user.email, "+7 900 000-00-00", "Москва"))
            with lock:
                ok.append(user.pk)
        except OutOfStockError:
            pass
        finally:
            connection.close()

    threads = [threading.Thread(target=buy, args=(u,)) for u in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    item.refresh_from_db()
    assert len(ok) == 5
    assert item.stock == 0
