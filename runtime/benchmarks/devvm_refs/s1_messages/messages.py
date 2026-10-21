from store import immediate

ROLES = ("captain", "agent", "system")
STATUSES = ("angenommen", "wartet_freigabe", "laeuft", "beantwortet", "fehler")
NEXT = {"angenommen": ("wartet_freigabe", "laeuft", "fehler"), "wartet_freigabe": ("laeuft", "fehler"), "laeuft": ("beantwortet", "fehler")}
MAX_TEXT = 8000


def _row(conn, msg_id):
    row = conn.execute("SELECT * FROM agent_messages WHERE id = ?", (msg_id,)).fetchone()
    return dict(row) if row else None


def add(conn, agent_id, rolle, text, now, key=None, status="angenommen", issue_id=None):
    if rolle not in ROLES:
        raise ValueError("message_role_invalid")
    if status not in STATUSES:
        raise ValueError("message_status_invalid")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("message_empty")
    if len(text) > MAX_TEXT:
        raise ValueError("message_too_long")
    with immediate(conn):
        if conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone() is None:
            raise ValueError("agent_not_found")
        if key is not None:
            old = conn.execute("SELECT id FROM agent_messages WHERE agent_id = ? AND idempotency_key = ?", (agent_id, key)).fetchone()
            if old is not None:
                return {"id": old[0], "neu": False}
        cur = conn.execute("INSERT INTO agent_messages (agent_id, rolle, text, ts, status, issue_id, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (agent_id, rolle, text, now, status, issue_id, key))
        return {"id": cur.lastrowid, "neu": True}


def set_status(conn, msg_id, status, now, mission_id=None):
    with immediate(conn):
        msg = _row(conn, msg_id)
        if msg is None:
            raise ValueError("message_not_found")
        if status not in NEXT.get(msg["status"], ()):
            raise ValueError("message_status_invalid")
        conn.execute("UPDATE agent_messages SET status = ?, mission_id = COALESCE(?, mission_id) WHERE id = ?", (status, mission_id, msg_id))
        return _row(conn, msg_id)


def page(conn, agent_id, before_id=None, limit=50):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("page_limit_invalid")
    sql, args = "SELECT * FROM agent_messages WHERE agent_id = ?", [agent_id]
    if before_id is not None:
        sql += " AND id < ?"
        args.append(before_id)
    rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", args + [limit + 1]).fetchall()
    return {"items": [dict(r) for r in reversed(rows[:limit])], "mehr": len(rows) > limit}


def last(conn, agent_id):
    row = conn.execute("SELECT max(id) FROM agent_messages WHERE agent_id = ?", (agent_id,)).fetchone()
    return row[0]
