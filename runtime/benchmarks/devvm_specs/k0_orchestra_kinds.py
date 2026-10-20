"""Spec 0, K0.21 (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, design D3.2, KERN-01, gate G2-S0-12; Captain OP-1: the task of the board is type `issue`, `task` stays the mission):
`desk/orchestra_kinds.py`, the desk adapter of the orchestration package. It turns rows of `orchestra.db` (read through the facade `Orchestra` of K0.18) into desk objects
of the one form {type, id, title, state, summary, actions, links} for the types `agent` (replaces the placeholder), `issue`, `routine` and `budget`, and registers them only
when `hub.runtime.orchestra` exists; with the switch off the desk stays as it is. `actions` is left empty here: the registry sets it from the verbs (K0.8). The verbs of D3.2
(zuweisen, wecken, pausieren, ... with their gates) come in Spec 1 together with org and board; Spec 0 registers the types read-only. The registry is passed in by
`desk/extensions.py` (K0.9), so this module imports nothing of the desk. GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference
(benchmarks/devvm_refs/k0_orchestra_kinds). Stages cut to at most 20 new hidden checks each (Captain, line L3, 20.10.2026)."""

NOTES = '''# Notes for k0_orchestra_kinds
Python 3 standard library only, and nothing needs to be imported: the registry (with its class `registry.Kind`) and the hub are passed in; the orchestration facade is `hub.runtime.orchestra`.
Rows are plain dicts; a missing optional key counts like None. Texts are German and exactly as the task says (the middle dot is the character "·" with one space on each side).
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code (ONE helper builds the object dict, ONE helper builds the links).
'''

HEAD = r'''
import copy
from types import SimpleNamespace
from orchestra_kinds import IMPORTS

SHAPE = ["type", "id", "title", "state", "summary", "actions", "links"]
UA = {"id": "ua", "name": "Unterarbeiter", "role": "unterarbeiter", "reports_to": None, "status": "aktiv", "budget_tokens": 1000, "budget_eur_cent": 200}
COD = {"id": "cod", "name": "Coder", "role": "coder", "reports_to": "ua", "status": "pausiert", "budget_tokens": None, "budget_eur_cent": None}
T1 = {"id": "t1", "title": "Bauen", "state": "in_arbeit", "assignee": "cod", "parent_id": "t0", "mission_id": "m-7", "goal_ref": "v-1", "project_id": "p-2",
      "checkout_by": "cod", "priority": 1}
T2 = {"id": "t2", "title": "Prüfen", "state": "offen", "assignee": None, "parent_id": None, "mission_id": None, "goal_ref": None, "project_id": None, "checkout_by": None}
R1 = {"id": "r1", "agent_id": "ua", "title": "Morgens", "cron": "0 6 * * *", "timezone": "Europe/Berlin", "enabled": 1}
R2 = {"id": "r2", "agent_id": "cod", "title": "Nachts", "cron": "0 2 * * *", "timezone": "UTC", "enabled": 0}
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert TYPES == ("agent", "issue", "routine", "budget")
rows = [UA, COD, R1, R2]
keep = copy.deepcopy(rows)
a = agent_object(UA)
assert list(a) == SHAPE
assert a == {"type": "agent", "id": "ua", "title": "Unterarbeiter", "state": "aktiv", "summary": "unterarbeiter · direkt unter dem Captain", "actions": [], "links": []}
assert agent_object(COD) == {"type": "agent", "id": "cod", "title": "Coder", "state": "pausiert", "summary": "coder · unter ua", "actions": [], "links": [{"type": "agent", "id": "ua"}]}
assert agent_object({"id": "x", "name": "X", "role": "r", "status": "beendet"})["summary"] == "r · direkt unter dem Captain"
r = routine_object(R1)
assert list(r) == SHAPE
assert r == {"type": "routine", "id": "r1", "title": "Morgens", "state": "an", "summary": "0 6 * * * (Europe/Berlin)", "actions": [], "links": [{"type": "agent", "id": "ua"}]}
assert routine_object(R2)["state"] == "aus"
assert routine_object(R2)["summary"] == "0 2 * * * (UTC)"
assert routine_object({"id": "r3", "agent_id": "ua", "title": "X", "cron": "* * * * *", "enabled": 1})["summary"] == "* * * * * (Europe/Berlin)"
assert rows == keep
'''

