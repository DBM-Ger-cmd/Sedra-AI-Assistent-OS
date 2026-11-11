"""Bau-Spec am3_rechte_diff: Rechte einer App, Schutzstufen und der Rechte-Diff beim Update (AM3-01, AM3-07, AM3-14, Stufe A4, Kern ohne Anbindung).
Vier Stufen S1 bis S4, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul rechte_diff.py; die Anbindung an Gateway, Berechtigungsdatei und Update-Gate macht Claude spaeter von Hand.
S1 Rechte -> Faehigkeiten | S2 Schutzstufe | S3 Diff und Urteil | S4 Schluessel der Liste. Anspruchsvoller als die anderen Kerne: viele Regeln in einer Aufgabe.
Referenz: benchmarks/devvm_refs/am3_rechte_diff/rechte_diff.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am3_rechte_diff start "<Auftrag>"."""

NOTES = '''# Notizen rechte_diff
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: rechte_diff.py.
Eine App beantragt Rechte in ihrem Manifest als dict "rechte". Eine "Faehigkeit" ist ein Text der Form "<art>:<wert>", zum Beispiel "lesen:rechnung" oder "verb:rechnung.ablegen". Faehigkeiten haben eine Schutzstufe "A" (harmlos), "B" (braucht eine Entscheidung des Captains) oder "C" (nie erlaubt).
Fehler sind ValueError mit genau dem angegebenen Text. Die Eingaben werden nie veraendert. Ergebnislisten sind neue Listen.
'''

