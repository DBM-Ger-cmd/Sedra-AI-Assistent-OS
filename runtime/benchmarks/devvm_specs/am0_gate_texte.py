"""Bau-Spec am0_gate_texte: die Risiko-Texte im Einbau-Gate fuer Werkzeuge und Vorgabe-Shells (AM0-07, Stufe A0, G3 Schritt S7, Kern ohne Anbindung).
Drei Stufen S1 bis S3, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul gate_texte.py; die Anbindung an uix_server.py (install_request) macht Claude spaeter von Hand.
S1 Leserouten-Text | S2 Risiken eines Werkzeugs | S3 Risiken einer Shell und Auswahl nach Art.
Referenz: benchmarks/devvm_refs/am0_gate_texte/gate_texte.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am0_gate_texte start "<Auftrag>"."""

NOTES = '''# Notizen gate_texte
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: gate_texte.py. Die Datei wird als UTF-8 geschrieben und darf Umlaute und den Gedankenstrich (Zeichen U+2013) enthalten.
Die Texte stehen unten genau so, wie sie im Gate erscheinen sollen; jedes Zeichen zaehlt. Alle Funktionen werfen nie eine Ausnahme (ausser dort, wo es ausdruecklich steht).
'''

TASK_S1 = '''Lege gate_texte.py an mit leserouten_text(routen) -> str.
routen ist eine Liste von Routen-Texten wie "GET /api/gateway/*" oder "POST /api/objects". Nur Eintraege, die ein Text sind und mit "GET " (GET, Leerzeichen) beginnen und danach mindestens ein Zeichen haben, zaehlen. Von jedem zaehlenden Eintrag gilt der Teil nach "GET " (der Pfad).
Ergebnis: "Leserouten: " gefolgt von den Pfaden, getrennt durch ", " (Komma, Leerzeichen), in der Reihenfolge der Liste, jeder Pfad nur einmal (bei Dopplung zaehlt die erste). Gibt es keinen Pfad (leere Liste, kein GET, routen ist keine Liste), ist das Ergebnis genau "Leserouten: keine".
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze gate_texte.py: risiken_werkzeug(routen, funde=None) -> list[str].
Das Ergebnis ist eine neue Liste aus genau diesen Texten in dieser Reihenfolge:
1. "läuft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite"
2. "nicht begrenzt: Rechenzeit und Speicher im Browser"
3. leserouten_text(routen)
4. danach alle Eintraege von funde, die nicht leere Texte sind, in ihrer Reihenfolge und unveraendert.
Ist funde keine Liste (zum Beispiel None), gibt es keine Funde. Die Eingaben werden nicht veraendert. Die Konstanten fuer Text 1 und 2 duerfen als Modulvariablen RAHMEN und GRENZE vorliegen.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze gate_texte.py:
- risiken_shell(funde=None) -> list[str]: eine neue Liste aus "ohne eigenen Code und ohne eigenes CSS – die Oberfläche baut der Rahmen des Vertrags (ui/frame.js)" (der Strich ist ein Gedankenstrich, U+2013, mit je einem Leerzeichen davor und danach), dann "Routen: nur die festen Routen des Rahmens", danach die Funde wie bei risiken_werkzeug (nicht leere Texte von funde, in ihrer Reihenfolge).
- risiken(art, routen=None, funde=None) -> list[str]: ist art genau "tool", das Ergebnis von risiken_werkzeug(routen, funde); ist art genau "shell", das von risiken_shell(funde) (routen wird dann nicht benutzt); jede andere art wirft ValueError("art").
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert leserouten_text(["GET /api/gateway/*"]) == "Leserouten: /api/gateway/*"
assert leserouten_text(["GET /api/a", "GET /api/b"]) == "Leserouten: /api/a, /api/b"
assert leserouten_text(["GET /api/a", "POST /api/x", "GET /api/b"]) == "Leserouten: /api/a, /api/b"
assert leserouten_text(["GET /api/a", "GET /api/a"]) == "Leserouten: /api/a"
assert leserouten_text(["GET /api/b", "GET /api/a", "GET /api/b"]) == "Leserouten: /api/b, /api/a"
assert leserouten_text([]) == "Leserouten: keine"
assert leserouten_text(["POST /api/objects"]) == "Leserouten: keine"
assert leserouten_text(["GET "]) == "Leserouten: keine"
assert leserouten_text(["GET"]) == "Leserouten: keine"
assert leserouten_text(["get /api/a"]) == "Leserouten: keine"
assert leserouten_text([" GET /api/a"]) == "Leserouten: keine"
assert leserouten_text([5, None, "GET /api/a"]) == "Leserouten: /api/a"
assert leserouten_text(None) == "Leserouten: keine"
assert leserouten_text("GET /api/a") == "Leserouten: keine"
assert leserouten_text(("GET /api/a",)) == "Leserouten: keine"
''', "from gate_texte import leserouten_text\n")

