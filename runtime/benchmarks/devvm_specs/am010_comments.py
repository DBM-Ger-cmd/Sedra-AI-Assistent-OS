"""AM-010 (comment archive, 2026-10-08): the Captain wants the comments and docstrings that the models write to be saved in a log BEFORE `tidy` strips them, so the judge (arbiter, failure search) can use them later.
This spec builds the pure part: finding every comment and docstring with its line and its owner, and writing them as JSON lines. The wiring into `tidy` is done afterwards by hand (small glue). Two small stages with hidden tests and a last stage "all".
GUPPI builds it, Claude only wrote this file and the reference."""

NOTES = '''# Notes for comment_archive
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings in the module itself, small private helpers instead of copied code.
'''

COMMON = r'''
import json
from comment_archive import IMPORTS

SRC = """#!/usr/bin/env python3
# coding: utf-8
\"\"\"Module doc.\"\"\"
# top comment
X = 1  # inline note


class Box:
    \"\"\"Box doc.\"\"\"

    def put(self, v):
        \"\"\"Put doc.\"\"\"
        # inside put
        def inner():
            # deep
            return 1
        return v  # trailing


def free():
    s = "# not a comment"
    return s
"""
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
got = extract_comments(SRC)
assert got == [
    {"line": 3, "kind": "docstring", "owner": "<module>", "inline": False, "text": "Module doc."},
    {"line": 4, "kind": "comment", "owner": "<module>", "inline": False, "text": "top comment"},
    {"line": 5, "kind": "comment", "owner": "<module>", "inline": True, "text": "inline note"},
    {"line": 9, "kind": "docstring", "owner": "Box", "inline": False, "text": "Box doc."},
    {"line": 12, "kind": "docstring", "owner": "Box.put", "inline": False, "text": "Put doc."},
    {"line": 13, "kind": "comment", "owner": "Box.put", "inline": False, "text": "inside put"},
    {"line": 15, "kind": "comment", "owner": "Box.put.inner", "inline": False, "text": "deep"},
    {"line": 17, "kind": "comment", "owner": "Box.put", "inline": True, "text": "trailing"},
], got
assert extract_comments("") == [] and extract_comments("x = 1\n") == [] and extract_comments("def f(:\n  # broken\n") == [] and extract_comments(None) == [] and extract_comments(5) == []
multi = 'def f():\n    """First line.\n\n    more text\n    """\n    return 1\n'
assert extract_comments(multi) == [{"line": 2, "kind": "docstring", "owner": "f", "inline": False, "text": "First line.\n\n    more text\n    "}]
assert extract_comments('s = "# no"\nt = "a#b"\n') == []
assert extract_comments("#!/usr/bin/env python\n# coding: utf-8\n# real\n") == [{"line": 3, "kind": "comment", "owner": "<module>", "inline": False, "text": "real"}]
assert extract_comments("x = 1 #   spaced   \n") == [{"line": 1, "kind": "comment", "owner": "<module>", "inline": True, "text": "spaced"}]
assert extract_comments("#\nx = 1\n") == [{"line": 1, "kind": "comment", "owner": "<module>", "inline": False, "text": ""}]
assert extract_comments("async def g():\n    # in async\n    pass\n") == [{"line": 2, "kind": "comment", "owner": "g", "inline": False, "text": "in async"}]
assert extract_comments("def f():\n    pass\n# after f\n") == [{"line": 3, "kind": "comment", "owner": "<module>", "inline": False, "text": "after f"}]
assert extract_comments("def f():\n    x = 1\n\n    # blank line before\n    return x\n")[0]["owner"] == "f"
src = "x = 1  # a\n"
extract_comments(src)
assert src == "x = 1  # a\n"
'''

C2 = r"""
entries = extract_comments(SRC)[:2]
text = to_jsonl(entries, {"path": "mod.py", "stage": "basics", "turn": 2})
lines = text.split("\n")
assert text.endswith("\n") and len(lines) == 3 and lines[2] == ""
first = json.loads(lines[0])
assert first == {"line": 3, "kind": "docstring", "owner": "<module>", "inline": False, "text": "Module doc.", "path": "mod.py", "stage": "basics", "turn": 2}
assert lines[0] == json.dumps(first, sort_keys=True, ensure_ascii=False)
assert to_jsonl([], {"path": "m.py"}) == "" and to_jsonl(None, {}) == "" and to_jsonl([], None) == ""
assert json.loads(to_jsonl([{"line": 1, "kind": "comment", "owner": "<module>", "inline": False, "text": "ä\nö"}], None)) == {"line": 1, "kind": "comment", "owner": "<module>", "inline": False, "text": "ä\nö"}
assert "ä" in to_jsonl([{"line": 1, "text": "ä"}], {}) and "\\u" not in to_jsonl([{"line": 1, "text": "ä"}], {})
over = json.loads(to_jsonl([{"line": 1, "text": "t"}], {"line": 99, "extra": True}))
assert over == {"line": 1, "text": "t", "extra": True}
junk = to_jsonl(["x", None, {"line": 2, "text": "ok"}, 5], {"path": "p"})
assert junk.count("\n") == 1 and json.loads(junk) == {"line": 2, "text": "ok", "path": "p"}
meta = {"path": "m.py"}
entries2 = [{"line": 1, "text": "a"}]
to_jsonl(entries2, meta)
assert meta == {"path": "m.py"} and entries2 == [{"line": 1, "text": "a"}]
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "extract",
     "task": """Create `comment_archive.py` (Python 3 standard library only) with `extract_comments(source) -> list`. It finds every comment and every docstring of a Python source text and returns them sorted by line as dicts with exactly the keys "line" (1-based; for a docstring the line where it starts), "kind" ("comment" or "docstring"),
"owner" (the dotted name of the innermost class or function that contains it, for example "Box.put.inner", for a docstring the name of the thing it documents, "<module>" at module level), "inline" (True when code stands before a comment on the same line, else False) and "text" (a comment without the "#" and stripped of surrounding white space;
a docstring exactly as the string value of the constant, not stripped).
Use `ast` for the structure and `tokenize` for the comments, so that a "#" inside a string is not a comment. The first two lines are skipped when they are a shebang ("#!...") or a coding line (contain "coding"), as `strip_comments` of the tidy step does. A comment on a line inside the span of a function or class (first line to last line of its body)
belongs to the innermost one. A source that is not a str or does not parse returns [].""" + STYLE + """ Add `tests/test_comment_archive.py` (unittest) with your own tests.""",
     "hidden": {"hidden_c1.py": hidden("extract_comments", C1)}},
    {"name": "jsonl",
     "task": """In the existing `comment_archive.py` (keep the other function) add `to_jsonl(entries, meta) -> str`: one JSON object per line for every entry of `entries` (an iterable of dicts; items that are not dicts are skipped) merged with the dict `meta` (None counts as empty); where a key exists in both, the ENTRY wins.
Each line is `json.dumps(obj, sort_keys=True, ensure_ascii=False)` and ends with "\\n"; the result is the empty string when nothing was written. `entries` that is None counts as empty.""" + STYLE + """ Add tests to `tests/test_comment_archive.py`.""",
     "hidden": {"hidden_c2.py": hidden("extract_comments, to_jsonl", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_comment_archive.py` and read `comment_archive.py` once more. Make sure no check is copied into several functions, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_c.py": hidden("extract_comments, to_jsonl", C1 + C2)}},
]
