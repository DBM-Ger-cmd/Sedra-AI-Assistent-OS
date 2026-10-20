"""Spec 0, K0.8 (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, design D1 and D2, gate G2-S0-01 and G2-S0-04): the desk registration `desk/kinds.py`. Object types and their verbs
are registered once at start instead of standing in if-elif chains of `uix_server.py`; `view`, `listing` and `request` give every object in the one form
{type, id, title, state, summary, actions, links} and set `actions` from the verbs of its type. `client_for` derives the audit field `client` from the token class (the server
sets it, never the caller). Pure logic: readers, verbs and the not-found object are injected, nothing of the desk is imported. The verb objects are the existing
`desk.actions.Verb` (attributes `verb`, methods `offered(obj)` and `describe()`); the tests use a small copy. GUPPI/SEDRA builds it; Claude only wrote this file, the hidden
tests and the reference (benchmarks/devvm_refs/k0_kinds). The integration (builtin kinds, uix_server.py, actions.table) is harness work (K0.10, K0.11)."""

NOTES = '''# Notes for k0_kinds
Pure Python 3 standard library (re), no file, process or network access, nothing of the desk is imported. Readers, listings, verbs and the not-found builder are passed in by the caller.
A verb object has the attribute `verb` (its name) and the methods `offered(obj) -> bool` and `describe() -> dict`; never call its `run`.
No comments and no docstrings, never modify the arguments except the object dicts that `view` and `listing` return (their "actions" key is set), small private helpers instead of copied code.
'''

HEAD = r'''
import copy
from kinds import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


class V:
    def __init__(self, verb, when=None):
        self.verb = verb
        self.when = when or (lambda o: True)
        self.runs = 0

    def offered(self, obj):
        return bool(self.when(obj))

    def describe(self):
        return {"verb": self.verb, "label": self.verb.upper(), "needs_gate": False, "confirm": None}

    def run(self, hub, oid, args):
        self.runs += 1


def obj(kind, oid, state="bereit", **extra):
    out = {"type": kind, "id": oid, "title": "T " + oid, "state": state, "summary": "S", "actions": ["alt"], "links": []}
    out.update(extra)
    return out
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
r = Registry()
assert r.names() == []
assert r.get("task") is None
assert r.problems == []
assert r.frozen is False
assert Registry.Kind is Kind
k = Kind("task", "Aufgabe", None, None, verbs=[V("a")], type_verbs=[V("neu")])
assert k.name == "task"
assert k.title == "Aufgabe"
assert k.source == "desk"
assert k.placeholder is False
assert k.own_actions is False
assert isinstance(k.verbs, tuple)
assert isinstance(k.type_verbs, tuple)
assert k.verb("a").verb == "a"
assert k.verb("neu") is None
assert k.type_verb("neu").verb == "neu"
assert k.type_verb("a") is None
assert Kind("x1", "X", None, None).verbs == ()
r.register(k)
r.register(Kind("model", "Modell", None, None))
assert r.names() == ["model", "task"]
assert r.get("task") is k
raises("kind_already_registered", r.register, Kind("task", "Neu", None, None))
assert r.get("task") is k
for bad in ("Task", "t", "1task", "task-x", "a" * 33, "", "tä"):
    raises("kind_name_invalid", r.register, Kind(bad, "B", None, None))
r.register(Kind("a" * 32, "Lang", None, None))
assert "a" * 32 in r.names()
r.register(Kind("agent", "Agent", None, None, placeholder=True))
raises("kind_already_registered", r.register, Kind("agent", "Agent 2", None, None))
real = Kind("agent", "Agent echt", None, None)
r.register(real, replace_placeholder=True)
assert r.get("agent") is real
raises("kind_already_registered", r.register, Kind("agent", "Agent 3", None, None), replace_placeholder=True)
raises("kind_already_registered", r.register, Kind("model", "M", None, None), replace_placeholder=True)
r.register(Kind("echo", "Echo", None, None), replace_placeholder=True)
assert r.get("echo").title == "Echo"
m = r.mark()
r.register(Kind("routine", "Routine", None, None))
assert "routine" in r.names()
r.reset(m)
assert "routine" not in r.names()
assert r.get("agent") is real
m2 = r.mark()
r.register(Kind("routine", "Routine", None, None))
r.reset(m2)
r.reset(m2)
assert "routine" not in r.names()
r.refuse("ext.mod", "boom")
r.refuse("ext.two", "kind_already_registered")
assert r.problems == [{"source": "ext.mod", "reason": "boom"}, {"source": "ext.two", "reason": "kind_already_registered"}]
before = r.names()
r.freeze()
assert r.frozen is True
raises("kinds_frozen", r.register, Kind("late", "Spät", None, None))
raises("kinds_frozen", r.reset, m)
assert r.names() == before
p = Registry()
p.register(Kind("agent", "A", None, None, placeholder=True))
p.register(Kind("agent", "B", None, None), replace_placeholder=True)
raises("kind_already_registered", p.register, Kind("agent", "C", None, None), replace_placeholder=True)
'''

