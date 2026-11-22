"""
Демо-данные — тот же набор, что в laravel-shop, symphony-shop и bitrix-shop(-classic):
4 категории × 6 товаров (цены в рублях, остатки, картинки), менеджер магазина, два покупателя
и 5 заказов, оформленных и оплаченных через сервисы (с резервом остатка).
Пароли демо-учёток не хранятся в коде: их генерирует docker/secrets.sh в var/demo-users.json.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from accounts.roles import MANAGERS_GROUP, ensure_managers_group
from cart.models import CartItem
from orders.models import Order, OrderStatus
from orders.services import CheckoutData, pay, place_order, set_status

from .models import Category, Product
from .seed_image import make_png
from .slugs import make_slug

EMAIL_DOMAIN = "django-shop.test"


class CategoryData(TypedDict):
    color: tuple[int, int, int]
    description: str
    products: list[tuple[str, int, int]]


CATALOG: dict[str, CategoryData] = {
    "Электроника": {
        "color": (37, 99, 235),
        "description": "Гаджеты и аксессуары для дома и работы.",
        "products": [
            ("Беспроводные наушники Aero", 5990, 15),
            ("Смарт-часы Pulse 2", 12490, 8),
            ("Портативная колонка Wave", 4290, 20),
            ("Внешний аккумулятор 20 000 мА·ч", 2790, 30),
            ("Механическая клавиатура K87", 6990, 6),
            ("Веб-камера Full HD", 3490, 0),
        ],
    },
    "Книги": {
        "color": (180, 83, 9),
        "description": "Художественная и профессиональная литература.",
        "products": [
            ("«Чистый код», Роберт Мартин", 1290, 12),
            ("«Мастер и Маргарита», М. Булгаков", 690, 25),
            ("«Django: быстрый старт»", 1590, 10),
            ("«Война и мир», Л. Толстой (2 тома)", 1890, 7),
            ("«Алгоритмы. Построение и анализ»", 3490, 4),
            ("«Сто лет одиночества», Г. Маркес", 790, 0),
        ],
    },
    "Дом и кухня": {
        "color": (5, 150, 105),
        "description": "Посуда, текстиль и полезные мелочи.",
        "products": [
            ("Френч-пресс 1 л", 1490, 18),
            ("Набор ножей «Шеф»", 4990, 5),
            ("Чугунная сковорода 26 см", 3290, 9),
            ("Электрочайник Glass", 2490, 14),
            ("Плед флисовый 150×200", 1790, 22),
            ("Набор контейнеров, 6 шт.", 990, 40),
        ],
    },
    "Спорт": {
        "color": (190, 24, 93),
        "description": "Инвентарь для тренировок дома и на улице.",
        "products": [
            ("Коврик для йоги 6 мм", 1990, 16),
            ("Гантели 2 × 5 кг", 3990, 6),
            ("Скакалка скоростная", 590, 35),
            ("Фитнес-резинки, 5 шт.", 890, 28),
            ("Бутылка для воды 0,7 л", 690, 50),
            ("Рюкзак спортивный 25 л", 2990, 0),
        ],
    },
}

# key, имя, фамилия, менеджер
USERS: tuple[tuple[str, str, str, bool], ...] = (
    ("manager", "Менеджер", "магазина", True),
    ("customer", "Иван", "Петров", False),
    ("maria", "Мария", "Соколова", False),
)


class DemoDataError(Exception):
    pass


def load_credentials(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise DemoDataError(f"Нет файла {path}: запустите docker/secrets.sh")
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, *_ in USERS:
        entry = data.get(key)
        if not isinstance(entry, dict) or not entry.get("email") or not entry.get("password"):
            raise DemoDataError(f"В {path} нет учётки «{key}»: запустите docker/secrets.sh")
    return {k: {"email": str(v["email"]), "password": str(v["password"])} for k, v in data.items()}


def purge() -> None:
    Order.objects.all().delete()
    CartItem.objects.all().delete()
    for product in Product.objects.all():
        product.image.delete(save=False)
    Product.objects.all().delete()
    for category in Category.objects.all():
        category.image.delete(save=False)
    Category.objects.all().delete()


@transaction.atomic
def load(credentials_file: Path | None = None) -> dict[str, int]:
    creds = load_credentials(credentials_file or settings.DEMO_USERS_FILE)
    purge()

    products: list[Product] = []
    base_time = timezone.now() - timedelta(days=30)
    position = 100
    for category_name, data in CATALOG.items():
        slug = make_slug(category_name)
        category = Category(name=category_name, slug=slug, description=data["description"], position=position)
        category.image.save(f"{slug}.png", ContentFile(make_png(data["color"], _seed(slug), 400)), save=False)
        category.save()
        position += 100
        for name, price, stock in data["products"]:
            product_slug = make_slug(name)
            product = Product(
                category=category,
                name=name,
                slug=product_slug,
                description=(
                    f"{name} — товар из раздела «{category_name}». Демо-описание для локальной базы: "
                    "характеристики, комплектация и условия гарантии указываются здесь."
                ),
                price=Decimal(price),
                stock=stock,
            )
            product.image.save(
                f"{product_slug}.png",
                ContentFile(make_png(data["color"], _seed(product_slug))),
                save=False,
            )
            product.save()
            products.append(product)

    # Новизна: товары «добавлялись» по одному в день — сортировка «Сначала новые» стабильна.
    for index, product in enumerate(products):
        Product.objects.filter(pk=product.pk).update(
            created_at=base_time + timedelta(days=index % 24, minutes=index)
        )

    managers = ensure_managers_group()
    users: dict[str, User] = {}
    for key, first, last, is_manager in USERS:
        email, password = creds[key]["email"], creds[key]["password"]
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "first_name": first,
                "last_name": last,
                "is_staff": is_manager,
                "is_active": True,
            },
        )
        user.set_password(password)
        user.save()
        if is_manager:
            user.groups.set([managers])
        else:
            user.groups.set(Group.objects.none())
        users[key] = user

    customer, maria = users["customer"], users["maria"]
    _order(customer, [(products[0], 1), (products[8], 2)], "completed", timedelta(days=10))
    _order(customer, [(products[13], 1)], "paid", timedelta(days=3))
    _order(customer, [(products[19], 1), (products[22], 2)], "new", timedelta(days=1))
    _order(maria, [(products[3], 1)], "paid", timedelta(days=2))
    _order(maria, [(products[15], 1)], "declined", timedelta(hours=5))

    return {
        "categories": Category.objects.count(),
        "products": Product.objects.count(),
        "users": len(users),
        "orders": Order.objects.count(),
        "managers_group": Group.objects.filter(name=MANAGERS_GROUP).count(),
    }


def _seed(text: str) -> int:
    import zlib

    return zlib.crc32(text.encode())


def _order(user: User, lines: list[tuple[Product, int]], state: str, ago: timedelta) -> None:
    order = place_order(
        user,
        [(p.pk, q) for p, q in lines],
        CheckoutData(
            customer_name=user.get_full_name(),
            customer_email=user.email,
            customer_phone="+7 900 123-45-67",
            address="г. Москва, ул. Тверская, д. 1, кв. 10",
        ),
    )
    if state == "declined":
        pay(order, approve=False)
    elif state in {"paid", "completed"}:
        pay(order, approve=True)
    if state == "completed":
        set_status(order, OrderStatus.COMPLETED)
    when = timezone.now() - ago
    Order.objects.filter(pk=order.pk).update(
        created_at=when, updated_at=when, paid_at=when if state in {"paid", "completed"} else None
    )
    order.payment_attempts.update(created_at=when)
