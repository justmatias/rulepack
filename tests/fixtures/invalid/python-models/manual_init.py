class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email


class Item:
    def __init__(self, name: str, quantity: int = 1) -> None:
        self.name = name
        self.quantity = quantity
