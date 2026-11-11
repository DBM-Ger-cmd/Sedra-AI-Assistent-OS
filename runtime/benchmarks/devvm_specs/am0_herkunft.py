"""Bau-Spec am0_herkunft: Herkunftsdatei eingebauter Module (AM0-02, Stufe A0 der Roadmap, G3 Schritt S6, Kern ohne Anbindung).
Vier Stufen S1 bis S4, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das eigenstaendige Modul herkunft_kern.py;
die Anbindung an desk/install.py, desk/gateway.py und uix_server.py macht Claude spaeter von Hand (Kandidat wird erst nach Durchsicht des Captains uebernommen).
S1 Pfad und Hashes | S2 schreiben, lesen, entfernen | S3 pruefen | S4 Zwischenspeicher.
Referenz: benchmarks/devvm_refs/am0_herkunft/herkunft_kern.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am0_herkunft start "<Auftrag>"."""

NOTES = '''# Notizen herkunft_kern
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: herkunft_kern.py.
Ein Modul liegt in einem Ordner (folder) mit Dateien, auch in Unterordnern. "area" ist genau "tools" oder "shells". "mid" ist die Kennung des Moduls und passt auf den regulaeren Ausdruck ^[a-z0-9][a-z0-9-]{1,39}$.
Fehlerhafte area oder mid fuehren zu ValueError (Text "area" beziehungsweise "id"). Pfade duerfen als Text oder als pathlib.Path uebergeben werden. Die Herkunftsdatei eines Moduls ist eine JSON-Datei; der Hash einer Datei ist der sha256 ihrer Bytes als kleingeschriebener Hex-Text.
'''

