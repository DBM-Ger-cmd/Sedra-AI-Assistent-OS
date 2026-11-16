"""Bau-Spec vorschlag_filter: bessere Vorschlaege beim Tippen (SPEC_LERNEN_UND_HILFSWERKZEUGE_v1, VS-02 "Korrektur schlaegt Lob" und VS-06 "Nicht mehr vorschlagen" samt VP-01 aus/einblenden).
Vier Stufen S1 bis S4, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul vorschlag_filter.py (Zielort spaeter harness/vorschlag_filter.py): reine Funktionen, keine Datei, kein Server.
Die Anbindung an harness/belohnung.py (vorschlaege), die Datei runtime_data/harness/belohnungen/_ausgeblendet.jsonl, die Route entfernen und das Werkzeug vorschlaege_pflegen macht Claude spaeter von Hand.
S1 Schluessel einer Frage | S2 korrigierte Lobe | S3 Zeilen der Ausblend-Datei | S4 Vorschlaege filtern.
Referenz: benchmarks/devvm_refs/vorschlag_filter/vorschlag_filter.py."""

NOTES = '''# Notizen vorschlag_filter
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: vorschlag_filter.py. Die Datei wird als UTF-8 geschrieben und darf Umlaute enthalten.
Alle Funktionen veraendern ihre Eingaben nie und werfen nie eine Ausnahme, ausser dort, wo es ausdruecklich steht.
Die Fuellwoerter (Modulvariable FUELLWOERTER, eine Menge): der, die, das, den, dem, des, ein, eine, einen, und, oder, mit, für, fuer, bitte, mal, mach, ist, sind, wie, was, wo, wir, ich, du, zu, in, im, auf, von, bei, nach, noch, auch, jetzt, dann, nicht, kann, kannst, soll, sollst, mir, uns.
'''

TASK_S1 = '''Lege vorschlag_filter.py an mit der Modulvariable FUELLWOERTER (Menge, siehe Notizen) und frage_schluessel(frage) -> str.
frage_schluessel: ist frage kein str, ist das Ergebnis "". Sonst: frage in Kleinbuchstaben (str.lower()), darin alle Wortstuecke mit dem regulaeren Ausdruck [0-9a-zäöüß]+ (re.findall; nur diese Zeichen, also keine Grossbuchstaben nach dem Kleinschreiben, keine Satzzeichen, keine anderen Ziffern als 0-9); behalten werden nur Woerter mit mindestens 3 Zeichen, die nicht in FUELLWOERTER stehen. Das Ergebnis ist diese Woerter in ihrer Reihenfolge, durch ein Leerzeichen getrennt (Doppelte bleiben); gibt es keine, ist es "".
Der Schluessel sagt: zwei Fragen mit denselben bedeutungstragenden Woertern in derselben Reihenfolge sind dieselbe Frage.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze vorschlag_filter.py: korrigierte_lobe(saetze) -> set. saetze ist die Liste der gespeicherten Urteile, aelteste zuerst; jedes Element ein dict mit den Schluesseln "frage" (str) und "urteil" ("lob" oder "korrektur").
Gesucht ist die Menge der Schluessel (frage_schluessel der Frage), die gesperrt werden sollen: Ein Schluessel ist gesperrt, wenn mindestens ein "lob" mit diesem Schluessel in der Liste steht und das LETZTE Element mit diesem Schluessel (in Listenreihenfolge) ein "korrektur" ist. Wird eine Frage nach der Korrektur wieder gelobt, ist sie nicht gesperrt; eine Frage, die nur korrigiert und nie gelobt wurde, ist ebenfalls nicht gesperrt (sie ist keine Warnung vor einem Lob).
Uebersprungen werden: Elemente, die kein dict sind, Elemente mit einem anderen "urteil", und Elemente, deren Schluessel "" ist. Ist saetze keine Liste, ist das Ergebnis die leere Menge.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze vorschlag_filter.py. Es kommt import json dazu. Die Ausblend-Datei ist eine Textdatei mit einer JSON-Zeile je Eintrag: {"frage": <text>, "aus": <true|false>}.
- ausblenden_zeile(frage, aus=True) -> str: die Zeile fuer die Datei: json.dumps({"frage": frage, "aus": bool(aus)}, ensure_ascii=False) gefolgt von einem Zeilenumbruch "\\n". Ist frage_schluessel(frage) leer (auch bei Nicht-Text), wirft die Funktion ValueError("frage").
- ausgeblendet_lesen(text) -> set: liest den Inhalt der Datei Zeile fuer Zeile (str.splitlines()) und liefert die Menge der Schluessel (frage_schluessel), die gerade ausgeblendet sind. Die Zeilen werden der Reihe nach angewendet: "aus" true fuegt den Schluessel hinzu, "aus" false nimmt ihn weg; eine spaetere Zeile gewinnt. Ungueltige Zeilen werden uebersprungen, ohne Fehler: kein JSON (auch eine leere Zeile), kein Objekt (zum Beispiel eine Zahl oder eine Liste), "aus" fehlt oder ist kein bool, "frage" fehlt oder ergibt den Schluessel "". Ist text kein str, ist das Ergebnis die leere Menge.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze vorschlag_filter.py: vorschlaege_filtern(vorschlaege, korrigiert, ausgeblendet) -> list. vorschlaege ist eine Liste von dicts mit dem Schluessel "frage" (die Vorschlaege fuer die Eingabe, jedes mit weiteren Schluesseln wie "stufe"), korrigiert und ausgeblendet sind Mengen (oder Listen) von Schluesseln wie in S2 und S3; beide duerfen None sein (dann leer).
Ergebnis ist eine neue Liste mit den Vorschlaegen, deren frage_schluessel weder in korrigiert noch in ausgeblendet steht, in der urspruenglichen Reihenfolge; die dicts selbst kommen unveraendert (dasselbe Objekt) in die Liste. Weggelassen werden ausserdem Elemente, die kein dict sind, und Vorschlaege, deren Schluessel "" ist. Ist vorschlaege keine Liste, ist das Ergebnis [].
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert frage_schluessel("Mach bitte die Tests") == "tests"
assert frage_schluessel("Tests laufen lassen") == "tests laufen lassen"
assert frage_schluessel("TESTS laufen lassen") == frage_schluessel("tests laufen lassen")
assert frage_schluessel("Wie lauten die Regeln? Und die Regeln!") == "lauten regeln regeln"
assert frage_schluessel("Tests, laufen; lassen.") == "tests laufen lassen"
assert frage_schluessel("Prüfe die Größe der Datei") == "prüfe größe datei"
assert frage_schluessel("ÄÖÜ Straße") == "äöü straße"
assert frage_schluessel("ab cd ef") == ""
assert frage_schluessel("abc") == "abc"
assert frage_schluessel("für fuer bitte mal") == ""
assert frage_schluessel("Version 2 von 3 und 10") == "version"
assert frage_schluessel("Plan 2026 starten") == "plan 2026 starten"
assert frage_schluessel("Plan \\u0662\\u0660\\u0662\\u0666 starten") == "plan starten"
assert frage_schluessel("") == ""
assert frage_schluessel(None) == ""
assert frage_schluessel(5) == ""
assert frage_schluessel(["tests"]) == ""
assert frage_schluessel("   ") == ""
assert len(FUELLWOERTER) == 43
assert {"fuer", "für", "uns", "mir"} <= FUELLWOERTER
''', "from vorschlag_filter import frage_schluessel, FUELLWOERTER\n")

