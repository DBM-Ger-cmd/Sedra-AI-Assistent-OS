"""Bau-Spec vorschau_prozess: die reinen Teile der Vorschau mit eigenem Pruefserver (SPEC_APPS_v1_O3PLUS_G9_G2 G2-09): der Befehl, die Pruefung und Kuerzung der Adresse, die Adresse aus der Ausgabe des Servers, das Ende der Vorschau.
Fuenf Stufen S1 bis S5, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul vorschau_prozess.py (Zielort spaeter harness/vorschau_prozess.py): keine Prozesse, keine Datei, kein Netz, keine Uhr (die Zeit wird hereingereicht).
Das Starten des Prozesses (subprocess, PID-Datei, leeres Pruefprojekt anlegen), die Route POST /api/harness/oberflaeche/vorschau und das Beenden macht Claude spaeter von Hand; der Eingriff in die Harness liegt nicht in diesem Bau.
S1 Befehl | S2 Adresse pruefen | S3 Adresse fuers Protokoll kuerzen | S4 Adresse aus der Ausgabe lesen | S5 Ende der Vorschau.
Referenz: benchmarks/devvm_refs/vorschau_prozess/vorschau_prozess.py."""

NOTES = '''# Notizen vorschau_prozess
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: vorschau_prozess.py. Kein Prozess wird gestartet, keine Datei gelesen, keine Uhr gelesen.
Alle Funktionen veraendern ihre Eingaben nie. Texte und Fehlercodes stehen unten genau so, wie sie erscheinen sollen; jedes Zeichen zaehlt. Regulaere Ausdruecke mit re.ASCII und mit fullmatch: der ganze Text muss passen, auch ein Zeilenumbruch am Ende macht ihn ungueltig.
Der Pruefserver gibt beim Start eine Zeile aus, die so aussieht: "SEDRA Desktop (UIX): http://127.0.0.1:51234/#" gefolgt von einem Token aus den Zeichen A-Z a-z 0-9 _ - (43 Zeichen); der Teil nach dem # ist ein Geheimnis und darf nie ins Protokoll.
'''

TASK_S1 = '''Lege vorschau_prozess.py an mit vorschau_befehl(python, root, architecture, shell=None) -> list[str]. Das Ergebnis ist die Argumentliste fuer den Prozess des Pruefservers, in dieser Reihenfolge:
[python, "-m", "sedra_runtime.uix_server", "--root", root, "--architecture", architecture, "--port", "0"] und, nur wenn shell nicht None ist, danach "--shell", shell. Die Werte stehen unveraendert in der Liste (kein Zerlegen, kein Anfuehrungszeichen, auch nicht bei Leerzeichen oder Backslash).
Gepruefte Fehler (ValueError mit dem Text als Meldung, in dieser Reihenfolge): python ist kein str, leer oder enthaelt ein Nullzeichen ("\\x00"): ValueError("python"). root ist kein str, leer, enthaelt ein Nullzeichen oder beginnt mit "-": ValueError("root"). architecture ebenso: ValueError("architecture"). shell ist nicht None und passt nicht ganz zu [a-z0-9-]{2,40} (re.ASCII, fullmatch; auch kein Nicht-Text): ValueError("shell").
Ein Wert, der mit "-" beginnt, wuerde als Option gelesen; deshalb ist er bei root und architecture verboten. Jeder Aufruf liefert eine neue Liste.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze vorschau_prozess.py. Es kommt import re dazu.
- adresse_gueltig(url) -> bool (genau True oder False): wahr nur, wenn url ein str ist und als GANZER Text diese Form hat: "http://127.0.0.1:" + Port (1 bis 5 ASCII-Ziffern, Wert von 1 bis 65535) + "/" und optional ein Fragment aus "#" und 16 bis 128 Zeichen aus A-Z a-z 0-9 _ - . Ein anderer Host (auch localhost), https, ein weiterer Pfad, Text davor oder danach (auch ein Zeilenumbruch), ein zu kurzes, zu langes oder falsch zusammengesetztes Fragment oder ein Port ausserhalb des Bereichs machen die Adresse ungueltig.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_LOG = '''Ergaenze vorschau_prozess.py: adresse_fuer_log(url) -> str. Ist adresse_gueltig(url) wahr, ist das Ergebnis die Adresse ohne das Fragment (alles ab dem "#" entfernt, der "/" bleibt); sonst "". Das Fragment ist ein Geheimnis und darf nie im Ergebnis stehen.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze vorschau_prozess.py: adresse_lesen(ausgabe) -> str oder None. ausgabe ist die Ausgabe des Pruefservers, entweder ein str mit Zeilenumbruechen (zerlegt mit splitlines()) oder eine Liste von Zeilen; jede andere Art von Eingabe (auch ein Tupel) ergibt None. Listeneintraege, die kein str sind, werden uebersprungen. Jede Zeile wird mit strip() bereinigt.
Gesucht ist die erste Zeile, die mit "SEDRA Desktop (UIX): " (mit dem Leerzeichen am Ende, ganz am Anfang der bereinigten Zeile) beginnt und deren Rest nach dem Praefix (nach strip()) laut adresse_gueltig eine gueltige Adresse ist. Zeilen mit dem Praefix und ungueltiger Adresse werden uebersprungen, die Suche geht weiter. Das Ergebnis ist dieser Rest; gibt es keine solche Zeile, None.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze vorschau_prozess.py: vorschau_ende(gestartet, jetzt, max_minuten=30, server_laeuft=True, sammelkarte_beantwortet=False) -> str oder None. gestartet und jetzt sind Zeitpunkte in Sekunden (int oder float, kein bool); die Funktion liest keine Uhr.
Zuerst wird geprueft: ist gestartet oder jetzt kein int/float (oder ein bool), oder ist jetzt kleiner als gestartet: ValueError("zeit"). Danach das Ergebnis: ist server_laeuft falsch: "server_ende"; sonst ist sammelkarte_beantwortet wahr: "beantwortet"; sonst ist jetzt - gestartet mindestens max_minuten * 60: "zeit"; sonst None (die Vorschau laeuft weiter). Die Reihenfolge ist wichtig: "server_ende" geht vor "beantwortet", das geht vor "zeit".
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert vorschau_befehl("python", "proj", "arch") == ["python", "-m", "sedra_runtime.uix_server", "--root", "proj", "--architecture", "arch", "--port", "0"]
assert vorschau_befehl("python", "proj", "arch", "harness") == ["python", "-m", "sedra_runtime.uix_server", "--root", "proj", "--architecture", "arch", "--port", "0", "--shell", "harness"]
assert vorschau_befehl("python", "proj", "arch", None) == vorschau_befehl("python", "proj", "arch")
assert vorschau_befehl("C:\\\\Pro gram\\\\python.exe", "E:\\\\a b\\\\p", "E:\\\\a b\\\\arch")[0] == "C:\\\\Pro gram\\\\python.exe"
assert vorschau_befehl("p", "E:\\\\a b\\\\p", "E:\\\\a b\\\\arch")[4] == "E:\\\\a b\\\\p"
assert vorschau_befehl("p", "x", "y", "ab")[-1] == "ab"
assert vorschau_befehl("p", "x", "y") is not vorschau_befehl("p", "x", "y")
assert all(isinstance(t, str) for t in vorschau_befehl("p", "x", "y", "kmu-2"))
def fehler(args, code):
    try:
        vorschau_befehl(*args)
    except ValueError as e:
        return str(e) == code
    return False
