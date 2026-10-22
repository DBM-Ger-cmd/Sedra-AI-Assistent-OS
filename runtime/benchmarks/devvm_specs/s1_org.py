"""Spec 1, Bau-Spec s1_org (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `org.py`, D1.2 agents, D1.4 fingerprint, ORC-01, ORC-02, ORC-08, ORC-12; gates G2-S1-01,
G2-S1-02, G2-S1-22): `orchestra/org.py`, the organisation of the agents in orchestra.db: hire (after the Captain's two gates, the desk applier calls it), change the place
in the tree, the role, recipe, level, delegation right, parallel limit and budget fields, pause (Captain, budget, quarantine; idempotent), resume, terminate (final, never
with live subordinates), and the readers. Every structural change goes through graphs.check_org (one root, no cycle, depth limit) and raises the agent's revision; the
fingerprint is what the standing approval of the guard is bound to (D1.4). Builds on the seed benchmarks/s1_schema2_seed (store.py schema 2, graphs.py = reference of s1_graphs).
Additions to D1.1: set_org also takes the budget fields (the desk verb `festlegen` of type budget), hire checks required and unknown fields.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_org)."""

SEED = "benchmarks/s1_schema2_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s1_org
Python 3 standard library only plus `import graphs` and `from store import immediate` (both files are in the workspace: do not change them). No clock (now is an argument), no other files, no network.
The connection is opened by the caller with store.open_db (rows are sqlite3.Row, isolation_level None, foreign keys on); return plain dicts. Every write runs inside `with immediate(conn):`.
Every refusal is a ValueError with exactly the code the task names; a refused call changes nothing. The module defines a function named `list`: use `builtins.list` (or no list() call) inside the module.
No comments and no docstrings, small private helpers instead of copied code (one helper updates an agent and raises its revision).
'''

HEAD = r'''
import store
from org import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def h(id, boss=None, **kw):
    out = {"id": id, "instance_id": "inst-" + id, "template_id": "guppi.orchestra.coder", "name": "Name " + id, "role": "coder", "permission_level": 2, "reports_to": boss}
    out.update(kw)
    return out


def raw(conn, id):
    return dict(conn.execute("SELECT * FROM agents WHERE id = ?", (id,)).fetchone())


def count(conn):
    return conn.execute("SELECT count(*) FROM agents").fetchone()[0]


def tree(conn):
    for i, (id, boss) in enumerate((("A", None), ("B", "A"), ("C", "B"), ("D", "A"))):
        conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at) "
                     "VALUES (?, ?, 't', ?, 'coder', ?, 'aktiv', 2, ?, ?)", (id, "inst-" + id, "Name " + id, boss, "2026-10-21T07:00:0%dZ" % i, "2026-10-21T07:00:00Z"))
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at) "
                 "VALUES ('X', 'inst-X', 't', 'Name X', 'coder', 'A', 'beendet', 2, '2026-10-21T06:00:00Z', '2026-10-21T07:00:00Z')")
    return conn


T0, T1, T2 = "2026-10-21T08:00:00Z", "2026-10-21T08:00:01Z", "2026-10-21T08:00:02Z"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = store.open_db(":memory:")
a = hire(c, h("A", role="foreman", can_delegate=True), T0, 6)
assert (a["id"], a["status"], a["reports_to"], a["role"], a["can_delegate"], a["max_parallel"], a["budget_period"], a["revision"]) == ("A", "aktiv", None, "foreman", 1, 1, "gesamt", 1)
assert (a["created_at"], a["updated_at"], a["pause_reason"], a["instance_id"], a["template_id"]) == (T0, T0, None, "inst-A", "guppi.orchestra.coder")
assert a == raw(c, "A")
assert type(a["can_delegate"]) is int
b = hire(c, h("B", "A", budget_tokens=1000, recipe_id="r1", max_parallel=2, budget_period="monat", budget_eur_cent=50), T1, 6)
assert (b["reports_to"], b["budget_tokens"], b["recipe_id"], b["max_parallel"], b["budget_period"], b["budget_eur_cent"], b["can_delegate"]) == ("A", 1000, "r1", 2, "monat", 50, 0)
assert b == raw(c, "B")
raises("org_second_root", hire, c, h("C"), T1, 6)
raises("org_unknown_superior", hire, c, h("C", "Z"), T1, 6)
raises("org_too_deep", hire, c, h("C", "B"), T1, 2)
for dup in (h("A", "B"), h("C", "A", instance_id="inst-A")):
    raises("agent_exists", hire, c, dup, T1, 6)
