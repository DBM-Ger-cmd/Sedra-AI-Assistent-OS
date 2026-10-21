import budgetcalc
from store import immediate

PROVIDERS = ("lokal", "cloud")
KINDS = ("warnung", "stopp")
RESOLUTIONS = ("erhoeht", "fortgesetzt", "abgelehnt", "zeitraum")


def _agent(conn, agent_id):
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if row is None:
        raise ValueError("agent_not_found")
    return dict(row)


def _totals(conn, agent, now):
    rows = [dict(r) for r in conn.execute("SELECT * FROM spend WHERE agent_id = ?", (agent["id"],))]
    return budgetcalc.totals(rows, agent["budget_period"], now)


def state(conn, agent, now, warn, stop):
    return budgetcalc.view(agent, _totals(conn, agent, now), warn, stop)


def book(conn, agent_id, task_id, mission_id, usage, provider, now, cap_tokens, warn=80, stop=100):
    if provider not in PROVIDERS:
        raise ValueError("budget_provider_invalid")
    estimated = 1 if usage is None else 0
    usage = {"tokens_out": cap_tokens} if usage is None else usage
    tokens_out = usage.get("tokens_out", 0)
    with immediate(conn):
        agent = _agent(conn, agent_id)
        before = state(conn, agent, now, warn, stop)["prozent"]
        conn.execute("INSERT INTO spend (agent_id, task_id, mission_id, provider, provider_id, model, tokens_in, tokens_out, requests, eur_cent, ts, estimated) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (agent_id, task_id, mission_id, provider, usage.get("provider_id"), usage.get("model"), usage.get("tokens_in", 0), tokens_out,
                      usage.get("requests", 1), usage.get("eur_cent", 0), now, estimated))
        after = state(conn, agent, now, warn, stop)["prozent"]
    return {"before_pct": before, "after_pct": after, "crossing": budgetcalc.crossing(before, after, warn, stop)}


def _incident(conn, incident_id):
    row = conn.execute("SELECT * FROM budget_incidents WHERE id = ?", (incident_id,)).fetchone()
    return dict(row) if row else None


def open_incident(conn, agent_id, kind, pct, now):
    if kind not in KINDS:
        raise ValueError("incident_kind_invalid")
    with immediate(conn):
        agent = _agent(conn, agent_id)
        old = conn.execute("SELECT id FROM budget_incidents WHERE agent_id = ? AND kind = ? AND resolved_at IS NULL", (agent_id, kind)).fetchone()
        if old is not None:
            return old[0]
        totals = _totals(conn, agent, now)
        cur = conn.execute("INSERT INTO budget_incidents (agent_id, kind, percent, used_tokens, limit_tokens, used_eur_cent, limit_eur_cent, created_at) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (agent_id, kind, pct, totals["tokens"], agent["budget_tokens"], totals["eur_cent"], agent["budget_eur_cent"], now))
        return cur.lastrowid


def resolve_incident(conn, incident_id, resolution, now):
    if resolution not in RESOLUTIONS:
        raise ValueError("incident_resolution_invalid")
    with immediate(conn):
        incident = _incident(conn, incident_id)
        if incident is None:
            raise ValueError("incident_not_found")
        if incident["resolved_at"] is not None:
            raise ValueError("incident_resolved")
        conn.execute("UPDATE budget_incidents SET resolved_at = ?, resolution = ? WHERE id = ?", (now, resolution, incident_id))
        return _incident(conn, incident_id)
