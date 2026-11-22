from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django import template

register = template.Library()

NBSP = "\u00a0"


@register.filter
def rub(value: Any) -> str:
    """5990 → «5 990 ₽», 1290.50 → «1 290,50 ₽» (неразрывные пробелы)."""
    if value is None or value == "":
        return ""
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole = int(amount)
    kopecks = int((amount - whole) * 100)
    text = f"{whole:,}".replace(",", NBSP)
    if kopecks:
        text += f",{kopecks:02d}"
    return f"{text}{NBSP}₽"


@register.filter
def plural_ru(number: int, forms: str) -> str:
    """{{ n|plural_ru:"товар,товара,товаров" }} → «товара» для 24."""
    one, few, many = forms.split(",")
    n = abs(int(number))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


@register.simple_tag
def status_class(status: str) -> str:
    return {
        "new": "badge-amber",
        "paid": "badge-green",
        "payment_declined": "badge-red",
        "processing": "badge-blue",
        "completed": "badge-gray",
        "cancelled": "badge-muted",
    }.get(status, "badge-gray")


@register.filter
def input_widget(field: Any, extra: str = "") -> str:
    """Рендер виджета поля с классом .input (у чекбоксов — свой класс)."""
    widget = field.field.widget
    if getattr(widget, "input_type", "") == "checkbox":
        css = "size-4 rounded border-neutral-300"
    elif widget.__class__.__name__ == "Select":
        css = "input pr-8"
    else:
        css = "input"
    if field.errors:
        css += " border-red-400"
    attrs = {"class": f"{css} {extra}".strip()}
    if field.errors:
        attrs["aria-invalid"] = "true"
    return str(field.as_widget(attrs=attrs))
