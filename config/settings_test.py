"""
Настройки для pytest и статических проверок: отдельный сервер PostgreSQL для тестов
(порт 54318 локально, service-контейнер в CI). Пароль — из var/secrets/test-db-password,
если файла нет (CI с trust-аутентификацией) — пустой.
"""

import tempfile
from pathlib import Path

from .settings import *  # noqa: F403
from .settings import SECRETS_DIR, env, read_secret

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("TEST_DB_NAME", "django_shop"),
        "USER": env("TEST_DB_USER", "shop"),
        "PASSWORD": read_secret("TEST_DB_PASSWORD_FILE", SECRETS_DIR / "test-db-password", required=False),
        "HOST": env("TEST_DB_HOST", "127.0.0.1"),
        "PORT": env("TEST_DB_PORT", "54318"),
        "TEST": {"NAME": "test_django_shop"},
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="django-shop-media-"))
DEMO_USERS_FILE = MEDIA_ROOT / "demo-users.json"
ADMIN_PASSWORD_FILE = MEDIA_ROOT / "admin-password"
LOGGING = {"version": 1, "disable_existing_loggers": False}
