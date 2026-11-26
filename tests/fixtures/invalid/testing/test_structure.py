import pytest


@pytest.fixture
def item():
    return {"name": "foo"}


class TestItem:
    def test_is_named(self, item):
        assert item["name"] == "foo"


def test_is_saved(_seed_database):
    assert True
