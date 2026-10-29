"""Harness-Shell Stufe 3, N8: der Fortschritt eines Laufs aus seiner Ausgabe – der erste Bau eines SEDRA-Agenten UNTER EINEM VORARBEITER, über die Harness
(SPEC_HARNESS_SHELL_v1 HS-E5, HS-31; G2 Stufe 3 §6.3; G3 Stufe 3 N8, Captain 29.10.2026).
Claude schrieb diese Datei, die versteckten Prüfungen (HIDDEN, höchstens 12, L3) und die Referenz (benchmarks/devvm_refs/harness_lauf_fortschritt).
SEDRA baut `lauf_fortschritt.py` nach der Aufgabe unten; besteht der Bau und übernimmt der Captain ihn, ersetzt er harness/lauf_fortschritt.py. Scheitert er,
gilt V4: die Referenz bleibt, der Befund steht im Bericht.
Bau nur nach Ja des Captains (P-12, es lädt ein Modell): spec_check.py harness_lauf_fortschritt --vm --project <projekt>, dann der Pilot über die Vorarbeiter-Sitzung
(Aufgaben-Freigabe, Lauf devvm_build) – nicht von Hand."""

NOTES = '''# Notes for lauf_fortschritt
Pure Python 3 standard library (re only). One file `lauf_fortschritt.py`. Never modify the arguments. No comments and no docstrings; small private
helpers instead of copied code; `import` lines at the top. Names are German on purpose (the rest of SEDRA uses them): keep them exactly.
Never raise on bad input.
'''

TASK = '''Write `lauf_fortschritt.py`: read the progress of a running job from the last lines of its output.

Function `fortschritt_aus(zeilen, regel)`:
- `zeilen` is a list of output lines (anything else, and entries that are not strings, count as no lines; blank lines are ignored; every line is stripped).
- `regel` is a dict {"art": "zeilen" | "prozent" | "text", "regex": str}; anything else gives None.
- art "text": the last non-blank line, at most 80 characters (a longer line is cut to its first 79 characters plus "…"). Result {"prozent": None, "text": line};
  with no lines {"prozent": None, "text": ""}.
- art "zeilen": `regex` has two groups, done and total. Search the lines from the LAST to the first with `re.search`; the first line that matches and
  whose total is above 0 decides: prozent = int(done / total * 100) clamped into 0..100, text = that line (cut like above). A line whose groups are not
  numbers, or whose total is 0 or below, counts as not matching. No decisive line gives None.
- art "prozent": `regex` has one group, a number (may have decimals). Same search; prozent = int(number) clamped into 0..100; text as above.
- An invalid `regex` (not a string or not a valid pattern) gives None. The result of "zeilen" and "prozent" always has exactly the keys "prozent" and "text".
'''

HEAD = '''
from lauf_fortschritt import fortschritt_aus
Z = {"art": "zeilen", "regex": r"(\\d+)\\s*/\\s*(\\d+)"}
P = {"art": "prozent", "regex": r"([\\d.]+)\\s*%"}
T = {"art": "text"}
'''

CHECKS = HEAD + '''
assert fortschritt_aus(["12/40"], Z)["prozent"] == 30 and fortschritt_aus(["  12 / 40  "], Z) == {"prozent": 30, "text": "12 / 40"}
assert fortschritt_aus(["ab 42 %"], P)["prozent"] == 42 and fortschritt_aus(["x 42.5%"], P)["prozent"] == 42
assert fortschritt_aus(["12/10"], Z)["prozent"] == 100 and fortschritt_aus(["150 %"], P)["prozent"] == 100
assert fortschritt_aus(["5/0"], Z) is None and fortschritt_aus(["3/10", "5/0"], Z)["prozent"] == 30
assert fortschritt_aus(["3/10", "x", "6/10", "Rauschen"], Z)["prozent"] == 60 and fortschritt_aus(["6/10", "x"], Z)["text"] == "6/10"
assert fortschritt_aus(["nichts", "hier"], Z) is None and fortschritt_aus([], P) is None
lang = "a" * 120
assert fortschritt_aus(["eins", "", "  zwei  ", "   "], T) == {"prozent": None, "text": "zwei"} and fortschritt_aus([], T) == {"prozent": None, "text": ""}
assert fortschritt_aus([lang], T)["text"] == "a" * 79 + "…" and len(fortschritt_aus(["7/10 " + lang], Z)["text"]) == 80
assert fortschritt_aus(None, Z) is None and fortschritt_aus([None, 5, ["1/2"]], Z) is None and fortschritt_aus(None, T) == {"prozent": None, "text": ""}
assert all(fortschritt_aus(["1/2"], x) is None for x in (None, "z", {}, {"art": "magie", "regex": "x"}, {"art": "zeilen"}, {"art": "zeilen", "regex": "(["}, {"art": "zeilen", "regex": 5}))
assert set(fortschritt_aus(["1/2"], Z)) == {"prozent", "text"} and fortschritt_aus(["1/2"], Z)["prozent"] == 50
assert fortschritt_aus(["a/b"], {"art": "zeilen", "regex": r"(\\w)/(\\w)"}) is None
'''

STAGES = [
    {"name": "fortschritt", "no_own_check": False, "task": TASK, "hidden": {"hidden_lauf_fortschritt.py": CHECKS}},
]