C2 = r'''
rows = [T1, T2]
keep = copy.deepcopy(rows)
i = issue_object(T1)
assert list(i) == SHAPE
assert i["type"] == "issue"
assert i["title"] == "Bauen"
assert i["state"] == "in_arbeit"
assert i["summary"] == "zugewiesen an cod · ausgecheckt von cod"
assert i["actions"] == []
assert i["links"] == [{"type": "agent", "id": "cod"}, {"type": "issue", "id": "t0"}, {"type": "task", "id": "m-7"}, {"type": "intent", "id": "v-1"}, {"type": "project", "id": "p-2"}]
assert issue_object(T2) == {"type": "issue", "id": "t2", "title": "Prüfen", "state": "offen", "summary": "nicht zugewiesen", "actions": [], "links": []}
assert issue_object({"id": "t3", "title": "X", "state": "wartet", "mission_id": "m-1"})["links"] == [{"type": "task", "id": "m-1"}]
assert issue_object({"id": "t4", "title": "X", "state": "offen", "checkout_by": "planer"})["summary"] == "nicht zugewiesen · ausgecheckt von planer"
assert rows == keep
'''

C3 = r'''
keep = copy.deepcopy([UA, COD])
b = budget_object(UA, {"tokens": 100, "eur_cent": 20, "requests": 3})
assert list(b) == SHAPE
assert b == {"type": "budget", "id": "ua", "title": "Budget Unterarbeiter", "state": "im Rahmen", "summary": "Token 100/1000 · Cent 20/200", "actions": [], "links": [{"type": "agent", "id": "ua"}]}
assert budget_object(UA, {"tokens": 800, "eur_cent": 0, "requests": 1})["state"] == "Warnung"
assert budget_object(UA, {"tokens": 799, "eur_cent": 159, "requests": 1})["state"] == "im Rahmen"
assert budget_object(UA, {"tokens": 0, "eur_cent": 160, "requests": 1})["state"] == "Warnung"
assert budget_object(UA, {"tokens": 1000, "eur_cent": 0, "requests": 1})["state"] == "gestoppt"
assert budget_object(UA, {"tokens": 5, "eur_cent": 250, "requests": 1})["state"] == "gestoppt"
assert budget_object(UA, {"tokens": 500, "eur_cent": 0, "requests": 1}, warn_percent=50, stop_percent=90)["state"] == "Warnung"
assert budget_object(UA, {"tokens": 900, "eur_cent": 0, "requests": 1}, warn_percent=50, stop_percent=90)["state"] == "gestoppt"
assert budget_object(UA, {"tokens": 1500, "eur_cent": 0, "requests": 1}, stop_percent=200)["state"] == "Warnung"
c = budget_object(COD, {"tokens": 99999, "eur_cent": 5, "requests": 9})
assert c["state"] == "ohne Grenze"
assert c["summary"] == "keine Grenze gesetzt"
only_tokens = dict(COD, budget_tokens=10)
assert budget_object(only_tokens, {"tokens": 3, "eur_cent": 999, "requests": 1})["summary"] == "Token 3/10"
assert budget_object(only_tokens, {"tokens": 3, "eur_cent": 999, "requests": 1})["state"] == "im Rahmen"
only_cent = dict(COD, budget_eur_cent=50)
assert budget_object(only_cent, {"tokens": 3, "eur_cent": 45, "requests": 1})["summary"] == "Cent 45/50"
assert budget_object(dict(COD, budget_tokens=0), {"tokens": 3, "eur_cent": 0, "requests": 1})["state"] == "ohne Grenze"
assert [UA, COD] == keep
'''

