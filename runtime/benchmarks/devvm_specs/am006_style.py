"""AM-006 (first run THROUGH the agent manager, 2026-10-07): solution idea (d) of docs/EINGRIFFE_CLAUDE_AUSWERTUNG_2026-10-07.md: an automatic style check for code the models write
(comment lines, over-long functions, copied code), pure stdlib, so a build can hand an oversized or commented file back to the model instead of the Captain finding it later.
Four small stages with hidden tests written outside the models and a last stage "all". Seeded with the accepted AM-002 module (`agent_contracts.py`). Build only, no integration."""

NOTES = '''# Notes for style_check
Pure Python 3 standard library (ast), no file or network access, never modify the arguments, no comments, small private helpers instead of copied code. Uses `ContractError` from `agent_contracts.py` (do not change that file).
It judges SOURCE TEXT only: it never imports or runs the code it is given.
'''

COMMON = r'''
import copy
from agent_contracts import ContractError
from style_check import IMPORTS

SAMPLE = """import os

# a comment
def alpha(x):
    y = x + 1
    return y


def beta(x):
    'doc'
    return x


class K:
    def method(self):
        return 1
"""


def raises(code, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ContractError as exc:
        assert exc.code == code, (code, exc.code)
        return
    raise AssertionError(f"no ContractError {code}")
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


Q1 = r"""
assert count_lines("") == {"total": 0, "blank": 0, "comment": 0, "code": 0}
assert count_lines("a = 1\n") == {"total": 1, "blank": 0, "comment": 0, "code": 1}
assert count_lines("a = 1\n\n   \n# c\n  # d\nb = 2  # trailing\n") == {"total": 6, "blank": 2, "comment": 2, "code": 2}
assert count_lines(SAMPLE) == {"total": 16, "blank": 5, "comment": 1, "code": 10}, count_lines(SAMPLE)
assert count_lines("x = 1\r\ny = 2\r\n") == {"total": 2, "blank": 0, "comment": 0, "code": 2}
assert count_lines("#!/usr/bin/env python\n") == {"total": 1, "blank": 0, "comment": 1, "code": 0}
assert count_lines('s = "# not a comment"\n')["comment"] == 0
raises("bad_source", count_lines, None)
raises("bad_source", count_lines, b"x = 1")
raises("bad_source", count_lines, 5)
c = count_lines(SAMPLE); assert c["blank"] + c["comment"] + c["code"] == c["total"]
"""

Q2 = r"""
assert function_lengths("") == [] and function_lengths("x = 1\n") == []
assert function_lengths(SAMPLE) == [{"name": "alpha", "lines": 3}, {"name": "beta", "lines": 3}, {"name": "method", "lines": 2}], function_lengths(SAMPLE)
src = "def outer():\n    def inner():\n        return 1\n    return inner\n\n\nasync def worker():\n    await x\n    return 2\n"
assert function_lengths(src) == [{"name": "inner", "lines": 2}, {"name": "outer", "lines": 4}, {"name": "worker", "lines": 3}], function_lengths(src)
dec = "@decorator\n@other\ndef f():\n    return 1\n"
assert function_lengths(dec) == [{"name": "f", "lines": 2}], function_lengths(dec)
same = "def f():\n    return 1\n\n\nclass A:\n    def f(self):\n        a = 1\n        return a\n"
assert function_lengths(same) == [{"name": "f", "lines": 2}, {"name": "f", "lines": 3}], function_lengths(same)
assert function_lengths("lam = lambda x: x\n") == []
raises("bad_source", function_lengths, "def broken(:\n")
raises("bad_source", function_lengths, None)
raises("bad_source", function_lengths, "x = (1,\n")
"""

Q3 = r"""
block = "    a = load()\n    b = clean(a)\n    c = split(b)\n    return save(c)\n"
src = "def one():\n" + block + "\n\ndef two():\n" + block + "\n\ndef three(x):\n    return x\n"
d = duplicate_blocks(src)
assert d == [{"lines": [2, 9], "text": "a = load()\nb = clean(a)\nc = split(b)\nreturn save(c)"}], d
assert duplicate_blocks("def one():\n" + block) == []
assert duplicate_blocks("a = 1\nb = 2\nc = 3\nd = 4\n") == []
three = "def x():\n" + block + "\n\ndef y():\n" + block + "\n\ndef z():\n" + block
t = duplicate_blocks(three); assert t == [{"lines": [2, 9, 16], "text": "a = load()\nb = clean(a)\nc = split(b)\nreturn save(c)"}], t
indent = "if p:\n    a = load()\n    b = clean(a)\n    c = split(b)\n    d = save(c)\nif q:\n        a = load()\n        b = clean(a)\n        c = split(b)\n        d = save(c)\n"
assert [x["lines"] for x in duplicate_blocks(indent)] == [[2, 7]], duplicate_blocks(indent)
spaced = block + "\n# note\n\n" + block
assert [x["lines"] for x in duplicate_blocks(spaced)] == [[1, 8]], duplicate_blocks(spaced)
assert duplicate_blocks(src, window=5) == []
two = "x = 1\ny = 2\nx = 1\ny = 2\n"
assert [x["lines"] for x in duplicate_blocks(two, window=2)] == [[1, 3]], duplicate_blocks(two, window=2)
overlap = "a = 1\na = 1\na = 1\na = 1\na = 1\n"
assert [x["lines"] for x in duplicate_blocks(overlap, window=2)] == [[1, 3]], duplicate_blocks(overlap, window=2)
raises("bad_source", duplicate_blocks, None)
raises("bad_window", duplicate_blocks, src, window=1)
raises("bad_window", duplicate_blocks, src, window="4")
raises("bad_window", duplicate_blocks, src, window=True)
"""

Q4 = r"""
r = style_report(SAMPLE)
assert r == {"ok": False, "lines": {"total": 16, "blank": 5, "comment": 1, "code": 10}, "functions": [{"name": "alpha", "lines": 3}, {"name": "beta", "lines": 3}, {"name": "method", "lines": 2}],
             "duplicates": [], "violations": ["comments"]}, r
clean = "def f(x):\n    return x + 1\n"
assert style_report(clean) == {"ok": True, "lines": {"total": 2, "blank": 0, "comment": 0, "code": 2}, "functions": [{"name": "f", "lines": 2}], "duplicates": [], "violations": []}
long_fn = "def big():\n" + "".join(f"    v{i} = {i}\n" for i in range(45)) + "    return v0\n"
assert style_report(long_fn)["violations"] == ["long_function"]
assert style_report(long_fn, max_function_lines=100)["violations"] == []
assert style_report(long_fn, max_function_lines=100)["ok"] is True
edge = "def f():\n" + "".join(f"    v{i} = {i}\n" for i in range(38)) + "    return v0\n"
assert style_report(edge)["violations"] == [] and style_report(edge, max_function_lines=39)["violations"] == ["long_function"]
block = "    a = load()\n    b = clean(a)\n    c = split(b)\n    return save(c)\n"
dup = "def one():\n" + block + "\n\ndef two():\n" + block
assert style_report(dup)["violations"] == ["duplicate_code"] and len(style_report(dup)["duplicates"]) == 1
many = "# c\ndef big():\n" + "".join(f"    v{i} = {i}\n" for i in range(45)) + "\n\ndef one():\n" + block + "\n\ndef two():\n" + block
assert style_report(many)["violations"] == ["comments", "duplicate_code", "long_function"], style_report(many)["violations"]
assert style_report(dup, window=5)["violations"] == []
raises("bad_source", style_report, "def broken(:\n")
raises("bad_source", style_report, None)
raises("bad_limit", style_report, clean, max_function_lines=0)
raises("bad_limit", style_report, clean, max_function_lines="40")
raises("bad_window", style_report, clean, window=1)
s = SAMPLE; style_report(s); assert s == SAMPLE
"""

FULL = Q1 + Q2 + Q3 + Q4
NAMES = "count_lines, function_lengths, duplicate_blocks, style_report"
STYLE = " No comments. Put repeated work into small private helpers. Never modify the arguments."

STAGES = [
    {"name": "counts",
     "task": """In this workspace `agent_contracts.py` already exists (do not change it; it has `ContractError(code, message, field=None)` with `.code`). Create `style_check.py` (Python 3 standard library only, no file or network access).
Add `count_lines(source) -> dict`: `source` must be a str, otherwise raise `ContractError("bad_source", ...)`. Split it with `str.splitlines()`; the result is {"total": number of lines, "blank": lines that are empty or only whitespace, "comment": lines whose first non-whitespace character is "#",
"code": all other lines}. A "#" inside a string or after code does not make a comment line (only the first character after the indentation counts). total = blank + comment + code. An empty string gives all zeros.""" + STYLE + """ Add `tests/test_style_check.py` (unittest) with your own tests.""",
     "hidden": {"hidden_q1.py": hidden("count_lines", Q1)}},
    {"name": "functions",
     "task": """In the existing `style_check.py` (keep the other functions) add `function_lengths(source) -> list`. Parse the source with `ast.parse` (never import or run it); a str that does not parse (SyntaxError, ValueError) or is not a str raises `ContractError("bad_source", ...)`.
Return one entry {"name": <function name>, "lines": <end line - first line + 1>} for EVERY function definition (def and async def, also nested ones and methods), where the first line is the line of the `def` keyword itself (decorators do not count) and the end line is `end_lineno` of the node.
Sort the entries by name, then by the line of the definition (so equal names keep source order). Lambdas are not functions here.""" + STYLE + """ Add tests to `tests/test_style_check.py`.""",
     "hidden": {"hidden_q2.py": hidden("function_lengths", Q2)}},
    {"name": "duplicates",
     "task": """In the existing `style_check.py` (keep the other functions) add `duplicate_blocks(source, window=4) -> list`. `source` must be a str (else `ContractError("bad_source", ...)`); `window` must be an int >= 2 and not a bool (else `ContractError("bad_window", ...)`).
Only lines that are neither blank nor comment lines count (same definition as in `count_lines`); compare them stripped of surrounding whitespace, so different indentation does not matter. Look at every run of `window` consecutive counted lines; runs with identical stripped text are a duplicate.
Report each duplicated text once as {"lines": <sorted list of the original 1-based line numbers where the occurrences begin>, "text": <the window lines stripped and joined with "\\n">}. Occurrences of the same text must not overlap: scanning from the top, an occurrence is taken only when it starts at least `window` counted lines after the previously taken occurrence of that text.
A text with fewer than 2 taken occurrences is not reported. Sort the result by the first line number. Do not report a text twice.""" + STYLE + """ Add tests to `tests/test_style_check.py`.""",
     "hidden": {"hidden_q3.py": hidden("duplicate_blocks", Q3)}},
    {"name": "report",
     "task": """In the existing `style_check.py` (keep the other functions) add `style_report(source, max_function_lines=40, window=4) -> dict`. `max_function_lines` must be an int >= 1 and not a bool (else `ContractError("bad_limit", ...)`); the other errors pass through from the helper functions.
The result has exactly the keys "ok", "lines" (= count_lines), "functions" (= function_lengths), "duplicates" (= duplicate_blocks with the given window) and "violations": a sorted list that contains "comments" when there is at least one comment line, "duplicate_code" when there is at least one duplicate,
and "long_function" when a function has MORE than `max_function_lines` lines. "ok" is True exactly when "violations" is empty. Reuse the helper functions, do not copy their logic. Nothing is modified.""" + STYLE + """ Add tests to `tests/test_style_check.py`.""",
     "hidden": {"hidden_q4.py": hidden("style_report", Q4)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_style_check.py` and read `style_check.py` once more. Make sure all functions (count_lines, function_lengths, duplicate_blocks, style_report) work together, that no logic is copied into several functions, that the file has no comments, and that there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_q.py": hidden(NAMES, FULL)}},
]
