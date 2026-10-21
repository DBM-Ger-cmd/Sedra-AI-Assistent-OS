"""Spec 1, Bau-Spec s1_board (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `board.py`, D3.3 checkout, D1.5, ORC-03, ORC-04, ORC-05, ORC-11, ORC-13, ORC-17, ORC-18;
gates G2-S1-01, G2-S1-16, G2-S1-22): `orchestra/board.py`, the task board in orchestra.db: create, assign (a second assignment replaces the first), the atomic checkout
(BEGIN IMMEDIATE and `checkout_by IS NULL`, never a blocked task), release only by the own run, blockers without cycles, comments, cancel, the check result for the report,
the rows for the goal chain, the test whether all children of a root are done, the orphaned checkouts after a restart, and the delegation of a foreman's decomposition
(all subtasks in one transaction, levels inherited downwards). Builds on the seed benchmarks/s1_schema2_seed (store.py schema 2, graphs.py = reference of s1_graphs).
Additions to D1.1: clear_blocker returns the number of open blockers left (for the wake-up "unblocked"); create checks its fields.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_board)."""

SEED = "benchmarks/s1_schema2_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s1_board
Python 3 standard library only (uuid) plus `import graphs` and `from store import immediate` (both files are in the workspace: do not change them). No clock (now is an argument), no other files, no network.
The connection is opened by the caller with store.open_db (rows are sqlite3.Row, isolation_level None, foreign keys on); return plain dicts with all columns. Every write runs inside ONE `with immediate(conn):`.
Every refusal is a ValueError with exactly the code the task names; a refused call changes nothing. Every change of a task sets updated_at = now and raises its revision by 1.
No comments and no docstrings, small private helpers instead of copied code (one reads a task or raises task_not_found, one updates a task, one counts open blockers).
'''

HEAD = r'''
import os, sqlite3, tempfile
import store
from board import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def agent(conn, id, boss, role, level, status="aktiv", can_delegate=0):
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, can_delegate, created_at, updated_at) "
                 "VALUES (?, ?, 't', ?, ?, ?, ?, ?, ?, '2026-10-21T07:00:00Z', '2026-10-21T07:00:00Z')", (id, "inst-" + id, "Name " + id, role, boss, status, level, can_delegate))


def task(conn, id, assignee=None, state=None, parent=None, run=None, max_level=None):
    conn.execute("INSERT INTO tasks (id, title, assignee, state, parent_id, checkout_by, checkout_run, max_level, created_by, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'captain', '2026-10-21T07:00:00Z', '2026-10-21T07:00:00Z')",
                 (id, "Titel " + id, assignee, state or ("in_arbeit" if run else "zugewiesen" if assignee else "offen"), parent, assignee if run else None, run, max_level))


def get(conn, id):
    return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone())


def count(conn, table="tasks"):
    return conn.execute("SELECT count(*) FROM %s" % table).fetchone()[0]


def setup(conn):
    agent(conn, "A", None, "foreman", 3, can_delegate=1)
    agent(conn, "B", "A", "coder", 2)
    agent(conn, "C", "A", "planner", 1)
    agent(conn, "P", "A", "coder", 2, "pausiert")
    agent(conn, "D", "B", "coder", 2)
    return conn


def db():
    return setup(store.open_db(":memory:"))


T0, T1, T2 = "2026-10-21T08:00:00Z", "2026-10-21T08:00:01Z", "2026-10-21T08:00:02Z"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = db()
t = create(c, {"title": "Erste Aufgabe", "description": "d", "priority": 2}, T0, "captain")
assert t["id"].startswith("T-") and len(t["id"]) == 14
assert (t["title"], t["description"], t["state"], t["assignee"], t["origin"], t["priority"], t["revision"]) == ("Erste Aufgabe", "d", "offen", None, "captain", 2, 1)
assert (t["created_by"], t["created_at"], t["updated_at"], t["max_level"], t["checkout_by"]) == ("captain", T0, T0, None, None)
u = create(c, {"id": "T1", "title": "Mit Bearbeiter", "assignee": "B", "origin": "routine", "max_level": 2, "parent_id": t["id"]}, T1, "routine:R1")
assert (u["id"], u["state"], u["assignee"], u["origin"], u["max_level"], u["parent_id"], u["created_by"]) == ("T1", "zugewiesen", "B", "routine", 2, t["id"], "routine:R1")
assert u == get(c, "T1")
assert create(c, {"title": "x"}, T0, "captain")["id"] != create(c, {"title": "x"}, T0, "captain")["id"]
assert create(c, {"title": "y" * 200}, T0, "captain")["priority"] == 0
n = count(c)
for title in ("", "   ", None, "x" * 201, 5):
    raises("task_title_invalid", create, c, {"title": title}, T0, "captain")
