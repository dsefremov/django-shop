from typing import Any

from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.http import HttpRequest

from .models import User
from .roles import ensure_managers_group


@receiver(post_migrate)
def create_managers_group(sender: AppConfig, **kwargs: Any) -> None:
    # Права моделей создаются в post_migrate приложения auth; группа — после приложения orders.
    if sender.label == "orders":
        ensure_managers_group()


@receiver(user_logged_in)
def merge_cart_on_login(sender: type[User], request: HttpRequest | None, user: User, **kwargs: Any) -> None:
    if request is None:
        return
    from cart.cart import merge_session_cart_into_user

    merge_session_cart_into_user(request, user)
