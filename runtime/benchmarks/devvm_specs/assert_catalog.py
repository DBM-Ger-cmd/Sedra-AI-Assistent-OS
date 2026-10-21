"""Test catalog (G0 of docs/ABLAUF_GESPRAECH_2026-10-13.md; Captain 2026-10-13: "es sollte einen Katalog fuer Tests geben, damit nicht immer neue erstellt werden muessen").
`assert_catalog.py` turns a catalog kind (K01 to K15, the test patterns that came back in every spec of 2026-10-13) and its parameters into the code of a hidden test: examples as a table, arguments unchanged, empty inputs, bounds,
a fixed order for ties, determinism, exceptions, stable order, numbers with a tolerance, a file result, a text format, a pure module, an output limit, the form of the source, a cumulative stage test. All parameters are DATA that is written
into the code with `repr`; a name that is not an identifier is refused, so no parameter can inject code. `check_proofs` runs every kind against its proof (seed `catalog_proofs.py`, written by Claude): the generated test must pass the good
example and fail every mutant. The hidden tests below judge the behaviour of the generated code, not its wording. Seed: benchmarks/assert_catalog_seed; reference: benchmarks/devvm_refs/assert_catalog."""

SEED = "benchmarks/assert_catalog_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given
NOTES = '''# Notes for assert_catalog
Pure Python 3 standard library (`subprocess`, `tempfile`, `pathlib`, `sys`, `builtins`, `re` are allowed). `catalog_proofs.py` is already in the workspace (data: PROOFS); do not change it. Never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top.
The generated code is plain Python text. Every piece you generate ends with ONE newline.
'''

HEAD = r'''
import subprocess, sys, tempfile
from pathlib import Path
from assert_catalog import kinds, describe, generate
from catalog_proofs import PROOFS

def runs(code, files):
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in files.items():
            target = Path(tmp) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        (Path(tmp) / "t_run.py").write_text(code, encoding="utf-8")
        return subprocess.run([sys.executable, "t_run.py"], cwd=tmp, capture_output=True, text=True, timeout=60).returncode == 0

def proof_holds(kind):
    proof = PROOFS[kind]
    code = generate(kind, **proof["params"])
    assert code.endswith(chr(10)) and not code.endswith(chr(10) * 2)
    assert runs(code, proof["good"]), kind + " good example fails"
    for number, mutant in enumerate(proof["mutants"], 1):
        assert not runs(code, mutant), kind + " mutant " + str(number) + " passes"

def raises(exception, kind, **params):
    try:
        generate(kind, **params)
    except exception:
        return True
    return False

S = "def f(x):" + chr(10) + "    return x" + chr(10)
'''

