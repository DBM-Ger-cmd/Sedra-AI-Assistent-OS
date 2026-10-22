"""Spec 2, Bau-Spec s2_slotplan (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D2.2 `slotplan.py`, D2.3, D2.10, SCH-02, SCH-04, SCH-06, SCH-07; gates G2-S2-02, G2-S2-14):
`jobs/slotplan.py`, the pure rules of the model scheduler: the effective priority of a waiting run (aging), the order of the waiting runs, which of them get a slot now, why a run
has to wait (the reason shown in the queue), and when the scheduler proposes the cloud stage. slot_store.py imports it (seed of s2_slot_store). Times are UTC texts
"YYYY-MM-DDTHH:MM:SSZ"; there is no clock in the module. GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s2_slotplan)."""

NOTES = '''# Notes for s2_slotplan
Python 3 standard library only (datetime); no sqlite3, no files, no clock (never datetime.now), no network. Times are texts in the form 2026-10-21T08:00:00Z (UTC).
Every function is pure and never modifies its arguments. Every refusal is a ValueError with exactly the code the task names.
No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import copy
from slotplan import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def at(s):
    return "2026-10-21T08:%02d:%02dZ" % divmod(s, 60)


def r(run_id, priority, enq=0):
    return {"run_id": run_id, "priority": priority, "enqueued": at(enq)}


CFG = {"age_after_s": 60, "age_cap": 5, "swap": "none", "queue_max": 3, "wait_max_s": 300}
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
row = r("a", 3)
keep = copy.deepcopy(row)
assert effective_priority(row, at(0), CFG) == 3
assert effective_priority(row, at(59), CFG) == 3
assert effective_priority(row, at(60), CFG) == 4
assert effective_priority(row, at(125), CFG) == 5
assert effective_priority(row, at(3000), CFG) == 5
assert row == keep
assert effective_priority(r("b", 5), at(3000), CFG) == 5
assert effective_priority(r("c", 7), at(3000), CFG) == 7
assert effective_priority(r("d", 4), at(120), CFG) == 5
assert effective_priority(r("e", 0, 100), at(160), CFG) == 1
assert effective_priority(r("f", 3, 100), at(0), CFG) == 3
assert effective_priority(r("g", 3), at(3000), dict(CFG, age_cap=0)) == 3
assert effective_priority(r("h", 3), at(120), dict(CFG, age_cap=9)) == 5
for bad in (10, -1, "3", None, True):
    raises("priority_invalid", effective_priority, r("x", bad), at(0), CFG)
raises("priority_invalid", effective_priority, {"run_id": "x", "enqueued": at(0)}, at(0), CFG)
raises("age_after_s_invalid", effective_priority, row, at(0), dict(CFG, age_after_s=0))
raises("age_cap_invalid", effective_priority, row, at(0), {"age_after_s": 60})
raises("time_invalid", effective_priority, dict(row, enqueued="gestern"), at(0), CFG)
'''

C2 = r'''
rows = [r("r1", 3, 0), r("a1", 5, 30), r("c1", 7, 50), r("a0", 5, 10), r("a2", 5, 30)]
keep = copy.deepcopy(rows)
out = order(rows, at(50), CFG)
assert [x["run_id"] for x in out] == ["c1", "a0", "a1", "a2", "r1"]
assert rows == keep
assert out[0] is rows[2]
assert order([], at(0), CFG) == []
aged = [r("r1", 3, 0), r("a1", 5, 100)]
assert [x["run_id"] for x in order(aged, at(50), CFG)] == ["a1", "r1"]
assert [x["run_id"] for x in order(aged, at(130), CFG)] == ["r1", "a1"]
assert [x["run_id"] for x in order([r("b", 3, 5), r("a", 3, 5)], at(5), CFG)] == ["a", "b"]
assert [x["run_id"] for x in order([r("late", 7, 40), r("early", 7, 10)], at(60), CFG)] == ["early", "late"]
assert [x["run_id"] for x in order([r("old", 1, 0), r("new", 2, 0)], at(0), CFG)] == ["new", "old"]
raises("priority_invalid", order, [r("x", 99)], at(0), CFG)
raises("age_after_s_invalid", order, [r("x", 3)], at(0), dict(CFG, age_after_s="60"))
'''

