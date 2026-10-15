from datetime import date, timedelta


def token_view(records, today):
    today_date = date.fromisoformat(today)

    valid = []
    for r in records:
        if not isinstance(r, dict):
            continue
        d = r.get("date")
        try:
            parsed = date.fromisoformat(d)
        except (TypeError, ValueError):
            continue
        t = r.get("tokens")
        if isinstance(t, bool) or not isinstance(t, int):
            continue
        if t < 0:
            continue
        valid.append(r)

    def _sum_count(dates):
        s = 0
        c = 0
        for r in valid:
            if date.fromisoformat(r["date"]) in dates:
                s += r["tokens"]
                c += 1
        return s, c

    today_set = {today_date}
    seven_set = {today_date - timedelta(days=i) for i in range(7)}
    thirty_set = {today_date - timedelta(days=i) for i in range(30)}

    ranges = {
        "today": {"tokens": _sum_count(today_set)[0], "runs": _sum_count(today_set)[1]},
        "7": {"tokens": _sum_count(seven_set)[0], "runs": _sum_count(seven_set)[1]},
        "30": {"tokens": _sum_count(thirty_set)[0], "runs": _sum_count(thirty_set)[1]},
        "all": {"tokens": sum(r["tokens"] for r in valid), "runs": len(valid)},
    }

    last = None
    for r in valid:
        if last is None:
            last = r
        else:
            if date.fromisoformat(r["date"]) >= date.fromisoformat(last["date"]):
                last = r

    if last is not None:
        last_out = {
            "date": last.get("date"),
            "spec": last.get("spec"),
            "model": last.get("model"),
            "tokens": last.get("tokens"),
        }
    else:
        last_out = None

    series = []
    for i in range(13, -1, -1):
        d = today_date - timedelta(days=i)
        day_tokens = sum(r["tokens"] for r in valid if date.fromisoformat(r["date"]) == d)
        series.append({"date": d.isoformat(), "tokens": day_tokens})

    return {"ranges": ranges, "last": last_out, "series": series}