SETUP = r'''
class Kind:
    def __init__(self, name, title, read, listing, verbs=(), type_verbs=(), source="desk", placeholder=False, own_actions=False):
        self.name, self.title, self.read, self.listing, self.verbs, self.source = name, title, read, listing, verbs, source


class Reg:
    Kind = Kind

    def __init__(self):
        self.kinds, self.calls = {}, []

    def register(self, kind, replace_placeholder=False):
        self.calls.append((kind.name, replace_placeholder))
        self.kinds[kind.name] = kind


class Orch:
    def __init__(self):
        self.config = SimpleNamespace(warn_percent=80, stop_percent=100)
        self.seen = []

    def agents(self):
        return [copy.deepcopy(COD), copy.deepcopy(UA)]

    def agent(self, oid):
        return copy.deepcopy({"ua": UA, "cod": COD}.get(oid))

    def issues(self, state=None, assignee=None):
        self.seen.append((state, assignee))
        return [copy.deepcopy(t) for t in (T1, T2) if state in (None, t["state"]) and assignee in (None, t["assignee"])]

    def issue(self, oid):
        return copy.deepcopy({"t1": T1, "t2": T2}.get(oid))

    def routines(self):
        return [copy.deepcopy(R1), copy.deepcopy(R2)]

    def routine(self, oid):
        return copy.deepcopy({"r1": R1, "r2": R2}.get(oid))

    def spent(self, oid):
        return {"ua": {"tokens": 900, "eur_cent": 0, "requests": 2}}.get(oid, {"tokens": 0, "eur_cent": 0, "requests": 0})


orch = Orch()
hub = SimpleNamespace(runtime=SimpleNamespace(orchestra=orch))
reg = Reg()
'''

C4 = SETUP + r'''
off = Reg()
assert register(off, SimpleNamespace(runtime=SimpleNamespace(orchestra=None))) == []
assert register(off, SimpleNamespace(runtime=SimpleNamespace())) == []
assert register(off, SimpleNamespace()) == []
assert off.calls == []
assert register(reg, hub) == ["agent", "issue", "routine", "budget"]
assert reg.calls == [("agent", True), ("issue", False), ("routine", False), ("budget", False)]
assert [reg.kinds[n].title for n in TYPES] == ["Agent", "Aufgabe", "Routine", "Budget"]
assert all(reg.kinds[n].source == "orchestra" for n in TYPES)
assert all(not reg.kinds[n].verbs for n in TYPES)
'''

C5 = SETUP + r'''
register(reg, hub)
K = reg.kinds
assert K["agent"].read(hub, "cod") == agent_object(COD)
assert K["agent"].read(hub, "zz") is None
assert [o["id"] for o in K["agent"].listing(hub, {})] == ["cod", "ua"]
assert K["issue"].read(hub, "t1") == issue_object(T1)
assert K["issue"].read(hub, "t9") is None
assert [o["id"] for o in K["issue"].listing(hub, {})] == ["t1", "t2"]
assert orch.seen[-1] == (None, None)
assert [o["id"] for o in K["issue"].listing(hub, {"type": "issue", "state": "offen"})] == ["t2"]
assert orch.seen[-1] == ("offen", None)
assert [o["id"] for o in K["issue"].listing(hub, {"assignee": "cod"})] == ["t1"]
assert orch.seen[-1] == (None, "cod")
assert K["routine"].read(hub, "r2") == routine_object(R2)
assert K["routine"].read(hub, "r9") is None
assert [o["state"] for o in K["routine"].listing(hub, {})] == ["an", "aus"]
'''

C6 = SETUP + r'''
register(reg, hub)
K = reg.kinds
assert K["budget"].read(hub, "ua") == budget_object(UA, {"tokens": 900, "eur_cent": 0, "requests": 2})
assert K["budget"].read(hub, "ua")["state"] == "Warnung"
assert K["budget"].read(hub, "zz") is None
assert [(o["id"], o["state"]) for o in K["budget"].listing(hub, {})] == [("cod", "ohne Grenze"), ("ua", "Warnung")]
orch.config.warn_percent, orch.config.stop_percent = 50, 90
assert K["budget"].read(hub, "ua")["state"] == "gestoppt"
other = Orch()
other.spent = lambda oid: {"tokens": 1, "eur_cent": 0, "requests": 1}
hub2 = SimpleNamespace(runtime=SimpleNamespace(orchestra=other))
assert K["budget"].read(hub2, "ua")["summary"] == "Token 1/1000 · Cent 0/200"
'''

ALL = "TYPES, agent_object, issue_object, routine_object, budget_object, register"
H1 = {"hidden_okinds_1.py": hidden("TYPES, agent_object, routine_object", C1)}
H2 = {**H1, "hidden_okinds_2.py": hidden("issue_object", C2)}
H3 = {**H2, "hidden_okinds_3.py": hidden("budget_object", C3)}
H4 = {**H3, "hidden_okinds_4.py": hidden(ALL, C4)}
H5 = {**H4, "hidden_okinds_5.py": hidden(ALL, C5)}
H6 = {**H5, "hidden_okinds_6.py": hidden(ALL, C6)}

