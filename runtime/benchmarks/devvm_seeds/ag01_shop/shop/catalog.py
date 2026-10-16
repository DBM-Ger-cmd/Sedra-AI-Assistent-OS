class Catalog:
    def __init__(self, items):
        self._items = {}
        for sku, item in items.items():
            self._items[sku] = {"name": item["name"], "price": int(item["price"]), "stock": int(item["stock"]), "category": item.get("category", "standard")}

    def get(self, sku):
        if sku not in self._items:
            raise KeyError("unknown_sku")
        return dict(self._items[sku])

    def stock(self, sku):
        return self.get(sku)["stock"]

    def take(self, sku, qty):
        self._items[sku]["stock"] -= qty