C2 = r'''
data = {"t1": obj("task", "t1"), "t2": obj("task", "t2", state="fertig")}
seen = []


def read_task(hub, oid):
    seen.append((hub, oid))
    return copy.deepcopy(data.get(oid))


def list_task(hub, payload):
    seen.append(("list", payload))
    return [copy.deepcopy(data[k]) for k in sorted(data)]


run_verb = V("ausfuehren", when=lambda o: o["state"] == "bereit")
always = V("zeigen")
r = Registry(not_found=lambda kind, oid: {"type": kind, "id": oid, "missing": True})
r.register(Kind("task", "Aufgabe", read_task, list_task, verbs=[run_verb, always], type_verbs=[V("anlegen")]))
r.register(Kind("decision", "Entscheidung", lambda h, i: obj("decision", i), lambda h, p: [obj("decision", "d1")], own_actions=True))
r.register(Kind("skill", "Fähigkeit", lambda h, i: None, lambda h, p: []))
r.register(Kind("broken", "Kaputt", lambda h, i: {"type": "broken", "id": i}, lambda h, p: [obj("broken", "b1"), {"type": "broken"}]))
r.register(Kind("onlynew", "Nur neu", lambda h, i: None, lambda h, p: [], type_verbs=[V("anlegen")]))
r.register(Kind("agent", "Agent", lambda h, i: (_ for _ in ()).throw(ValueError("unknown_object_type")), lambda h, p: [], placeholder=True))
HUB = object()
desc = lambda v: v.describe()
assert r.offered(obj("task", "x")) == [desc(run_verb), desc(always)]
assert r.offered(obj("task", "x", state="fertig")) == [desc(always)]
assert r.offered(obj("nothing", "x")) == []
assert r.offered({"id": "x"}) == []
v = r.view(HUB, "task", "t1")
assert v["actions"] == [desc(run_verb), desc(always)]
assert v["title"] == "T t1"
assert seen[-1] == (HUB, "t1")
assert data["t1"]["actions"] == ["alt"]
assert r.view(HUB, "task", "t2")["actions"] == [desc(always)]
assert r.view(HUB, "task", "nope") == {"type": "task", "id": "nope", "missing": True}
assert r.view(HUB, "decision", "d7")["actions"] == ["alt"]
assert r.view(HUB, "skill", "s1") == {"type": "skill", "id": "s1", "missing": True}
raises("object_shape_invalid", r.view, HUB, "broken", "b1")
raises("unknown_object_type", r.view, HUB, "nix", "1")
raises("unknown_object_type", r.view, HUB, "agent", "a1")
plain = Registry()
plain.register(Kind("skill", "F", lambda h, i: None, lambda h, p: []))
raises("object_not_found", plain.view, HUB, "skill", "s1")
items = r.listing(HUB, "task", {"type": "task", "state": "bereit"})
assert [i["id"] for i in items] == ["t1", "t2"]
assert items[0]["actions"] == [desc(run_verb), desc(always)]
assert items[1]["actions"] == [desc(always)]
assert seen[-1] == ("list", {"type": "task", "state": "bereit"})
r.listing(HUB, "task")
assert seen[-1] == ("list", {})
assert r.listing(HUB, "decision")[0]["actions"] == []
assert r.listing(HUB, "agent") == []
raises("object_shape_invalid", r.listing, HUB, "broken")
raises("unknown_object_type", r.listing, HUB, "nix")
payload = {"type": " task ", "id": "t1"}
keep = copy.deepcopy(payload)
assert r.request(HUB, payload)["id"] == "t1"
assert payload == keep
assert r.request(HUB, {"type": "task", "id": 7}) == {"type": "task", "id": "7", "missing": True}
out = r.request(HUB, {"type": "task"})
assert out["type"] == "task"
assert [i["id"] for i in out["items"]] == ["t1", "t2"]
assert r.request(HUB, {"type": "task", "id": ""})["type"] == "task"
assert r.request(HUB, {"type": "agent"}) == {"type": "agent", "items": []}
raises("unknown_object_type", r.request, HUB, {"type": "nix"})
raises("unknown_object_type", r.request, HUB, {})
raises("unknown_object_type", r.request, HUB, {"type": None, "id": "1"})
t = r.table()
assert sorted(t) == ["onlynew", "task"]
assert t["task"] == {"ausfuehren": run_verb, "zeigen": always}
assert t["onlynew"] == {}
assert r.type_verb("task", "anlegen").verb == "anlegen"
assert r.type_verb("task", "ausfuehren") is None
raises("unknown_object_type", r.type_verb, "nix", "anlegen")
assert run_verb.runs == 0
'''

