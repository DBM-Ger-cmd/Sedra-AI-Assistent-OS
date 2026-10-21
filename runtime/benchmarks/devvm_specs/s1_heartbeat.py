"""Spec 1, Bau-Spec s1_heartbeat (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `heartbeat.py`, D1.2 wakeups, D1.5, ORC-06, ORC-11; gates G2-S1-15, G2-S1-22):
`orchestra/heartbeat.py`, the wake-up queue of the heartbeat. A wake-up is written once per idempotency key (ORC-06), never for an agent that is not active (ORC-12),
and becomes due after the coalescing window; `due` groups the open wake-ups per agent with wakeplan.coalesce and marks the members in one transaction (three assignments
within a second -> one run); `finish` closes a wake-up with its outcome (a wake-up waiting for a single approval can still turn into a run or a refusal);
`pending_request` keeps the tick from filing a second request; `in_flight` lists the checked-out runs for the comparison with the supervisor (ORC-11).
Builds on the seed benchmarks/s1_schema2_seed (store.py schema 2, wakeplan.py = reference of s1_wakeplan).
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_heartbeat)."""

SEED = "benchmarks/s1_schema2_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s1_heartbeat
Python 3 standard library only (datetime) plus `import wakeplan` and `from store import immediate` (both files are in the workspace: do not change them).
No clock (now is an argument, a UTC text like 2026-10-21T08:00:00Z), no other files, no network. The connection is opened by the caller with store.open_db (rows are sqlite3.Row,
isolation_level None, foreign keys on); return plain dicts. Every write runs inside `with immediate(conn):`. Every refusal is a ValueError with exactly the code the task names.
No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import store
from heartbeat import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def agent(conn, id, boss=None, status="aktiv"):
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at) "
                 "VALUES (?, ?, 't', ?, 'coder', ?, ?, 2, '2026-10-21T08:00:00Z', '2026-10-21T08:00:00Z')", (id, "inst-" + id, "Name " + id, boss, status))


def task(conn, id, assignee=None, by=None, run=None, state="zugewiesen"):
    conn.execute("INSERT INTO tasks (id, title, assignee, state, checkout_by, checkout_run, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'captain', ?, ?)",
                 (id, "Titel " + id, assignee, state, by, run, T0, T0))


def wake(conn, id):
    return dict(conn.execute("SELECT * FROM wakeups WHERE id = ?", (id,)).fetchone())


def count(conn):
    return conn.execute("SELECT count(*) FROM wakeups").fetchone()[0]


def db():
    conn = store.open_db(":memory:")
    agent(conn, "A")
    agent(conn, "B", "A")
    agent(conn, "P", "A", "pausiert")
    agent(conn, "X", "A", "beendet")
    return conn


T0, T1, T2 = "2026-10-21T08:00:00Z", "2026-10-21T08:00:01Z", "2026-10-21T08:00:02Z"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = db()
w = enqueue(c, "B", "zugewiesen", "assign:T1:1", T0, 2, task_id="T1")
assert isinstance(w, int)
r = wake(c, w)
assert (r["agent_id"], r["task_id"], r["reason"], r["due_at"], r["created_at"], r["idempotency_key"]) == ("B", "T1", "zugewiesen", T2, T0, "assign:T1:1")
assert (r["coalesced_into"], r["done_at"], r["outcome"], r["job_id"]) == (None, None, None, None)
assert enqueue(c, "B", "antwort", "assign:T1:1", T1, 2) is None
assert count(c) == 1
assert isinstance(enqueue(c, "A", "zugewiesen", "assign:T1:1", T0, 2), int)
assert enqueue(c, "B", "captain", None, T0, 0) != enqueue(c, "B", "captain", None, T0, 0)
assert count(c) == 4
assert wake(c, enqueue(c, "B", "routine", "routine:R1:x", T0, 0))["due_at"] == T0
assert wake(c, enqueue(c, "B", "wiederholung", "retry:T1:1", "2026-10-21T23:59:59Z", 2))["due_at"] == "2026-10-22T00:00:01Z"
assert enqueue(c, "P", "zugewiesen", "k", T0, 2) is None
assert enqueue(c, "X", "zugewiesen", "k", T0, 2) is None
assert count(c) == 6
raises("agent_not_found", enqueue, c, "Z", "zugewiesen", "k", T0, 2)
for reason in ("wecken", "", None, "Captain"):
    raises("wake_reason_invalid", enqueue, c, "B", reason, "k", T0, 2)
