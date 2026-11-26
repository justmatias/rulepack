import logging

from fixtures.valid.models import Order

logger = logging.getLogger(__name__)


class OrderNotFoundError(LookupError):
    pass


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order
        logger.info("Saved order %s", order.order_id)

    def get(self, order_id: str) -> Order:
        try:
            return self._orders[order_id]
        except KeyError as error:
            raise OrderNotFoundError(order_id) from error
