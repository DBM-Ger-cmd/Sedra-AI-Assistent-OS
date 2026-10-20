PARTS = ("guard", "supervisor", "templates")
_ISSUE_ORDER = " ORDER BY priority DESC, created_at, id"


class Orchestra:
    def __init__(self, config, conn, audit=None, guard=None, supervisor=None, templates=None):
        self.config, self.conn, self.audit = config, conn, audit
        self.guard, self.supervisor, self.templates = guard, supervisor, templates

    def _rows(self, sql, args=()):
        cursor = self.conn.execute(sql, args)
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def _one(self, sql, args):
        rows = self._rows(sql, args)
        return rows[0] if rows else None

    def schema_version(self):
        row = self._one("SELECT value FROM meta WHERE key = ?", ("schema_version",))
        return int(row["value"]) if row else 0

    def agents(self):
        return self._rows("SELECT * FROM agents ORDER BY id")

    def agent(self, agent_id):
        return self._one("SELECT * FROM agents WHERE id = ?", (agent_id,))

    def issues(self, state=None, assignee=None):
        where, args = [], []
        for column, value in (("state", state), ("assignee", assignee)):
            if value is not None:
                where.append(f"{column} = ?")
                args.append(value)
        clause = " WHERE " + " AND ".join(where) if where else ""
        return self._rows("SELECT * FROM tasks" + clause + _ISSUE_ORDER, args)

    def issue(self, task_id):
        return self._one("SELECT * FROM tasks WHERE id = ?", (task_id,))

    def routines(self):
        return self._rows("SELECT * FROM routines ORDER BY id")

    def routine(self, routine_id):
        return self._one("SELECT * FROM routines WHERE id = ?", (routine_id,))

    def spent(self, agent_id):
        row = self._one("SELECT COALESCE(SUM(tokens_in + tokens_out), 0) AS tokens, COALESCE(SUM(eur_cent), 0) AS eur_cent, "
                        "COALESCE(SUM(requests), 0) AS requests FROM spend WHERE agent_id = ?", (agent_id,))
        return {"tokens": row["tokens"], "eur_cent": row["eur_cent"], "requests": row["requests"]}

    def close(self):
        self.conn.close()


def _reason(exc, prefix, fallback):
    text = str(exc) if isinstance(exc, ValueError) else ""
    return text if text.startswith(prefix) else fallback


def build(switch_on, load_config, open_db, config_path, runtime_data, audit=None, **parts):
    unknown = sorted(set(parts) - set(PARTS))
    if unknown:
        raise TypeError(f"unknown part: {unknown[0]}")
    if switch_on is not True:
        return None, None
    try:
        config = load_config(config_path)
    except Exception as exc:
        return _off(audit, _reason(exc, "orchestra_config_", "orchestra_config_invalid:unreadable"))
    try:
        conn = open_db(config.database_path(runtime_data))
    except Exception as exc:
        return _off(audit, _reason(exc, "orchestra_", "orchestra_db_error:open"))
    return Orchestra(config, conn, audit=audit, **parts), None


def _off(audit, reason):
    if audit is not None:
        audit("ORCHESTRA_OFF", {"reason": reason})
    return None, reason


def boot_entry(orchestra, error):
    return {"enabled": orchestra is not None, "error": error, "schema_version": orchestra.schema_version() if orchestra is not None else None}
