"""Skill digest, round 2 (Captain 2026-10-13: "gehen wir das an", on the review of the first digest). Two findings. (1) Review: the first digest keeps the fence logic in two places (a generator for outline and summary, a loop in templates) and
treats a nested fence differently in the two. (2) Measurement skill_need with `brief`: the model used the digest (10 skill_read brief=true per run) but only 1/5, 2/5, 2/5 stages passed, against 4/5 when it read the whole pages: the digest shows the template
but not the rules around it ("Store ADRs in `docs/decisions/`", "default: `tasks/todo.md`", "`SPEC.md`"), and the model stopped reading. Round 2: ONE fence scanner `fences` (CommonMark-like: backtick or tilde fences, longer fences hold shorter ones,
an info string never closes a block), `outline`, `templates` and the summary use it, and a new section "Locations" lists the text lines that name a path or a file in backticks. Seed: benchmarks/skill_fences_seed (the digest of round 1).
GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/skill_fences)."""
SEED = "benchmarks/skill_fences_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given
import importlib.util
from pathlib import Path

NOTES = '''# Notes for skill_digest (round 2)
`skill_digest.py` is already in the workspace and works. Keep the names and results of `outline`, `templates` and `digest` as they are unless the task says otherwise. Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code. `import` lines at the top.
'''

_old = importlib.util.spec_from_file_location("skill_digest_spec", Path(__file__).with_name("skill_digest.py"))
_mod = importlib.util.module_from_spec(_old)
_old.loader.exec_module(_mod)
OLD = _mod.S4

HEAD = '''
B3 = chr(96) * 3
B4 = chr(96) * 4
T3 = chr(126) * 3
NL = chr(10)
'''

S1 = HEAD + '''
from skill_digest import fences
assert fences(NL.join(["a", B3 + "Python extra", "x", B3, "b"])) == [{"start": 2, "end": 4, "lang": "python", "body": ["x"], "closed": True}]
assert fences(NL.join([B4 + "markdown", "# T", B3 + "python", "x = 1", B3, B4])) == [{"start": 1, "end": 6, "lang": "markdown", "body": ["# T", B3 + "python", "x = 1", B3], "closed": True}]
assert fences(NL.join([T3 + "md", "# X", T3, "after"])) == [{"start": 1, "end": 3, "lang": "md", "body": ["# X"], "closed": True}]
assert fences(NL.join([B3 + "markdown", "# in", B3 + "python", "still in", B3])) == [{"start": 1, "end": 5, "lang": "markdown", "body": ["# in", B3 + "python", "still in"], "closed": True}]
assert fences(NL.join([B4, "a", B3, "b", B4])) == [{"start": 1, "end": 5, "lang": "", "body": ["a", B3, "b"], "closed": True}]
assert fences(NL.join([T3, "a", B3, "b", T3])) == [{"start": 1, "end": 5, "lang": "", "body": ["a", B3, "b"], "closed": True}]
assert len(fences("   " + B3 + "md" + NL + "x" + NL + "   " + B3)) == 1
assert fences("    " + B3 + "md" + NL + "x") == []
assert fences(B3 + "a" + chr(96) + "b" + NL + "text") == []
assert fences(B3 + "md" + NL + "x") == [{"start": 1, "end": None, "lang": "md", "body": ["x"], "closed": False}]
assert fences(NL.join([B3, "a", B3 + " x", B3 + "  "])) == [{"start": 1, "end": 4, "lang": "", "body": ["a", B3 + " x"], "closed": True}]
assert fences("") == [] and fences(None) == [] and fences("no fences") == []
assert [(b["start"], b["end"]) for b in fences(NL.join([B3, "a", B3, "mid", B3 + "md", "b", B3]))] == [(1, 3), (5, 7)]
'''

S2 = S1 + '''
from skill_digest import outline, templates, digest
n1 = NL.join(["# A", B4 + "markdown", "# T", B3 + "python", "x = 1", B3, B4, "## After"])
assert outline(n1) == [(1, 1, "A"), (8, 2, "After")]
assert templates(n1) == [{"title": "A", "start": 2, "end": 7, "lang": "markdown", "body": ["# T", B3 + "python", "x = 1", B3]}]
n2 = NL.join(["## B", T3 + "md", "# X", T3, "## C"])
assert outline(n2) == [(1, 2, "B"), (5, 2, "C")]
assert templates(n2) == [{"title": "B", "start": 2, "end": 4, "lang": "md", "body": ["# X"]}]
n3 = NL.join([B3 + "markdown", "# in", B3 + "python", "## still in", B3, "## out"])
assert outline(n3) == [(6, 2, "out")]
assert templates(n3) == [{"title": "", "start": 1, "end": 5, "lang": "markdown", "body": ["# in", B3 + "python", "## still in"]}]
n4 = NL.join(["# Open", B3 + "markdown", "# never closed", "## also inside"])
assert outline(n4) == [(1, 1, "Open")] and templates(n4) == []
assert digest(NL.join([B3 + "python", "code", B3, "text after"])).splitlines()[0] == "Summary: text after"
assert digest(NL.join([T3, "code", T3, "tilde text"])).splitlines()[0] == "Summary: tilde text"
assert digest(NL.join([B4, B3, "still code", B3, B4, "real text"])).splitlines()[0] == "Summary: real text"
''' + OLD

