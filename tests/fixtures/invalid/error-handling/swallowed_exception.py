def do_work(callback):
    try:
        callback()
    except Exception:
        pass


def do_other_work(callback):
    try:
        callback()
    except Exception as error:
        pass
