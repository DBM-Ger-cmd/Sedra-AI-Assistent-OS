"""G1 build_request (docs/ABLAUF_GESPRAECH_2026-10-13.md; Captain 2026-10-13: the tests come from the examples of the conversation, GUPPI writes the asserts, the Captain confirms a spec card; a catalog of test patterns
saves new tests). `build_request.py` takes the RESULT of a conversation as data (name, title, notes, stages with a task text and a list of catalog checks) and makes two things from it: the text of a devvm spec file
(NOTES and STAGES with the hidden tests that `assert_catalog.build_test` writes, each stage test cumulative) and the spec card the Captain reads and confirms. Pure functions; the conversation itself and the files are
handled elsewhere. Seed: benchmarks/g1_seed (the finished test catalog: assert_catalog.py and catalog_proofs.py). GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/build_request)."""

NOTES = '''# Notes for build_request
`assert_catalog.py` (the test catalog, import it with `import assert_catalog`) and `catalog_proofs.py` are already in the workspace and work; do not change them. Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top. Texts contain the characters ä ü – · (UTF-8 source).
A request is a dict: {"name": ..., "title": ..., "notes": ..., "stages": [{"name": ..., "task": ..., "checks": [{"kind": "K01", "params": {...}}, ...]}, ...]}. `kind` is a kind of the catalog (assert_catalog.kinds()), `params` are the parameters of assert_catalog.generate(kind, **params).
'''

HEAD = r'''
import subprocess, sys, tempfile
from pathlib import Path
import assert_catalog
from catalog_proofs import PROOFS

def runs(code, files):
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in files.items():
            target = Path(tmp) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        (Path(tmp) / "t_run.py").write_text(code, encoding="utf-8")
        return subprocess.run([sys.executable, "t_run.py"], cwd=tmp, capture_output=True, text=True, timeout=60).returncode == 0

GOOD = {"sample.py": "def double(x):" + chr(10) + "    if isinstance(x, (int, float)) and not isinstance(x, bool):" + chr(10) + "        return x * 2" + chr(10) + "    return x" + chr(10)}
BAD_NONE = {"sample.py": "def double(x):" + chr(10) + "    return x * 2" + chr(10)}
BAD_CASE = {"sample.py": "def double(x):" + chr(10) + "    return x + 2 if isinstance(x, int) else x" + chr(10)}
REQ = {"name": "doubler", "title": "Verdoppler", "notes": "Pure Python.", "stages": [
    {"name": "basic", "task": "Create sample.py with double(x) returning x * 2.", "checks": [{"kind": "K01", "params": {"module": "sample", "func": "double", "cases": [((2,), 4), ((0,), 0)]}}]},
    {"name": "safe", "task": "double must not change a list argument and must accept None.",
     "checks": [{"kind": "K02", "params": {"module": "sample", "func": "double", "args": ([1],)}}, {"kind": "K03", "params": {"module": "sample", "func": "double"}}]}]}
'''

