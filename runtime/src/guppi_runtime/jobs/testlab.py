"""The test lab: one small SQLite file that several chats, scripts and GUPPI instances share (Phase 9c).

Problem: every test run starts a model on the one GPU (and on one fixed llama-server port). Two runs at the same time corrupt each
other's measurements or crash each other. Nobody should have to guess whether the GPU is free.

What is in the file
  lease     ONE row, "gpu". Whoever holds it may start models. It carries owner, purpose, pid, and a heartbeat. A lease whose heartbeat is
            older than its ttl, or whose process no longer exists, is stale and is taken over (and says so in `events`).
  queue     planned test rounds, so another chat can see what is coming and what is already done: nobody repeats a round.
  runs      one row per measurement run, with its settings.
  results   one row per call/task of a run (model, variant, task, ok, tokens, seconds), so rounds can be compared later.
  events    what happened to the lease (acquired, released, stale takeover, refused, deferred).
  reservations  a chain that must come first (Captain 2026-10-13: "als erstes in die Nacht-Warteschlange"): while a live reservation of priority P exists, every taker with a
            LOWER priority (the default is 0) is deferred, also in the gaps between two builds of the chain. It dies with its process or when its heartbeat is stale; without a
            reservation nothing changes (the race of the polling takers stays as it was).
  slot_*    Schema 2 (Spec 2, D2.3): the model scheduler's tables `slot_server`, `slot_leases`, `handover_requests`, `slot_events`, word for word
            from the seed `benchmarks/s2_schema_seed/slot_db.py`. Times there are UTC text (`YYYY-MM-DDTHH:MM:SSZ`), the old tables keep REAL.
            `acquire` registers a taker that has to wait in `handover_requests` (`register_waiter`), so the scheduler can hand the GPU over (D2.7).

It never starts or stops a model itself and has no say over files outside the database. SQLite in WAL mode, `BEGIN IMMEDIATE` for the
lease, so two processes cannot both win it.

Default location: <project>/runtime_data/testlab/testlab.db
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS lease (name TEXT PRIMARY KEY, owner TEXT NOT NULL, purpose TEXT NOT NULL, pid INTEGER NOT NULL,
    acquired REAL NOT NULL, heartbeat REAL NOT NULL, ttl_s REAL NOT NULL, token TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, owner TEXT NOT NULL, kind TEXT NOT NULL,
    description TEXT NOT NULL, models TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'planned', note TEXT NOT NULL DEFAULT '', updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started REAL NOT NULL, finished REAL, owner TEXT NOT NULL, kind TEXT NOT NULL,
    label TEXT NOT NULL, config TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'running', queue_id INTEGER, pid INTEGER);
CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id), ts REAL NOT NULL,
    model TEXT NOT NULL, variant TEXT NOT NULL DEFAULT '', task TEXT NOT NULL DEFAULT '', ok INTEGER, tokens_in INTEGER, tokens_out INTEGER,
    seconds REAL, extra TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS results_run ON results(run_id);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT NOT NULL, owner TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS reservations (owner TEXT PRIMARY KEY, purpose TEXT NOT NULL, priority INTEGER NOT NULL, pid INTEGER NOT NULL, since REAL NOT NULL, heartbeat REAL NOT NULL, ttl_s REAL NOT NULL);
"""
from . import testlab_slots
from .testlab_slots import SCHEMA_VERSION, SLOT_SCHEMA, TIME_FORMAT, utc_text  # noqa: F401  (re-exported: slot_db and the scheduler import them from here)

QUEUE_STATUS = ("planned", "running", "done", "cancelled")
RUN_STATUS = ("running", "done", "failed", "aborted")


class LeaseBusy(Exception):
    def __init__(self, holder):
        self.holder = holder
        super().__init__(f"gpu lease held by {holder['owner']} for '{holder['purpose']}' (pid {holder['pid']}, heartbeat {holder['age_s']:.0f}s ago)")


def default_path(project):
    return Path(project) / "runtime_data" / "testlab" / "testlab.db"


