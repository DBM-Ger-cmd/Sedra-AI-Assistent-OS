"""G4 review_report (docs/ABLAUF_GESPRAECH_2026-10-13.md step 6, "Abnahme-Bericht"). After a build GUPPI reads the candidate and tells the Captain in the chat what was built, what is wrong with it and what to do. Three pure parts:
`findings_from_source` is the automatic part of the review (the things Claude had to find by hand in every candidate of 2026-10-13: comments, docstrings, imports inside functions, imports after code, unused imports),
`question` / `parse_answer` are the dialogue when a stage fails ("the test expects X, the code gives Y: which is right?"), `report` is the report text. No files, no clock, no model. GUPPI builds it, Claude wrote this file,
the hidden tests and the reference (benchmarks/devvm_refs/review_report)."""

NOTES = '''# Notes for review_report
Pure Python 3 standard library (`ast`, `io`, `tokenize` are allowed), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top. Texts contain the characters ä ü Ü (UTF-8 source).
A finding is a dict {"path": ..., "line": int, "kind": ..., "text": ...}.
'''

SRC = r'''
SRC = chr(10).join(['"""doc"""', "import os", "import re  # note", "from json import dumps", "x = 1", "import sys", "", "def f(a):", '    """d"""', "    import json", "    return re.sub('a', 'b', a)", "",
                    "class C:", '    """c"""', "    def m(self):", "        from pathlib import Path", "        return Path", ""])
'''

S1 = SRC + r'''
from review_report import findings_from_source
simple = findings_from_source("a.py", "x = 1  # eins" + chr(10) + "y = 2" + chr(10) + "# ganze Zeile" + chr(10))
assert simple == [{"path": "a.py", "line": 1, "kind": "comment", "text": "Kommentar"}, {"path": "a.py", "line": 3, "kind": "comment", "text": "Kommentar"}]
assert findings_from_source("a.py", "x = '# kein Kommentar'" + chr(10)) == []
doc = findings_from_source("d.py", chr(34) * 3 + "modul" + chr(34) * 3 + chr(10) + "def f():" + chr(10) + "    " + chr(34) * 3 + "d" + chr(34) * 3 + chr(10) + "    return 1" + chr(10) + "class C:" + chr(10) + "    'c'" + chr(10) + "    async def g(self):" + chr(10) + "        'async'" + chr(10) + "        return 1" + chr(10))
assert [(f["line"], f["kind"], f["text"]) for f in doc] == [(1, "docstring", "Docstring"), (3, "docstring", "Docstring"), (6, "docstring", "Docstring"), (8, "docstring", "Docstring")]
assert findings_from_source("e.py", "x = 1" + chr(10) + "'text'" + chr(10)) == [] and findings_from_source("e.py", "") == []
bad = findings_from_source("bad.py", "def (:" + chr(10))
assert bad == [{"path": "bad.py", "line": 1, "kind": "syntax", "text": "Syntaxfehler: invalid syntax"}]
mixed = findings_from_source("m.py", chr(34) * 3 + "doc" + chr(34) * 3 + chr(10) + "x = 1  # c" + chr(10))
assert [(f["line"], f["kind"]) for f in mixed] == [(1, "docstring"), (2, "comment")]
text = "x = 1  # c"
snapshot = text
findings_from_source("a.py", text)
assert text == snapshot
'''

