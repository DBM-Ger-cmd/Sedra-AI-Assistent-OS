"""Spec 1, Bau-Spec s1_wakeplan (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `wakeplan.py`, D1.5, ORC-05, ORC-06; gates G2-S1-01, G2-S1-22):
`orchestra/wakeplan.py`, the pure rules of the heartbeat: the idempotency key of a wake-up, the coalescing of the open wake-ups of an agent into one run, the choice of
the task (never a blocked or checked-out one, ORC-05) and the decision what a wake-up leads to (run with a standing approval, a request, or an end without a mission).
heartbeat.py imports it (seed of s1_heartbeat). Times are UTC texts "YYYY-MM-DDTHH:MM:SSZ"; there is no clock in the module.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_wakeplan)."""

NOTES = '''# Notes for s1_wakeplan
Python 3 standard library only (datetime); no sqlite3, no files, no clock (never datetime.now), no network. Times are texts in the form 2026-10-21T08:00:00Z (UTC).
Every function is pure and never modifies its arguments. Every refusal is a ValueError with exactly the code the task names.
No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import copy
from wakeplan import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def w(id, agent, due, done=None, into=None):
    return {"id": id, "agent_id": agent, "due_at": due, "done_at": done, "coalesced_into": into, "reason": "zugewiesen"}


def t(id, state="zugewiesen", prio=0, created="2026-10-21T08:00:00Z", by=None):
    return {"id": id, "state": state, "priority": prio, "created_at": created, "checkout_by": by, "assignee": "A"}


NOW = "2026-10-21T08:00:10Z"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert key_for("assign", ("T1", 3)) == "assign:T1:3"
assert key_for("comment", 17) == "comment:17"
assert key_for("captain", ["m-9"]) == "captain:m-9"
assert key_for("routine", ("R1", "2026-10-21T08:00:00Z")) == "routine:R1:2026-10-21T08:00:00Z"
assert [key_for(s, r) for s, r in (("unblocked", ("T1", "T2")), ("report", "T0"), ("retry", ("T1", 1)))] == ["unblocked:T1:T2", "report:T0", "retry:T1:1"]
for source in ("wecken", "", None, "ASSIGN"):
    raises("wake_source_unknown", key_for, source, "x")
for source, ref in (("assign", "T1"), ("assign", ("T1", 2, 3)), ("comment", ("1", "2")), ("captain", None), ("report", ""), ("retry", ("T1", None)), ("routine", ())):
    raises("wake_ref_invalid", key_for, source, ref)
'''

C2 = r'''
rows = [w(5, "A", "2026-10-21T08:00:03Z"), w(2, "A", "2026-10-21T08:00:01Z"), w(3, "A", "2026-10-21T08:00:01Z"), w(4, "B", "2026-10-21T08:00:00Z"),
        w(6, "A", "2026-10-21T08:00:11Z"), w(7, "A", "2026-10-21T08:00:13Z"), w(8, "C", "2026-10-21T08:00:11Z"), w(9, "B", "2026-10-21T07:00:00Z", done="x"),
        w(10, "B", "2026-10-21T07:00:00Z", into=4)]
keep = copy.deepcopy(rows)
groups = coalesce(rows, NOW, 2)
assert [g["leader"]["id"] for g in groups] == [4, 2]
assert [m["id"] for m in groups[1]["members"]] == [3, 5, 6]
assert groups[0]["members"] == []
assert groups[1]["leader"] == w(2, "A", "2026-10-21T08:00:01Z")
assert rows == keep
assert [[m["id"] for m in g["members"]] for g in coalesce(rows, NOW, 3)] == [[], [3, 5, 6, 7]]
assert [[m["id"] for m in g["members"]] for g in coalesce(rows, NOW, 0)] == [[], [3, 5]]
assert coalesce(rows, "2026-10-21T07:59:59Z", 2) == []
assert [g["leader"]["id"] for g in coalesce(rows, "2026-10-21T08:00:00Z", 2)] == [4]
assert coalesce([], NOW, 2) == []
assert [g["leader"]["id"] for g in coalesce(rows, "2026-10-21T08:00:11Z", 0)] == [4, 2, 8]
late = coalesce([w(1, "A", "2026-10-21T23:59:59Z")], "2026-10-22T00:00:00Z", 5)
assert [g["leader"]["id"] for g in late] == [1]
day = coalesce([w(1, "A", "2026-10-21T23:59:59Z"), w(2, "A", "2026-10-22T00:00:04Z")], "2026-10-22T00:00:00Z", 5)
assert [m["id"] for m in day[0]["members"]] == [2]
'''