C3 = r'''
ready = {"state": "bereit", "slots": 2, "recipe": "R1"}
w = [r("lo", 3, 0), r("hi", 7, 20), r("mid", 5, 10)]
keep = copy.deepcopy(w)
assert admit(ready, [], w, "normal", at(30), CFG) == ["hi", "mid"]
assert w == keep
assert admit(ready, [r("on", 5)], w, "normal", at(30), CFG) == ["hi"]
assert admit(ready, [r("on", 5), r("on2", 5)], w, "normal", at(30), CFG) == []
assert admit(ready, [r("on", 5), r("on2", 5), r("on3", 5)], w, "normal", at(30), CFG) == []
assert admit(dict(ready, slots=4), [], w, "normal", at(30), CFG) == ["hi", "mid", "lo"]
assert admit(ready, [], [], "normal", at(30), CFG) == []
for mode in ("drain", "exklusiv"):
    assert admit(ready, [], w, mode, at(30), CFG) == []
assert admit({"state": "aus"}, [], w, "normal", at(30), CFG) == ["hi"]
assert admit({"state": "aus"}, [r("starter", 5)], w, "normal", at(30), CFG) == []
for state in ("startet", "gesperrt", "drain", "exklusiv"):
    assert admit({"state": state, "slots": 2}, [], w, "normal", at(30), CFG) == [], state
raises("mode_invalid", admit, ready, [], w, "pause", at(30), CFG)
raises("mode_invalid", admit, {"state": "startet"}, [], w, None, at(30), CFG)
raises("server_state_invalid", admit, {"state": "an"}, [], w, "normal", at(30), CFG)
for slots in (0, 9, None, "2"):
    raises("slots_invalid", admit, {"state": "bereit", "slots": slots}, [], w, "normal", at(30), CFG)
'''

C4 = r'''
ready = {"state": "bereit", "slots": 2, "recipe": "R1"}
assert decide_reason(ready, "R1", "normal", [], CFG) is None
assert decide_reason(ready, "R1", "normal", [r("a", 5), r("b", 5)], CFG) == "kein_slot"
assert decide_reason(ready, "R2", "normal", [], CFG) == "model_swap_not_allowed"
assert decide_reason(ready, "R2", "normal", [], dict(CFG, swap="idle")) is None
assert decide_reason(ready, "R2", "normal", [r("a", 5)], dict(CFG, swap="idle")) == "model_swap_not_allowed"
assert decide_reason(ready, "R2", "normal", [], dict(CFG, swap={"fallback": "R1"})) is None
assert decide_reason({"state": "gesperrt"}, "R1", "normal", [], CFG) == "gesperrt"
assert decide_reason(ready, "R1", "exklusiv", [], dict(CFG)) == "exklusiv:?"
assert decide_reason(dict(ready, owner="nacht"), "R1", "exklusiv", [], CFG) == "exklusiv:nacht"
assert decide_reason(dict(ready, state="exklusiv", owner="nacht"), "R1", "normal", [], CFG) == "exklusiv:nacht"
assert decide_reason(ready, "R1", "drain", [], CFG) == "drain"
assert decide_reason(dict(ready, state="drain"), "R1", "normal", [], CFG) == "drain"
assert decide_reason({"state": "startet"}, "R1", "normal", [], CFG) == "server_startet"
assert decide_reason({"state": "aus"}, "R1", "normal", [], CFG) is None
assert decide_reason({"state": "aus"}, "R1", "normal", [r("starter", 5)], CFG) == "server_startet"
raises("mode_invalid", decide_reason, ready, "R1", "x", [], CFG)
raises("server_state_invalid", decide_reason, {"state": None}, "R1", "normal", [], CFG)
raises("slots_invalid", decide_reason, {"state": "bereit", "slots": 0, "recipe": "R1"}, "R1", "normal", [], CFG)
'''

C5 = r'''
w = [r("a", 3, 0), r("b", 5, 10), r("c", 7, 20)]
keep = copy.deepcopy(w)
assert needs_cloud_offer([], at(500), CFG) is None
assert needs_cloud_offer(w, at(100), CFG) is None
assert needs_cloud_offer(w, at(300), CFG) is None
assert needs_cloud_offer(w, at(301), CFG) == {"run_id": "a", "grund": "wartezeit"}
assert needs_cloud_offer(w, at(3000), dict(CFG, wait_max_s=3500)) is None
assert needs_cloud_offer(w + [r("d", 5, 30)], at(40), CFG) == {"run_id": "a", "grund": "schlange"}
assert needs_cloud_offer(w + [r("d", 5, 30)], at(3000), CFG) == {"run_id": "a", "grund": "schlange"}
assert needs_cloud_offer([r("z", 5, 50), r("y", 5, 50)], at(400), CFG) == {"run_id": "y", "grund": "wartezeit"}
assert needs_cloud_offer(w, at(40), dict(CFG, queue_max=3)) is None
assert needs_cloud_offer(w, at(40), dict(CFG, queue_max=3, wait_max_s=0)) == {"run_id": "a", "grund": "wartezeit"}
assert needs_cloud_offer(w, at(40), dict(CFG, queue_max=0)) == {"run_id": "a", "grund": "schlange"}
assert w == keep
raises("queue_max_invalid", needs_cloud_offer, w, at(40), {"wait_max_s": 300})
raises("wait_max_s_invalid", needs_cloud_offer, w, at(40), dict(CFG, wait_max_s=-1))
raises("time_invalid", needs_cloud_offer, w, "heute", CFG)
'''

