"""Bau-Spec am1_manifest_felder: die neuen Manifest-Felder shells, profile und zelle (AM1, Stufe A1 der Roadmap, G3 Schritt S11, Kern ohne Anbindung).
Vier Stufen S1 bis S4, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das eigenstaendige Modul manifest_felder.py;
die Anbindung an desk/gateway.py (check_tool, manifest) macht Claude spaeter von Hand (Kandidat wird erst nach Durchsicht des Captains uebernommen).
S1 shells | S2 profile | S3 zelle | S4 Filter nach Shell und Profil.
Referenz: benchmarks/devvm_refs/am1_manifest_felder/manifest_felder.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am1_manifest_felder start "<Auftrag>"."""

NOTES = '''# Notizen manifest_felder
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: manifest_felder.py.
Die Funktionen pruefen Felder eines Modul-Manifests (ein dict aus einer YAML-Datei). Sie werfen nie eine Ausnahme; falsche Typen ergeben die genannte Fehlermeldung. Fehlermeldungen und Warnungen sind Texte genau in der angegebenen Schreibweise. Ein Muster gilt immer fuer den ganzen Text (kein Zeilenumbruch am Ende).
'''

TASK_S1 = '''Lege manifest_felder.py an mit pruefe_shells(wert, bekannte=None) -> tuple (fehler, warnungen), beides Listen von Texten.
- wert None heisst: das Feld fehlt, Ergebnis ([], []).
- Gueltig ist eine Liste (list) mit 1 bis 20 Eintraegen, jeder Eintrag ein Text, der vollstaendig auf das Muster [a-z0-9-]{2,40} passt, ohne doppelte Eintraege. Sonst ist das Ergebnis (["shells_invalid"], []). Ein Tupel, ein Text, ein dict, eine leere Liste oder eine Liste mit mehr als 20 Eintraegen sind ungueltig.
- Ist die Liste gueltig und bekannte nicht None (eine Menge oder Liste von Shell-Kennungen), gibt es fuer jeden Eintrag, der nicht in bekannte steht, eine Warnung "shells_unbekannt:<eintrag>" in der Reihenfolge der Liste; fehler bleibt []. Ist bekannte None, gibt es keine Warnungen.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze manifest_felder.py: pruefe_profile(wert, bekannte=None, grundfunktion=False) -> tuple (fehler, warnungen), beides Listen von Texten.
- wert None heisst: das Feld fehlt, Ergebnis ([], []).
- Gueltig ist eine Liste (list) mit 1 bis 40 Eintraegen, jeder Eintrag ein Text, der vollstaendig auf das Muster [a-z0-9][a-z0-9-]{1,39} passt, ohne doppelte Eintraege. Sonst ist das Ergebnis (["profile_invalid"], []).
- Ist die Liste gueltig: Ist bekannte nicht None, gibt es fuer jeden Eintrag, der weder in bekannte steht noch "standard" ist, eine Warnung "profil_unbekannt:<eintrag>" in der Reihenfolge der Liste ("standard" ist immer bekannt). Ist grundfunktion wahr, kommt danach als letzte Warnung "grundfunktion_ignoriert_profil". fehler ist [].
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze manifest_felder.py: pruefe_zelle(wert, kind, orte) -> list[str] (nur Fehlermeldungen). orte ist eine Menge oder Liste erlaubter Ort-Kennungen.
- wert None heisst: das Feld fehlt, Ergebnis [].
- Ist kind nicht genau "instrument", ist das Ergebnis ["zelle_nur_fuer_instrument"]. Ist wert kein dict, ist es ["zelle_invalid"].
- Sonst werden diese Regeln in dieser Reihenfolge geprueft, jede verletzte ergibt eine Meldung:
  1. "feld" muss ein Text sein, der vollstaendig auf [a-z][a-z0-9_]{1,30} passt (fehlt er, ist das ein Verstoss): "zelle_feld_invalid".
  2. "label" muss ein Text mit 1 bis 20 Zeichen sein (fehlt er, ist das ein Verstoss): "zelle_label_invalid".
  3. "ort" ist optional; steht der Schluessel im dict, muss der Wert in orte vorkommen: sonst "zelle_ort_unbekannt".
  4. "aktion" ist optional; steht der Schluessel im dict, muss der Wert ein Text sein, der entweder genau "freigaben", "modellmenue" oder "routermenue" ist oder vollstaendig auf einstellungen:[a-z]+(/[a-z]+)? passt: sonst "zelle_aktion_invalid".
  5. "quelle" ist optional; steht der Schluessel im dict, muss der Wert ein Text sein, der vollstaendig auf [a-z][a-z0-9_]{1,30} passt: sonst "zelle_quelle_invalid".
  6. Fuer jeden anderen Schluessel im dict, in aufsteigender Reihenfolge der Schluessel (Textvergleich): "zelle_unbekannt:<schluessel>".
Ein gueltiges dict ergibt [].
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze manifest_felder.py: filtere(tools, shell, profil, grundfunktionen) -> tuple (sichtbar, nicht_in_shell, nicht_in_profil).
tools ist eine Liste von dicts mit "id", "name" und den optionalen Schluesseln "shells" und "profile" (je eine Liste von Texten oder None beziehungsweise fehlend). shell ist die Kennung der aktiven Shell, profil die des aktiven Profils oder None; None heisst das Profil "standard". grundfunktionen ist eine Menge oder Liste von Werkzeug-Kennungen.
Jeder Eintrag aus tools, der ein dict ist (andere Eintraege werden uebersprungen), geht in genau eine der drei Listen, in der Reihenfolge von tools:
1. Steht seine "id" in grundfunktionen: in sichtbar (als dasselbe dict), ohne weitere Pruefung.
2. Sonst, wenn "shells" nicht None ist und shell nicht darin steht: in nicht_in_shell als neues dict {"id": ..., "name": ..., "shells": <die Liste>}.
3. Sonst, wenn "profile" nicht None ist und das aktive Profil (profil oder "standard") nicht darin steht: in nicht_in_profil als neues dict {"id": ..., "name": ..., "profile": <die Liste>}.
4. Sonst in sichtbar (als dasselbe dict).
Die Eingabe wird nicht veraendert. Fehlende Schluessel "id" oder "name" ergeben None in den neuen dicts.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert pruefe_shells(None) == ([], [])
assert pruefe_shells(["harness"]) == ([], [])
assert pruefe_shells(["harness", "cockpit"]) == ([], [])
assert pruefe_shells([]) == (["shells_invalid"], [])
assert pruefe_shells("harness") == (["shells_invalid"], [])
assert pruefe_shells(("harness",)) == (["shells_invalid"], [])
assert pruefe_shells({"a": 1}) == (["shells_invalid"], [])
assert pruefe_shells(["harness", "harness"]) == (["shells_invalid"], [])
assert pruefe_shells(["H"]) == (["shells_invalid"], [])
assert pruefe_shells(["a"]) == (["shells_invalid"], [])
assert pruefe_shells([5]) == (["shells_invalid"], [])
assert pruefe_shells(["harness\\n"]) == (["shells_invalid"], [])
assert pruefe_shells(["s%d" % i for i in range(20)]) == ([], [])
assert pruefe_shells(["s%d" % i for i in range(21)]) == (["shells_invalid"], [])
assert pruefe_shells(["harness", "xp", "mini"], ["harness", "cockpit"]) == ([], ["shells_unbekannt:xp", "shells_unbekannt:mini"])
assert pruefe_shells(["harness"], {"harness"}) == ([], [])
assert pruefe_shells(["harness"], []) == ([], ["shells_unbekannt:harness"])
assert pruefe_shells(["xp"], None) == ([], [])
assert pruefe_shells(["H"], ["harness"]) == (["shells_invalid"], [])
''', "from manifest_felder import pruefe_shells\n")