assert count(c) == 6
assert not c.in_transaction
'''

C2 = r'''
c = db()
w1 = enqueue(c, "B", "zugewiesen", "k1", T0, 0)
w2 = enqueue(c, "B", "antwort", "k2", T1, 0)
w3 = enqueue(c, "B", "captain", "k3", "2026-10-21T08:00:05Z", 0)
w4 = enqueue(c, "A", "captain", None, T0, 0)
g = due(c, T2)
assert [x["leader"]["id"] for x in g] == [w1, w4]
assert [m["id"] for m in g[0]["members"]] == [w2]
assert g[0]["members"][0]["coalesced_into"] == w1
assert (g[0]["leader"]["reason"], g[1]["members"]) == ("zugewiesen", [])
assert (wake(c, w2)["coalesced_into"], wake(c, w3)["coalesced_into"], wake(c, w1)["coalesced_into"]) == (w1, None, None)
assert [(x["leader"]["id"], x["members"]) for x in due(c, T2)] == [(w1, []), (w4, [])]
assert [m["id"] for m in due(c, T2, coalesce_s=3)[0]["members"]] == [w3]
assert wake(c, w3)["coalesced_into"] == w1
assert due(c, "2026-10-21T07:59:59Z") == []
c2 = db()
ids = [enqueue(c2, "B", "zugewiesen", "assign:T%d:1" % i, t, 2) for i, t in enumerate((T0, T0, T1))]
assert due(c2, T1) == []
burst = due(c2, "2026-10-21T08:00:03Z")
assert [(x["leader"]["id"], [m["id"] for m in x["members"]]) for x in burst] == [(ids[0], ids[1:])]
assert c2.execute("SELECT count(*) FROM wakeups WHERE coalesced_into IS NOT NULL").fetchone()[0] == 2
assert not c2.in_transaction
'''

C3 = r'''
c = db()
w1 = enqueue(c, "B", "zugewiesen", "k1", T0, 0)
w2 = enqueue(c, "B", "antwort", "k2", T0, 0)
due(c, T1)
f = finish(c, w1, "lauf", T1, job_id="job-1", mission_id="M-1")
assert (f["id"], f["outcome"], f["done_at"], f["job_id"], f["mission_id"], f["request_mission_id"]) == (w1, "lauf", T1, "job-1", "M-1", None)
assert (wake(c, w2)["outcome"], wake(c, w2)["done_at"]) == ("lauf", T1)
assert due(c, T2) == []
raises("wakeup_finished", finish, c, w1, "pausiert", T2)
w4 = enqueue(c, "A", "captain", None, T0, 0)
finish(c, w4, "antrag", T1, request_mission_id="M-9")
assert pending_request(c, "A")["id"] == w4
assert finish(c, w4, "lauf", T2, mission_id="M-10")["request_mission_id"] == "M-9"
raises("wakeup_finished", finish, c, w4, "abgelehnt", T2)
assert pending_request(c, "A") is None
w5 = enqueue(c, "A", "captain", None, T0, 0)
w6 = enqueue(c, "A", "captain", None, T0, 0)
finish(c, w5, "antrag", T1, request_mission_id="M-5")
finish(c, w6, "antrag", T1, request_mission_id="M-6")
assert pending_request(c, "A")["id"] == w6
assert finish(c, w6, "abgelehnt", T2)["outcome"] == "abgelehnt"
assert pending_request(c, "A")["id"] == w5
assert pending_request(c, "B") is None
for outcome in ("x", "", None, "lauf_dauerfreigabe"):
    raises("wake_outcome_invalid", finish, c, w5, outcome, T2)
