"""Schema 2 of the test lab (Spec 2, S2.H1, D2.3): the model scheduler's slot tables, the migration with backup, and the entry of a taker
that waits for the GPU (`handover_requests`, D2.7). Used by `testlab.TestLab`; no import of it, so both stay small."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SLOT_SCHEMA = """
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
SCHEMA_VERSION = 2
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"      # the slot tables' time text (slotplan.FORMAT)


def utc_text(ts):
    """Epoch seconds as the UTC text of the slot tables."""
    return datetime.fromtimestamp(ts, timezone.utc).strftime(TIME_FORMAT)


def backup_path(path, stamp):
    target = path.with_name(f"{path.name}.bak-{stamp}-schema2")
    n = 1
    while target.exists():
        n += 1
        target = path.with_name(f"{path.name}.bak-{stamp}-schema2-{n}")
    return target


def migrate(db, path, now_ts):
    """Schema 2 on an open connection: (schema, error, backup path). A file that already holds data gets a backup first
    (`testlab.db.bak-<date>-schema2`, rule 3). When the backup or the migration fails the file stays at schema 1 and `error` says why:
    the lease works as before, only the model scheduler stays off (D2.12)."""
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return version, None, None
    used = any(db.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() for t in ("lease", "queue", "runs", "results", "events", "reservations"))
    backup = None
    try:
        if used:
            target = backup_path(path, datetime.fromtimestamp(now_ts, timezone.utc).strftime("%Y%m%d"))
            copy = sqlite3.connect(target)
            try:
                db.backup(copy)
            finally:
                copy.close()
            backup = target
        db.executescript("BEGIN IMMEDIATE;" + SLOT_SCHEMA + f"PRAGMA user_version = {SCHEMA_VERSION};COMMIT;")
        return SCHEMA_VERSION, None, backup
    except (sqlite3.Error, OSError) as exc:
        if db.in_transaction:
            db.execute("ROLLBACK")
        return 1, f"testlab_schema2_failed:{type(exc).__name__}", backup


def write_waiter(db, owner, purpose, priority, pid, now, ttl_s):
    """Enter or refresh a waiting taker in one transaction; True when it is new (then one `handover` event, not one per poll)."""
    db.execute("BEGIN IMMEDIATE")
    try:
        new = db.execute("SELECT 1 FROM handover_requests WHERE owner=?", (owner,)).fetchone() is None
        if new:
            db.execute("INSERT INTO handover_requests (owner, purpose, priority, pid, since, heartbeat, ttl_s) VALUES (?,?,?,?,?,?,?)",
                       (owner, purpose, priority, pid, now, now, ttl_s))
            db.execute("INSERT INTO slot_events (ts, kind, run_id, detail) VALUES (?, 'handover', NULL, ?)", (now, owner))
        else:
            db.execute("UPDATE handover_requests SET purpose=?, priority=?, pid=?, heartbeat=?, ttl_s=? WHERE owner=?",
                       (purpose, priority, pid, now, ttl_s, owner))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return new


def clear_waiter(db, owner):
    return db.execute("DELETE FROM handover_requests WHERE owner=?", (owner,)).rowcount == 1