H1 = {"hidden_slotplan_1.py": hidden("effective_priority", C1)}
H2 = {**H1, "hidden_slotplan_2.py": hidden("order", C2)}
H3 = {**H2, "hidden_slotplan_3.py": hidden("admit", C3)}
H4 = {**H3, "hidden_slotplan_4.py": hidden("decide_reason", C4)}
H5 = {**H4, "hidden_slotplan_5.py": hidden("needs_cloud_offer", C5)}

STAGES = [
    {"name": "priority",
     "task": """Create `slotplan.py` (Python 3 standard library only) with `effective_priority(row, now, cfg)` -> int, the priority of a waiting run after aging.
row is a dict with priority (int 0..9), enqueued (UTC text like '2026-10-21T08:00:00Z', parse it with the format '%Y-%m-%dT%H:%M:%SZ'; no clock) and run_id; now is a UTC text; cfg is a dict with age_after_s (int >= 1) and age_cap (int >= 0).
Rule: waited = whole seconds from enqueued to now (never negative). A row whose priority is already >= age_cap is returned unchanged (no aging). Otherwise the result is min(age_cap, priority + waited // age_after_s).
Checks in this order, each a ValueError: priority not an int (a bool counts as not an int) or outside 0..9 or missing -> 'priority_invalid'; cfg.age_after_s missing, not an int or < 1 -> 'age_after_s_invalid'; cfg.age_cap missing, not an int or < 0 -> 'age_cap_invalid'; enqueued or now not a valid time text -> 'time_invalid'.
Never modify the arguments.""",
     "hidden": H1},
    {"name": "order",
     "task": """Add `order(rows, now, cfg)` -> a NEW list of the same row dicts (the same objects) to `slotplan.py` (keep everything else), sorted by (higher effective_priority first, then smaller enqueued text, then smaller run_id). Errors come from effective_priority. An empty list gives an empty list. Never modify the arguments.""",
     "hidden": H2},
    {"name": "admit",
     "task": """Add `admit(server, active, waiting, mode, now, cfg)` -> list of run_ids that get a slot now, in the order of `order(waiting, ...)`, to `slotplan.py` (keep everything else).
server is a dict with state ('aus', 'startet', 'bereit', 'drain', 'exklusiv' or 'gesperrt'), slots (int, only needed when state is 'bereit') and recipe; active and waiting are lists of rows like those of `order`; mode is 'normal', 'drain' or 'exklusiv'.
Checks first: mode not one of the three -> ValueError('mode_invalid'); server state not one of the six -> ValueError('server_state_invalid').
Then: mode other than 'normal', or a state other than 'aus'/'bereit' -> []. State 'aus': if nothing is active, only the first of the ordered waiting runs (the one that starts the server), else []. State 'bereit' (mode 'normal'): slots must be an int 1..8 (else ValueError('slots_invalid')); the first max(0, slots - len(active)) runs of the ordered waiting list.""",
     "hidden": H3},
    {"name": "reason",
     "task": """Add `decide_reason(server, wanted_recipe, mode, active, cfg)` -> None or a reason text to `slotplan.py` (keep everything else): why a run cannot start now. Same server/mode/active/cfg shapes as `admit`; cfg may carry swap ('none' by default, 'idle', or a dict with 'fallback' = a recipe name); server may carry owner.
Same input checks as `admit` (mode_invalid, server_state_invalid). Then in this order: state 'gesperrt' -> 'gesperrt'; mode 'exklusiv' or state 'exklusiv' -> 'exklusiv:' + owner (the text '?' when owner is missing or empty); mode 'drain' or state 'drain' -> 'drain'; state 'startet' -> 'server_startet'; state 'aus' -> 'server_startet' when something is active, else None.
State 'bereit': when wanted_recipe is truthy and differs from server.recipe, the swap must be allowed, else 'model_swap_not_allowed'; allowed means swap == 'idle' and nothing is active, or swap is a dict whose 'fallback' equals server.recipe ('none' never allows). Then slots must be an int 1..8 (else ValueError('slots_invalid')); len(active) >= slots -> 'kein_slot'; otherwise None.""",
     "hidden": H4},
    {"name": "offer",
     "task": """Add `needs_cloud_offer(waiting, now, cfg)` -> None or {"run_id": ..., "grund": 'schlange' or 'wartezeit'} to `slotplan.py` (keep everything else). waiting is a list of rows (run_id, enqueued, priority); cfg carries queue_max (int >= 0) and wait_max_s (int >= 0).
No waiting rows -> None (no checks). Otherwise check cfg: queue_max missing/not an int/negative -> ValueError('queue_max_invalid'), then wait_max_s -> ValueError('wait_max_s_invalid'). The oldest row is the one with the smallest enqueued text, then the smaller run_id; its run_id is returned. More rows than queue_max -> grund 'schlange'; else when the oldest has waited more than wait_max_s whole seconds -> grund 'wartezeit'; else None. An invalid time text -> ValueError('time_invalid'). Never modify the arguments.""",
     "hidden": H5},
]