S1 = HEAD + r'''
from build_request import validate_request, cases_from_examples
assert validate_request(REQ) == []
bad = {"name": "1x", "stages": [{"name": "a b", "task": ""}, {"name": "a", "task": "t", "checks": []},
                                {"name": "a", "task": "t", "checks": [{"kind": "K99", "params": {}}, {"kind": "K01", "params": {"module": "m", "func": "f"}}]}]}
assert validate_request(bad) == ["bad name", "bad stage name: 'a b'", "stage a: no checks", "stage name twice: a", "stage a check 1: unknown kind K99", "stage a check 2: missing parameter: cases"]
assert validate_request({}) == ["bad name", "no stages"]
assert validate_request({"name": "ok", "stages": "x"}) == ["no stages"] and validate_request({"name": "ok", "stages": []}) == ["no stages"]
assert validate_request({"name": "ok", "stages": [{"name": "s", "task": "   ", "checks": [{"kind": "K12", "params": {"module": "pure"}}]}]}) == ["stage s: no task"]
assert validate_request({"name": "ok", "stages": [{"name": "s", "task": "t"}]}) == ["stage s: no checks"]
assert validate_request({"name": "ok", "stages": [{"name": "s", "task": "t", "checks": [{"kind": "K01", "params": 5}, 7]}]}) == ["stage s check 1: bad check", "stage s check 2: bad check"]
assert validate_request({"name": "ok", "stages": [{"name": "s", "task": "t", "checks": [{"kind": "K01", "params": {"module": "m x", "func": "f", "cases": [((1,), 1)]}}]}]}) == ["stage s check 1: bad name: 'm x'"]
assert validate_request({"name": "ok", "stages": [{"name": "s", "task": "t", "checks": [{"kind": "K07", "params": {"module": "m", "func": "f", "cases": [((1,), "NoSuchError", "x")]}}]}]}) == ["stage s check 1: not an exception: 'NoSuchError'"]
assert validate_request({"name": "_ok1", "stages": [{"name": "_s2", "task": "t", "checks": [{"kind": "K12", "params": {"module": "pure"}}]}]}) == []
before = repr(REQ)
validate_request(REQ)
assert repr(REQ) == before
assert cases_from_examples([{"input": [1, 2], "output": 3}, {"input": "a", "output": "b"}, {"input": (5,), "output": None}]) == [((1, 2), 3), (("a",), "b"), ((5,), None)]
for given in ([], "x", None, [{"input": 1}], [{"output": 1}], [5], [{"input": 1, "output": 1}, "z"]):
    try:
        cases_from_examples(given)
    except ValueError as error:
        assert str(error) in ("no examples", "bad example"), str(error)
    else:
        raise AssertionError(repr(given))
for given, text in (([], "no examples"), ("x", "no examples"), ([{"input": 1}], "bad example"), ([5], "bad example")):
    try:
        cases_from_examples(given)
    except ValueError as error:
        assert str(error) == text
'''

S2 = S1 + r'''
from build_request import stage_tests, render_spec
tests = stage_tests(REQ)
first = REQ["stages"][0]["checks"][0]
second = REQ["stages"][1]["checks"]
assert len(tests) == 2
assert tests[0] == assert_catalog.build_test([("K01", first["params"])])
assert tests[1] == assert_catalog.build_test([("K01", first["params"]), ("K02", second[0]["params"]), ("K03", second[1]["params"])])
assert runs(tests[0], GOOD) and runs(tests[1], GOOD)
assert not runs(tests[0], BAD_CASE) and not runs(tests[1], BAD_CASE)
assert runs(tests[0], BAD_NONE) and not runs(tests[1], BAD_NONE)
text = render_spec(REQ)
assert isinstance(text, str) and text.endswith(chr(10)) and text == render_spec(REQ)
space = {}
exec(compile(text, "spec", "exec"), space)
assert space["TITLE"] == "Verdoppler" and space["NOTES"] == "Pure Python." and len(space["STAGES"]) == 2
for number, (stage, code) in enumerate(zip(space["STAGES"], tests), 1):
    assert stage["name"] == REQ["stages"][number - 1]["name"] and stage["task"] == REQ["stages"][number - 1]["task"] and stage["no_own_check"] is True
    assert stage["hidden"] == {"hidden_doubler_" + str(number) + ".py": code}
assert all(list(stage) == ["name", "no_own_check", "task", "hidden"] for stage in space["STAGES"])
tricky = {"name": "tricky", "title": "Say " + chr(34) * 3 + "hi" + chr(34) * 3 + "  now", "notes": "line1" + chr(10) + "it" + chr(39) + "s", "stages": [
    {"name": "s", "task": "Task with " + chr(34) + "quotes" + chr(34) + " and " + chr(39) + " and " + chr(92) + "n and ä – ü" + chr(10) + "second line", "checks": [{"kind": "K12", "params": {"module": "pure"}}]}]}
other = {}
exec(compile(render_spec(tricky), "spec", "exec"), other)
assert other["TITLE"] == "Say " + chr(34) * 3 + "hi" + chr(34) * 3 + " now" and other["NOTES"] == "line1" + chr(10) + "it" + chr(39) + "s"
assert other["STAGES"][0]["task"] == tricky["stages"][0]["task"]
assert render_spec({"name": "n", "stages": [{"name": "s", "task": "t", "checks": [{"kind": "K12", "params": {"module": "pure"}}]}]}).count("TITLE = 'n'") == 1
for broken, message in ((dict(REQ, name="bad name"), "invalid request: bad name"), (dict(REQ, stages=[]), "invalid request: no stages")):
    try:
        render_spec(broken)
    except ValueError as error:
        assert str(error) == message, str(error)
    else:
        raise AssertionError(message)
try:
    stage_tests({"name": "x", "stages": [{"name": "s", "task": "t", "checks": [{"kind": "K99", "params": {}}]}]})
except (ValueError, KeyError):
    pass
else:
    raise AssertionError("stage_tests accepted an unknown kind")
snapshot = repr(REQ)
render_spec(REQ)
stage_tests(REQ)
assert repr(REQ) == snapshot
'''

