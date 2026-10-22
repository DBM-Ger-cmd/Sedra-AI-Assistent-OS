"""Spec 1, Bau-Spec s1_decompose (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `decompose.py`, D1.5, ORC-17, ORC-18; gates G2-S1-16, G2-S1-17, G2-S1-22):
`orchestra/decompose.py`, the pure check of the foreman's decomposition and the report table. The model answers only in the JSON schema `SCHEMA`; `check` accepts the
answer all or nothing (one bad entry and no subtask is created, the reason goes as a system comment to the parent task), maps every role to an active subordinate
without the right to delegate (so a subtask is never decomposed again) and refuses blocker indexes and cycles. `report` builds the table of the report from the
database rows, never from the model: a child without check_result is 'nicht_geprueft', whatever the model says. runner.py imports it (seed of s1_runner).
`check` takes an optional fourth argument `roles` (all roles of the organisation) to tell an unknown role from a role that is no subordinate; D1.1 names the first three.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_decompose)."""

NOTES = '''# Notes for s1_decompose
Python 3 standard library only, and nothing needs to be imported: no sqlite3, no files, no clock, no network, no JSON-schema library (the checks are written by hand).
Every function is pure and never modifies its arguments. Every refusal is ValueError('decompose_invalid:<reason>') with exactly the reason the task names.
No comments and no docstrings, small private helpers instead of copied code (one helper checks one entry, one finds a cycle without recursion).
'''

HEAD = r'''
import copy
from decompose import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def item(titel="Teil", rolle="coder", blocker=None, **kw):
    out = {"titel": titel, "beschreibung": "b", "rolle": rolle, "blocker": blocker or [], "akzeptanz": "a"}
    out.update(kw)
    return out


def ans(*items, **kw):
    out = {"teilaufgaben": list(items), "rueckfrage": None}
    out.update(kw)
    return out


SUBS = [{"id": "C2", "role": "coder", "status": "aktiv", "open_tasks": 1, "can_delegate": 0},
        {"id": "C1", "role": "coder", "status": "aktiv", "open_tasks": 1, "can_delegate": 0},
        {"id": "C0", "role": "coder", "status": "aktiv", "open_tasks": 3, "can_delegate": 0},
        {"id": "P1", "role": "planner", "status": "aktiv", "open_tasks": 0, "can_delegate": 0},
        {"id": "R1", "role": "reviewer", "status": "pausiert", "open_tasks": 0, "can_delegate": 0},
        {"id": "F2", "role": "foreman", "status": "aktiv", "open_tasks": 0, "can_delegate": 1}]
BAD = "decompose_invalid:"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert SCHEMA["type"] == "object"
assert SCHEMA["additionalProperties"] is False
assert sorted(SCHEMA["properties"]) == ["rueckfrage", "teilaufgaben"]
entry = SCHEMA["properties"]["teilaufgaben"]["items"]
assert sorted(entry["properties"]) == ["akzeptanz", "beschreibung", "blocker", "rolle", "titel"]
assert entry["additionalProperties"] is False
a = ans(item("Eins"), item("Zwei", "planner", [0]))
keep = copy.deepcopy(a)
out = check(a, SUBS, 8)
assert [o["titel"] for o in out] == ["Eins", "Zwei"]
assert [(o["rolle"], o["blocker"], o["beschreibung"], o["akzeptanz"]) for o in out] == [("coder", [], "b", "a"), ("planner", [0], "b", "a")]
assert a == keep
assert len(check(ans(*[item(f"T{i}") for i in range(8)]), SUBS, 8)) == 8
raises(BAD + "too_many", check, ans(*[item(f"T{i}") for i in range(9)]), SUBS, 8)
raises(BAD + "too_many", check, ans(item(), item()), SUBS, 1)
for answer in ({"teilaufgaben": [item()], "rueckfrage": None, "notiz": "x"}, {"aufgaben": []}, None, [item()], "text"):
    raises(BAD + "extra_key", check, answer, SUBS, 8)
for answer in (ans(), {"rueckfrage": "Was genau?"}, {"teilaufgaben": None, "rueckfrage": None}, {"teilaufgaben": "x", "rueckfrage": None}):
    raises(BAD + "empty", check, answer, SUBS, 8)
assert check({"teilaufgaben": [item()]}, SUBS, 8)[0]["titel"] == "Teil"
'''

