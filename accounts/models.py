from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class EmailUserManager(UserManager["User"]):
    """Менеджер пользователей, у которых логин — эл. почта (поля username нет)."""

    use_in_migrations = True

    def _create_user_with_email(self, email: str, password: str | None, **extra_fields: Any) -> User:
        if not email:
            raise ValueError("Нужна эл. почта")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(  # type: ignore[override]
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user_with_email(email, password, **extra_fields)

    def create_superuser(  # type: ignore[override]
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user_with_email(email, password, **extra_fields)


class User(AbstractUser):
    """Пользователь магазина: вход по эл. почте, имя и фамилия — для оформления заказа."""

    username = None  # type: ignore[assignment]
    email = models.EmailField("эл. почта", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[EmailUserManager] = EmailUserManager()

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ("email",)

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.email
