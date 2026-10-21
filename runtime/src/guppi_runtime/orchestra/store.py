import sqlite3
from contextlib import contextmanager

SCHEMA_VERSION = 1

TABLES = ("meta", "agents", "tasks", "blockers", "comments", "wakeups", "routines", "routine_runs", "spend")

MIGRATIONS = {
    1: (
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE agents (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL UNIQUE, template_id TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL, recipe_id, reports_to TEXT REFERENCES agents(id), status TEXT NOT NULL CHECK (status IN ('aktiv','pausiert','beendet')), permission_level INTEGER NOT NULL CHECK (permission_level >= 0 AND permission_level <= 6), budget_tokens, budget_eur_cent, budget_period TEXT NOT NULL DEFAULT 'gesamt' CHECK (budget_period IN ('gesamt','monat')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1)",
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description, goal_ref, project_id, parent_id REFERENCES tasks(id), assignee TEXT REFERENCES agents(id), state TEXT NOT NULL CHECK (state IN ('offen','zugewiesen','in_arbeit','wartet','erledigt','abgebrochen')), priority INTEGER NOT NULL DEFAULT 0, checkout_by, checkout_at, checkout_run, mission_id, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1)",
        "CREATE TABLE blockers (task_id TEXT NOT NULL REFERENCES tasks(id), blocked_by_task_id TEXT NOT NULL REFERENCES tasks(id), created_at TEXT NOT NULL, PRIMARY KEY (task_id, blocked_by_task_id), CHECK (task_id <> blocked_by_task_id))",
        "CREATE TABLE comments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id), author_kind TEXT NOT NULL CHECK (author_kind IN ('captain','agent','system')), author_id, text TEXT NOT NULL, ts TEXT NOT NULL)",
        "CREATE TABLE wakeups (id INTEGER PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), task_id TEXT, reason TEXT NOT NULL CHECK (reason IN ('zugewiesen','antwort','routine','captain','wiederholung')), due_at TEXT NOT NULL, created_at TEXT NOT NULL, coalesced_into INTEGER REFERENCES wakeups(id), job_id TEXT, done_at TEXT)",
        "CREATE TABLE routines (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), title TEXT NOT NULL, cron TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'Europe/Berlin', catch_up TEXT NOT NULL CHECK (catch_up IN ('nachholen','auslassen')), enabled INTEGER NOT NULL DEFAULT 1, task_template TEXT, last_run TEXT, next_run TEXT)",
        "CREATE TABLE routine_runs (routine_id TEXT NOT NULL, due_at TEXT NOT NULL, task_id TEXT, outcome TEXT CHECK (outcome IN ('erzeugt','ausgelassen','nachgeholt')), PRIMARY KEY (routine_id, due_at))",
        "CREATE TABLE spend (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL, task_id TEXT, mission_id TEXT, provider TEXT NOT NULL CHECK (provider IN ('lokal','cloud')), provider_id TEXT, model TEXT, tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 1, eur_cent INTEGER NOT NULL DEFAULT 0, ts TEXT NOT NULL)",
        "CREATE INDEX idx_agents_reports_to ON agents (reports_to)",
        "CREATE INDEX idx_agents_status ON agents (status)",
        "CREATE INDEX idx_tasks_assignee_state ON tasks (assignee, state)",
        "CREATE INDEX idx_tasks_parent_id ON tasks (parent_id)",
        "CREATE INDEX idx_tasks_mission_id ON tasks (mission_id)",
        "CREATE INDEX idx_tasks_checkout_by ON tasks (checkout_by) WHERE checkout_by IS NOT NULL",
        "CREATE INDEX idx_blockers_blocked_by_task_id ON blockers (blocked_by_task_id)",
        "CREATE INDEX idx_comments_task_id_ts ON comments (task_id, ts)",
        "CREATE INDEX idx_wakeups_agent_id_due_at ON wakeups (agent_id, due_at) WHERE done_at IS NULL AND coalesced_into IS NULL",
        "CREATE INDEX idx_routines_next_run ON routines (next_run) WHERE enabled = 1",
        "CREATE INDEX idx_spend_agent_id_ts ON spend (agent_id, ts)",
        "CREATE INDEX idx_spend_provider_id_ts ON spend (provider_id, ts)",
        "CREATE INDEX idx_spend_task_id ON spend (task_id)",
    ),
}


def schema_version(conn):
    try:
        cur = conn.execute(
            "SELECT value FROM meta WHERE key = ?", ("schema_version",)
        )
        row = cur.fetchone()
        if row is None:
            return 0
        return int(row[0])
    except sqlite3.OperationalError:
        return 0


@contextmanager
def immediate(conn):
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "locked" in msg or "busy" in msg:
            raise ValueError("orchestra_busy") from None
        raise
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def migrate(conn, target=SCHEMA_VERSION, migrations=None):
    if migrations is None:
        migrations = MIGRATIONS
    current = schema_version(conn)
    if current > target:
        raise ValueError("orchestra_db_error:schema_newer")
    for ver in range(current + 1, target + 1):
        if ver not in migrations:
            raise ValueError(f"orchestra_db_error:no_migration_{ver}")
        with immediate(conn):
            for stmt in migrations[ver]:
                conn.execute(stmt)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("schema_version", str(ver)),
            )
    return schema_version(conn)


def open_db(path, target=SCHEMA_VERSION, migrations=None, busy_ms=30000):
    from pathlib import Path
    conn = None
    try:
        if str(path) == ":memory:":
            conn = sqlite3.connect(
                str(path),
                isolation_level=None,
                timeout=busy_ms / 1000,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {busy_ms}")
            conn.execute("PRAGMA foreign_keys = ON")
        else:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(path),
                isolation_level=None,
                timeout=busy_ms / 1000,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {busy_ms}")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
    except (sqlite3.Error, OSError):
        if conn is not None:
            conn.close()
        raise ValueError("orchestra_db_error:open")
    try:
        migrate(conn, target, migrations)
    except ValueError:
        conn.close()
        raise
    except sqlite3.Error:
        conn.close()
        raise ValueError("orchestra_db_error:migration")
    return conn
