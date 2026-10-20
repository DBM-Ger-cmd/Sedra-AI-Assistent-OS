"""Spec 0, K0.16 (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, design D3.4 and D3.5, KERN-06, gates G2-S0-08 and G2-S0-10): `orchestra/config.py`, the checked configuration
of the orchestration package. `OrchestraConfig.from_dict` checks the content of `runtime/config/orchestra.yaml`: unknown keys refused, integers within limits (the rule of
`SupervisorConfig._int`: a bool is no int), `coalesce_s < tick_s`, `warn_percent < stop_percent`, `database` relative and without `..`. Every error is
ValueError("orchestra_config_invalid:<field>") with the dotted field name; a missing file is ValueError("orchestra_config_missing"). `runtime.py` turns these texts into
`orchestra_error` and `boot()["orchestra"]["error"]` (harness, K0.20). The YAML parser is injected (the tests use json, which is a subset of YAML), so the module needs no yaml
in the microVM. GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/k0_orchestra_config)."""

NOTES = '''# Notes for k0_orchestra_config
Python 3 standard library only (pathlib); `yaml` is imported only inside `load` and only when no `parse` function is given (the tests always give one). Reading a file is allowed in `load`, nothing else touches files, processes or the network.
Every error is a ValueError with exactly the text the task names. No comments and no docstrings, never modify the arguments, small private helpers instead of copied code (ONE helper checks an integer with its limits).
'''

HEAD = r'''
import copy, json, os, tempfile
from pathlib import Path
from config import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def cfg(**changes):
    raw = {"schema": 1}
    for key, value in changes.items():
        if "__" in key:
            section, field = key.split("__")
            raw.setdefault(section, {})[field] = value
        else:
            raw[key] = value
    return {"orchestra": raw}


BAD = "orchestra_config_invalid:"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = OrchestraConfig.from_dict(cfg())
assert c.schema == 1
assert c.enabled is False
assert c.database == "orchestra/orchestra.db"
assert c.tick_s == 5
assert c.coalesce_s == 2
assert c.max_runs_per_tick == 1
assert c.stall_s == 900
assert c.warn_percent == 80
assert c.stop_percent == 100
assert c.max_catch_up == 3
assert c.max_depth == 6
full = {"orchestra": {"schema": 1, "enabled": True, "database": "orc/o.db", "heartbeat": {"tick_s": 10, "coalesce_s": 0, "max_runs_per_tick": 4},
        "checkout": {"stall_s": 2}, "budget": {"warn_percent": 90, "stop_percent": 150}, "routines": {"max_catch_up": 0}, "org": {"max_depth": 32}}}
keep = copy.deepcopy(full)
f = OrchestraConfig.from_dict(full)
assert full == keep
assert f.enabled is True
assert f.database == "orc/o.db"
assert f.tick_s == 10
assert f.coalesce_s == 0
assert f.max_runs_per_tick == 4
assert f.stall_s == 2
assert f.warn_percent == 90
assert f.stop_percent == 150
assert f.max_catch_up == 0
assert f.max_depth == 32
assert OrchestraConfig.from_dict(cfg(heartbeat__tick_s=3600, heartbeat__coalesce_s=3599)).coalesce_s == 3599
assert OrchestraConfig.from_dict(cfg(checkout__stall_s=86400)).stall_s == 86400
assert OrchestraConfig.from_dict(cfg(budget__warn_percent=1, budget__stop_percent=1000)).stop_percent == 1000
assert OrchestraConfig.from_dict(cfg(budget__warn_percent=99)).warn_percent == 99
assert OrchestraConfig.from_dict(cfg(routines__max_catch_up=100)).max_catch_up == 100
assert OrchestraConfig.from_dict(cfg(heartbeat__max_runs_per_tick=16)).max_runs_per_tick == 16
for data in (None, [], "x", {}, {"orchestra": None}, {"orchestra": []}, {"other": {}}):
    raises(BAD + "orchestra", OrchestraConfig.from_dict, data)
raises(BAD + "schema", OrchestraConfig.from_dict, {"orchestra": {}})
for schema in (0, 2, "1", True, 1.0):
    raises(BAD + "schema", OrchestraConfig.from_dict, cfg(schema=schema))
raises(BAD + "zzz", OrchestraConfig.from_dict, {"orchestra": {"schema": 7, "zzz": 1}})
raises(BAD + "aaa", OrchestraConfig.from_dict, cfg(zzz=1, aaa=2))
for value in (1, "true", None):
    raises(BAD + "enabled", OrchestraConfig.from_dict, cfg(enabled=value))
'''

