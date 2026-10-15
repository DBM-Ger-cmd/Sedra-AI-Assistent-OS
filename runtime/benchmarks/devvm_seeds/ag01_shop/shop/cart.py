class Cart:
    def __init__(self, catalog):
        self.catalog = catalog
        self._qty = {}

    def add(self, sku, qty=1):
        if qty < 1:
            raise ValueError("qty")
        self.catalog.get(sku)
        self._qty[sku] = self._qty.get(sku, 0) + qty

    def remove(self, sku):
        self._qty.pop(sku, None)

    def lines(self):
        out = []
        for sku in sorted(self._qty):
            item = self.catalog.get(sku)
            qty = self._qty[sku]
            out.append({"sku": sku, "qty": qty, "price": item["price"], "category": item["category"], "amount": item["price"] * qty})
        return out

    def subtotal(self):
        return sum(line["amount"] for line in self.lines())
