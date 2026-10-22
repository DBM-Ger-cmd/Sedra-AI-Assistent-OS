from . import graphs
from .store import immediate

_ALLOWED_FIELDS = {
    "id", "instance_id", "template_id", "name", "role",
    "recipe_id", "reports_to", "permission_level",
    "budget_tokens", "budget_eur_cent", "budget_period",
    "can_delegate", "max_parallel",
}

_MISSING_FIELDS = [
    "id", "instance_id", "template_id", "name", "role", "permission_level",
]


def hire(conn, row, now, max_depth):
    unknown = sorted(k for k in row if k not in _ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"org_field_unknown:{unknown[0]}")

    for f in _MISSING_FIELDS:
        if f not in row or row[f] is None:
            raise ValueError(f"org_field_missing:{f}")

    can_delegate = row.get("can_delegate", 0)
    max_parallel = row.get("max_parallel", 1)
    budget_period = row.get("budget_period", "gesamt")

    pl = row["permission_level"]
    if type(pl) is not int:
        raise ValueError("level_not_allowed")
    if pl < 0 or pl > 6:
        raise ValueError("level_not_allowed")

    if can_delegate not in (0, 1):
        raise ValueError("org_field_invalid:can_delegate")

    if type(max_parallel) is not int or max_parallel < 1 or max_parallel > 4:
        raise ValueError("org_field_invalid:max_parallel")

    if budget_period not in ("gesamt", "monat"):
        raise ValueError("org_field_invalid:budget_period")

    agent = {
        "id": row["id"],
        "instance_id": row["instance_id"],
        "template_id": row["template_id"],
        "name": row["name"],
        "role": row["role"],
        "recipe_id": row.get("recipe_id"),
        "reports_to": row.get("reports_to"),
        "status": "aktiv",
        "permission_level": row["permission_level"],
        "budget_tokens": row.get("budget_tokens"),
        "budget_eur_cent": row.get("budget_eur_cent"),
        "budget_period": budget_period,
        "created_at": now,
        "updated_at": now,
        "revision": 1,
        "can_delegate": can_delegate,
        "max_parallel": max_parallel,
        "pause_reason": None,
    }

    with immediate(conn):
        existing = conn.execute(
            "SELECT id FROM agents WHERE id = ? OR instance_id = ?",
            (agent["id"], agent["instance_id"]),
        ).fetchone()
        if existing is not None:
            raise ValueError("agent_exists")

        all_rows = conn.execute(
            "SELECT id, reports_to, status FROM agents"
        ).fetchall()

        all_rows_dicts = [
            {"id": r["id"], "reports_to": r["reports_to"], "status": r["status"]}
            for r in all_rows
        ]

        change = {
            "id": agent["id"],
            "reports_to": agent["reports_to"],
            "status": "aktiv",
        }
        graphs.check_org(all_rows_dicts, change, max_depth)

        conn.execute(
            "INSERT INTO agents ("
            "id, instance_id, template_id, name, role, recipe_id, reports_to, "
            "status, permission_level, budget_tokens, budget_eur_cent, budget_period, "
            "created_at, updated_at, revision, can_delegate, max_parallel, pause_reason"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent["id"],
                agent["instance_id"],
                agent["template_id"],
                agent["name"],
                agent["role"],
                agent["recipe_id"],
                agent["reports_to"],
                agent["status"],
                agent["permission_level"],
                agent["budget_tokens"],
                agent["budget_eur_cent"],
                agent["budget_period"],
                agent["created_at"],
                agent["updated_at"],
                agent["revision"],
                agent["can_delegate"],
                agent["max_parallel"],
                agent["pause_reason"],
            ),
        )

        new_row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent["id"],)
        ).fetchone()

        return dict(new_row)


