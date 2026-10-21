import uuid

import graphs
from store import immediate

FIELDS = ("id", "title", "description", "goal_ref", "project_id", "parent_id", "assignee", "priority", "origin", "max_level")
ORIGINS = ("captain", "routine", "delegation", "system")
CLOSED = ("erledigt", "abgebrochen")
RELEASE = ("zugewiesen", "offen", "wartet", "erledigt")
AUTHORS = ("captain", "agent", "system")
RESULTS = ("gruen", "rot", "nicht_geprueft")
CLEAR = {"checkout_by": None, "checkout_run": None, "checkout_at": None}


def _task(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def _need(conn, task_id):
    task = _task(conn, task_id)
    if task is None:
        raise ValueError("task_not_found")
    return task


def _agent(conn, agent_id):
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if row is None:
        raise ValueError("agent_not_found")
    return dict(row)


def _active(conn, agent_id):
    agent = _agent(conn, agent_id)
    if agent["status"] != "aktiv":
        raise ValueError("agent_inactive")
    return agent


def _update(conn, task_id, values, now):
    sets = ", ".join("%s = ?" % k for k in values)
    conn.execute("UPDATE tasks SET %s, updated_at = ?, revision = revision + 1 WHERE id = ?" % sets, list(values.values()) + [now, task_id])
    return _task(conn, task_id)


def _open_blockers(conn, task_id):
    return conn.execute("SELECT count(*) FROM blockers b JOIN tasks t ON t.id = b.blocked_by_task_id WHERE b.task_id = ? AND t.state NOT IN ('erledigt', 'abgebrochen')",
                        (task_id,)).fetchone()[0]


def _check_fields(fields):
    unknown = sorted(set(fields) - set(FIELDS))
    if unknown:
        raise ValueError("task_field_unknown:" + unknown[0])
    title = fields.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("task_title_invalid")
    if fields.get("origin", "captain") not in ORIGINS:
        raise ValueError("task_origin_invalid")
    level = fields.get("max_level")
    if level is not None and not (type(level) is int and 0 <= level <= 6):
        raise ValueError("level_not_allowed")
    if type(fields.get("priority", 0)) is not int:
        raise ValueError("task_field_invalid:priority")


def _insert(conn, fields, now, created_by):
    values = {"origin": "captain", "priority": 0, **fields}
    values["id"] = values.get("id") or "T-" + uuid.uuid4().hex[:12]
    if _task(conn, values["id"]) is not None:
        raise ValueError("task_exists")
    if values.get("parent_id") is not None:
        _need(conn, values["parent_id"])
    if values.get("assignee") is not None:
        _active(conn, values["assignee"])
    values.update(state="zugewiesen" if values.get("assignee") else "offen", created_by=created_by, created_at=now, updated_at=now)
    names = list(values)
    conn.execute("INSERT INTO tasks (%s) VALUES (%s)" % (", ".join(names), ", ".join("?" * len(names))), [values[n] for n in names])
    return _task(conn, values["id"])


def create(conn, fields, now, created_by):
    _check_fields(fields)
    with immediate(conn):
        return _insert(conn, fields, now, created_by)


def assign(conn, task_id, agent_id, now, by):
    with immediate(conn):
        task = _need(conn, task_id)
        if task["state"] in CLOSED:
            raise ValueError("task_closed")
        if task["checkout_by"]:
            raise ValueError("task_checked_out")
        _active(conn, agent_id)
        return {"task": _update(conn, task_id, {"assignee": agent_id, "state": "zugewiesen"}, now), "old": task["assignee"]}


def checkout(conn, task_id, agent_id, run_id, now):
    with immediate(conn):
        task = _need(conn, task_id)
        if task["checkout_by"]:
            raise ValueError("task_already_checked_out")
        if task["assignee"] != agent_id or task["state"] not in ("zugewiesen", "offen"):
            raise ValueError("task_not_assignable")
        if _open_blockers(conn, task_id):
            raise ValueError("task_blocked")
        cur = conn.execute("UPDATE tasks SET checkout_by = ?, checkout_run = ?, checkout_at = ?, state = 'in_arbeit', updated_at = ?, revision = revision + 1 "
                           "WHERE id = ? AND checkout_by IS NULL", (agent_id, run_id, now, now, task_id))
        if cur.rowcount != 1:
            raise ValueError("task_already_checked_out")
        return _task(conn, task_id)


def set_blocker(conn, task_id, blocked_by, now):
    if task_id == blocked_by:
        raise ValueError("blocker_self")
    with immediate(conn):
        _need(conn, task_id)
        _need(conn, blocked_by)
        edges = [tuple(r) for r in conn.execute("SELECT task_id, blocked_by_task_id FROM blockers")]
        if (task_id, blocked_by) in edges:
            return
        if graphs.has_cycle(edges + [(task_id, blocked_by)]):
            raise ValueError("blocker_cycle")
        conn.execute("INSERT INTO blockers (task_id, blocked_by_task_id, created_at) VALUES (?, ?, ?)", (task_id, blocked_by, now))


def clear_blocker(conn, task_id, blocked_by, now):
    with immediate(conn):
        cur = conn.execute("DELETE FROM blockers WHERE task_id = ? AND blocked_by_task_id = ?", (task_id, blocked_by))
        if cur.rowcount != 1:
            raise ValueError("blocker_not_found")
        return _open_blockers(conn, task_id)


def _comment(conn, task_id, author_kind, author_id, text, now):
    cur = conn.execute("INSERT INTO comments (task_id, author_kind, author_id, text, ts) VALUES (?, ?, ?, ?, ?)", (task_id, author_kind, author_id, text, now))
    return cur.lastrowid


def _check_text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("comment_empty")
    if len(text) > 8000:
        raise ValueError("text_too_long")


def release(conn, task_id, run_id, state, now, comment=None):
    if state not in RELEASE:
        raise ValueError("task_state_invalid")
    if comment is not None:
        _check_text(comment)
    with immediate(conn):
        task = _need(conn, task_id)
        if task["checkout_run"] is None or task["checkout_run"] != run_id:
            raise ValueError("run_mismatch")
        values = dict(CLEAR, state=state)
        if state == "offen":
            values["assignee"] = None
        if comment is not None:
            _comment(conn, task_id, "system", None, comment, now)
        return _update(conn, task_id, values, now)


def cancel(conn, task_id, now, by):
    with immediate(conn):
        task = _need(conn, task_id)
        if task["state"] in CLOSED:
            raise ValueError("task_closed")
        return {"task": _update(conn, task_id, dict(CLEAR, state="abgebrochen"), now), "run_id": task["checkout_run"]}


def comment(conn, task_id, author_kind, author_id, text, now):
    if author_kind not in AUTHORS:
        raise ValueError("comment_author_invalid")
    _check_text(text)
    with immediate(conn):
        _need(conn, task_id)
        return _comment(conn, task_id, author_kind, author_id, text, now)


def set_check(conn, task_id, result, ref, now):
    if result not in RESULTS:
        raise ValueError("check_result_invalid")
    with immediate(conn):
        _need(conn, task_id)
        return _update(conn, task_id, {"check_result": result, "check_ref": ref}, now)


def chain_rows(conn, task_id):
    task = _need(conn, task_id)
    parents, seen, parent = [], {task_id}, task["parent_id"]
    while parent is not None and parent not in seen:
        row = _task(conn, parent)
        if row is None:
            break
        seen.add(parent)
        parents.insert(0, row)
        parent = row["parent_id"]
    return {"task": task, "parents": parents}


def children_done(conn, root_id):
    states = [r[0] for r in conn.execute("SELECT state FROM tasks WHERE parent_id = ?", (root_id,))]
    return bool(states) and all(s in CLOSED for s in states)


def orphans(conn, live_run_ids):
    live = set(live_run_ids)
    rows = conn.execute("SELECT * FROM tasks WHERE checkout_run IS NOT NULL ORDER BY id").fetchall()
    return [dict(r) for r in rows if r["checkout_run"] not in live]


def delegate(conn, parent_id, frm, items, now):
    if not items:
        raise ValueError("delegate_empty")
    with immediate(conn):
        parent = _need(conn, parent_id)
        if parent["state"] in CLOSED:
            raise ValueError("task_closed")
        if parent["decomposed_at"] is not None:
            raise ValueError("task_already_decomposed")
        boss = _agent(conn, frm)
        rows = [dict(r) for r in conn.execute("SELECT id, reports_to, status FROM agents")]
        created = []
        for item in items:
            target = _agent(conn, item["agent_id"])
            graphs.check_delegation(rows, frm, target["id"], boss["can_delegate"])
            text = item.get("beschreibung") or ""
            if item.get("akzeptanz"):
                text += "\n\nAkzeptanz: " + item["akzeptanz"]
            fields = {"title": item["titel"], "description": text, "parent_id": parent_id, "assignee": target["id"], "origin": "delegation",
                      "max_level": graphs.inherit_level(parent["max_level"], target["permission_level"])}
            _check_fields(fields)
            created.append(_insert(conn, fields, now, frm))
        for task, item in zip(created, items):
            for index in item.get("blocker") or []:
                conn.execute("INSERT INTO blockers (task_id, blocked_by_task_id, created_at) VALUES (?, ?, ?)", (task["id"], created[index]["id"], now))
        _update(conn, parent_id, {"decomposed_at": now}, now)
        return [_task(conn, t["id"]) for t in created]
