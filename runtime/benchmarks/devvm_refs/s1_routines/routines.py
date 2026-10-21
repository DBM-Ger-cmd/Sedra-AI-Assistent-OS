import uuid

import cron
from store import immediate

FIELDS = ("id", "agent_id", "title", "cron", "timezone", "catch_up", "task_template")
REQUIRED = ("agent_id", "title", "cron", "catch_up")
CATCH_UP = ("nachholen", "auslassen")
CLOSED = ("erledigt", "abgebrochen")
LIMIT = 1000


def _routine(conn, rid):
    row = conn.execute("SELECT * FROM routines WHERE id = ?", (rid,)).fetchone()
    return dict(row) if row else None


def _need(conn, rid):
    routine = _routine(conn, rid)
    if routine is None:
        raise ValueError("routine_not_found")
    return routine


def _next(expr, tz, now):
    return cron.next_after(cron.parse(expr), now, tz)


def _check(fields, allowed):
    unknown = sorted(set(fields) - set(allowed))
    if unknown:
        raise ValueError("routine_field_unknown:" + unknown[0])
    if "title" in fields and not (isinstance(fields["title"], str) and fields["title"].strip()):
        raise ValueError("routine_title_invalid")
    if "catch_up" in fields and fields["catch_up"] not in CATCH_UP:
        raise ValueError("routine_catch_up_invalid")


def _agent(conn, agent_id):
    if conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone() is None:
        raise ValueError("agent_not_found")


def _set(conn, rid, values):
    conn.execute("UPDATE routines SET %s WHERE id = ?" % ", ".join("%s = ?" % k for k in values), list(values.values()) + [rid])
    return _routine(conn, rid)


def create(conn, fields, now):
    _check(fields, FIELDS)
    missing = [k for k in REQUIRED if fields.get(k) is None]
    if missing:
        raise ValueError("routine_field_missing:" + missing[0])
    values = {"timezone": "Europe/Berlin", **fields}
    next_run = _next(values["cron"], values["timezone"], now)
    with immediate(conn):
        _agent(conn, values["agent_id"])
        values["id"] = values.get("id") or "R-" + uuid.uuid4().hex[:12]
        if _routine(conn, values["id"]) is not None:
            raise ValueError("routine_exists")
        values.update(enabled=1, last_run=now, next_run=next_run)
        names = list(values)
        conn.execute("INSERT INTO routines (%s) VALUES (%s)" % (", ".join(names), ", ".join("?" * len(names))), [values[n] for n in names])
        return _routine(conn, values["id"])


def update(conn, rid, fields, now):
    _check(fields, FIELDS[1:])
    with immediate(conn):
        routine = _need(conn, rid)
        if "agent_id" in fields:
            _agent(conn, fields["agent_id"])
        values = dict(fields)
        if "cron" in values or "timezone" in values:
            merged = {**routine, **values}
            next_run = _next(merged["cron"], merged["timezone"], now)
            if routine["enabled"]:
                values.update(last_run=now, next_run=next_run)
        return _set(conn, rid, values) if values else routine


def set_enabled(conn, rid, on, now):
    with immediate(conn):
        routine = _need(conn, rid)
        if bool(routine["enabled"]) == bool(on):
            return routine
        if on:
            return _set(conn, rid, {"enabled": 1, "last_run": now, "next_run": _next(routine["cron"], routine["timezone"], now)})
        return _set(conn, rid, {"enabled": 0, "next_run": None})


def _outcomes(dates, catch_up, max_catch_up, skip_all):
    if skip_all:
        return ["ausgelassen"] * len(dates)
    older = len(dates) - 1
    kept = 0 if catch_up == "auslassen" else min(max_catch_up, older)
    return ["ausgelassen"] * (older - kept) + ["nachgeholt"] * kept + ["erzeugt"]


def _previous_open(conn, rid):
    row = conn.execute("SELECT t.state FROM routine_runs r JOIN tasks t ON t.id = r.task_id WHERE r.routine_id = ? ORDER BY r.due_at DESC LIMIT 1", (rid,)).fetchone()
    return row is not None and row[0] not in CLOSED


def _claim(conn, routine, now, max_catch_up):
    dates = cron.due_between(cron.parse(routine["cron"]), routine["last_run"] or now, now, routine["timezone"], LIMIT)[:LIMIT]
    if not dates:
        return []
    status = conn.execute("SELECT status FROM agents WHERE id = ?", (routine["agent_id"],)).fetchone()
    skip_all = status is None or status[0] != "aktiv" or _previous_open(conn, routine["id"])
    claimed = []
    for due_at, outcome in zip(dates, _outcomes(dates, routine["catch_up"], max_catch_up, skip_all)):
        cur = conn.execute("INSERT OR IGNORE INTO routine_runs (routine_id, due_at, outcome) VALUES (?, ?, ?)", (routine["id"], due_at, outcome))
        if cur.rowcount == 1:
            claimed.append({"routine_id": routine["id"], "due_at": due_at, "outcome": outcome, "task_id": None})
    _set(conn, routine["id"], {"last_run": now, "next_run": _next(routine["cron"], routine["timezone"], now)})
    return claimed


def fire_due(conn, now, max_catch_up, make_task):
    results = []
    for routine in [dict(r) for r in conn.execute("SELECT * FROM routines WHERE enabled = 1 ORDER BY id")]:
        with immediate(conn):
            claimed = _claim(conn, routine, now, max_catch_up)
        for item in claimed:
            if item["outcome"] != "ausgelassen":
                item["task_id"] = make_task(routine, item["due_at"])
                with immediate(conn):
                    conn.execute("UPDATE routine_runs SET task_id = ? WHERE routine_id = ? AND due_at = ?", (item["task_id"], item["routine_id"], item["due_at"]))
        results += claimed
    return results
