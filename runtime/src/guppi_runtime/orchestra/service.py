PARTS = ("guard", "supervisor", "templates")


def _error_text(exc, prefix, fallback):
    if isinstance(exc, ValueError) and str(exc).startswith(prefix):
        return str(exc)
    return fallback


def _query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    if not rows:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


class Orchestra:
    def __init__(self, config, conn, audit=None, guard=None, supervisor=None, templates=None):
        self.config = config
        self.conn = conn
        self.audit = audit
        self.guard = guard
        self.supervisor = supervisor
        self.templates = templates

    def schema_version(self):
        rows = _query(self.conn, "SELECT value FROM meta WHERE key = ?", ("schema_version",))
        if not rows:
            return 0
        return int(rows[0]["value"])

    def close(self):
        self.conn.close()

    def agents(self):
        return _query(self.conn, "SELECT * FROM agents ORDER BY id")

    def agent(self, agent_id):
        rows = _query(self.conn, "SELECT * FROM agents WHERE id = ?", (agent_id,))
        return rows[0] if rows else None

    def routines(self):
        return _query(self.conn, "SELECT * FROM routines ORDER BY id")

    def routine(self, routine_id):
        rows = _query(self.conn, "SELECT * FROM routines WHERE id = ?", (routine_id,))
        return rows[0] if rows else None

    def spent(self, agent_id):
        rows = _query(self.conn, "SELECT tokens_in, tokens_out, eur_cent, requests FROM spend WHERE agent_id = ?", (agent_id,))
        if not rows:
            return {"tokens": 0, "eur_cent": 0, "requests": 0}
        total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in rows)
        total_eur_cent = sum(r["eur_cent"] for r in rows)
        total_requests = sum(r["requests"] for r in rows)
        return {"tokens": total_tokens, "eur_cent": total_eur_cent, "requests": total_requests}

    def issues(self, state=None, assignee=None):
        sql = "SELECT * FROM tasks"
        params = []
        conditions = []
        if state is not None:
            conditions.append("state = ?")
            params.append(state)
        if assignee is not None:
            conditions.append("assignee = ?")
            params.append(assignee)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY priority DESC, created_at, id"
        return _query(self.conn, sql, tuple(params))

    def issue(self, task_id):
        rows = _query(self.conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        return rows[0] if rows else None


def build(switch_on, load_config, open_db, config_path, runtime_data, audit=None, **parts):
    for key in parts:
        if key not in PARTS:
            raise TypeError(f"Unexpected part: {key}")
    if switch_on is not True:
        return (None, None)
    try:
        config = load_config(config_path)
    except Exception as exc:
        error = _error_text(exc, "orchestra_config_", "orchestra_config_invalid:unreadable")
        if audit is not None:
            audit("ORCHESTRA_OFF", {"reason": error})
        return (None, error)
    try:
        conn = open_db(config.database_path(runtime_data))
    except Exception as exc:
        error = _error_text(exc, "orchestra_", "orchestra_db_error:open")
        if audit is not None:
            audit("ORCHESTRA_OFF", {"reason": error})
        return (None, error)
    return (Orchestra(config, conn, audit=audit, **parts), None)


def boot_entry(orchestra, error):
    return {
        "enabled": orchestra is not None,
        "error": error,
        "schema_version": orchestra.schema_version() if orchestra is not None else None,
    }
