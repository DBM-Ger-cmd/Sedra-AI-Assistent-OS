import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS slot_server (name TEXT PRIMARY KEY CHECK (name = 'main'), gen INTEGER NOT NULL DEFAULT 0, recipe TEXT, slots INTEGER,
    context_per_slot INTEGER, state TEXT NOT NULL CHECK (state IN ('aus', 'startet', 'bereit', 'drain', 'exklusiv', 'gesperrt')), pid INTEGER,
    since TEXT NOT NULL, restarts TEXT NOT NULL DEFAULT '[]', garbage TEXT NOT NULL DEFAULT '[]', reason TEXT, owner TEXT);
CREATE TABLE IF NOT EXISTS slot_leases (run_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('job', 'direkt')), owner TEXT NOT NULL, agent_id TEXT,
    task_id TEXT, priority INTEGER NOT NULL CHECK (priority BETWEEN 0 AND 9), enqueued TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('wartend', 'aktiv', 'fertig', 'unterbrochen', 'verfallen')), slot INTEGER, server_gen INTEGER, started TEXT,
    heartbeat TEXT, ttl_s INTEGER NOT NULL DEFAULT 120, reason TEXT);
CREATE INDEX IF NOT EXISTS slot_leases_state ON slot_leases(state);
CREATE TABLE IF NOT EXISTS handover_requests (owner TEXT PRIMARY KEY, purpose TEXT NOT NULL, priority INTEGER NOT NULL, pid INTEGER, since TEXT NOT NULL,
    heartbeat TEXT NOT NULL, ttl_s INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS slot_events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL, run_id TEXT, detail TEXT NOT NULL DEFAULT '');
"""


@contextmanager
def immediate(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def open_db(path, busy_ms=30000):
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=busy_ms / 1000, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {busy_ms}")
    conn.executescript(SCHEMA)
    return conn