TASK_S1 = '''Lege herkunft_kern.py an mit:
- ORDNER = "uix_herkunft".
- pfad(project_root, area, mid) -> pathlib.Path: project_root / "local_config" / ORDNER / area / (mid + ".json"). Prueft area und mid zuerst (ValueError).
- erfassen(folder, area) -> dict: Schluessel ist der relative Pfad jeder Datei im Ordner und in allen Unterordnern, geschrieben mit "/" als Trenner (zum Beispiel "sub/x.js"), Wert ist der sha256-Hex der Dateibytes. Das dict ist nach Schluessel sortiert. Ein leerer Ordner ergibt {}.
  Fehler (ValueError): area ungueltig (Text "area"); folder ist kein vorhandener Ordner (Text "ordner"); irgendein Teil eines relativen Pfades, auch ein Ordnername, beginnt mit einem Punkt (Text "punkt_pfad").
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze herkunft_kern.py:
- schreiben(project_root, area, mid, folder, *, quelle, mission_id, vertrauen) -> dict: legt die Datei pfad(project_root, area, mid) an (fehlende Ordner werden erzeugt, eine vorhandene Datei wird ersetzt) und gibt denselben Inhalt als dict zurueck. Inhalt (JSON, UTF-8): "schema": 1, "art": area, "id": mid, "vertrauen_beim_einbau": vertrauen, "quelle": str(quelle), "commit": None, "mission_id": mission_id, "eingebaut_am": Zeitpunkt jetzt in UTC im Format "2026-11-10T22:30:00Z" (JJJJ-MM-TTTHH:MM:SSZ), "dateien": erfassen(folder, area).
  Die Datei wird atomar geschrieben: erst in eine Datei mit dem Namen der Zieldatei plus ".tmp" im selben Ordner, dann ersetzen; nach dem Schreiben bleibt keine ".tmp"-Datei zurueck. Ist area oder mid ungueltig, wird nichts angelegt (ValueError).
- lesen(project_root, area, mid) -> dict oder None: None, wenn die Datei nicht existiert. Sonst der Inhalt als dict. Ist die Datei kein gueltiges JSON, kein JSON-Objekt (dict) oder hat "schema" nicht den Wert 1, wird ValueError("herkunft_unlesbar") geworfen.
- entfernen(project_root, area, mid) -> None: loescht die Datei; gibt es sie nicht, passiert nichts und es gibt keinen Fehler. Andere Dateien bleiben.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze herkunft_kern.py: pruefen(folder, area, eintrag) -> list[str] vergleicht den Ordner mit einem gelesenen Eintrag (dem dict aus lesen) und gibt die Abweichungen zurueck; leere Liste heisst in Ordnung.
- Ist eintrag kein dict oder hat keinen Schluessel "dateien" mit einem dict als Wert: ["herkunft_unlesbar"].
- Ist folder kein vorhandener Ordner, gilt er als leer (alle Dateien des Eintrags fehlen).
- Wirft erfassen fuer den Ordner einen ValueError (zum Beispiel wegen eines Punkt-Pfades), ist das Ergebnis ["herkunft_pfad_ungueltig"].
- Sonst wird fuer jeden relativen Pfad, der im Eintrag oder im Ordner vorkommt, in aufsteigender Reihenfolge der Pfade (Textvergleich) genau eine Meldung erzeugt: steht der Pfad nur im Eintrag "herkunft_datei_fehlt:<pfad>"; steht er nur im Ordner "herkunft_datei_neu:<pfad>"; stehen beide da mit verschiedenem Hash "herkunft_abweichung:<pfad>"; gleicher Hash ergibt keine Meldung.
Weder der Ordner noch der Eintrag werden veraendert.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze herkunft_kern.py: die Klasse HerkunftsPruefer mit dem Attribut hash_laeufe (int, beginnt bei 0) und der Methode pruefen(folder, area, eintrag) -> list[str].
pruefen liefert dasselbe Ergebnis wie die Funktion pruefen von oben, spart aber das erneute Hashen: Zu jedem Ordner (aufgeloester absoluter Pfad als Schluessel) merkt sich der Pruefer den Stand der Dateien (aufsteigend sortiert: relativer Pfad, Groesse in Bytes, st_mtime_ns), den Eintrag (als Text mit json.dumps, sort_keys=True, default=str) und das Ergebnis. Sind Stand und Eintrag beim naechsten Aufruf fuer denselben Ordner gleich, wird das gemerkte Ergebnis (als neue Liste, nie dasselbe Listenobjekt) zurueckgegeben und hash_laeufe bleibt unveraendert. Sonst wird die Funktion pruefen aufgerufen, hash_laeufe um 1 erhoeht und das Ergebnis gemerkt. Der Stand wird nur aus os.stat gebildet, ohne Dateien zu lesen. Ist der Ordner kein Ordner, oder wirft die Standbildung einen ValueError, wird nichts gemerkt, aber hash_laeufe trotzdem um 1 erhoeht.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


HEAD = '''
import hashlib, json, os, pathlib, re, tempfile
def sha(b):
    return hashlib.sha256(b).hexdigest()
def schreib(root, rel, data):
    p = pathlib.Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
def modul():
    d = tempfile.mkdtemp()
    schreib(d, "tool.yaml", b"a")
    schreib(d, "sub/x.js", b"bb")
    schreib(d, "README.md", b"")
    return d
def wirft(f, *a, **k):
    try:
        f(*a, **k)
    except ValueError:
        return True
    return False