TASK_S1 = '''Lege rechte_diff.py an mit rechte_zu_faehigkeiten(rechte) -> list[str].
rechte ist None (ergibt []) oder ein dict; jedes andere ist ein Fehler ValueError("rechte_ungueltig"). Erlaubte Schluessel: lesen, verben, ereignisse, zelle, ablage, dienst. Gibt es andere Schluessel, ist es ein Fehler ValueError("rechte_unbekannt:<schluessel>") fuer den ersten unbekannten Schluessel in aufsteigender Reihenfolge (Textvergleich); das wird vor allen anderen Pruefungen entschieden.
Aus den Schluesseln entstehen Faehigkeiten:
- lesen, verben, ereignisse: je eine Liste nicht leerer Texte (sonst ValueError("rechte_ungueltig:<schluessel>")). Jeder Eintrag x wird zu "lesen:x", "verb:x" beziehungsweise "ereignis:x".
- zelle: "nein" (nichts) oder "text" (ergibt "zelle:text"); sonst ValueError("rechte_ungueltig:zelle").
- ablage: eine ganze Zahl (kein bool) groesser oder gleich 0 (sonst ValueError("rechte_ungueltig:ablage")); 0 ergibt nichts, n groesser 0 ergibt "ablage:<n>" (n als Dezimalzahl).
- dienst: "nein" (nichts), "host" (ergibt "dienst:host") oder "microvm" (ergibt "dienst:microvm"); sonst ValueError("rechte_ungueltig:dienst").
Das Ergebnis ist aufsteigend sortiert (Textvergleich) und ohne Doppelte. Fehlende Schluessel sind erlaubt und ergeben nichts.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze rechte_diff.py: stufe(faehigkeit) -> "A", "B" oder "C".
Die Faehigkeit wird am ersten ":" in art und rest geteilt. Ist faehigkeit kein Text, hat kein ":" oder ist rest leer, ist das Ergebnis "C". Sonst nach art:
- "lesen": "A".
- "verb": "B".
- "ereignis": "A", wenn rest eines von system.state, model.changed, desk.resync, tools.refresh, slot.changed ist (die oeffentlichen Ereignisse), sonst "B".
- "zelle": "B", wenn rest genau "text" ist, sonst "C".
- "ablage": ist rest nicht nur aus den Ziffern 0 bis 9 gebildet, "C"; sonst "A", wenn die Zahl hoechstens 1048576 ist, sonst "B".
- "dienst": "B", wenn rest genau "microvm" ist, sonst "C" (zum Beispiel "dienst:host").
- jede andere art: "C".
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze rechte_diff.py:
- rechte_diff(alt, neu) -> list[dict]: alt und neu sind je ein rechte-dict oder None. Fehler aus rechte_zu_faehigkeiten werden nicht abgefangen. Verglichen werden die Mengen ihrer Faehigkeiten. Das Ergebnis enthaelt zuerst fuer jede Faehigkeit, die nur in neu steht, {"faehigkeit": f, "richtung": "neu", "stufe": stufe(f)}, aufsteigend nach f sortiert, danach fuer jede, die nur in alt steht, {"faehigkeit": f, "richtung": "entfallen", "stufe": stufe(f)}, ebenfalls aufsteigend sortiert. Gleiche Faehigkeiten kommen nicht vor. Eine geaenderte Ablagegroesse ist deshalb eine entfallene und eine neue Faehigkeit.
- rechte_urteil(diff) -> dict mit genau den Schluesseln "braucht_gate" und "abgewiesen". diff ist eine Liste wie von rechte_diff; Eintraege, die kein dict sind, werden uebersprungen. Nur Eintraege mit richtung "neu" zaehlen. "braucht_gate" ist True, wenn mindestens ein zaehlender Eintrag die stufe "B" hat, sonst False. "abgewiesen" ist die Liste der faehigkeit-Werte der zaehlenden Eintraege mit stufe "C", in der Reihenfolge von diff. Ist diff keine Liste, gilt sie als leer.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze rechte_diff.py: rechte_schluessel(faehigkeiten) -> str, der Schluessel einer Entscheidung ueber genau diese Liste von Faehigkeiten.
faehigkeiten muss eine Liste von Texten sein, sonst ValueError("faehigkeiten_ungueltig"). Das Ergebnis ist der sha256 (Hex, klein geschrieben, 64 Zeichen) des UTF-8-Textes, der entsteht, wenn man die Eintraege ohne Doppelte aufsteigend sortiert (Textvergleich) und mit "\\n" (einem Zeilenumbruch) verbindet. Eine leere Liste ergibt den sha256 des leeren Textes. Reihenfolge und Doppelte der Eingabe aendern den Schluessel also nicht, jede andere Aenderung schon.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
def wirft(rechte, text):
    try:
        rechte_zu_faehigkeiten(rechte)
    except ValueError as e:
        return str(e) == text
    return False
assert rechte_zu_faehigkeiten(None) == []
assert rechte_zu_faehigkeiten({}) == []
assert rechte_zu_faehigkeiten({"lesen": ["rechnung"]}) == ["lesen:rechnung"]
assert rechte_zu_faehigkeiten({"verben": ["rechnung.ablegen"]}) == ["verb:rechnung.ablegen"]
assert rechte_zu_faehigkeiten({"ereignisse": ["system.state"]}) == ["ereignis:system.state"]
assert rechte_zu_faehigkeiten({"zelle": "text"}) == ["zelle:text"]
assert rechte_zu_faehigkeiten({"zelle": "nein"}) == []
assert rechte_zu_faehigkeiten({"ablage": 0}) == []
assert rechte_zu_faehigkeiten({"ablage": 2048}) == ["ablage:2048"]
assert rechte_zu_faehigkeiten({"dienst": "nein"}) == []
assert rechte_zu_faehigkeiten({"dienst": "host"}) == ["dienst:host"]
assert rechte_zu_faehigkeiten({"dienst": "microvm"}) == ["dienst:microvm"]
assert rechte_zu_faehigkeiten({"lesen": ["b", "a", "b"], "verben": ["x.y"], "zelle": "text", "ablage": 5}) == ["ablage:5", "lesen:a", "lesen:b", "verb:x.y", "zelle:text"]
assert rechte_zu_faehigkeiten({"lesen": []}) == []
assert wirft("text", "rechte_ungueltig")
assert wirft([1], "rechte_ungueltig")
assert wirft({"zebra": 1, "alpha": 2}, "rechte_unbekannt:alpha")
assert wirft({"unbekannt": 1, "lesen": "kaputt"}, "rechte_unbekannt:unbekannt")
assert wirft({"lesen": "rechnung"}, "rechte_ungueltig:lesen")
assert wirft({"verben": [""]}, "rechte_ungueltig:verben")
assert wirft({"ereignisse": [5]}, "rechte_ungueltig:ereignisse")
assert wirft({"zelle": "ja"}, "rechte_ungueltig:zelle")
assert wirft({"ablage": -1}, "rechte_ungueltig:ablage")
assert wirft({"ablage": True}, "rechte_ungueltig:ablage")
assert wirft({"ablage": "5"}, "rechte_ungueltig:ablage")
assert wirft({"dienst": "cloud"}, "rechte_ungueltig:dienst")
eingabe = {"lesen": ["a"]}
rechte_zu_faehigkeiten(eingabe)
assert eingabe == {"lesen": ["a"]}
''', "from rechte_diff import rechte_zu_faehigkeiten\n")

C2 = hidden('''
assert stufe("lesen:rechnung") == "A"
assert stufe("verb:rechnung.ablegen") == "B"
assert stufe("ereignis:system.state") == "A"
assert stufe("ereignis:model.changed") == "A"
assert stufe("ereignis:desk.resync") == "A"
assert stufe("ereignis:tools.refresh") == "A"
assert stufe("ereignis:slot.changed") == "A"
assert stufe("ereignis:decision.pending") == "B"
assert stufe("ereignis:system.state2") == "B"
assert stufe("zelle:text") == "B"
assert stufe("zelle:bild") == "C"
assert stufe("ablage:1") == "A"
assert stufe("ablage:1048576") == "A"
assert stufe("ablage:1048577") == "B"
assert stufe("ablage:abc") == "C"
assert stufe("ablage:-5") == "C"
assert stufe("ablage:10x") == "C"
assert stufe("dienst:microvm") == "B"
assert stufe("dienst:host") == "C"
assert stufe("route:GET /api/x") == "C"
assert stufe("lesen:") == "C"
assert stufe("lesen") == "C"
assert stufe("") == "C"
assert stufe(None) == "C"
assert stufe(5) == "C"
assert stufe(":x") == "C"
assert stufe("verb:a:b") == "B"
assert stufe("Lesen:x") == "C"
''', "from rechte_diff import stufe\n")

