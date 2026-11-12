"""Bau-Spec betrieb_uebersichten: der rechnende Kern zweier Fach-Apps der KMU-Shell (AM7-10, Kandidaten Schutzklassen-Uebersicht und Verzeichnis der eingesetzten KI): Vorgaenge nach Schutzklasse und Zustand zaehlen, Anbieter-Verzeichnis ohne Zugangsdaten.
Vier Stufen S1 bis S4, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul betrieb_uebersichten.py (Zielort spaeter desk/betrieb_uebersichten.py): reine Funktionen auf den Daten, die desk/betrieb.py schon liefert (_vorgaenge, _empfaenger).
Die Fach-Apps selbst (Manifest, Oberflaeche, Route, Eintrag in uix/shells/gateway-kmu/apps/) macht Claude spaeter von Hand und erst, wenn der Captain die Kandidaten aus AM7-10 festgelegt hat; der Bau legt nichts davon fest.
S1 Schutzklassen-Uebersicht | S2 Adresse ohne Zugangsdaten | S3 Verzeichnis der Anbieter | S4 Text fuer die Beschaeftigten.
Referenz: benchmarks/devvm_refs/betrieb_uebersichten/betrieb_uebersichten.py."""

NOTES = '''# Notizen betrieb_uebersichten
Nur Python-Standardbibliothek (urllib.parse ist erlaubt). Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: betrieb_uebersichten.py. Keine Datei wird gelesen.
Alle Funktionen veraendern ihre Eingaben nie und werfen nie eine Ausnahme. Texte stehen unten genau so, wie sie erscheinen sollen; jedes Zeichen zaehlt.
Ein "Name" in den Regeln unten ist: ein str, der nach strip() nicht leer ist; sein Wert ist der Text mit strip() bereinigt.
'''

TASK_S1 = '''Lege betrieb_uebersichten.py an mit schutzklassen_uebersicht(vorgaenge) -> dict. vorgaenge ist die Liste der Vorgaenge aus dem Betriebsexport; jeder Vorgang ein dict mit den Schluesseln id, zustand, klasse (die Schutzklasse), weg, zweck, verantwortlich; ein Eintrag mit dem Schluessel "fehler" ist eine Fehlermeldung des Exports.
Das Ergebnis hat genau die Schluessel:
- "summe": Anzahl der gezaehlten Vorgaenge
- "uebersprungen": Anzahl der Eintraege, die nicht gezaehlt wurden: Eintraege, die kein dict sind, und dicts, die den Schluessel "fehler" enthalten (egal mit welchem Wert)
- "nach_klasse": dict Schutzklasse -> Anzahl; die Schutzklasse ist der Name aus vorgang["klasse"], sonst (fehlt, None, kein str oder leer) der Text "unbekannt"
- "nach_zustand": dict Zustand -> Anzahl, ebenso mit vorgang["zustand"]
- "ohne_verantwortlichen": Liste der Kennungen aller gezaehlten Vorgaenge, bei denen verantwortlich kein Name ist (fehlt, None, kein str oder nur Leerraum); die Kennung ist der Name aus vorgang["id"], sonst der Text "?". Reihenfolge wie in der Eingabe.
Ist vorgaenge keine Liste, ist das Ergebnis {"summe": 0, "uebersprungen": 0, "nach_klasse": {}, "nach_zustand": {}, "ohne_verantwortlichen": []}.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze betrieb_uebersichten.py. Es kommt from urllib.parse import urlsplit dazu.
adresse_kuerzen(adresse) -> str: die Adresse eines Anbieters ohne Zugangsdaten. urlsplit(adresse.strip()) liefert Schema, hostname und port; ist adresse kein str, ist das Schema (in Kleinbuchstaben) nicht "http" oder "https", fehlt der hostname, oder wirft urlsplit oder der Zugriff auf port einen ValueError (zum Beispiel Port 99999 oder "abc"), ist das Ergebnis "". Sonst ist es Schema + "://" + hostname + (":" + str(port), falls ein Port angegeben ist). Enthaelt der hostname einen Doppelpunkt (IPv6), steht er in eckigen Klammern. Benutzername, Passwort, Pfad, Query und Fragment kommen nie vor; Schema und hostname stehen in Kleinbuchstaben.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_V = '''Ergaenze betrieb_uebersichten.py: ki_verzeichnis(anbieter) -> list[dict]. anbieter ist die Liste der Cloud-Anbieter, jeder ein dict mit den Schluesseln anbieter (Name), an (bool) und adresse (str, kann Zugangsdaten enthalten). Ist anbieter keine Liste: [].
Jeder Eintrag, der ein dict mit einem Namen in "anbieter" ist, ergibt eine Zeile {"anbieter": Name, "status": "an" oder "aus", "adresse": adresse_kuerzen(Wert von "adresse")}. Status ist "an" nur, wenn der Wert von "an" genau True ist, sonst "aus". Kommt ein Name mehrfach vor, gilt nur der erste Eintrag. Eintraege, die kein dict sind oder keinen Namen haben, werden uebersprungen. Die Zeilen sind sortiert nach (Name in Kleinbuchstaben, Name), also ohne Beachtung der Gross-/Kleinschreibung, bei Gleichstand der Name selbst.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze betrieb_uebersichten.py: ki_text(zeilen) -> str, der Text der Fach-App fuer Beschaeftigte aus dem Ergebnis von ki_verzeichnis.
Beruecksichtigt werden nur Zeilen, die dicts sind und in "anbieter" einen nicht leeren str haben (die Zeilen der Liste in ihrer Reihenfolge); ist zeilen keine Liste oder bleibt keine Zeile uebrig, ist das Ergebnis genau "Keine Cloud-KI eingetragen. Nur lokale Modelle.".
Sonst: die Zeile "Eingesetzte Cloud-KI:", danach je Anbieter eine Zeile "- " + anbieter + ": " + status, wobei status "an" ist, wenn zeile.get("status") genau "an" ist, sonst "aus"; hat die Zeile einen nicht leeren str in "adresse", folgt ", " und die Adresse. Die Zeilen sind durch "\\n" getrennt, am Ende steht kein Zeilenumbruch.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
LEER = {"summe": 0, "uebersprungen": 0, "nach_klasse": {}, "nach_zustand": {}, "ohne_verantwortlichen": []}
def v(**kw):
    d = {"id": "V-1", "zustand": "entwurf", "klasse": "N", "weg": "lokal", "zweck": "z", "verantwortlich": "Frau A"}
    d.update(kw)
    return d