C2 = hidden('''
assert pruefe_profile(None) == ([], [])
assert pruefe_profile(["standard", "kmu", "stick"]) == ([], [])
assert pruefe_profile([]) == (["profile_invalid"], [])
assert pruefe_profile("kmu") == (["profile_invalid"], [])
assert pruefe_profile(["kmu", "kmu"]) == (["profile_invalid"], [])
assert pruefe_profile(["-kmu"]) == (["profile_invalid"], [])
assert pruefe_profile(["a"]) == (["profile_invalid"], [])
assert pruefe_profile(["KMU"]) == (["profile_invalid"], [])
assert pruefe_profile([None]) == (["profile_invalid"], [])
assert pruefe_profile(["p%d" % i for i in range(40)]) == ([], [])
assert pruefe_profile(["p%d" % i for i in range(41)]) == (["profile_invalid"], [])
assert pruefe_profile(["a" * 40]) == ([], [])
assert pruefe_profile(["a" * 41]) == (["profile_invalid"], [])
assert pruefe_profile(["standard", "kmu", "stick"], ["kmu"]) == ([], ["profil_unbekannt:stick"])
assert pruefe_profile(["standard"], []) == ([], [])
assert pruefe_profile(["kmu"], None) == ([], [])
assert pruefe_profile(["kmu"], ["kmu"], True) == ([], ["grundfunktion_ignoriert_profil"])
assert pruefe_profile(["kmu", "x1"], ["kmu"], True) == ([], ["profil_unbekannt:x1", "grundfunktion_ignoriert_profil"])
assert pruefe_profile(["kmu"], None, True) == ([], ["grundfunktion_ignoriert_profil"])
assert pruefe_profile([], ["kmu"], True) == (["profile_invalid"], [])
assert pruefe_profile(None, None, True) == ([], [])
''', "from manifest_felder import pruefe_profile\n")

