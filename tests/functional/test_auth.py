import secrets

import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_register_logs_in_and_redirects_to_orders(client: Client) -> None:
    pw = secrets.token_urlsafe(14)
    response = client.post(
        reverse("accounts:register"),
        {
            "first_name": "Пётр",
            "last_name": "Покупателев",
            "email": "Petr@Example.test",
            "password1": pw,
            "password2": pw,
        },
        follow=True,
    )
    assert response.redirect_chain[-1][0] == reverse("orders:list")
    assert "Заказов пока нет." in response.content.decode()
    user = User.objects.get(email="petr@example.test")
    assert user.get_full_name() == "Пётр Покупателев"
    assert int(client.session["_auth_user_id"]) == user.pk


def test_register_validation(client: Client, customer: User) -> None:
    pw = secrets.token_urlsafe(14)
    response = client.post(
        reverse("accounts:register"),
        {"first_name": "", "email": customer.email.upper(), "password1": pw, "password2": pw + "x"},
    )
    form = response.context["form"]
    assert response.status_code == 200
    assert "first_name" in form.errors
    assert "уже зарегистрирован" in form.errors["email"][0]
    assert "password2" in form.errors


def test_login_with_email_and_next(client: Client, customer: User, customer_password: str) -> None:
    response = client.post(
        reverse("accounts:login"),
        {
            "username": customer.email.upper(),
            "password": customer_password,
            "next": "/checkout/",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == "/checkout/"


def test_login_rejects_bad_password_and_external_next(
    client: Client, customer: User, customer_password: str
) -> None:
    response = client.post(
        reverse("accounts:login"), {"username": customer.email, "password": secrets.token_hex(8)}
    )
    assert "Неверная эл. почта или пароль." in response.content.decode()
    response = client.post(
        reverse("accounts:login"),
        {
            "username": customer.email,
            "password": customer_password,
            "next": "https://evil.example/",
        },
    )
    assert response["Location"] == reverse("catalog:index")


def test_logout_requires_post(customer_client: Client) -> None:
    assert customer_client.get(reverse("accounts:logout")).status_code == 405
    response = customer_client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert "_auth_user_id" not in customer_client.session


def test_profile_update_and_unique_email(
    customer_client: Client, customer: User, other_customer: User
) -> None:
    response = customer_client.post(
        reverse("accounts:profile"),
        {"first_name": "Иван", "last_name": "Сидоров", "email": "new@example.test"},
        follow=True,
    )
    assert "Профиль сохранён." in response.content.decode()
    customer.refresh_from_db()
    assert (customer.last_name, customer.email) == ("Сидоров", "new@example.test")
    response = customer_client.post(
        reverse("accounts:profile"),
        {"first_name": "Иван", "last_name": "", "email": other_customer.email},
    )
    assert "уже занята" in response.content.decode()


def test_password_change(customer_client: Client, customer: User, customer_password: str) -> None:
    new = secrets.token_urlsafe(14)
    response = customer_client.post(
        reverse("accounts:password_change"),
        {"old_password": customer_password, "new_password1": new, "new_password2": new},
        follow=True,
    )
    assert "Пароль изменён." in response.content.decode()
    customer.refresh_from_db()
    assert customer.check_password(new)


@pytest.mark.parametrize("name", ["accounts:profile", "orders:list", "orders:checkout"])
def test_private_pages_redirect_guest_to_login(client: Client, name: str) -> None:
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:login") + "?next=")
