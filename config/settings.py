"""
Настройки Django Shop.

Секретов в коде нет: SECRET_KEY и пароль БД читаются из файлов, которые генерирует
docker/secrets.sh в var/secrets (каталог вне git). Пути к файлам и остальное — из окружения.
"""

import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

# Generic-аннотации классов Django (ModelAdmin[Product], ListView[Order] …) во время выполнения.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def read_secret(env_name: str, default_path: Path, *, required: bool = True) -> str:
    """Секрет из файла: путь в переменной `env_name` или файл по умолчанию в var/secrets."""
    path = Path(env(env_name, str(default_path)))
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    if required:
        raise ImproperlyConfigured(f"Нет файла {path}: запустите docker/secrets.sh")
    return ""


SECRETS_DIR = BASE_DIR / "var" / "secrets"

SECRET_KEY = read_secret("DJANGO_SECRET_KEY_FILE", SECRETS_DIR / "secret-key")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_filters",
    "accounts",
    "catalog",
    "cart",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cart.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "django_shop"),
        "USER": env("DB_USER", "shop"),
        "PASSWORD": read_secret("DB_PASSWORD_FILE", SECRETS_DIR / "db-password", required=False),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "54317"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "catalog:index"
LOGOUT_REDIRECT_URL = "catalog:index"

LANGUAGE_CODE = "ru"
LANGUAGES = [("ru", "Русский")]
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(env("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

# За nginx: схема и хост из заголовков прокси (только локальный стенд, порт с хостом).
USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Магазин
CATALOG_PAGE_SIZE = 12
ORDERS_PAGE_SIZE = 10
DEMO_USERS_FILE = Path(env("DEMO_USERS_FILE", str(BASE_DIR / "var" / "demo-users.json")))
ADMIN_PASSWORD_FILE = Path(env("ADMIN_PASSWORD_FILE", str(BASE_DIR / "var" / "admin-password")))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