C3 = hidden('''
O = ["models", "hardware", "slots"]
assert pruefe_zelle(None, "instrument", O) == []
assert pruefe_zelle(None, "tool", O) == []
assert pruefe_zelle({"feld": "ram", "label": "RAM"}, "instrument", O) == []
assert pruefe_zelle({"feld": "ram", "label": "RAM", "ort": "hardware", "aktion": "modellmenue", "quelle": "gpu"}, "instrument", O) == []
assert pruefe_zelle({"feld": "ram", "label": "RAM"}, "tool", O) == ["zelle_nur_fuer_instrument"]
assert pruefe_zelle("x", "instrument", O) == ["zelle_invalid"]
assert pruefe_zelle(["feld"], "instrument", O) == ["zelle_invalid"]
assert pruefe_zelle({}, "instrument", O) == ["zelle_feld_invalid", "zelle_label_invalid"]
assert pruefe_zelle({"feld": "R", "label": "x"}, "instrument", O) == ["zelle_feld_invalid"]
assert pruefe_zelle({"feld": "r", "label": "x"}, "instrument", O) == ["zelle_feld_invalid"]
assert pruefe_zelle({"feld": "ram", "label": ""}, "instrument", O) == ["zelle_label_invalid"]
assert pruefe_zelle({"feld": "ram", "label": "x" * 20}, "instrument", O) == []
assert pruefe_zelle({"feld": "ram", "label": "x" * 21}, "instrument", O) == ["zelle_label_invalid"]
assert pruefe_zelle({"feld": "ram", "label": 5}, "instrument", O) == ["zelle_label_invalid"]
assert pruefe_zelle({"feld": "ram", "label": "R", "ort": "nirgends"}, "instrument", O) == ["zelle_ort_unbekannt"]
assert pruefe_zelle({"feld": "ram", "label": "R", "ort": None}, "instrument", O) == ["zelle_ort_unbekannt"]
assert pruefe_zelle({"feld": "ram", "label": "R", "ort": "slots"}, "instrument", {"slots"}) == []
for gut in ("freigaben", "modellmenue", "routermenue", "einstellungen:system", "einstellungen:system/ram"):
    assert pruefe_zelle({"feld": "ram", "label": "R", "aktion": gut}, "instrument", O) == []
for schlecht in ("", "oeffnen", "einstellungen:", "einstellungen:a/b/c", "einstellungen:Sys", "einstellungen:system/", 7):
    assert pruefe_zelle({"feld": "ram", "label": "R", "aktion": schlecht}, "instrument", O) == ["zelle_aktion_invalid"]
assert pruefe_zelle({"feld": "ram", "label": "R", "quelle": "gpu"}, "instrument", O) == []
assert pruefe_zelle({"feld": "ram", "label": "R", "quelle": "GPU"}, "instrument", O) == ["zelle_quelle_invalid"]
assert pruefe_zelle({"feld": "ram", "label": "R", "ort": ["a"]}, "instrument", {"models"}) == ["zelle_ort_unbekannt"]
assert pruefe_zelle({"feld": "ram", "label": "R", "ort": {"a": 1}}, "instrument", {"models"}) == ["zelle_ort_unbekannt"]
assert pruefe_zelle({"feld": "ram", "label": "R", "zebra": 1, "alpha": 2}, "instrument", O) == ["zelle_unbekannt:alpha", "zelle_unbekannt:zebra"]
assert pruefe_zelle({"feld": "R", "label": "", "ort": "x", "aktion": "y", "quelle": "Z", "b": 1}, "instrument", O) == ["zelle_feld_invalid", "zelle_label_invalid", "zelle_ort_unbekannt", "zelle_aktion_invalid", "zelle_quelle_invalid", "zelle_unbekannt:b"]
''', "from manifest_felder import pruefe_zelle\n")

