"""Bau-Spec rueckblick_antrag: die reinen Teile des Werkzeugs rueckblick_schreiben (W4, SPEC_LERNEN_UND_HILFSWERKZEUGE_v1 LR-10, LR-14, LR-15): den Antrag pruefen, Regeln an LESSONS.md anhaengen, das Budget von 25 Regelzeilen berechnen.
Vier Stufen S1 bis S4, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul rueckblick_antrag.py (Zielort spaeter harness/rueckblick_antrag.py). Es liest und schreibt keine Datei:
Das Werkzeug, der Antrag im Posteingang, die Klasse H, der Vorbehalt docs/AAR/** und das Schreiben der Dateien (LR-11 bis LR-14, LR-16, LR-17) macht Claude spaeter von Hand, nach der Entscheidung E3 der Spec Freigaben S4.
S1 Antrag: id, titel, bericht | S2 Antrag: regeln, quelle, belege | S3 Regeln anhaengen | S4 Budget.
Referenz: benchmarks/devvm_refs/rueckblick_antrag/rueckblick_antrag.py."""

NOTES = '''# Notizen rueckblick_antrag
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: rueckblick_antrag.py. Keine Datei wird gelesen oder geschrieben.
Alle Funktionen veraendern ihre Eingaben nie. Texte und Fehlercodes stehen unten genau so, wie sie erscheinen sollen; jedes Zeichen zaehlt.
Fehler sind Texte der Form "<feld>:<code>". Codes: "fehlt" (Schluessel fehlt oder ist None), "typ" (falscher Datentyp), "ungueltig" (Wert verletzt die Regel), "unbekannt" (Schluessel nicht erlaubt).
Ein "echtes Datum" hat das Format JJJJ-MM-TT mit ASCII-Ziffern (Regex mit re.ASCII und mit fullmatch: der ganze Text muss passen, auch ein Zeilenumbruch am Ende macht ihn ungueltig; nicht \\d ohne Flag). Das gilt auch fuer jeden anderen Wert, der unten mit einem regulaeren Ausdruck beschrieben ist. und besteht datetime.date.fromisoformat.
'''

