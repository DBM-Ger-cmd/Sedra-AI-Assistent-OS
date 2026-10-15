from .money import fmt


def daily(orders):
    by_sku = {}
    for order in orders:
        for line in order["lines"]:
            by_sku[line["sku"]] = by_sku.get(line["sku"], 0) + line["qty"]
    top = sorted(by_sku.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return {"orders": len(orders), "net": fmt(sum(o["totals"]["net"] for o in orders)), "tax": fmt(sum(o["totals"]["tax"] for o in orders)), "top": top}
