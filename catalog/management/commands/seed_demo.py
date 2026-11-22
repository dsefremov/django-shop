from typing import Any

from django.core.management.base import BaseCommand, CommandError

from catalog.demo import DemoDataError, load


class Command(BaseCommand):
    help = "Загружает демо-данные (каталог, пользователи, заказы). Существующие данные магазина удаляются."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            stats = load()
        except DemoDataError as exc:
            raise CommandError(str(exc)) from exc
        summary = ", ".join(f"{k}: {v}" for k, v in stats.items())
        self.stdout.write(self.style.SUCCESS(f"Демо-данные загружены ({summary})."))