assert count(c) == 2
assert not c.in_transaction
'''

C1B = r'''
c = store.open_db(":memory:")
hire(c, h("A"), T0, 6)
raises("org_field_unknown:status", hire, c, h("C", "A", status="pausiert"), T1, 6)
raises("org_field_unknown:aaa", hire, c, h("C", "A", zzz=1, aaa=2), T1, 6)
raises("org_field_missing:instance_id", hire, c, {"id": "C", "reports_to": "A"}, T1, 6)
raises("org_field_missing:role", hire, c, h("C", "A", role=None), T1, 6)
for level in (7, -1, "2", 2.0, True):
    raises("level_not_allowed", hire, c, h("C", "A", permission_level=level), T1, 6)
raises("org_field_invalid:can_delegate", hire, c, h("C", "A", can_delegate=2), T1, 6)
raises("org_field_invalid:max_parallel", hire, c, h("C", "A", max_parallel=5), T1, 6)
raises("org_field_invalid:budget_period", hire, c, h("C", "A", budget_period="jahr"), T1, 6)
raises("org_field_unknown:status", hire, c, h("C", "Z", status="aktiv", permission_level=9), T1, 6)
assert count(c) == 1
assert not c.in_transaction
'''

C2 = r'''
c = tree(store.open_db(":memory:"))
r = set_org(c, "C", {"reports_to": "D", "role": "reviewer"}, T1, 6)
assert (r["reports_to"], r["role"], r["revision"], r["updated_at"]) == ("D", "reviewer", 2, T1)
assert r == raw(c, "C")
same = set_org(c, "C", {"reports_to": "D", "role": "reviewer"}, T2, 6)
assert (same["revision"], same["updated_at"]) == (2, T1)
assert same == raw(c, "C")
change = {"permission_level": 3, "can_delegate": 1, "max_parallel": 4, "budget_tokens": 500, "budget_period": "monat", "recipe_id": "r2", "budget_eur_cent": 100}
r = set_org(c, "C", change, T2, 6)
assert (r["revision"], r["permission_level"], r["can_delegate"], r["max_parallel"], r["budget_tokens"], r["budget_period"], r["recipe_id"], r["budget_eur_cent"]) == (3, 3, 1, 4, 500, "monat", "r2", 100)
assert set_org(c, "C", {"budget_tokens": None}, T2, 6)["budget_tokens"] is None
c.execute("UPDATE agents SET status = 'pausiert', pause_reason = 'budget' WHERE id = 'D'")
assert set_org(c, "D", {"role": "tester"}, T2, 6) == raw(c, "D")
raises("org_cycle", set_org, c, "A", {"reports_to": "C"}, T2, 6)
raises("org_self", set_org, c, "B", {"reports_to": "B"}, T2, 6)
raises("org_unknown_superior", set_org, c, "B", {"reports_to": "X"}, T2, 6)
raises("org_second_root", set_org, c, "B", {"reports_to": None}, T2, 6)
raises("org_too_deep", set_org, c, "C", {"reports_to": "B"}, T2, 2)
raises("agent_not_found", set_org, c, "Z", {"role": "x"}, T2, 6)
raises("agent_terminated", set_org, c, "X", {"role": "x"}, T2, 6)
assert (raw(c, "A")["revision"], raw(c, "B")["revision"], raw(c, "B")["reports_to"], raw(c, "D")["pause_reason"]) == (1, 1, "A", "budget")
assert not c.in_transaction
'''

C2B = r'''
c = tree(store.open_db(":memory:"))
raises("org_field_unknown:name", set_org, c, "B", {"name": "neu", "role": "x"}, T2, 6)
raises("org_field_unknown:status", set_org, c, "B", {"status": "aktiv"}, T2, 6)
raises("level_not_allowed", set_org, c, "B", {"permission_level": 9}, T2, 6)
raises("org_field_invalid:max_parallel", set_org, c, "B", {"max_parallel": 0}, T2, 6)
raises("org_field_invalid:can_delegate", set_org, c, "B", {"can_delegate": 2}, T2, 6)
raises("org_field_invalid:budget_period", set_org, c, "B", {"budget_period": "woche"}, T2, 6)
raises("org_field_unknown:id", set_org, c, "Z", {"id": "Y"}, T2, 6)
assert raw(c, "B")["revision"] == 1
assert not c.in_transaction
'''

C3 = r'''
c = tree(store.open_db(":memory:"))
p = pause(c, "B", "captain", T1)
assert (p["status"], p["pause_reason"], p["revision"], p["updated_at"]) == ("pausiert", "captain", 2, T1)
assert p == raw(c, "B")
again = pause(c, "B", "budget", T2)
assert (again["pause_reason"], again["revision"], again["updated_at"]) == ("captain", 2, T1)
r = resume(c, "B", T2)
assert (r["status"], r["pause_reason"], r["revision"], r["updated_at"]) == ("aktiv", None, 3, T2)
raises("agent_not_paused", resume, c, "B", T2)
assert pause(c, "D", "quarantaene", T1)["pause_reason"] == "quarantaene"
assert pause(c, "C", "budget", T1)["pause_reason"] == "budget"
for reason in ("Captain", "", None, "urlaub"):
    raises("pause_reason_invalid", pause, c, "B", reason, T1)
