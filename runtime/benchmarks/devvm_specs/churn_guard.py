"""Churn guard (coder extension, 2026-10-12, Captain: "daran sollten wir arbeiten"): in the coin hole build Qwen3.6 deleted and rewrote the same file again and again
(22 writes, 21 deletes, 22 syntax notes) until the round limit. `churn_guard.py` watches the tool calls of one agent run and returns ONE correction text per file when a file
is deleted and written again `limit` times, or `limit` writes in a row leave a syntax error; reading the file resets it. Pure logic; the hook into the tool loop (after each
tool call, like coder_ext) comes after acceptance. GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/churn_guard)."""

NOTES = '''# Notes for churn_guard
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
'''

CODE = r'''
from churn_guard import ChurnGuard
MSG = "churn: {p} ({r}). Read the file with read_file, then change it with edit_file; do not delete and rewrite it again."
g = ChurnGuard()
assert g.limit == 3
assert g.feed("write_file", {"path": "a.py"}, "created a.py (10 bytes)") is None
for i in (1, 2):
    assert g.feed("delete_file", {"path": "a.py"}, "deleted a.py") is None
    assert g.feed("write_file", {"path": "a.py"}, "created a.py (10 bytes)") is None
assert g.feed("delete_file", {"path": "a.py"}, "deleted a.py") is None
assert g.feed("write_file", {"path": "a.py"}, "created a.py (10 bytes)") == MSG.format(p="a.py", r="deleted and written again 3 times")
assert g.warnings == 1
g.feed("delete_file", {"path": "a.py"}, "deleted a.py")
assert g.feed("write_file", {"path": "a.py"}, "created a.py") is None
assert g.feed("read_file", {"path": "a.py"}, "x = 1") is None
for i in (1, 2):
    g.feed("delete_file", {"path": "a.py"}, "deleted a.py"); assert g.feed("write_file", {"path": "a.py"}, "created a.py") is None
g.feed("delete_file", {"path": "a.py"}, "deleted a.py")
assert g.feed("write_file", {"path": "a.py"}, "created a.py") == MSG.format(p="a.py", r="deleted and written again 3 times")
assert g.warnings == 2
h = ChurnGuard(limit=2)
assert h.feed("delete_file", {"path": "b.py"}, "deleted b.py") is None
assert h.feed("write_file", {"path": "b.py"}, "created b.py") is None
assert h.feed("write_file", {"path": "c.py"}, "created c.py\nsyntax error in c.py line 1: invalid syntax") is None
assert h.feed("edit_file", {"path": "c.py"}, "changed c.py\nsyntax error in c.py line 2: x") == MSG.format(p="c.py", r="2 writes in a row with a syntax error")
k = ChurnGuard(limit=2)
k.feed("write_file", {"path": "d.py"}, "created d.py\nsyntax error in d.py line 1: x")
k.feed("append_file", {"path": "d.py"}, "appended to d.py")
assert k.feed("write_file", {"path": "d.py"}, "overwrote d.py\nsyntax error in d.py line 1: x") is None
assert k.feed("write_file", {"path": "d.py"}, "error: write_file refused\nsyntax error") is None
assert k.feed("write_file", {"path": "d.py"}, "overwrote d.py\nsyntax error in d.py line 1: x") == MSG.format(p="d.py", r="2 writes in a row with a syntax error")
m = ChurnGuard(limit=1)
m.feed("write_file", {"path": "e.py"}, "created e.py")
assert m.feed("delete_file", {"path": "e.py"}, "error: no such file") is None
assert m.feed("write_file", {"path": "e.py"}, "created e.py") is None
for bad in ((None, "x"), ({"path": 5}, "x"), ({"path": "e.py"}, None), ("e.py", "x")):
    assert m.feed("write_file", *bad) is None
assert m.feed("list_dir", {"path": "e.py"}, "x") is None
args = {"path": "e.py"}; m.feed("delete_file", args, "deleted"); assert args == {"path": "e.py"}
assert m.feed("write_file", {"path": "e.py"}, "created e.py") == MSG.format(p="e.py", r="deleted and written again 1 times")
print("ok")
'''

STAGES = [
    {"name": "guard",
     "task": """Create `churn_guard.py` (Python 3 standard library only) with class `ChurnGuard(limit=3)` (keep `limit` and a counter `warnings`, starting at 0) and the method `feed(name, args, result) -> str or None`, called after every tool call of an agent run (name = tool name, args = its arguments, result = its result text):
- Return None and change nothing when args is not a dict, args["path"] is not a str, result is not a str, or result starts with "error".
- "read_file" of a path resets that path (its cycle count and syntax count become 0 and it may warn again).
- "delete_file" of a path that was written before in this run marks it as deleted.
- "write_file", "append_file", "edit_file" of a path: if the path is marked deleted, unmark it and add 1 to its cycle count; remember it as written; its syntax count becomes +1 when "syntax error" is in result, else 0.
- After such a write: if the path has not warned since its last reset and its cycle count >= limit (checked first) or its syntax count >= limit, count one warning and return
  "churn: <path> (<reason>). Read the file with read_file, then change it with edit_file; do not delete and rewrite it again."
  where reason is "deleted and written again <cycles> times" or "<n> writes in a row with a syntax error". Each path warns at most once until it is reset.
- Every other tool, or no warning: None. Never modify the arguments, no comments, no docstrings.""",
     "hidden": {"hidden_churn_1.py": CODE}},
    {"name": "all",
     "task": """Read `churn_guard.py` once more. Make sure no rule is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_churn_full.py": CODE}},
]
