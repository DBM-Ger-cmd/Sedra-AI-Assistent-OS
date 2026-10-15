"""G6 adopt_plan (docs/ABLAUF_GESPRAECH_2026-10-13.md step 7, "Uebernahme"). When a candidate has passed, its files have to go into the package, and that has traps the project already met: the old top-level files of the
package are SHIMS (editing them breaks the alias, docs/ENTWICKLUNG.md and the memory "package split"), the self-integration path E1 allows only NEW files, and every module needs its test. `adopt_plan.py` makes the PLAN of
such an adoption from names alone (no file is read or written): which candidate file goes where, what is refused and why, which tests must run, whether a Captain's gate is needed, and the German text for the chat; the actual
copying is done by the caller with the pairs this module returns. GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/adopt_plan)."""

NOTES = '''# Notes for adopt_plan
Pure Python 3 standard library (`posixpath` is allowed), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top. Texts contain the characters ü ö (UTF-8 source).
All paths are texts with "/" as the separator; `candidate_files` are relative to the candidate folder, `existing`, `shims`, `target_dir` and `tests_dir` are relative to the repository root.
'''

HEAD = r'''
CAND = ["NOTES.md", "assert_catalog.py", "catalog_proofs.py", "hidden_x.py", "check_it.py", "pkg/__pycache__/x.pyc", "pkg/mod.py", "readme.txt", "devvm_tools.py"]
EXISTING = ["runtime/src/guppi_runtime/devenv/catalog_proofs.py", "runtime/src/guppi_runtime/devenv/devvm_tools.py", "runtime/tests/test_catalog_proofs.py"]
SHIMS = ["runtime/src/guppi_runtime/devenv/devvm_tools.py"]
D = "runtime/src/guppi_runtime/devenv"
'''

S1 = HEAD + r'''
from adopt_plan import plan_adoption
plan = plan_adoption(CAND, D, EXISTING, SHIMS)
assert plan["entries"] == [
    {"source": "NOTES.md", "target": None, "action": "skip", "reason": "helper file of the build"},
    {"source": "assert_catalog.py", "target": D + "/assert_catalog.py", "action": "create", "reason": ""},
    {"source": "catalog_proofs.py", "target": D + "/catalog_proofs.py", "action": "replace", "reason": "exists: review the diff"},
    {"source": "check_it.py", "target": None, "action": "skip", "reason": "helper file of the build"},
    {"source": "devvm_tools.py", "target": D + "/devvm_tools.py", "action": "refuse", "reason": "shim: edit the file in the subpackage"},
    {"source": "hidden_x.py", "target": None, "action": "skip", "reason": "helper file of the build"},
    {"source": "pkg/__pycache__/x.pyc", "target": None, "action": "skip", "reason": "cache"},
    {"source": "pkg/mod.py", "target": D + "/pkg/mod.py", "action": "create", "reason": ""},
    {"source": "readme.txt", "target": None, "action": "skip", "reason": "not a module"}]
only_new = plan_adoption(["a.py", "sub/b.py"], "d", [])
assert [(e["source"], e["target"], e["action"]) for e in only_new["entries"]] == [("a.py", "d/a.py", "create"), ("sub/b.py", "d/sub/b.py", "create")]
assert plan_adoption(["NOTES.md", "hidden_1.py", "check_all.py", "data.json"], "d", [])["entries"][0]["action"] == "skip"
assert [e["action"] for e in plan_adoption(["b.py", "a.py"], "d", ["d/a.py"])["entries"]] == ["replace", "create"]
assert plan_adoption([], "d", [])["entries"] == []
cand, existing, shims = list(CAND), list(EXISTING), list(SHIMS)
plan_adoption(cand, D, existing, shims)
assert (cand, existing, shims) == (list(CAND), list(EXISTING), list(SHIMS))
assert plan_adoption(tuple(CAND), D, set(EXISTING), frozenset(SHIMS))["entries"] == plan["entries"]
'''

