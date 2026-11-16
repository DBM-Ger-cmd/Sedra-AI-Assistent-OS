"""Bau-Spec syntax_hinweis: Prüfen vor der Freigabe (F8/H-b der SPEC_LERNEN_UND_HILFSWERKZEUGE_v1, HW-10 und HW-11): die Diff-Karte zeigt vor dem Ja "Syntax ok" oder den ersten Fehler.
Drei Stufen S1 bis S3, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul syntax_hinweis.py (Zielort spaeter harness/syntax_hinweis.py): reine Funktionen ohne Dateizugriff und ohne Prozess.
Node wird nur als Funktion hereingereicht (node_pruefer); den Prozess mit Zeitlimit (HW-11), die Karte und die Anbindung an die Diff-Karten macht Claude spaeter von Hand. YAML ist bewusst nicht dabei (Parser nicht in jeder Umgebung vorhanden).
S1 Python und JSON | S2 JavaScript ueber einen hereingereichten Pruefer | S3 Zeile fuer die Karte.
Referenz: benchmarks/devvm_refs/syntax_hinweis/syntax_hinweis.py."""

NOTES = '''# Notizen syntax_hinweis
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: syntax_hinweis.py. Keine Datei wird gelesen, kein Prozess gestartet.
Die Funktionen werfen nie eine Ausnahme (die Pruefung ist ein Hinweis und entscheidet nichts). Die Texte stehen unten genau so, wie sie erscheinen sollen; jedes Zeichen zaehlt.
Die Meldungstexte des Python-Compilers und des JSON-Parsers unterscheiden sich je nach Python-Fassung: nimm sie aus dem Fehlerobjekt (msg), erfinde keine eigenen.
'''