S1 = HEAD + r'''
assert set(kinds()) >= {"K01", "K02", "K03", "K04", "K05"} and kinds() == sorted(kinds())
assert describe("K01") == {"id": "K01", "name": "table", "required": ["module", "func", "cases"], "optional": {}}
assert describe("K03") == {"id": "K03", "name": "empty", "required": ["module", "func"], "optional": {"values": (None, "", [], {}), "prefix": ()}}
assert describe("K05")["optional"] == {"field": "id"} and describe("K04")["required"] == ["module", "func", "name", "cases"]
assert raises(KeyError, "K99", module="m", func="f")
assert raises(ValueError, "K01", module="m", func="f")
assert raises(ValueError, "K01", module="m", func="f", cases=[((1,), 1)], extra=1)
assert raises(ValueError, "K01", module="m x", func="f", cases=[((1,), 1)])
assert raises(ValueError, "K01", module="m", func="f()", cases=[((1,), 1)])
assert raises(ValueError, "K01", module="m; import os", func="f", cases=[((1,), 1)])
assert raises(ValueError, "K01", module="m", func="f", cases=[])
assert raises(ValueError, "K04", module="m", func="f", name="a b", cases=[(1, 1)])
assert not raises(ValueError, "K01", module="pkg.mod", func="f", cases=[((1,), 1)])
for kind in ("K01", "K02", "K03", "K04", "K05"):
    proof_holds(kind)
quoted = generate("K01", module="s", func="f", cases=[(("a'b" + chr(10),), "a'b" + chr(10)), (("x",), "x")])
assert runs(quoted, {"s.py": S})
assert not runs(quoted, {"s.py": "def f(x):" + chr(10) + "    return x + '!'" + chr(10)})
nested = generate("K02", module="s", func="f", args=({"k": [1]},))
assert runs(nested, {"s.py": S})
assert not runs(nested, {"s.py": "def f(x):" + chr(10) + "    x['k'].append(2)" + chr(10) + "    return x" + chr(10)})
empties = generate("K03", module="s", func="f", prefix=(3,), values=(None,))
assert runs(empties, {"s.py": "def f(n, x):" + chr(10) + "    return n" + chr(10)})
assert not runs(empties, {"s.py": "def f(n, x):" + chr(10) + "    return len(x)" + chr(10)})
assert not runs(generate("K03", module="s", func="f"), {"s.py": "def f(x):" + chr(10) + "    return x.strip()" + chr(10)})
assert runs(generate("K03", module="s", func="f"), {"s.py": "def f(x):" + chr(10) + "    return x" + chr(10)})
byname = generate("K05", module="s", func="f", args=([2, 1],), field="name")
assert runs(byname, {"s.py": "def f(xs):" + chr(10) + "    return [{'name': n} for n in sorted(xs)]" + chr(10)})
assert not runs(byname, {"s.py": "def f(xs):" + chr(10) + "    return [{'name': n} for n in xs]" + chr(10)})
args = ([1, 2], {"a": 1})
before = repr(args)
generate("K02", module="s", func="f", args=args)
assert repr(args) == before
'''

S2 = S1 + r'''
for kind in ("K06", "K07", "K08", "K09", "K10"):
    proof_holds(kind)
assert set(kinds()) >= {"K06", "K07", "K08", "K09", "K10"}
assert describe("K09") == {"id": "K09", "name": "near", "required": ["module", "func", "cases"], "optional": {"tol": 0.01}}
assert describe("K10")["required"] == ["pattern", "heads"] and describe("K10")["optional"] == {"head_prefix": "## ", "first_regex": "", "contains": ()}
assert raises(ValueError, "K07", module="s", func="f", cases=[((1,), "NoSuchError", "m")])
assert raises(ValueError, "K07", module="s", func="f", cases=[((1,), "os", "m")])
assert raises(ValueError, "K07", module="s", func="f", cases=[((1,), "ValueError")])
anyerr = generate("K07", module="s", func="f", cases=[((1,), "Exception", "boom"), ((2,), "KeyError", "'k'")])
assert runs(anyerr, {"s.py": "def f(x):" + chr(10) + "    if x == 1:" + chr(10) + "        raise Exception('boom')" + chr(10) + "    raise KeyError('k')" + chr(10)})
assert not runs(anyerr, {"s.py": "def f(x):" + chr(10) + "    raise Exception('boom')" + chr(10)})
assert not runs(anyerr, {"s.py": "def f(x):" + chr(10) + "    return x" + chr(10)})
other = generate("K08", module="s", func="f", args=([{"n": 1}, {"n": 2}, {"n": 3}],), field="n")
assert runs(other, {"s.py": "def f(xs):" + chr(10) + "    return xs[:2]" + chr(10)})
assert not runs(other, {"s.py": "def f(xs):" + chr(10) + "    return xs[::-1]" + chr(10)})
loose = generate("K09", module="s", func="f", cases=[((1,), 1.0)], tol=0.5)
tight = generate("K09", module="s", func="f", cases=[((1,), 1.0)])
off = {"s.py": "def f(x):" + chr(10) + "    return x + 0.4" + chr(10)}
assert runs(loose, off) and not runs(tight, off)
assert runs(tight, {"s.py": "def f(x):" + chr(10) + "    return x + 0.001" + chr(10)})
sub = generate("K10", pattern="*.md", heads=["### X"], head_prefix="### ", contains=["body"])
assert runs(sub, {"a.md": "## Y" + chr(10) + "### X" + chr(10) + "body" + chr(10)})
assert not runs(sub, {"a.md": "## Y" + chr(10) + "### X" + chr(10)})
assert not runs(sub, {})
assert not runs(sub, {"a.md": "### X" + chr(10) + "body", "b.md": "### X" + chr(10) + "body"})
no_regex = generate("K10", pattern="*.md", heads=[])
assert runs(no_regex, {"a.md": "anything"}) and not runs(no_regex, {"a.md": "## H"})
'''

