"""E-01 (coder extension "read before change", 2026-10-10): `read_tracker.py` remembers which files and which lines the coder has seen in this run, so that the DevToolBox can refuse
edit_file on a file the model never read and a whole-file write_file over content it has not fully seen. Ideas from little-coder (edit refuses on unread files) and Hermes
(file_tools_read_tracking: overwrite only with a full-read baseline, warning when the file changed since the read). Pure class, no file access; the toolbox integration comes after
acceptance. GUPPI builds it, Claude only wrote this file and the hidden tests. Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for read_tracker
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
Lines are counted with str.splitlines(): "a\\nb\\n" has 2 lines, "" has 0. Line ranges are 1-based and inclusive.
'''

COMMON = r'''
from read_tracker import ReadTracker

A = "a = 1\nb = 2\n"
L = "".join(f"x{i} = {i}\n" for i in range(1, 301))
L2 = L.replace("x1 = 1\n", "x1 = 100\nextra = 0\n")
BODY
print("ok")
'''


def hidden(body):
    return COMMON.replace("BODY", body)


C1 = r"""
t = ReadTracker()
assert t.check_edit("a.py", A) == "unread"
t.note_read("a.py", A)
assert t.check_edit("a.py", A) == "ok"
assert t.check_edit("a.py", A + "c = 3\n") == "changed"
assert t.check_edit("b.py", A) == "unread"
t.note_read("p.py", A, 2, 2)
assert t.check_edit("p.py", A) == "ok"
t.note_write("n.py", "x = 1\n")
assert t.check_edit("n.py", "x = 1\n") == "ok"
t.note_edit("a.py", "a = 10\nb = 2\n")
assert t.check_edit("a.py", "a = 10\nb = 2\n") == "ok"
assert t.check_edit("a.py", A) == "changed"
t.note_edit("z.py", "q = 1\n")
assert t.check_edit("z.py", "q = 1\n") == "unread"
t.forget("a.py")
assert t.check_edit("a.py", "a = 10\nb = 2\n") == "unread"
t.forget("never.py")
t.note_read("m.py", A)
t.move("m.py", "k.py")
assert t.check_edit("k.py", A) == "ok" and t.check_edit("m.py", A) == "unread"
t.note_read("d.py", A)
t.move("nothing.py", "d.py")
assert t.check_edit("d.py", A) == "unread"
t.note_read(None, A)
t.note_read("x.py", None)
t.note_write(5, A)
assert t.check_edit("x.py", A) == "unread" and t.check_edit(None, A) == "unread" and t.check_edit("n.py", None) == "changed"
other = ReadTracker()
assert other.check_edit("n.py", "x = 1\n") == "unread"
"""

C2 = r"""
t = ReadTracker()
t.note_read("big.py", L, 1, 150)
assert t.seen("big.py") == [(1, 150)] and t.check_overwrite("big.py", L) == "partial"
t.note_read("big.py", L, 151, 300)
assert t.seen("big.py") == [(1, 300)] and t.check_overwrite("big.py", L) == "ok"
t.note_read("o.py", L, 100, 200)
t.note_read("o.py", L, 1, 120)
assert t.seen("o.py") == [(1, 200)]
t.note_read("o.py", L, 250, 400)
assert t.seen("o.py") == [(1, 200), (250, 300)]
t.note_read("o.py", L, 201, 249)
assert t.seen("o.py") == [(1, 300)]
t.note_read("f.py", L)
t.note_read("g.py", L, 290)
t.note_read("h.py", L, None, 5)
t.note_read("s.py", L, -5, 3)
t.note_read("b.py", L, True, 3)
assert (t.seen("f.py"), t.seen("g.py"), t.seen("h.py"), t.seen("s.py"), t.seen("b.py")) == ([(1, 300)], [(290, 300)], [(1, 5)], [(1, 3)], [(1, 3)])
t.note_read("e.py", L, 10, 5)
assert t.seen("e.py") == [] and t.check_edit("e.py", L) == "ok" and t.check_overwrite("e.py", L) == "partial"
t.note_read("big.py", L + "y = 1\n", 1, 10)
assert t.seen("big.py") == [(1, 10)] and t.check_overwrite("big.py", L + "y = 1\n") == "partial" and t.check_overwrite("big.py", L) == "changed"
t.note_write("w.py", L)
assert t.seen("w.py") == [(1, 300)] and t.check_overwrite("w.py", L) == "ok"
t.note_edit("w.py", L2)
assert t.seen("w.py") == [(1, 301)] and t.check_overwrite("w.py", L2) == "ok"
t.note_read("q.py", L, 1, 10)
t.note_edit("q.py", L2)
assert t.seen("q.py") == [] and t.check_edit("q.py", L2) == "ok" and t.check_overwrite("q.py", L2) == "partial"
t.note_read("parts.py", L, 1, 150)
t.note_read("parts.py", L, 151, 300)
t.note_edit("parts.py", L2)
assert t.seen("parts.py") == [(1, 301)] and t.check_overwrite("parts.py", L2) == "ok"
t.note_read("rev.py", L, 151, 300)
t.note_read("rev.py", L, 1, 150)
t.note_edit("rev.py", L2)
assert t.check_overwrite("rev.py", L2) == "ok"
t.note_write("w0.py", "")
assert t.seen("w0.py") == [] and t.check_overwrite("w0.py", "") == "ok"
t.note_edit("w0.py", "a = 1\n")
assert t.seen("w0.py") == [(1, 1)] and t.check_overwrite("w0.py", "a = 1\n") == "ok"
t.note_read("gone.py", A)
t.note_edit("gone.py", "")
assert t.seen("gone.py") == [] and t.check_overwrite("gone.py", "") == "ok"
t.note_read("e0.py", "")
assert t.seen("e0.py") == [] and t.check_overwrite("e0.py", "") == "ok"
assert t.seen("nope.py") == [] and t.check_overwrite("nope.py", L) == "unread" and t.check_overwrite(None, L) == "unread"
s = t.seen("f.py")
s.append((9, 9))
assert t.seen("f.py") == [(1, 300)]
t.move("f.py", "f2.py")
assert t.seen("f2.py") == [(1, 300)] and t.seen("f.py") == []
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "tracking",
     "task": """Create `read_tracker.py` (Python 3 standard library only) with a class `ReadTracker` (no constructor arguments). It remembers, per file path (a str, compared exactly), which VERSION of the file the coder knows (the full text it had then) and whether the file is known at all.
Methods:
- `note_read(path, text, start=None, end=None)`: the coder read lines start..end of the file whose content is now `text`. The file becomes known with this text as its version.
- `note_write(path, text)`: the coder wrote the whole file; it becomes known with this text.
- `note_edit(path, text)`: the coder changed a KNOWN file, its content is now `text`; the known version becomes `text`. On a path that is not known it does nothing.
- `forget(path)`: the file was deleted; it is no longer known (no error for an unknown path).
- `move(source, destination)`: the file was moved; whatever was known about source is now known about destination and source is unknown. When source was not known, destination becomes unknown too.
- `check_edit(path, text) -> str` with `text` = the content of the file right now: "unread" when the path is not known, "changed" when it is known but `text` differs from the known version (also when text is not a str), else "ok".
A call to note_read, note_write or note_edit with a path or a text that is not a str does nothing; check_edit with a path that is not a str returns "unread".""" + STYLE + """ Add `tests/test_read_tracker.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e01_1.py": hidden(C1)}},
    {"name": "coverage",
     "task": """In the existing `read_tracker.py` (keep everything) the tracker also remembers WHICH LINES of the known version were seen. Lines are counted with `text.splitlines()` (n lines, 1-based, inclusive ranges).