TASK_S1 = '''Lege syntax_hinweis.py an mit syntax_hinweis(pfad, text, node_pruefer=None) -> dict mit genau den Schluesseln "art", "ok", "hinweis". Es kommt import json dazu.
Die Art kommt aus dem Dateinamen: der letzte Teil des Pfades (Trenner "/" oder "\\\\"), seine Endung nach dem letzten Punkt in Kleinbuchstaben verglichen: "py" -> art "py", "json" -> art "json", "js" -> art "js"; jede andere Endung, ein Name ohne Punkt, ein Name, der nur aus einem Punkt und der Endung besteht (".py") und ein pfad, der kein str ist, haben art None. Bei art None ist das Ergebnis {"art": None, "ok": None, "hinweis": ""}.
Ist text kein str: {"art": art, "ok": None, "hinweis": "nicht geprueft: kein Text"}. Ist text laenger als 2000000 Zeichen: {"art": art, "ok": None, "hinweis": "nicht geprueft: zu gross"} (genau 2000000 Zeichen werden noch geprueft).
In dieser Stufe wird nur "py" und "json" geprueft (js folgt in S2; bis dahin gilt fuer js: {"art": "js", "ok": None, "hinweis": "nicht geprueft: Node fehlt"}).
- py: text wird mit compile(text, "<datei>", "exec") uebersetzt, nichts wird ausgefuehrt. Gelingt es: {"art": "py", "ok": True, "hinweis": "Syntax ok"}. SyntaxError (auch IndentationError): {"art": "py", "ok": False, "hinweis": "Zeile <n>: <msg>"} mit n = lineno des Fehlers (1, wenn keiner da ist) und msg = die Meldung des Fehlers. ValueError (zum Beispiel ein Nullbyte): ok False, hinweis "Zeile 1: nicht lesbar".
- json: text wird mit json.loads gelesen. Gelingt es: {"art": "json", "ok": True, "hinweis": "Syntax ok"}. json.JSONDecodeError: ok False, hinweis "Zeile <lineno>: <msg>" (lineno und msg des Fehlers); ein leerer Text ist ein Fehler. Andere ValueError oder RecursionError: ok False, hinweis "Zeile 1: nicht lesbar".
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Erweitere syntax_hinweis in syntax_hinweis.py um JavaScript (art "js"; die Regeln fuer art None, Nicht-Text, zu grossen Text, py und json bleiben, ebenso die Pruefung der Endung auch in Grossbuchstaben).
node_pruefer ist eine Funktion node_pruefer(text) -> (ok, meldung), die der Aufrufer hereinreicht; syntax_hinweis startet selbst keinen Prozess. Sie wird nur fuer art "js" und nur mit einem str-Text im erlaubten Umfang aufgerufen, genau einmal, mit dem Text unveraendert.
- node_pruefer ist None: {"art": "js", "ok": None, "hinweis": "nicht geprueft: Node fehlt"}.
- Der Pruefer wirft irgendeine Exception: {"art": "js", "ok": None, "hinweis": "nicht geprueft: Pruefer abgestuerzt"}.
- ok ist wahr (jeder wahre Wert): {"art": "js", "ok": True, "hinweis": "Syntax ok"}.
- ok ist falsch: ok False; hinweis ist die erste Zeile der meldung, die nach strip() nicht leer ist (mit strip() bereinigt); ist meldung leer, None oder hat keine solche Zeile, ist hinweis "Syntaxfehler". meldung kann ein beliebiges Objekt sein (benutze str(meldung)); None zaehlt als leer.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze syntax_hinweis.py: karten_zeile(erg) -> str, die eine Zeile fuer die Diff-Karte aus einem Ergebnis von syntax_hinweis.
- Ist erg ein dict und erg.get("ok") genau True (der Wert True, nicht nur ein wahrer Wert): "Syntax ok (" + art + ")" mit art aus erg.get("art"), zum Beispiel "Syntax ok (py)".
- Ist erg ein dict und erg.get("ok") genau False: "Syntax-Hinweis: " + hinweis (str von erg.get("hinweis"), bei None oder fehlendem Schluessel leer, also nur "Syntax-Hinweis: ").
- In allen anderen Faellen (ok ist None, erg ist kein dict, Schluessel fehlen, ok ist ein anderer wahrer Wert wie 1): der leere String "".
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert syntax_hinweis("a.py", "x = 1\\n") == {"art": "py", "ok": True, "hinweis": "Syntax ok"}
assert syntax_hinweis("a.json", '{"a": [1, 2]}') == {"art": "json", "ok": True, "hinweis": "Syntax ok"}
r = syntax_hinweis("dir/a.py", "def f(:\\n")
assert r["ok"] is False
assert r["hinweis"].startswith("Zeile 1: ")
assert syntax_hinweis("a.py", "x = 1\\nif x\\n    y = 2\\n")["hinweis"].startswith("Zeile 2: ")
assert syntax_hinweis("dir\\\\a.PY", "x = 1\\n")["art"] == "py"
r = syntax_hinweis("a.json", "{")
assert r["ok"] is False
assert r["hinweis"].startswith("Zeile 1: ")
assert syntax_hinweis("a.json", "[1,\\n2,\\n,]")["hinweis"].startswith("Zeile 3: ")
assert syntax_hinweis("a.json", "")["ok"] is False
assert syntax_hinweis("a.txt", "x") == {"art": None, "ok": None, "hinweis": ""}
assert syntax_hinweis(".py", "def f(:") == {"art": None, "ok": None, "hinweis": ""}
assert syntax_hinweis("x.py.txt", "def f(:") == {"art": None, "ok": None, "hinweis": ""}
assert syntax_hinweis(None, "x") == {"art": None, "ok": None, "hinweis": ""}
assert syntax_hinweis("a.py", None) == {"art": "py", "ok": None, "hinweis": "nicht geprueft: kein Text"}
assert syntax_hinweis("a.json", b"{}") == {"art": "json", "ok": None, "hinweis": "nicht geprueft: kein Text"}
assert syntax_hinweis("a.py", "x = 1\\x00")["ok"] is False
assert syntax_hinweis("a.py", "#" * 2000001) == {"art": "py", "ok": None, "hinweis": "nicht geprueft: zu gross"}
assert syntax_hinweis("a.py", "#" * 2000000)["ok"] is True
assert syntax_hinweis("a.js", "x")["ok"] is None
''', "from syntax_hinweis import syntax_hinweis\n")