assert schutzklassen_uebersicht([]) == LEER
assert schutzklassen_uebersicht(None) == LEER
assert schutzklassen_uebersicht("V-1") == LEER
assert schutzklassen_uebersicht([v()]) == {"summe": 1, "uebersprungen": 0, "nach_klasse": {"N": 1}, "nach_zustand": {"entwurf": 1}, "ohne_verantwortlichen": []}
r = schutzklassen_uebersicht([v(), v(id="V-2", klasse="A01"), v(id="V-3", klasse="N", zustand="freigegeben")])
assert r["nach_klasse"] == {"N": 2, "A01": 1}
assert r["nach_zustand"] == {"entwurf": 2, "freigegeben": 1}
assert r["summe"] == 3
assert schutzklassen_uebersicht([v(klasse=None), v(klasse=""), v(klasse="  "), v(klasse=5), v(klasse=["N"])])["nach_klasse"] == {"unbekannt": 5}
d = v()
del d["klasse"]
del d["zustand"]
assert schutzklassen_uebersicht([d])["nach_klasse"] == {"unbekannt": 1}
assert schutzklassen_uebersicht([d])["nach_zustand"] == {"unbekannt": 1}
assert schutzklassen_uebersicht([v(klasse=" A01 ")])["nach_klasse"] == {"A01": 1}
assert schutzklassen_uebersicht([v(id="V-1", verantwortlich=None), v(id="V-2", verantwortlich=""), v(id="V-3", verantwortlich="   "), v(id="V-4", verantwortlich=5), v(id="V-5")])["ohne_verantwortlichen"] == ["V-1", "V-2", "V-3", "V-4"]
assert schutzklassen_uebersicht([v(id=" V-9 ", verantwortlich=None), v(id=None, verantwortlich=None), v(id=7, verantwortlich=None)])["ohne_verantwortlichen"] == ["V-9", "?", "?"]
assert schutzklassen_uebersicht([v(id="V-3", verantwortlich=None), v(id="V-1", verantwortlich=None)])["ohne_verantwortlichen"] == ["V-3", "V-1"]
r = schutzklassen_uebersicht([{"fehler": "TypeError: x"}, v(), {"fehler": None}])
assert (r["summe"], r["uebersprungen"]) == (1, 2)
r = schutzklassen_uebersicht(["text", None, 5, ["x"], v()])
assert (r["summe"], r["uebersprungen"]) == (1, 4)
assert schutzklassen_uebersicht([{"fehler": "x"}]) == {"summe": 0, "uebersprungen": 1, "nach_klasse": {}, "nach_zustand": {}, "ohne_verantwortlichen": []}
eingabe = [v(klasse=" A "), v(verantwortlich=None)]
schutzklassen_uebersicht(eingabe)
assert eingabe == [v(klasse=" A "), v(verantwortlich=None)]
''', "from betrieb_uebersichten import schutzklassen_uebersicht\n")

C2 = hidden('''
assert adresse_kuerzen("https://api.langdock.com/openai/eu/v1") == "https://api.langdock.com"
assert adresse_kuerzen("https://user:geheim@Api.Example.com:8443/v1?key=abc#f") == "https://api.example.com:8443"
assert "geheim" not in adresse_kuerzen("https://user:geheim@api.example.com/")
assert "abc" not in adresse_kuerzen("https://api.example.com/v1?key=abc")
assert adresse_kuerzen("https://token@api.example.com/") == "https://api.example.com"
assert adresse_kuerzen("http://localhost:11434/v1") == "http://localhost:11434"
assert adresse_kuerzen("ftp://h.example/x") == ""
assert adresse_kuerzen("api.example.com/v1") == ""
assert adresse_kuerzen("//api.example.com/v1") == ""
assert adresse_kuerzen("https:///nur-pfad") == ""
assert adresse_kuerzen(None) == ""
assert adresse_kuerzen(5) == ""
assert adresse_kuerzen("") == ""
assert adresse_kuerzen("https://h.example:99999/") == ""
assert adresse_kuerzen("https://h.example:abc/") == ""
assert adresse_kuerzen("http://[::1]:8080/x") == "http://[::1]:8080"
assert adresse_kuerzen("HTTPS://X.Com/a") == "https://x.com"
assert adresse_kuerzen("  https://x.com/a  ") == "https://x.com"
assert adresse_kuerzen("https://x.com") == "https://x.com"
''', "from betrieb_uebersichten import adresse_kuerzen\n")

CV = hidden('''
def a(name, an=True, adresse="https://api.example.com/v1"):
    return {"anbieter": name, "an": an, "adresse": adresse}

