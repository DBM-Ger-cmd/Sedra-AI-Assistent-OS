"""Harness-Shell Stufe 3, N2: die Deckung einer Aufgaben-Freigabe – SEDRA-Bau (SPEC_HARNESS_SHELL_v1 HS-27, G2 Stufe 3 §4.2, G3 Stufe 3 N2, Captain 29.10.2026).
Claude schrieb diese Datei, die versteckten Prüfungen (HIDDEN, höchstens 20, L3) und die Referenz (benchmarks/devvm_refs/harness_aufgabe_deckung).
SEDRA baut `aufgabe_deckung.py` nach der Aufgabe unten; besteht der Bau, ersetzt er harness/aufgabe_deckung.py (Übernahme durch den Captain). Scheitert er,
gilt V4: die Referenz bleibt, die Quote steht im Logbuch.
Bau nur nach Ja des Captains (P-11, es lädt ein Modell): spec_check.py harness_aufgabe_deckung --vm --project <projekt>, dann
devvm_build.py <projekt> --spec harness_aufgabe_deckung --profile standard."""

NOTES = '''# Notes for aufgabe_deckung
Pure Python 3 standard library (datetime only). One file `aufgabe_deckung.py`. Never modify the arguments. No comments and no docstrings; small private
helpers instead of copied code; `import` lines at the top. Names are German on purpose (the rest of SEDRA uses them): keep them exactly.
Never raise on bad input: a broken task simply never covers anything.
'''

TASK = '''Write `aufgabe_deckung.py`: which approved task (if any) covers a tool call.

A task is a dict {"id": str, "sitzungen": [str], "erlaubt": [{"werkzeug": str, "muster": str}], "status": str,
"aufrufe": int, "ende": {"bis": ISO-8601 string or None, "max_aufrufe": int or None}}. `jetzt` is a timezone-aware datetime that is passed in.

Functions:
1. `zustand(aufgabe, jetzt) -> str`: the status of the task at `jetzt`. If `status` is not "aktiv" it is returned unchanged (a missing or non-string
   status, or a task that is not a dict, counts as "zurueckgenommen"). For an "aktiv" task: if `ende["bis"]` is set and `jetzt` is not before it
   (equal counts as over), or it cannot be read as a timezone-aware time (naive times and garbage count as over), the result is "abgelaufen"; else if
   `ende["max_aufrufe"]` is set (not None) and `aufrufe` is not below it (a `max_aufrufe` that is not a plain int, or `aufrufe` that is not a plain int,
   counts as used up; a bool is not a plain int), the result is "erschoepft"; otherwise "aktiv". Time is checked before the counter.
2. `deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt, passt)`: `aufgaben` is a list (anything else covers nothing). A task is a candidate only if
   `zustand` is "aktiv" and its `sitzungen` is a list (anything else never matches) that contains `sitzung_id`. It covers the call if one of its `erlaubt` entries has the same `werkzeug` and
   `passt(muster, werkzeug, ziel)` is true; `passt` is given to you, call it with exactly these three arguments and never write your own pattern
   matching. An entry that is broken, or a `passt` that raises, counts as "does not match" for that entry. Several candidates cover the call: the one
   whose `ende["bis"]` is earliest wins; tasks without a readable `bis` come last; on a tie the smaller `id` (compared as text; a task without `id` must not raise) wins.
   Result: {"aufgabe_id": <id of the winner>, "eintrag": <the matching entry>} or None.
'''

HEAD = '''
from datetime import datetime, timedelta, timezone
from aufgabe_deckung import deckt, zustand
J = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
def iso(**kw): return (J + timedelta(**kw)).isoformat()
def passt(m, w, z): return m == "**" or m == z or (m.endswith("**") and z.startswith(m[:-2]))
def a(i="T-00000001", sitzungen=("S-1",), erlaubt=(("datei_schreiben", "docs/**"),), status="aktiv", aufrufe=0, bis=None, maximum=None):
    return {"id": i, "sitzungen": list(sitzungen), "erlaubt": [{"werkzeug": w, "muster": m} for w, m in erlaubt], "status": status, "aufrufe": aufrufe,
            "ende": {"bis": bis if bis is None or isinstance(bis, str) else iso(**bis), "max_aufrufe": maximum}}
def m(aufrufe=0, **ende):
    x = a(aufrufe=aufrufe); x["ende"].update(ende); return x
def d(aufgaben, w="datei_schreiben", z="docs/a.md", s="S-1", passt=passt): return deckt(aufgaben, s, w, z, J, passt)
'''