S3 = S2 + r'''
from assert_catalog import build_test
for kind in ("K11", "K12", "K13", "K14", "K15"):
    proof_holds(kind)
assert set(kinds()) == {"K%02d" % n for n in range(1, 16)}
assert describe("K11") == {"id": "K11", "name": "text_format", "required": ["path", "first_regex"], "optional": {"max_first": 72, "blank_second": True, "body_lines": 1}}
assert describe("K15")["required"] == ["previous", "new"] and describe("K12")["name"] == "pure" and describe("K14")["name"] == "form"
nb = generate("K11", path="m.txt", first_regex="^fix: ", blank_second=False, body_lines=2)
assert runs(nb, {"m.txt": "fix: a" + chr(10) + "one" + chr(10) + "two" + chr(10)})
assert not runs(nb, {"m.txt": "fix: a" + chr(10) + "one" + chr(10)})
dotted = generate("K12", module="pkg.mod")
assert runs(dotted, {"pkg/mod.py": "def f():" + chr(10) + "    return 1" + chr(10)})
assert not runs(dotted, {"pkg/mod.py": "from subprocess import run" + chr(10)})
assert not runs(dotted, {"pkg/mod.py": "x = eval('1')" + chr(10)})
assert runs(dotted, {"pkg/mod.py": "import re" + chr(10) + "from json import dumps" + chr(10)})
two = generate("K13", module="s", func="f", cases=[((5,), 3, "[end]"), ((9,), 3, "[end]")])
cut = "def f(n):" + chr(10) + "    return chr(10).join(['x'] * (n if n < 3 else 2) + ([] if n < 3 else ['[end]']))" + chr(10)
assert runs(two, {"s.py": cut}) and not runs(two, {"s.py": "def f(n):" + chr(10) + "    return chr(10).join(['x'] * n)" + chr(10)})
form_ok = {"f.py": "from json import dumps" + chr(10) + chr(10) + chr(10) + "def g(x):" + chr(10) + "    return dumps(x)" + chr(10)}
form = generate("K14", module="f")
assert runs(form, form_ok)
assert not runs(form, {"f.py": "x = 1  # note" + chr(10)})
assert not runs(form, {"f.py": "class A:" + chr(10) + "    " + chr(39) * 3 + "doc" + chr(39) * 3 + chr(10)})
assert not runs(form, {"f.py": chr(34) * 3 + "module doc" + chr(34) * 3 + chr(10) + "x = 1" + chr(10)})
p, n = "from m import f" + chr(10) + "assert f(1) == 1" + chr(10), "from m import f" + chr(10) + chr(10) + "assert f(2) == 2" + chr(10)
assert generate("K15", previous=p, new=n) == "from m import f" + chr(10) + "assert f(1) == 1" + chr(10) + chr(10) + "assert f(2) == 2" + chr(10)
assert generate("K15", previous="a = 1", new="a = 1") == "a = 1" + chr(10)
one = [("K01", {"module": "s", "func": "f", "cases": [((1,), 1)]}), ("K03", {"module": "s", "func": "f"}), ("K06", {"module": "s", "func": "f", "args": (3,)})]
merged = build_test(one)
assert merged.count("from s import f") == 1 and merged.endswith(chr(10)) and not merged.endswith(chr(10) * 2)
assert runs(merged, {"s.py": S}) and not runs(merged, {"s.py": "def f(x):" + chr(10) + "    return x + 1" + chr(10)})
assert build_test([]) == chr(10) or build_test([]) == ""
assert build_test([("K12", {"module": "s"}), ("K14", {"module": "s"})]).count("import ast") == 1
'''