TASK_S1 = '''Lege rueckblick_antrag.py an mit antrag_pruefen(p) -> tuple (antrag, fehler). p ist der Antrag eines Rueckblicks (ein dict). Ist p kein dict: (None, ["antrag:typ"]).
Geprueft werden in dieser Stufe nur diese Schluessel:
- id (Pflicht, str): "AAR-JJJJ-MM-TT-stichwort". Der Teil JJJJ-MM-TT muss ein echtes Datum sein; das Stichwort besteht nur aus ASCII-Kleinbuchstaben, Ziffern und Bindestrichen, beginnt mit Buchstabe oder Ziffer und ist 1 bis 40 Zeichen lang. Regulaerer Ausdruck mit re.ASCII: ^AAR-([0-9]{4}-[0-9]{2}-[0-9]{2})-[a-z0-9][a-z0-9-]{0,39}$
- titel (Pflicht, str, nach strip() 1 bis 120 Zeichen und ohne Zeilenumbruch)
- bericht (Pflicht, str, nach strip() nicht leer und hoechstens 30 Zeilen; Zeilen zaehlt strip() danach splitlines())
Die Schluessel regeln, quelle und belege werden in dieser Stufe weder geprueft noch uebernommen. Jeder andere Schluessel ist ein Fehler "<schluessel>:unbekannt".
Alle Fehler werden gesammelt, in der Reihenfolge id, titel, bericht, danach die unbekannten Schluessel alphabetisch.
Ergebnis ohne Fehler: (antrag, []) mit einem neuen dict mit genau den Schluesseln id, titel, bericht (titel und bericht mit strip() bereinigt). Mit Fehlern: (None, fehler).
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Erweitere antrag_pruefen in rueckblick_antrag.py. Dazu kommen diese Schluessel (die Regeln fuer id, titel, bericht und unbekannte Schluessel bleiben):
- regeln (optional, Liste von str, hoechstens 5 Eintraege; jeder Eintrag nach strip() 1 bis 200 Zeichen und ohne Zeilenumbruch; fehlt der Schluessel oder ist er None, gilt die leere Liste)
- quelle (Pflicht, str, genau einer der Texte "korrektur", "lob", "auftrag")
- belege (optional, Liste von str; jeder Eintrag muss zu ^A-[0-9A-F]{8}$ mit re.ASCII passen; Vorgabe leere Liste)
Fehler: regeln keine Liste: "regeln:typ"; mehr als 5 Eintraege: "regeln:ungueltig" (zusaetzlich zu Fehlern einzelner Eintraege); ein ungueltiger Eintrag: "regeln[k]:ungueltig" mit der Position k ab 0, jeder einzeln. quelle: "quelle:fehlt", "quelle:typ" (kein str), "quelle:ungueltig" (anderer Text, auch andere Gross-/Kleinschreibung). belege keine Liste: "belege:typ"; ungueltiger Eintrag: "belege[k]:ungueltig", jeder einzeln.
Reihenfolge aller Fehler: id, titel, bericht, regeln (zuerst "regeln:..." dann die Eintraege), quelle, belege, zuletzt die unbekannten Schluessel alphabetisch.
Ergebnis ohne Fehler: (antrag, []) mit einem neuen dict mit genau den sechs Schluesseln id, titel, bericht, regeln, quelle, belege; die Regeln sind mit strip() bereinigt; regeln und belege sind neue Listen.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze rueckblick_antrag.py: lessons_anhaengen(text, antrag_id, regeln, datum) -> str. text ist der bisherige Inhalt der Datei LESSONS.md (str; None oder nur Leerraum zaehlt als leer), antrag_id eine id wie in antrag_pruefen (gleiche Regel inklusive echtem Datum), regeln eine Liste von Regeltexten, datum ein echtes Datum JJJJ-MM-TT.
Ergebnis ist der neue Inhalt der Datei. Jede Regel wird als eigene Zeile angehaengt: "- " + datum + ": " + regel.strip() + " (Quelle: " + antrag_id + ")". Regeln, die kein str oder nach strip() leer sind, werden uebersprungen; regeln darf None sein (dann gibt es keine Regeln). Eine Zeile, die (nach strip() der vorhandenen Zeilen) schon genauso im Text steht, und eine Wiederholung innerhalb von regeln werden nicht noch einmal angehaengt.
Gibt es keine neue Zeile, ist das Ergebnis der Text unveraendert (bei None ein leerer String ""). Sonst: ist der bisherige Text leer, beginnt das Ergebnis mit der Ueberschrift "# Gelernte Regeln", einem Zeilenumbruch, einer Leerzeile (also "# Gelernte Regeln\\n\\n") und danach den neuen Zeilen; ist er nicht leer, bleibt er erhalten, abschliessende Zeilenumbrueche werden durch genau einen ersetzt, dann folgen die neuen Zeilen. Das Ergebnis endet immer mit genau einem Zeilenumbruch, die Zeilen sind durch "\\n" getrennt.
Fehler: datum kein echtes Datum (auch kein str): ValueError("datum"); antrag_id ungueltig: ValueError("id"); das Datum wird zuerst geprueft, beide vor allem anderen.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze rueckblick_antrag.py: lessons_budget(text, hinzu, grenze=25) -> dict mit genau den Schluesseln "zeilen_jetzt", "zeilen_danach", "zu_viel", "archivieren".
Regelzeilen des Textes sind alle Zeilen, die nach strip() nicht leer sind und nicht mit "#" beginnen (Ueberschriften und Leerzeilen zaehlen nicht); text darf None sein (keine Zeilen). zeilen_jetzt ist ihre Anzahl, zeilen_danach ist zeilen_jetzt + hinzu, zu_viel ist max(0, zeilen_danach - grenze). archivieren ist eine neue Liste der aeltesten Regelzeilen (die ersten im Text, mit strip() bereinigt), und zwar zu_viel Stueck, aber nie mehr als es Regelzeilen gibt.
Fehler: hinzu ist kein int, ein bool oder kleiner als 0: ValueError("hinzu").
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
def antrag(**kw):
    d = {"id": "AAR-2026-11-12-test", "titel": "Titel", "bericht": "Zeile", "quelle": "korrektur", "regeln": [], "belege": []}
    d.update(kw)
    return d

r, fe = antrag_pruefen(antrag(titel="  Titel  ", bericht="\\n Zeile \\n"))
assert fe == []
assert (r["id"], r["titel"], r["bericht"]) == ("AAR-2026-11-12-test", "Titel", "Zeile")
assert antrag_pruefen("x") == (None, ["antrag:typ"])
assert antrag_pruefen(antrag(id=None)) == (None, ["id:fehlt"])
assert antrag_pruefen(antrag(id=5)) == (None, ["id:typ"])
assert antrag_pruefen(antrag(id="AAR-2026-11-12")) == (None, ["id:ungueltig"])
assert antrag_pruefen(antrag(id="AAR-2026-02-30-x")) == (None, ["id:ungueltig"])
assert antrag_pruefen(antrag(id="AAR-2026-11-12-test\\n")) == (None, ["id:ungueltig"])
assert antrag_pruefen(antrag(id="AAR-\\u0662\\u0660\\u0662\\u0666-11-12-x")) == (None, ["id:ungueltig"])
assert antrag_pruefen(antrag(id="AAR-2026-11-12-" + "a" * 40))[1] == []
assert antrag_pruefen(antrag(id="AAR-2026-11-12-" + "a" * 41)) == (None, ["id:ungueltig"])
assert antrag_pruefen(antrag(titel=["a"])) == (None, ["titel:typ"])
assert antrag_pruefen(antrag(titel="a\\nb")) == (None, ["titel:ungueltig"])
assert antrag_pruefen(antrag(titel="x" * 121)) == (None, ["titel:ungueltig"])
assert antrag_pruefen(antrag(bericht=None)) == (None, ["bericht:fehlt"])
assert antrag_pruefen(antrag(bericht=" \\n ")) == (None, ["bericht:ungueltig"])
assert antrag_pruefen(antrag(bericht="\\n".join("z%d" % i for i in range(30))))[1] == []
assert antrag_pruefen(antrag(bericht="\\n".join("z%d" % i for i in range(31)))) == (None, ["bericht:ungueltig"])
assert antrag_pruefen(antrag(zusatz=1, anderes=2)) == (None, ["anderes:unbekannt", "zusatz:unbekannt"])
assert antrag_pruefen(antrag(id="x", titel=3, bericht=None, zz=1)) == (None, ["id:ungueltig", "titel:typ", "bericht:fehlt", "zz:unbekannt"])
''', "from rueckblick_antrag import antrag_pruefen\n")