C2 = hidden('''
A = "l\\u00e4uft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite"
B = "nicht begrenzt: Rechenzeit und Speicher im Browser"
assert risiken_werkzeug(["GET /api/a"]) == [A, B, "Leserouten: /api/a"]
assert risiken_werkzeug([]) == [A, B, "Leserouten: keine"]
assert risiken_werkzeug(None) == [A, B, "Leserouten: keine"]
assert risiken_werkzeug(["GET /api/a"], ["Fund 1", "Fund 2"]) == [A, B, "Leserouten: /api/a", "Fund 1", "Fund 2"]
assert risiken_werkzeug([], ["", None, 5, "Fund"]) == [A, B, "Leserouten: keine", "Fund"]
assert risiken_werkzeug([], None) == [A, B, "Leserouten: keine"]
assert risiken_werkzeug([], "Fund") == [A, B, "Leserouten: keine"]
assert risiken_werkzeug([], ()) == [A, B, "Leserouten: keine"]
assert len(risiken_werkzeug(["GET /x y"])) == 3
r = ["GET /api/a"]
f = ["x"]
r2 = risiken_werkzeug(r, f)
assert r == ["GET /api/a"]
assert f == ["x"]
r2.append("zusatz")
assert risiken_werkzeug(r, f) == [A, B, "Leserouten: /api/a", "x"]
''', "from gate_texte import risiken_werkzeug\n")

C3 = hidden('''
A = "l\\u00e4uft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite"
B = "nicht begrenzt: Rechenzeit und Speicher im Browser"
S1 = "ohne eigenen Code und ohne eigenes CSS \\u2013 die Oberfl\\u00e4che baut der Rahmen des Vertrags (ui/frame.js)"
S2 = "Routen: nur die festen Routen des Rahmens"
assert risiken_shell() == [S1, S2]
assert risiken_shell(None) == [S1, S2]
assert risiken_shell(["Fund"]) == [S1, S2, "Fund"]
assert risiken_shell(["", "a", 3]) == [S1, S2, "a"]
assert risiken_shell("x") == [S1, S2]
assert risiken("shell") == [S1, S2]
assert risiken("shell", ["GET /api/a"], ["F"]) == [S1, S2, "F"]
assert risiken("tool", ["GET /api/a"]) == [A, B, "Leserouten: /api/a"]
assert risiken("tool") == [A, B, "Leserouten: keine"]
assert risiken("tool", ["GET /api/a"], ["F"]) == [A, B, "Leserouten: /api/a", "F"]
for falsch in ("instrument", "", "Tool", None, 5):
    try:
        risiken(falsch)
    except ValueError as e:
        assert str(e) == "art"
    else:
        raise AssertionError("kein ValueError")
''', "from gate_texte import risiken_shell, risiken\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_gate_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_gate_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_gate_s3.py": C3}},
]
TASK = TASK_S1
HIDDEN = {"hidden_gate_s1.py": C1}
