from decimal import Decimal

import pytest

from catalog.slugs import make_slug
from catalog.templatetags.shop import plural_ru, rub, status_class

NB = "\u00a0"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("5990.00"), f"5{NB}990{NB}₽"),
        (Decimal("11980"), f"11{NB}980{NB}₽"),
        (Decimal("690"), f"690{NB}₽"),
        (Decimal("1290.50"), f"1{NB}290,50{NB}₽"),
        (Decimal("1234567.05"), f"1{NB}234{NB}567,05{NB}₽"),
        (0, f"0{NB}₽"),
        (None, ""),
    ],
)
def test_rub(value: object, expected: str) -> None:
    assert rub(value) == expected


@pytest.mark.parametrize(
    ("number", "expected"),
    [(1, "товар"), (2, "товара"), (5, "товаров"), (11, "товаров"), (21, "товар"), (24, "товара"),
     (112, "товаров"), (0, "товаров")],
)  # fmt: skip
def test_plural_ru(number: int, expected: str) -> None:
    assert plural_ru(number, "товар,товара,товаров") == expected


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Беспроводные наушники Aero", "besprovodnye-naushniki-aero"),
        ("Френч-пресс 1 л", "french-press-1-l"),
        ("Электроника", "elektronika"),
        ("Дом и кухня", "dom-i-kukhnya"),
        ("«Чистый код», Роберт Мартин", "chistyy-kod-robert-martin"),
        ("Плед флисовый 150×200", "pled-flisovyy-150200"),
    ],
)
def test_make_slug(text: str, slug: str) -> None:
    assert make_slug(text) == slug


def test_status_class_known_and_unknown() -> None:
    assert status_class("paid") == "badge-green"
    assert status_class("payment_declined") == "badge-red"
    assert status_class("whatever") == "badge-gray"