raises("task_field_unknown:state", create, c, {"title": "x", "state": "erledigt"}, T0, "captain")
raises("task_origin_invalid", create, c, {"title": "x", "origin": "modell"}, T0, "captain")
for level in (7, -1, "2", True):
    raises("level_not_allowed", create, c, {"title": "x", "max_level": level}, T0, "captain")
raises("task_field_invalid:priority", create, c, {"title": "x", "priority": "1"}, T0, "captain")
raises("task_not_found", create, c, {"title": "x", "parent_id": "nope"}, T0, "captain")
raises("agent_not_found", create, c, {"title": "x", "assignee": "Z"}, T0, "captain")
raises("agent_inactive", create, c, {"title": "x", "assignee": "P"}, T0, "captain")
raises("task_exists", create, c, {"id": "T1", "title": "x"}, T0, "captain")
assert count(c) == n
assert not c.in_transaction
'''

C2 = r'''
c = db()
task(c, "T1")
r = assign(c, "T1", "B", T1, "captain")
assert r["old"] is None
assert (r["task"]["assignee"], r["task"]["state"], r["task"]["revision"], r["task"]["updated_at"]) == ("B", "zugewiesen", 2, T1)
r2 = assign(c, "T1", "C", T2, "captain")
assert (r2["old"], r2["task"]["assignee"], r2["task"]["revision"]) == ("B", "C", 3)
assert r2["task"] == get(c, "T1")
task(c, "W", "B", "wartet")
assert assign(c, "W", "D", T1, "captain")["task"]["state"] == "zugewiesen"
raises("agent_not_found", assign, c, "T1", "Z", T2, "captain")
raises("agent_inactive", assign, c, "T1", "P", T2, "captain")
raises("task_not_found", assign, c, "nope", "B", T2, "captain")
for state in ("erledigt", "abgebrochen"):
    task(c, "X-" + state, "B", state)
    raises("task_closed", assign, c, "X-" + state, "C", T2, "captain")
task(c, "K", "B", run="run-1")
raises("task_checked_out", assign, c, "K", "C", T2, "captain")
assert (get(c, "T1")["assignee"], get(c, "T1")["revision"], get(c, "K")["assignee"]) == ("C", 3, "B")
assert not c.in_transaction
'''

C3 = r'''
c = db()
task(c, "T1", "B")
out = checkout(c, "T1", "B", "run-1", T1)
assert (out["state"], out["checkout_by"], out["checkout_run"], out["checkout_at"], out["revision"], out["updated_at"]) == ("in_arbeit", "B", "run-1", T1, 2, T1)
raises("task_already_checked_out", checkout, c, "T1", "B", "run-2", T2)
raises("task_already_checked_out", checkout, c, "T1", "C", "run-2", T2)
task(c, "T2", "B")
raises("task_not_assignable", checkout, c, "T2", "C", "run-2", T2)
task(c, "T3")
raises("task_not_assignable", checkout, c, "T3", "B", "run-3", T2)
task(c, "T4", "B", "wartet")
raises("task_not_assignable", checkout, c, "T4", "B", "run-4", T2)
task(c, "T5", "B")
task(c, "T6", "C")
c.execute("INSERT INTO blockers VALUES ('T5', 'T6', ?)", (T0,))
raises("task_blocked", checkout, c, "T5", "B", "run-5", T2)
assert get(c, "T5")["checkout_by"] is None
c.execute("UPDATE tasks SET state = 'erledigt' WHERE id = 'T6'")
assert checkout(c, "T5", "B", "run-5", T2)["checkout_run"] == "run-5"
raises("task_not_found", checkout, c, "nope", "B", "run-9", T2)
path = os.path.join(tempfile.mkdtemp(), "o.db")
c1 = setup(store.open_db(path))
c2 = store.open_db(path)
task(c1, "R", "B")
assert checkout(c1, "R", "B", "run-a", T1)["checkout_run"] == "run-a"
raises("task_already_checked_out", checkout, c2, "R", "B", "run-b", T1)
assert tuple(c2.execute("SELECT checkout_by, checkout_run FROM tasks WHERE id = 'R'").fetchone()) == ("B", "run-a")
assert not c1.in_transaction and not c2.in_transaction
'''

C4 = r'''
c = db()
for t in ("T1", "T2", "T3"):
    task(c, t)
