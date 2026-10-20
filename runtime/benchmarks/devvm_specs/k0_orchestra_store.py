"""Spec 0, K0.17 (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, design D3.1 and D3.3, gate G2-S0-09; Captain OP-5: the database secures itself with transactions and WAL):
`orchestra/store.py`, the SQLite store of the orchestration package. Schema version 1 is exactly the data model of D3.3 (tables meta, agents, tasks, blockers, comments,
wakeups, routines, routine_runs, spend, with their CHECKs, keys and indexes); `migrate` brings a database up to the version of the code, a database NEWER than the code is
refused; `immediate` is the helper for `BEGIN IMMEDIATE` (the checkout of Spec 1 uses it); `open_db` opens with WAL, `busy_timeout` and `foreign_keys`. Every refusal is a
ValueError whose text `runtime.py` reports as `orchestra_error` (KERN-06). The logic of org, board, heartbeat, budget and routines comes in Spec 1.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/k0_orchestra_store)."""

NOTES = '''# Notes for k0_orchestra_store
Python 3 standard library only (sqlite3, contextlib, pathlib). Files are touched only through sqlite3 and the folder creation of `open_db`; no process or network access.
Connections are opened with isolation_level=None (the code itself writes BEGIN, COMMIT and ROLLBACK). Every refusal is a ValueError with exactly the text the task names; sqlite3 errors of a statement inside `migrate` are NOT translated there.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. The SQL text is data: keep each CREATE statement as one string in a tuple.
'''

HEAD = r'''
import os, sqlite3, tempfile, time
from pathlib import Path
from store import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def refused(conn, sql, args=()):
    try:
        conn.execute(sql, args)
    except sqlite3.IntegrityError:
        return True
    return False


def mem():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


TMP = Path(tempfile.mkdtemp())
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = mem()
assert schema_version(c) == 0
c.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
assert schema_version(c) == 0
c.execute("INSERT INTO meta VALUES ('other', '9')")
assert schema_version(c) == 0
c.execute("INSERT INTO meta VALUES ('schema_version', '3')")
assert schema_version(c) == 3
c.execute("CREATE TABLE t (x INTEGER)")
with immediate(c) as same:
    assert same is c
    assert c.in_transaction
    c.execute("INSERT INTO t VALUES (1)")
assert not c.in_transaction
assert c.execute("SELECT count(*) FROM t").fetchone()[0] == 1
class Stop(Exception):
    pass
try:
    with immediate(c):
        c.execute("INSERT INTO t VALUES (2)")
        raise Stop()
except Stop:
    pass
else:
    raise AssertionError("exception swallowed")
assert not c.in_transaction
assert c.execute("SELECT count(*) FROM t").fetchone()[0] == 1
try:
    with immediate(c):
        c.execute("INSERT INTO t VALUES (3)")
        c.execute("INSERT INTO nowhere VALUES (3)")
except sqlite3.OperationalError:
    pass
else:
    raise AssertionError("sqlite error swallowed")
assert c.execute("SELECT count(*) FROM t").fetchone()[0] == 1
path = TMP / "busy.db"
a = sqlite3.connect(str(path), isolation_level=None)
a.execute("CREATE TABLE t (x)")
b = sqlite3.connect(str(path), isolation_level=None, timeout=0.2)
a.execute("BEGIN IMMEDIATE")
t0 = time.time()
raises("orchestra_busy", lambda: immediate(b).__enter__())
assert time.time() - t0 < 10
assert not b.in_transaction
a.execute("ROLLBACK")
with immediate(b):
    b.execute("INSERT INTO t VALUES (1)")
assert a.execute("SELECT count(*) FROM t").fetchone()[0] == 1
'''

