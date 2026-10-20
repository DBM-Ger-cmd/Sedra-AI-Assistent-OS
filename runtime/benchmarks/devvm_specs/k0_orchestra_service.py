"""Spec 0, K0.18 (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, design D3.1, D3.2 and D3.5, KERN-06, gates G2-S0-08 and G2-S0-11): `orchestra/service.py`, the facade
`Orchestra` for desk and runtime. `build` is the decision table of D3.5: switch off -> no orchestra and no error; config missing or invalid -> the text of the config error;
database not openable or newer than the code -> the text of the database error; everything valid -> an `Orchestra`. Every error is written once as audit `ORCHESTRA_OFF`.
`boot_entry` is the entry `boot()["orchestra"]`. The read methods give the rows that the desk adapter `desk/orchestra_kinds.py` turns into objects (K0.21). Config loader,
database opener, audit, guard, job supervisor and template reader are PASSED IN (D3.1: no import of desk, agent_manager or devvm), so the tests use fakes and their own
sqlite tables. The domain logic (org, board, heartbeat, budget, routines) comes in Spec 1. GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the
reference (benchmarks/devvm_refs/k0_orchestra_service). Wiring into runtime.py is harness work (K0.20)."""

NOTES = '''# Notes for k0_orchestra_service
Python 3 standard library only, and in fact nothing needs to be imported: the config loader, the database opener and the audit are functions passed in, the connection is a sqlite3 connection passed in.
Never import config.py, store.py or anything else of the package. Read rows with `cursor.description` so that the code works with and without a row_factory.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code (ONE helper turns a query into a list of dicts).
'''

HEAD = r'''
import sqlite3
from pathlib import Path
from service import IMPORTS


class Cfg:
    def __init__(self, database="orc/o.db"):
        self.database = database

    def database_path(self, runtime_data):
        return Path(runtime_data) / self.database


def db(version="1", factory=None):
    conn = sqlite3.connect(":memory:", isolation_level=None)
    if factory:
        conn.row_factory = factory
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    if version is not None:
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (version,))
    return conn


log, events = [], []
audit = lambda event, payload: events.append((event, payload))
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert PARTS == ("guard", "supervisor", "templates")
conn = db()
cfg = Cfg()
o = Orchestra(cfg, conn)
assert o.config is cfg
assert o.conn is conn
assert o.audit is None
assert o.guard is None
assert o.supervisor is None
assert o.templates is None
assert o.schema_version() == 1
g, s, t = object(), object(), (lambda ref: {})
o2 = Orchestra(cfg, db("7"), audit=audit, guard=g, supervisor=s, templates=t)
assert o2.guard is g
assert o2.supervisor is s
assert o2.templates is t
assert o2.audit is audit
assert o2.schema_version() == 7
assert Orchestra(cfg, db(None)).schema_version() == 0
assert Orchestra(cfg, db("2", sqlite3.Row)).schema_version() == 2


def loader(result):
    def load(path):
        log.append(("load", path))
        if isinstance(result, Exception):
            raise result
        return result
    return load


def opener(result):
    def open_db(path):
        log.append(("open", path))
        if isinstance(result, Exception):
            raise result
        return result
    return open_db


assert build(False, loader(cfg), opener(conn), "c.yaml", "rd", audit=audit) == (None, None)
assert build(None, loader(cfg), opener(conn), "c.yaml", "rd", audit=audit) == (None, None)
assert build("yes", loader(cfg), opener(conn), "c.yaml", "rd", audit=audit) == (None, None)
assert log == []
assert events == []
cases = [
    (loader(ValueError("orchestra_config_missing")), opener(conn), "orchestra_config_missing"),
    (loader(ValueError("orchestra_config_invalid:heartbeat.tick_s")), opener(conn), "orchestra_config_invalid:heartbeat.tick_s"),
    (loader(ValueError("something else")), opener(conn), "orchestra_config_invalid:unreadable"),
    (loader(OSError("disk")), opener(conn), "orchestra_config_invalid:unreadable"),
    (loader(cfg), opener(ValueError("orchestra_db_error:schema_newer")), "orchestra_db_error:schema_newer"),
    (loader(cfg), opener(ValueError("orchestra_busy")), "orchestra_busy"),
    (loader(cfg), opener(ValueError("kaputt")), "orchestra_db_error:open"),
    (loader(cfg), opener(sqlite3.OperationalError("unable to open")), "orchestra_db_error:open"),
    (loader(cfg), opener(PermissionError("nope")), "orchestra_db_error:open"),
]
for load, open_db, reason in cases:
    events.clear()
    assert build(True, load, open_db, "c.yaml", "rd", audit=audit) == (None, reason)
    assert events == [("ORCHESTRA_OFF", {"reason": reason})]
assert build(True, loader(ValueError("orchestra_config_missing")), opener(conn), "c.yaml", "rd") == (None, "orchestra_config_missing")
log.clear()
events.clear()
built, error = build(True, loader(cfg), opener(conn), "cfg/orchestra.yaml", "rd", audit=audit, guard=g, templates=t)
assert error is None
assert isinstance(built, Orchestra)
assert built.config is cfg
assert built.conn is conn
assert built.audit is audit
assert built.guard is g
assert built.templates is t
assert built.supervisor is None
assert log == [("load", "cfg/orchestra.yaml"), ("open", Path("rd") / "orc/o.db")]
assert events == []
log.clear()
built2, _ = build(True, loader(cfg), opener(conn), "c.yaml", "rd")
assert built2.audit is None
log.clear()
try:
    build(False, loader(cfg), opener(conn), "c.yaml", "rd", gaurd=g)
except TypeError:
    pass
else:
    raise AssertionError("unknown part accepted")
assert log == []
assert boot_entry(None, None) == {"enabled": False, "error": None, "schema_version": None}
assert boot_entry(None, "orchestra_config_missing") == {"enabled": False, "error": "orchestra_config_missing", "schema_version": None}
assert boot_entry(built, None) == {"enabled": True, "error": None, "schema_version": 1}
assert boot_entry(o2, None)["schema_version"] == 7
o.close()
try:
    conn.execute("SELECT 1")
except sqlite3.ProgrammingError:
    pass
else:
    raise AssertionError("not closed")
'''