assert set_blocker(c, "T1", "T2", T1) is None
assert tuple(c.execute("SELECT task_id, blocked_by_task_id, created_at FROM blockers").fetchone()) == ("T1", "T2", T1)
set_blocker(c, "T1", "T2", T2)
assert count(c, "blockers") == 1
raises("blocker_cycle", set_blocker, c, "T2", "T1", T2)
set_blocker(c, "T2", "T3", T2)
raises("blocker_cycle", set_blocker, c, "T3", "T1", T2)
raises("blocker_self", set_blocker, c, "T1", "T1", T2)
raises("task_not_found", set_blocker, c, "T1", "nope", T2)
raises("task_not_found", set_blocker, c, "nope", "T1", T2)
assert count(c, "blockers") == 2
set_blocker(c, "T1", "T3", T2)
assert clear_blocker(c, "T1", "T2", T2) == 1
c.execute("UPDATE tasks SET state = 'erledigt' WHERE id = 'T3'")
set_blocker(c, "T1", "T2", T2)
assert clear_blocker(c, "T1", "T2", T2) == 0
assert clear_blocker(c, "T1", "T3", T2) == 0
raises("blocker_not_found", clear_blocker, c, "T1", "T3", T2)
assert count(c, "blockers") == 1
assert not c.in_transaction
'''

C5 = r'''
c = db()
task(c, "T1", "B", run="run-1")
raises("run_mismatch", release, c, "T1", "run-2", "wartet", T1)
r = release(c, "T1", "run-1", "wartet", T1, comment="Ergebnis liegt vor")
assert (r["state"], r["checkout_by"], r["checkout_run"], r["checkout_at"], r["assignee"], r["revision"], r["updated_at"]) == ("wartet", None, None, None, "B", 2, T1)
assert tuple(c.execute("SELECT task_id, author_kind, author_id, text, ts FROM comments").fetchone()) == ("T1", "system", None, "Ergebnis liegt vor", T1)
raises("run_mismatch", release, c, "T1", "run-1", "zugewiesen", T2)
raises("run_mismatch", release, c, "T1", None, "zugewiesen", T2)
task(c, "T2", "B", run="run-2")
o = release(c, "T2", "run-2", "offen", T1)
assert (o["state"], o["assignee"], count(c, "comments")) == ("offen", None, 1)
task(c, "T5", "B", run="run-5")
assert release(c, "T5", "run-5", "erledigt", T1)["state"] == "erledigt"
for state in ("in_arbeit", "abgebrochen", "", None):
    raises("task_state_invalid", release, c, "T1", "run-1", state, T2)
task(c, "T6", "B", run="run-6")
raises("comment_empty", release, c, "T6", "run-6", "offen", T2, comment=" ")
assert get(c, "T6")["checkout_run"] == "run-6"
task(c, "T3", "B", run="run-3")
x = cancel(c, "T3", T2, "captain")
assert (x["run_id"], x["task"]["state"], x["task"]["checkout_by"], x["task"]["checkout_run"], x["task"]["revision"]) == ("run-3", "abgebrochen", None, None, 2)
raises("task_closed", cancel, c, "T3", T2, "captain")
task(c, "T4", "B")
assert cancel(c, "T4", T2, "captain")["run_id"] is None
raises("task_not_found", cancel, c, "nope", T2, "captain")
raises("task_not_found", release, c, "nope", "run-1", "offen", T2)
'''

C6 = r'''
c = db()
task(c, "T1", "B")
cid = comment(c, "T1", "captain", None, "Bitte prüfen", T1)
assert isinstance(cid, int)
assert tuple(c.execute("SELECT task_id, author_kind, author_id, text, ts FROM comments WHERE id = ?", (cid,)).fetchone()) == ("T1", "captain", None, "Bitte prüfen", T1)
assert comment(c, "T1", "agent", "B", "x" * 8000, T2) > cid
for kind in ("user", "", None, "Captain"):
    raises("comment_author_invalid", comment, c, "T1", kind, None, "Hallo", T1)
for text in ("", "  ", None):
    raises("comment_empty", comment, c, "T1", "captain", None, text, T1)