C2 = hidden('''
def antrag(**kw):
    d = {"id": "AAR-2026-11-12-test", "titel": "Titel", "bericht": "Zeile", "quelle": "korrektur"}
    d.update(kw)
    return d

assert antrag_pruefen(antrag()) == ({"id": "AAR-2026-11-12-test", "titel": "Titel", "bericht": "Zeile", "regeln": [], "quelle": "korrektur", "belege": []}, [])
assert antrag_pruefen(antrag(regeln=["  Regel eins  ", "Zwei"]))[0]["regeln"] == ["Regel eins", "Zwei"]
assert antrag_pruefen(antrag(regeln=None, belege=None))[0]["regeln"] == []
assert antrag_pruefen(antrag(regeln="Regel")) == (None, ["regeln:typ"])
assert antrag_pruefen(antrag(regeln=["a"] * 6)) == (None, ["regeln:ungueltig"])
assert antrag_pruefen(antrag(regeln=["a"] * 5))[1] == []
assert antrag_pruefen(antrag(regeln=["ok", "", "x" * 201, "a\\nb", 7])) == (None, ["regeln[1]:ungueltig", "regeln[2]:ungueltig", "regeln[3]:ungueltig", "regeln[4]:ungueltig"])
assert antrag_pruefen(antrag(regeln=["x" * 200]))[1] == []
a = antrag()
del a["quelle"]
assert antrag_pruefen(a) == (None, ["quelle:fehlt"])
assert antrag_pruefen(antrag(quelle=3)) == (None, ["quelle:typ"])
assert antrag_pruefen(antrag(quelle="Korrektur")) == (None, ["quelle:ungueltig"])
assert [antrag_pruefen(antrag(quelle=q))[1] for q in ("korrektur", "lob", "auftrag")] == [[], [], []]
assert antrag_pruefen(antrag(belege="A-0123ABCD")) == (None, ["belege:typ"])
assert antrag_pruefen(antrag(belege=["A-0123ABCD", "a-0123ABCD", "A-0123abcd", "A-0123ABC", 5, "A-0123ABCD\\n"])) == (None, ["belege[1]:ungueltig", "belege[2]:ungueltig", "belege[3]:ungueltig", "belege[4]:ungueltig", "belege[5]:ungueltig"])
assert antrag_pruefen(antrag(belege=["A-\\u0660\\u0661\\u0662\\u0663\\u0664\\u0665\\u0666\\u0667"])) == (None, ["belege[0]:ungueltig"])
assert antrag_pruefen(antrag(belege=["A-0123ABCD", "A-FFFFFFFF"]))[0]["belege"] == ["A-0123ABCD", "A-FFFFFFFF"]
assert antrag_pruefen({"id": "x", "titel": 1, "bericht": None, "regeln": 5, "quelle": "x", "belege": 1, "zz": 0}) == (None, ["id:ungueltig", "titel:typ", "bericht:fehlt", "regeln:typ", "quelle:ungueltig", "belege:typ", "zz:unbekannt"])
q = antrag(regeln=["r"], belege=["A-0123ABCD"])
r, _ = antrag_pruefen(q)
r["regeln"].append("z")
r["belege"].append("z")
assert (q["regeln"], q["belege"]) == (["r"], ["A-0123ABCD"])
''', "from rueckblick_antrag import antrag_pruefen\n")

