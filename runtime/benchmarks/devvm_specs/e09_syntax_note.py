"""E-09 (coder extension "syntax note after a write", 2026-10-10): after every write_file / append_file / edit_file the toolbox adds a short note to the tool result when the file does
not parse any more, so the model fixes it at once instead of finding out at the end (today only `--step-syntax-check` checks, and only after a whole step). Idea from Hermes
(tools/file_operations_lint.py). Pure function, no file access, nothing is executed. GUPPI builds it, Claude only wrote this file and the hidden tests.
Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for syntax_note
Pure Python 3 standard library (ast, json, tomllib), no file, process or network access, nothing is executed, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
'''

COMMON = r'''
import ast, json, tomllib
from syntax_note import note

def py_expected(path, text):
    try:
        ast.parse(text)
    except SyntaxError as e:
        lines = [f"syntax error in {path} line {e.lineno}: {e.msg}"]
        src = text.split("\n")
        if isinstance(e.lineno, int) and 1 <= e.lineno <= len(src):
            lines.append(src[e.lineno - 1].rstrip())
            if isinstance(e.offset, int) and e.offset >= 1:
                lines.append(" " * (e.offset - 1) + "^")
        return "\n".join(lines)
    return None
BODY
print("ok")
'''


def hidden(body):
    return COMMON.replace("BODY", body)


C1 = r"""
assert note("a.py", "def f(x):\n    return x\n") is None
bad = "def f(:\n    pass\n"
assert note("pkg/a.py", bad) == py_expected("pkg/a.py", bad) and note("pkg/a.py", bad).startswith("syntax error in pkg/a.py line 1: ")
indent = "def f():\nreturn 1\n"
assert note("b.py", indent) == py_expected("b.py", indent) and "line 2" in note("b.py", indent)
assert note("B.PY", bad) == py_expected("B.PY", bad)
class FakeErr(SyntaxError):
    pass
import syntax_note as _sn
_orig = _sn.ast.parse
def _fake(text):
    e = FakeErr("bad thing")
    e.lineno, e.offset = 99, 3
    raise e
_sn.ast.parse = _fake
try:
    assert note("f.py", "x = 1\n") == "syntax error in f.py line 99: bad thing"
finally:
    _sn.ast.parse = _orig
assert note("c.json", '{"a": [1, 2]}') is None
j = '{"a": 1,\n "b": }'
try:
    json.loads(j)
except json.JSONDecodeError as e:
    assert note("c.json", j) == f"invalid JSON in c.json line {e.lineno} column {e.colno}: {e.msg}"
assert note("p.toml", 'name = "x"\n[tool]\nv = 1\n') is None
t = "name = \n"
try:
    tomllib.loads(t)
except tomllib.TOMLDecodeError as e:
    assert note("p.toml", t) == f"invalid TOML in p.toml: {e}"
assert note("r.md", "def f(:") is None and note("x.yaml", "a: [") is None and note("noext", "{") is None
assert note("a.py", None) is None and note(None, "x = (") is None and note("a.py", "") is None
assert note("e.json", "") == note("e.json", "") and note("e.json", "").startswith("invalid JSON in e.json line 1 column 1: ")
"""

STAGES = [
    {"name": "note",
     "task": """Create `syntax_note.py` (Python 3 standard library only) with `note(path, text) -> str or None`: a short note when `text` (the new content of the file `path`) does not parse, else None. Nothing is executed. The file type is the suffix of path, case-insensitive:
- ".py": ast.parse(text). On SyntaxError (also IndentationError) return the lines, joined with "\\n": "syntax error in <path> line <lineno>: <msg>"; then, when lineno is an int within 1..number of lines of text.split("\\n"), that source line with its trailing white space removed; then, when also offset is an int >= 1, a caret line of (offset - 1) spaces and "^".
- ".json": json.loads(text). On json.JSONDecodeError: "invalid JSON in <path> line <lineno> column <colno>: <msg>".
- ".toml": tomllib.loads(text). On tomllib.TOMLDecodeError: "invalid TOML in <path>: <str(error)>".
- any other suffix, or path or text not a str: None.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. Add `tests/test_syntax_note.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e09_1.py": hidden(C1)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_syntax_note.py` and read `syntax_note.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e09_full.py": hidden(C1)}},
]
