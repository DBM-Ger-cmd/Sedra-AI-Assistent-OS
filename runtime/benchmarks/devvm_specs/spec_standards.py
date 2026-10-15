"""G2 spec_standards (docs/ABLAUF_GESPRAECH_2026-10-13.md; Captain 2026-10-13: "Tests werden nach Standardvorgaben getestet, die vorher erstellt werden"). The test standards T1 to T8 as one function: `check_request` takes a request of
`build_request` (the result of a conversation: stages with catalog checks) and checks it WITHOUT a GPU: T1 the request is valid, T2 the catalog kinds it uses pass their proofs, T3 the examples do not contradict each other, T4 the first
stage fails on the seed, T6 no absolute path or address in the parameters, T7 every stage test passes on a pattern (a reference or an existing module), T8 a mutation probe on that pattern (a mutant that no test catches shows a test gap).
What cannot be checked (no seed, no pattern) is NOT hidden: it is listed in `unchecked`, so the spec card can say "not checked against a pattern". (T5, one statement per assert, holds for catalog code by construction.) Seed: benchmarks/g2_seed
(assert_catalog.py, catalog_proofs.py, build_request.py, all finished). GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/spec_standards)."""

NOTES = '''# Notes for spec_standards
`assert_catalog.py`, `catalog_proofs.py` and `build_request.py` are already in the workspace and work (import them with `import assert_catalog`, `import build_request`, `from catalog_proofs import PROOFS`); do not change them. Pure Python 3 standard library (`subprocess`, `tempfile`, `shutil`, `pathlib`, `re`, `os`, `sys` are allowed), never modify the arguments and never write into the folders `tree` and `seed` (work on copies in a temporary folder), no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top.
The request format is the one of `build_request` (see build_request.validate_request). A "tree" is a folder with python files: a seed (the start of the build) or a pattern (code that satisfies the tests).
'''

HEAD = r'''
import os, tempfile
from pathlib import Path
import assert_catalog, build_request
from catalog_proofs import PROOFS
import copy

def tree(files):
    root = Path(tempfile.mkdtemp())
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root

def listing(root):
    return sorted((p.relative_to(root).as_posix(), p.read_text(encoding="utf-8")) for p in Path(root).rglob("*") if p.is_file())

def only(report, *tags):
    return [p for p in report["problems"] if p.startswith(tags)]

GOOD = {"sample.py": "def double(x):" + chr(10) + "    if isinstance(x, (int, float)) and not isinstance(x, bool):" + chr(10) + "        return x * 2" + chr(10) + "    return x" + chr(10)}
REQ = {"name": "doubler", "title": "Verdoppler", "notes": "Pure Python.", "stages": [
    {"name": "basic", "task": "Create sample.py with double(x) returning x * 2.", "checks": [{"kind": "K01", "params": {"module": "sample", "func": "double", "cases": [((2,), 4), ((0,), 0)]}}]},
    {"name": "safe", "task": "t2", "checks": [{"kind": "K02", "params": {"module": "sample", "func": "double", "args": ([1],)}}, {"kind": "K03", "params": {"module": "sample", "func": "double"}}]}]}
WEAK = {"name": "weak", "stages": [{"name": "w", "task": "t", "checks": [{"kind": "K03", "params": {"module": "sample", "func": "double"}}]}]}
'''

