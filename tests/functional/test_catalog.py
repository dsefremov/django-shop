from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from catalog.models import Category, Product

from ..factories import CategoryFactory, ProductFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog() -> dict[str, Category]:
    sport = CategoryFactory.create(name="Спорт", slug="sport", position=200)
    books = CategoryFactory.create(name="Книги", slug="knigi", position=100)
    for i, (price, stock) in enumerate([(1990, 16), (3990, 6), (590, 35), (2990, 0)]):
        ProductFactory.create(
            category=sport,
            name=f"Спорт-товар {i}",
            slug=f"sport-{i}",
            price=Decimal(price),
            stock=stock,
            description="Инвентарь — товар из раздела «Спорт».",
        )
    for i in range(10):
        ProductFactory.create(
            category=books, name=f"Книга {i:02d}", slug=f"book-{i}", price=Decimal(700 + i * 100)
        )
    ProductFactory.create(category=books, name="Скрытая книга", slug="hidden", is_active=False)
    return {"sport": sport, "books": books}


def names(response: Any) -> list[str]:
    return [p.name for p in response.context["products"]]


def test_catalog_first_page_has_12_and_total(client: Client, catalog: dict[str, Category]) -> None:
    response = client.get(reverse("catalog:index"))
    assert response.status_code == 200
    assert len(response.context["products"]) == 12
    assert response.context["page_obj"].paginator.count == 14  # скрытый товар не считается
    content = response.content.decode()
    assert "Найдено: 14 товаров" in content
    assert "Скрытая книга" not in content
    assert [c.name for c in response.context["categories"]] == ["Книги", "Спорт"]


def test_pagination_second_page(client: Client, catalog: dict[str, Category]) -> None:
    response = client.get(reverse("catalog:index"), {"page": 2})
    assert len(response.context["products"]) == 2
    assert client.get(reverse("catalog:index"), {"page": 99}).status_code == 404


def test_category_filter_stock_and_sort_by_price_desc(client: Client, catalog: dict[str, Category]) -> None:
    url = reverse("catalog:category", kwargs={"slug": "sport"})
    response = client.get(url, {"in_stock": "1", "ordering": "-price"})
    assert names(response) == ["Спорт-товар 1", "Спорт-товар 0", "Спорт-товар 2"]
    assert response.context["category"].name == "Спорт"
    assert "<h1>Спорт</h1>" in response.content.decode()


@pytest.mark.parametrize(
    ("ordering", "first"),
    [
        ("name", "Книга 00"),
        ("price", "Спорт-товар 2"),
        ("-price", "Спорт-товар 1"),
        ("-created", "Книга 09"),
    ],
)
def test_sorting(client: Client, catalog: dict[str, Category], ordering: str, first: str) -> None:
    assert names(client.get(reverse("catalog:index"), {"ordering": ordering}))[0] == first


def test_unknown_sort_falls_back_to_name(client: Client, catalog: dict[str, Category]) -> None:
    response = client.get(reverse("catalog:index"), {"ordering": "DROP TABLE", "price_min": "x"})
    assert response.status_code == 200
    assert names(response)[0] == "Книга 00"


def test_search_by_name_and_description(client: Client, catalog: dict[str, Category]) -> None:
    assert len(names(client.get(reverse("catalog:index"), {"q": "книга 0"}))) == 10
    assert len(names(client.get(reverse("catalog:index"), {"q": "спорт"}))) == 4
    # % и _ ищутся буквально
    assert names(client.get(reverse("catalog:index"), {"q": "%"})) == []
    response = client.get(reverse("catalog:index"), {"q": "несуществующий"})
    assert 'data-testid="no-results"' in response.content.decode()


def test_price_range(client: Client, catalog: dict[str, Category]) -> None:
    response = client.get(reverse("catalog:index"), {"price_min": "1000", "price_max": "2000"})
    assert sorted(names(response)) == [f"Книга {i:02d}" for i in range(3, 10)] + ["Спорт-товар 0"]


def test_product_page(client: Client, product: Product) -> None:
    response = client.get(product.get_absolute_url())
    content = response.content.decode()
    assert response.status_code == 200
    assert "<h1>Беспроводные наушники Aero</h1>" in content
    assert "5\u00a0990\u00a0₽" in content
    assert "В наличии: 15 шт." in content
    assert 'data-testid="add-to-cart"' in content


def test_out_of_stock_product_has_no_add_button(client: Client) -> None:
    item = ProductFactory.create(stock=0)
    content = client.get(item.get_absolute_url()).content.decode()
    assert "Нет в наличии" in content
    assert 'data-testid="add-to-cart"' not in content


def test_hidden_product_and_unknown_category_404(client: Client) -> None:
    hidden = ProductFactory.create(is_active=False)
    assert client.get(hidden.get_absolute_url()).status_code == 404
    assert client.get(reverse("catalog:category", kwargs={"slug": "nope"})).status_code == 404
