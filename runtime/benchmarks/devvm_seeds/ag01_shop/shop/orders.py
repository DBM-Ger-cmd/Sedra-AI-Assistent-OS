from .tax import tax_for


class OrderBook:
    def __init__(self, catalog, rules=None):
        self.catalog = catalog
        self.rules = rules
        self.orders = []

    def place(self, cart):
        lines = cart.lines()
        if not lines:
            raise ValueError("empty_cart")
        out_lines = []
        for line in lines:
            discount = self.rules.line_discount(line) if self.rules else 0
            net = line["amount"] - discount
            out_lines.append({**line, "discount": discount, "net": net, "tax": tax_for(line["category"], net)})
        totals = {"subtotal": sum(l["amount"] for l in out_lines), "discount": sum(l["discount"] for l in out_lines),
                  "net": sum(l["net"] for l in out_lines), "tax": sum(l["tax"] for l in out_lines)}
        totals["total"] = totals["net"] + totals["tax"]
        order = {"number": len(self.orders) + 1, "lines": out_lines, "totals": totals}
        for line in lines:
            self.catalog.take(line["sku"], line["qty"])
        self.orders.append(order)
        return order