raises("text_too_long", comment, c, "T1", "captain", None, "x" * 8001, T1)
raises("task_not_found", comment, c, "nope", "captain", None, "Hallo", T1)
assert count(c, "comments") == 2
assert get(c, "T1")["revision"] == 1
s = set_check(c, "T1", "gruen", "cand-1", T2)
assert (s["check_result"], s["check_ref"], s["revision"], s["updated_at"]) == ("gruen", "cand-1", 2, T2)
assert set_check(c, "T1", "nicht_geprueft", None, T2)["check_ref"] is None
for result in ("bestanden", "", None, "GRUEN"):
    raises("check_result_invalid", set_check, c, "T1", result, "x", T2)
raises("task_not_found", set_check, c, "nope", "rot", "x", T2)
assert not c.in_transaction
'''

C7 = r'''
c = db()
task(c, "R")
task(c, "M", "B", parent="R")
task(c, "T", "D", parent="M")
ch = chain_rows(c, "T")
assert ch["task"] == get(c, "T")
assert [p["id"] for p in ch["parents"]] == ["R", "M"]
assert ch["parents"][0] == get(c, "R")
assert chain_rows(c, "R") == {"task": get(c, "R"), "parents": []}
raises("task_not_found", chain_rows, c, "nope")
assert children_done(c, "R") is False
c.execute("UPDATE tasks SET state = 'erledigt' WHERE id = 'M'")
assert children_done(c, "R") is True
assert children_done(c, "T") is False
task(c, "M2", "B", "abgebrochen", parent="R")
task(c, "M3", "B", "wartet", parent="R")
assert children_done(c, "R") is False
c.execute("UPDATE tasks SET state = 'erledigt' WHERE id = 'M3'")
assert children_done(c, "R") is True
task(c, "K1", "B", run="run-1")
task(c, "K2", "D", run="run-2")
assert [t["id"] for t in orphans(c, ["run-1"])] == ["K2"]
assert [t["id"] for t in orphans(c, [])] == ["K1", "K2"]
assert orphans(c, {"run-1", "run-2", "run-9"}) == []
assert orphans(c, ("run-2",))[0] == get(c, "K1")
'''

C8 = r'''
c = db()
task(c, "P0", "A", max_level=2)
items = [{"titel": "Bauen", "beschreibung": "b", "rolle": "coder", "blocker": [], "akzeptanz": "Tests grün", "agent_id": "B"},
         {"titel": "Planen", "beschreibung": "p", "rolle": "planner", "blocker": [0], "akzeptanz": "", "agent_id": "C"}]