C3 = hidden('''
assert rechte_diff(None, None) == []
assert rechte_diff({"lesen": ["a"]}, {"lesen": ["a"]}) == []
assert rechte_diff(None, {"lesen": ["a"]}) == [{"faehigkeit": "lesen:a", "richtung": "neu", "stufe": "A"}]
assert rechte_diff({"lesen": ["a"]}, None) == [{"faehigkeit": "lesen:a", "richtung": "entfallen", "stufe": "A"}]
d = rechte_diff({"lesen": ["a", "b"], "verben": ["x.y"]}, {"lesen": ["b", "c"], "zelle": "text", "dienst": "host"})
assert [(x["faehigkeit"], x["richtung"], x["stufe"]) for x in d] == [("dienst:host", "neu", "C"), ("lesen:c", "neu", "A"), ("zelle:text", "neu", "B"), ("lesen:a", "entfallen", "A"), ("verb:x.y", "entfallen", "B")]
assert all(set(x) == {"faehigkeit", "richtung", "stufe"} for x in d)
g = rechte_diff({"ablage": 1000}, {"ablage": 2000000})
assert [(x["faehigkeit"], x["richtung"], x["stufe"]) for x in g] == [("ablage:2000000", "neu", "B"), ("ablage:1000", "entfallen", "A")]
try:
    rechte_diff({"zebra": 1}, None)
except ValueError as e:
    assert str(e) == "rechte_unbekannt:zebra"
else:
    raise AssertionError("kein ValueError")
try:
    rechte_diff(None, {"lesen": "x"})
except ValueError as e:
    assert str(e) == "rechte_ungueltig:lesen"
else:
    raise AssertionError("kein ValueError")
u = rechte_urteil(d)
assert set(u) == {"braucht_gate", "abgewiesen"}
assert u["braucht_gate"] is True
assert u["abgewiesen"] == ["dienst:host"]
assert rechte_urteil([]) == {"braucht_gate": False, "abgewiesen": []}
assert rechte_urteil(None) == {"braucht_gate": False, "abgewiesen": []}
assert rechte_urteil("x") == {"braucht_gate": False, "abgewiesen": []}
assert rechte_urteil([None, 5, "x"]) == {"braucht_gate": False, "abgewiesen": []}
nur_alt = rechte_diff({"verben": ["x.y"], "dienst": "host"}, None)
assert rechte_urteil(nur_alt) == {"braucht_gate": False, "abgewiesen": []}
nur_a = rechte_diff(None, {"lesen": ["a"], "ereignisse": ["system.state"]})
assert rechte_urteil(nur_a) == {"braucht_gate": False, "abgewiesen": []}
zwei_c = [{"richtung": "neu", "stufe": "C", "faehigkeit": "q:2"}, {"richtung": "neu", "stufe": "C", "faehigkeit": "q:1"}]
assert rechte_urteil(zwei_c) == {"braucht_gate": False, "abgewiesen": ["q:2", "q:1"]}
''', "from rechte_diff import rechte_diff, rechte_urteil\n")

C4 = hidden('''
import hashlib
def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
assert rechte_schluessel([]) == h("")
assert rechte_schluessel(["lesen:a"]) == h("lesen:a")
assert rechte_schluessel(["b", "a"]) == h("a\\nb")
assert rechte_schluessel(["a", "b"]) == h("a\\nb")
assert rechte_schluessel(["a", "a", "b"]) == h("a\\nb")
assert rechte_schluessel(["a", "b"]) != rechte_schluessel(["a", "c"])
assert rechte_schluessel(["a"]) != rechte_schluessel(["a", "b"])
assert len(rechte_schluessel(["x"])) == 64
assert rechte_schluessel(["\\u00e4"]) == h("\\u00e4")
liste = ["b", "a", "b"]
rechte_schluessel(liste)
assert liste == ["b", "a", "b"]
for falsch in (None, "a", ("a",), [1], ["a", None], {"a"}):
    try:
        rechte_schluessel(falsch)
    except ValueError as e:
        assert str(e) == "faehigkeiten_ungueltig"
    else:
        raise AssertionError("kein ValueError")
''', "from rechte_diff import rechte_schluessel\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_rechte_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_rechte_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_rechte_s3.py": C3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_rechte_s4.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_rechte_s1.py": C1}
