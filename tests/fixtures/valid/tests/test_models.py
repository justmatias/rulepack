import pydantic
import pytest

from fixtures.valid.models import Item, Order, order_total


def test_total_sums_price_times_quantity_when_order_has_items() -> None:
    order = Order(
        order_id="A-1",
        items=[
            Item(name="pen", unit_price=2.0, quantity=3),
            Item(name="pad", unit_price=5.0, quantity=1),
        ],
    )

    assert order_total(order) == pytest.approx(11.0)


def test_item_rejects_price_when_negative() -> None:
    with pytest.raises(pydantic.ValidationError):
        Item(name="pen", unit_price=-1.0, quantity=1)
