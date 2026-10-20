"""Spec 0, K0.9 (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, design D1 and D5, gate G2-S0-01): `desk/extensions.py`, the list of modules that dock new object types onto the desk.
A new use case is one module with `register(registry, hub)` plus one line in `MODULES`; `uix_server.py` stays untouched (KERN-04). An extension that fails on import or in
`register` is left out completely (its half registration is undone), the reason goes to `registry.problems` and to the audit as `DESK_KIND_REFUSED`, and the desk starts anyway.
`start(hub, loaded)` calls the optional `start(hub)` of each loaded module (the heartbeat clock of Spec 1). Pure logic: the importer, the registry and the audit are injected.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/k0_extensions). Wiring into uix_server.py is harness work (K0.11)."""

NOTES = '''# Notes for k0_extensions
Python 3 standard library only (importlib), no file, process or network access of its own. Modules are imported ONLY through the injected `importer`; the registry and the audit are the objects passed in.
The registry has `mark()`, `reset(mark)`, `refuse(source, reason)` and whatever an extension calls on it; `audit(event, payload)` is a plain function.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code.
'''

HEAD = r'''
import importlib
from types import SimpleNamespace
from extensions import IMPORTS


class FakeRegistry:
    def __init__(self):
        self.kinds, self.problems = {}, []

    def register(self, name):
        if name in self.kinds:
            raise ValueError("kind_already_registered")
        self.kinds[name] = True

    def mark(self):
        return dict(self.kinds)

    def reset(self, mark):
        self.kinds = dict(mark)

    def refuse(self, source, reason):
        self.problems.append({"source": source, "reason": reason})


class Boom(Exception):
    pass


def mod(name, register=None, start=None):
    out = SimpleNamespace(__name__=name)
    if register is not None:
        out.register = register
    if start is not None:
        out.start = start
    return out


calls = []
HUB = object()


def reg(*names):
    def register(registry, hub):
        calls.append(("register", hub is HUB))
        for n in names:
            registry.register(n)
    return register


def half(registry, hub):
    registry.register("halb")
    raise Boom("mitten drin")


MODS = {
    "ext.a": mod("ext.a", reg("alpha", "beta")),
    "ext.b": mod("ext.b", reg("alpha")),
    "ext.c": mod("ext.c", half),
    "ext.d": mod("ext.d"),
    "ext.e": mod("ext.e", reg("echo")),
    "ext.f": mod("ext.f", reg("fox")),
}
MODS["ext.d"].register = "not callable"


def importer(name):
    calls.append(("import", name))
    if name == "ext.missing":
        raise ModuleNotFoundError("No module named 'ext.missing'")
    if name == "ext.empty":
        raise Boom()
    return MODS[name]


events = []
audit = lambda event, payload: events.append((event, payload))
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert MODULES == ("guppi_runtime.desk.orchestra_kinds",)
r = FakeRegistry()
order = ["ext.a", "ext.missing", "ext.b", "ext.c", "ext.d", "ext.empty", "ext.e"]
keep = list(order)
loaded = load(r, HUB, order, importer=importer, audit=audit)
assert order == keep
assert loaded == [MODS["ext.a"], MODS["ext.e"]]
assert sorted(r.kinds) == ["alpha", "beta", "echo"]
assert r.problems == [
    {"source": "ext.missing", "reason": "No module named 'ext.missing'"},
    {"source": "ext.b", "reason": "kind_already_registered"},
    {"source": "ext.c", "reason": "mitten drin"},
    {"source": "ext.d", "reason": "extension_without_register"},
    {"source": "ext.empty", "reason": "Boom"},
]
assert events == [("DESK_KIND_REFUSED", {"module": p["source"], "reason": p["reason"]}) for p in r.problems]
assert [c[1] for c in calls if c[0] == "import"] == order
assert all(c[1] for c in calls if c[0] == "register")
r2 = FakeRegistry()
assert load(r2, HUB, ("ext.c",), importer=importer) == []
assert r2.kinds == {}
assert r2.problems == [{"source": "ext.c", "reason": "mitten drin"}]
r3 = FakeRegistry()
assert load(r3, HUB, (), importer=importer, audit=audit) == []
assert r3.problems == []
r4 = FakeRegistry()
r4.register("alpha")
assert load(r4, HUB, ("ext.a",), importer=importer) == []
assert r4.kinds == {"alpha": True}
r5 = FakeRegistry()
seen = []
assert load(r5, HUB, ("json",), importer=lambda n: seen.append(n) or importlib.import_module(n)) == []
assert seen == ["json"]
assert r5.problems == [{"source": "json", "reason": "extension_without_register"}]
'''

C2 = r'''
order = []
def ok_start(hub):
    order.append(("A", hub is HUB))
def bad_start(hub):
    order.append(("B", hub is HUB))
    raise RuntimeError("kein Takt")
def silent(hub):
    raise Boom()
A = mod("ext.a", reg(), ok_start)
B = mod("ext.b", reg(), bad_start)
C = mod("ext.c", reg())
D = mod("ext.d", reg(), silent)
E = mod("ext.e", reg(), ok_start)
E.start = "not callable"
F = mod("ext.f", reg(), ok_start)
events.clear()
assert start(HUB, [A, B, C, D, E, F], audit=audit) == ["ext.a", "ext.f"]
assert order == [("A", True), ("B", True), ("A", True)]
assert events == [("DESK_EXTENSION_START_FAILED", {"module": "ext.b", "reason": "kein Takt"}),
                  ("DESK_EXTENSION_START_FAILED", {"module": "ext.d", "reason": "Boom"})]
assert start(HUB, [B]) == []
assert start(HUB, []) == []
lst = [A, C]
start(HUB, lst)
assert lst == [A, C]
'''

STAGES = [
    {"name": "load",
     "task": """Create `extensions.py` (Python 3 standard library only). Module constant `MODULES = ("guppi_runtime.desk.orchestra_kinds",)`.
`load(registry, hub, modules=MODULES, importer=importlib.import_module, audit=None) -> list`: docks the extension modules onto the registry, in the order of `modules`.
- For each name: take `mark = registry.mark()`; module = importer(name); `register = getattr(module, "register", None)`; when it is not callable raise ValueError("extension_without_register") (treated like any failure); call register(registry, hub).
- Any Exception in these steps (import, missing register, register itself): `registry.reset(mark)` (a half registration is undone), `registry.refuse(name, reason)` and, when audit is not None, `audit("DESK_KIND_REFUSED", {"module": name, "reason": reason})`; then go on with the next name. reason = str(exc), or the class name of the exception when str(exc) is empty.
- Return the list of the module objects whose register succeeded, in order. Never change `modules`.""",
     "hidden": {"hidden_ext_1.py": hidden("MODULES, load", C1)}},
    {"name": "start",
     "task": """Add `start(hub, loaded, audit=None) -> list` to `extensions.py` (keep everything else): for each module of `loaded`, in order, call its `start(hub)` when the module has a callable attribute `start` (modules without one, or with a non-callable one, are skipped silently).
- Return the `__name__` of every module whose start returned without an exception.
- An Exception in a start does not stop the others: when audit is not None, `audit("DESK_EXTENSION_START_FAILED", {"module": module.__name__, "reason": reason})` with reason as in `load` (str(exc) or the class name). Use ONE helper for the reason in both functions.
Never change `loaded`.""",
     "hidden": {"hidden_ext_1.py": hidden("MODULES, load", C1), "hidden_ext_2.py": hidden("load, start", C2)}},
]