C2 = r'''
assert SCHEMA_VERSION == 1
assert TABLES == ("meta", "agents", "tasks", "blockers", "comments", "wakeups", "routines", "routine_runs", "spend")
assert sorted(MIGRATIONS) == [1]
c = mem()
assert migrate(c) == 1
assert schema_version(c) == 1
assert not c.in_transaction
names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'") if not r[0].startswith("sqlite_")}
assert names == set(TABLES)
cols = lambda t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
assert cols("meta") == ["key", "value"]
assert cols("agents") == ["id", "instance_id", "template_id", "name", "role", "recipe_id", "reports_to", "status", "permission_level", "budget_tokens", "budget_eur_cent", "budget_period", "created_at", "updated_at", "revision"]
assert cols("tasks") == ["id", "title", "description", "goal_ref", "project_id", "parent_id", "assignee", "state", "priority", "checkout_by", "checkout_at", "checkout_run", "mission_id", "created_by", "created_at", "updated_at", "revision"]
assert cols("blockers") == ["task_id", "blocked_by_task_id", "created_at"]
assert cols("comments") == ["id", "task_id", "author_kind", "author_id", "text", "ts"]
assert cols("wakeups") == ["id", "agent_id", "task_id", "reason", "due_at", "created_at", "coalesced_into", "job_id", "done_at"]
assert cols("routines") == ["id", "agent_id", "title", "cron", "timezone", "catch_up", "enabled", "task_template", "last_run", "next_run"]
assert cols("routine_runs") == ["routine_id", "due_at", "task_id", "outcome"]
assert cols("spend") == ["id", "agent_id", "task_id", "mission_id", "provider", "provider_id", "model", "tokens_in", "tokens_out", "requests", "eur_cent", "ts"]
def indexes(table):
    out = set()
    for row in c.execute(f"PRAGMA index_list({table})"):
        if row[3] == "c":
            out.add((tuple(r[2] for r in c.execute(f"PRAGMA index_info({row[1]})")), bool(row[4])))
    return out
assert indexes("agents") == {(("reports_to",), False), (("status",), False)}
assert indexes("tasks") == {(("assignee", "state"), False), (("parent_id",), False), (("mission_id",), False), (("checkout_by",), True)}
assert indexes("blockers") == {(("blocked_by_task_id",), False)}
assert indexes("comments") == {(("task_id", "ts"), False)}
assert indexes("wakeups") == {(("agent_id", "due_at"), True)}
assert indexes("routines") == {(("next_run",), True)}
assert indexes("spend") == {(("agent_id", "ts"), False), (("provider_id", "ts"), False), (("task_id",), False)}
NOW = "2026-10-20T10:00:00Z"
AG = "INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
c.execute(AG, ("ua", "i1", "tpl", "Unterarbeiter", "unterarbeiter", None, "aktiv", 3, NOW, NOW))
row = c.execute("SELECT budget_period, revision FROM agents WHERE id = 'ua'").fetchone()
assert row == ("gesamt", 1)
assert refused(c, AG, ("x", "i1", "tpl", "X", "coder", None, "aktiv", 1, NOW, NOW))
assert refused(c, AG, ("x", "i2", "tpl", "X", "coder", "ghost", "aktiv", 1, NOW, NOW))
assert refused(c, AG, ("x", "i2", "tpl", "X", "coder", "ua", "schläft", 1, NOW, NOW))
assert refused(c, AG, ("x", "i2", "tpl", "X", "coder", "ua", "aktiv", 7, NOW, NOW))
assert refused(c, AG, ("x", "i2", "tpl", "X", "coder", "ua", "aktiv", -1, NOW, NOW))
assert refused(c, "INSERT INTO agents (id, instance_id, template_id, name, role, status, permission_level, budget_period, created_at, updated_at) VALUES ('y','i3','t','Y','r','aktiv',0,'woche',?,?)", (NOW, NOW))
c.execute(AG, ("cod", "i2", "tpl", "Coder", "coder", "ua", "aktiv", 2, NOW, NOW))
TK = "INSERT INTO tasks (id, title, assignee, parent_id, state, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)"
c.execute(TK, ("t1", "Bauen", "cod", None, "zugewiesen", "captain", NOW, NOW))
c.execute(TK, ("t2", "Prüfen", None, "t1", "offen", "captain", NOW, NOW))
assert c.execute("SELECT priority, revision FROM tasks WHERE id = 't1'").fetchone() == (0, 1)
assert refused(c, TK, ("t3", "X", "ghost", None, "offen", "captain", NOW, NOW))
assert refused(c, TK, ("t3", "X", None, "nope", "offen", "captain", NOW, NOW))
assert refused(c, TK, ("t3", "X", None, None, "fertig", "captain", NOW, NOW))
assert refused(c, "INSERT INTO tasks (id, title, state, created_at, updated_at) VALUES ('t4','X','offen',?,?)", (NOW, NOW))
c.execute("INSERT INTO blockers VALUES ('t1', 't2', ?)", (NOW,))
assert refused(c, "INSERT INTO blockers VALUES ('t1', 't2', ?)", (NOW,))
assert refused(c, "INSERT INTO blockers VALUES ('t2', 't2', ?)", (NOW,))
assert refused(c, "INSERT INTO blockers VALUES ('t2', 'ghost', ?)", (NOW,))
c.execute("INSERT INTO comments (task_id, author_kind, author_id, text, ts) VALUES ('t1', 'captain', NULL, 'los', ?)", (NOW,))
assert refused(c, "INSERT INTO comments (task_id, author_kind, text, ts) VALUES ('t1', 'gast', 'x', ?)", (NOW,))
assert refused(c, "INSERT INTO comments (task_id, author_kind, text, ts) VALUES ('ghost', 'agent', 'x', ?)", (NOW,))
c.execute("INSERT INTO wakeups (agent_id, task_id, reason, due_at, created_at) VALUES ('cod', 't1', 'zugewiesen', ?, ?)", (NOW, NOW))
assert refused(c, "INSERT INTO wakeups (agent_id, reason, due_at, created_at) VALUES ('cod', 'langeweile', ?, ?)", (NOW, NOW))
assert refused(c, "INSERT INTO wakeups (agent_id, reason, due_at, created_at, coalesced_into) VALUES ('cod', 'captain', ?, ?, 99)", (NOW, NOW))
assert refused(c, "INSERT INTO wakeups (agent_id, reason, due_at, created_at) VALUES ('ghost', 'captain', ?, ?)", (NOW, NOW))
c.execute("INSERT INTO routines (id, agent_id, title, cron, catch_up, task_template) VALUES ('r1', 'cod', 'Täglich', '0 6 * * *', 'nachholen', '{}')")
assert c.execute("SELECT timezone, enabled FROM routines").fetchone() == ("Europe/Berlin", 1)
assert refused(c, "INSERT INTO routines (id, agent_id, title, cron, catch_up, task_template) VALUES ('r2', 'cod', 'X', '* * * * *', 'immer', '{}')")
c.execute("INSERT INTO routine_runs VALUES ('r1', ?, 't1', 'erzeugt')", (NOW,))
assert refused(c, "INSERT INTO routine_runs VALUES ('r1', ?, NULL, 'nachgeholt')", (NOW,))
assert refused(c, "INSERT INTO routine_runs VALUES ('r1', '2026-10-21', NULL, 'vergessen')")
c.execute("INSERT INTO spend (agent_id, provider, ts) VALUES ('cod', 'lokal', ?)", (NOW,))
assert c.execute("SELECT tokens_in, tokens_out, requests, eur_cent FROM spend").fetchone() == (0, 0, 1, 0)
assert refused(c, "INSERT INTO spend (agent_id, provider, ts) VALUES ('cod', 'mond', ?)", (NOW,))
assert migrate(c) == 1
assert c.execute("SELECT count(*) FROM agents").fetchone()[0] == 2
raises("orchestra_db_error:schema_newer", migrate, c, 0)
two = {1: MIGRATIONS[1], 2: ("CREATE TABLE extra (x TEXT)",)}
keep = dict(two)
assert migrate(c, 2, two) == 2
assert two == keep
assert c.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0] == "2"
assert "extra" in {r[0] for r in c.execute("SELECT name FROM sqlite_master")}
raises("orchestra_db_error:schema_newer", migrate, c)
raises("orchestra_db_error:no_migration_3", migrate, c, 3, two)
d = mem()
raises("orchestra_db_error:no_migration_2", migrate, d, 2, {1: ("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",)})
assert schema_version(d) == 1
e = mem()
try:
    migrate(e, 1, {1: ("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)", "CREATE TABLE a (x)", "THIS IS NOT SQL")})
except sqlite3.Error:
    pass
else:
    raise AssertionError("broken migration passed")
assert not e.in_transaction
assert schema_version(e) == 0
assert {r[0] for r in e.execute("SELECT name FROM sqlite_master")} == set()
'''