C2 = hidden('''
aufrufe = []
def pruefer(ok, meldung):
    def f(text):
        aufrufe.append(text)
        return ok, meldung
    return f

assert syntax_hinweis("a.js", "x", None) == {"art": "js", "ok": None, "hinweis": "nicht geprueft: Node fehlt"}
assert syntax_hinweis("a.js", "x", pruefer(True, "")) == {"art": "js", "ok": True, "hinweis": "Syntax ok"}
assert syntax_hinweis("a.js", "x", pruefer(False, "a.js:3\\nSyntaxError: Unexpected token\\nmehr")) == {"art": "js", "ok": False, "hinweis": "a.js:3"}
assert syntax_hinweis("a.js", "x", pruefer(False, "\\n\\n  Fehler eins  \\nzwei"))["hinweis"] == "Fehler eins"
assert syntax_hinweis("a.js", "x", pruefer(False, ""))["hinweis"] == "Syntaxfehler"
assert syntax_hinweis("a.js", "x", pruefer(False, None))["hinweis"] == "Syntaxfehler"
assert syntax_hinweis("a.js", "x", pruefer(False, " \\n \\n"))["hinweis"] == "Syntaxfehler"
assert syntax_hinweis("a.js", "x", pruefer(1, ""))["ok"] is True
def kaputt(text):
    raise RuntimeError("weg")
assert syntax_hinweis("a.js", "x", kaputt) == {"art": "js", "ok": None, "hinweis": "nicht geprueft: Pruefer abgestuerzt"}
aufrufe.clear()
syntax_hinweis("a.js", "var a = 1;", pruefer(True, ""))
assert aufrufe == ["var a = 1;"]
aufrufe.clear()
syntax_hinweis("a.py", "x = 1", pruefer(True, ""))
syntax_hinweis("a.json", "{}", pruefer(True, ""))
syntax_hinweis("a.txt", "x", pruefer(True, ""))
assert aufrufe == []
assert syntax_hinweis("a.js", None, pruefer(True, "")) == {"art": "js", "ok": None, "hinweis": "nicht geprueft: kein Text"}
assert syntax_hinweis("a.js", "x" * 2000001, pruefer(True, "")) == {"art": "js", "ok": None, "hinweis": "nicht geprueft: zu gross"}
assert aufrufe == []
assert syntax_hinweis("DIR/A.JS", "x", pruefer(True, ""))["art"] == "js"
assert syntax_hinweis("a.mjs", "x", pruefer(True, ""))["art"] is None
''', "from syntax_hinweis import syntax_hinweis\n")

C3 = hidden('''
assert karten_zeile(syntax_hinweis("a.py", "x = 1")) == "Syntax ok (py)"
assert karten_zeile(syntax_hinweis("a.json", "{}")) == "Syntax ok (json)"
assert karten_zeile(syntax_hinweis("a.js", "x", lambda t: (True, ""))) == "Syntax ok (js)"
assert karten_zeile({"art": "py", "ok": False, "hinweis": "Zeile 2: kaputt"}) == "Syntax-Hinweis: Zeile 2: kaputt"
assert karten_zeile({"art": "py", "ok": False}) == "Syntax-Hinweis: "
assert karten_zeile({"art": "py", "ok": False, "hinweis": None}) == "Syntax-Hinweis: "
assert karten_zeile({"art": "py", "ok": None, "hinweis": "nicht geprueft: kein Text"}) == ""
assert karten_zeile({"art": None, "ok": None, "hinweis": ""}) == ""
assert karten_zeile(None) == ""
assert karten_zeile("Syntax ok") == ""
assert karten_zeile({}) == ""
assert karten_zeile({"art": "py", "ok": 1, "hinweis": "x"}) == ""
assert karten_zeile({"art": "py", "ok": 0, "hinweis": "x"}) == ""
assert karten_zeile(syntax_hinweis("a.py", "x = (")).startswith("Syntax-Hinweis: Zeile 1: ")
assert karten_zeile(syntax_hinweis("a.js", "x", lambda t: (False, "boom\\nzwei"))) == "Syntax-Hinweis: boom"
''', "from syntax_hinweis import syntax_hinweis, karten_zeile\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_syntax_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_syntax_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_syntax_s3.py": C3}},
]
TASK = TASK_S1
HIDDEN = {"hidden_syntax_s1.py": C1}
