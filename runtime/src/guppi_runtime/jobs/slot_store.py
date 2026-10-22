from .slot_db import immediate
from .slotplan import FORMAT, STATES, admit, decide_reason, needs_cloud_offer, order
import json
from datetime import datetime, timedelta


def _default_server():
    return {"state": "aus", "gen": 0, "recipe": None, "slots": None}


def _empty_server():
    return {"gen": 0, "recipe": None, "slots": None, "context_per_slot": None,
            "state": "aus", "pid": None, "since": None, "reason": None,
            "owner": None, "restarts": "[]", "garbage": "[]"}


def _check_request(run_id, kind, owner, priority, ttl_s):
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id_invalid")
    if kind not in ("job", "direkt"):
        raise ValueError("lease_kind_invalid")
    _check_owner_priority_ttl(owner, priority, ttl_s)


def _check_owner_priority_ttl(owner, priority, ttl_s):
    if not isinstance(owner, str) or not owner:
        raise ValueError("owner_invalid")
    if isinstance(priority, bool) or not isinstance(priority, int) or not (0 <= priority <= 9):
        raise ValueError("priority_invalid")
    if isinstance(ttl_s, bool) or not isinstance(ttl_s, int) or ttl_s < 1:
        raise ValueError("ttl_invalid")


def set_server(conn, now, state, **fields):
    valid_fields = {"recipe", "slots", "context_per_slot", "pid", "reason", "owner"}
    if state not in STATES:
        raise ValueError("server_state_invalid")
    for fname in fields:
        if fname not in valid_fields:
            raise ValueError("field_invalid")
    if "slots" in fields and fields["slots"] is not None:
        if type(fields["slots"]) is not int or not (1 <= fields["slots"] <= 8):
            raise ValueError("slots_invalid")
    with immediate(conn):
        row = conn.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone()
        old = dict(row) if row else _empty_server()
        new_gen = old["gen"] + 1 if state == "startet" else old["gen"]
        new_since = now if (state != old["state"] or old["since"] is None) else old["since"]
        new_recipe = None if state == "aus" else old["recipe"]
        new_slots = None if state == "aus" else old["slots"]
        new_ctx = None if state == "aus" else old["context_per_slot"]
        new_pid = None if state == "aus" else old["pid"]
        new_reason = old["reason"]
        new_owner = old["owner"]
        for k in ("recipe", "slots", "context_per_slot", "pid", "reason", "owner"):
            if k in fields:
                if k == "recipe": new_recipe = fields[k]
                elif k == "slots": new_slots = fields[k]
                elif k == "context_per_slot": new_ctx = fields[k]
                elif k == "pid": new_pid = fields[k]
                elif k == "reason": new_reason = fields[k]
                elif k == "owner": new_owner = fields[k]
        interrupted = []
        if state in ("aus", "gesperrt") and old["state"] not in ("aus", "gesperrt"):
            for lease in conn.execute(
                "SELECT run_id FROM slot_leases WHERE state = 'aktiv' ORDER BY run_id"
            ).fetchall():
                rid = lease["run_id"]
                conn.execute(
                    "UPDATE slot_leases SET state = 'unterbrochen', reason = ? WHERE run_id = ?",
                    ("server_aus" if state == "aus" else "server_gesperrt", rid))
                interrupted.append(rid)
        conn.execute(
            "INSERT OR REPLACE INTO slot_server (name, gen, recipe, slots, context_per_slot, state, pid, since, restarts, garbage, reason, owner) "
            "VALUES ('main', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (new_gen, new_recipe, new_slots, new_ctx, state, new_pid, new_since,
             old["restarts"], old["garbage"], new_reason, new_owner))
        conn.execute(
            "INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, ?, NULL, ?)",
            (now, "server_" + state, new_recipe if new_recipe is not None else ""))
        return {"name": "main", "gen": new_gen, "recipe": new_recipe, "slots": new_slots,
                "context_per_slot": new_ctx, "state": state, "pid": new_pid, "since": new_since,
                "restarts": old["restarts"], "garbage": old["garbage"],
                "reason": new_reason, "owner": new_owner, "interrupted": interrupted}