S3 = S2 + r'''
from build_request import card_text, LABELS
card = card_text(REQ)
assert card == chr(10).join(["Spec-Karte: Verdoppler (doubler)", "Stufe 1: basic – Create sample.py with double(x) returning x * 2.", "  geprüft wird: 2 Beispiele",
                             "Stufe 2: safe – double must not change a list argument and must accept None.", "  geprüft wird: Argumente unverändert · leere Eingaben"]) + chr(10)
one = {"name": "n", "stages": [{"name": "s", "task": "  Long   task " + "x" * 200, "checks": [{"kind": "K01", "params": {"module": "m", "func": "f", "cases": [((1,), 1)]}}, {"kind": "K14", "params": {"module": "m"}}]}]}
lines = card_text(one).splitlines()
assert lines[0] == "Spec-Karte: n (n)" and lines[1] == "Stufe 1: s – Long task " + "x" * 90 and lines[2] == "  geprüft wird: 1 Beispiel · Bauform"
assert set(LABELS) == {"K%02d" % n for n in range(1, 16)} and LABELS["K03"] == "leere Eingaben" and LABELS["K05"] == "feste Reihenfolge bei Gleichstand" and LABELS["K15"] == "Vorstufen gelten weiter"
for broken in (dict(REQ, name="bad name"), dict(REQ, stages=[])):
    try:
        card_text(broken)
    except ValueError as error:
        assert str(error).startswith("invalid request: ")
    else:
        raise AssertionError("no ValueError")
snapshot = repr(REQ)
card_text(REQ)
assert repr(REQ) == snapshot
'''

S4 = S3 + r'''
many = {"name": "all_kinds", "title": "Alle", "stages": []}
for kind in assert_catalog.kinds():
    many["stages"].append({"name": "s_" + kind.lower(), "task": "Task for " + kind, "checks": [{"kind": kind, "params": PROOFS[kind]["params"]}]})
assert validate_request(many) == []
card = card_text(many)
assert card.count("Stufe ") == 15 and "geprüft wird: Vorstufen gelten weiter" in card and "geprüft wird: 2 Beispiele" in card and "geprüft wird: Ausgabegrenze" in card
rendered = {}
exec(compile(render_spec(many), "spec", "exec"), rendered)
assert [s["name"] for s in rendered["STAGES"]] == ["s_k%02d" % n for n in range(1, 16)]
assert "hidden_all_kinds_15.py" in rendered["STAGES"][14]["hidden"] and rendered["STAGES"][14]["hidden"]["hidden_all_kinds_15.py"].count("from sample import double") == 1
first_code = stage_tests(many)[0]
assert first_code in rendered["STAGES"][14]["hidden"]["hidden_all_kinds_15.py"]
'''

