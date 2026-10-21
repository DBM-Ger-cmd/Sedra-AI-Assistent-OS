import builtins

import graphs
from store import immediate

HIRE = ("id", "instance_id", "template_id", "name", "role", "recipe_id", "reports_to", "permission_level", "budget_tokens", "budget_eur_cent",
        "budget_period", "can_delegate", "max_parallel")
REQUIRED = ("id", "instance_id", "template_id", "name", "role", "permission_level")
CHANGE = ("reports_to", "role", "recipe_id", "permission_level", "can_delegate", "max_parallel", "budget_tokens", "budget_eur_cent", "budget_period")
REASONS = ("captain", "budget", "quarantaene")
FINGERPRINT = ("status", "permission_level", "recipe_id", "reports_to", "budget_tokens", "budget_eur_cent", "budget_period")


def _rows(conn):
    return [dict(r) for r in conn.execute("SELECT id, reports_to, status FROM agents")]


def get(conn, agent_id):
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return dict(row) if row else None


def _live(conn, agent_id):
    agent = get(conn, agent_id)
    if agent is None:
        raise ValueError("agent_not_found")
    if agent["status"] == "beendet":
        raise ValueError("agent_terminated")
    return agent


def _check_values(values):
    level = values.get("permission_level")
    if "permission_level" in values and not (type(level) is int and 0 <= level <= 6):
        raise ValueError("level_not_allowed")
    if "can_delegate" in values and values["can_delegate"] not in (0, 1):
        raise ValueError("org_field_invalid:can_delegate")
    if "max_parallel" in values and not (type(values["max_parallel"]) is int and 1 <= values["max_parallel"] <= 4):
        raise ValueError("org_field_invalid:max_parallel")
    if "budget_period" in values and values["budget_period"] not in ("gesamt", "monat"):
        raise ValueError("org_field_invalid:budget_period")


def _update(conn, agent_id, values, now):
    sets = ", ".join("%s = ?" % k for k in values)
    conn.execute("UPDATE agents SET %s, updated_at = ?, revision = revision + 1 WHERE id = ?" % sets, builtins.list(values.values()) + [now, agent_id])
    return get(conn, agent_id)


def hire(conn, row, now, max_depth):
    unknown = sorted(set(row) - set(HIRE))
    if unknown:
        raise ValueError("org_field_unknown:" + unknown[0])
    missing = [k for k in REQUIRED if row.get(k) is None]
    if missing:
        raise ValueError("org_field_missing:" + missing[0])
    values = {"can_delegate": 0, "max_parallel": 1, "budget_period": "gesamt", **row}
    _check_values(values)
    with immediate(conn):
        if conn.execute("SELECT 1 FROM agents WHERE id = ? OR instance_id = ?", (values["id"], values["instance_id"])).fetchone():
            raise ValueError("agent_exists")
        graphs.check_org(_rows(conn), {"id": values["id"], "reports_to": values.get("reports_to"), "status": "aktiv"}, max_depth)
        values.update(status="aktiv", created_at=now, updated_at=now)
        names = builtins.list(values)
        conn.execute("INSERT INTO agents (%s) VALUES (%s)" % (", ".join(names), ", ".join("?" * len(names))), [values[n] for n in names])
        return get(conn, values["id"])


def set_org(conn, agent_id, change, now, max_depth):
    unknown = sorted(set(change) - set(CHANGE))
    if unknown:
        raise ValueError("org_field_unknown:" + unknown[0])
    _check_values(change)
    with immediate(conn):
        agent = _live(conn, agent_id)
        values = {k: v for k, v in change.items() if agent[k] != v}
        if not values:
            return agent
        if "reports_to" in values:
            graphs.check_org(_rows(conn), {"id": agent_id, "reports_to": values["reports_to"], "status": agent["status"]}, max_depth)
        return _update(conn, agent_id, values, now)


def pause(conn, agent_id, reason, now):
    if reason not in REASONS:
        raise ValueError("pause_reason_invalid")
    with immediate(conn):
        agent = _live(conn, agent_id)
        if agent["status"] == "pausiert":
            return agent
        return _update(conn, agent_id, {"status": "pausiert", "pause_reason": reason}, now)


def resume(conn, agent_id, now):
    with immediate(conn):
        agent = _live(conn, agent_id)
        if agent["status"] != "pausiert":
            raise ValueError("agent_not_paused")
        return _update(conn, agent_id, {"status": "aktiv", "pause_reason": None}, now)


def terminate(conn, agent_id, now):
    with immediate(conn):
        _live(conn, agent_id)
        graphs.can_terminate(_rows(conn), agent_id)
        return _update(conn, agent_id, {"status": "beendet", "pause_reason": None}, now)


def list(conn, status=None):
    sql, args = "SELECT * FROM agents", []
    if status is not None:
        sql, args = sql + " WHERE status = ?", [status]
    return [dict(r) for r in conn.execute(sql + " ORDER BY created_at, id", args)]


def subordinates(conn, agent_id, deep=False):
    out, level = [], [agent_id]
    while level:
        rows = [dict(r) for r in conn.execute("SELECT * FROM agents WHERE reports_to IN (%s) AND status <> 'beendet' ORDER BY created_at, id"
                                                 % ", ".join("?" * len(level)), level)]
        out += rows
        level = [r["id"] for r in rows] if deep else []
    return out


def fingerprint(agent):
    return {"agent_id": agent["id"], **{k: agent.get(k) for k in FINGERPRINT}}
