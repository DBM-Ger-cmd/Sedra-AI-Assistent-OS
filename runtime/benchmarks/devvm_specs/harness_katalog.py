"""Harness-Shell Stufe 2, U2: die Einstufung des Freigabe-Katalogs – der erste SEDRA-Bau (SPEC_HARNESS_SHELL_v1 HS-E5, G3 Stufe 2 U2, D-E6).
Claude schrieb diese Datei, die versteckten Prüfungen (HIDDEN, höchstens 20, L3) und die Referenz (benchmarks/devvm_refs/harness_katalog).
SEDRA baut `katalog_einstufen.py` nach der Aufgabe unten; besteht der Bau, ersetzt er `einstufen` in runtime/src/guppi_runtime/harness/katalog.py
(Übernahme durch den Captain). Scheitert er, gilt V4: die Referenz bleibt, die Quote steht im Logbuch.
Bau nur nach Ja des Captains (es lädt ein Modell): spec_check.py harness_katalog --vm, dann devvm_build.py <projekt> --spec harness_katalog --profile standard."""

NOTES = '''# Notes for katalog_einstufen
Pure Python 3 standard library (re only). One file `katalog_einstufen.py`. Never modify the arguments. No comments and no docstrings; small private
helpers instead of copied code; `import` lines at the top. Names are German on purpose (the rest of SEDRA uses them): keep them exactly.
'''

TASK = '''Write `katalog_einstufen.py`: the rating of a tool call against an approval catalogue.

A rule is a dict {"id": str, "werkzeug": [str], "muster": [str], "stufe": str, "begruendung": str}. `werkzeug` holds tool names or "*" (every tool).
The levels, from mild to strict: STUFEN = ("frei", "vorarbeiter", "captain", "verboten").

Functions:
1. `befehl_normal(zeile)`: `str(zeile)` (None counts as empty) with every run of whitespace turned into one space, stripped, `casefold()`ed.
2. `pfad_normal(pfad)`: `str(pfad)` (None counts as empty) with backslashes turned into "/", split at "/", parts that are empty or "." dropped,
   joined with "/", `casefold()`ed. ".." stays as it is.
3. `passt(muster, werkzeug, ziel) -> bool`:
   - werkzeug == "befehl": compare `befehl_normal` of both. If the normalized pattern ends with "*", the rest (without the "*" and trailing
     spaces) must be a prefix of the normalized target; otherwise both must be equal.
   - any other tool: a glob over `pfad_normal` of both, matching the WHOLE target: "**/" matches zero or more whole folders, "**" matches anything
     (also "/"), "*" matches anything except "/", "?" one character except "/"; every other character literally.
4. `genauigkeit(muster) -> int`: the length of the pattern without the characters "*" and "?".
5. `einstufen(regeln, werkzeug, ziel) -> dict`: among the rules whose `werkzeug` holds the tool or "*", every pattern that `passt` is a candidate;
   the winner has the highest `genauigkeit`, on a tie the stricter `stufe`; on a full tie the first one found wins. Result
   {"stufe": …, "regel": <id>, "begruendung": …} of the winner. Without any candidate:
   {"stufe": "captain", "regel": None, "begruendung": "Keine Regel passt – ohne Regel entscheidet der Captain (HS-21)."}.
'''

HEAD = '''
from katalog_einstufen import einstufen, passt, genauigkeit, befehl_normal, pfad_normal
def r(i, w, m, s): return {"id": i, "werkzeug": w if isinstance(w, list) else [w], "muster": m if isinstance(m, list) else [m], "stufe": s, "begruendung": "b-" + i}
LESEN = ["datei_lesen", "dateien_auflisten", "suchen"]
K = [r("lesen-alles", LESEN, "**", "frei"), r("lesen-geheim", LESEN, ["**/.env", "**/local_config/**"], "verboten"),
     r("docs", ["datei_schreiben", "datei_aendern"], "docs/**", "captain"), r("git", "befehl", ["git status*", "git log*"], "frei"),
     r("tests", "befehl", "python benchmarks/run_tests.py *", "frei"), r("py", "befehl", "python *", "captain")]
def st(w, z, k=K): return einstufen(k, w, z)["stufe"]
'''

CHECKS = HEAD + '''
assert befehl_normal("  Git   STATUS\\t-s ") == "git status -s" and befehl_normal(None) == ""
assert pfad_normal("Docs\\\\Sub//./x.MD") == "docs/sub/x.md" and pfad_normal("../a") == "../a" and pfad_normal(None) == ""
assert genauigkeit("docs/**") == 5 and genauigkeit("a?b*") == 2
assert passt("**/.env", "datei_lesen", ".env") and passt("**/.env", "datei_lesen", "a/b/.ENV") and not passt("**/.env", "datei_lesen", "a/x.env")
assert passt("docs/*.md", "datei_lesen", "docs/a.md") and not passt("docs/*.md", "datei_lesen", "docs/sub/a.md")
assert passt("docs/**", "datei_lesen", "docs/sub/a.md") and not passt("docs/**", "datei_lesen", "runtime/docs/a.md")
assert passt("git status*", "befehl", "GIT   status -s") and not passt("git status*", "befehl", "git stash")
assert passt("nvidia-smi", "befehl", "nvidia-smi") and not passt("nvidia-smi", "befehl", "nvidia-smi -q")
assert st("datei_lesen", "runtime/src/x.py") == "frei"
assert einstufen(K, "datei_lesen", "workspace/local_config/switches.yaml") == {"stufe": "verboten", "regel": "lesen-geheim", "begruendung": "b-lesen-geheim"}
assert st("datei_lesen", ".env") == "verboten"
assert st("datei_schreiben", "docs/LOGBUCH.md") == "captain" and st("datei_schreiben", "runtime/x.py") == "captain"
assert einstufen(K, "datei_schreiben", "runtime/x.py")["regel"] is None
assert einstufen(K, "befehl", "python benchmarks/run_tests.py harness")["regel"] == "tests"
assert einstufen(K, "befehl", "python setup.py")["regel"] == "py"
assert st("befehl", "rm -rf docs") == "captain" and einstufen([], "befehl", "x")["begruendung"].startswith("Keine Regel passt")
T = [r("a", "befehl", "x*", "frei"), r("b", "befehl", "x*", "verboten"), r("c", "befehl", "x*", "captain")]
assert einstufen(T, "befehl", "xy")["regel"] == "b"
A = [r("alle", "*", "**", "frei"), r("eng", "datei_lesen", "**", "captain")]
assert einstufen(A, "suchen", "a")["regel"] == "alle" and einstufen(A, "datei_lesen", "a")["regel"] == "eng"
before = [dict(x) for x in K]
einstufen(K, "datei_lesen", "docs/a.md")
assert K == before
'''

STAGES = [
    {"name": "einstufen", "no_own_check": False, "task": TASK, "hidden": {"hidden_katalog_einstufen.py": CHECKS}},
]
