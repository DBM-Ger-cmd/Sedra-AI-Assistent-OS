"""Differenztest-Faelle fuer den A/B-Bau (ab_bau.py): am3_rechte_diff. Randfaelle der Checkliste (docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md Abschnitt 3):
Unicode-Ziffern, bool statt Zahl, unhashbare Werte, gemischte Schluesseltypen, Eingaben nicht veraendern, fremder Fehlertext.
Neue Spec: eine Datei <spec>.py mit MODUL (Name der Loesungsdatei ohne .py) und faelle(ref) -> {Funktionsname: [Argument-Tupel]}."""

MODUL = "rechte_diff"

STUFE = ["lesen:x", "verb:x", "ereignis:system.state", "ereignis:andere", "zelle:text", "zelle:x", "ablage:0", "ablage:1048576", "ablage:1048577", "ablage:007",
         "ablage:²", "ablage:١٢", "ablage:", "ablage:-1", "ablage:1.5", "ablage: 5", "dienst:microvm", "dienst:host", "dienst:", "nix:y", "lesen:", "lesen",
         "", ":", "::", "lesen:a:b", "ablage:1_0", 5, None, ["lesen:x"], b"lesen:x", "ablage:１２"]
RECHTE = [None, {}, [], "x", 5, {"lesen": ["a"]}, {"lesen": []}, {"lesen": [""]}, {"lesen": [1]}, {"lesen": [["a"]]}, {"lesen": "a"}, {"lesen": ["b", "a", "b"]},
          {"verben": ["v"], "ereignisse": ["e"]}, {"ereignisse": [{"a": 1}]}, {"zelle": "text"}, {"zelle": "nein"}, {"zelle": "x"}, {"zelle": []}, {"zelle": {}}, {"zelle": None},
          {"ablage": 0}, {"ablage": 5}, {"ablage": -1}, {"ablage": True}, {"ablage": 1.0}, {"ablage": "5"}, {"ablage": None}, {"dienst": "host"}, {"dienst": "microvm"},
          {"dienst": "nein"}, {"dienst": []}, {"dienst": {}}, {"dienst": "x"}, {"x": 1}, {"x": 1, "a": 2}, {1: ["a"]}, {1: 1, "a": 2}, {"lesen": ["a"], "zzz": 1, "aaa": 2},
          {"lesen": ["a"], "verben": ["a"], "ereignisse": ["a"], "zelle": "text", "ablage": 3, "dienst": "microvm"}, {"lesen": ("a",)}, {"lesen": ["a²"]}]
DIFF = [(a, b) for a in (None, {}, {"lesen": ["a"]}, {"lesen": ["a"], "dienst": "host"}, {"ablage": 5})
        for b in (None, {}, {"lesen": ["a", "b"]}, {"dienst": "microvm"}, {"ablage": 2000000}, {"zelle": "text", "ablage": 9}, {"x": 1}, "x")]
URTEIL = [[], None, "x", 5, [1, "a", None], [{"richtung": "neu", "faehigkeit": "lesen:a", "stufe": "A"}], [{"richtung": "neu", "stufe": "C", "faehigkeit": "dienst:host"}],
          [{"richtung": "neu", "stufe": "B", "faehigkeit": "verb:x"}], [{"richtung": "entfaellt", "stufe": "C", "faehigkeit": "x"}], [{"richtung": "neu"}], [{}],
          [{"richtung": "neu", "stufe": "C", "faehigkeit": "a"}, {"richtung": "neu", "stufe": "C", "faehigkeit": "b"}, {"richtung": "neu", "stufe": "B", "faehigkeit": "c"}],
          [{"richtung": ["neu"], "stufe": "C"}], [{"richtung": "neu", "stufe": ["C"], "faehigkeit": "x"}], [{"richtung": "neu", "stufe": "c", "faehigkeit": "x"}]]
SCHLUESSEL = [[], ["a"], ["b", "a"], ["a", "a"], ["a", "b", "a"], None, "a", ("a",), [1], ["a", None], [["a"]], ["ä"], ["a,b"], ["a", "a "], set(), {"a"}, ["a" * 1000] * 5]


def faelle(ref):
    urteil = [(x,) for x in URTEIL]
    for alt, neu in DIFF:                       # echte Diffs der Referenz als Eingabe des Urteils
        try:
            urteil.append((ref.rechte_diff(alt, neu),))
        except Exception:                       # noqa: BLE001 - ein Fehler der Referenz ergibt keinen Eingabefall
            pass
    return {"stufe": [(x,) for x in STUFE], "rechte_zu_faehigkeiten": [(x,) for x in RECHTE], "rechte_diff": DIFF, "rechte_urteil": urteil,
            "rechte_schluessel": [(x,) for x in SCHLUESSEL]}