C3 = r'''
path = TMP / "sub" / "deeper" / "orchestra.db"
c = open_db(path)
assert path.is_file()
assert c.isolation_level is None
assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
assert schema_version(c) == 1
row = c.execute("SELECT key, value FROM meta").fetchone()
assert row["key"] == "schema_version"
assert row["value"] == "1"
NOW = "2026-10-20T10:00:00Z"
c.execute("INSERT INTO agents (id, instance_id, template_id, name, role, status, permission_level, created_at, updated_at) VALUES ('ua','i1','t','U','unterarbeiter','aktiv',3,?,?)", (NOW, NOW))
assert refused(c, "INSERT INTO tasks (id, title, assignee, state, created_by, created_at, updated_at) VALUES ('t','X','ghost','offen','captain',?,?)", (NOW, NOW))
c.close()
again = open_db(str(path))
assert again.execute("SELECT name FROM agents").fetchone()["name"] == "U"
assert schema_version(again) == 1
again.execute("UPDATE meta SET value = '5' WHERE key = 'schema_version'")
again.close()
raises("orchestra_db_error:schema_newer", open_db, path)
m = open_db(":memory:")
assert schema_version(m) == 1
assert m.execute("PRAGMA foreign_keys").fetchone()[0] == 1
assert not (Path.cwd() / ":memory:").exists()
folder = TMP / "is_a_folder.db"
folder.mkdir()
raises("orchestra_db_error:open", open_db, folder)
blocker = TMP / "plain_file"
blocker.write_text("x", encoding="utf-8")
raises("orchestra_db_error:open", open_db, blocker / "o.db")
raises("orchestra_db_error:migration", open_db, TMP / "bad.db", 1, {1: ("THIS IS NOT SQL",)})
p2 = TMP / "two.db"
a = open_db(p2, busy_ms=200)
assert a.execute("PRAGMA busy_timeout").fetchone()[0] == 200
b = open_db(p2, busy_ms=200)
a.execute("BEGIN IMMEDIATE")
raises("orchestra_busy", lambda: immediate(b).__enter__())
a.execute("ROLLBACK")
with immediate(b):
    b.execute("INSERT INTO meta VALUES ('probe', 'x')")
assert a.execute("SELECT value FROM meta WHERE key = 'probe'").fetchone()[0] == "x"
'''

