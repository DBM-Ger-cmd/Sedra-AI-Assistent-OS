"""Buildflow core (docs/BUILDFLOW_2026-10-13.md; Captain 2026-10-13: "schaffe eine richtige Funktion in GUPPI fuer so einen Workflow"). `buildflow_core.py` is the pure logic of a build task: how a task is made, the
state machine (draft -> checked -> spec_approved -> queued -> building -> built/failed -> reported -> adopt_approved -> adopted, cancel from nearly everywhere), the order of the queue (priority, then age; night tasks only at
night) and the one-line text of a task. No files, no clock, no processes: the store, the runner and the command line (Claude) call these functions and give them the time. GUPPI builds it, Claude wrote this file, the
hidden tests and the reference (benchmarks/devvm_refs/buildflow_core)."""

NOTES = '''# Notes for buildflow_core
Pure Python 3 standard library (`copy`, `re`, `uuid` are allowed), no file, process, clock or network access (the time is always an argument, an ISO text such as "2026-10-13T18:00:00"), never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top.
Texts contain the character · (UTF-8 source).
'''

S1 = r'''
from buildflow_core import new_task, line
t = new_task("  Katalog   bauen ", "assert_catalog", now="2026-10-13T18:00:00", task_id="BF-AAAA0001")
assert t == {"id": "BF-AAAA0001", "title": "Katalog bauen", "spec": "assert_catalog", "seed": "", "review": "", "from_stage": "", "rework": 3, "priority": 0, "window": "now",
             "state": "draft", "created": "2026-10-13T18:00:00", "updated": "2026-10-13T18:00:00",
             "history": [{"at": "2026-10-13T18:00:00", "event": "created", "from": None, "to": "draft", "note": ""}], "result": {}}
u = new_task("Leiste", "gate_bar", now="2026-10-13T18:05:00", seed="seeds/x", review="reviews/y.md", from_stage="rest", rework=0, priority=9, window="night", task_id="BF-BBBB0002")
assert (u["seed"], u["review"], u["from_stage"], u["rework"], u["priority"], u["window"]) == ("seeds/x", "reviews/y.md", "rest", 0, 9, "night")
auto = new_task("A", "x", now="2026-10-13T18:00:00")
assert auto["id"].startswith("BF-") and len(auto["id"]) == 11 and auto["id"] == auto["id"].upper() and auto["id"] != new_task("A", "x", now="2026-10-13T18:00:00")["id"]
for kw in ({"title": ""}, {"title": "   "}, {"title": None}, {"spec": "bad name"}, {"spec": ""}, {"spec": "a/b"}, {"spec": 5}, {"window": "later"}, {"rework": -1}, {"rework": 11}, {"rework": True}, {"rework": "3"},
           {"priority": -1}, {"priority": 10}, {"priority": 1.5}):
    args = {"title": "T", "spec": "s", "now": "2026-10-13T18:00:00"}
    args.update(kw)
    title, spec = args.pop("title"), args.pop("spec")
    try:
        new_task(title, spec, **args)
    except ValueError as error:
        assert str(error) in ("bad title", "bad spec", "bad window", "bad rework", "bad priority"), str(error)
    else:
        raise AssertionError(repr(kw))
for kw, text in (({"title": ""}, "bad title"), ({"spec": "a b"}, "bad spec"), ({"window": "x"}, "bad window"), ({"rework": 11}, "bad rework"), ({"priority": 10}, "bad priority")):
    args = {"title": "T", "spec": "s", "now": "2026-10-13T18:00:00"}
    args.update(kw)
    title, spec = args.pop("title"), args.pop("spec")
    try:
        new_task(title, spec, **args)
    except ValueError as error:
        assert str(error) == text
assert line(t) == "BF-AAAA0001 [draft] V0 jetzt · Katalog bauen"
assert line(u) == "BF-BBBB0002 [draft] V9 nacht · Leiste"
'''