S1 = HEAD + r'''
from spec_standards import check_request, ok
r = check_request(REQ)
assert set(r) == {"problems", "warnings", "unchecked"} and only(r, "T1", "T3", "T6") == [] and ok(r)
assert check_request({}) == {"problems": ["T1: bad name", "T1: no stages"], "warnings": [], "unchecked": [t + ": not checked (invalid request)" for t in ("T2", "T3", "T4", "T6", "T7", "T8")]}
bad = {"name": "b", "stages": [
    {"name": "s1", "task": "t", "checks": [{"kind": "K01", "params": {"module": "m", "func": "f", "cases": [((1,), 1), ((1,), 2)]}}, {"kind": "K04", "params": {"module": "m", "func": "f", "name": "n", "cases": [(1, 1)]}}]},
    {"name": "s2", "task": "t", "checks": [{"kind": "K01", "params": {"module": "m", "func": "f", "cases": [((1,), 3)]}}, {"kind": "K04", "params": {"module": "m", "func": "f", "name": "n", "cases": [(1, 2)]}},
                                          {"kind": "K10", "params": {"pattern": "C:/docs/*.md", "heads": []}}, {"kind": "K11", "params": {"path": "/abs/x.txt", "first_regex": "^a"}}]}]}
assert only(check_request(bad), "T1", "T3", "T6") == ["T3: stage s1: same input, different results: (1,)", "T3: stage s2: same input, different results: (1,)", "T3: stage s2: same input, different results: 1",
                                                      "T6: stage s2 check 3: absolute path or address in the parameters", "T6: stage s2 check 4: absolute path or address in the parameters"]
assert not ok(check_request(bad)) and ok({"problems": [], "warnings": ["w"], "unchecked": ["u"]}) and not ok({"problems": ["p"], "warnings": [], "unchecked": []})
fine = {"name": "f", "stages": [
    {"name": "a", "task": "t", "checks": [{"kind": "K01", "params": {"module": "m", "func": "f", "cases": [((1,), 1), ((2,), 2)]}}, {"kind": "K04", "params": {"module": "m", "func": "f", "name": "n", "prefix": (1,), "cases": [(1, 1)]}}]},
    {"name": "b", "task": "t", "checks": [{"kind": "K01", "params": {"module": "m", "func": "g", "cases": [((1,), 5)]}}, {"kind": "K01", "params": {"module": "m", "func": "f", "cases": [((1,), 1)]}},
                                          {"kind": "K04", "params": {"module": "m", "func": "f", "name": "n", "prefix": (2,), "cases": [(1, 9)]}}, {"kind": "K09", "params": {"module": "m", "func": "f", "cases": [((1,), 1.0), ((1,), 7.0)]}}]}]}
assert only(check_request(fine), "T3") == []
leaky = {"name": "l", "stages": [{"name": "a", "task": "t", "checks": [{"kind": "K03", "params": {"module": "m", "func": "f", "values": ("see https://example.org/x",)}},
                                                                        {"kind": "K03", "params": {"module": "m", "func": "f", "prefix": (None,), "values": ("/tmp/y",)}},
                                                                        {"kind": "K03", "params": {"module": "m", "func": "f", "values": ("D:" + chr(92) + "z",)}},
                                                                        {"kind": "K10", "params": {"pattern": "docs/*.md", "heads": ["## A"], "first_regex": "^/?x"}}]}]}
assert only(check_request(leaky), "T6") == ["T6: stage a check 1: absolute path or address in the parameters", "T6: stage a check 2: absolute path or address in the parameters", "T6: stage a check 3: absolute path or address in the parameters"]
snapshot = repr(REQ) + repr(bad)
check_request(REQ)
check_request(bad)
assert repr(REQ) + repr(bad) == snapshot
'''

S2 = S1 + r'''
broken = copy.deepcopy(PROOFS)
broken["K03"]["mutants"] = [broken["K03"]["good"]]
broken["K15"]["mutants"] = []
assert only(check_request(REQ, proofs=broken), "T2") == ["T2: K03: mutant 1 passes"]
broken = copy.deepcopy(PROOFS)
del broken["K02"]
assert only(check_request(REQ, proofs=broken), "T2") == ["T2: K02: no proof"]
broken = copy.deepcopy(PROOFS)
broken["K01"]["good"] = {"sample.py": "def double(x):" + chr(10) + "    return 0" + chr(10)}
problems = only(check_request(REQ, proofs=broken), "T2")
assert len(problems) == 1 and problems[0].startswith("T2: K01: the good example fails")
assert only(check_request(REQ), "T2") == [] and only(check_request(REQ, proofs=PROOFS), "T2") == []
assert only(check_request({}, proofs=broken), "T2") == []
before = repr(broken)
check_request(REQ, proofs=broken)
assert repr(broken) == before
'''

S3 = S2 + r'''
assert [u for u in check_request(REQ)["unchecked"]] == ["T4: no seed given", "T7: no pattern given", "T8: no pattern given"]
seed_ok = tree({"other.py": "x = 1" + chr(10)})
r = check_request(REQ, seed=seed_ok)
assert only(r, "T4") == [] and r["unchecked"] == ["T7: no pattern given", "T8: no pattern given"]
good_tree = tree(GOOD)
r = check_request(REQ, seed=good_tree)
assert only(r, "T4") == ["T4: stage basic already passes on the seed"]
r = check_request(REQ, tree=good_tree, seed=seed_ok)
assert only(r, "T4", "T7") == [] and r["unchecked"] == [] and [w for w in r["warnings"] if not w.startswith("T8")] == []
wrong = tree({"sample.py": "def double(x):" + chr(10) + "    return x + 2" + chr(10)})
r = check_request(REQ, tree=wrong, seed=seed_ok)
assert only(r, "T7") == ["T7: stage basic fails on the pattern", "T7: stage safe fails on the pattern"] and r["unchecked"] == ["T8: not checked (T7 failed)"]
half = tree({"sample.py": "def double(x):" + chr(10) + "    return x * 2" + chr(10)})
r = check_request(REQ, tree=half)
assert only(r, "T7") == ["T7: stage safe fails on the pattern"] and r["unchecked"] == ["T4: no seed given", "T8: not checked (T7 failed)"]
assert check_request({}, tree=good_tree, seed=good_tree)["problems"] == ["T1: bad name", "T1: no stages"]
snap = (listing(good_tree), listing(seed_ok), listing(wrong))
check_request(REQ, tree=good_tree, seed=seed_ok)
check_request(REQ, tree=wrong, seed=good_tree)
assert (listing(good_tree), listing(seed_ok), listing(wrong)) == snap
assert only(check_request(REQ, tree=str(good_tree), seed=str(seed_ok), timeout=30), "T4", "T7") == []
'''

