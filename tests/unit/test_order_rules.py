import pytest

from orders.models import TRANSITIONS, Order, OrderStatus


@pytest.mark.parametrize(
    ("status", "payable", "cancellable"),
    [
        (OrderStatus.NEW, True, True),
        (OrderStatus.PAYMENT_DECLINED, True, True),
        (OrderStatus.PAID, False, False),
        (OrderStatus.PROCESSING, False, False),
        (OrderStatus.COMPLETED, False, False),
        (OrderStatus.CANCELLED, False, False),
    ],
)
def test_payable_and_cancellable(status: str, payable: bool, cancellable: bool) -> None:
    order = Order(status=status)
    assert order.is_payable is payable
    assert order.can_cancel is cancellable


def test_transitions_cover_every_status_and_final_states_are_closed() -> None:
    assert set(TRANSITIONS) == set(OrderStatus.values)
    assert TRANSITIONS[OrderStatus.COMPLETED] == frozenset()
    assert TRANSITIONS[OrderStatus.CANCELLED] == frozenset()
    # Оплата и отказ — только через PaymentService, не через смену статуса.
    for targets in TRANSITIONS.values():
        assert OrderStatus.PAID not in targets
        assert OrderStatus.PAYMENT_DECLINED not in targets


def test_status_labels_in_russian() -> None:
    assert OrderStatus.NEW.label == "Новый"
    assert OrderStatus.PAID.label == "Оплачен"
    assert OrderStatus.PAYMENT_DECLINED.label == "Оплата отклонена"
    assert OrderStatus.CANCELLED.label == "Отменён"
