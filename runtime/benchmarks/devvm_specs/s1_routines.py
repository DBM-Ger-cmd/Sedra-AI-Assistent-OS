"""Spec 1, Bau-Spec s1_routines (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `routines.py`, D1.3.1 type routine, ORC-10; gates G2-S1-05, G2-S1-22):
`orchestra/routines.py`, the routines in orchestra.db: create and change them (an invalid cron is refused with cron_invalid:<field> already then), switch them on and off
(switching on counts dates only from now, missed ones do not count), and `fire_due` for the tick: every date of a routine since its last run is claimed once in
routine_runs (the primary key (routine_id, due_at) keeps a double tick from creating a second task); 'auslassen' creates only the newest date, 'nachholen' also up to
max_catch_up older ones; a paused or terminated agent or a still open task of the previous date skips them all. The task itself is made by the caller's make_task
(board.create plus the wake-up), called OUTSIDE the transaction. Builds on the seed benchmarks/s1_schema2_seed (store.py schema 2, cron.py = reference of s1_cron).
OP-S1-03: without tzdata only "UTC" works as a zone name on Windows; the tests use "UTC" and never the schema default 'Europe/Berlin'.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_routines)."""

SEED = "benchmarks/s1_schema2_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s1_routines
Python 3 standard library only (uuid) plus `import cron` and `from store import immediate` (both files are in the workspace: do not change them). No clock (now is an argument), no other files, no network.
The connection is opened by the caller with store.open_db (rows are sqlite3.Row, isolation_level None, foreign keys on); return plain dicts with all columns. Writes run inside `with immediate(conn):`,
but make_task is called while NO transaction is open (it opens its own). Every refusal is a ValueError with exactly the code the task names; cron.py's errors pass through unchanged.
No comments and no docstrings, small private helpers instead of copied code (one reads a routine or raises routine_not_found, one computes the next run).
'''

HEAD = r'''
import store
from routines import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def agent(conn, id, boss=None, status="aktiv"):
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at) "
                 "VALUES (?, ?, 't', ?, 'coder', ?, ?, 2, '2026-10-21T07:00:00Z', '2026-10-21T07:00:00Z')", (id, "inst-" + id, "Name " + id, boss, status))


def maker(conn, log):
    def make(routine, due_at):
        tid = "T-%s-%s" % (routine["id"], due_at[11:13])
        with store.immediate(conn):
            conn.execute("INSERT INTO tasks (id, title, assignee, state, origin, created_by, created_at, updated_at) VALUES (?, ?, ?, 'zugewiesen', 'routine', ?, ?, ?)",
                         (tid, routine["title"], routine["agent_id"], "routine:" + routine["id"], due_at, due_at))
        log.append((routine["id"], due_at))
        return tid
    return make


def r(id, agent="B", expr="0 * * * *", catch_up="auslassen", **kw):
    out = {"id": id, "agent_id": agent, "title": "Routine " + id, "cron": expr, "timezone": "UTC", "catch_up": catch_up}
    out.update(kw)
    return out


def get(conn, id):
    return dict(conn.execute("SELECT * FROM routines WHERE id = ?", (id,)).fetchone())


def runs(conn, rid):
    return [tuple(x) for x in conn.execute("SELECT due_at, outcome, task_id FROM routine_runs WHERE routine_id = ? ORDER BY due_at", (rid,))]


def close(conn):
    conn.execute("UPDATE tasks SET state = 'erledigt'")


def db():
    conn = store.open_db(":memory:")
    agent(conn, "A")
    agent(conn, "B", "A")
    agent(conn, "P", "A", "pausiert")
    agent(conn, "X", "A", "beendet")
    return conn


def at(hhmm):
    return "2026-10-21T%s:00Z" % hhmm


