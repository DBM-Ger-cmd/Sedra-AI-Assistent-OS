def balance(entries):
    total = 0.0
    for entry in entries:
        if entry["type"] == "credit":
            total += entry["amount"]
        elif entry["type"] == "debit":
            total += entry["amount"]
    return round(total, 2)