C3 = hidden('''
ID = "AAR-2026-11-12-test"
Z = "- 2026-11-12: Regel (Quelle: AAR-2026-11-12-test)"
assert lessons_anhaengen("", ID, ["Regel"], "2026-11-12") == "# Gelernte Regeln\\n\\n" + Z + "\\n"
assert lessons_anhaengen(None, ID, ["Regel"], "2026-11-12") == "# Gelernte Regeln\\n\\n" + Z + "\\n"
assert lessons_anhaengen("  \\n ", ID, ["Regel"], "2026-11-12") == "# Gelernte Regeln\\n\\n" + Z + "\\n"
assert lessons_anhaengen("# Kopf\\n\\n- alt", ID, ["Regel"], "2026-11-12") == "# Kopf\\n\\n- alt\\n" + Z + "\\n"
assert lessons_anhaengen("# Kopf\\n- alt\\n\\n\\n", ID, ["Regel"], "2026-11-12") == "# Kopf\\n- alt\\n" + Z + "\\n"
assert lessons_anhaengen("- alt\\n", ID, ["Eins", " Zwei "], "2026-11-12") == "- alt\\n- 2026-11-12: Eins (Quelle: AAR-2026-11-12-test)\\n- 2026-11-12: Zwei (Quelle: AAR-2026-11-12-test)\\n"
assert lessons_anhaengen("- alt\\n", ID, ["A", "A"], "2026-11-12").count("2026-11-12: A") == 1
assert lessons_anhaengen("- alt\\n" + Z + "\\n", ID, ["Regel"], "2026-11-12") == "- alt\\n" + Z + "\\n"
assert lessons_anhaengen("- alt\\n  " + Z + "  \\n", ID, ["Regel"], "2026-11-12") == "- alt\\n  " + Z + "  \\n"
assert lessons_anhaengen("- alt", ID, [], "2026-11-12") == "- alt"
assert lessons_anhaengen("- alt", ID, None, "2026-11-12") == "- alt"
assert lessons_anhaengen(None, ID, [], "2026-11-12") == ""
assert lessons_anhaengen("- alt\\n", ID, ["", "  ", 5, None, "Regel"], "2026-11-12") == "- alt\\n" + Z + "\\n"
assert lessons_anhaengen("  ", ID, [" "], "2026-11-12") == "  "
assert lessons_anhaengen("# Kopf\\n\\n" + Z + "\\n", ID, ["Neu"], "2026-11-13").endswith("- 2026-11-13: Neu (Quelle: AAR-2026-11-12-test)\\n")
assert lessons_anhaengen("# Kopf\\n", ID, ["R"], "2026-11-12").count("# ") == 1
for datum in ("2026-13-01", "2026-02-30", "", None, 20261112, "2026-1-2", "2026-11-12\\n", "\\u0662\\u0660\\u0662\\u0666-11-12"):
    try:
        lessons_anhaengen("", ID, ["R"], datum)
    except ValueError as e:
        assert str(e) == "datum"
    else:
        raise AssertionError("kein ValueError datum")
for bad in ("AAR-2026-11-12", "x", None, "AAR-2026-02-30-x"):
    try:
        lessons_anhaengen("", bad, ["R"], "2026-11-12")
    except ValueError as e:
        assert str(e) == "id"
    else:
        raise AssertionError("kein ValueError id")
try:
    lessons_anhaengen("", "x", ["R"], "kein")
except ValueError as e:
    assert str(e) == "datum"
else:
    raise AssertionError("kein ValueError")
''', "from rueckblick_antrag import lessons_anhaengen\n")

