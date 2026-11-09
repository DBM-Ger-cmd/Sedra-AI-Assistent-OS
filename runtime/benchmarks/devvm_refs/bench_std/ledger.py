def balance(entries):
    total = 0.0
    for entry in entries:
        kind = entry["type"]
        amount = entry["amount"]
        if kind not in ("credit", "debit"):
            raise ValueError("unknown type: %s" % kind)
        if amount < 0:
            raise ValueError("negative amount")
        total += amount if kind == "credit" else -amount
    return round(total, 2)