C2 = r'''
DDL = (
    "CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, reports_to TEXT, status TEXT NOT NULL, budget_tokens INTEGER, budget_eur_cent INTEGER)",
    "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, assignee TEXT, state TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)",
    "CREATE TABLE routines (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, title TEXT NOT NULL, cron TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1)",
    "CREATE TABLE spend (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL, tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 1, eur_cent INTEGER NOT NULL DEFAULT 0)",
)
for factory in (None, sqlite3.Row):
    conn = db("1", factory)
    for statement in DDL:
        conn.execute(statement)
    conn.executemany("INSERT INTO agents VALUES (?,?,?,?,?,?,?)", [
        ("planer", "Planer", "planer", "ua", "aktiv", None, None),
        ("ua", "Unterarbeiter", "unterarbeiter", None, "aktiv", 100000, 0),
        ("coder", "Coder", "coder", "ua", "pausiert", 5000, None),
    ])
    conn.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?)", [
        ("t3", "Drei", "coder", "offen", 0, "2026-10-20T09:00:00Z"),
        ("t1", "Eins", "coder", "zugewiesen", 5, "2026-10-20T11:00:00Z"),
        ("t2", "Zwei", None, "offen", 5, "2026-10-20T10:00:00Z"),
        ("t0", "Null", "planer", "offen", 0, "2026-10-20T09:00:00Z"),
    ])
    conn.executemany("INSERT INTO routines VALUES (?,?,?,?,?)", [("r2", "ua", "Woche", "0 6 * * 1", 0), ("r1", "planer", "Tag", "0 6 * * *", 1)])
    conn.executemany("INSERT INTO spend (agent_id, tokens_in, tokens_out, requests, eur_cent) VALUES (?,?,?,?,?)",
                     [("coder", 100, 50, 1, 0), ("coder", 10, 5, 2, 3), ("ua", 1, 1, 1, 0)])
    o = Orchestra(object(), conn)
    agents = o.agents()
    assert [a["id"] for a in agents] == ["coder", "planer", "ua"]
    assert agents[0] == {"id": "coder", "name": "Coder", "role": "coder", "reports_to": "ua", "status": "pausiert", "budget_tokens": 5000, "budget_eur_cent": None}
    assert type(agents[0]) is dict
    assert o.agent("ua")["name"] == "Unterarbeiter"
    assert type(o.agent("ua")) is dict
    assert o.agent("nope") is None
    assert [t["id"] for t in o.issues()] == ["t2", "t1", "t0", "t3"]
    assert [t["id"] for t in o.issues(state="offen")] == ["t2", "t0", "t3"]
    assert [t["id"] for t in o.issues(assignee="coder")] == ["t1", "t3"]
    assert [t["id"] for t in o.issues(state="offen", assignee="coder")] == ["t3"]
    assert o.issues(state="erledigt") == []
    assert o.issues(assignee="x' OR '1'='1") == []
    assert o.issue("t1") == {"id": "t1", "title": "Eins", "assignee": "coder", "state": "zugewiesen", "priority": 5, "created_at": "2026-10-20T11:00:00Z"}
    assert o.issue("t9") is None
    assert [r["id"] for r in o.routines()] == ["r1", "r2"]
    assert o.routine("r2")["enabled"] == 0
    assert o.routine("r9") is None
    assert o.spent("coder") == {"tokens": 165, "eur_cent": 3, "requests": 3}
    assert o.spent("ua") == {"tokens": 2, "eur_cent": 0, "requests": 1}
    assert o.spent("planer") == {"tokens": 0, "eur_cent": 0, "requests": 0}
    assert conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == 4
'''

