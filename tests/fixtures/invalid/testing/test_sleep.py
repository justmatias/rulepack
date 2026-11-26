import time


def test_order_is_processed(order_queue):
    order_queue.submit("A-1")
    time.sleep(2)
    assert order_queue.processed("A-1")