C2 = r'''
assert OrchestraConfig.from_dict(cfg(database="./orchestra\\x.db")).database == "orchestra/x.db"
assert OrchestraConfig.from_dict(cfg(database="a/b.db")).database == "a/b.db"
cases = [
    ("heartbeat.tick_s", dict(heartbeat__tick_s=0)), ("heartbeat.tick_s", dict(heartbeat__tick_s=3601)), ("heartbeat.tick_s", dict(heartbeat__tick_s=True)),
    ("heartbeat.tick_s", dict(heartbeat__tick_s=5.0)), ("heartbeat.tick_s", dict(heartbeat__tick_s="5")),
    ("heartbeat.coalesce_s", dict(heartbeat__coalesce_s=-1)), ("heartbeat.max_runs_per_tick", dict(heartbeat__max_runs_per_tick=0)),
    ("heartbeat.max_runs_per_tick", dict(heartbeat__max_runs_per_tick=17)),
    ("checkout.stall_s", dict(checkout__stall_s=1)), ("checkout.stall_s", dict(checkout__stall_s=86401)),
    ("budget.warn_percent", dict(budget__warn_percent=0)), ("budget.warn_percent", dict(budget__warn_percent=101)),
    ("budget.stop_percent", dict(budget__stop_percent=1001)), ("budget.stop_percent", dict(budget__stop_percent=False)),
    ("routines.max_catch_up", dict(routines__max_catch_up=-1)), ("routines.max_catch_up", dict(routines__max_catch_up=101)),
    ("org.max_depth", dict(org__max_depth=0)), ("org.max_depth", dict(org__max_depth=33)),
    ("heartbeat.coalesce_s", dict(heartbeat__coalesce_s=5)), ("heartbeat.coalesce_s", dict(heartbeat__tick_s=2, heartbeat__coalesce_s=3)),
    ("budget.warn_percent", dict(budget__warn_percent=100)), ("budget.warn_percent", dict(budget__warn_percent=60, budget__stop_percent=50)),
    ("heartbeat.zz", dict(heartbeat__zz=1, heartbeat__tick_s=0)), ("org.depth", dict(org__depth=6)),
]
for field, changes in cases:
    raises(BAD + field, OrchestraConfig.from_dict, cfg(**changes))
for name in ("heartbeat", "checkout", "budget", "routines", "org"):
    raises(BAD + name, OrchestraConfig.from_dict, cfg(**{name: [1]}))
    raises(BAD + name, OrchestraConfig.from_dict, cfg(**{name: None}))
raises(BAD + "heartbeat.tick_s", OrchestraConfig.from_dict, cfg(heartbeat__tick_s=0, org__max_depth=0))
raises(BAD + "budget.warn_percent", OrchestraConfig.from_dict, cfg(budget__stop_percent=0, budget__warn_percent=0))
raises(BAD + "budget.stop_percent", OrchestraConfig.from_dict, cfg(budget__stop_percent=0, budget__warn_percent=50))
for db in ("", "  ", None, 5, "/abs/o.db", "\\abs\\o.db", "C:/o.db", "C:o.db", "d:\\x\\o.db", "../o.db", "orchestra/../../o.db", "a\\..\\b.db", "\\\\server\\share\\o.db"):
    raises(BAD + "database", OrchestraConfig.from_dict, cfg(database=db))
raises(BAD + "enabled", OrchestraConfig.from_dict, cfg(enabled="x", database="/abs"))
raises(BAD + "database", OrchestraConfig.from_dict, cfg(database="/abs", heartbeat__tick_s=0))
'''

C3 = r'''
tmp = Path(tempfile.mkdtemp())
missing = tmp / "nope.yaml"
raises("orchestra_config_missing", OrchestraConfig.load, missing, parse=json.loads)
raises("orchestra_config_missing", OrchestraConfig.load, tmp, parse=json.loads)
good = tmp / "orchestra.yaml"
good.write_text(json.dumps(cfg(enabled=True, heartbeat__tick_s=9)), encoding="utf-8")
c = OrchestraConfig.load(good, parse=json.loads)
assert c.enabled is True
assert c.tick_s == 9
assert OrchestraConfig.load(str(good), parse=json.loads).tick_s == 9
seen = []
OrchestraConfig.load(good, parse=lambda text: seen.append(text) or json.loads(text))
assert seen == [good.read_text(encoding="utf-8")]
broken = tmp / "broken.yaml"
broken.write_text("{nicht json", encoding="utf-8")
raises(BAD + "unreadable", OrchestraConfig.load, broken, parse=json.loads)
empty = tmp / "empty.yaml"
empty.write_text("null", encoding="utf-8")
raises(BAD + "orchestra", OrchestraConfig.load, empty, parse=json.loads)
wrong = tmp / "wrong.yaml"
wrong.write_text(json.dumps(cfg(org__max_depth=99)), encoding="utf-8")
raises(BAD + "org.max_depth", OrchestraConfig.load, wrong, parse=json.loads)
d = OrchestraConfig.from_dict(cfg(database="orc/x.db"))
assert d.database_path(tmp) == tmp / "orc" / "x.db"
assert d.database_path(str(tmp)) == tmp / "orc" / "x.db"
assert isinstance(d.database_path(str(tmp)), Path)
expected = {"orchestra": {"schema": 1, "enabled": False, "database": "orc/x.db", "heartbeat": {"tick_s": 5, "coalesce_s": 2, "max_runs_per_tick": 1},
            "checkout": {"stall_s": 900}, "budget": {"warn_percent": 80, "stop_percent": 100}, "routines": {"max_catch_up": 3}, "org": {"max_depth": 6}}}
assert d.as_dict() == expected
again = OrchestraConfig.from_dict(d.as_dict())
assert again.as_dict() == expected
out = d.as_dict()
out["orchestra"]["heartbeat"]["tick_s"] = 99
assert d.as_dict() == expected
assert d.tick_s == 5
'''