raises("agent_not_found", pause, c, "Z", "captain", T1)
raises("agent_not_found", resume, c, "Z", T1)
raises("agent_terminated", pause, c, "X", "captain", T1)
raises("agent_terminated", resume, c, "X", T1)
assert raw(c, "B")["revision"] == 3
assert not c.in_transaction
'''

C4 = r'''
c = tree(store.open_db(":memory:"))
raises("org_has_subordinates", terminate, c, "A", T1)
raises("org_has_subordinates", terminate, c, "B", T1)
t = terminate(c, "C", T1)
assert (t["status"], t["revision"], t["updated_at"]) == ("beendet", 2, T1)
assert t == raw(c, "C")
raises("agent_terminated", terminate, c, "C", T2)
pause(c, "B", "captain", T1)
b = terminate(c, "B", T2)
assert (b["status"], b["pause_reason"]) == ("beendet", None)
pause(c, "D", "budget", T1)
raises("org_has_subordinates", terminate, c, "A", T2)
assert hire(c, h("E", "D"), T2, 6)["reports_to"] == "D"
raises("org_unknown_superior", hire, c, h("F", "B"), T2, 6)
raises("agent_not_found", terminate, c, "Z", T2)
assert raw(c, "A")["status"] == "aktiv"
assert not c.in_transaction
'''

C5 = r'''
c = tree(store.open_db(":memory:"))
assert get(c, "A") == raw(c, "A")
assert get(c, "Z") is None
assert [a["id"] for a in list(c)] == ["X", "A", "B", "C", "D"]
assert [a["id"] for a in list(c, "aktiv")] == ["A", "B", "C", "D"]
assert [a["id"] for a in list(c, "beendet")] == ["X"]
assert list(c, "pausiert") == []
assert [a["id"] for a in subordinates(c, "A")] == ["B", "D"]
assert [a["id"] for a in subordinates(c, "A", deep=True)] == ["B", "D", "C"]
assert subordinates(c, "C", deep=True) == []
assert subordinates(c, "B")[0] == raw(c, "C")
fp = fingerprint(get(c, "B"))
assert fp == {"agent_id": "B", "status": "aktiv", "permission_level": 2, "recipe_id": None, "reports_to": "A", "budget_tokens": None, "budget_eur_cent": None, "budget_period": "gesamt"}
set_org(c, "B", {"permission_level": 1}, T1, 6)
assert fingerprint(get(c, "B")) != fp
assert fingerprint(get(c, "B"))["permission_level"] == 1
assert fingerprint(pause(c, "D", "captain", T1))["status"] == "pausiert"
'''

H1 = {"hidden_org_1.py": hidden("hire", C1)}
H1B = {**H1, "hidden_org_1b.py": hidden("hire", C1B)}
H2 = {**H1B, "hidden_org_2.py": hidden("set_org", C2)}
H2B = {**H2, "hidden_org_2b.py": hidden("set_org", C2B)}
H3 = {**H2B, "hidden_org_3.py": hidden("pause, resume", C3)}
H4 = {**H3, "hidden_org_4.py": hidden("hire, pause, terminate", C4)}
H5 = {**H4, "hidden_org_5.py": hidden("get, list, subordinates, fingerprint, set_org, pause", C5)}

TABLE = """Table agents (store.py, schema 2): id, instance_id (UNIQUE), template_id, name, role, recipe_id, reports_to, status ('aktiv','pausiert','beendet'), permission_level (0..6), budget_tokens, budget_eur_cent, budget_period ('gesamt','monat'), created_at, updated_at, revision (default 1), can_delegate (0/1, default 0), max_parallel (1..4, default 1), pause_reason ('captain','budget','quarantaene' or NULL)."""
GRAPHS = """graphs.py (given): check_org(rows, change, max_depth) with rows [{id, reports_to, status}] raises org_self, org_unknown_superior, org_cycle, org_second_root, org_no_root, org_too_deep; can_terminate(rows, id) raises org_has_subordinates."""
VALUES = """Value checks (one helper): permission_level an int 0..6 (`type(x) is int`) else ValueError('level_not_allowed'); can_delegate 0 or 1 else 'org_field_invalid:can_delegate'; max_parallel an int 1..4 else 'org_field_invalid:max_parallel'; budget_period 'gesamt' or 'monat' else 'org_field_invalid:budget_period'."""

STAGES = [
    {"name": "hire",
     "task": f"""Create `org.py` (Python 3; `import graphs`, `from store import immediate`; both are in the workspace) with `hire(conn, row, now, max_depth)` -> the new agent row as a dict with ALL columns, read back from the table after the insert (so can_delegate is the stored 0/1, also when True was given).
{TABLE}
{GRAPHS}
row may hold id, instance_id, template_id, name, role, recipe_id, reports_to, permission_level, budget_tokens, budget_eur_cent, budget_period, can_delegate, max_parallel (defaults: can_delegate 0, max_parallel 1, budget_period 'gesamt'). The field checks follow in the next stage.
Inside `with immediate(conn):`, each a ValueError, a refused call writes nothing: an agent with the same id or the same instance_id exists -> 'agent_exists'; then graphs.check_org(all agents as rows {{id, reports_to, status}}, {{id, reports_to, status 'aktiv'}}, max_depth).
Insert with status 'aktiv', created_at = updated_at = now (revision and pause_reason keep their defaults).""",
     "hidden": H1},
    {"name": "hire_fields",
     "task": f"""Add the field checks to `hire` in `org.py` (keep everything else). They come before the transaction, in this order, each a ValueError, a refused call writes nothing:
1. a key of row that is not one of id, instance_id, template_id, name, role, recipe_id, reports_to, permission_level, budget_tokens, budget_eur_cent, budget_period, can_delegate, max_parallel -> 'org_field_unknown:<first such key alphabetically>';
2. id, instance_id, template_id, name, role or permission_level missing or None -> 'org_field_missing:<first missing in this order>';
3. {VALUES} (defaults before the check: can_delegate 0, max_parallel 1, budget_period 'gesamt').
Then the checks of the first stage (agent_exists, check_org).""",
     "hidden": H1B},
    {"name": "set_org",
     "task": """Add `set_org(conn, agent_id, change, now, max_depth)` -> the agent as a dict with ALL columns as stored in the table (also when nothing changed) to `org.py` (keep everything else). change may hold reports_to, role, recipe_id, permission_level, can_delegate, max_parallel, budget_tokens, budget_eur_cent, budget_period (the field checks follow in the next stage).
Inside `with immediate(conn):` unknown agent -> ValueError('agent_not_found'), status 'beendet' -> 'agent_terminated' (a paused agent can be changed).
Only fields whose value really differs count; none -> return the agent unchanged (no revision, no updated_at). When reports_to differs: graphs.check_org(all agents, {id, new reports_to, the agent's status}, max_depth). Then update the fields, updated_at = now and revision + 1 (ONE helper for every agent update that returns the stored row: also used by later stages).""",
     "hidden": H2},
    {"name": "set_org_fields",
     "task": f"""Add the field checks to `set_org` in `org.py` (keep everything else), before the transaction and in this order: a key of change that is not one of reports_to, role, recipe_id, permission_level, can_delegate, max_parallel, budget_tokens, budget_eur_cent, budget_period -> 'org_field_unknown:<first alphabetically>'; then the value checks of hire for the keys present ({VALUES}). A refused call changes nothing.""",
     "hidden": H2B},
    {"name": "pause",
     "task": """Add to `org.py` (keep everything else), each inside `with immediate(conn):`, returning the agent as a dict:
- `pause(conn, agent_id, reason, now)`: reason must be 'captain', 'budget' or 'quarantaene' (else ValueError('pause_reason_invalid'), checked first); unknown agent -> 'agent_not_found'; 'beendet' -> 'agent_terminated'; already 'pausiert' -> return it unchanged (idempotent, the first reason stays); else status 'pausiert', pause_reason = reason, updated_at, revision + 1.
- `resume(conn, agent_id, now)`: unknown -> 'agent_not_found'; 'beendet' -> 'agent_terminated'; not 'pausiert' -> 'agent_not_paused'; else status 'aktiv', pause_reason NULL, updated_at, revision + 1.""",
     "hidden": H3},
    {"name": "terminate",
     "task": """Add `terminate(conn, agent_id, now)` -> the agent as a dict to `org.py` (keep everything else), inside `with immediate(conn):`: unknown -> 'agent_not_found'; already 'beendet' -> 'agent_terminated'; graphs.can_terminate(all agents, agent_id) (an active or paused subordinate -> 'org_has_subordinates'); else status 'beendet' (final), pause_reason NULL, updated_at, revision + 1. A terminated agent can no longer be a superior (check_org refuses it).""",
     "hidden": H4},
    {"name": "read",
     "task": """Add the readers to `org.py` (keep everything else), all returning plain dicts with all columns:
- `get(conn, agent_id)` -> the agent or None.
- `list(conn, status=None)` -> all agents (or those with that status), ordered by created_at, then id. (The function is named list: inside the module use builtins.list.)
- `subordinates(conn, agent_id, deep=False)` -> the agents with reports_to = agent_id whose status is not 'beendet', ordered by created_at, then id; deep=True adds the next levels level by level (all direct ones first, then theirs, ...).
- `fingerprint(agent)` -> {"agent_id", "status", "permission_level", "recipe_id", "reports_to", "budget_tokens", "budget_eur_cent", "budget_period"} from an agent dict (the binding of the standing approval, D1.4).""",
     "hidden": H5},
]
