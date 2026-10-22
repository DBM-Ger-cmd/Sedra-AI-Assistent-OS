from .store import immediate

VALID_ROLLE = ('captain', 'agent', 'system')
VALID_STATUS = ('angenommen', 'wartet_freigabe', 'laeuft', 'beantwortet', 'fehler')


def add(conn, agent_id, rolle, text, now, key=None, status='angenommen', issue_id=None):
    if rolle not in VALID_ROLLE:
        raise ValueError('message_role_invalid')
    if status not in VALID_STATUS:
        raise ValueError('message_status_invalid')
    if not isinstance(text, str):
        raise ValueError('message_empty')
    if not text.strip():
        raise ValueError('message_empty')
    if len(text) > 8000:
        raise ValueError('message_too_long')

    with immediate(conn):
        row = conn.execute(
            "SELECT id FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            raise ValueError('agent_not_found')

        if key is not None:
            existing = conn.execute(
                "SELECT id FROM agent_messages WHERE agent_id = ? AND idempotency_key = ?",
                (agent_id, key)
            ).fetchone()
            if existing is not None:
                return {"id": existing[0], "neu": False}

        cur = conn.execute(
            """INSERT INTO agent_messages
               (agent_id, rolle, text, ts, status, issue_id, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, rolle, text, now, status, issue_id, key)
        )
        msg_id = cur.lastrowid

    return {"id": msg_id, "neu": True}


ALLOWED_TRANSITIONS = {
    'angenommen': {'wartet_freigabe', 'laeuft', 'fehler'},
    'wartet_freigabe': {'laeuft', 'fehler'},
    'laeuft': {'beantwortet', 'fehler'},
    'beantwortet': set(),
    'fehler': set(),
}


def set_status(conn, msg_id, status, now, mission_id=None):
    if status not in VALID_STATUS:
        raise ValueError('message_status_invalid')

    with immediate(conn):
        row = conn.execute(
            "SELECT id, agent_id, rolle, text, ts, status, issue_id, mission_id, route, provider_id, model, idempotency_key FROM agent_messages WHERE id = ?",
            (msg_id,)
        ).fetchone()
        if row is None:
            raise ValueError('message_not_found')

        current_status = row[5]
        if status not in ALLOWED_TRANSITIONS.get(current_status, set()):
            raise ValueError('message_status_invalid')

        if mission_id is not None:
            conn.execute(
                """UPDATE agent_messages
                   SET status = ?, mission_id = ?
                   WHERE id = ?""",
                (status, mission_id, msg_id)
            )
        else:
            conn.execute(
                """UPDATE agent_messages
                   SET status = ?
                   WHERE id = ?""",
                (status, msg_id)
            )

        row = conn.execute(
            "SELECT id, agent_id, rolle, text, ts, status, issue_id, mission_id, route, provider_id, model, idempotency_key FROM agent_messages WHERE id = ?",
            (msg_id,)
        ).fetchone()

    return {
        "id": row[0],
        "agent_id": row[1],
        "rolle": row[2],
        "text": row[3],
        "ts": row[4],
        "status": row[5],
        "issue_id": row[6],
        "mission_id": row[7],
        "route": row[8],
        "provider_id": row[9],
        "model": row[10],
        "idempotency_key": row[11],
    }


def page(conn, agent_id, before_id=None, limit=50):
    if type(limit) is not int or limit < 1 or limit > 200:
        raise ValueError('page_limit_invalid')

    if before_id is not None:
        sub = conn.execute(
            """SELECT id FROM agent_messages
               WHERE agent_id = ? AND id < ?
               ORDER BY id DESC
               LIMIT ?""",
            (agent_id, before_id, limit),
        ).fetchall()
        ids = [r[0] for r in sub]
        if not ids:
            rows = []
            mehr = False
        else:
            placeholders = ','.join('?' for _ in ids)
            rows = conn.execute(
                f"""SELECT id, agent_id, rolle, text, ts, status, issue_id, mission_id, route, provider_id, model, idempotency_key
                    FROM agent_messages
                    WHERE agent_id = ? AND id IN ({placeholders})
                    ORDER BY id ASC""",
                (agent_id, *ids),
            ).fetchall()
            if len(ids) == limit:
                min_id = min(ids)
                mehr = conn.execute(
                    """SELECT COUNT(*) FROM agent_messages
                       WHERE agent_id = ? AND id < ?""",
                    (agent_id, min_id),
                ).fetchone()[0] > 0
            else:
                mehr = False
    else:
        sub = conn.execute(
            """SELECT id FROM agent_messages
               WHERE agent_id = ?
               ORDER BY id DESC
               LIMIT ?""",
            (agent_id, limit),
        ).fetchall()
        ids = [r[0] for r in sub]
        if not ids:
            rows = []
            mehr = False
        else:
            placeholders = ','.join('?' for _ in ids)
            rows = conn.execute(
                f"""SELECT id, agent_id, rolle, text, ts, status, issue_id, mission_id, route, provider_id, model, idempotency_key
                    FROM agent_messages
                    WHERE agent_id = ? AND id IN ({placeholders})
                    ORDER BY id ASC""",
                (agent_id, *ids),
            ).fetchall()
            if len(ids) == limit:
                min_id = min(ids)
                mehr = conn.execute(
                    """SELECT COUNT(*) FROM agent_messages
                       WHERE agent_id = ? AND id < ?""",
                    (agent_id, min_id),
                ).fetchone()[0] > 0
            else:
                mehr = False

    items = [
        {
            "id": row[0],
            "agent_id": row[1],
            "rolle": row[2],
            "text": row[3],
            "ts": row[4],
            "status": row[5],
            "issue_id": row[6],
            "mission_id": row[7],
            "route": row[8],
            "provider_id": row[9],
            "model": row[10],
            "idempotency_key": row[11],
        }
        for row in rows
    ]

    return {"items": items, "mehr": mehr}


def last(conn, agent_id):
    row = conn.execute(
        """SELECT id FROM agent_messages
           WHERE agent_id = ?
           ORDER BY id DESC
           LIMIT 1""",
        (agent_id,),
    ).fetchone()
    if row is None:
        return None
    return row[0]