STAGES = [
    {"name": "top",
     "task": """Create `config.py` (Python 3 standard library only) with `class OrchestraConfig` and the classmethod `OrchestraConfig.from_dict(data)`: the checked configuration of the orchestration package. Every error is ValueError("orchestra_config_invalid:<field>").
- data must be a dict whose key "orchestra" holds a dict, else field "orchestra". In that dict only the keys schema, enabled, database, heartbeat, checkout, budget, routines, org are allowed; for unknown keys the field is the alphabetically FIRST unknown key (checked before everything else).
- "schema" must be the int 1 (missing, 2, "1", True or 1.0 -> field "schema"). "enabled": a bool, default False (field "enabled"). "database": default "orchestra/orchestra.db" (its own rules come in the next stage; for now keep a given string).
- The sections with their integer fields as (default, lowest, highest): heartbeat: tick_s (5, 1, 3600), coalesce_s (2, 0, 3600), max_runs_per_tick (1, 1, 16); checkout: stall_s (900, 2, 86400); budget: warn_percent (80, 1, 100), stop_percent (100, 1, 1000); routines: max_catch_up (3, 0, 100); org: max_depth (6, 1, 32). Missing sections and fields take the defaults.
- The result has the attributes schema, enabled, database and one attribute per integer field with the same name (c.tick_s, c.stall_s, c.max_depth, ...). Never change data.""",
     "hidden": {"hidden_ocfg_1.py": hidden("OrchestraConfig", C1)}},
    {"name": "fields",
     "task": """Complete the checks of `OrchestraConfig.from_dict` in `config.py` (keep everything else). Order of the checks: unknown top keys, schema, enabled, database, then the sections in the order heartbeat, checkout, budget, routines, org, then the two rules between fields.
- A section that is present but not a dict -> field "<section>" (for example "budget"). Unknown keys in a section -> "<section>.<first unknown key alphabetically>", checked before its values.
- Every integer field: `type(value) is int` (True, 5.0 and "5" are wrong) and lowest <= value <= highest, else "<section>.<field>" (for example "heartbeat.tick_s"); fields in the order of the list of the previous stage. ONE helper checks an integer.
- After all sections: coalesce_s must be smaller than tick_s, else "heartbeat.coalesce_s"; warn_percent must be smaller than stop_percent, else "budget.warn_percent".
- "database": a non-empty string that is not only spaces, relative and without "..": a Windows drive ("C:", "C:/x", "C:x"), a leading slash or a leading backslash (also two of them, a network path) and any ".." part are wrong (field "database"). A backslash counts as "/"; the stored value is the normalised posix form: "./orchestra" + backslash + "x.db" is stored as "orchestra/x.db".""",
     "hidden": {"hidden_ocfg_1.py": hidden("OrchestraConfig", C1), "hidden_ocfg_2.py": hidden("OrchestraConfig", C2)}},
    {"name": "load",
     "task": """Add to `OrchestraConfig` in `config.py` (keep everything else):
- classmethod `load(path, parse=None)`: path is a str or Path. When it is not an existing file -> ValueError("orchestra_config_missing"). Otherwise read it as UTF-8 text and give the text to `parse` (when parse is None: `yaml.safe_load`, imported inside `load` only in that case). When parse raises any Exception -> ValueError("orchestra_config_invalid:unreadable"). Then return from_dict(parsed data) (so `null` gives field "orchestra").
- `database_path(runtime_data)`: Path(runtime_data) joined with the database value, always a Path.
- `as_dict()`: a NEW nested dict {"orchestra": {"schema", "enabled", "database", and every section as a dict of all its integer fields}} that from_dict accepts and that gives the same as_dict again; changing the returned dict never changes the config.""",
     "hidden": {"hidden_ocfg_1.py": hidden("OrchestraConfig", C1), "hidden_ocfg_2.py": hidden("OrchestraConfig", C2), "hidden_ocfg_3.py": hidden("OrchestraConfig", C3)}},
]