C2 = hidden('''
def s(frage, urteil):
    return {"frage": frage, "urteil": urteil}

assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur")]) == {"tests laufen lassen"}
assert korrigierte_lobe([s("Tests laufen lassen", "korrektur"), s("Tests laufen lassen", "lob")]) == set()
assert korrigierte_lobe([s("Tests laufen lassen", "korrektur")]) == set()
assert korrigierte_lobe([s("Tests laufen lassen", "lob")]) == set()
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Mach bitte TESTS laufen, lassen!", "korrektur")]) == {"tests laufen lassen"}
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur"), s("Tests laufen lassen", "lob")]) == set()
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur"), s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur")]) == {"tests laufen lassen"}
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Doku schreiben", "lob"), s("Doku schreiben", "korrektur")]) == {"doku schreiben"}
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Tests anders laufen", "korrektur")]) == set()
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur"), s("Tests laufen lassen", "frage"), s("Tests laufen lassen", None)]) == {"tests laufen lassen"}
assert korrigierte_lobe([s("Tests laufen lassen", "lob"), "text", None, 5, s("Tests laufen lassen", "korrektur")]) == {"tests laufen lassen"}
assert korrigierte_lobe([s("", "lob"), s("", "korrektur"), s("ab cd", "lob"), s("ab cd", "korrektur")]) == set()
assert korrigierte_lobe([{"urteil": "lob"}, {"urteil": "korrektur"}, s(None, "lob"), s(None, "korrektur")]) == set()
assert korrigierte_lobe([]) == set()
assert korrigierte_lobe(None) == set()
assert korrigierte_lobe("lob") == set()
assert isinstance(korrigierte_lobe([]), set)
liste = [s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur")]
korrigierte_lobe(liste)
assert liste == [s("Tests laufen lassen", "lob"), s("Tests laufen lassen", "korrektur")]
''', "from vorschlag_filter import korrigierte_lobe\n")

