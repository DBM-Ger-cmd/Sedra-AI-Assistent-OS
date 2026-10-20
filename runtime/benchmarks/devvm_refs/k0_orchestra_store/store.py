import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
TABLES = ("meta", "agents", "tasks", "blockers", "comments", "wakeups", "routines", "routine_runs", "spend")

_V1 = (
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE agents (
        id TEXT PRIMARY KEY, instance_id TEXT NOT NULL UNIQUE, template_id TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL, recipe_id TEXT,
        reports_to TEXT REFERENCES agents(id),
        status TEXT NOT NULL CHECK (status IN ('aktiv', 'pausiert', 'beendet')),
        permission_level INTEGER NOT NULL CHECK (permission_level BETWEEN 0 AND 6),
        budget_tokens INTEGER, budget_eur_cent INTEGER,
        budget_period TEXT NOT NULL DEFAULT 'gesamt' CHECK (budget_period IN ('gesamt', 'monat')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1)""",
    "CREATE INDEX agents_reports_to ON agents (reports_to)",
    "CREATE INDEX agents_status ON agents (status)",
    """CREATE TABLE tasks (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT, goal_ref TEXT, project_id TEXT,
        parent_id TEXT REFERENCES tasks(id), assignee TEXT REFERENCES agents(id),
        state TEXT NOT NULL CHECK (state IN ('offen', 'zugewiesen', 'in_arbeit', 'wartet', 'erledigt', 'abgebrochen')),
        priority INTEGER NOT NULL DEFAULT 0, checkout_by TEXT, checkout_at TEXT, checkout_run TEXT, mission_id TEXT,
        created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1)""",
    "CREATE INDEX tasks_assignee_state ON tasks (assignee, state)",
    "CREATE INDEX tasks_parent ON tasks (parent_id)",
    "CREATE INDEX tasks_mission ON tasks (mission_id)",
    "CREATE INDEX tasks_checkout ON tasks (checkout_by) WHERE checkout_by IS NOT NULL",
    """CREATE TABLE blockers (
        task_id TEXT NOT NULL REFERENCES tasks(id), blocked_by_task_id TEXT NOT NULL REFERENCES tasks(id), created_at TEXT NOT NULL,
        PRIMARY KEY (task_id, blocked_by_task_id), CHECK (task_id <> blocked_by_task_id))""",
    "CREATE INDEX blockers_by ON blockers (blocked_by_task_id)",
    """CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id),
        author_kind TEXT NOT NULL CHECK (author_kind IN ('captain', 'agent', 'system')), author_id TEXT, text TEXT NOT NULL, ts TEXT NOT NULL)""",
    "CREATE INDEX comments_task_ts ON comments (task_id, ts)",
    """CREATE TABLE wakeups (
        id INTEGER PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), task_id TEXT,
        reason TEXT NOT NULL CHECK (reason IN ('zugewiesen', 'antwort', 'routine', 'captain', 'wiederholung')),
        due_at TEXT NOT NULL, created_at TEXT NOT NULL, coalesced_into INTEGER REFERENCES wakeups(id), job_id TEXT, done_at TEXT)""",
    "CREATE INDEX wakeups_due ON wakeups (agent_id, due_at) WHERE done_at IS NULL AND coalesced_into IS NULL",
    """CREATE TABLE routines (
        id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), title TEXT NOT NULL, cron TEXT NOT NULL,
        timezone TEXT NOT NULL DEFAULT 'Europe/Berlin', catch_up TEXT NOT NULL CHECK (catch_up IN ('nachholen', 'auslassen')),
        enabled INTEGER NOT NULL DEFAULT 1, task_template TEXT NOT NULL, last_run TEXT, next_run TEXT)""",
    "CREATE INDEX routines_next ON routines (next_run) WHERE enabled = 1",
    """CREATE TABLE routine_runs (
        routine_id TEXT NOT NULL, due_at TEXT NOT NULL, task_id TEXT,
        outcome TEXT NOT NULL CHECK (outcome IN ('erzeugt', 'ausgelassen', 'nachgeholt')), PRIMARY KEY (routine_id, due_at))""",
    """CREATE TABLE spend (
        id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL, task_id TEXT, mission_id TEXT,
        provider TEXT NOT NULL CHECK (provider IN ('lokal', 'cloud')), provider_id TEXT, model TEXT,
        tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 1,
        eur_cent INTEGER NOT NULL DEFAULT 0, ts TEXT NOT NULL)""",
    "CREATE INDEX spend_agent_ts ON spend (agent_id, ts)",
    "CREATE INDEX spend_provider_ts ON spend (provider_id, ts)",
    "CREATE INDEX spend_task ON spend (task_id)",
)
MIGRATIONS = {1: _V1}


def _db_error(reason):
    return ValueError(f"orchestra_db_error:{reason}")


def schema_version(conn):
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0


@contextmanager
def immediate(conn):
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc) or "busy" in str(exc):
            raise ValueError("orchestra_busy") from None
        raise
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def migrate(conn, target=SCHEMA_VERSION, migrations=None):
    steps = MIGRATIONS if migrations is None else migrations
    current = schema_version(conn)
    if current > target:
        raise _db_error("schema_newer")
    for version in range(current + 1, target + 1):
        if version not in steps:
            raise _db_error(f"no_migration_{version}")
        with immediate(conn):
            for statement in steps[version]:
                conn.execute(statement)
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)", (str(version),))
    return schema_version(conn)


def open_db(path, target=SCHEMA_VERSION, migrations=None, busy_ms=30000):
    memory = str(path) == ":memory:"
    try:
        if not memory:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), isolation_level=None, timeout=busy_ms / 1000, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {int(busy_ms)}")
        conn.execute("PRAGMA foreign_keys = ON")
        if not memory:
            conn.execute("PRAGMA journal_mode = WAL")
    except (sqlite3.Error, OSError):
        raise _db_error("open") from None
    try:
        migrate(conn, target, migrations)
    except ValueError:
        conn.close()
        raise
    except sqlite3.Error:
        conn.close()
        raise _db_error("migration") from None
    return conn