def request(conn, run_id, kind, owner, priority, now, agent_id=None, task_id=None, ttl_s=120):
    _check_request(run_id, kind, owner, priority, ttl_s)
    with immediate(conn):
        row = conn.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()
        if row is not None and row["state"] in ("wartend", "aktiv"):
            return {"run_id": run_id, "neu": False}
        conn.execute(
            "INSERT OR REPLACE INTO slot_leases (run_id, kind, owner, priority, enqueued, state, agent_id, task_id, "
            "slot, server_gen, started, heartbeat, ttl_s, reason) "
            "VALUES (?, ?, ?, ?, ?, 'wartend', ?, ?, NULL, NULL, NULL, NULL, ?, NULL)",
            (run_id, kind, owner, priority, now, agent_id, task_id, ttl_s))
        return {"run_id": run_id, "neu": True}


def note(conn, field, now, window_s):
    if field not in ("restarts", "garbage"):
        raise ValueError("field_invalid")
    if isinstance(window_s, bool) or not isinstance(window_s, int) or window_s < 1:
        raise ValueError("window_invalid")
    limit_str = (datetime.strptime(now, FORMAT) - timedelta(seconds=window_s)).strftime(FORMAT)
    with immediate(conn):
        row = conn.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone()
        if row is None:
            old = _empty_server()
        else:
            old = dict(row)
        old_list = json.loads(old[field]) if old[field] else []
        filtered = [t for t in old_list if t >= limit_str]
        filtered.append(now)
        new_json = json.dumps(filtered)
        new_since = now if old["since"] is None else old["since"]
        conn.execute(
            "INSERT OR REPLACE INTO slot_server (name, gen, recipe, slots, context_per_slot, state, pid, since, restarts, garbage, reason, owner) "
            "VALUES ('main', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (old["gen"], old["recipe"], old["slots"], old["context_per_slot"],
             old["state"], old["pid"], new_since,
             new_json if field == "restarts" else old["restarts"],
             new_json if field == "garbage" else old["garbage"],
             old["reason"], old["owner"]))
        return len(filtered)