- `note_read(path, text, start=None, end=None)`: start or end that is not an int (a bool is not an int) counts as None; None start = 1, None end = n; then clamp start to at least 1 and end to at most n. If start > end after that, no lines are added, but the file is still known. When `text` differs from the known version, the old lines are dropped first (a new version starts with nothing seen); otherwise the new range is added to the ones already seen.
- `note_write(path, text)`: all lines 1..n are seen.
- `note_edit(path, text)`: if ALL lines of the old known version were seen, all lines 1..n of the new text are seen; otherwise no lines are seen any more (the file stays known).
- `move` carries the seen lines along.
- `seen(path) -> list`: the seen ranges of the known version as a sorted list of (start, end) tuples, overlapping or touching ranges merged ((1, 150) and (151, 300) become (1, 300)); [] for an unknown path. Changing the returned list must not change the tracker.
- `check_overwrite(path, text) -> str` with `text` = the content right now: "unread" when unknown (or path not a str), "changed" when text differs from the known version, "partial" when not every line 1..n of it was seen, else "ok". A known file with 0 lines counts as fully seen.""" + STYLE + """ Add tests to `tests/test_read_tracker.py`.""",
     "hidden": {"hidden_e01_2.py": hidden(C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_read_tracker.py` and read `read_tracker.py` once more. Make sure no check is copied into several methods, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e01_full.py": hidden(C1 + C2)}},
]