S2 = S1 + r'''
got = findings_from_source("m.py", SRC)
assert [(f["line"], f["kind"], f["text"]) for f in got] == [(1, "docstring", "Docstring"), (2, "unused_import", "Import nicht benutzt: os"), (3, "comment", "Kommentar"), (4, "unused_import", "Import nicht benutzt: dumps"),
    (6, "late_import", "Import nicht am Dateianfang"), (6, "unused_import", "Import nicht benutzt: sys"), (9, "docstring", "Docstring"), (10, "nested_import", "Import in Funktion oder Klasse"),
    (14, "docstring", "Docstring"), (16, "nested_import", "Import in Funktion oder Klasse")]
assert all(f["path"] == "m.py" for f in got)
fine = findings_from_source("ok.py", "from __future__ import annotations" + chr(10) + "import a.b" + chr(10) + "from x import *" + chr(10) + "print(a.b)" + chr(10))
assert fine == []
alias = findings_from_source("al.py", "import numpy as np" + chr(10) + "from os import path as p, sep" + chr(10) + "print(p)" + chr(10))
assert [(f["line"], f["text"]) for f in alias] == [(1, "Import nicht benutzt: np"), (2, "Import nicht benutzt: sep")]
late = findings_from_source("l.py", chr(34) * 3 + "doc" + chr(34) * 3 + chr(10) + "import os" + chr(10) + "print(os)" + chr(10) + "import re" + chr(10) + "print(re)" + chr(10))
assert [(f["line"], f["kind"]) for f in late] == [(1, "docstring"), (4, "late_import")]
nested = findings_from_source("n.py", "def f():" + chr(10) + "    def g():" + chr(10) + "        import os" + chr(10) + "        return os" + chr(10) + "    return g" + chr(10))
assert [(f["line"], f["kind"]) for f in nested] == [(3, "nested_import")]
twice = findings_from_source("t.py", "import os, sys" + chr(10) + "print(1)" + chr(10))
assert [f["text"] for f in twice] == ["Import nicht benutzt: os", "Import nicht benutzt: sys"]
'''

S3 = S2 + r'''
from review_report import parse_answer, question, report
QUESTION = "Ist der Test richtig (dann wird der Code geändert) oder ist der Code richtig (dann wird der Test geändert)? Antwort: 'Test' oder 'Code'."
assert [parse_answer(a) for a in ("Test", "test!", " 'Code' ", "Code ist richtig", "CODE.", "Der Test", "vielleicht", "", None, "123", "Testen wir")] == ["test", "test", "code", "code", "code", None, None, None, None, None, None]
assert question("rest", "line 42: assert x == 1", "AssertionError") == "Stufe rest scheitert an: line 42: assert x == 1 (AssertionError)" + chr(10) + QUESTION
assert question("a", "line 1: b") == "Stufe a scheitert an: line 1: b" + chr(10) + QUESTION
stages = [{"name": "core", "passed": True, "reworks": 2, "seconds": 713}, {"name": "rest", "passed": False, "reworks": 3, "seconds": 975}]
found = findings_from_source("m.py", SRC)[:2]
failed = {"spec": "assert_catalog", "stages": stages, "files": [{"path": "assert_catalog.py", "lines": 591}], "findings": found, "failure": {"stage": "rest", "line": "line 42: assert x", "error": "AssertionError"}, "seconds": 5845.0, "calls": 145}
assert report(failed) == chr(10).join(["Abnahme-Bericht: assert_catalog", "Ergebnis: 1 von 2 Stufen bestanden, 145 Aufrufe, 5845 s", "Dateien: assert_catalog.py (591 Zeilen)", "Befunde (2):",
    "  m.py:1 Docstring", "  m.py:2 Import nicht benutzt: os", "Fehlschlag: Stufe rest: line 42: assert x", "Stufe rest scheitert an: line 42: assert x (AssertionError)" + chr(10) + QUESTION,
    "Empfehlung: erst klären, ob Test oder Code stimmt (siehe Frage)"]) + chr(10)
good = {"spec": "s", "stages": [{"name": "a", "passed": True}], "files": [], "findings": []}
assert report(good) == chr(10).join(["Abnahme-Bericht: s", "Ergebnis: 1 von 1 Stufen bestanden", "Dateien: keine", "Befunde: keine", "Empfehlung: Übernahme vorschlagen"]) + chr(10)
with_findings = dict(good, findings=found, files=[{"path": "a.py", "lines": 3}, {"path": "b.py", "lines": 7}], calls=5, seconds=12.4)
assert report(with_findings) == chr(10).join(["Abnahme-Bericht: s", "Ergebnis: 1 von 1 Stufen bestanden, 5 Aufrufe, 12 s", "Dateien: a.py (3 Zeilen), b.py (7 Zeilen)", "Befunde (2):", "  m.py:1 Docstring", "  m.py:2 Import nicht benutzt: os",
    "Empfehlung: Übernahme nach Korrektur der Befunde (2)"]) + chr(10)
stopped = {"spec": None, "stages": [{"name": "a", "passed": True}, {"name": "b", "passed": False}], "files": [], "findings": []}
assert report(stopped) == chr(10).join(["Abnahme-Bericht: ?", "Ergebnis: 1 von 2 Stufen bestanden", "Dateien: keine", "Befunde: keine", "Empfehlung: Bau fortsetzen oder Spec prüfen"]) + chr(10)
assert report({}) == chr(10).join(["Abnahme-Bericht: ?", "Ergebnis: 0 von 0 Stufen bestanden", "Dateien: keine", "Befunde: keine", "Empfehlung: Bau fortsetzen oder Spec prüfen"]) + chr(10)
snapshot = repr(failed)
report(failed)
assert repr(failed) == snapshot
'''