CHECKS = HEAD + '''
assert deckt([], "S-1", "datei_schreiben", "docs/a.md", J, passt) is None and deckt("kein", "S-1", "x", "y", J, passt) is None
t = a(maximum=3, bis={"hours": 1})
r = d([t])
assert r == {"aufgabe_id": "T-00000001", "eintrag": {"werkzeug": "datei_schreiben", "muster": "docs/**"}}
assert d([t], w="datei_aendern") is None and d([t], s="S-2") is None and d([t], z="runtime/x.py") is None
assert all(d([a(status=x)]) is None for x in ("zurueckgenommen", "erledigt", "abgelaufen", "erschoepft"))
assert d([a(bis={"seconds": 1})]) is not None and d([a(bis={"seconds": 0})]) is None and d([a(bis={"seconds": -1})]) is None
assert d([a(maximum=3, aufrufe=2)]) is not None and d([a(maximum=3, aufrufe=3)]) is None
seen = []
def spion(m, w, z): seen.append((m, w, z)); return True
assert d([a()], passt=spion) is not None and seen == [("docs/**", "datei_schreiben", "docs/a.md")]
spaet, frueh, ohne = a("T-00000001", bis={"hours": 5}), a("T-00000009", bis={"hours": 1}), a("T-00000000")
assert d([spaet, frueh, ohne])["aufgabe_id"] == "T-00000009" and d([ohne, spaet])["aufgabe_id"] == "T-00000001"
gleich = iso(hours=2)
assert d([a("T-00000005", bis=gleich), a("T-00000002", bis=gleich)])["aufgabe_id"] == "T-00000002" and d([ohne, a("T-00000003")])["aufgabe_id"] == "T-00000000"
assert zustand(a(), J) == "aktiv" and zustand(a(bis={"seconds": 0}), J) == "abgelaufen" and zustand(a(maximum=2, aufrufe=2), J) == "erschoepft"
assert zustand(a(bis={"seconds": 0}, maximum=1, aufrufe=5), J) == "abgelaufen" and zustand(a(status="erledigt", maximum=1, aufrufe=5), J) == "erledigt"
x = a(maximum=3, bis={"hours": 1}); vorher = repr(x)
zustand(x, J); d([x])
assert repr(x) == vorher
assert zustand(a(bis="2026-10-29T13:00:00"), J) == "abgelaufen" and d([a(bis="2026-10-29T13:00:00")]) is None and d([a(bis="kaputt")]) is None
kaputt = [None, "x", 5, [], {}, {"status": "aktiv"}, {"status": "aktiv", "ende": "kaputt"}, {"status": "aktiv", "sitzungen": ["S-1"], "erlaubt": ["x", 5, None, {"werkzeug": "datei_schreiben"}]}]
assert all(d([k]) is None for k in kaputt) and zustand(None, J) == "zurueckgenommen" and zustand({"status": 5}, J) == "zurueckgenommen"
assert zustand(m(bis=5), J) == "abgelaufen" and zustand(m(bis=True), J) == "abgelaufen" and d([m(bis=[])]) is None
assert all(zustand(m(max_aufrufe=v), J) == "erschoepft" for v in ("x", True, 2.5)) and zustand(m(max_aufrufe=3, aufrufe=True), J) == "erschoepft"
falsch = a(); falsch["sitzungen"] = "S-1"; ohne_id = a(); del ohne_id["id"]
assert d([falsch]) is None and d([ohne_id]) is not None
def bricht(m, w, z): raise ValueError("x")
assert d([a()], passt=bricht) is None and d([a("T-00000001", erlaubt=(("datei_schreiben", "boese"), ("datei_schreiben", "docs/**")))])["eintrag"]["muster"] == "docs/**"
'''

STAGES = [
    {"name": "deckung", "no_own_check": False, "task": TASK, "hidden": {"hidden_aufgabe_deckung.py": CHECKS}},
]