C2 = r'''
raises(BAD + "extra_key", check, ans(item(), item(befehl="zuweisen")), SUBS, 8)
raises(BAD + "extra_key", check, ans("nur Text"), SUBS, 8)
for title in ("", "   ", None, 7):
    raises(BAD + "title_empty", check, ans(item(title)), SUBS, 8)
raises(BAD + "title_empty", check, ans({"rolle": "coder"}), SUBS, 8)
assert check(ans(item("x" * 200)), SUBS, 8)[0]["titel"] == "x" * 200
assert check(ans(item("  Mit Rand  ")), SUBS, 8)[0]["titel"] == "Mit Rand"
raises(BAD + "title_too_long", check, ans(item("x" * 201)), SUBS, 8)
raises(BAD + "text_too_long", check, ans(item(beschreibung="y" * 4001)), SUBS, 8)
raises(BAD + "text_too_long", check, ans(item(akzeptanz="y" * 4001)), SUBS, 8)
assert check(ans(item(beschreibung="y" * 4000, akzeptanz=None)), SUBS, 8)[0]["akzeptanz"] == ""
for blocker in ([2], [-1], ["0"], [True], [0.0], "0"):
    raises(BAD + "blocker_index", check, ans(item(), item(blocker=blocker)), SUBS, 8)
raises(BAD + "blocker_cycle", check, ans(item(blocker=[1]), item(blocker=[0])), SUBS, 8)
raises(BAD + "blocker_cycle", check, ans(item(blocker=[0])), SUBS, 8)
raises(BAD + "blocker_cycle", check, ans(item(), item(blocker=[2]), item(blocker=[3]), item(blocker=[1])), SUBS, 8)
assert [o["blocker"] for o in check(ans(item(), item(blocker=[0]), item(blocker=[0, 1])), SUBS, 8)] == [[], [0], [0, 1]]
raises(BAD + "title_empty", check, ans(item(blocker=[1]), item(""), item(blocker=[0])), SUBS, 8)
raises(BAD + "too_many", check, ans(item(""), item()), SUBS, 1)
'''

C3 = r'''
out = check(ans(item(), item(rolle="planner"), item()), SUBS, 8)
assert [o["agent_id"] for o in out] == ["C1", "P1", "C1"]
subs = [dict(s, open_tasks=0) if s["id"] == "C0" else s for s in SUBS]
assert check(ans(item()), subs, 8)[0]["agent_id"] == "C0"
assert check(ans(item()), [s for s in SUBS if s["id"] != "C1"], 8)[0]["agent_id"] == "C2"
assert check(ans(item()), [{"id": "C9", "role": "coder", "status": "aktiv"}], 8)[0]["agent_id"] == "C9"
for role in ("tester", "", None, "Coder"):
    raises(BAD + "role_unknown", check, ans(item(rolle=role)), SUBS, 8)
raises(BAD + "role_unknown", check, ans(item(rolle="tester")), SUBS, 8, ["coder"])
raises(BAD + "role_not_subordinate", check, ans(item(rolle="tester")), SUBS, 8, ["coder", "tester"])
raises(BAD + "role_not_subordinate", check, ans(item(rolle="reviewer")), SUBS, 8)
raises(BAD + "role_not_subordinate", check, ans(item(rolle="foreman")), SUBS, 8)
raises(BAD + "role_not_subordinate", check, ans(item(), item(rolle="reviewer")), SUBS, 8, ["reviewer"])
raises(BAD + "role_unknown", check, ans(item(), item(rolle="tester")), [], 8)
raises(BAD + "title_too_long", check, ans(item("x" * 201, rolle="tester")), SUBS, 8)
keep = copy.deepcopy(SUBS)
check(ans(item(), item(rolle="planner")), SUBS, 8)
assert SUBS == keep
'''

C4 = r'''
def child(id, state, result=None, created="2026-10-21T08:00:00Z", title=None):
    return {"id": id, "title": title or "Titel " + id, "state": state, "check_result": result, "created_at": created, "parent_id": "R"}
root = {"id": "R", "title": "Wurzel", "state": "wartet"}
kids = [child("T2", "erledigt", "gruen", "2026-10-21T08:00:02Z"), child("T1", "erledigt", None, "2026-10-21T08:00:01Z", "alle Tests bestanden"),
        child("T3", "abgebrochen", "rot", "2026-10-21T08:00:02Z"), child("T4", "erledigt", "nicht_geprueft", "2026-10-21T08:00:03Z")]
keep = copy.deepcopy(kids)
r = report(root, kids)
assert sorted(r) == ["offen", "vollstaendig", "zeilen"]
assert [z["issue_id"] for z in r["zeilen"]] == ["T1", "T2", "T3", "T4"]
assert r["zeilen"][0] == {"issue_id": "T1", "titel": "alle Tests bestanden", "zustand": "erledigt", "pruefung": "nicht_geprueft"}
assert [z["pruefung"] for z in r["zeilen"]] == ["nicht_geprueft", "gruen", "rot", "nicht_geprueft"]
assert [z["zustand"] for z in r["zeilen"]] == ["erledigt", "erledigt", "abgebrochen", "erledigt"]
assert r["offen"] == ["T1", "T3", "T4"]
assert r["vollstaendig"] is True
assert kids == keep
half = report(root, kids + [child("T5", "in_arbeit", "gruen", "2026-10-21T08:00:04Z")])
assert half["vollstaendig"] is False
assert half["offen"] == ["T1", "T3", "T4", "T5"]
green = report(root, [child("T1", "erledigt", "gruen")])
assert (green["offen"], green["vollstaendig"]) == ([], True)
assert report(root, []) == {"zeilen": [], "offen": [], "vollstaendig": False}
assert report(root, [child("T1", "erledigt", "")])["zeilen"][0]["pruefung"] == "nicht_geprueft"
'''

