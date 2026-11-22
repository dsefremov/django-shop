from decimal import Decimal

from pytest_django.fixtures import Settings

from orders.payments import FakePaymentGateway, PaymentResult, get_gateway


def test_fake_gateway_approves_and_declines() -> None:
    gateway = FakePaymentGateway()
    ok = gateway.charge(7, Decimal("100"), approve=True)
    declined = gateway.charge(7, Decimal("100"), approve=False)
    assert ok.succeeded
    assert ok.reference.startswith("FAKE-7-")
    assert not declined.succeeded
    assert "отклонён" in declined.message
    assert ok.reference != declined.reference


def test_gateway_is_configurable(settings: Settings) -> None:
    assert isinstance(get_gateway(), FakePaymentGateway)
    settings.PAYMENT_GATEWAY = "tests.unit.test_payment_gateway.AlwaysDecline"
    assert isinstance(get_gateway(), AlwaysDecline)


class AlwaysDecline(FakePaymentGateway):
    def charge(self, order_id: int, amount: Decimal, *, approve: bool) -> PaymentResult:
        return super().charge(order_id, amount, approve=False)