C3 = hidden('''
import json
assert ausblenden_zeile("Tests laufen lassen") == '{"frage": "Tests laufen lassen", "aus": true}' + chr(10)
assert ausblenden_zeile("Tests laufen lassen", False) == '{"frage": "Tests laufen lassen", "aus": false}' + chr(10)
assert ausblenden_zeile("Pr\\u00fcfe Gr\\u00f6\\u00dfe") == '{"frage": "Pr\\u00fcfe Gr\\u00f6\\u00dfe", "aus": true}' + chr(10)
assert json.loads(ausblenden_zeile('Sag "hallo" Welt')) == {"frage": 'Sag "hallo" Welt', "aus": True}
for bad in ("", "ab cd", None, 5, "bitte mal"):
    try:
        ausblenden_zeile(bad)
    except ValueError as e:
        assert str(e) == "frage"
    else:
        raise AssertionError("kein ValueError")
z = ausblenden_zeile("Tests laufen lassen") + ausblenden_zeile("Doku schreiben")
assert ausgeblendet_lesen(z) == {"tests laufen lassen", "doku schreiben"}
assert ausgeblendet_lesen(z + ausblenden_zeile("Tests laufen lassen", False)) == {"doku schreiben"}
assert ausgeblendet_lesen(ausblenden_zeile("Tests laufen lassen", False) + ausblenden_zeile("Tests laufen lassen")) == {"tests laufen lassen"}
assert ausgeblendet_lesen(ausblenden_zeile("Tests laufen lassen") + ausblenden_zeile("TESTS, laufen lassen!", False)) == set()
assert ausgeblendet_lesen("kein json" + chr(10) + chr(10) + z) == {"tests laufen lassen", "doku schreiben"}
assert ausgeblendet_lesen("5" + chr(10) + "[1]" + chr(10) + '"text"' + chr(10) + "null") == set()
assert ausgeblendet_lesen('{"frage": "Tests laufen lassen"}') == set()
assert ausgeblendet_lesen('{"frage": "Tests laufen lassen", "aus": 1}') == set()
assert ausgeblendet_lesen('{"frage": "Tests laufen lassen", "aus": "true"}') == set()
assert ausgeblendet_lesen('{"aus": true}') == set()
assert ausgeblendet_lesen('{"frage": "ab cd", "aus": true}') == set()
assert ausgeblendet_lesen('{"frage": 5, "aus": true}') == set()
assert ausgeblendet_lesen("") == set()
assert ausgeblendet_lesen(None) == set()
assert ausgeblendet_lesen('{"frage": "Tests laufen lassen", "aus": true}' + chr(13) + chr(10)) == {"tests laufen lassen"}
''', "from vorschlag_filter import ausblenden_zeile, ausgeblendet_lesen\n")

C4 = hidden('''
a = {"frage": "Tests laufen lassen", "stufe": 2}
b = {"frage": "Doku schreiben", "stufe": 1}
c = {"frage": "Plan pruefen", "stufe": 1}
assert vorschlaege_filtern([a, b, c], set(), set()) == [a, b, c]
assert vorschlaege_filtern([a, b, c], {"doku schreiben"}, set()) == [a, c]
assert vorschlaege_filtern([a, b, c], set(), {"tests laufen lassen"}) == [b, c]
assert vorschlaege_filtern([a, b, c], {"doku schreiben"}, {"plan pruefen"}) == [a]
assert vorschlaege_filtern([a, b, c], {"doku schreiben", "tests laufen lassen"}, {"plan pruefen"}) == []
assert vorschlaege_filtern([a, b, c], None, None) == [a, b, c]
assert vorschlaege_filtern([a, b, c], ["doku schreiben"], ("plan pruefen",)) == [a]
assert vorschlaege_filtern([{"frage": "TESTS laufen, lassen!"}], {"tests laufen lassen"}, None) == []
assert vorschlaege_filtern([{"frage": "Doku schreiben bitte"}, b], {"doku schreiben"}, set()) == []
assert vorschlaege_filtern([c, a, b], {"doku schreiben"}, set()) == [c, a]
assert vorschlaege_filtern([a, "text", None, 5, ["x"], b], set(), set()) == [a, b]
assert vorschlaege_filtern([{"frage": ""}, {"frage": "ab cd"}, {"frage": None}, {"stufe": 1}, a], set(), set()) == [a]
assert vorschlaege_filtern(None, set(), set()) == []
assert vorschlaege_filtern("text", set(), set()) == []
assert vorschlaege_filtern([], set(), set()) == []
erg = vorschlaege_filtern([a, b], set(), set())
assert erg[0] is a
erg.append(c)
assert vorschlaege_filtern([a, b], set(), set()) == [a, b]
eingabe = [a, b, c]
sperre = {"doku schreiben"}
vorschlaege_filtern(eingabe, sperre, set())
assert (eingabe, sperre) == ([a, b, c], {"doku schreiben"})
''', "from vorschlag_filter import vorschlaege_filtern\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_filter_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_filter_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_filter_s3.py": C3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_filter_s4.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_filter_s1.py": C1}