def take(conn, run_id, now, cfg, recipe=None):
    with immediate(conn):
        row = conn.execute("SELECT * FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()
        if row is None or row["state"] != "wartend":
            raise ValueError("lease_not_requested")
        server_row = conn.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone()
        server = dict(server_row) if server_row else _default_server()
        mode = server["state"] if server["state"] in ("drain", "exklusiv") else "normal"
        active = [dict(r) for r in conn.execute("SELECT * FROM slot_leases WHERE state = 'aktiv'").fetchall()]
        waiting = [dict(r) for r in conn.execute("SELECT * FROM slot_leases WHERE state = 'wartend'").fetchall()]
        reason = decide_reason(server, recipe, mode, active, cfg)
        if reason is None and run_id in admit(server, active, waiting, mode, now, cfg):
            used_slots = {r["slot"] for r in active if r["slot"] is not None}
            n = 1
            while n in used_slots:
                n += 1
            conn.execute(
                "UPDATE slot_leases SET state = 'aktiv', slot = ?, server_gen = ?, started = ?, heartbeat = ?, reason = NULL WHERE run_id = ?",
                (n, server["gen"], now, now, run_id))
            conn.execute("INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, ?, ?, ?)",
                         (now, "take", run_id, str(n)))
            return {"granted": True, "slot": n, "reason": None}
        else:
            if reason is None:
                reason = "wartet_in_reihe"
            conn.execute("UPDATE slot_leases SET reason = ? WHERE run_id = ?", (reason, run_id))
            return {"granted": False, "slot": None, "reason": reason}


def release(conn, run_id, outcome, now):
    if outcome not in ('fertig', 'unterbrochen'):
        raise ValueError('outcome_invalid')
    with immediate(conn):
        row = conn.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()
        if row is None or row["state"] in ('fertig', 'unterbrochen', 'verfallen'):
            return False
        new_state = outcome if row["state"] == 'aktiv' else 'verfallen'
        conn.execute("UPDATE slot_leases SET state = ? WHERE run_id = ?", (new_state, run_id))
        conn.execute("INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, ?, ?, ?)",
                     (now, 'release', run_id, outcome))
        return True


def beat(conn, run_id, now):
    with immediate(conn):
        cursor = conn.execute(
            "UPDATE slot_leases SET heartbeat = ? WHERE run_id = ? AND state = 'aktiv'",
            (now, run_id))
        return cursor.rowcount > 0


def reap(conn, live_run_ids, now):
    with immediate(conn):
        placeholders = ','.join(['?' for _ in live_run_ids]) if live_run_ids else 'NULL'
        if live_run_ids:
            rows = conn.execute(
                "SELECT run_id FROM slot_leases WHERE state IN ('wartend', 'aktiv') AND run_id NOT IN ({})".format(placeholders),
                live_run_ids).fetchall()
        else:
            rows = conn.execute("SELECT run_id FROM slot_leases WHERE state IN ('wartend', 'aktiv')").fetchall()
        result = []
        for row in rows:
            rid = row["run_id"]
            conn.execute("UPDATE slot_leases SET state = 'verfallen' WHERE run_id = ?", (rid,))
            conn.execute("INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, ?, ?, ?)",
                         (now, 'reap', rid, ''))
            result.append(rid)
        return sorted(result)


def handover_request(conn, owner, purpose, priority, pid, now, ttl_s=60):
    _check_owner_priority_ttl(owner, priority, ttl_s)
    with immediate(conn):
        row = conn.execute("SELECT * FROM handover_requests WHERE owner = ?", (owner,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO handover_requests (owner, purpose, priority, pid, since, heartbeat, ttl_s) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (owner, purpose[:200], priority, pid, now, now, ttl_s))
            conn.execute("INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, ?, NULL, ?)",
                         (now, "handover", owner))
            return True
        else:
            conn.execute(
                "UPDATE handover_requests SET purpose = ?, priority = ?, pid = ?, heartbeat = ?, ttl_s = ? WHERE owner = ?",
                (purpose[:200], priority, pid, now, ttl_s, owner))
            return False


def handover_clear(conn, owner):
    with immediate(conn):
        cursor = conn.execute("DELETE FROM handover_requests WHERE owner = ?", (owner,))
        return cursor.rowcount > 0


def handover_pending(conn, now):
    now_dt = datetime.strptime(now, FORMAT)
    rows = conn.execute(
        "SELECT * FROM handover_requests ORDER BY priority DESC, since ASC, owner ASC"
    ).fetchall()
    result = []
    for r in rows:
        try:
            hb = datetime.strptime(r["heartbeat"], FORMAT)
            ttl = r["ttl_s"]
            if hb + timedelta(seconds=ttl) >= now_dt:
                result.append(dict(r))
        except (ValueError, TypeError):
            pass
    return result


def events(conn, limit=20):
    rows = conn.execute("SELECT * FROM slot_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def view(conn, now, cfg):
    server_row = conn.execute("SELECT * FROM slot_server WHERE name = 'main'").fetchone()
    if server_row is None:
        server = _default_server()
    else:
        server = {"state": server_row["state"], "gen": server_row["gen"],
                  "recipe": server_row["recipe"], "slots": server_row["slots"]}
    gesamt = server["slots"] if server["slots"] is not None else 0
    aktiv_rows = conn.execute("SELECT * FROM slot_leases WHERE state = 'aktiv' ORDER BY slot").fetchall()
    belegt = [{"slot": r["slot"], "run_id": r["run_id"], "agent_id": r["agent_id"],
               "task_id": r["task_id"], "prioritaet": r["priority"], "seit": r["started"]}
              for r in aktiv_rows]
    wartend_rows = conn.execute("SELECT * FROM slot_leases WHERE state = 'wartend'").fetchall()
    waiting = [dict(r) for r in wartend_rows]
    ordered = order(waiting, now, cfg)
    schlange = [{"run_id": r["run_id"], "agent_id": r["agent_id"], "prioritaet": r["priority"],
                 "seit": r["enqueued"], "grund": r["reason"]} for r in ordered]
    warnung = needs_cloud_offer(waiting, now, cfg)
    return {"server": server, "gesamt": gesamt, "belegt": belegt, "schlange": schlange, "warnung": warnung}
