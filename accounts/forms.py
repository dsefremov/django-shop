from typing import Any

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordChangeForm,
)

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Эл. почта",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Неверная эл. почта или пароль.",
    }

    def clean(self) -> dict[str, Any]:
        username = self.cleaned_data.get("username")
        if username:
            self.cleaned_data["username"] = username.lower()
        return super().clean()


class RegistrationForm(BaseUserCreationForm[User]):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Имя", "last_name": "Фамилия", "email": "Эл. почта"}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["password1"].label = "Пароль"
        self.fields["password2"].label = "Подтверждение пароля"
        self.fields["email"].widget.attrs["autocomplete"] = "email"

    def clean_email(self) -> str:
        email = str(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с такой эл. почтой уже зарегистрирован.")
        return email


class ProfileForm(forms.ModelForm[User]):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Имя", "last_name": "Фамилия", "email": "Эл. почта"}

    def clean_email(self) -> str:
        email = str(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Эта эл. почта уже занята.")
        return email


class ShopPasswordChangeForm(PasswordChangeForm):
    pass
