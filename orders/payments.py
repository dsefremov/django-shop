"""
Платёжный шлюз-заглушка. Деньги не списываются: решение («оплатить» или «отказ») передаёт
покупатель кнопкой на странице заказа. Интерфейс позволяет подменить шлюз в настройках.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class PaymentResult:
    succeeded: bool
    reference: str
    message: str


class PaymentGateway(Protocol):
    def charge(self, order_id: int, amount: Decimal, *, approve: bool) -> PaymentResult: ...


class FakePaymentGateway:
    def charge(self, order_id: int, amount: Decimal, *, approve: bool) -> PaymentResult:
        reference = f"FAKE-{order_id}-{secrets.token_hex(4).upper()}"
        if approve:
            return PaymentResult(True, reference, "Оплата прошла успешно.")
        return PaymentResult(False, reference, "Платёж отклонён банком (тестовый отказ).")


def get_gateway() -> PaymentGateway:
    path = getattr(settings, "PAYMENT_GATEWAY", "orders.payments.FakePaymentGateway")
    gateway: PaymentGateway = import_string(path)()
    return gateway