STAGES = [
    {"name": "source", "no_own_check": True,
     "task": '''Create `review_report.py`. `findings_from_source(path, text) -> list` is the automatic part of a code review of one python file. It returns a list of findings, each a dict {"path": path, "line": int, "kind": ..., "text": ...}, sorted by (line, kind) (plain string order of the kind). In this step: (1) when `ast.parse(text)` raises SyntaxError the result is ONE finding {"kind": "syntax", "line": error.lineno or 1, "text": "Syntaxfehler: <error.msg>"} and nothing else; (2) every comment (use the `tokenize` module, token type COMMENT; a "#" inside a string is no comment) gives kind "comment", text "Kommentar", at the line of the comment; (3) every module, class, function or async function with a docstring (`ast.get_docstring` is not empty) gives kind "docstring", text "Docstring", at the line of the docstring (the line of the first statement of its body). Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_rev_1.py": S1}},
    {"name": "imports", "no_own_check": True,
     "task": '''In `review_report.py` (keep everything) add three kinds of findings to `findings_from_source`: (1) "nested_import", text "Import in Funktion oder Klasse": every import statement (`import` or `from ... import`) that stands inside a function, async function or class (at any depth), at the line of that statement, once per statement. (2) "late_import", text "Import nicht am Dateianfang": a module level import statement after a module level statement that is neither an import nor the docstring (the first statement when it is a text); at the line of the import. (3) "unused_import", text "Import nicht benutzt: <name>": for every MODULE LEVEL import statement and every name it binds (`import a.b` binds "a"; `import x as y` binds "y"; `from m import n as k` binds "k", `from m import n` binds "n"), when no `ast.Name` node in the file has that id; at the line of the import statement, one finding per name, in the order of the names in the statement. `from __future__ import ...` and `from m import *` bind no names that are checked. The sort order stays (line, kind). No comments and no docstrings.''',
     "hidden": {"hidden_rev_2.py": S2}},
    {"name": "talk", "no_own_check": True,
     "task": '''In `review_report.py` add `parse_answer(text)`, `question(stage, line, error="")` and `report(data)`.
`parse_answer`: the Captain's answer to the question below. Replace every character that is not a letter by a space, make it lower case, split into words; when the FIRST word is "test" or "code" return it, otherwise None (also for empty text and None).
`question`: "Stufe <stage> scheitert an: <line>" + (" (<error>)" when error is not empty) + a line break + the fixed sentence in a module level constant `QUESTION`: "Ist der Test richtig (dann wird der Code geändert) oder ist der Code richtig (dann wird der Test geändert)? Antwort: 'Test' oder 'Code'."
`report(data) -> str`: the report text for the chat, lines joined with a newline and ONE newline at the end. `data` is a dict with the optional keys spec, stages (a list of dicts with "name" and "passed"), files (a list of {"path", "lines"}), findings (a list of findings), failure ({"stage", "line", "error"}), seconds, calls. Lines: "Abnahme-Bericht: <spec or ?>"; "Ergebnis: <passed> von <number of stages> Stufen bestanden" + (", <calls> Aufrufe, <seconds, format .0f> s" when both calls and seconds are given); "Dateien: " + the files as "<path> (<lines> Zeilen)" joined with ", " or "keine"; the findings: without any "Befunde: keine", otherwise "Befunde (<n>):" and one line "  <path>:<line> <text>" per finding in the given order; when there is a failure: "Fehlschlag: Stufe <stage>: <line>" and then the `question(...)` text (it has two lines); the last line "Empfehlung: <advice>" with the advice: a failure -> "erst klären, ob Test oder Code stimmt (siehe Frage)"; else, if there are stages and all passed -> "Übernahme vorschlagen" without findings, or "Übernahme nach Korrektur der Befunde (<n>)" with findings; otherwise "Bau fortsetzen oder Spec prüfen". Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_rev_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `review_report.py` once more: no rule may be copied into several places (the list of import statement types, the check for a docstring), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_rev_full.py": S3}},
]