COMMON_RULE = """Every object is a NEW dict with exactly the keys type, id, title, state, summary, actions, links in this order; actions is always []; links is a list of {"type": t, "id": i} only for values that are set (not None, not empty), in the order given. A missing optional key counts like None. Never change the rows."""

STAGES = [
    {"name": "agent",
     "task": """Create `orchestra_kinds.py` (Python 3, nothing to import) with `TYPES = ("agent", "issue", "routine", "budget")` and two functions that turn a row dict into a desk object. """ + COMMON_RULE + """
- `agent_object(row)`: type "agent", id row["id"], title row["name"], state row["status"], summary row["role"] + " · " + ("unter " + reports_to when reports_to is set, else "direkt unter dem Captain"); links: agent reports_to.
- `routine_object(row)`: type "routine", id, title, state "an" when row["enabled"] is truthy else "aus", summary cron + " (" + timezone + ")" with timezone "Europe/Berlin" when missing; links: agent agent_id.""",
     "hidden": H1},
    {"name": "issue",
     "task": """Add `issue_object(row)` to `orchestra_kinds.py` (keep everything else). """ + COMMON_RULE + """
- type "issue", id, title row["title"], state row["state"], summary "zugewiesen an <assignee>" or "nicht zugewiesen", followed by " · ausgecheckt von <checkout_by>" when checkout_by is set.
- links in this order: agent assignee, issue parent_id, task mission_id, intent goal_ref, project project_id.""",
     "hidden": H2},
    {"name": "budget",
     "task": """Add `budget_object(agent, spent, warn_percent=80, stop_percent=100)` to `orchestra_kinds.py` (keep everything else). """ + COMMON_RULE + """
- spent is {"tokens", "eur_cent", "requests"}. type "budget", id agent["id"], title "Budget " + agent["name"], links: agent agent["id"].
- A limit counts only when it is set and not 0: budget_tokens (label "Token", used spent["tokens"]) and budget_eur_cent (label "Cent", used spent["eur_cent"]), in this order.
- No limit: state "ohne Grenze", summary "keine Grenze gesetzt".
- Otherwise summary is the parts "<label> <used>/<limit>" joined with " · ", and with the highest used*100/limit of the limits: >= stop_percent -> "gestoppt", >= warn_percent -> "Warnung", else "im Rahmen".""",
     "hidden": H3},
    {"name": "register",
     "task": """Add `register(registry, hub)` to `orchestra_kinds.py` (keep everything else). The orchestration facade is `hub.runtime.orchestra`; a hub without `runtime`, a runtime without `orchestra` or orchestra None -> return [] and register nothing.
Otherwise build four kinds with `registry.Kind(name, title, read, listing, source="orchestra")` (no verbs) and register them in the order of TYPES: `registry.register(kind, replace_placeholder=True)` for "agent" (it replaces the placeholder), `registry.register(kind, replace_placeholder=False)` for the others. Titles: agent "Agent", issue "Aufgabe", routine "Routine", budget "Budget". Return list(TYPES).
In this stage read and listing may still be simple placeholders; the next stage fills them.""",
     "hidden": H4},
    {"name": "readers",
     "task": """Fill the read and listing functions of the kinds "agent", "issue" and "routine" in `orchestra_kinds.py` (keep everything else). read(hub, oid) and listing(hub, payload) take the facade from the hub they get at CALL time (hub.runtime.orchestra), not from the hub of register. read returns None when the facade returns None.
- agent: read orch.agent(oid) -> agent_object; listing orch.agents() -> agent_object for each.
- issue: read orch.issue(oid) -> issue_object; listing orch.issues(state=payload.get("state"), assignee=payload.get("assignee")) -> issue_object for each.
- routine: read orch.routine(oid); listing orch.routines(); -> routine_object.
ONE helper makes a read function and ONE helper makes a listing function.""",
     "hidden": H5},
    {"name": "budget_kind",
     "task": """Fill the kind "budget" in `orchestra_kinds.py` (keep everything else; id = agent id), with the same read and listing helpers: read orch.agent(oid) (None stays None); listing orch.agents(); each agent -> budget_object(agent, orch.spent(agent["id"]), orch.config.warn_percent, orch.config.stop_percent), with orch taken from the hub at CALL time.""",
     "hidden": H6},
]