STAGES = [
    {"name": "build",
     "task": """Create `service.py` (Python 3, nothing to import) with `class Orchestra`, `build` and `boot_entry`. Module constant `PARTS = ("guard", "supervisor", "templates")`.
- `Orchestra(config, conn, audit=None, guard=None, supervisor=None, templates=None)`: keeps every argument as an attribute of the same name. `schema_version()`: the int of meta.value for key "schema_version" read through conn (0 when there is no such row). `close()`: closes conn.
- `build(switch_on, load_config, open_db, config_path, runtime_data, audit=None, **parts) -> (orchestra or None, error text or None)`:
  1. a key of parts that is not in PARTS -> TypeError (before anything else, nothing is called).
  2. switch_on is not exactly True -> (None, None); nothing is loaded, opened or written.
  3. config = load_config(config_path). Any exception: when it is a ValueError whose text starts with "orchestra_config_" the error is that text, otherwise "orchestra_config_invalid:unreadable".
  4. conn = open_db(config.database_path(runtime_data)). Any exception: when it is a ValueError whose text starts with "orchestra_" the error is that text, otherwise "orchestra_db_error:open". ONE helper decides the error text for 3 and 4.
  5. With an error: when audit is not None call audit("ORCHESTRA_OFF", {"reason": error}) once; return (None, error).
  6. Otherwise return (Orchestra(config, conn, audit=audit, **parts), None).
- `boot_entry(orchestra, error)`: {"enabled": orchestra is not None, "error": error, "schema_version": orchestra.schema_version() or None when orchestra is None}.""",
     "hidden": {"hidden_osvc_1.py": hidden("PARTS, Orchestra, build, boot_entry", C1)}},
    {"name": "read",
     "task": """Add read methods to `Orchestra` in `service.py` (keep everything else). Every row is a plain dict {column name: value} with ALL columns of its table (use cursor.description, so it works with and without conn.row_factory); always use `?` parameters, never put a value into the SQL text.
- `agents()`: all rows of table agents ordered by id. `agent(agent_id)`: that row or None.
- `issues(state=None, assignee=None)`: rows of table tasks; a given state and/or assignee filters with equality (None means no filter); order: priority descending, then created_at, then id. `issue(task_id)`: that row or None.
- `routines()`: all rows of table routines ordered by id. `routine(routine_id)`: that row or None.
- `spent(agent_id)`: from table spend for this agent {"tokens": sum of tokens_in + tokens_out, "eur_cent": sum of eur_cent, "requests": sum of requests}, all 0 when there is no row.
Nothing is ever written.""",
     "hidden": {"hidden_osvc_1.py": hidden("PARTS, Orchestra, build, boot_entry", C1), "hidden_osvc_2.py": hidden("Orchestra", C2)}},
]
