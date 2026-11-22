from typing import Any

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, UpdateView

from .forms import EmailAuthenticationForm, ProfileForm, RegistrationForm, ShopPasswordChangeForm
from .models import User


class ShopLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class RegisterView(CreateView[User, RegistrationForm]):
    template_name = "accounts/register.html"
    form_class = RegistrationForm

    def form_valid(self, form: RegistrationForm) -> HttpResponse:
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, "Добро пожаловать! Аккаунт создан.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self) -> str:
        url = self.request.POST.get("next") or self.request.GET.get("next") or ""
        if url and url_has_allowed_host_and_scheme(
            url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            return url
        return reverse("orders:list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context


class ProfileView(LoginRequiredMixin, SuccessMessageMixin[ProfileForm], UpdateView[User, ProfileForm]):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Профиль сохранён."

    def get_object(self, queryset: Any = None) -> User:
        user = self.request.user
        if not isinstance(user, User):
            raise PermissionDenied
        return user


class ShopPasswordChangeView(SuccessMessageMixin[ShopPasswordChangeForm], PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = ShopPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Пароль изменён."