LOC = '''
from skill_digest import locations
L1 = NL.join(["# T", "Store them in `docs/decisions/` please.", "Name it `SPEC.md`.", "Plain `word` here.", B3, "see `a/b.md`", B3, "## Sub `x/y`", "tail `notes.txt`", "version `v1.2` and `my file.md`"])
assert locations(L1) == [(2, "Store them in `docs/decisions/` please."), (3, "Name it `SPEC.md`."), (9, "tail `notes.txt`")]
assert locations(L1, 2) == [(2, "Store them in `docs/decisions/` please."), (3, "Name it `SPEC.md`.")]
assert locations(L1, 0) == [] and locations("") == [] and locations(None) == []
assert locations("  indented `src/a.py` text  ") == [(1, "indented `src/a.py` text")]
assert locations("`one` and `two/three`") == [(1, "`one` and `two/three`")]
assert locations("x" * 200 + " `a/b`")[0][1] == ("x" * 200 + " `a/b`")[:160]
assert locations("`a.TXT` `b.json`") == [(1, "`a.TXT` `b.json`")]
assert locations("`a.TXT`") == []
many = NL.join(f"line {i} `dir{i}/`" for i in range(10))
assert [n for n, _ in locations(many)] == [1, 2, 3, 4, 5, 6]
assert len(locations(many, 10)) == 10
LD = NL.join(["# G", "Guide intro.", "", "Save to `docs/x/` always.", B3 + "markdown", "# Doc", B3, "## Rules"])
assert digest(LD) == NL.join(["Summary: Guide intro.", "Template (G, lines 5-7):", "# Doc", "Locations:", "4 Save to `docs/x/` always.", "Outline:", "8 Rules"])
assert digest(LD, 4).splitlines() == ["Summary: Guide intro.", "Template (G, lines 5-7):", "# Doc", "[more: read the full text with skill_read start/end]"]
assert "Locations:" not in digest(DOC)
assert digest(many).splitlines()[:3] == ["Summary: line 0 `dir0/`", "Locations:", "1 line 0 `dir0/`"]
assert len(digest(many).splitlines()) == 1 + 1 + 6 + 1
'''

S3 = S2 + LOC

STAGES = [
    {"name": "fences", "no_own_check": True,
     "task": '''In the existing `skill_digest.py` (keep everything in it) add `fences(text) -> list`, the ONE place that knows what a fenced block is. Lines are `str(text or "").splitlines()`, numbered from 1. An opening fence is a line with at most 3 leading spaces, then 3 or more backticks OR 3 or more tildes (one kind only), then an info string. For backtick fences the info string must not contain a backtick (otherwise the line is no fence). The language is the first word of the info string in lower case ("" when there is none).
A block is closed by the first later line with at most 3 leading spaces, the SAME character, at least as many of them as the opening fence, and nothing but white space after them; every other line (also a line like "```python" or a shorter fence) belongs to the body. Result: a list of dicts {"start", "end", "lang", "body", "closed"} (start/end = line numbers of the fences, body = the lines between, closed True). A block that is never closed has "end" None, the rest of the text as body and "closed" False. No comments and no docstrings.''',
     "hidden": {"hidden_fences_1.py": S1}},
    {"name": "rewire", "no_own_check": True,
     "task": '''Make `outline`, `templates` and the summary line of `digest` use `fences` and remove their own fence logic (the helper `_non_fence_lines` goes away; the fence check must exist once). Lines of a block (the fence lines too, and for an unclosed block all lines to the end) are "inside": no heading is found there and the summary is never taken from there. `templates` returns only CLOSED blocks whose language is `markdown` or `md`; its dict keeps the keys title, start, end, lang, body as before. Everything else stays as it is: the tests for the results of `outline`, `templates` and `digest` from the first round still hold, and nested or tilde fences now work as described in the task before.''',
     "hidden": {"hidden_fences_2.py": S2}},
    {"name": "locations", "no_own_check": True,
     "task": '''Add `locations(text, limit=6) -> list` to `skill_digest.py`: the lines outside of any fenced block (use `fences`) that are not headings (a line that starts with "#" after white space) and that hold a backtick token (`` `token` `` with no white space and no backtick inside) which names a path or a file: the token contains "/" or ends with ".md", ".py", ".json", ".yaml", ".yml", ".txt", ".toml", ".js" or ".ts" (upper or lower case). Result: a list of tuples (line number, the line with white space cut at both ends and at most 160 characters), in text order, at most `limit` of them (`limit` 0 gives []).
In `digest` the section comes after the templates and before "Outline:": when `locations(text)` is not empty, the line "Locations:" and then one line "<line number> <line>" per entry. When there is none, nothing is added. The length limit works as before. No comments and no docstrings.''',
     "hidden": {"hidden_fences_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `skill_digest.py` once more: the fence rule exists once (`fences`), no rule is copied into several places, no comments, no docstrings, all `import` lines at the top, no unused helpers or variables, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_fences_full.py": S3}},
]
