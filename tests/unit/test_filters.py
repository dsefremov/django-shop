import pytest
from django.http import QueryDict

from catalog.filters import ProductFilter, sanitize
from catalog.models import Product
from orders.filters import OrderFilter
from orders.models import Order


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("ordering=-price&q=aero", {"ordering": "-price", "q": "aero"}),
        ("ordering=hack&q=aero", {"q": "aero"}),
        ("price_min=abc&in_stock=1", {"in_stock": "1"}),
        ("unknown=1&page=2", {}),
    ],
)
def test_catalog_sanitize_drops_invalid_and_unknown(query: str, expected: dict[str, str]) -> None:
    assert sanitize(QueryDict(query), ProductFilter, Product.objects.all()) == expected


def test_orders_sanitize_drops_bad_status_and_dates() -> None:
    data = QueryDict("status=nope&date_from=2026-13-40&ordering=-total&q=7")
    assert sanitize(data, OrderFilter, Order.objects.all()) == {"ordering": "-total", "q": "7"}