STAGES = [
    {"name": "validate", "no_own_check": True,
     "task": '''Create `build_request.py` (it uses `import assert_catalog`; the request format is in NOTES.md). Two functions.
`validate_request(request) -> list`: the list of problems as texts (empty = fine), found in this order:
1. `name` is not a text that matches `[A-Za-z_][A-Za-z0-9_]*` (re.fullmatch): "bad name".
2. `stages` is not a non-empty list: "no stages", and nothing more is checked.
3. For every stage in order: its name is not such a text: "bad stage name: <name!r>" and the rest of THIS stage is skipped; a name already used by an earlier stage: "stage name twice: <name>" (the stage is still checked); a missing, empty or white-space-only `task`: "stage <name>: no task"; `checks` not a non-empty list: "stage <name>: no checks" and its checks are skipped; for every check n (counted from 1): not a dict, or `params` not a dict: "stage <name> check <n>: bad check"; a `kind` that is not in `assert_catalog.kinds()`: "stage <name> check <n>: unknown kind <kind>"; otherwise the parameters are tried with `assert_catalog.generate(kind, **params)` and a ValueError, KeyError or TypeError gives "stage <name> check <n>: <the message of the error>".
`cases_from_examples(examples) -> list`: the examples of a conversation (a list of dicts {"input": ..., "output": ...}) as catalog cases for the kind K01: a list of tuples (args_tuple, output) where a list or tuple input becomes a tuple and any other input becomes a tuple with that one value. Not a non-empty list: ValueError("no examples"); an entry that is not a dict with both keys: ValueError("bad example"). Neither function modifies its argument. No comments and no docstrings.''',
     "hidden": {"hidden_req_1.py": S1}},
    {"name": "render", "no_own_check": True,
     "task": '''In `build_request.py` (keep everything) add `stage_tests(request) -> list` and `render_spec(request) -> str`.
`stage_tests`: one test text per stage; the test of stage k holds the checks of the stages 1 to k (cumulative: the earlier stages stay tested): `assert_catalog.build_test([(check["kind"], check["params"]), ...])` over all checks of stages 1 to k in order.
`render_spec`: the text of a spec file. When `validate_request` finds a problem it raises ValueError("invalid request: <first problem>"). The text defines three module level names, each written with `repr`: `TITLE` (the title with white space cleaned `" ".join(text.split())`; the name when there is no title), `NOTES` (the notes text, "" when none) and `STAGES`, a list with one dict per stage in the form {"name": stage name, "no_own_check": True, "task": task text exactly as given, "hidden": {"hidden_<request name>_<n>.py": the test of that stage}} with n counted from 1 (key order: name, no_own_check, task, hidden). The text can be executed with `exec` and gives exactly these values, also when titles, notes or tasks hold quotes, triple quotes, backslashes, line breaks or non-ASCII letters; it ends with ONE newline; the same request gives the same text. Neither function modifies its argument. No comments and no docstrings.''',
     "hidden": {"hidden_req_2.py": S2}},
    {"name": "card", "no_own_check": True,
     "task": '''In `build_request.py` add the spec card for the Captain: a module level dict `LABELS` {"K01": "Beispiele", "K02": "Argumente unverändert", "K03": "leere Eingaben", "K04": "Grenzen", "K05": "feste Reihenfolge bei Gleichstand", "K06": "gleiche Eingabe, gleiches Ergebnis", "K07": "Ausnahmen", "K08": "Eingabereihenfolge bleibt", "K09": "Zahlen mit Toleranz", "K10": "Datei-Ergebnis", "K11": "Textformat", "K12": "reiner Baustein", "K13": "Ausgabegrenze", "K14": "Bauform", "K15": "Vorstufen gelten weiter"} and `card_text(request) -> str`. An invalid request raises ValueError("invalid request: <first problem>") like `render_spec`. The card has these lines, joined with a newline and ONE newline at the end: first "Spec-Karte: <title> (<name>)" (the cleaned title, the name when there is no title); then for every stage n (from 1) two lines: "Stufe <n>: <stage name> – <task>" where the task is cleaned of white space (`" ".join(text.split())`) and cut to its first 100 characters, and "  geprüft wird: " followed by the labels of the checks of that stage, joined with " · ", in order. The label of a K01 check is its number of cases with the word "Beispiel" (one case) or "Beispiele" (otherwise), for example "2 Beispiele", "1 Beispiel"; every other label comes from `LABELS`. The argument is not modified. No comments and no docstrings.''',
     "hidden": {"hidden_req_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `build_request.py` once more: no rule may be copied into several places (the check of a name, the cleaning of white space, the problem check used by `render_spec` and `card_text`), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_req_full.py": S4}},
]