STAGES = [
    {"name": "tx",
     "task": """Create `store.py` (Python 3 standard library only: sqlite3, contextlib, pathlib) with two helpers for a sqlite3 connection that was opened with isolation_level=None.
- `schema_version(conn) -> int`: the int of the value in table `meta` (columns key, value) under key "schema_version"; 0 when the table does not exist or has no such row.
- `immediate(conn)`: a context manager (contextlib.contextmanager) that runs "BEGIN IMMEDIATE", yields conn, runs "COMMIT" when the block ends normally and "ROLLBACK" when the block raises (any exception, which is then raised again unchanged).
  When "BEGIN IMMEDIATE" itself fails with sqlite3.OperationalError because the database is locked or busy (the message contains "locked" or "busy") raise ValueError("orchestra_busy") instead; other errors stay as they are.""",
     "hidden": {"hidden_ostore_1.py": hidden("schema_version, immediate", C1)}},
    {"name": "schema",
     "task": """Add the schema and `migrate` to `store.py` (keep everything else). `SCHEMA_VERSION = 1`; `TABLES = ("meta", "agents", "tasks", "blockers", "comments", "wakeups", "routines", "routine_runs", "spend")`; `MIGRATIONS = {1: (...CREATE statements, each one string...)}`.
Schema 1, columns in exactly this order (NN = NOT NULL):
- meta: key TEXT PRIMARY KEY, value TEXT NN.
- agents: id TEXT PRIMARY KEY, instance_id TEXT NN UNIQUE, template_id TEXT NN, name TEXT NN, role TEXT NN, recipe_id TEXT, reports_to TEXT REFERENCES agents(id), status TEXT NN CHECK in ('aktiv','pausiert','beendet'), permission_level INTEGER NN CHECK 0..6, budget_tokens INTEGER, budget_eur_cent INTEGER, budget_period TEXT NN DEFAULT 'gesamt' CHECK in ('gesamt','monat'), created_at TEXT NN, updated_at TEXT NN, revision INTEGER NN DEFAULT 1. Indexes on (reports_to) and (status).
- tasks: id TEXT PRIMARY KEY, title TEXT NN, description TEXT, goal_ref TEXT, project_id TEXT, parent_id TEXT REFERENCES tasks(id), assignee TEXT REFERENCES agents(id), state TEXT NN CHECK in ('offen','zugewiesen','in_arbeit','wartet','erledigt','abgebrochen'), priority INTEGER NN DEFAULT 0, checkout_by TEXT, checkout_at TEXT, checkout_run TEXT, mission_id TEXT, created_by TEXT NN, created_at TEXT NN, updated_at TEXT NN, revision INTEGER NN DEFAULT 1. Indexes on (assignee, state), (parent_id), (mission_id) and a partial index on (checkout_by) WHERE checkout_by IS NOT NULL.
- blockers: task_id TEXT NN REFERENCES tasks(id), blocked_by_task_id TEXT NN REFERENCES tasks(id), created_at TEXT NN; PRIMARY KEY (task_id, blocked_by_task_id); CHECK task_id <> blocked_by_task_id. Index on (blocked_by_task_id).
- comments: id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NN REFERENCES tasks(id), author_kind TEXT NN CHECK in ('captain','agent','system'), author_id TEXT, text TEXT NN, ts TEXT NN. Index on (task_id, ts).
- wakeups: id INTEGER PRIMARY KEY, agent_id TEXT NN REFERENCES agents(id), task_id TEXT, reason TEXT NN CHECK in ('zugewiesen','antwort','routine','captain','wiederholung'), due_at TEXT NN, created_at TEXT NN, coalesced_into INTEGER REFERENCES wakeups(id), job_id TEXT, done_at TEXT. Partial index on (agent_id, due_at) WHERE done_at IS NULL AND coalesced_into IS NULL.
- routines: id TEXT PRIMARY KEY, agent_id TEXT NN REFERENCES agents(id), title TEXT NN, cron TEXT NN, timezone TEXT NN DEFAULT 'Europe/Berlin', catch_up TEXT NN CHECK in ('nachholen','auslassen'), enabled INTEGER NN DEFAULT 1, task_template TEXT NN, last_run TEXT, next_run TEXT. Partial index on (next_run) WHERE enabled = 1.
- routine_runs: routine_id TEXT NN, due_at TEXT NN, task_id TEXT, outcome TEXT NN CHECK in ('erzeugt','ausgelassen','nachgeholt'); PRIMARY KEY (routine_id, due_at).
- spend: id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NN, task_id TEXT, mission_id TEXT, provider TEXT NN CHECK in ('lokal','cloud'), provider_id TEXT, model TEXT, tokens_in INTEGER NN DEFAULT 0, tokens_out INTEGER NN DEFAULT 0, requests INTEGER NN DEFAULT 1, eur_cent INTEGER NN DEFAULT 0, ts TEXT NN. Indexes on (agent_id, ts), (provider_id, ts), (task_id).
No other indexes. `migrate(conn, target=SCHEMA_VERSION, migrations=None) -> int` (migrations None means MIGRATIONS): current = schema_version(conn); current > target -> ValueError("orchestra_db_error:schema_newer"); then for every version from current+1 to target: missing in migrations -> ValueError("orchestra_db_error:no_migration_<version>"); else, inside ONE `immediate(conn)` block per version, run its statements and store the version as text under key "schema_version" in meta (insert or replace). A failing statement rolls this version back and its sqlite3 error is raised unchanged. Return schema_version(conn).""",
     "hidden": {"hidden_ostore_1.py": hidden("schema_version, immediate", C1), "hidden_ostore_2.py": hidden("SCHEMA_VERSION, TABLES, MIGRATIONS, schema_version, migrate", C2)}},
    {"name": "open",
     "task": """Add `open_db(path, target=SCHEMA_VERSION, migrations=None, busy_ms=30000)` to `store.py` (keep everything else): opens the orchestration database and brings it to the code's schema.
- path is a str or Path, or ":memory:" (then no folder and no file is made and no WAL is set). Otherwise create the parent folders first.
- sqlite3.connect(str(path), isolation_level=None, timeout=busy_ms / 1000, check_same_thread=False); row_factory = sqlite3.Row; then "PRAGMA busy_timeout = <busy_ms>", "PRAGMA foreign_keys = ON" and (not for ":memory:") "PRAGMA journal_mode = WAL".
- Any sqlite3.Error or OSError while creating the folders, connecting or setting the pragmas -> ValueError("orchestra_db_error:open").
- Then migrate(conn, target, migrations). Its ValueError is raised unchanged (after closing the connection); a sqlite3.Error during the migration closes the connection and raises ValueError("orchestra_db_error:migration").
- Return the open connection.""",
     "hidden": {"hidden_ostore_1.py": hidden("schema_version, immediate", C1), "hidden_ostore_2.py": hidden("SCHEMA_VERSION, TABLES, MIGRATIONS, schema_version, migrate", C2),
                "hidden_ostore_3.py": hidden("open_db, immediate, schema_version", C3)}},
]
