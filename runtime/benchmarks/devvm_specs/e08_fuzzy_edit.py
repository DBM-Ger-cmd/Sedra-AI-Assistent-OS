"""E-08 (coder extension "tolerant edit", 2026-10-10): `fuzzy_edit.py` finds the text an edit_file call means when the model's `old` differs from the file only in trailing spaces,
indentation or typographic characters (smart quotes, dashes), and re-indents `new` to fit. Half of the edits of a Cline session failed on exactly this (2026-10-09, see edit_hint in
devvm_tools.py); idea and strategy order from Hermes tools/fuzzy_match.py (MIT). Never guesses: more than one match is an error. Pure functions, no file access; the edit_file
integration comes after acceptance. GUPPI builds it, Claude only wrote this file and the hidden tests. Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for fuzzy_edit
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
Offsets are character offsets into the text (text[start:end] is the matched piece). Lines are split on "\\n" only; a "\\r" stays part of its line.
'''

COMMON = r'''
from fuzzy_edit import IMPORTS

T = "def f(x):\n    if x:\n        return 1\n    return 2\n"
NONE = {"strategy": None, "spans": []}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
i = T.index("return 2")
assert locate(T, "return 2") == {"strategy": "exact", "spans": [(i, i + 8)]}
assert locate(T, "return") == {"strategy": "exact", "spans": [(T.index("return 1"), T.index("return 1") + 6), (i, i + 6)]}
T2 = "a = 1   \nb = 2\n"
assert locate(T2, "a = 1\nb = 2") == {"strategy": "trailing_space", "spans": [(0, len("a = 1   \nb = 2"))]}
assert locate(T2, "a = 1\nb = 2\n") == {"strategy": "trailing_space", "spans": [(0, len(T2))]}
s = T.index("    if x:")
assert locate(T, "if x:\n    return 1") == {"strategy": "indentation", "spans": [(s, T.index("return 1") + 8)]}
U = 'msg = "hi"\n'
assert locate(U, "msg = \u201chi\u201d") == {"strategy": "unicode", "spans": [(0, 10)]}
assert locate("a = 1 \u2013 2\n", "a = 1 - 2") == {"strategy": "unicode", "spans": [(0, 9)]}
assert locate(T, "return 3") == NONE
D = "  x = 1\ny = 0\n    x = 1\n"
assert locate(D, "x = 1 ") == {"strategy": "indentation", "spans": [(0, 7), (14, 23)]}
assert locate("x = 1\n  x = 1\n", "x = 1") == {"strategy": "exact", "spans": [(0, 5), (8, 13)]}
C = "a = 1\r\nb = 2\r\n"
assert locate(C, "a = 1\nb = 2") == {"strategy": "trailing_space", "spans": [(0, len("a = 1\r\nb = 2\r"))]}
assert locate(T, "") == NONE and locate(T, "  \n ") == NONE and locate(None, "x") == NONE and locate(T, 5) == NONE
assert locate("aaaa", "aa") == {"strategy": "exact", "spans": [(0, 2), (2, 4)]}
"""