for bad in ("", None, 5, "a\\x00b"):
    assert fehler((bad, "x", "y"), "python")
for bad in ("", None, 5, "-x", "--root", "a\\x00b"):
    assert fehler(("p", bad, "y"), "root")
for bad in ("", None, 5, "-x", "a\\x00b"):
    assert fehler(("p", "x", bad), "architecture")
for bad in ("", "a", "A", "a b", "a" * 41, "a/b", "ab\\n", "\\u0662\\u0663", 5, ["harness"]):
    assert fehler(("p", "x", "y", bad), "shell")
assert fehler(("", "", "", "x"), "python")
assert fehler(("p", "", "", "x"), "root")
assert fehler(("p", "x", "", "x"), "architecture")
assert not fehler(("p", "x", "y", "a" * 40), "shell")
''', "from vorschau_prozess import vorschau_befehl\n")

C2 = hidden('''
T = "abcdefghijklmnopqrstuvwxyz0123456789_-ABCDEFG"
U = "http://127.0.0.1:51234/#" + T
assert adresse_gueltig(U) is True
assert adresse_gueltig("http://127.0.0.1:8080/") is True
assert adresse_gueltig("http://127.0.0.1:65535/#" + "a" * 16) is True
assert adresse_gueltig("http://127.0.0.1:51234/#" + "a" * 128) is True
assert adresse_gueltig("http://127.0.0.1:51234/#" + "a" * 129) is False
assert adresse_gueltig("http://127.0.0.1:51234/#" + "a" * 15) is False
assert adresse_gueltig("http://127.0.0.1:51234/#" + "a" * 15 + "!") is False
assert adresse_gueltig("http://127.0.0.1:51234/#") is False
assert adresse_gueltig("http://127.0.0.1:0/") is False
assert adresse_gueltig("http://127.0.0.1:65536/") is False
assert adresse_gueltig("http://127.0.0.1:123456/") is False
assert adresse_gueltig("http://127.0.0.1:\\u0665\\u0660/") is False
assert adresse_gueltig("http://127.0.0.1:80") is False
assert adresse_gueltig("http://127.0.0.1:80/\\n") is False
assert adresse_gueltig(" http://127.0.0.1:80/") is False
assert adresse_gueltig("http://127.0.0.1:80/admin") is False
assert adresse_gueltig("http://localhost:80/") is False
assert adresse_gueltig("https://127.0.0.1:80/") is False
assert adresse_gueltig("http://127.0.0.2:80/") is False
assert adresse_gueltig(None) is False
''', "from vorschau_prozess import adresse_gueltig\n")

CL = hidden('''
T = "abcdefghijklmnopqrstuvwxyz0123456789_-ABCDEFG"
U = "http://127.0.0.1:51234/#" + T
assert adresse_fuer_log(U) == "http://127.0.0.1:51234/"
assert adresse_fuer_log("http://127.0.0.1:8080/") == "http://127.0.0.1:8080/"
assert adresse_fuer_log("http://127.0.0.1:51234/#kurz") == ""
assert adresse_fuer_log("http://127.0.0.1:80/\\n") == ""
assert adresse_fuer_log("http://127.0.0.1:80/#" + T + "\\n") == ""
assert adresse_fuer_log("http://localhost:80/#" + T) == ""
assert adresse_fuer_log(None) == ""
assert adresse_fuer_log(5) == ""
assert T not in adresse_fuer_log(U)
assert "#" not in adresse_fuer_log(U)
''', "from vorschau_prozess import adresse_fuer_log\n")

C3 = hidden('''
T = "abcdefghijklmnopqrstuvwxyz0123456789_-ABCDEFG"
U = "http://127.0.0.1:51234/#" + T
P = "SEDRA Desktop (UIX): "
assert adresse_lesen(["Loopback-only. Captain gates remain enforced.", P + U, "weiter"]) == U
assert adresse_lesen("start" + chr(13) + chr(10) + P + U + chr(13) + chr(10) + "ende" + chr(13) + chr(10)) == U
assert adresse_lesen([P + "http://127.0.0.1:8080/"]) == "http://127.0.0.1:8080/"
assert adresse_lesen(["   " + P + U + "   "]) == U
assert adresse_lesen([P + "http://127.0.0.1:80", P + "http://127.0.0.1:81/"]) == "http://127.0.0.1:81/"
assert adresse_lesen([P + "http://127.0.0.1:80/", P + "http://127.0.0.1:81/"]) == "http://127.0.0.1:80/"
assert adresse_lesen([P + "http://localhost:51234/#" + T]) is None
assert adresse_lesen([P + U + " extra"]) is None
assert adresse_lesen([P + "http://127.0.0.1:51234/#kurz"]) is None
assert adresse_lesen(["x " + P + U]) is None
assert adresse_lesen(["SEDRA Desktop (UIX):" + U]) is None
assert adresse_lesen([U]) is None
assert adresse_lesen([None, 5, P + U]) == U
assert adresse_lesen([]) is None
assert adresse_lesen("") is None
assert adresse_lesen(None) is None
assert adresse_lesen(5) is None
assert adresse_lesen((P + U,)) is None
''', "from vorschau_prozess import adresse_lesen\n")

C4 = hidden('''
assert vorschau_ende(0, 10) is None
assert vorschau_ende(100.0, 100.0) is None
assert vorschau_ende(0, 1799.9) is None
assert vorschau_ende(0, 1800) == "zeit"
assert vorschau_ende(0, 99999) == "zeit"
assert vorschau_ende(10, 70, max_minuten=1) == "zeit"
assert vorschau_ende(10, 69.9, max_minuten=1) is None
assert vorschau_ende(5, 5, max_minuten=0) == "zeit"
assert vorschau_ende(-5, 0) is None
assert vorschau_ende(0, 10, server_laeuft=False) == "server_ende"
assert vorschau_ende(0, 99999, server_laeuft=False, sammelkarte_beantwortet=True) == "server_ende"
assert vorschau_ende(0, 10, sammelkarte_beantwortet=True) == "beantwortet"
assert vorschau_ende(0, 99999, sammelkarte_beantwortet=True) == "beantwortet"
assert vorschau_ende(0.5, 1800.5) == "zeit"
def fehler(*args, **kw):
    try:
        vorschau_ende(*args, **kw)
    except ValueError as e:
        return str(e) == "zeit"
    return False
assert fehler(10, 5)
assert fehler(10, 5, server_laeuft=False)
for bad in (True, None, "5", [5]):
    assert fehler(bad, 10)
    assert fehler(0, bad)
''', "from vorschau_prozess import vorschau_ende\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_vorschau_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_vorschau_s2.py": C2}},
    {"name": "S3", "task": TASK_LOG, "no_own_check": True, "hidden": {"hidden_vorschau_s3.py": CL}},
    {"name": "S4", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_vorschau_s4.py": C3}},
    {"name": "S5", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_vorschau_s5.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_vorschau_s1.py": C1}