S2 = S1 + r'''
from buildflow_core import STATES, transition, can, events_for
assert STATES == ("draft", "checked", "spec_approved", "queued", "building", "built", "failed", "reported", "adopt_approved", "adopted", "cancelled")
assert events_for(t) == ["cancel", "check_failed", "check_ok"]
assert can(t, "check_ok") and not can(t, "queue") and not can(t, "start")
path = [("check_ok", "checked"), ("approve_spec", "spec_approved"), ("queue", "queued"), ("start", "building"), ("finish_ok", "built"), ("report", "reported"),
        ("approve_adopt", "adopt_approved"), ("adopt", "adopted")]
cur = t
for number, (event, state) in enumerate(path, 1):
    stamp = "2026-10-13T19:%02d:00" % number
    nxt = transition(cur, event, stamp, note="n" + str(number))
    assert nxt["state"] == state and nxt["updated"] == stamp and nxt["created"] == "2026-10-13T18:00:00"
    assert nxt["history"][-1] == {"at": stamp, "event": event, "from": cur["state"], "to": state, "note": "n" + str(number)}
    assert len(nxt["history"]) == len(cur["history"]) + 1 and cur["state"] != state
    cur = nxt
assert cur["state"] == "adopted" and events_for(cur) == [] and len(cur["history"]) == 9
assert events_for(transition(t, "check_ok", "x")) == ["approve_spec", "cancel", "check_failed"]
assert events_for({"state": "building"}) == ["finish_failed", "finish_ok"]
assert events_for({"state": "failed"}) == ["cancel", "requeue"] and events_for({"state": "reported"}) == ["approve_adopt", "cancel", "requeue"]
assert events_for({"state": "cancelled"}) == [] and events_for({"state": "queued"}) == ["cancel", "start"]
failed = transition(transition(transition(transition(transition(t, "check_ok", "a"), "approve_spec", "b"), "queue", "c"), "start", "d"), "finish_failed", "e", note="stage rest", result={"failed_stage": "rest", "passed": 2})
assert failed["state"] == "failed" and failed["result"] == {"failed_stage": "rest", "passed": 2}
again = transition(failed, "requeue", "f", review="reviews/k14.md", from_stage="rest")
assert again["state"] == "queued" and again["review"] == "reviews/k14.md" and again["from_stage"] == "rest" and again["result"] == {"failed_stage": "rest", "passed": 2}
merged = transition(again, "start", "g")
done = transition(merged, "finish_ok", "h", result={"passed": 4, "seconds": 12.5})
assert done["result"] == {"failed_stage": "rest", "passed": 4, "seconds": 12.5}
checked_again = transition(transition(t, "check_ok", "a"), "check_failed", "b", note="lint problems")
assert checked_again["state"] == "draft" and checked_again["history"][-1]["note"] == "lint problems"
assert transition(transition(t, "check_ok", "a"), "cancel", "b")["state"] == "cancelled"
for state in ("draft", "checked", "spec_approved", "queued", "failed", "built", "reported", "adopt_approved"):
    assert can({"state": state}, "cancel"), state
for state in ("building", "adopted", "cancelled"):
    assert not can({"state": state}, "cancel"), state
for task, event, text in ((t, "queue", "illegal_transition: draft queue"), (t, "finish_ok", "illegal_transition: draft finish_ok"), (cur, "cancel", "illegal_transition: adopted cancel"),
                          ({"state": "building"}, "cancel", "illegal_transition: building cancel"), (t, "explode", "unknown_event: explode")):
    try:
        transition(task, event, "x")
    except ValueError as error:
        assert str(error) == text, str(error)
    else:
        raise AssertionError(event)
try:
    transition(t, "check_ok", "x", color="red")
except ValueError as error:
    assert str(error) == "unknown change: color"
else:
    raise AssertionError("no ValueError")
before = repr(failed)
transition(failed, "requeue", "z", review="r", result={"extra": 1})
assert repr(failed) == before
'''

S3 = S2 + r'''
from buildflow_core import queue_order, pick_next
def queued(i, priority, created, window="now", state="queued"):
    task = new_task("T" + i, "s", now=created, task_id="BF-" + i, priority=priority, window=window)
    task["state"] = state
    return task
a, b, c = queued("A", 1, "2026-10-13T10:00:00"), queued("B", 5, "2026-10-13T11:00:00"), queued("C", 5, "2026-10-13T09:00:00")
d, e = queued("D", 9, "2026-10-13T08:00:00", window="night"), queued("E", 9, "2026-10-13T07:00:00", state="building")
tasks = [a, b, c, d, e, queued("F", 0, "2026-10-13T06:00:00", state="draft")]
assert [x["id"] for x in queue_order(tasks)] == ["BF-D", "BF-C", "BF-B", "BF-A"]
assert pick_next(tasks, night=True) is d
assert pick_next(tasks) is c and pick_next(tasks, night=False) is c
assert pick_next([a, d]) is a and pick_next([d]) is None and pick_next([d], night=True) is d
assert pick_next([]) is None and pick_next([e, tasks[-1]]) is None and pick_next([], night=True) is None
tie = [queued("Z", 3, "2026-10-13T10:00:00"), queued("Y", 3, "2026-10-13T10:00:00")]
assert [x["id"] for x in queue_order(tie)] == ["BF-Y", "BF-Z"] and pick_next(tie)["id"] == "BF-Y"
snapshot = repr(tasks)
queue_order(tasks)
pick_next(tasks, night=True)
assert repr(tasks) == snapshot and tasks[0] is a
'''