C4 = hidden('''
def t(i, shells="fehlt", profile="fehlt"):
    d = {"id": i, "name": i.upper()}
    if shells != "fehlt":
        d["shells"] = shells
    if profile != "fehlt":
        d["profile"] = profile
    return d
alle = t("a")
nur_h = t("b", shells=["harness"])
nur_c = t("c", shells=["cockpit"])
kmu = t("d", profile=["kmu"])
std = t("e", profile=["standard"])
beides = t("f", shells=["harness"], profile=["stick"])
gf = t("decisions", shells=["cockpit"], profile=["kmu"])
tools = [alle, nur_h, nur_c, kmu, std, beides, gf]
s, ns, np_ = filtere(tools, "harness", None, ["decisions"])
assert [x["id"] for x in s] == ["a", "b", "e", "decisions"]
assert ns == [{"id": "c", "name": "C", "shells": ["cockpit"]}]
assert np_ == [{"id": "d", "name": "D", "profile": ["kmu"]}, {"id": "f", "name": "F", "profile": ["stick"]}]
assert s[0] is alle
s, ns, np_ = filtere(tools, "harness", "kmu", {"decisions"})
assert [x["id"] for x in s] == ["a", "b", "d", "decisions"]
assert [x["id"] for x in np_] == ["e", "f"]
s, ns, np_ = filtere(tools, "harness", "stick", [])
assert [x["id"] for x in s] == ["a", "b", "f"]
assert [x["id"] for x in ns] == ["c", "decisions"]
assert [x["id"] for x in np_] == ["d", "e"]
s, ns, np_ = filtere(tools, "cockpit", "standard", ["decisions"])
assert [x["id"] for x in s] == ["a", "c", "e", "decisions"]
assert [x["id"] for x in ns] == ["b", "f"]
assert [x["id"] for x in np_] == ["d"]
assert filtere([], "harness", None, []) == ([], [], [])
assert filtere(None, "harness", None, None) == ([], [], [])
s, ns, np_ = filtere([None, 5, "x", alle, {"shells": ["xp"]}], "harness", None, None)
assert s == [alle]
assert ns == [{"id": None, "name": None, "shells": ["xp"]}]
assert np_ == []
vorher = [dict(x) for x in tools]
filtere(tools, "harness", "kmu", ["decisions"])
assert tools == vorher
''', "from manifest_felder import filtere\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_mfelder_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_mfelder_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_mfelder_s3.py": C3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_mfelder_s4.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_mfelder_s1.py": C1}