C3 = r'''
tasks = [t("T1", prio=1, created="2026-10-21T07:00:00Z"), t("T2", prio=5, created="2026-10-21T07:30:00Z"), t("T3", prio=5, created="2026-10-21T07:10:00Z"),
         t("T4", state="offen", prio=9), t("T5", state="erledigt", prio=99), t("T6", state="wartet", prio=99)]
keep = copy.deepcopy(tasks)
blockers = [{"task_id": "T4", "blocked_by_task_id": "T9", "state": "offen"}, {"task_id": "T3", "blocked_by_task_id": "T8", "state": "erledigt"},
            {"task_id": "T2", "blocked_by_task_id": "T7", "state": "abgebrochen"}]
task, reason = pick_task(tasks, blockers, None)
assert (task["id"], reason) == ("T3", "ok")
assert task == keep[2]
assert tasks == keep
assert pick_task(tasks, blockers, "T1")[0]["id"] == "T1"
assert pick_task(tasks, blockers, "T4")[0]["id"] == "T3"
assert pick_task(tasks, blockers, "T5")[0]["id"] == "T3"
assert pick_task(tasks, blockers, "T99")[0]["id"] == "T3"
assert pick_task(tasks, [], None)[0]["id"] == "T4"
assert pick_task([t("Ta", created="2026-10-21T07:00:00Z"), t("T0", created="2026-10-21T07:00:00Z")], [], None)[0]["id"] == "T0"
assert pick_task([t("T1", by="run-1"), t("T2")], [], None)[0]["id"] == "T2"
assert pick_task([t("T4", state="offen")], blockers, None) == (None, "nur_blockiert")
assert pick_task([t("T4", state="offen"), t("T1", state="in_arbeit", by="run-1")], blockers, None) == (None, "nur_blockiert")
assert pick_task([t("T1", state="in_arbeit", by="run-1"), t("T5", state="erledigt")], [], None) == (None, "ausgecheckt")
assert pick_task([t("T5", state="erledigt"), t("T6", state="wartet")], [], None) == (None, "keine_aufgabe")
assert pick_task([], [], "T1") == (None, "keine_aufgabe")
assert pick_task([{"id": "T1", "state": "offen", "created_at": "2026-10-21T07:00:00Z", "checkout_by": None}], [], None)[1] == "ok"
'''

C4 = r'''
on, off = {"id": "A", "status": "aktiv"}, {"id": "A", "status": "pausiert"}
assert decide_run(on, "ok", True, "ok") == "lauf_dauerfreigabe"
assert decide_run(on, "warnung", True, "ok") == "lauf_dauerfreigabe"
assert decide_run(on, "ok", False, "ok") == "antrag"
assert decide_run(on, "warnung", None, "ok") == "antrag"
for budget in ("gestoppt", "zu_wenig"):
    assert decide_run(on, budget, True, "ok") == "kein_budget", budget
assert decide_run(off, "ok", True, "ok") == "pausiert"
assert decide_run({"id": "A", "status": "beendet"}, "gestoppt", False, "keine_aufgabe") == "pausiert"
assert decide_run(on, "gestoppt", True, "ausgecheckt") == "laeuft_schon"
assert decide_run(on, "gestoppt", True, "nur_blockiert") == "blockiert"
assert decide_run(on, "zu_wenig", False, "keine_aufgabe") == "keine_aufgabe"
for reason in ("", "blockiert", None):
    raises("wake_reason_unknown", decide_run, on, "ok", True, reason)
for budget in ("", "stopp", None):
    raises("budget_state_unknown", decide_run, on, budget, True, "ok")
raises("wake_reason_unknown", decide_run, off, "stopp", True, "x")
raises("budget_state_unknown", decide_run, off, "stopp", True, "ok")
task, reason = pick_task([t("T1", by="run-1", state="in_arbeit")], [], None)
assert decide_run(on, "ok", True, reason) == "laeuft_schon"
'''