S2 = S1 + r'''
assert plan["tests"] == [{"module": D + "/assert_catalog.py", "test": "runtime/tests/test_assert_catalog.py", "exists": False}, {"module": D + "/catalog_proofs.py", "test": "runtime/tests/test_catalog_proofs.py", "exists": True},
                         {"module": D + "/pkg/mod.py", "test": "runtime/tests/test_mod.py", "exists": False}]
assert plan["needs_gate"] is True and plan["ok"] is False
assert plan_adoption(["a.py"], "d", [])["ok"] is True and plan_adoption(["a.py"], "d", [])["needs_gate"] is True
nothing = plan_adoption(["NOTES.md", "x.txt"], "d", [])
assert nothing["needs_gate"] is False and nothing["ok"] is True and nothing["tests"] == []
refused = plan_adoption(["a.py"], "d", ["d/a.py"], ["d/a.py"])
assert refused["entries"][0]["action"] == "refuse" and refused["needs_gate"] is False and refused["ok"] is False and refused["tests"] == []
e1 = plan_adoption(CAND, D, EXISTING, (), mode="e1")
assert [(e["source"], e["action"], e["reason"]) for e in e1["entries"] if e["action"] in ("replace", "refuse")] == [("catalog_proofs.py", "refuse", "e1 allows only new files"), ("devvm_tools.py", "refuse", "e1 allows only new files")]
assert e1["ok"] is False and plan_adoption(["new.py"], "d", [], (), mode="e1")["ok"] is True
assert plan_adoption(CAND, D, EXISTING, SHIMS, mode="e1")["entries"][4]["reason"] == "shim: edit the file in the subpackage"
two = plan_adoption(["a/x.py", "b/x.py"], "d", [], tests_dir="t")
assert two["tests"] == [{"module": "d/a/x.py", "test": "t/test_x.py", "exists": False}]
custom = plan_adoption(["m.py"], "d", ["tests/test_m.py"], tests_dir="tests")
assert custom["tests"] == [{"module": "d/m.py", "test": "tests/test_m.py", "exists": True}]
'''

S3 = S2 + r'''
from adopt_plan import describe, copy_pairs
text = describe(plan)
assert text == chr(10).join(["Übernahmeplan (9 Dateien)", "  übersprungen: NOTES.md (helper file of the build)", "  neu: " + D + "/assert_catalog.py", "  ersetzen: " + D + "/catalog_proofs.py (exists: review the diff)",
    "  übersprungen: check_it.py (helper file of the build)", "  abgelehnt: " + D + "/devvm_tools.py (shim: edit the file in the subpackage)", "  übersprungen: hidden_x.py (helper file of the build)",
    "  übersprungen: pkg/__pycache__/x.pyc (cache)", "  neu: " + D + "/pkg/mod.py", "  übersprungen: readme.txt (not a module)", "Test fehlt: runtime/tests/test_assert_catalog.py (neuer Test nötig)",
    "Tests: runtime/tests/test_catalog_proofs.py", "Test fehlt: runtime/tests/test_mod.py (neuer Test nötig)", "Freigabe nötig: ja", "Plan ausführbar: nein"]) + chr(10)
ok_plan = plan_adoption(["a.py", "NOTES.md"], "d", [])
assert describe(ok_plan) == chr(10).join(["Übernahmeplan (2 Dateien)", "  übersprungen: NOTES.md (helper file of the build)", "  neu: d/a.py", "Test fehlt: runtime/tests/test_a.py (neuer Test nötig)", "Freigabe nötig: ja", "Plan ausführbar: ja"]) + chr(10)
assert describe(plan_adoption([], "d", [])) == chr(10).join(["Übernahmeplan (0 Dateien)", "Freigabe nötig: nein", "Plan ausführbar: ja"]) + chr(10)
assert copy_pairs(ok_plan, "cand/dir") == [("cand/dir/a.py", "d/a.py")]
mixed = plan_adoption(["a.py", "b.py", "NOTES.md"], "d", ["d/b.py"])
assert copy_pairs(mixed, "c") == [("c/a.py", "d/a.py"), ("c/b.py", "d/b.py")]
assert copy_pairs(plan_adoption([], "d", []), "c") == [] and copy_pairs(plan_adoption(["NOTES.md"], "d", []), "c") == []
try:
    copy_pairs(plan, "c")
except ValueError as error:
    assert str(error) == "plan_not_ok"
else:
    raise AssertionError("no ValueError")
snapshot = repr(ok_plan)
describe(ok_plan)
copy_pairs(ok_plan, "x")
assert repr(ok_plan) == snapshot
'''