'''

C1 = hidden('''
assert ORDNER == "uix_herkunft"
assert pfad("/x/proj", "tools", "rechnung") == pathlib.Path("/x/proj") / "local_config" / "uix_herkunft" / "tools" / "rechnung.json"
assert pfad(pathlib.Path("/x/proj"), "shells", "a-b").name == "a-b.json"
assert wirft(pfad, "/x", "apps", "ab")
assert wirft(pfad, "/x", "tools", "A")
assert wirft(pfad, "/x", "tools", "../ab")
assert wirft(pfad, "/x", "tools", None)
d = modul()
assert erfassen(d, "tools") == {"README.md": sha(b""), "sub/x.js": sha(b"bb"), "tool.yaml": sha(b"a")}
assert list(erfassen(d, "tools")) == ["README.md", "sub/x.js", "tool.yaml"]
assert erfassen(pathlib.Path(d), "shells") == erfassen(d, "tools")
assert erfassen(tempfile.mkdtemp(), "tools") == {}
assert wirft(erfassen, d, "apps")
assert wirft(erfassen, d + "/gibt-es-nicht", "tools")
assert wirft(erfassen, d + "/tool.yaml", "tools")
h = modul()
schreib(h, ".env", b"x")
assert wirft(erfassen, h, "tools")
k = modul()
schreib(k, ".git/config", b"x")
assert wirft(erfassen, k, "tools")
n = modul()
schreib(n, "sub/.versteckt", b"x")
assert wirft(erfassen, n, "tools")
''', "from herkunft_kern import pfad, erfassen, ORDNER\n" + HEAD)

C2 = hidden('''
root = tempfile.mkdtemp()
d = modul()
r = schreiben(root, "tools", "rechnung", d, quelle=pathlib.Path("/q/rechnung"), mission_id="M-1", vertrauen="COMMUNITY")
datei = pfad(root, "tools", "rechnung")
assert datei.is_file()
assert set(r) == {"schema", "art", "id", "vertrauen_beim_einbau", "quelle", "commit", "mission_id", "eingebaut_am", "dateien"}
assert r["schema"] == 1
assert r["art"] == "tools"
assert r["id"] == "rechnung"
assert r["vertrauen_beim_einbau"] == "COMMUNITY"
assert r["quelle"] == str(pathlib.Path("/q/rechnung"))
assert r["commit"] is None
assert r["mission_id"] == "M-1"
assert re.fullmatch(r"\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\dZ", r["eingebaut_am"])
assert r["dateien"] == erfassen(d, "tools")
assert json.loads(datei.read_text(encoding="utf-8")) == r
assert lesen(root, "tools", "rechnung") == r
assert os.listdir(datei.parent) == ["rechnung.json"]
schreib(d, "tool.yaml", b"neu")
r2 = schreiben(root, "tools", "rechnung", d, quelle="q2", mission_id="M-2", vertrauen="CAPTAIN")
assert lesen(root, "tools", "rechnung")["mission_id"] == "M-2"
assert lesen(root, "tools", "rechnung")["dateien"]["tool.yaml"] == sha(b"neu")
assert os.listdir(datei.parent) == ["rechnung.json"]
assert lesen(root, "tools", "gibt-es-nicht") is None
assert lesen(root, "shells", "rechnung") is None
assert wirft(schreiben, root, "tools", "X", d, quelle="q", mission_id="m", vertrauen="v")
assert wirft(schreiben, root, "apps", "ab", d, quelle="q", mission_id="m", vertrauen="v")
assert not (pathlib.Path(root) / "local_config" / "uix_herkunft" / "apps").exists()
datei.write_text("kein json", encoding="utf-8")
assert wirft(lesen, root, "tools", "rechnung")
try:
    lesen(root, "tools", "rechnung")
except ValueError as e:
    assert str(e) == "herkunft_unlesbar"
else:
    raise AssertionError("kein ValueError")
