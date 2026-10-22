import json
from datetime import datetime, timedelta

from slot_db import immediate
from slotplan import FORMAT, STATES, admit, decide_reason, needs_cloud_offer, order

KINDS = ("job", "direkt")
FIELDS = ("recipe", "slots", "context_per_slot", "pid", "reason", "owner")
NOTED = ("restarts", "garbage")


def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _event(conn, now, kind, run_id=None, detail=""):
    conn.execute("INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, ?, ?, ?)", (now, kind, run_id, str(detail)[:500]))


def _server(conn):
    row = conn.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone()
    return dict(row) if row else {"name": "main", "gen": 0, "recipe": None, "slots": None, "context_per_slot": None, "state": "aus", "pid": None,
                                  "since": None, "restarts": "[]", "garbage": "[]", "reason": None, "owner": None}


def _save(conn, server):
    conn.execute("INSERT OR REPLACE INTO slot_server (name, gen, recipe, slots, context_per_slot, state, pid, since, restarts, garbage, reason, owner) "
                 "VALUES ('main', :gen, :recipe, :slots, :context_per_slot, :state, :pid, :since, :restarts, :garbage, :reason, :owner)", server)


def request(conn, run_id, kind, owner, priority, now, agent_id=None, task_id=None, ttl_s=120):
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id_invalid")
    if kind not in KINDS:
        raise ValueError("lease_kind_invalid")
    if not isinstance(owner, str) or not owner:
        raise ValueError("owner_invalid")
    if type(priority) is not int or not 0 <= priority <= 9:
        raise ValueError("priority_invalid")
    if type(ttl_s) is not int or ttl_s < 1:
        raise ValueError("ttl_invalid")
    with immediate(conn):
        row = conn.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()
        if row and row["state"] in ("wartend", "aktiv"):
            return {"run_id": run_id, "neu": False}
        conn.execute("INSERT OR REPLACE INTO slot_leases (run_id, kind, owner, agent_id, task_id, priority, enqueued, state, ttl_s) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, 'wartend', ?)", (run_id, kind, owner, agent_id, task_id, priority, now, ttl_s))
    return {"run_id": run_id, "neu": True}


def set_server(conn, now, state, **fields):
    if state not in STATES:
        raise ValueError("server_state_invalid")
    if set(fields) - set(FIELDS):
        raise ValueError("field_invalid")
    slots = fields.get("slots")
    if slots is not None and (type(slots) is not int or not 1 <= slots <= 8):
        raise ValueError("slots_invalid")
    with immediate(conn):
        server = _server(conn)
        before = server["state"]
        interrupted = []
        if state == "startet":
            server["gen"] += 1
        if state != before or server["since"] is None:
            server["since"] = now
        server["state"] = state
        if state == "aus":
            server.update(recipe=None, slots=None, context_per_slot=None, pid=None, owner=None)
        server.update(fields)
        if state in ("aus", "gesperrt") and before not in ("aus", "gesperrt"):
            interrupted = [r["run_id"] for r in _rows(conn, "SELECT run_id FROM slot_leases WHERE state = 'aktiv' ORDER BY run_id")]
            conn.execute("UPDATE slot_leases SET state = 'unterbrochen', reason = ? WHERE state = 'aktiv'", ("server_" + state,))
        _save(conn, server)
        _event(conn, now, "server_" + state, None, server["recipe"] or "")
    return dict(server, interrupted=interrupted)


def note(conn, field, now, window_s):
    if field not in NOTED:
        raise ValueError("field_invalid")
    if type(window_s) is not int or window_s < 1:
        raise ValueError("window_invalid")
    limit = (datetime.strptime(now, FORMAT) - timedelta(seconds=window_s)).strftime(FORMAT)
    with immediate(conn):
        server = _server(conn)
        kept = [t for t in json.loads(server[field]) if t >= limit] + [now]
        server[field] = json.dumps(kept)
        server["since"] = server["since"] or now
        _save(conn, server)
    return len(kept)