STAGES = [
    {"name": "classify", "no_own_check": True,
     "task": '''Create `adopt_plan.py` (the path rules are in NOTES.md). `plan_adoption(candidate_files, target_dir, existing, shims=(), mode="e2", tests_dir="runtime/tests") -> dict` returns {"entries": [...], "tests": [...], "needs_gate": bool, "ok": bool}. In this step only "entries" matters (the others may be present with any value). The candidate files are sorted (plain string order) and each gives one entry {"source": the file, "target": ..., "action": ..., "reason": ...}:
- A file that is no module of the package is skipped: action "skip", target None. The reasons, checked in this order: any path part is "__pycache__": "cache"; the file name (last part) is "NOTES.md" or starts with "hidden_" or "check_": "helper file of the build"; the name does not end with ".py": "not a module".
- Otherwise the target is `target_dir` + "/" + the source path (use `posixpath.join`). If the target is in `shims`: action "refuse", reason "shim: edit the file in the subpackage". Else if the target is in `existing` (in this step always as in mode "e2"): action "replace", reason "exists: review the diff". Else action "create", reason "".
`existing` and `shims` can be lists, tuples or sets; nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_adopt_1.py": S1}},
    {"name": "rules", "no_own_check": True,
     "task": '''In `adopt_plan.py` (keep everything) complete `plan_adoption`. (1) Mode "e1" (the self-integration path allows only NEW files): a target that exists but is no shim gets action "refuse", reason "e1 allows only new files" (a shim is still refused with the shim reason first). (2) "tests": for every entry with action "create" or "replace", in the order of the entries, one dict {"module": the target, "test": `tests_dir` + "/test_" + the base name of the source (`posixpath.basename`), "exists": the test path is in `existing`}; a test path that was already listed is not listed again. (3) "needs_gate": true when at least one entry has action "create" or "replace". (4) "ok": false when at least one entry has action "refuse", otherwise true. Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_adopt_2.py": S2}},
    {"name": "text", "no_own_check": True,
     "task": '''In `adopt_plan.py` add `describe(plan) -> str` and `copy_pairs(plan, candidate_dir) -> list`. `describe`: the plan as German text, lines joined with a newline and ONE newline at the end: first "Übernahmeplan (<number of entries> Dateien)"; then one line per entry "  <word>: <name>" + " (<reason>)" when the reason is not empty, with the word "neu" for create, "ersetzen" for replace, "abgelehnt" for refuse, "übersprungen" for skip, and the name = the target, or the source when there is no target; then one line per test: "Tests: <test>" when it exists, otherwise "Test fehlt: <test> (neuer Test nötig)"; then "Freigabe nötig: ja" or "nein" (needs_gate); the last line "Plan ausführbar: ja" or "nein" (ok). `copy_pairs`: the list of (source path, target) tuples for the entries with action "create" or "replace", in the order of the entries, with the source path = `posixpath.join(candidate_dir, source)`; a plan that is not ok raises ValueError("plan_not_ok"). Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_adopt_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `adopt_plan.py` once more: no rule may be copied into several places (the list of actions that change a file, the word for an action), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_adopt_full.py": S3}},
]
