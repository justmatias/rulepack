import pytest

from fixtures.valid.models import Item


def test_item_rejects_a_negative_price():
    with pytest.raises(Exception):
        Item(name="pen", unit_price=-1.0, quantity=1)