C3 = r'''
assert CHAT_TOOLS == frozenset({"talk", "planung"})
assert SHAPE == ("type", "id", "title", "state", "summary", "actions", "links")
assert client_for("cli") == "cli"
assert client_for("mcp") == "mcp"
assert client_for("mcp", "talk", True) == "mcp"
assert client_for("browser") == "shell"
assert client_for("browser", "talk", True) == "chat"
assert client_for("browser", "planung", True) == "chat"
assert client_for("browser", "talk", False) == "shell"
assert client_for("browser", "werkbank", True) == "shell"
assert client_for("browser", None, True) == "shell"
for bad in ("shell", "chat", "", None, "paperclip"):
    raises("unknown_token_class", client_for, bad)
p = {"type": "model", "id": "m", "verb": "laden", "client": "cli"}
keep = dict(p)
raises("client_is_set_by_server", refuse_client_field, p)
assert p == keep
raises("client_is_set_by_server", refuse_client_field, {"client": None})
assert refuse_client_field({"type": "model", "args": {"client": "x"}}) is None
assert refuse_client_field({}) is None
assert refuse_client_field(None) is None
'''

STAGES = [
    {"name": "register",
     "task": """Create `kinds.py` (Python 3 standard library only) with `class Kind` and `class Registry`: the register of the desk's object types.
- `Kind(name, title, read, listing, verbs=(), type_verbs=(), source="desk", placeholder=False, own_actions=False)`: keeps every argument as an attribute of the same name; `verbs` and `type_verbs` are stored as tuples. `kind.verb(name)` and `kind.type_verb(name)` return the first verb object in `verbs` or `type_verbs` whose attribute `verb` equals name, else None.
- `Registry(not_found=None)`: the class attribute `Registry.Kind` is the class `Kind` (an extension gets the registry and builds kinds with `registry.Kind(...)`). Attribute `problems`: a list, starts empty. Property `frozen`: False until `freeze()` was called.
- `register(kind, replace_placeholder=False)`: after `freeze()` -> ValueError("kinds_frozen"). The name must fully match `[a-z][a-z0-9_]{1,31}`, else ValueError("kind_name_invalid"). A name that is already registered -> ValueError("kind_already_registered") and the old kind stays; the ONLY exception: replace_placeholder=True and the registered kind has placeholder=True, then the new kind replaces it. replace_placeholder=True for a new name simply registers it.
- `names()` the registered names sorted; `get(name)` the kind or None.
- `mark()` returns a copy of the current registrations; `reset(mark)` goes back to exactly that state (also undoes a replaced placeholder; after `freeze()` -> ValueError("kinds_frozen")). A mark can be used more than once.
- `refuse(source, reason)` appends {"source": source, "reason": reason} to `problems`.""",
     "hidden": {"hidden_kinds_1.py": hidden("Kind, Registry", C1)}},
    {"name": "view",
     "task": """Add to `Registry` in `kinds.py` (keep everything else). The module constant `SHAPE = ("type", "id", "title", "state", "summary", "actions", "links")`.
- `offered(obj)`: for the kind named obj["type"] (missing type or unknown kind: []), `[v.describe() for v in kind.verbs if v.offered(obj)]` in the order of `verbs`.
- `view(hub, name, oid)`: unknown name -> ValueError("unknown_object_type"). obj = kind.read(hub, oid); exceptions of the reader are not caught. obj None -> `not_found(name, oid)` of the constructor is returned unchanged, and without a not_found function ValueError("object_not_found"). Otherwise obj must be a dict that has every key of SHAPE (more keys are fine), else ValueError("object_shape_invalid"); then obj["actions"] = offered(obj) unless the kind has own_actions=True (then the reader's actions stay). Return obj.
- `listing(hub, name, payload=None)`: unknown name -> ValueError("unknown_object_type"); items = list(kind.listing(hub, a copy of payload as dict, {} for None)); every item must have every key of SHAPE, else ValueError("object_shape_invalid"); for EVERY item (also with own_actions) item["actions"] = offered(item). Return the list.
- `request(hub, payload)` (the route POST /api/objects): name = str(payload.get("type") or "").strip(); unknown -> ValueError("unknown_object_type"). If payload.get("id") is truthy: view(hub, name, str(id)); else {"type": name, "items": listing(hub, name, payload)}. Never change payload.
- `table()`: {name: {v.verb: v for v in kind.verbs}} for every kind that has at least one verb or one type verb (a kind without any verb is NOT in the table).
- `type_verb(name, verb)`: unknown name -> ValueError("unknown_object_type"), else kind.type_verb(verb).
Never call a verb's `run`.""",
     "hidden": {"hidden_kinds_1.py": hidden("Kind, Registry", C1), "hidden_kinds_2.py": hidden("Kind, Registry", C2)}},
    {"name": "client",
     "task": """Add two functions to `kinds.py` (keep everything else) for the audit field `client` that the server sets, never the caller. Module constant `CHAT_TOOLS = frozenset({"talk", "planung"})`.
- `client_for(token_class, tool=None, tool_ok=False)`: token_class "cli" or "mcp" -> the same string (tool is ignored). "browser" -> "chat" when tool_ok is True and tool is in CHAT_TOOLS, else "shell". Any other token_class -> ValueError("unknown_token_class").
- `refuse_client_field(payload)`: when payload is a dict with the top-level key "client" (any value) -> ValueError("client_is_set_by_server"); otherwise return None (nested dicts, an empty dict or None are fine). Never change payload.""",
     "hidden": {"hidden_kinds_1.py": hidden("Kind, Registry", C1), "hidden_kinds_2.py": hidden("Kind, Registry", C2),
                "hidden_kinds_3.py": hidden("Kind, Registry, CHAT_TOOLS, SHAPE, client_for, refuse_client_field", C3)}},
]
