def fmt(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def percent_of(cents, percent):
    return (cents * percent + 50) // 100