def _update_agent(conn, agent_id, updates, now):
    new_revision = updates.pop("_revision", None)
    new_updated_at = updates.pop("_updated_at", None)

    if not updates:
        return None

    set_parts = []
    set_values = []
    for field, value in updates.items():
        set_parts.append(f"{field} = ?")
        set_values.append(value)
    if new_updated_at is not None:
        set_parts.append("updated_at = ?")
        set_values.append(new_updated_at)
    if new_revision is not None:
        set_parts.append("revision = ?")
        set_values.append(new_revision)

    set_clause = ", ".join(set_parts)
    set_values.append(agent_id)

    conn.execute(
        f"UPDATE agents SET {set_clause} WHERE id = ?",
        set_values,
    )

    new_row = conn.execute(
        "SELECT * FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()

    return dict(new_row)


def _check_change_value(key, value):
    if key == "permission_level":
        if type(value) is not int or value < 0 or value > 6:
            raise ValueError("level_not_allowed")
    elif key == "can_delegate":
        if value not in (0, 1):
            raise ValueError("org_field_invalid:can_delegate")
    elif key == "max_parallel":
        if type(value) is not int or value < 1 or value > 4:
            raise ValueError("org_field_invalid:max_parallel")
    elif key == "budget_period":
        if value not in ("gesamt", "monat"):
            raise ValueError("org_field_invalid:budget_period")


def set_org(conn, agent_id, change, now, max_depth):
    _SETTABLE_FIELDS = {
        "reports_to", "role", "recipe_id", "permission_level",
        "can_delegate", "max_parallel",
        "budget_tokens", "budget_eur_cent", "budget_period",
    }

    unknown = sorted(k for k in change if k not in _SETTABLE_FIELDS)
    if unknown:
        raise ValueError(f"org_field_unknown:{unknown[0]}")

    for key, value in change.items():
        _check_change_value(key, value)

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()

        if row is None:
            raise ValueError("agent_not_found")

        if row["status"] == "beendet":
            raise ValueError("agent_terminated")

        current = dict(row)
        updates = {}
        for field in _SETTABLE_FIELDS:
            if field in change and change[field] != current.get(field):
                updates[field] = change[field]

        if not updates:
            return dict(row)

        if "reports_to" in updates:
            all_rows = conn.execute(
                "SELECT id, reports_to, status FROM agents"
            ).fetchall()
            all_rows_dicts = [
                {"id": r["id"], "reports_to": r["reports_to"], "status": r["status"]}
                for r in all_rows
            ]
            graph_change = {
                "id": agent_id,
                "reports_to": updates["reports_to"],
                "status": row["status"],
            }
            graphs.check_org(all_rows_dicts, graph_change, max_depth)

        new_updated_at = now
        new_revision = current["revision"] + 1

        updates["_updated_at"] = new_updated_at
        updates["_revision"] = new_revision

        return _update_agent(conn, agent_id, updates, now)


def pause(conn, agent_id, reason, now):
    if reason not in ("captain", "budget", "quarantaene"):
        raise ValueError("pause_reason_invalid")

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()

        if row is None:
            raise ValueError("agent_not_found")

        if row["status"] == "beendet":
            raise ValueError("agent_terminated")

        if row["status"] == "pausiert":
            return dict(row)

        new_revision = row["revision"] + 1
        updates = {
            "status": "pausiert",
            "pause_reason": reason,
            "_updated_at": now,
            "_revision": new_revision,
        }

        return _update_agent(conn, agent_id, updates, now)


def resume(conn, agent_id, now):
    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()

        if row is None:
            raise ValueError("agent_not_found")

        if row["status"] == "beendet":
            raise ValueError("agent_terminated")

        if row["status"] != "pausiert":
            raise ValueError("agent_not_paused")

        new_revision = row["revision"] + 1
        updates = {
            "status": "aktiv",
            "pause_reason": None,
            "_updated_at": now,
            "_revision": new_revision,
        }

        return _update_agent(conn, agent_id, updates, now)


def terminate(conn, agent_id, now):
    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()

        if row is None:
            raise ValueError("agent_not_found")

        if row["status"] == "beendet":
            raise ValueError("agent_terminated")

        all_rows = conn.execute(
            "SELECT id, reports_to, status FROM agents"
        ).fetchall()
        all_rows_dicts = [
            {"id": r["id"], "reports_to": r["reports_to"], "status": r["status"]}
            for r in all_rows
        ]
        graphs.can_terminate(all_rows_dicts, agent_id)

        new_revision = row["revision"] + 1
        updates = {
            "status": "beendet",
            "pause_reason": None,
            "_updated_at": now,
            "_revision": new_revision,
        }

        return _update_agent(conn, agent_id, updates, now)


def get(conn, agent_id):
    row = conn.execute(
        "SELECT * FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def list(conn, status=None):
    if status is not None:
        rows = conn.execute(
            "SELECT * FROM agents WHERE status = ? ORDER BY created_at, id",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agents ORDER BY created_at, id"
        ).fetchall()
    return [dict(r) for r in rows]


def subordinates(conn, agent_id, deep=False):
    if deep:
        rows = conn.execute(
            "SELECT * FROM agents WHERE reports_to = ? AND status != 'beendet' ORDER BY created_at, id",
            (agent_id,),
        ).fetchall()
        result = [dict(r) for r in rows]
        queue = [r["id"] for r in result]
        while queue:
            next_queue = []
            for parent_id in queue:
                child_rows = conn.execute(
                    "SELECT * FROM agents WHERE reports_to = ? AND status != 'beendet' ORDER BY created_at, id",
                    (parent_id,),
                ).fetchall()
                for r in child_rows:
                    d = dict(r)
                    result.append(d)
                    next_queue.append(d["id"])
            queue = next_queue
        return result
    else:
        rows = conn.execute(
            "SELECT * FROM agents WHERE reports_to = ? AND status != 'beendet' ORDER BY created_at, id",
            (agent_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def fingerprint(agent):
    return {
        "agent_id": agent["id"],
        "status": agent["status"],
        "permission_level": agent["permission_level"],
        "recipe_id": agent["recipe_id"],
        "reports_to": agent["reports_to"],
        "budget_tokens": agent["budget_tokens"],
        "budget_eur_cent": agent["budget_eur_cent"],
        "budget_period": agent["budget_period"],
    }