assert ki_verzeichnis([a("Langdock", True, "https://api.langdock.com/openai/eu/v1")]) == [{"anbieter": "Langdock", "status": "an", "adresse": "https://api.langdock.com"}]
assert ki_verzeichnis([a("X", False)])[0]["status"] == "aus"
assert [ki_verzeichnis([a("X", w)])[0]["status"] for w in ("yes", 1, None, "True")] == ["aus", "aus", "aus", "aus"]
assert [z["anbieter"] for z in ki_verzeichnis([a("gamma"), a("Beta"), a("alpha")])] == ["alpha", "Beta", "gamma"]
assert [z["anbieter"] for z in ki_verzeichnis([a("ab"), a("AB")])] == ["AB", "ab"]
assert ki_verzeichnis([a("X", True, "https://a.example/"), a("X", False, "https://b.example/")]) == [{"anbieter": "X", "status": "an", "adresse": "https://a.example"}]
assert [z["anbieter"] for z in ki_verzeichnis([a("  X  "), a(""), a("   "), a(None), a(5), "x", None, 7, a("Y")])] == ["X", "Y"]
assert "geheim" not in repr(ki_verzeichnis([a("X", True, "https://user:geheim@api.example.com/")]))
assert ki_verzeichnis([a("X", True, 5)])[0]["adresse"] == ""
assert ki_verzeichnis([{"anbieter": "X"}]) == [{"anbieter": "X", "status": "aus", "adresse": ""}]
assert ki_verzeichnis(None) == []
assert ki_verzeichnis("x") == []
assert ki_verzeichnis([]) == []
eingabe = [a("b", True, "https://u:p@h.example/"), a("a")]
ki_verzeichnis(eingabe)
assert eingabe == [a("b", True, "https://u:p@h.example/"), a("a")]
''', "from betrieb_uebersichten import ki_verzeichnis\n")

C3 = hidden('''
KEINE = "Keine Cloud-KI eingetragen. Nur lokale Modelle."
assert ki_text([]) == KEINE
assert ki_text(None) == KEINE
assert ki_text("Langdock") == KEINE
assert ki_text([{"anbieter": "Langdock", "status": "an", "adresse": "https://api.langdock.com"}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- Langdock: an, https://api.langdock.com"
assert ki_text([{"anbieter": "X", "status": "aus", "adresse": ""}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- X: aus"
assert ki_text([{"anbieter": "X", "status": "aus"}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- X: aus"
assert ki_text([{"anbieter": "B", "status": "an", "adresse": "https://b.example"}, {"anbieter": "A", "status": "aus", "adresse": ""}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- B: an, https://b.example" + chr(10) + "- A: aus"
assert ki_text([None, {}, {"anbieter": ""}, {"anbieter": 5}, "x", {"anbieter": "X", "status": "an"}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- X: an"
assert ki_text([None, {}, {"anbieter": ""}, {"anbieter": 5}, "x"]) == KEINE
assert ki_text([{"anbieter": "X", "status": "AN"}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- X: aus"
assert ki_text([{"anbieter": "X", "status": True}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- X: aus"
assert ki_text([{"anbieter": "X", "status": "an", "adresse": 5}]) == "Eingesetzte Cloud-KI:" + chr(10) + "- X: an"
assert not ki_text([{"anbieter": "X", "status": "an"}]).endswith(chr(10))
assert ki_text(ki_verzeichnis([{"anbieter": "Langdock", "an": True, "adresse": "https://u:p@api.langdock.com/x"}])) == "Eingesetzte Cloud-KI:" + chr(10) + "- Langdock: an, https://api.langdock.com"
assert ki_text(ki_verzeichnis([])) == KEINE
''', "from betrieb_uebersichten import ki_verzeichnis, ki_text\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_betrieb_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_betrieb_s2.py": C2}},
    {"name": "S3", "task": TASK_V, "no_own_check": True, "hidden": {"hidden_betrieb_s3.py": CV}},
    {"name": "S4", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_betrieb_s4.py": C3}},
]
TASK = TASK_S1
HIDDEN = {"hidden_betrieb_s1.py": C1}
