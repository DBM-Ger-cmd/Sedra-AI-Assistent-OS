from datetime import datetime, timedelta

from .wakeplan import FORMAT, coalesce as _coalesce
from .store import immediate

VALID_REASONS = {"zugewiesen", "antwort", "routine", "captain", "wiederholung"}
VALID_OUTCOMES = {"lauf", "antrag", "pausiert", "kein_budget", "blockiert", "keine_aufgabe", "laeuft_schon", "abgelehnt"}


def enqueue(conn, agent_id, reason, key, now, coalesce_s, task_id=None):
    if reason not in VALID_REASONS:
        raise ValueError("wake_reason_invalid")

    with immediate(conn):
        agent = conn.execute(
            "SELECT id, status FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if agent is None:
            raise ValueError("agent_not_found")

        if agent["status"] != "aktiv":
            return None

        if key is not None:
            existing = conn.execute(
                "SELECT id FROM wakeups WHERE agent_id = ? AND idempotency_key = ?",
                (agent_id, key),
            ).fetchone()
            if existing is not None:
                return None

        due_at = (datetime.strptime(now, FORMAT) + timedelta(seconds=coalesce_s)).strftime(FORMAT)
        cur = conn.execute(
            "INSERT INTO wakeups (agent_id, task_id, reason, due_at, created_at, idempotency_key) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, task_id, reason, due_at, now, key),
        )
        return cur.lastrowid


def due(conn, now, coalesce_s=0):
    with immediate(conn):
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM wakeups WHERE done_at IS NULL AND coalesced_into IS NULL "
            "ORDER BY due_at, id"
        ).fetchall()]
        groups = _coalesce(rows, now, coalesce_s)
        for group in groups:
            leader = group["leader"]
            for i, member in enumerate(group["members"]):
                conn.execute(
                    "UPDATE wakeups SET coalesced_into = ? WHERE id = ?",
                    (leader["id"], member["id"]),
                )
                member = dict(member)
                member["coalesced_into"] = leader["id"]
                group["members"][i] = member
        return groups


def finish(conn, wakeup_id, outcome, now, job_id=None, mission_id=None, request_mission_id=None):
    if outcome not in VALID_OUTCOMES:
        raise ValueError("wake_outcome_invalid")

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM wakeups WHERE id = ?", (wakeup_id,)
        ).fetchone()
        if row is None:
            raise ValueError("wakeup_not_found")

        row = dict(row)

        if row["done_at"] is not None:
            if row["outcome"] == "antrag" and outcome in ("lauf", "abgelehnt"):
                pass
            else:
                raise ValueError("wakeup_finished")

        updates = []
        params = []
        updates.append("outcome = ?")
        params.append(outcome)
        updates.append("done_at = ?")
        params.append(now)
        if job_id is not None:
            updates.append("job_id = ?")
            params.append(job_id)
        if mission_id is not None:
            updates.append("mission_id = ?")
            params.append(mission_id)
        if request_mission_id is not None:
            updates.append("request_mission_id = ?")
            params.append(request_mission_id)

        conn.execute(
            "UPDATE wakeups SET " + ", ".join(updates) + " WHERE id = ?",
            params + [wakeup_id],
        )

        conn.execute(
            "UPDATE wakeups SET outcome = ?, done_at = ? WHERE coalesced_into = ?",
            (outcome, now, wakeup_id),
        )

        updated = conn.execute(
            "SELECT * FROM wakeups WHERE id = ?", (wakeup_id,)
        ).fetchone()
        return dict(updated)


def pending_request(conn, agent_id):
    row = conn.execute(
        "SELECT * FROM wakeups WHERE agent_id = ? AND outcome = 'antrag' AND coalesced_into IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (agent_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def in_flight(conn):
    rows = conn.execute(
        "SELECT t.id AS task_id, t.checkout_run AS run_id, t.checkout_by AS agent_id, "
        "w.job_id "
        "FROM tasks t "
        "LEFT JOIN wakeups w ON w.task_id = t.id AND w.outcome = 'lauf' "
        "  AND w.id = ("
        "    SELECT MAX(w2.id) FROM wakeups w2 "
        "    WHERE w2.task_id = t.id AND w2.outcome = 'lauf'"
        "  ) "
        "WHERE t.checkout_run IS NOT NULL "
        "ORDER BY t.id"
    ).fetchall()
    return [dict(r) for r in rows]
