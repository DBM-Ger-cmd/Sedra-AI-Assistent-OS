from .tax import tax_for


def _shares(total, nets):
    whole = sum(nets)
    if not whole:
        return [0] * len(nets)
    shares = [total * n // whole for n in nets]
    order = sorted(range(len(nets)), key=lambda i: (-nets[i], i))
    for k in range(total - sum(shares)):
        shares[order[k]] += 1
    return shares


class OrderBook:
    def __init__(self, catalog, rules=None, coupons=None):
        self.catalog = catalog
        self.rules = rules
        self.coupons = coupons
        self.orders = []

    def place(self, cart, coupon=None):
        lines = cart.lines()
        if not lines:
            raise ValueError("empty_cart")
        if any(line["qty"] > self.catalog.stock(line["sku"]) for line in lines):
            raise ValueError("out_of_stock")
        discounts = [self.rules.line_discount(line) if self.rules else 0 for line in lines]
        nets = [line["amount"] - d for line, d in zip(lines, discounts)]
        found, coupon_total = None, 0
        if coupon is not None:
            if self.coupons is None:
                raise ValueError("unknown_coupon")
            found = self.coupons.find(coupon, sum(nets))
            coupon_total = self.coupons.amount(found, sum(nets))
        shares = _shares(coupon_total, nets)
        out_lines = []
        for line, discount, net, share in zip(lines, discounts, nets, shares):
            out_lines.append({**line, "discount": discount, "coupon": share, "net": net - share, "tax": tax_for(line["category"], net - share)})
        totals = {"subtotal": sum(l["amount"] for l in out_lines), "discount": sum(l["discount"] for l in out_lines), "coupon": coupon_total,
                  "net": sum(l["net"] for l in out_lines), "tax": sum(l["tax"] for l in out_lines)}
        totals["total"] = totals["net"] + totals["tax"]
        order = {"number": len(self.orders) + 1, "lines": out_lines, "totals": totals, "coupon": str(coupon).upper() if found else None}
        for line in lines:
            self.catalog.take(line["sku"], line["qty"])
        if found:
            self.coupons.mark_used(coupon)
        self.orders.append(order)
        return order