def out(rid, hh, outcome, task=True):
    return {"routine_id": rid, "due_at": at(hh + ":00"), "outcome": outcome, "task_id": ("T-%s-%s" % (rid, hh)) if task else None}
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = db()
x = create(c, r("R1", task_template="{}"), at("08:10"))
assert (x["id"], x["agent_id"], x["title"], x["cron"], x["timezone"], x["catch_up"], x["task_template"]) == ("R1", "B", "Routine R1", "0 * * * *", "UTC", "auslassen", "{}")
assert (x["enabled"], x["last_run"], x["next_run"]) == (1, at("08:10"), at("09:00"))
y = create(c, {"agent_id": "B", "title": "Ohne ID", "cron": "*/15 * * * *", "timezone": "UTC", "catch_up": "nachholen"}, at("08:10"))
assert y["id"].startswith("R-") and len(y["id"]) == 14
assert y["next_run"] == at("08:15")
for expr, code in (("61 * * * *", "cron_invalid:minute"), ("* * *", "cron_invalid:fields"), ("0 25 * * *", "cron_invalid:hour")):
    raises(code, create, c, r("R9", expr=expr), at("08:10"))
raises("cron_timezone_unknown", create, c, r("R9", timezone="Mars/Base"), at("08:10"))
raises("routine_catch_up_invalid", create, c, r("R9", catch_up="immer"), at("08:10"))
raises("routine_title_invalid", create, c, r("R9", title=" "), at("08:10"))
raises("routine_field_unknown:enabled", create, c, r("R9", enabled=0), at("08:10"))
raises("routine_field_missing:cron", create, c, {"agent_id": "B", "title": "x", "catch_up": "auslassen", "timezone": "UTC"}, at("08:10"))
raises("agent_not_found", create, c, r("R9", agent="Z"), at("08:10"))
raises("routine_exists", create, c, r("R1"), at("08:10"))
assert c.execute("SELECT count(*) FROM routines").fetchone()[0] == 2
assert not c.in_transaction
'''

C2 = r'''
c = db()
create(c, r("R1"), at("08:10"))
u = update(c, "R1", {"title": "Neu", "task_template": "t"}, at("08:20"))
assert (u["title"], u["task_template"], u["last_run"], u["next_run"]) == ("Neu", "t", at("08:10"), at("09:00"))
u = update(c, "R1", {"cron": "30 * * * *"}, at("08:20"))
assert (u["cron"], u["last_run"], u["next_run"]) == ("30 * * * *", at("08:20"), at("08:30"))
assert update(c, "R1", {"agent_id": "A", "catch_up": "nachholen"}, at("08:25"))["catch_up"] == "nachholen"
raises("routine_field_unknown:id", update, c, "R1", {"id": "R2"}, at("08:25"))
raises("routine_not_found", update, c, "R9", {"title": "x"}, at("08:25"))
raises("cron_invalid:hour", update, c, "R1", {"cron": "0 24 * * *"}, at("08:25"))
raises("agent_not_found", update, c, "R1", {"agent_id": "Z"}, at("08:25"))
raises("routine_catch_up_invalid", update, c, "R1", {"catch_up": "x"}, at("08:25"))
off = set_enabled(c, "R1", False, at("09:00"))
assert (off["enabled"], off["next_run"], off["last_run"]) == (0, None, at("08:20"))
assert set_enabled(c, "R1", False, at("09:30")) == off
assert update(c, "R1", {"cron": "45 * * * *"}, at("09:40"))["next_run"] is None
on = set_enabled(c, "R1", True, at("10:05"))
assert (on["enabled"], on["last_run"], on["next_run"]) == (1, at("10:05"), at("10:45"))
assert set_enabled(c, "R1", True, at("11:00")) == on
raises("routine_not_found", set_enabled, c, "R9", True, at("11:00"))
assert get(c, "R1") == on
assert not c.in_transaction
'''

C3 = r'''
c = db()
log = []
mk = maker(c, log)
create(c, r("R1"), at("08:10"))
assert fire_due(c, at("08:59"), 3, mk) == []
assert fire_due(c, at("09:00"), 3, mk) == [out("R1", "09", "erzeugt")]
assert runs(c, "R1") == [(at("09:00"), "erzeugt", "T-R1-09")]
assert (get(c, "R1")["last_run"], get(c, "R1")["next_run"]) == (at("09:00"), at("10:00"))
assert fire_due(c, at("09:00"), 3, mk) == []
assert log == [("R1", at("09:00"))]
close(c)
assert fire_due(c, at("12:30"), 3, mk) == [out("R1", "10", "ausgelassen", False), out("R1", "11", "ausgelassen", False), out("R1", "12", "erzeugt")]
assert runs(c, "R1")[1:] == [(at("10:00"), "ausgelassen", None), (at("11:00"), "ausgelassen", None), (at("12:00"), "erzeugt", "T-R1-12")]
assert len(log) == 2
assert c.execute("SELECT origin, assignee FROM tasks WHERE id = 'T-R1-12'").fetchone()[1] == "B"
create(c, r("R0"), at("12:30"))
create(c, r("R2"), at("12:30"))
set_enabled(c, "R2", False, at("12:30"))
close(c)
assert [(o["routine_id"], o["due_at"]) for o in fire_due(c, at("13:00"), 3, mk)] == [("R0", at("13:00")), ("R1", at("13:00"))]
assert runs(c, "R2") == []
assert not c.in_transaction
'''

C4 = r'''
c = db()
log = []
mk = maker(c, log)
create(c, r("R1", catch_up="nachholen"), at("08:10"))
got = fire_due(c, at("13:30"), 2, mk)
assert got == [out("R1", "09", "ausgelassen", False), out("R1", "10", "ausgelassen", False), out("R1", "11", "nachgeholt"), out("R1", "12", "nachgeholt"), out("R1", "13", "erzeugt")]
assert [x[0] for x in log] == ["R1", "R1", "R1"]
assert [due for _, due in log] == [at("11:00"), at("12:00"), at("13:00")]
assert runs(c, "R1")[2] == (at("11:00"), "nachgeholt", "T-R1-11")
close(c)
assert [o["outcome"] for o in fire_due(c, at("16:00"), 0, mk)] == ["ausgelassen", "ausgelassen", "erzeugt"]
close(c)
assert [o["outcome"] for o in fire_due(c, at("19:00"), 10, mk)] == ["nachgeholt", "nachgeholt", "erzeugt"]
assert len(log) == 7
assert get(c, "R1")["last_run"] == at("19:00")
'''

C5 = r'''
c = db()
log = []
mk = maker(c, log)
create(c, r("RP", agent="P"), at("08:10"))
create(c, r("RX", agent="X"), at("08:10"))
assert [o["outcome"] for o in fire_due(c, at("10:00"), 3, mk)] == ["ausgelassen"] * 4
assert (log, get(c, "RP")["last_run"]) == ([], at("10:00"))
create(c, r("R1", catch_up="nachholen"), at("08:10"))
assert [o for o in fire_due(c, at("09:00"), 3, mk) if o["routine_id"] == "R1"] == [out("R1", "09", "erzeugt")]
assert [o for o in fire_due(c, at("11:00"), 3, mk) if o["routine_id"] == "R1"] == [out("R1", "10", "ausgelassen", False), out("R1", "11", "ausgelassen", False)]
assert len(log) == 1
c.execute("UPDATE tasks SET state = 'abgebrochen'")
assert [o for o in fire_due(c, at("12:00"), 3, mk) if o["routine_id"] == "R1"] == [out("R1", "12", "erzeugt")]
c.execute("UPDATE routines SET last_run = ? WHERE id = 'R1'", (at("08:10"),))
close(c)
again = fire_due(c, at("13:00"), 3, mk)
assert [o for o in again if o["routine_id"] == "R1"] == [out("R1", "13", "erzeugt")]
assert c.execute("SELECT count(*) FROM tasks").fetchone()[0] == 3
assert len(runs(c, "R1")) == 5
assert not c.in_transaction
'''

H1 = {"hidden_routines_1.py": hidden("create", C1)}
H2 = {**H1, "hidden_routines_2.py": hidden("create, update, set_enabled", C2)}
H3 = {**H2, "hidden_routines_3.py": hidden("create, set_enabled, fire_due", C3)}
H4 = {**H3, "hidden_routines_4.py": hidden("create, fire_due", C4)}
H5 = {**H4, "hidden_routines_5.py": hidden("create, fire_due", C5)}

TABLES = """Tables (store.py, schema 2): routines (id, agent_id, title, cron, timezone (default 'Europe/Berlin'), catch_up ('nachholen','auslassen'), enabled (default 1), task_template, last_run, next_run); routine_runs (routine_id, due_at, task_id, outcome ('erzeugt','ausgelassen','nachgeholt'); PRIMARY KEY (routine_id, due_at)); tasks (id, state, ...); agents (id, status, ...)."""
CRON = """cron.py (given): parse(expr) -> cron dict or ValueError('cron_invalid:<field>'); next_after(cron, after_utc, tz) -> UTC text (strictly after) or None, ValueError('cron_timezone_unknown'); due_between(cron, from_utc, to_utc, tz, limit) -> the dates in (from, to], at most limit + 1."""

STAGES = [
    {"name": "crud",
     "task": f"""Create `routines.py` (Python 3, uuid; `import cron`, `from store import immediate`; both are in the workspace) with `create(conn, fields, now)` -> the new routine as a dict (all columns).
{TABLES}
{CRON}
Checks in this order (each a ValueError, a refused call writes nothing): a key not in id, agent_id, title, cron, timezone, catch_up, task_template -> 'routine_field_unknown:<first alphabetically>'; title present but not a non-empty string after strip -> 'routine_title_invalid'; catch_up present but not 'nachholen'/'auslassen' -> 'routine_catch_up_invalid'; agent_id, title, cron or catch_up missing or None -> 'routine_field_missing:<first missing in this order>'; then next_run = cron.next_after(cron.parse(cron text), now, timezone) with timezone default 'Europe/Berlin' (its errors pass through: cron_invalid:<field>, cron_timezone_unknown).
Inside `with immediate(conn):` unknown agent -> 'agent_not_found'; id missing -> 'R-' + 12 hex characters of uuid4; id exists -> 'routine_exists'; insert with enabled 1, last_run = now (dates count only from now on), next_run.""",
     "hidden": H1},
    {"name": "change",
     "task": """Add to `routines.py` (keep everything else), each inside `with immediate(conn):`, returning the routine as a dict:
- `update(conn, rid, fields, now)`: allowed keys agent_id, title, cron, timezone, catch_up, task_template (the same field checks as create, 'routine_field_unknown:<key>' for others, also for id); unknown routine -> 'routine_not_found'; agent_id given but unknown -> 'agent_not_found'. When cron or timezone is in fields, the new pair is checked with cron (errors pass through) and, only if the routine is enabled, last_run = now and next_run = the next date after now. Store the given fields.
- `set_enabled(conn, rid, on, now)`: unknown -> 'routine_not_found'; already in that state -> return it unchanged; switching on: enabled 1, last_run = now (missed dates do not count), next_run = the next date after now; switching off: enabled 0, next_run NULL (last_run stays).""",
     "hidden": H2},
    {"name": "fire",
     "task": """Add `fire_due(conn, now, max_catch_up, make_task)` -> list of {"routine_id", "due_at", "outcome", "task_id"} to `routines.py` (keep everything else). For every ENABLED routine, ordered by id:
1. In ONE `with immediate(conn):` take dates = cron.due_between(parsed cron, last_run, now, timezone, 1000); no dates -> nothing for this routine. Give each date an outcome (this stage: catch_up 'auslassen': the newest date 'erzeugt', all older ones 'ausgelassen'). Claim each date with `INSERT OR IGNORE INTO routine_runs (routine_id, due_at, outcome)`; a date already in routine_runs is dropped completely (no result, no task). Set last_run = now and next_run = the next date after now.
2. AFTER that transaction (make_task opens its own): for every claimed date whose outcome is not 'ausgelassen' call task_id = make_task(routine dict, due_at) and store task_id in its routine_runs row; ausgelassen dates keep task_id None.
Results in routine order, dates ascending. A second call with the same now finds no dates (a double tick creates nothing).""",
     "hidden": H3},
    {"name": "catchup",
     "task": """Extend `fire_due` in `routines.py` (keep everything else): catch_up 'nachholen': the newest date is 'erzeugt', the newest max_catch_up of the OLDER dates are 'nachgeholt' (each gets its own task from make_task, in date order), all remaining older dates 'ausgelassen'. max_catch_up 0 behaves like 'auslassen'.""",
     "hidden": H4},
    {"name": "active",
     "task": """Extend `fire_due` in `routines.py` (keep everything else): ALL dates of a routine are 'ausgelassen' (no task, but still claimed, last_run moves on) when its agent is not 'aktiv' (paused or terminated), or when the task of its previous date is still open: take the routine's routine_runs row with the latest due_at that has a task_id; if that task's state is not 'erledigt' or 'abgebrochen', the previous run is still open. The primary key of routine_runs still drops dates that were claimed before, even when last_run was moved back.""",
     "hidden": H5},
]