def pid_alive(pid):
    """True when a process with this pid exists. (os.kill(pid, 0) would TERMINATE the process on Windows, so it is never used there.)"""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259     # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TestLab:
    __test__ = False                       # not a unittest case, despite the name

    def __init__(self, path, *, clock=time.time, alive=pid_alive, pid=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock, self.alive, self.pid = clock, alive, pid if pid is not None else os.getpid()
        self.schema, self.schema_error, self.backup = 1, None, None
        with self._db() as db:
            db.executescript(SCHEMA)
            if not any(c["name"] == "pid" for c in db.execute("PRAGMA table_info(runs)")):
                db.execute("ALTER TABLE runs ADD COLUMN pid INTEGER")       # databases from before the liveness check
            self._migrate(db)

    def _migrate(self, db):
        """Schema 2 (see testlab_slots.migrate): a failure leaves schema 1 and says why in `schema_error`."""
        self.schema, self.schema_error, self.backup = testlab_slots.migrate(db, self.path, self.clock())

    def connect(self):
        """A connection for the slot store (`slot_store.py`): same file, WAL, busy timeout, rows by name. The caller closes it."""
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _text(value, limit=500):
        return str(value)[:limit]

    def _event(self, db, kind, owner, detail=""):
        db.execute("INSERT INTO events (ts, kind, owner, detail) VALUES (?,?,?,?)", (self.clock(), kind, owner, self._text(detail)))

    # ---- the GPU lease -------------------------------------------------------------------------------------------------------
    def holder(self, name="gpu"):
        """The current holder as a dict (with `age_s` and `stale`), or None when the lease is free."""
        with self._db() as db:
            row = db.execute("SELECT * FROM lease WHERE name=?", (name,)).fetchone()
        return self._describe(row) if row else None

    def _describe(self, row):
        info = dict(row)
        info["age_s"] = max(0.0, self.clock() - row["heartbeat"])
        info["stale"] = info["age_s"] > row["ttl_s"] or not self.alive(row["pid"])
        return info

    def try_acquire(self, owner, purpose, *, ttl_s=300, name="gpu", priority=0):
        """The lease token, or None when somebody else holds it or a live reservation of a higher priority waits (see `reserve`). A stale holder is replaced (and logged)."""
        token = uuid.uuid4().hex
        now = self.clock()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                blocker = self._blocking_reservation(db, owner, priority)
                if blocker:
                    self._event(db, "deferred", owner, f"{purpose}; reservation of {blocker['owner']} (priority {blocker['priority']})")
                    db.execute("COMMIT")
                    return None
                row = db.execute("SELECT * FROM lease WHERE name=?", (name,)).fetchone()
                if row:
                    info = self._describe(row)
                    if not info["stale"]:
                        self._event(db, "refused", owner, f"{purpose}; held by {row['owner']}")
                        db.execute("COMMIT")
                        return None
                    self._event(db, "stale_takeover", owner, f"was {row['owner']} ({row['purpose']}), pid {row['pid']}, silent {info['age_s']:.0f}s")
                    db.execute("DELETE FROM lease WHERE name=?", (name,))
                db.execute("INSERT INTO lease (name, owner, purpose, pid, acquired, heartbeat, ttl_s, token) VALUES (?,?,?,?,?,?,?,?)",
                           (name, self._text(owner, 80), self._text(purpose, 200), self.pid, now, now, float(ttl_s), token))
                self._event(db, "acquired", owner, purpose)
                db.execute("COMMIT")
                return token
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def acquire(self, owner, purpose, *, ttl_s=300, wait_s=0, poll_s=5, sleep=time.sleep, name="gpu", priority=0):
        """Wait up to `wait_s` for the lease. A taker that has to wait stands in `handover_requests` meanwhile (D2.7): the model scheduler
        sees it, drains its slots and gives the GPU back. The entry is gone once the lease is granted or the wait is given up."""
        deadline = self.clock() + wait_s
        waiting = False
        try:
            while True:
                token = self.try_acquire(owner, purpose, ttl_s=ttl_s, name=name, priority=priority)
                if token:
                    return token
                if self.clock() >= deadline:
                    raise LeaseBusy(self.holder(name))
                if name == "gpu":
                    self.register_waiter(owner, purpose, priority=priority, ttl_s=max(60, int(poll_s * 3)))
                    waiting = True
                sleep(poll_s)
        finally:
            if waiting:
                self.clear_waiter(owner)

    def register_waiter(self, owner, purpose, *, priority=0, ttl_s=60):
        """Enter (or refresh) a taker that waits for the GPU in `handover_requests`; True when it is new. Without schema 2 nothing happens."""
        if self.schema < SCHEMA_VERSION:
            return False
        with self._db() as db:
            return testlab_slots.write_waiter(db, self._text(owner, 80), self._text(purpose, 200), min(9, max(0, int(priority))), self.pid,
                                              utc_text(self.clock()), int(ttl_s))

    def clear_waiter(self, owner):
        """Remove a waiting taker's entry (lease granted or wait given up)."""
        if self.schema < SCHEMA_VERSION:
            return False
        with self._db() as db:
            return testlab_slots.clear_waiter(db, self._text(owner, 80))

    def _live_reservation(self, row):
        return self.clock() - row["heartbeat"] <= row["ttl_s"] and self.alive(row["pid"])

    def _blocking_reservation(self, db, owner, priority):
        for row in db.execute("SELECT * FROM reservations WHERE priority > ? AND owner != ? ORDER BY priority DESC, since", (int(priority), owner)):
            if self._live_reservation(row):
                return dict(row)
        return None

    def reservations(self):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM reservations ORDER BY priority DESC, since") if self._live_reservation(r)]

    @contextmanager
    def reserve(self, owner, purpose, *, priority=1, ttl_s=120):
        """`with lab.reserve("night-g", "G builds", priority=1): ...builds that take the lease with priority=1...`. While the block runs and its process lives, takers with a lower priority wait,
        so the chain comes first even between two of its builds. A thread keeps the heartbeat; the reservation is removed on exit, also on an exception."""
        now = self.clock()
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO reservations (owner, purpose, priority, pid, since, heartbeat, ttl_s) VALUES (?,?,?,?,?,?,?)",
                       (self._text(owner, 80), self._text(purpose, 200), int(priority), self.pid, now, now, float(ttl_s)))
            self._event(db, "reserved", owner, f"{purpose} (priority {int(priority)})")
        stop = threading.Event()

        def beat():
            while not stop.wait(max(1.0, ttl_s / 3)):
                with self._db() as db:
                    db.execute("UPDATE reservations SET heartbeat=? WHERE owner=?", (self.clock(), self._text(owner, 80)))
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=2)
            with self._db() as db:
                db.execute("DELETE FROM reservations WHERE owner=?", (self._text(owner, 80),))
                self._event(db, "unreserved", owner)

    def heartbeat(self, token, name="gpu"):
        with self._db() as db:
            cur = db.execute("UPDATE lease SET heartbeat=? WHERE name=? AND token=?", (self.clock(), name, token))
        return cur.rowcount == 1               # False: the lease was taken over (we were silent too long)

    def release(self, token, name="gpu"):
        with self._db() as db:
            row = db.execute("SELECT owner FROM lease WHERE name=? AND token=?", (name, token)).fetchone()
            if not row:
                return False
            db.execute("DELETE FROM lease WHERE name=? AND token=?", (name, token))
            self._event(db, "released", row["owner"])
        return True

    @contextmanager
    def lease(self, owner, purpose, *, ttl_s=300, wait_s=0, poll_s=5, name="gpu", sleep=time.sleep, preflight=None, priority=0):
        """`with lab.lease("me", "quality round gemma", wait_s=600): ...start models, measure...`. A thread keeps the heartbeat going
        while the block runs; the lease is released on exit, also on an exception.
        `preflight(owner)` runs once the lease is held and before the block (see gpu_preflight.clear_leftovers: removes what earlier runs left
        on the GPU). If it raises, the lease is released and the exception goes to the caller. TestLab itself still never stops a model."""
        token = self.acquire(owner, purpose, ttl_s=ttl_s, wait_s=wait_s, poll_s=poll_s, name=name, sleep=sleep, priority=priority)
        if preflight is not None:
            try:
                preflight(owner)
            except BaseException as exc:
                with self._db() as db:
                    self._event(db, "preflight_failed", owner, str(exc)[:300])
                self.release(token, name)
                raise
        stop = threading.Event()

        def beat():
            while not stop.wait(max(1.0, ttl_s / 3)):
                self.heartbeat(token, name)
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield token
        finally:
            stop.set()
            thread.join(timeout=2)
            self.release(token, name)

    # ---- planned rounds ------------------------------------------------------------------------------------------------------
    def plan(self, owner, kind, description, models=()):
        with self._db() as db:
            cur = db.execute("INSERT INTO queue (created, owner, kind, description, models, updated) VALUES (?,?,?,?,?,?)",
                             (self.clock(), self._text(owner, 80), self._text(kind, 60), self._text(description), ",".join(models), self.clock()))
        return cur.lastrowid

    def set_queue_status(self, queue_id, status, note=""):
        if status not in QUEUE_STATUS:
            raise ValueError("invalid_queue_status")
        with self._db() as db:
            cur = db.execute("UPDATE queue SET status=?, note=?, updated=? WHERE id=?", (status, self._text(note), self.clock(), queue_id))
        return cur.rowcount == 1

    def queue(self, statuses=("planned", "running")):
        with self._db() as db:
            marks = ",".join("?" * len(statuses))
            return [dict(r) for r in db.execute(f"SELECT * FROM queue WHERE status IN ({marks}) ORDER BY id", tuple(statuses))]

    # ---- is a "running" round still running? -----------------------------------------------------------------------------------
    def activity(self):
        """For every queue entry and every run that says `running`: is anything alive behind it?
        A run is alive while the process that started it is (`runs.pid`). A round without a live run counts as alive while its owner holds a fresh
        GPU lease. Anything else is `active: False`: it was never finished, e.g. the chat or the script died. Rows from before the pid column
        have no pid; for them only the lease can vouch."""
        holder = self.holder()
        lease_owner = holder["owner"] if holder and not holder["stale"] else None
        with self._db() as db:
            queue = [dict(r) for r in db.execute("SELECT * FROM queue WHERE status='running' ORDER BY id")]
            runs = [dict(r) for r in db.execute("SELECT * FROM runs WHERE status='running' ORDER BY id")]
        for r in runs:
            r["active"], r["why"] = (True, f"process {r['pid']} is alive") if r["pid"] and self.alive(r["pid"]) else                 (True, "its owner holds the GPU lease") if r["owner"] == lease_owner else (False, "no live process and no lease")
        for q in queue:
            live = next((r for r in runs if r["queue_id"] == q["id"] and r["active"]), None)
            q["active"], q["why"] = (True, f"run {live['id']} is alive") if live else                 (True, "its owner holds the GPU lease") if q["owner"] == lease_owner else (False, "no live run and no lease")
        return {"queue": queue, "runs": runs}

    def reap_stale(self, min_age_s=1800):
        """Only on request: puts rounds that nothing vouches for back on the plan (like a failed run) and marks their runs `aborted`.
        Entries touched within `min_age_s` are left alone: a chat may be between two steps. Returns {'queue': [ids], 'runs': [ids]}."""
        now, seen = self.clock(), self.activity()
        queue = [q["id"] for q in seen["queue"] if not q["active"] and now - q["updated"] >= min_age_s]
        runs = [r["id"] for r in seen["runs"] if not r["active"] and now - r["started"] >= min_age_s]
        with self._db() as db:
            for rid in runs:
                db.execute("UPDATE runs SET finished=?, status='aborted' WHERE id=?", (now, rid))
                self._event(db, "reaped_run", "testlab", f"run {rid}: no live process")
            for qid in queue:
                db.execute("UPDATE queue SET status='planned', note=?, updated=? WHERE id=?", (self._text("orphaned: nothing was running behind it, back on the plan"), now, qid))
                self._event(db, "reaped_round", "testlab", f"round {qid}: no live process")
        return {"queue": queue, "runs": runs}

    # ---- runs and results ----------------------------------------------------------------------------------------------------
    def start_run(self, owner, kind, label, config=None, queue_id=None):
        with self._db() as db:
            cur = db.execute("INSERT INTO runs (started, owner, kind, label, config, queue_id, pid) VALUES (?,?,?,?,?,?,?)",
                             (self.clock(), self._text(owner, 80), self._text(kind, 60), self._text(label, 200), json.dumps(config or {}, sort_keys=True), queue_id, self.pid))
            if queue_id:
                db.execute("UPDATE queue SET status='running', updated=? WHERE id=?", (self.clock(), queue_id))
        return cur.lastrowid

    def record(self, run_id, model, *, variant="", task="", ok=None, tokens_in=None, tokens_out=None, seconds=None, **extra):
        with self._db() as db:
            db.execute("INSERT INTO results (run_id, ts, model, variant, task, ok, tokens_in, tokens_out, seconds, extra) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (run_id, self.clock(), model, variant, task, None if ok is None else int(bool(ok)), tokens_in, tokens_out, seconds, json.dumps(extra, sort_keys=True, default=str)))

    def finish_run(self, run_id, status="done"):
        if status not in RUN_STATUS:
            raise ValueError("invalid_run_status")
        with self._db() as db:
            db.execute("UPDATE runs SET finished=?, status=? WHERE id=?", (self.clock(), status, run_id))
            row = db.execute("SELECT queue_id FROM runs WHERE id=?", (run_id,)).fetchone()
            if row and row["queue_id"]:
                db.execute("UPDATE queue SET status=?, updated=? WHERE id=?", ("done" if status == "done" else "planned", self.clock(), row["queue_id"]))

    def runs(self, limit=20):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))]

    def summary(self, run_id):
        """Per model and variant: calls, share ok, mean tokens out, mean seconds."""
        with self._db() as db:
            rows = db.execute("SELECT model, variant, COUNT(*) AS n, AVG(ok) AS ok_rate, AVG(tokens_out) AS tokens_out, AVG(seconds) AS seconds "
                              "FROM results WHERE run_id=? GROUP BY model, variant ORDER BY model, variant", (run_id,)).fetchall()
        return [dict(r) for r in rows]

    def events(self, limit=20):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]