C2 = r"""
assert apply(T, "return 2", "return 3") == {"text": T.replace("return 2", "return 3"), "strategy": "exact"}
assert apply(T, "return", "r") == {"error": "ambiguous", "count": 2}
assert apply(T, "return 9", "x") == {"error": "not_found", "count": 0}
assert apply(T, "return 9", "return 9") == {"error": "identical", "count": 0}
assert apply(T, "", "x") == {"error": "invalid", "count": 0} and apply(None, "a", "b") == {"error": "invalid", "count": 0} and apply(T, "a", None) == {"error": "invalid", "count": 0}
assert apply(T, "if x:\n    return 1", "if x:\n    return 10\nelse:\n    return 0") == {"text": "def f(x):\n    if x:\n        return 10\n    else:\n        return 0\n    return 2\n", "strategy": "indentation"}
assert apply(T, "if x:\n    return 1", "if x:\n\n    return 10") == {"text": "def f(x):\n    if x:\n\n        return 10\n    return 2\n", "strategy": "indentation"}
K = "x = 1\ny = 2\n"
assert apply(K, "    x = 1\n    y = 2", "    x = 5\n    y = 6\n    z = 7") == {"text": "x = 5\ny = 6\nz = 7\n", "strategy": "indentation"}
assert apply("  a\n", "a", "b\nc") == {"text": "  b\nc\n", "strategy": "exact"}
assert apply('    s = "a"\n', "s = \u201ca\u201d", 's = "b"') == {"text": '    s = "b"\n', "strategy": "unicode"}
assert apply("a = 1   \nb = 2\n", "a = 1\nb = 2", "a = 3\nb = 4") == {"text": "a = 3\nb = 4\n", "strategy": "trailing_space"}
assert apply("\tif y:\n\t\tpass\n", "if y:\n    pass", "if y:\n    return") == {"text": "\tif y:\n\t    return\n", "strategy": "indentation"}
assert apply("\tif y:\n\t\tpass\n", "  if y:\n      pass", "  if y:\n      return") == {"text": "  if y:\n      return\n", "strategy": "indentation"}
assert apply("  x = 1\ny = 0\n    x = 1\n", "x = 1 ", "x = 2") == {"error": "ambiguous", "count": 2}
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "locate",
     "task": """Create `fuzzy_edit.py` (Python 3 standard library only) with `locate(text, old) -> dict` that finds where `old` (a piece of text an AI model wants to replace) is in `text` (the file content).
It tries these strategies in this order and stops at the FIRST one that finds at least one match; the result is {"strategy": name, "spans": [(start, end), ...]} with all matches of that strategy as character offsets, sorted by start:
1. "exact": every non-overlapping occurrence of `old` in `text` (search from the left, continue after the end of a match: "aa" in "aaaa" gives (0, 2) and (2, 4)).
2. "trailing_space", 3. "indentation", 4. "unicode": LINE strategies. Split `old` on "\\n"; if `old` ends with "\\n", drop the last empty piece and remember that it ended with a newline. Split `text` on "\\n" too (a "\\r" stays part of its line). A window of as many consecutive text lines as `old` has lines matches when every text line equals its old line after normalizing BOTH with: "trailing_space" = str.rstrip(); "indentation" = str.strip(); "unicode" = replace \u201c and \u201d by '"', \u2018 and \u2019 by "'", \u2013 and \u2014 by "-", \u2026 by "...", \u00a0 by " ", then str.strip(). Every window position is checked (windows may overlap). The span of a window starts at the first character of its first line and ends at the end of its last line (before that line's "\\n"); when `old` ended with a newline and that line is followed by "\\n", the span includes this "\\n".
When no strategy matches, or `text` or `old` is not a str, or `old` is empty or only white space, return {"strategy": None, "spans": []}.""" + STYLE + """ Add `tests/test_fuzzy_edit.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e08_1.py": hidden("locate", C1)}},
    {"name": "apply",
     "task": """In the existing `fuzzy_edit.py` (keep `locate`) add `apply(text, old, new) -> dict` that does ONE replacement.
Checks in this order: if text, old or new is not a str, or old is empty or only white space: {"error": "invalid", "count": 0}; if old == new: {"error": "identical", "count": 0}. Then use `locate(text, old)`: no match gives {"error": "not_found", "count": 0}; more than one match gives {"error": "ambiguous", "count": number of matches} (never guess).
Exactly one match: replace text[start:end] by `new` and return {"text": the new text, "strategy": the strategy}. For the strategies "indentation" and "unicode" `new` is first RE-INDENTED: take old_indent = the leading white space of the first non-blank line of `old` and file_indent = the leading white space of the text line in the matched window at the same position (same line index within the window). If old_indent is a prefix of file_indent, put the rest (file_indent without old_indent) in front of every non-blank line of `new`; otherwise, if file_indent is a prefix of old_indent, remove the surplus (old_indent without file_indent) from the front of every line of `new` that starts with it; otherwise leave `new` as it is. Blank lines of `new` (empty or only white space) stay unchanged. The strategies "exact" and "trailing_space" never re-indent.""" + STYLE + """ Add tests to `tests/test_fuzzy_edit.py`.""",
     "hidden": {"hidden_e08_2.py": hidden("locate, apply", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_fuzzy_edit.py` and read `fuzzy_edit.py` once more. Make sure no check is copied into several functions, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e08_full.py": hidden("locate, apply", C1 + C2)}},
]