S4 = S3 + r'''
survivors = lambda rep: [w for w in rep["warnings"] if w.startswith("T8")]
assert survivors(check_request(REQ, tree=good_tree, seed=seed_ok)) == ["T8: mutant survives: sample.py line 4: 'return x' -> 'return None'"]
r = check_request(WEAK, tree=good_tree)
assert survivors(r) == ["T8: mutant survives: sample.py line 3: 'return x * 2' -> 'return None'", "T8: mutant survives: sample.py line 4: 'return x' -> 'return None'"]
assert survivors(check_request(WEAK, tree=good_tree, mutants=1)) == ["T8: mutant survives: sample.py line 3: 'return x * 2' -> 'return None'"]
assert survivors(check_request(WEAK, tree=good_tree, mutants=0)) == [] and ok(check_request(WEAK, tree=good_tree))
same = tree({"m.py": "def same(a, b):" + chr(10) + "    return a == b" + chr(10)})
strong = {"name": "s", "stages": [{"name": "a", "task": "t", "checks": [{"kind": "K01", "params": {"module": "m", "func": "same", "cases": [((1, 1), True), ((1, 2), False)]}}]}]}
weak_same = {"name": "w", "stages": [{"name": "a", "task": "t", "checks": [{"kind": "K03", "params": {"module": "m", "func": "same", "prefix": (0,)}}]}]}
assert survivors(check_request(strong, tree=same)) == []
assert survivors(check_request(weak_same, tree=same)) == ["T8: mutant survives: m.py line 2: 'return a == b' -> 'return None'", "T8: mutant survives: m.py line 2: '==' -> '!='"]
nested = tree({"pkg/__init__.py": "", "pkg/calc.py": "def add(a, b):" + chr(10) + "    return a + b" + chr(10)})
strong_add = {"name": "s", "stages": [{"name": "a", "task": "t", "checks": [{"kind": "K01", "params": {"module": "pkg.calc", "func": "add", "cases": [((1, 2), 3)]}}]}]}
weak_add = {"name": "w", "stages": [{"name": "a", "task": "t", "checks": [{"kind": "K12", "params": {"module": "pkg.calc"}}]}]}
assert survivors(check_request(strong_add, tree=nested)) == []
assert survivors(check_request(weak_add, tree=nested)) == ["T8: mutant survives: pkg/calc.py line 2: 'return a + b' -> 'return None'", "T8: mutant survives: pkg/calc.py line 2: ' + ' -> ' - '"]
text = tree({"t.py": "VALUE = 'a - b'" + chr(10) + "def f(x):" + chr(10) + "    return VALUE" + chr(10)})
weak_t = {"name": "w", "stages": [{"name": "a", "task": "t", "checks": [{"kind": "K03", "params": {"module": "t", "func": "f"}}]}]}
assert survivors(check_request(weak_t, tree=text)) == ["T8: mutant survives: t.py line 1: ' - ' -> ' + '", "T8: mutant survives: t.py line 3: 'return VALUE' -> 'return None'"]
snap = (listing(good_tree), listing(same), listing(nested))
check_request(WEAK, tree=good_tree)
check_request(weak_same, tree=same)
check_request(weak_add, tree=nested)
assert (listing(good_tree), listing(same), listing(nested)) == snap
'''

