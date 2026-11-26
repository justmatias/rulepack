def do_work(callback):
    try:
        return callback()
    except:
        return None