datei.write_text("[1, 2]", encoding="utf-8")
assert wirft(lesen, root, "tools", "rechnung")
datei.write_text('{"schema": 2}', encoding="utf-8")
assert wirft(lesen, root, "tools", "rechnung")
schreiben(root, "tools", "andere", d, quelle="q", mission_id="m", vertrauen="v")
entfernen(root, "tools", "rechnung")
assert not datei.exists()
assert pfad(root, "tools", "andere").is_file()
assert entfernen(root, "tools", "rechnung") is None
assert entfernen(root, "shells", "nie-da") is None
''', "from herkunft_kern import pfad, erfassen, schreiben, lesen, entfernen\n" + HEAD)

C3 = hidden('''
d = modul()
e = {"dateien": erfassen(d, "tools")}
assert pruefen(d, "tools", e) == []
schreib(d, "sub/x.js", b"zz")
assert pruefen(d, "tools", e) == ["herkunft_abweichung:sub/x.js"]
d = modul()
os.remove(pathlib.Path(d) / "README.md")
assert pruefen(d, "tools", e) == ["herkunft_datei_fehlt:README.md"]
d = modul()
schreib(d, "extra.txt", b"x")
assert pruefen(d, "tools", e) == ["herkunft_datei_neu:extra.txt"]
d2 = tempfile.mkdtemp()
schreib(d2, "b.txt", b"1")
schreib(d2, "a.txt", b"1")
e2 = {"dateien": erfassen(d2, "tools")}
os.remove(pathlib.Path(d2) / "a.txt")
schreib(d2, "b.txt", b"2")
schreib(d2, "c.txt", b"3")
assert pruefen(d2, "tools", e2) == ["herkunft_datei_fehlt:a.txt", "herkunft_abweichung:b.txt", "herkunft_datei_neu:c.txt"]
assert pruefen(d, "tools", None) == ["herkunft_unlesbar"]
assert pruefen(d, "tools", {}) == ["herkunft_unlesbar"]
assert pruefen(d, "tools", {"dateien": []}) == ["herkunft_unlesbar"]
assert pruefen(d, "tools", "text") == ["herkunft_unlesbar"]
assert pruefen(d + "/gibt-es-nicht", "tools", {"dateien": {"z.txt": "1", "a.txt": "2"}}) == ["herkunft_datei_fehlt:a.txt", "herkunft_datei_fehlt:z.txt"]
assert pruefen(tempfile.mkdtemp(), "tools", {"dateien": {}}) == []
p = modul()
schreib(p, ".env", b"x")
assert pruefen(p, "tools", e) == ["herkunft_pfad_ungueltig"]
vorher = json.dumps(e, sort_keys=True)
pruefen(d, "tools", e)
assert json.dumps(e, sort_keys=True) == vorher
''', "from herkunft_kern import erfassen, pruefen\n" + HEAD)

C4 = hidden('''
d = modul()
e = {"dateien": erfassen(d, "tools")}
pr = HerkunftsPruefer()
assert pr.hash_laeufe == 0
assert pr.pruefen(d, "tools", e) == []
assert pr.hash_laeufe == 1
assert pr.pruefen(d, "tools", e) == []
assert pr.hash_laeufe == 1
spaeter = os.stat(pathlib.Path(d) / "tool.yaml").st_mtime_ns + 5000000000
schreib(d, "tool.yaml", b"b")
os.utime(pathlib.Path(d) / "tool.yaml", ns=(spaeter, spaeter))
assert pr.pruefen(d, "tools", e) == ["herkunft_abweichung:tool.yaml"]
assert pr.hash_laeufe == 2
assert pr.pruefen(d, "tools", e) == ["herkunft_abweichung:tool.yaml"]
assert pr.hash_laeufe == 2
e2 = {"dateien": dict(e["dateien"], **{"tool.yaml": sha(b"b")})}
assert pr.pruefen(d, "tools", e2) == []
assert pr.hash_laeufe == 3
erg = pr.pruefen(d, "tools", e2)
erg.append("muell")
assert pr.pruefen(d, "tools", e2) == []
assert pr.hash_laeufe == 3
anderer = modul()
assert pr.pruefen(anderer, "tools", {"dateien": erfassen(anderer, "tools")}) == []
assert pr.hash_laeufe == 4
schreib(d, "neu.txt", b"n")
assert pr.pruefen(d, "tools", e2) == ["herkunft_datei_neu:neu.txt"]
assert pr.hash_laeufe == 5
nichts = tempfile.mkdtemp() + "/gibt-es-nicht"
assert pr.pruefen(nichts, "tools", {"dateien": {"a": "1"}}) == ["herkunft_datei_fehlt:a"]
assert pr.hash_laeufe == 6
assert pr.pruefen(nichts, "tools", {"dateien": {"a": "1"}}) == ["herkunft_datei_fehlt:a"]
assert pr.hash_laeufe == 7
''', "from herkunft_kern import erfassen, HerkunftsPruefer\n" + HEAD)

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_herkunft_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_herkunft_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_herkunft_s3.py": C3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_herkunft_s4.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_herkunft_s1.py": C1}
