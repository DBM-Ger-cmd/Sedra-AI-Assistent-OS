"""Differenztest-Faelle fuer den A/B-Bau (ab_bau.py): am3_berechtigung. Diese Spec ist NICHT auf die Randfall-Muster der Checkliste geschaerft
(docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md Abschnitt 5): ihre versteckten Tests lassen Fehler durch, die der Differenztest findet.
Nur Faelle, die die Spec eindeutig festlegt (kein Fall, in dem schon die Referenz mit etwas anderem als dem vereinbarten ValueError scheitert):
Zeichenklassen (`²`, arabische und volle Ziffern), Text statt Liste (Teilstring-Treffer), bool statt Zahl, falsche Typen, Eingaben nicht veraendern,
vereinbarte Fehlertexte, Reihenfolge der Pruefungen."""

MODUL = "berechtigung"

LISTEN = [["a", "b"], ["b", "a", "a"], [], ("a", "b"), {"a"}, "a", "ab", None, 5, {"a": 1}, ["a", 1], ["a", None], ["a", ["b"]], [b"a"], [True], ["a²"], ["ä"], ["a", "A"]]
EINTRAEGE = [None, [], "x", 5, {}, {"manifest_sha256": "h"}, {"manifest_sha256": "h", "aktiv": True}, {"manifest_sha256": "h", "aktiv": True, "gewaehrt": ["a", "b"]},
             {"manifest_sha256": "h", "aktiv": True, "gewaehrt": ["a"]}, {"manifest_sha256": "h", "aktiv": True, "gewaehrt": ("a", "b")},
             {"manifest_sha256": "h", "aktiv": True, "gewaehrt": "ab"}, {"manifest_sha256": "h", "aktiv": True, "gewaehrt": None},
             {"manifest_sha256": "h", "aktiv": True, "gewaehrt": ["a", 5, None, ["b"], "b"]}, {"manifest_sha256": "h", "aktiv": "True", "gewaehrt": ["a", "b"]},
             {"manifest_sha256": "h", "aktiv": 1, "gewaehrt": ["a", "b"]}, {"manifest_sha256": "h", "aktiv": False, "gewaehrt": ["a", "b"]},
             {"manifest_sha256": "h", "gewaehrt": ["a", "b"]}, {"manifest_sha256": "x", "aktiv": True, "gewaehrt": ["a", "b"]}, {"manifest_sha256": None, "aktiv": True, "gewaehrt": ["a"]},
             {"manifest_sha256": 5, "aktiv": True, "gewaehrt": ["a"]}, {"aktiv": True, "gewaehrt": ["a", "b"]}, {"manifest_sha256": "H", "aktiv": True, "gewaehrt": ["a", "b"]},
             {"manifest_sha256": "h", "aktiv": True, "gewaehrt": ["b", "a", "c", "a"], "vertrauen": "COMMUNITY", "extra": [1]}]
BEANTRAGT = [[], ["a"], ["a", "b"], ["b", "a", "a"], ["c", "b", "a"], ("a",), {"b"}, "a", None, ["a", 1], ["a", ["b"]], ["z", "y"], ["a²"]]
HASHES = ["h", "x", None, 5, ""]
TYPEN = [["rechnung"], ("rechnung",), {"rechnung"}, "rechnung", "rechnung.x", None, {"rechnung": 1}, 5, [], ["x", "rechnung"], ["a:b"]]
WERK = ["lesen:rechnung", "lesen:x", "lesen:rechnung.x", "lesen:rech", "lesen:echnung", "lesen:a:b", "LESEN:rechnung", "lesen", "ereignis:system.state", "ereignis:slot.changed",
        "ereignis:system.state ", "ereignis:andere", "ereignis:System.state", "ablage:1", "ablage:1048576", "ablage:1048577", "ablage:0", "ablage:00", "ablage:007", "ablage:²",
        "ablage:٣", "ablage:１", "ablage:", "ablage:-5", "ablage:+5", "ablage: 5", "ablage:5 ", "ablage:1_0", "ablage:1.5", "ablage:١٢", "ablage:5²",
        "verb:rechnung", "zelle:text", "dienst:microvm", "x", "", ":", "lesen:rechnung:x"]
EINTRAG_OK = {"vertrauen": "COMMUNITY", "manifest_sha256": "h", "aktiv": False, "gewaehrt": ["a", "b"], "extra": {"k": [1]}}
GEW_EINTRAEGE = [None, [], "x", 5, {}, {"gewaehrt": None}, {"gewaehrt": "ab"}, {"gewaehrt": ("a",)}, {"aktiv": True}, EINTRAG_OK, {"gewaehrt": []}, {"gewaehrt": ["b", "a", "a"], "aktiv": True}]
FAEHIGKEITEN = [["c"], ["a"], [], ["a", "a", "c"], ("c",), {"c"}, "c", None, 5, ["c", 1], ["c", ["d"]], ["ä"], ["a", "b", "c"]]
AKTIV = [True, False, 1, 0, "true", "", None, 1.0, [], [True]]


def faelle(ref):
    return {
        "wirksam": [(a, b) for a in LISTEN for b in (["a", "b"], ["b", "c"], [], "a", None)] + [(["a", "b"], ["a", "b"], o) for o in LISTEN + [[]]],
        "ladeentscheidung": [(e, b, h) for e in EINTRAEGE for b in BEANTRAGT for h in ("h",)] + [(EINTRAEGE[7], ["a"], h) for h in HASHES] + [(EINTRAEGE[18], ["a"], None), (EINTRAEGE[19], ["a"], 5)],
        "werkseinstellung": [([f], t) for f in WERK for t in (["rechnung"], [], None)] + [(WERK, t) for t in TYPEN] + [(b, ["a"]) for b in LISTEN],
        "eintrag_neu": [("h", v, g) for v in ("COMMUNITY", None, 5) for g in LISTEN],
        "gewaehren": [(e, f) for e in GEW_EINTRAEGE for f in FAEHIGKEITEN],
        "entziehen": [(e, f) for e in GEW_EINTRAEGE for f in FAEHIGKEITEN],
        "aktivieren": [(e, a) for e in GEW_EINTRAEGE for a in AKTIV],
    }