H1 = {"hidden_decompose_1.py": hidden("SCHEMA, check", C1)}
H2 = {**H1, "hidden_decompose_2.py": hidden("check", C2)}
H3 = {**H2, "hidden_decompose_3.py": hidden("check", C3)}
H4 = {**H3, "hidden_decompose_4.py": hidden("report", C4)}

ANSWER = """The answer of the model is a dict {"teilaufgaben": [entry, ...], "rueckfrage": text or None}; an entry is {"titel", "beschreibung", "rolle", "blocker": [int], "akzeptanz"} (blocker = indexes of other entries of the same list that must be done first)."""

STAGES = [
    {"name": "schema",
     "task": f"""Create `decompose.py` (Python 3, nothing to import) with:
- `SCHEMA`: the JSON schema (a dict) of the answer, for models.structured. {ANSWER} SCHEMA is {{"type": "object", "additionalProperties": False, "required": [...], "properties": {{"teilaufgaben": {{"type": "array", "items": {{"type": "object", "additionalProperties": False, "required": [the five keys], "properties": {{one entry per key}}}}}}, "rueckfrage": {{...}}}}}}; titel, beschreibung, rolle, akzeptanz are strings, blocker an array of integers, rueckfrage a string or null.
- `check(answer, subordinates, max_subtasks, roles=None)` -> list of subtasks, or ValueError('decompose_invalid:<reason>'). This stage checks the answer as a whole, in this order: answer is not a dict, or has a key other than 'teilaufgaben'/'rueckfrage' -> 'extra_key'; 'teilaufgaben' missing, not a list or empty -> 'empty'; more than max_subtasks entries -> 'too_many'.
  Result: one dict per entry, in order, with the keys titel, beschreibung, rolle, blocker (a new list), akzeptanz; a missing or None beschreibung/akzeptanz/blocker becomes '' / '' / []. (subordinates and roles are used in a later stage.) Never modify the arguments.""",
     "hidden": H1},
    {"name": "rules",
     "task": """Extend `check` in `decompose.py` (keep everything else): all or nothing – one bad entry and the whole answer is refused. After the checks of the whole answer, each entry in order, checks in this order:
- not a dict, or a key that is not one of the five -> 'extra_key';
- titel not a string, or empty after strip() -> 'title_empty'; longer than 200 characters after strip() -> 'title_too_long'; the result holds the stripped titel;
- beschreibung or akzeptanz longer than 4000 characters -> 'text_too_long';
- blocker not a list, or an element that is not an int (`type(x) is int`, so True and 0.0 are wrong) or not in 0 .. number of entries - 1 -> 'blocker_index'.
After all entries: the blocker indexes form a cycle (an entry blocking itself counts) -> 'blocker_cycle' (without recursion).""",
     "hidden": H2},
    {"name": "assign",
     "task": """Extend `check` in `decompose.py` (keep everything else). subordinates are the foreman's subordinates, rows {id, role, status, open_tasks, can_delegate} (missing open_tasks = 0, missing can_delegate = 0); roles (optional) are all roles of the organisation.
In the check of each entry, after 'blocker_index': the known roles are the given roles plus the roles of all subordinates; rolle not among them -> 'role_unknown'. Otherwise the candidates are the subordinates with that role, status 'aktiv' and can_delegate falsy (a subtask never goes to an agent that could decompose again); none -> 'role_not_subordinate'.
Each subtask in the result gets 'agent_id': the candidate with the fewest open_tasks, then the smallest id. The blocker cycle is still checked after all entries.""",
     "hidden": H3},
    {"name": "report",
     "task": """Add `report(root, children)` -> {"zeilen", "offen", "vollstaendig"} to `decompose.py` (keep everything else): the table of the report of a root task, built from the database rows, never from the model.
children are task rows {id, title, state, check_result, created_at}. zeilen: one {"issue_id", "titel", "zustand", "pruefung"} per child, ordered by created_at, then id; titel = title, zustand = state, pruefung = check_result, but a missing, None or empty check_result is 'nicht_geprueft' (never green).
offen: the ids (same order) of children that are not closed (state 'erledigt' or 'abgebrochen') or whose pruefung is not 'gruen'. vollstaendig: True when there is at least one child and every child is closed.""",
     "hidden": H4},
]
