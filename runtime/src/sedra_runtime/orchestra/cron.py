from datetime import datetime, timedelta, timezone, tzinfo

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FIELDS = (("minute", 0, 59), ("hour", 0, 23), ("day", 1, 31), ("month", 1, 12), ("weekday", 0, 7))
MONTHS = {n: i + 1 for i, n in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
DAYS = {n: i for i, n in enumerate(("sun", "mon", "tue", "wed", "thu", "fri", "sat"))}
NAMES = {"month": MONTHS, "weekday": DAYS}
SEARCH_DAYS = 2930
TAGE = ("sonntags", "montags", "dienstags", "mittwochs", "donnerstags", "freitags", "samstags")
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")


def _number(text, field, low, high):
    value = NAMES.get(field, {}).get(text.lower())
    if value is None:
        if not (text.isascii() and text.isdigit()):
            raise ValueError("cron_invalid:" + field)
        value = int(text)
    if not low <= value <= high:
        raise ValueError("cron_invalid:" + field)
    return value


def _field(text, field, low, high):
    values = set()
    for part in text.split(","):
        body, _, step = part.partition("/")
        if step and not (step.isascii() and step.isdigit() and int(step) > 0):
            raise ValueError("cron_invalid:" + field)
        if body == "*":
            start, end = low, high
        elif "-" in body:
            a, _, b = body.partition("-")
            start, end = _number(a, field, low, high), _number(b, field, low, high)
            if start > end:
                raise ValueError("cron_invalid:" + field)
        else:
            start = _number(body, field, low, high)
            end = high if step else start
        values.update(range(start, end + 1, int(step) if step else 1))
    if field == "weekday":
        values = {v % 7 for v in values}
    return sorted(values)


def parse(expr):
    parts = expr.split() if isinstance(expr, str) else []
    if len(parts) != 5:
        raise ValueError("cron_invalid:fields")
    cron = {name: _field(text, name, low, high) for text, (name, low, high) in zip(parts, FIELDS)}
    minute = parts[0]
    cron["day_any"] = parts[2] == "*"
    cron["weekday_any"] = parts[4] == "*"
    cron["every"] = int(minute[2:]) if minute.startswith("*/") else None
    cron["text"] = " ".join(parts)
    return cron


def _zone(tz):
    if isinstance(tz, tzinfo):
        return tz
    if tz == "UTC":
        return timezone.utc
    if not isinstance(tz, str) or not tz:
        raise ValueError("cron_timezone_unknown")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz)
    except Exception:
        raise ValueError("cron_timezone_unknown") from None


def _day_ok(cron, day):
    dom = day.day in cron["day"]
    dow = (day.weekday() + 1) % 7 in cron["weekday"]
    if not cron["day_any"] and not cron["weekday_any"]:
        return dom or dow
    return dom and dow


def _instant(local, zone):
    probe = local
    for _ in range(181):
        utc = probe.replace(tzinfo=zone, fold=0).astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == probe:
            return utc.replace(tzinfo=None)
        probe += timedelta(minutes=1)
    return None


def next_after(cron, after_utc, tz):
    zone = _zone(tz)
    after = datetime.strptime(after_utc, FORMAT)
    start = after.replace(tzinfo=timezone.utc).astimezone(zone).replace(tzinfo=None, second=0, fold=0)
    day = start.date()
    for _ in range(SEARCH_DAYS):
        if day.month in cron["month"] and _day_ok(cron, day):
            for hour in cron["hour"]:
                for minute in cron["minute"]:
                    local = datetime(day.year, day.month, day.day, hour, minute)
                    if local < start:
                        continue
                    utc = _instant(local, zone)
                    if utc is not None and utc > after:
                        return utc.strftime(FORMAT)
        day += timedelta(days=1)
    return None


def due_between(cron, from_utc, to_utc, tz, limit):
    out, cursor = [], from_utc
    while len(out) <= limit:
        cursor = next_after(cron, cursor, tz)
        if cursor is None or cursor > to_utc:
            break
        out.append(cursor)
    return out


def _list(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " und " + items[-1]


def _weekdays(values):
    order = sorted(values, key=lambda v: (v + 6) % 7)
    keys = [(v + 6) % 7 for v in order]
    if len(order) >= 3 and keys == list(range(keys[0], keys[0] + len(keys))):
        return TAGE[order[0]] + " bis " + TAGE[order[-1]]
    return _list([TAGE[v] for v in order])


def _time(cron):
    minutes, hours = cron["minute"], cron["hour"]
    if cron["every"] and len(hours) == 24:
        return "alle %d Minuten" % cron["every"], True
    if len(minutes) == 60:
        return None, False
    if len(hours) == 24:
        if minutes == [0]:
            return "stündlich zur vollen Stunde", True
        if len(minutes) == 1:
            return "stündlich zur Minute %02d" % minutes[0], True
        return "stündlich zu den Minuten " + _list(["%02d" % m for m in minutes]), True
    times = ["%02d:%02d" % (h, m) for h in hours for m in minutes]
    return (("um " + _list(times) + " Uhr") if len(times) <= 8 else None), False


def describe(cron):
    text, takt = _time(cron)
    if text is None:
        return None
    parts = []
    if not cron["day_any"]:
        parts.append("am " + _list(["%d." % d for d in cron["day"]]) + " des Monats")
    if not cron["weekday_any"]:
        parts.append(_weekdays(cron["weekday"]))
    days = " oder ".join(parts) or "jeden Tag"
    months = "" if len(cron["month"]) == 12 else " im " + _list([MONATE[m - 1] for m in cron["month"]])
    if days == "jeden Tag" and takt and not months:
        return text
    return days + months + " " + text