def take(conn, run_id, now, cfg, recipe=None):
    with immediate(conn):
        mine = conn.execute("SELECT run_id FROM slot_leases WHERE run_id = ? AND state = 'wartend'", (run_id,)).fetchone()
        if mine is None:
            raise ValueError("lease_not_requested")
        server = _server(conn)
        mode = server["state"] if server["state"] in ("drain", "exklusiv") else "normal"
        active = _rows(conn, "SELECT * FROM slot_leases WHERE state = 'aktiv'")
        waiting = _rows(conn, "SELECT * FROM slot_leases WHERE state = 'wartend'")
        reason = decide_reason(server, recipe, mode, active, cfg)
        if reason is None and run_id in admit(server, active, waiting, mode, now, cfg):
            used = {a["slot"] for a in active}
            slot = next(i for i in range(1, (server["slots"] if server["state"] == "bereit" else 1) + 1) if i not in used)
            conn.execute("UPDATE slot_leases SET state = 'aktiv', slot = ?, server_gen = ?, started = ?, heartbeat = ?, reason = NULL WHERE run_id = ?",
                         (slot, server["gen"], now, now, run_id))
            _event(conn, now, "take", run_id, slot)
            return {"granted": True, "slot": slot, "reason": None}
        reason = reason or "wartet_in_reihe"
        conn.execute("UPDATE slot_leases SET reason = ? WHERE run_id = ?", (reason, run_id))
    return {"granted": False, "slot": None, "reason": reason}


def release(conn, run_id, outcome, now):
    if outcome not in ("fertig", "unterbrochen"):
        raise ValueError("outcome_invalid")
    with immediate(conn):
        row = conn.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()
        if row is None or row["state"] not in ("wartend", "aktiv"):
            return False
        conn.execute("UPDATE slot_leases SET state = ? WHERE run_id = ?", (outcome if row["state"] == "aktiv" else "verfallen", run_id))
        _event(conn, now, "release", run_id, outcome)
    return True


def beat(conn, run_id, now):
    with immediate(conn):
        cur = conn.execute("UPDATE slot_leases SET heartbeat = ? WHERE run_id = ? AND state = 'aktiv'", (now, run_id))
    return cur.rowcount == 1


def reap(conn, live_run_ids, now):
    live = set(live_run_ids)
    with immediate(conn):
        gone = [r["run_id"] for r in _rows(conn, "SELECT run_id FROM slot_leases WHERE state IN ('wartend', 'aktiv') ORDER BY run_id") if r["run_id"] not in live]
        for run_id in gone:
            conn.execute("UPDATE slot_leases SET state = 'verfallen' WHERE run_id = ?", (run_id,))
            _event(conn, now, "reap", run_id)
    return gone


def handover_request(conn, owner, purpose, priority, pid, now, ttl_s=60):
    if not isinstance(owner, str) or not owner:
        raise ValueError("owner_invalid")
    if type(priority) is not int or not 0 <= priority <= 9:
        raise ValueError("priority_invalid")
    if type(ttl_s) is not int or ttl_s < 1:
        raise ValueError("ttl_invalid")
    with immediate(conn):
        row = conn.execute("SELECT since FROM handover_requests WHERE owner = ?", (owner,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO handover_requests (owner, purpose, priority, pid, since, heartbeat, ttl_s) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (owner, str(purpose)[:200], priority, pid, row["since"] if row else now, now, ttl_s))
        if row is None:
            _event(conn, now, "handover", None, owner)
    return row is None


def handover_clear(conn, owner):
    with immediate(conn):
        cur = conn.execute("DELETE FROM handover_requests WHERE owner = ?", (owner,))
    return cur.rowcount == 1


def handover_pending(conn, now):
    stamp = datetime.strptime(now, FORMAT)
    rows = _rows(conn, "SELECT * FROM handover_requests ORDER BY priority DESC, since, owner")
    return [r for r in rows if datetime.strptime(r["heartbeat"], FORMAT) + timedelta(seconds=r["ttl_s"]) >= stamp]


def events(conn, limit=20):
    return _rows(conn, "SELECT * FROM slot_events ORDER BY id DESC LIMIT ?", (limit,))


def view(conn, now, cfg):
    server = _server(conn)
    active = _rows(conn, "SELECT * FROM slot_leases WHERE state = 'aktiv' ORDER BY slot")
    waiting = _rows(conn, "SELECT * FROM slot_leases WHERE state = 'wartend'")
    return {"server": {k: server[k] for k in ("state", "gen", "recipe", "slots")}, "gesamt": server["slots"] or 0,
            "belegt": [{"slot": a["slot"], "run_id": a["run_id"], "agent_id": a["agent_id"], "task_id": a["task_id"], "prioritaet": a["priority"],
                        "seit": a["started"]} for a in active],
            "schlange": [{"run_id": w["run_id"], "agent_id": w["agent_id"], "prioritaet": w["priority"], "seit": w["enqueued"], "grund": w["reason"]}
                         for w in order(waiting, now, cfg)],
            "warnung": needs_cloud_offer(waiting, now, cfg)}