out = delegate(c, "P0", "A", items, T1)
assert [(t["title"], t["parent_id"], t["assignee"], t["origin"], t["state"], t["created_by"]) for t in out] == [("Bauen", "P0", "B", "delegation", "zugewiesen", "A"), ("Planen", "P0", "C", "delegation", "zugewiesen", "A")]
assert [t["max_level"] for t in out] == [2, 1]
assert [t["description"] for t in out] == ["b\n\nAkzeptanz: Tests grün", "p"]
assert [tuple(r) for r in c.execute("SELECT task_id, blocked_by_task_id FROM blockers")] == [(out[1]["id"], out[0]["id"])]
assert (get(c, "P0")["decomposed_at"], get(c, "P0")["revision"]) == (T1, 2)
raises("task_already_decomposed", delegate, c, "P0", "A", items, T2)
task(c, "P1", "A")
assert [t["max_level"] for t in delegate(c, "P1", "A", items[:1], T2)] == [2]
n = count(c)
task(c, "P2", "A")
raises("delegation_not_allowed", delegate, c, "P2", "B", [dict(items[0], agent_id="D")], T2)
c.execute("UPDATE agents SET can_delegate = 1 WHERE id = 'B'")
raises("delegation_not_below", delegate, c, "P2", "B", [dict(items[0], agent_id="C")], T2)
raises("delegation_target_inactive", delegate, c, "P2", "A", [items[0], dict(items[0], agent_id="P")], T2)
raises("agent_not_found", delegate, c, "P2", "A", [dict(items[0], agent_id="Z")], T2)
raises("delegate_empty", delegate, c, "P2", "A", [], T2)
raises("task_not_found", delegate, c, "nope", "A", items, T2)
assert (count(c), get(c, "P2")["decomposed_at"], count(c, "blockers")) == (n + 1, None, 1)
assert delegate(c, "P2", "B", [dict(items[0], agent_id="D")], T2)[0]["assignee"] == "D"
assert not c.in_transaction
'''

H1 = {"hidden_board_1.py": hidden("create", C1)}
H2 = {**H1, "hidden_board_2.py": hidden("assign", C2)}
H3 = {**H2, "hidden_board_3.py": hidden("checkout", C3)}
H4 = {**H3, "hidden_board_4.py": hidden("set_blocker, clear_blocker", C4)}
H5 = {**H4, "hidden_board_5.py": hidden("release, cancel", C5)}
H6 = {**H5, "hidden_board_6.py": hidden("comment, set_check", C6)}
H7 = {**H6, "hidden_board_7.py": hidden("chain_rows, children_done, orphans", C7)}
H8 = {**H7, "hidden_board_8.py": hidden("delegate", C8)}

TABLES = """Tables (store.py, schema 2): tasks (id, title, description, goal_ref, project_id, parent_id, assignee, state ('offen','zugewiesen','in_arbeit','wartet','erledigt','abgebrochen'), priority (default 0), checkout_by, checkout_at, checkout_run, mission_id, created_by, created_at, updated_at, revision (default 1), max_level (0..6 or NULL), origin ('captain','routine','delegation','system', default 'captain'), decomposed_at, check_result ('gruen','rot','nicht_geprueft'), check_ref, reported_at); blockers (task_id, blocked_by_task_id, created_at; PRIMARY KEY of both); comments (id AUTOINCREMENT, task_id, author_kind ('captain','agent','system'), author_id, text, ts); agents (id, reports_to, status, permission_level, can_delegate, ...)."""
RULES = """Common rules: a task is closed in state 'erledigt' or 'abgebrochen'; every change of a task sets updated_at = now and revision + 1 (one helper); unknown task -> ValueError('task_not_found'), unknown agent -> 'agent_not_found', an agent whose status is not 'aktiv' -> 'agent_inactive'."""

STAGES = [
    {"name": "create",
     "task": f"""Create `board.py` (Python 3, uuid; `import graphs`, `from store import immediate`; both are in the workspace) with `create(conn, fields, now, created_by)` -> the new task as a dict (all columns).
{TABLES}
{RULES}
Checks before the transaction, in this order: a key of fields that is not one of id, title, description, goal_ref, project_id, parent_id, assignee, priority, origin, max_level -> 'task_field_unknown:<first alphabetically>'; title not a string, empty after strip or longer than 200 -> 'task_title_invalid'; origin (default 'captain') not one of the four -> 'task_origin_invalid'; max_level not None and not an int 0..6 (`type(x) is int`) -> 'level_not_allowed'; priority (default 0) not an int -> 'task_field_invalid:priority'.
Inside `with immediate(conn):` (one private helper inserts, a later stage reuses it inside its own transaction): id missing or empty -> 'T-' + 12 hex characters of uuid4; a task with that id exists -> 'task_exists'; parent_id given but unknown -> 'task_not_found'; assignee given: unknown -> 'agent_not_found', not active -> 'agent_inactive'. Insert with state 'zugewiesen' when there is an assignee, else 'offen', created_by, created_at = updated_at = now.""",
     "hidden": H1},
    {"name": "assign",
     "task": """Add `assign(conn, task_id, agent_id, now, by)` -> {"task": the task after the change, "old": the assignee before (or None)} to `board.py` (keep everything else), inside `with immediate(conn):`, checks in this order: unknown task -> 'task_not_found'; closed -> 'task_closed'; checked out (checkout_by set) -> 'task_checked_out'; unknown agent -> 'agent_not_found'; not active -> 'agent_inactive'. Then assignee = agent_id, state 'zugewiesen' (also from 'wartet' or 'offen'), updated_at, revision + 1. A second assignment simply replaces the first.""",
     "hidden": H2},
    {"name": "checkout",
     "task": """Add `checkout(conn, task_id, agent_id, run_id, now)` -> the task as a dict to `board.py` (keep everything else). All inside ONE `with immediate(conn):` (BEGIN IMMEDIATE), checks in this order: unknown task -> 'task_not_found'; checkout_by already set -> 'task_already_checked_out'; assignee is not agent_id or state not 'zugewiesen'/'offen' -> 'task_not_assignable'; the task has an open blocker (a blockers row whose blocking task is not closed) -> 'task_blocked'.
Then `UPDATE tasks SET checkout_by = agent, checkout_run = run_id, checkout_at = now, state = 'in_arbeit', updated_at = now, revision = revision + 1 WHERE id = ? AND checkout_by IS NULL`; when not exactly one row changed -> 'task_already_checked_out'. Two connections to the same file: only the first checkout wins.""",
     "hidden": H3},
    {"name": "blockers",
     "task": """Add to `board.py` (keep everything else), each inside `with immediate(conn):`:
- `set_blocker(conn, task_id, blocked_by, now)` -> None: task_id == blocked_by -> 'blocker_self' (checked first); either task unknown -> 'task_not_found'; the pair exists already -> nothing happens; graphs.has_cycle(all blocker pairs (task_id, blocked_by_task_id) plus the new one) -> 'blocker_cycle'; else insert (created_at = now).
- `clear_blocker(conn, task_id, blocked_by, now)` -> the number of OPEN blockers task_id still has afterwards (blocking task not closed); no such pair -> 'blocker_not_found'. (0 means: the last blocker is gone, the caller wakes the agent.)""",
     "hidden": H4},
    {"name": "release",
     "task": """Add to `board.py` (keep everything else):
- `release(conn, task_id, run_id, state, now, comment=None)` -> the task: state must be 'zugewiesen', 'offen', 'wartet' or 'erledigt' (else 'task_state_invalid', checked first); a comment that is given must be a non-empty string after strip (else 'comment_empty') of at most 8000 characters (else 'text_too_long'); inside `with immediate(conn):` unknown task -> 'task_not_found'; checkout_run empty or not equal to run_id -> 'run_mismatch' (only the own run releases). Then checkout_by, checkout_run, checkout_at = NULL, the new state, and for state 'offen' also assignee = NULL; with a comment add a comments row (author_kind 'system', author_id NULL, ts = now) in the same transaction.
- `cancel(conn, task_id, now, by)` -> {"task", "run_id"}: unknown -> 'task_not_found'; closed -> 'task_closed'; else state 'abgebrochen', checkout fields NULL; run_id = the checkout_run before (or None), so the caller can stop the run.""",
     "hidden": H5},
    {"name": "comment",
     "task": """Add to `board.py` (keep everything else):
- `comment(conn, task_id, author_kind, author_id, text, now)` -> the new comment id: author_kind not 'captain'/'agent'/'system' -> 'comment_author_invalid'; text not a non-empty string after strip -> 'comment_empty'; longer than 8000 -> 'text_too_long' (the same text helper as release); inside `with immediate(conn):` unknown task -> 'task_not_found'; insert (ts = now). A comment does not change the task (no revision).
- `set_check(conn, task_id, result, ref, now)` -> the task: result must be 'gruen', 'rot' or 'nicht_geprueft' (else 'check_result_invalid'); unknown task -> 'task_not_found'; sets check_result and check_ref (revision + 1).""",
     "hidden": H6},
    {"name": "chain",
     "task": """Add the readers to `board.py` (keep everything else):
- `chain_rows(conn, task_id)` -> {"task": the task, "parents": [the parent tasks, the root FIRST]}; unknown task -> 'task_not_found'; walk up over parent_id with a visited set (stop at a missing parent).
- `children_done(conn, root_id)` -> True when the task has at least one child (parent_id = root_id) and every child is closed; else False.
- `orphans(conn, live_run_ids)` -> the tasks (dicts, ordered by id) with a checkout_run that is not in live_run_ids (any iterable): checkouts whose run no longer lives after a restart.""",
     "hidden": H7},
    {"name": "delegate",
     "task": """Add `delegate(conn, parent_id, frm, items, now)` -> list of the new tasks to `board.py` (keep everything else): the subtasks of a foreman's decomposition, all or nothing in ONE `with immediate(conn):`.
items are the results of decompose.check: {titel, beschreibung, rolle, blocker: [indexes into items], akzeptanz, agent_id}. Empty items -> 'delegate_empty' (first). Then: unknown parent -> 'task_not_found'; parent closed -> 'task_closed'; parent decomposed_at already set -> 'task_already_decomposed'; unknown frm -> 'agent_not_found'.
Per item in order: unknown agent_id -> 'agent_not_found'; graphs.check_delegation(all agents as {id, reports_to, status}, frm, agent_id, frm's can_delegate) (delegation_not_allowed, delegation_not_below, delegation_target_inactive); create the task with the insert helper of create: title = titel, description = beschreibung plus '\\n\\nAkzeptanz: ' + akzeptanz when akzeptanz is not empty, parent_id, assignee = agent_id, origin 'delegation', max_level = graphs.inherit_level(parent max_level, the agent's permission_level), created_by = frm.
After all items: one blockers row (new task of the item, new task of the index) per blocker index; parent decomposed_at = now (revision + 1). Return the new tasks in item order. Any error: nothing is written.""",
     "hidden": H8},
]
