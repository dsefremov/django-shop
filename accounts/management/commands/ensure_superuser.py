from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

ADMIN_EMAIL = "admin@django-shop.test"


class Command(BaseCommand):
    help = (
        "Создаёт или обновляет суперпользователя admin@django-shop.test; пароль — из файла "
        "ADMIN_PASSWORD_FILE (var/admin-password, генерирует docker/secrets.sh). Пароль не печатается."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        path = settings.ADMIN_PASSWORD_FILE
        if not path.is_file():
            raise CommandError(f"Нет файла {path}: запустите docker/secrets.sh")
        password = path.read_text(encoding="utf-8").strip()
        user, created = User.objects.get_or_create(
            email=ADMIN_EMAIL, defaults={"first_name": "Администратор"}
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        verb = "создан" if created else "обновлён"
        self.stdout.write(self.style.SUCCESS(f"Суперпользователь {ADMIN_EMAIL} {verb}."))
