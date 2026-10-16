from datetime import date, timedelta


def _day(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _valid(record):
    return isinstance(record, dict) and _day(record.get("date")) is not None and type(record.get("tokens")) is int and record["tokens"] >= 0


def token_view(records, today):
    now = date.fromisoformat(today)
    good = [r for r in records if _valid(r)]
    spans = {"today": 1, "7": 7, "30": 30}
    ranges = {}
    for key, days in spans.items():
        inside = [r for r in good if 0 <= (now - _day(r["date"])).days < days]
        ranges[key] = {"tokens": sum(r["tokens"] for r in inside), "runs": len(inside)}
    ranges["all"] = {"tokens": sum(r["tokens"] for r in good), "runs": len(good)}
    last = None
    for r in good:
        if last is None or _day(r["date"]) >= _day(last["date"]):
            last = r
    series = []
    for back in range(13, -1, -1):
        day = now - timedelta(days=back)
        series.append({"date": day.isoformat(), "tokens": sum(r["tokens"] for r in good if _day(r["date"]) == day)})
    return {"ranges": ranges, "last": {k: last.get(k) for k in ("date", "spec", "model", "tokens")} if last else None, "series": series}