STAGES = [
    {"name": "basic", "no_own_check": True,
     "task": '''Create `spec_standards.py` (it uses `import assert_catalog`, `import build_request`, `from catalog_proofs import PROOFS`). `check_request(request, *, tree=None, seed=None, proofs=None, mutants=30, timeout=60) -> dict` returns {"problems": [...], "warnings": [...], "unchecked": [...]} (lists of texts). In this step it does T1, T3 and T6, in this order of problems (later steps add T2 before T3 and T4, T7 after T6):
- T1: when `build_request.validate_request(request)` finds problems, the result is {"problems": ["T1: <problem>", ...] (all of them, in order), "warnings": [], "unchecked": ["T2: not checked (invalid request)", "T3: ...", "T4: ...", "T6: ...", "T7: ...", "T8: ..."] (the six tags T2, T3, T4, T6, T7, T8 in this order, each as "<tag>: not checked (invalid request)")} and nothing else is done.
- T3 (contradictions): look at the checks of kind K01 and K04 over the WHOLE request, stage by stage and case by case. Cases belong together when the kind is the same and the parameters `module` and `func` (K04 also `name` and `prefix`, default ()) are equal. For K01 a case is (args, expected), the input is `args`; for K04 a case is (value, expected), the input is `value`. When a case has the same input (compared with `repr`) as an EARLIER case of the same group (in an earlier stage or earlier in the list) but a different expected result (compared with `repr`), the problem is "T3: stage <stage name>: same input, different results: <input!r>". The first case seen of an input is the reference.
- T6 (no absolute paths or addresses): for every check n of every stage (n from 1) look at ALL strings in its `params` (nested in lists, tuples, dicts, also dict keys): a string that starts with a drive letter and a colon and "/" or "\\" (re `^[A-Za-z]:[\\\\/]`), or starts with "/", or holds "http://" or "https://", gives ONE problem per check: "T6: stage <stage name> check <n>: absolute path or address in the parameters".
`ok(report) -> bool` is true when the problems list is empty. Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_std_1.py": S1}},
    {"name": "proofs", "no_own_check": True,
     "task": '''In `spec_standards.py` (keep everything) add T2: the catalog kinds the request USES must pass their proofs. `proofs` (default `PROOFS`) is a dict like PROOFS. For the used kinds only, run `assert_catalog.check_proofs` on a dict that holds the entries of the used kinds (a used kind missing in `proofs` is simply not in that dict, so check_proofs reports "<kind>: no proof"); of the lines it returns keep only those of used kinds (the text before the first ":" is the kind) and add each as a problem "T2: <line>". The T2 problems come BEFORE the T3 problems. A request that T1 refuses never reaches T2. Neither the request nor `proofs` is modified. No comments and no docstrings.''',
     "hidden": {"hidden_std_2.py": S2}},
    {"name": "trees", "no_own_check": True,
     "task": '''In `spec_standards.py` add T4 and T7. Use `build_request.stage_tests(request)` (the cumulative test text of every stage). A test text is run by writing it as `t_run.py` into a COPY of the tree (a temporary folder; ignore `__pycache__`; with no tree an empty folder) and running `sys.executable t_run.py` there (UTF-8: set the environment variable PYTHONUTF8=1 and decode with encoding utf-8, errors replace), with the `timeout` in seconds; exit code 0 = passed. `tree` and `seed` may be a path text or a Path; nothing is ever written into them.
- T4: when `seed` is None, `unchecked` gets "T4: no seed given". Otherwise the test of the FIRST stage runs on the seed; when it PASSES the problem is "T4: stage <first stage name> already passes on the seed" (a build that starts from a passing seed would prove nothing).
- T7: when `tree` is None, `unchecked` gets "T7: no pattern given" and "T8: no pattern given" (in this order, after the T4 entry). Otherwise every stage test runs on the tree; each stage that does not pass gives "T7: stage <stage name> fails on the pattern" (in stage order); when at least one failed, `unchecked` gets "T8: not checked (T7 failed)" (after the T4 entry).
Order of the problems: T1 (nothing else then), T2, T3, T6, T4, T7. The order of `unchecked` entries: T4, then T7/T8. No comments and no docstrings.''',
     "hidden": {"hidden_std_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''In `spec_standards.py` add T8, the mutation probe, for the case that `tree` is given and all stage tests passed (T7 found nothing). A mutant is the pattern with ONE change in ONE `.py` file of the tree (found with `rglob("*.py")`, files sorted by path, `__pycache__` files not touched). The changes (spots) of a file's text: every match of the regex `return [^\\n]+` replaced by `return None`; and for each pair in this module level tuple OPERATORS = (("==", "!="), ("!=", "=="), (" + ", " - "), (" - ", " + "), (" < ", " >= "), (" > ", " <= "), ("True", "False"), ("False", "True")) every occurrence of the first text replaced by the second. All spots of a file are ordered by their start position in the file (ties: end position, then texts); a mutant that does not compile (`compile(text, name, "exec")` raises SyntaxError) is skipped and does not count. At most `mutants` mutants are made in total (over all files, in that order); with `mutants=0` none.
Each mutant is written into a COPY of the tree and the test of the LAST stage (the one that holds all checks) runs there as before. A mutant that PASSES that test survives and gives the warning "T8: mutant survives: <path of the file relative to the tree with />" + " line <line number of the start of the change, from 1>: <the old text!r> -> <the new text!r>" (for the return changes the old text is the whole matched `return ...` text). The warnings come in the order of the mutants. Without a tree, or when T7 failed, no mutants are made. `tree` is never written. Then read the file once more: no rule may be copied into several places (running a test text in a copy of a tree exists once), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_std_full.py": S4}},
]