raises("wakeup_not_found", finish, c, 999, "lauf", T2)
'''

C4 = r'''
c = db()
assert in_flight(c) == []
task(c, "T1", "B", "B", "run-1", "in_arbeit")
task(c, "T2", "B")
task(c, "T3", "A", "A", "run-3", "in_arbeit")
old = enqueue(c, "B", "zugewiesen", "k0", T0, 0, task_id="T1")
finish(c, old, "lauf", T0, job_id="job-0")
new = enqueue(c, "B", "zugewiesen", "k1", T1, 0, task_id="T1")
finish(c, new, "lauf", T1, job_id="job-1")
other = enqueue(c, "B", "zugewiesen", "k2", T1, 0, task_id="T1")
finish(c, other, "blockiert", T1, job_id="job-x")
flight = in_flight(c)
assert flight == [{"task_id": "T1", "run_id": "run-1", "job_id": "job-1", "agent_id": "B"}, {"task_id": "T3", "run_id": "run-3", "job_id": None, "agent_id": "A"}]
assert sorted(flight[0]) == ["agent_id", "job_id", "run_id", "task_id"]
c.execute("UPDATE tasks SET checkout_run = NULL, checkout_by = NULL, state = 'zugewiesen' WHERE id = 'T1'")
assert [f["task_id"] for f in in_flight(c)] == ["T3"]
task(c, "T0", "A", "A", "run-0", "in_arbeit")
assert [f["task_id"] for f in in_flight(c)] == ["T0", "T3"]
assert not c.in_transaction
'''

H1 = {"hidden_heartbeat_1.py": hidden("enqueue", C1)}
H2 = {**H1, "hidden_heartbeat_2.py": hidden("enqueue, due", C2)}
H3 = {**H2, "hidden_heartbeat_3.py": hidden("enqueue, due, finish, pending_request", C3)}
H4 = {**H3, "hidden_heartbeat_4.py": hidden("enqueue, finish, in_flight", C4)}

TABLE = """Table wakeups (store.py, schema 2): id INTEGER PRIMARY KEY, agent_id, task_id, reason ('zugewiesen','antwort','routine','captain','wiederholung'), due_at, created_at, coalesced_into, job_id, done_at, idempotency_key, outcome ('lauf','antrag','pausiert','kein_budget','blockiert','keine_aufgabe','laeuft_schon','abgelehnt'), mission_id, request_mission_id."""

STAGES = [
    {"name": "enqueue",
     "task": f"""Create `heartbeat.py` (Python 3; `import wakeplan`, `from store import immediate`; both are in the workspace) with `enqueue(conn, agent_id, reason, key, now, coalesce_s, task_id=None)` -> wake-up id or None.
{TABLE}
- reason not one of the five -> ValueError('wake_reason_invalid') (checked first). Then inside `with immediate(conn):` no agent with that id -> ValueError('agent_not_found').
- An agent whose status is not 'aktiv' gets no wake-up: return None. When key is not None and the agent already has a wake-up with that idempotency_key: return None (nothing written).
- Else insert agent_id, task_id, reason, due_at = now + coalesce_s seconds, created_at = now, idempotency_key = key, and return the new id. Times are UTC texts '%Y-%m-%dT%H:%M:%SZ'.""",
     "hidden": H1},
    {"name": "due",
     "task": """Add `due(conn, now, coalesce_s=0)` -> list of {"leader": row, "members": [rows]} to `heartbeat.py` (keep everything else), inside one `with immediate(conn):`:
- read the open wake-ups (done_at IS NULL and coalesced_into IS NULL) as dicts and group them with `wakeplan.coalesce(rows, now, coalesce_s)` (leader = the agent's oldest due one, members = its other ones due until now + coalesce_s, groups ordered by the leader).
- set coalesced_into = leader id for every member in the database; the returned member dicts carry that new coalesced_into.
A leader stays open (and is returned again by the next `due`) until it is finished.""",
     "hidden": H2},
    {"name": "finish",
     "task": """Add to `heartbeat.py` (keep everything else):
- `finish(conn, wakeup_id, outcome, now, job_id=None, mission_id=None, request_mission_id=None)` -> the wake-up as a dict. outcome must be one of the eight outcomes (else ValueError('wake_outcome_invalid'), checked first); inside `with immediate(conn):` unknown id -> 'wakeup_not_found'. A wake-up that is already finished (done_at set) can only go from outcome 'antrag' to 'lauf' or 'abgelehnt'; anything else -> 'wakeup_finished'. Set outcome and done_at = now; job_id, mission_id, request_mission_id replace the stored value only when given (not None). The members (coalesced_into = this id) get the same outcome and done_at.
- `pending_request(conn, agent_id)` -> the agent's newest wake-up (highest id) with outcome 'antrag' that is not a member (coalesced_into IS NULL), as a dict, or None.""",
     "hidden": H3},
    {"name": "flight",
     "task": """Add `in_flight(conn)` -> list to `heartbeat.py` (keep everything else): one dict {"task_id", "run_id", "job_id", "agent_id"} per task with a checkout_run (tasks.checkout_run IS NOT NULL), ordered by task id: run_id = checkout_run, agent_id = checkout_by, job_id = the job_id of the newest wake-up (highest id) of that task with outcome 'lauf', or None.""",
     "hidden": H4},
]