STAGES = [
    {"name": "task", "no_own_check": True,
     "task": '''Create `buildflow_core.py` (what a task is: see below). `new_task(title, spec, *, now, seed="", review="", from_stage="", rework=3, priority=0, window="now", task_id=None) -> dict`:
- `title`: white space is cleaned (`" ".join(text.split())`); an empty or missing title raises ValueError("bad title").
- `spec`: a text of letters, digits and "_" only (`re.fullmatch`), else ValueError("bad spec").
- `window`: "now" or "night", else ValueError("bad window"). `rework`: an int from 0 to 10 (a bool or a text is not allowed), else ValueError("bad rework"). `priority`: an int from 0 to 9, else ValueError("bad priority"). The checks run in this order: title, spec, window, rework, priority.
- `task_id`: when None the id is "BF-" + 8 upper case hex characters of `uuid.uuid4()` (11 characters in total).
- Result: {"id", "title", "spec", "seed" (text), "review" (text), "from_stage" (text), "rework", "priority", "window", "state": "draft", "created": now, "updated": now, "history": [{"at": now, "event": "created", "from": None, "to": "draft", "note": ""}], "result": {}}.
`line(task) -> str`: "<id> [<state>] V<priority> <window text> · <title>" where the window text is "jetzt" for "now" and "nacht" for "night" (module level dict `WINDOWS`), for example "BF-AAAA0001 [draft] V0 jetzt · Katalog bauen". No comments and no docstrings.''',
     "hidden": {"hidden_flow_1.py": S1}},
    {"name": "machine", "no_own_check": True,
     "task": '''In `buildflow_core.py` (keep everything) add the state machine. `STATES` is the tuple ("draft", "checked", "spec_approved", "queued", "building", "built", "failed", "reported", "adopt_approved", "adopted", "cancelled"). The allowed transitions (a module level dict `TRANSITIONS` {(state, event): new_state}):
draft: check_ok -> checked, check_failed -> draft; checked: approve_spec -> spec_approved, check_failed -> draft; spec_approved: queue -> queued; queued: start -> building; building: finish_ok -> built, finish_failed -> failed; failed: requeue -> queued; built: report -> reported; reported: approve_adopt -> adopt_approved, requeue -> queued; adopt_approved: adopt -> adopted.
Besides, the event "cancel" leads to "cancelled" from every state except building, adopted and cancelled.
`events_for(task) -> list`: the sorted list of the events the task's state allows (cancel included where it is allowed). `can(task, event) -> bool`.
`transition(task, event, now, note="", **changes) -> dict`: returns a NEW task (the argument is not modified; use deep copies). An event that exists nowhere raises ValueError("unknown_event: <event>"); a change other than review, from_stage or result raises ValueError("unknown change: <name>") (this check comes before the legal check); an event the state does not allow raises ValueError("illegal_transition: <state> <event>"). The new task has the new state, `updated` = now, a history entry appended {"at": now, "event": event, "from": old state, "to": new state, "note": note}, and the changes applied: `review` and `from_stage` replace the values, `result` (a dict) is merged into the existing result dict (`update`). No comments and no docstrings.''',
     "hidden": {"hidden_flow_2.py": S2}},
    {"name": "queue", "no_own_check": True,
     "task": '''In `buildflow_core.py` add the order of the queue. `queue_order(tasks) -> list`: the tasks whose state is "queued", sorted by priority (higher first), then `created` (older first, plain text comparison), then id. `pick_next(tasks, night=False)`: the first task of `queue_order` that may run now: a task with window "night" only when `night` is true; it returns that task object itself (not a copy) or None. Neither function modifies the list or the tasks. No comments and no docstrings.''',
     "hidden": {"hidden_flow_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `buildflow_core.py` once more: no rule may be copied into several places (the list of events of a state, the check of the numbers), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_flow_full.py": S3}},
]
