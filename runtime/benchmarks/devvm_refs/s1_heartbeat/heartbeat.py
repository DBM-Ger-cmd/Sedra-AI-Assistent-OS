from datetime import datetime, timedelta

import wakeplan
from store import immediate

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
REASONS = ("zugewiesen", "antwort", "routine", "captain", "wiederholung")
OUTCOMES = ("lauf", "antrag", "pausiert", "kein_budget", "blockiert", "keine_aufgabe", "laeuft_schon", "abgelehnt")


def _wakeup(conn, wakeup_id):
    row = conn.execute("SELECT * FROM wakeups WHERE id = ?", (wakeup_id,)).fetchone()
    return dict(row) if row else None


def enqueue(conn, agent_id, reason, key, now, coalesce_s, task_id=None):
    if reason not in REASONS:
        raise ValueError("wake_reason_invalid")
    due_at = (datetime.strptime(now, FORMAT) + timedelta(seconds=coalesce_s)).strftime(FORMAT)
    with immediate(conn):
        agent = conn.execute("SELECT status FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if agent is None:
            raise ValueError("agent_not_found")
        if agent[0] != "aktiv":
            return None
        if key is not None and conn.execute("SELECT 1 FROM wakeups WHERE agent_id = ? AND idempotency_key = ?", (agent_id, key)).fetchone():
            return None
        cur = conn.execute("INSERT INTO wakeups (agent_id, task_id, reason, due_at, created_at, idempotency_key) VALUES (?, ?, ?, ?, ?, ?)",
                           (agent_id, task_id, reason, due_at, now, key))
        return cur.lastrowid


def due(conn, now, coalesce_s=0):
    with immediate(conn):
        rows = [dict(r) for r in conn.execute("SELECT * FROM wakeups WHERE done_at IS NULL AND coalesced_into IS NULL")]
        groups = wakeplan.coalesce(rows, now, coalesce_s)
        out = []
        for group in groups:
            leader = group["leader"]
            members = [dict(m, coalesced_into=leader["id"]) for m in group["members"]]
            for member in members:
                conn.execute("UPDATE wakeups SET coalesced_into = ? WHERE id = ?", (leader["id"], member["id"]))
            out.append({"leader": dict(leader), "members": members})
        return out


def finish(conn, wakeup_id, outcome, now, job_id=None, mission_id=None, request_mission_id=None):
    if outcome not in OUTCOMES:
        raise ValueError("wake_outcome_invalid")
    with immediate(conn):
        old = _wakeup(conn, wakeup_id)
        if old is None:
            raise ValueError("wakeup_not_found")
        if old["done_at"] is not None and not (old["outcome"] == "antrag" and outcome in ("lauf", "abgelehnt")):
            raise ValueError("wakeup_finished")
        conn.execute("UPDATE wakeups SET outcome = ?, done_at = ?, job_id = COALESCE(?, job_id), mission_id = COALESCE(?, mission_id), "
                     "request_mission_id = COALESCE(?, request_mission_id) WHERE id = ?", (outcome, now, job_id, mission_id, request_mission_id, wakeup_id))
        conn.execute("UPDATE wakeups SET outcome = ?, done_at = ? WHERE coalesced_into = ?", (outcome, now, wakeup_id))
        return _wakeup(conn, wakeup_id)


def pending_request(conn, agent_id):
    row = conn.execute("SELECT * FROM wakeups WHERE agent_id = ? AND outcome = 'antrag' AND coalesced_into IS NULL ORDER BY id DESC LIMIT 1", (agent_id,)).fetchone()
    return dict(row) if row else None


def in_flight(conn):
    rows = conn.execute("SELECT t.id, t.checkout_run, t.checkout_by, (SELECT w.job_id FROM wakeups w WHERE w.task_id = t.id AND w.outcome = 'lauf' "
                        "ORDER BY w.id DESC LIMIT 1) FROM tasks t WHERE t.checkout_run IS NOT NULL ORDER BY t.id").fetchall()
    return [{"task_id": r[0], "run_id": r[1], "job_id": r[3], "agent_id": r[2]} for r in rows]
