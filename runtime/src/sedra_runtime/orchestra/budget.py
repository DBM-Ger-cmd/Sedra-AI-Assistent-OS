from . import budgetcalc
from .store import immediate


def state(conn, agent, now, warn, stop):
    spend_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM spend WHERE agent_id = ?", (agent["id"],)
    ).fetchall()]
    return budgetcalc.view(agent, budgetcalc.totals(spend_rows, agent["budget_period"], now), warn, stop)


def book(conn, agent_id, task_id, mission_id, usage, provider, now, cap_tokens, warn=80, stop=100):
    if provider not in ('lokal', 'cloud'):
        raise ValueError('budget_provider_invalid')

    with immediate(conn):
        agent_row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if agent_row is None:
            raise ValueError('agent_not_found')
        agent_row = dict(agent_row)

        view_before = state(conn, agent_row, now, warn, stop)
        before_pct = view_before["prozent"]

        if usage is None:
            tokens_in = 0
            tokens_out = cap_tokens
            requests = 1
            eur_cent = 0
            estimated = 1
        else:
            tokens_in = usage.get("tokens_in", 0)
            tokens_out = usage.get("tokens_out", 0)
            requests = usage.get("requests", 1)
            eur_cent = usage.get("eur_cent", 0)
            estimated = 0

        conn.execute(
            "INSERT INTO spend (agent_id, task_id, mission_id, provider, provider_id, model, tokens_in, tokens_out, requests, eur_cent, ts, estimated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (agent_id, task_id, mission_id, provider, usage.get("provider_id") if usage else None,
             usage.get("model") if usage else None,
             tokens_in, tokens_out, requests, eur_cent, now, estimated)
        )

        view_after = state(conn, agent_row, now, warn, stop)
        after_pct = view_after["prozent"]

        crossing = budgetcalc.crossing(before_pct, after_pct, warn, stop)

    return {"before_pct": before_pct, "after_pct": after_pct, "crossing": crossing}


def open_incident(conn, agent_id, kind, pct, now):
    if kind not in ('warnung', 'stopp'):
        raise ValueError('incident_kind_invalid')
    with immediate(conn):
        agent_row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if agent_row is None:
            raise ValueError('agent_not_found')
        agent_row = dict(agent_row)

        existing = conn.execute(
            "SELECT id FROM budget_incidents WHERE agent_id = ? AND kind = ? AND resolved_at IS NULL",
            (agent_id, kind),
        ).fetchone()
        if existing is not None:
            return existing["id"]

        spend_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM spend WHERE agent_id = ?",
            (agent_id,),
        ).fetchall()]
        totals = budgetcalc.totals(spend_rows, agent_row["budget_period"], now)

        conn.execute(
            "INSERT INTO budget_incidents (agent_id, kind, percent, used_tokens, limit_tokens, used_eur_cent, limit_eur_cent, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (agent_id, kind, pct, totals["tokens"], agent_row.get("budget_tokens"),
             totals["eur_cent"], agent_row.get("budget_eur_cent"), now),
        )
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def resolve_incident(conn, incident_id, resolution, now):
    valid_resolutions = ('erhoeht', 'fortgesetzt', 'abgelehnt', 'zeitraum')
    if resolution not in valid_resolutions:
        raise ValueError('incident_resolution_invalid')
    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM budget_incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
        if row is None:
            raise ValueError('incident_not_found')
        row = dict(row)
        if row["resolved_at"] is not None:
            raise ValueError('incident_resolved')
        conn.execute(
            "UPDATE budget_incidents SET resolved_at = ?, resolution = ? WHERE id = ?",
            (now, resolution, incident_id),
        )
        row["resolved_at"] = now
        row["resolution"] = resolution
        return row