C4 = hidden('''
assert lessons_budget("", 3) == {"zeilen_jetzt": 0, "zeilen_danach": 3, "zu_viel": 0, "archivieren": []}
assert lessons_budget(None, 0) == {"zeilen_jetzt": 0, "zeilen_danach": 0, "zu_viel": 0, "archivieren": []}
assert lessons_budget("# Kopf\\n\\n- a\\n  \\n## Unter\\n- b\\n", 1)["zeilen_jetzt"] == 2
text22 = "# Kopf\\n\\n" + "\\n".join("- r%d" % i for i in range(22)) + "\\n"
assert lessons_budget(text22, 3) == {"zeilen_jetzt": 22, "zeilen_danach": 25, "zu_viel": 0, "archivieren": []}
b = lessons_budget(text22, 4)
assert (b["zeilen_danach"], b["zu_viel"], b["archivieren"]) == (26, 1, ["- r0"])
assert lessons_budget(text22, 8)["archivieren"] == ["- r0", "- r1", "- r2", "- r3", "- r4"]
assert lessons_budget("- a\\n- b\\n- c\\n", 1, 2) == {"zeilen_jetzt": 3, "zeilen_danach": 4, "zu_viel": 2, "archivieren": ["- a", "- b"]}
assert lessons_budget("- a\\n- b\\n", 30)["zu_viel"] == 7
assert lessons_budget("- a\\n- b\\n", 30)["archivieren"] == ["- a", "- b"]
assert lessons_budget("  - a  \\n", 30, 0)["archivieren"] == ["- a"]
assert lessons_budget("- a\\n", 0, 0)["zu_viel"] == 1
assert sorted(lessons_budget("", 0)) == ["archivieren", "zeilen_danach", "zeilen_jetzt", "zu_viel"]
assert lessons_budget(text22, 4)["archivieren"] is not lessons_budget(text22, 4)["archivieren"]
for bad in (-1, 1.5, True, "3", None):
    try:
        lessons_budget("- a", bad)
    except ValueError as e:
        assert str(e) == "hinzu"
    else:
        raise AssertionError("kein ValueError hinzu")
''', "from rueckblick_antrag import lessons_budget\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_antrag_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_antrag_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_antrag_s3.py": C3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_antrag_s4.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_antrag_s1.py": C1}
