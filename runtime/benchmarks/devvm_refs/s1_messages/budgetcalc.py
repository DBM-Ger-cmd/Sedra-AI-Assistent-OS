PERIODS = ("gesamt", "monat")


def totals(spend_rows, period, now):
    if period not in PERIODS:
        raise ValueError("budget_period_unknown")
    rows = [r for r in spend_rows if period == "gesamt" or r["ts"][:7] == now[:7]]
    return {"tokens": sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in rows),
            "eur_cent": sum(r.get("eur_cent", 0) for r in rows),
            "requests": sum(r.get("requests", 1) for r in rows),
            "estimated": sum(1 for r in rows if r.get("estimated"))}


def percent(used, limit):
    if limit is None:
        return None
    if limit <= 0:
        return 100
    return used * 100 // limit


def stage(pct, warn, stop):
    if pct is None or pct < warn:
        return "ok"
    return "gestoppt" if pct >= stop else "warnung"


def precheck(limit, used, run_cap):
    if limit is not None and limit - used < run_cap:
        raise ValueError("budget_insufficient")


def crossing(before_pct, after_pct, warn, stop):
    if after_pct is None:
        return None
    before = before_pct or 0
    if before < stop <= after_pct:
        return "stopp"
    if before < warn <= after_pct:
        return "warnung"
    return None


def view(agent_row, totals, warn, stop):
    shares = [p for p in (percent(totals["tokens"], agent_row.get("budget_tokens")), percent(totals["eur_cent"], agent_row.get("budget_eur_cent"))) if p is not None]
    pct = max(shares) if shares else None
    return {"grenze_token": agent_row.get("budget_tokens"), "verbraucht_token": totals["tokens"],
            "grenze_eur_cent": agent_row.get("budget_eur_cent"), "verbraucht_eur_cent": totals["eur_cent"],
            "prozent": pct, "stufe": stage(pct, warn, stop), "zeitraum": agent_row.get("budget_period", "gesamt")}