H1 = {"hidden_wakeplan_1.py": hidden("key_for", C1)}
H2 = {**H1, "hidden_wakeplan_2.py": hidden("coalesce", C2)}
H3 = {**H2, "hidden_wakeplan_3.py": hidden("pick_task", C3)}
H4 = {**H3, "hidden_wakeplan_4.py": hidden("decide_run, pick_task", C4)}

STAGES = [
    {"name": "key",
     "task": """Create `wakeplan.py` (Python 3 standard library only) with `key_for(source, ref)` -> str, the idempotency key of a wake-up.
source and the number of parts of ref: 'assign' 2 (task, revision), 'comment' 1 (comment id), 'captain' 1 (message id), 'routine' 2 (routine id, due time), 'unblocked' 2 (task, blocker), 'report' 1 (root task), 'retry' 2 (task, n).
ref is a tuple or list of parts, or a single value (= one part). The key is source and the parts joined with ':' (every part as str), e.g. key_for('assign', ('T1', 3)) == 'assign:T1:3'.
Errors: an unknown source -> ValueError('wake_source_unknown'); a wrong number of parts, or a part that is None or '' -> ValueError('wake_ref_invalid').""",
     "hidden": H1},
    {"name": "coalesce",
     "task": """Add `coalesce(open_wakeups, now, coalesce_s)` -> list of {"leader": row, "members": [rows]} to `wakeplan.py` (keep everything else).
Rows are dicts with id (int), agent_id, due_at, done_at, coalesced_into; times are UTC texts like '2026-10-21T08:00:00Z' (parse them with the format '%Y-%m-%dT%H:%M:%SZ'; no clock).
- Only open rows count: done_at is None and coalesced_into is None.
- Per agent: the leader is its oldest open row (smallest due_at, then smallest id). The agent gets a group only when the leader is due (due_at <= now).
- members: the agent's other open rows with due_at <= now + coalesce_s seconds, ordered by due_at, then id (so a wake-up that comes a moment later joins the run).
- The groups are ordered by the leader's due_at, then id. The rows in the result are the input rows (equal dicts); never modify the input.""",
     "hidden": H2},
    {"name": "pick",
     "task": """Add `pick_task(tasks, blockers, prefer_task_id)` -> (task or None, reason) to `wakeplan.py` (keep everything else).
tasks are the task rows of ONE agent (dicts with id, state, priority, created_at, checkout_by; a missing priority counts 0). blockers are rows {task_id, blocked_by_task_id, state} where state is the state of the BLOCKING task; a blocker is open unless that state is 'erledigt' or 'abgebrochen'.
- A task can be picked when its state is 'zugewiesen' or 'offen', checkout_by is empty (None or ''), and it has no open blocker.
- Choice: the task prefer_task_id if it can be picked; else the highest priority, then the oldest created_at, then the smallest id. Return (that task row, 'ok').
- Nothing can be picked: (None, 'nur_blockiert') when some task in state 'zugewiesen'/'offen' with empty checkout_by exists (all of them are blocked); else (None, 'ausgecheckt') when any task has a checkout_by; else (None, 'keine_aufgabe').""",
     "hidden": H3},
    {"name": "decide",
     "task": """Add `decide_run(agent, budget_state, standing, task_reason)` -> outcome to `wakeplan.py` (keep everything else). agent is a row with status; budget_state is 'ok', 'warnung', 'gestoppt' or 'zu_wenig' (the rest is smaller than the output cap of a run); standing is truthy when the agent has a valid standing approval; task_reason is the reason from pick_task.
First the inputs: task_reason not in (ok, nur_blockiert, ausgecheckt, keine_aufgabe) -> ValueError('wake_reason_unknown'); then budget_state unknown -> ValueError('budget_state_unknown').
Then in this order: status not 'aktiv' -> 'pausiert'; task_reason 'ausgecheckt' -> 'laeuft_schon', 'nur_blockiert' -> 'blockiert', 'keine_aufgabe' -> 'keine_aufgabe'; budget_state 'gestoppt' or 'zu_wenig' -> 'kein_budget'; standing truthy -> 'lauf_dauerfreigabe'; else 'antrag'.""",
     "hidden": H4},
]