S4 = S3 + r'''
import copy
import assert_catalog
from assert_catalog import check_proofs
assert kinds() == ["K%02d" % n for n in range(1, 16)]
assert check_proofs() == []
broken = copy.deepcopy(PROOFS)
broken["K01"]["mutants"] = [broken["K01"]["good"]]
assert check_proofs(broken) == ["K01: mutant 1 passes"]
broken = copy.deepcopy(PROOFS)
broken["K02"]["good"] = {"sample.py": "def total(xs):" + chr(10) + "    xs.append(1)" + chr(10) + "    return sum(xs)" + chr(10)}
problems = check_proofs(broken)
assert len(problems) == 1 and problems[0].startswith("K02: the good example fails")
broken = copy.deepcopy(PROOFS)
del broken["K03"]
broken["K04"]["mutants"] = []
assert check_proofs(broken) == ["K03: no proof", "K04: no mutant"]
broken = copy.deepcopy(PROOFS)
broken["K05"]["mutants"].append(broken["K05"]["good"])
assert check_proofs(broken) == ["K05: mutant 2 passes"]
assert PROOFS["K01"]["params"]["cases"] == [((2,), 4), ((0,), 0)]
'''

STAGES = [
    {"name": "core", "no_own_check": True,
     "task": '''Create `assert_catalog.py`: a catalog of test patterns that turn parameters into the code of a test. `catalog_proofs.py` (data, already in the workspace) shows for every kind a parameter set, a good example and mutants; do not change it.
Module level data and functions:
- `NAMES`: {"K01": "table", "K02": "unchanged", "K03": "empty", "K04": "bounds", "K05": "tie_order", "K06": "deterministic", "K07": "raises", "K08": "stable_order", "K09": "near", "K10": "file_result", "K11": "text_format", "K12": "pure", "K13": "limit_marker", "K14": "form", "K15": "cumulative"}.
- `SCHEMA`: kind -> (required parameter names as a tuple, optional parameters as a dict of defaults): K01 (module, func, cases) {}; K02 (module, func, args) {}; K03 (module, func) {"values": (None, "", [], {}), "prefix": ()}; K04 (module, func, name, cases) {"prefix": ()}; K05 (module, func, args) {"field": "id"}; K06 (module, func, args) {}; K07 (module, func, cases) {}; K08 (module, func, args) {"field": "id"}; K09 (module, func, cases) {"tol": 0.01}; K10 (pattern, heads) {"head_prefix": "## ", "first_regex": "", "contains": ()}; K11 (path, first_regex) {"max_first": 72, "blank_second": True, "body_lines": 1}; K12 (module,) {}; K13 (module, func, cases) {}; K14 (module,) {}; K15 (previous, new) {}.
- `kinds()`: the sorted list of the kinds that can be generated (in this step K01 to K05 at least; K06 to K15 may raise NotImplementedError until later steps, or already work).
- `describe(kind)`: {"id", "name", "required" (a list), "optional" (a dict)}.
- `generate(kind, **params)`: the code of the test as text, with ONE newline at the end. An unknown kind raises KeyError; a missing required parameter raises ValueError("missing parameter: <name>"); a parameter that is neither required nor optional raises ValueError("unknown parameter: <name>"). The values of `module` (dotted names allowed, every part an identifier), `func` and `name` must be identifiers, else ValueError("bad name: <value!r>"). Values (cases, args, strings, ...) are written into the code with `repr`; they are never pasted as code. `cases` must be a non-empty list (or tuple) of tuples of the right size, else ValueError. The arguments are never modified.
The generated code is run as a script in a folder that holds the module; it raises no error when the function behaves as described and raises an error (AssertionError or any exception) when not. It starts with `from <module> import <func>` for the kinds that have a function. The kinds of this step:
- K01 table: cases = [(args_tuple, expected), ...]; for every case `func(*args) == expected`.
- K02 unchanged: args = a tuple; calling `func(*args)` does not change args (compare a deep copy taken before the call).
- K03 empty: for every v in values, `func(*prefix, v)` runs without an exception.
- K04 bounds: cases = [(value, expected), ...]; for every case `func(*prefix, name=value) == expected`.
- K05 tie_order: `result = func(*args)` is a list of dicts; the list of `item[field]` is in ascending order (equal to its sorted copy).
No comments and no docstrings.''',
     "hidden": {"hidden_cat_1.py": S1}},
    {"name": "more", "no_own_check": True,
     "task": '''In `assert_catalog.py` (keep everything) make the kinds K06 to K10 work in `generate` (and in `kinds()`), by the same rules (identifier checks, `repr`, ONE newline at the end, the schema above):
- K06 deterministic: two calls `func(*copy_of_args)` with separate deep copies of args give equal results.
- K07 raises: cases = [(args_tuple, exception_name, message), ...]; for every case `func(*args)` raises the builtin exception named `exception_name` with `str(error) == message`; when it raises nothing, the code fails. A name that is not the name of a builtin exception class raises ValueError("not an exception: <name!r>") in `generate`.
- K08 stable_order: args = a tuple whose first element is a list of dicts; with before = [item[field] for item in args[0]] and after = [item[field] for item in func(*args)]: after == [key for key in before if key in after].
- K09 near: cases = [(args_tuple, expected_number), ...]; for every case `abs(func(*args) - expected) < tol`.
- K10 file_result (no function, no import of a module): in the current folder exactly one file matches the glob `pattern` (sorted(Path('.').glob(pattern))); its lines that start with `head_prefix`, stripped, are equal to the list `heads`; when `first_regex` is not empty the first line matches it (`re.match`); every string in `contains` occurs in the text of the file.
No comments and no docstrings.''',
     "hidden": {"hidden_cat_2.py": S2}},
    {"name": "rest", "no_own_check": True,
     "task": '''In `assert_catalog.py` make the kinds K11 to K15 work and add `build_test(items)`:
- K11 text_format (no function): the file `path` (read as UTF-8, split into lines): `re.match(first_regex, first line)` and the first line is at most `max_first` characters; when `blank_second` is true there are at least 3 lines and the second line is empty; at least `body_lines` of the lines after the first are not blank.
- K12 pure (no function): the source file of `module` (dots become folders, ending ".py") is parsed with `ast`; it imports none of the modules os, subprocess, socket, urllib, http, requests, shutil, pathlib, sys, ctypes (the first part of the module name counts) and calls none of open, exec, eval, input.
- K13 limit_marker: cases = [(args_tuple, maximum, marker), ...]; for every case `out = func(*args).splitlines()` has at most `maximum` lines and its last line equals `marker`.
- K14 form (no function): the source file of `module` has no comment (use `tokenize`), no docstring (module, classes, functions), all imports at the start of the module (nothing but imports before the last import, none nested in a function or class), and every imported name (the bound name: `as` name, or the first part of a dotted module, or the name of a from-import) is used as a name somewhere in the code.
- K15 cumulative (no function): the code is the lines of `previous` (trailing newlines removed) followed by the lines of `new` that are not identical to a non-blank line of `previous` (blank lines of `new` stay); ONE newline at the end.
- `build_test(items)`: items = [(kind, params_dict), ...]; the generated pieces one after the other; a line that starts with "import " or "from " is kept only the first time it occurs (the first occurrence stays where it is); ONE newline at the end; an empty list gives "\\n" or "".
`kinds()` now returns all 15 kinds. No comments and no docstrings.''',
     "hidden": {"hidden_cat_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Add `check_proofs(proofs=None) -> list` to `assert_catalog.py`: `proofs` defaults to `PROOFS` of `catalog_proofs` (import it inside the function when the argument is None). For every kind of `kinds()` in order: a kind without an entry gives the problem "<kind>: no proof" and nothing else; otherwise the code is `generate(kind, **entry["params"])`, written with the files of `entry["good"]` ({relative path: text}) into a temporary folder and run there as a script with `sys.executable`: when it fails the problem is "<kind>: the good example fails <last line of stderr>" (white space at the end cut); then every mutant of `entry["mutants"]` ({path: text} each) is run the same way: when it passes the problem is "<kind>: mutant <n> passes" (n from 1); an entry with no mutants gives "<kind>: no mutant". The result is the list of problems (empty when all is well). A script that takes longer than 60 seconds counts as failed. `kinds()` returns exactly K01 to K15.
Then read the file once more: no rule may be copied into several places, no comments, no docstrings, all `import` lines at the top, no leftover debug files, `catalog_proofs.py` unchanged. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_cat_full.py": S4}},
]
