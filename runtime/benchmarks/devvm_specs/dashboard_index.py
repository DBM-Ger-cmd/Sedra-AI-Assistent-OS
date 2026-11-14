"""Bau-Spec dashboard_index (Vergleichsaufgabe Unsloth gegen SEDRA, Captain 2026-11-12: "alles in einer Schleife"). Aufgabe aus dem Unsloth-Chat vom 12.11. (Index, Dashboard, Spaltennamen, Abgleich), der dort in 12 Schleifen
ein nicht lauffaehiges Dashboard ergab (Syntaxfehler, Funktion als Text nach </script>, feste Kopfzahlen, kein git_info, localStorage-Quote). Drei Stufen, je ein versteckter Test, kein eigener Test des Modells.
Referenz: benchmarks/devvm_refs/dashboard_index/build_index.py. Die Tests laufen mit Python und rufen node nur fuer die Syntaxpruefung der HTML-Seite auf. In der microVM gibt es kein node (geprueft 2026-11-12): dort entfaellt diese eine Pruefung (syntax_ok gibt True), die uebrigen Pruefungen (keine "= const", nur Tags nach </script>, ...) laufen. Die volle Pruefung eines Kandidaten mit node macht danach `spec_check dashboard_index --tree <Kandidat> --host-ok` auf dem Host."""

NOTES = '''# Notizen build_index.py
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests. Alles steht in EINER Datei `build_index.py` im Arbeitsordner (auch die HTML-Seite, als Textkonstante). Aufruf: `python build_index.py --root <Ordner> --out <Ordner> [--check]`. `--root` ist der zu scannende Ordner (Vorgabe: aktueller Ordner), `--out` der Ordner fuer die drei Ausgabedateien (Vorgabe: der Wert von --root).
Die drei Ausgabedateien heissen `dashboard_data.json`, `INDEX.md`, `PROJEKT_DASHBOARD.html`. Sie werden beim Scannen nie mitgezaehlt (auch nicht, wenn --out gleich --root ist). Ohne --check schreibt das Programm alle drei und endet mit Exit-Code 0.
Ausgeschlossen vom Scan (nicht gezaehlt, nicht gelistet): Ordner mit dem Namen `__pycache__`, `node_modules`, `.venv`. Die Systemordner `.git` und `.claude` erscheinen als Ordner mit Kategorie "system", echten Zaehlwerten (direkt und rekursiv, alles darin mitgezaehlt) und `children` = [], Groesse 0.
Die Datei `dashboard_data.json` ist die einzige Datenquelle. Ihr Wurzelknoten und jeder Ordnerknoten haben genau diese Felder: `name` (Wurzel: "."), `path` (relativ zur Wurzel, mit "/" getrennt, Wurzel: "."), `type` = "dir", `category`, `files_direct`, `files_recursive`, `dirs_direct`, `dirs_recursive`, `size_bytes` (Summe aller Dateien darunter in Bytes), `children`. Ein Dateiknoten hat `name`, `path`, `type` = "file", `category`, `size_bytes`.
`children`: zuerst alle Ordner, dann alle Dateien, jede Gruppe nach dem Namen in Kleinbuchstaben sortiert. `files_direct`/`dirs_direct` zaehlen nur den Ordner selbst, `files_recursive`/`dirs_recursive` alles darunter (ein Unterordner zaehlt als ein Ordner, seine Inhalte kommen dazu).
Kategorie einer Datei nach der Endung (klein geschrieben): .py .js .ts .html .css .bat .ps1 .sh = "code"; .md .txt .rst = "docs"; .json .yaml .yml .toml .ini .cfg = "config"; alles andere "other". Kategorie eines Ordners (ausser .git und .claude): die Kategorie, die unter allen Dateien darunter (rekursiv, ohne Systemordner) am haeufigsten vorkommt, bei Gleichstand die alphabetisch erste; ohne Dateien "other".
Nur der Wurzelknoten hat zusaetzlich `generated_at` (ISO-Zeitpunkt als Text), `count_mode` (Text, der "direkt" und "rekursiv" erklaert) und `git_info` mit genau den Schluesseln `branch`, `commit`, `date`, `total_commits`. Ist die Wurzel kein Git-Repository, sind die ersten drei None und total_commits 0.
'''

HEAD = r'''
import json, os, re, shutil, subprocess, sys, tempfile, datetime

FILES = {"a.py": "x = 1\n", "README.md": "# r\n", "docs/guide.md": "guide\n", "docs/notes.txt": "notes\n",
         "docs/Anleitung Süd.md": "s\n", "docs/deep/more.md": "more\n", "src/main.py": "print(1)\n", "src/util.js": "1\n",
         "src/conf.json": "{}\n", "mix/a.py": "a\n", "mix/b.md": "b\n", "__pycache__/x.pyc": "bin\n",
         ".git/HEAD": "ref\n", ".git/objects/ab/cd": "o\n", ".claude/s.json": "{}\n"}
COUNTED = {k: v for k, v in FILES.items() if not k.startswith((".git", ".claude", "__pycache__"))}
SCRIPT = os.path.abspath("build_index.py")

def make_tree():
    root = tempfile.mkdtemp()
    for rel, text in FILES.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(text.encode("utf-8"))
    os.makedirs(os.path.join(root, "leer"))
    return root

def run(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})

def FAIL_INFO(done):
    lines = [l for l in done.stderr.strip().splitlines() if l.strip()]
    where = [l.strip() for l in lines if l.lstrip().startswith("File ")]
    return ((lines[-1] if lines else "no stderr") + " @ " + (where[-1].split(", in ")[0].split("\\")[-1] if where else ""))[:200]

def load(out):
    with open(os.path.join(out, "dashboard_data.json"), encoding="utf-8") as fh:
        return json.load(fh)

def child(node, name):
    return next((c for c in node["children"] if c["name"] == name), None)

def counts(n):
    return (n["files_direct"], n["files_recursive"], n["dirs_direct"], n["dirs_recursive"])

ROOT = make_tree()
OUT = tempfile.mkdtemp()
RUN = run("--root", ROOT, "--out", OUT)
'''

S1 = HEAD + r'''
D = load(OUT)
docs, src, leer, git = child(D, "docs"), child(D, "src"), child(D, "leer"), child(D, ".git")
assert RUN.returncode == 0, FAIL_INFO(RUN)
assert (D["name"], D["path"], D["type"]) == (".", ".", "dir")
assert counts(D) == (2, 14, 6, 9)
assert counts(docs) == (3, 4, 1, 1)
assert (docs["category"], src["category"], child(D, "mix")["category"], leer["category"], D["category"]) == ("docs", "code", "code", "other", "docs")
assert counts(leer) == (0, 0, 0, 0)
assert (git["category"], git["children"], counts(git), git["size_bytes"]) == ("system", [], (1, 2, 1, 2), 0)
assert [c["name"] for c in D["children"]] == [".claude", ".git", "docs", "leer", "mix", "src", "a.py", "README.md"]
assert child(D, "a.py") == {"name": "a.py", "path": "a.py", "type": "file", "category": "code", "size_bytes": 6}
assert child(child(docs, "deep"), "more.md")["path"] == "docs/deep/more.md"
assert D["size_bytes"] == sum(len(t.encode("utf-8")) for t in COUNTED.values())
assert D["git_info"] == {"branch": None, "commit": None, "date": None, "total_commits": 0}
assert datetime.datetime.fromisoformat(D["generated_at"]) is not None
assert "direkt" in D["count_mode"]
assert "rekursiv" in D["count_mode"]
assert child(docs, "Anleitung Süd.md")["path"] == "docs/Anleitung Süd.md"
assert run("--root", ROOT, "--out", ROOT).returncode == 0
assert counts(load(ROOT)) == (2, 14, 6, 9)
'''

S2_ONLY = r'''
TEXT = open(os.path.join(OUT, "INDEX.md"), encoding="utf-8").read()
LINES = TEXT.splitlines()
HEADER = "| Verzeichnis | Kategorie | Dateien direkt | Dateien rekursiv | Unterordner direkt | Unterordner rekursiv |"
assert HEADER in LINES
assert "| . | docs | 2 | 14 | 6 | 9 |" in LINES
assert "| docs | docs | 3 | 4 | 1 | 1 |" in LINES
assert "| .git | system | 1 | 2 | 1 | 2 |" in LINES
assert "| mix | code | 2 | 2 | 0 | 0 |" in LINES
assert not any(l.startswith("| docs/deep") for l in LINES)
assert len([l for l in LINES if l.startswith("|")]) == 9
assert "child name" not in TEXT.lower() and "node name" not in TEXT.lower()
assert "Erzeugt: " + load(OUT)["generated_at"] in LINES
assert "Git: kein Repository" in LINES
GOOD = run("--root", ROOT, "--out", OUT, "--check")
assert (GOOD.returncode, GOOD.stdout.strip()) == (0, "konsistent")
with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write(TEXT.replace("| docs | docs | 3 | 4 | 1 | 1 |", "| docs | docs | 3 | 5 | 1 | 1 |"))
BAD = run("--root", ROOT, "--out", OUT, "--check")
assert BAD.returncode == 1
assert "abweichung: docs files_recursive index=5 json=4" in BAD.stdout
with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write(TEXT)
DATA = load(OUT)
DATA["files_direct"] = 99
with open(os.path.join(OUT, "dashboard_data.json"), "w", encoding="utf-8") as fh:
    json.dump(DATA, fh)
assert "abweichung: . files_direct index=2 json=99" in run("--check", "--out", OUT).stdout
os.remove(os.path.join(OUT, "INDEX.md"))
MISSING = run("--check", "--out", OUT)
assert (MISSING.returncode, MISSING.stdout.strip()) == (1, "fehlt: INDEX.md")
'''

S2 = S1 + S2_ONLY

S3_ONLY = r'''
RUN = run("--root", ROOT, "--out", OUT)
assert RUN.returncode == 0, FAIL_INFO(RUN)
HTML = open(os.path.join(OUT, "PROJEKT_DASHBOARD.html"), encoding="utf-8").read()
SCRIPTS = re.findall(r"<script>(.*?)</script>", HTML, re.S)
JS = SCRIPTS[0] if SCRIPTS else ""

def syntax_ok(js):
    node = shutil.which("node")
    if not node:
        return True
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(js)
    try:
        return subprocess.run([node, "--check", fh.name], capture_output=True).returncode == 0
    finally:
        os.unlink(fh.name)

def stat_content(name):
    m = re.search(r'id="' + name + r'"[^>]*>(.*?)<', HTML, re.S)
    return m.group(1).strip() if m else None

assert HTML.lstrip().lower().startswith("<!doctype html>")
assert (HTML.count("<script>"), HTML.count("</script>")) == (1, 1)
assert re.sub(r"<[^>]*>", "", HTML.rsplit("</script>", 1)[1]).strip() == ""
assert syntax_ok(JS)
assert re.search(r"=\s*(const|let|var)\s", JS) is None
assert "fetch(" in JS and "dashboard_data.json" in JS
assert ".catch(" in JS and "http.server" in HTML
assert "localStorage" not in HTML and "sessionStorage" not in HTML
assert '"children"' not in HTML and "files_recursive\": " not in HTML
assert [i for i in ("statFiles", "statDirs", "statSize", "treeContainer", "fileList", "globalSearch", "searchResults", "currentPath", "dashboardFooter") if 'id="' + i + '"' not in HTML] == []
assert [i for i in ("statFiles", "statDirs", "statSize") if stat_content(i) != "-"] == []
assert [f for f in ("renderTree", "showDirectory", "initGlobalSearch", "showGitInfo", "exportJSON") if "function " + f not in JS] == []
assert re.search(r"MAX_ITEMS\s*=\s*200\b", JS) is not None
assert "child name" not in HTML.lower() and "node name" not in HTML.lower()
assert "(rekursiv)" in HTML
assert len(HTML.encode("utf-8")) < 100000
'''

S3 = S2 + S3_ONLY

STAGES = [
    {"name": "scan", "no_own_check": True,
     "task": '''Lege `build_index.py` an (siehe die Notizen: Aufruf, Ausschluesse, Feldnamen, Sortierung, Kategorien). Ohne --check scannt das Programm den Ordner von --root und schreibt in den Ordner von --out die Datei `dashboard_data.json` (Aufbau genau wie in den Notizen) und endet mit Exit-Code 0; die zwei anderen Ausgabedateien schreibst du erst in den naechsten Stufen. Die Ausgabedateien selbst werden nie mitgezaehlt. Die Namen koennen Leerzeichen und Umlaute enthalten. Keine Kommentare, keine Docstrings, keine eigenen Tests.''',
     "hidden": {"hidden_dashboard_1.py": S1}},
    {"name": "index", "no_own_check": True,
     "task": '''Ergaenze `build_index.py`: Beim Schreiben entsteht aus denselben Daten auch `INDEX.md` im Ordner von --out. Aufbau (jede Zeile genau so): `# Projekt-Index`, leere Zeile, `Erzeugt: <generated_at>`, `Git: <branch>@<commit> (<total_commits> Commits)` oder `Git: kein Repository` (wenn commit None ist), `Zaehlweise: <count_mode>`, leere Zeile, dann die Tabellenkopfzeile `| Verzeichnis | Kategorie | Dateien direkt | Dateien rekursiv | Unterordner direkt | Unterordner rekursiv |`, die Trennzeile `|---|---|---|---|---|---|` und je eine Zeile `| <path> | <category> | <files_direct> | <files_recursive> | <dirs_direct> | <dirs_recursive> |` fuer die Wurzel (path ".") und dann fuer jeden Ordner der ersten Ebene (in der Reihenfolge von `children`). Keine tieferen Ordner, keine Dateien. Platzhalter wie "child name" oder "node name" kommen nirgends vor.
Dazu `python build_index.py --out <Ordner> --check`: liest `dashboard_data.json` und `INDEX.md` aus dem Ordner und vergleicht die vier Zaehlfelder jeder Tabellenzeile mit dem Ordner gleichen Pfads in der JSON (Wurzel und Ordner der ersten Ebene). Ist alles gleich: Ausgabe `konsistent`, Exit-Code 0. Sonst je Abweichung eine Zeile `abweichung: <path> <feldname> index=<Wert im Index> json=<Wert in der JSON>` (Feldname wie in der JSON, zum Beispiel files_recursive) und Exit-Code 1; fehlt ein Pfad im Index, die Zeile `abweichung: <path> fehlt im Index`. Fehlt eine der beiden Dateien: Ausgabe `fehlt: <Dateiname>` und Exit-Code 1. --check schreibt nichts. Keine Kommentare, keine Docstrings, keine eigenen Tests.''',
     "hidden": {"hidden_dashboard_2.py": S2}},
    {"name": "dashboard", "no_own_check": True,
     "task": '''Ergaenze `build_index.py`: Beim Schreiben entsteht auch `PROJEKT_DASHBOARD.html` im Ordner von --out, eine einzelne HTML-Seite mit genau einem `<script>`-Block, die `dashboard_data.json` per `fetch("dashboard_data.json")` laedt (die Daten stehen NICHT in der Seite). Die Seite braucht diese Elemente mit diesen ids: `statFiles`, `statDirs`, `statSize` (Kopfzahlen; im HTML steht darin nur der Platzhalter `-`, die Werte setzt das Skript aus der JSON: Dateien und Verzeichnisse rekursiv, Groesse), `treeContainer` (Verzeichnisbaum), `fileList` (Inhalt des gewaehlten Ordners), `currentPath`, `globalSearch` (Eingabefeld) mit `searchResults` (Trefferzahl), `dashboardFooter` (Zeile mit Zeitpunkt und Git: Branch, Commit, Anzahl Commits, oder "kein Repository"). Beschriftungen der Kopfzahlen tragen den Zusatz "(rekursiv)".
Das Skript definiert die Funktionen `renderTree`, `showDirectory`, `initGlobalSearch`, `showGitInfo` und `exportJSON` (Export der Daten als JSON-Datei) und die Konstante `MAX_ITEMS = 200`: ein Ordner mit mehr Eintraegen zeigt zuerst 200 und einen Knopf "<n> weitere laden". Die Kategorien haben Farben (CSS-Klassen `cat-<kategorie>`). Gelingt das Laden nicht, ersetzt eine Fehlermeldung die Seite mit dem Hinweis auf `python -m http.server`. Kein localStorage und kein sessionStorage. Die Seite ist kleiner als 100000 Bytes, der Skriptblock muss ohne Syntaxfehler laufen (jede Funktion innerhalb von `<script>`, nach `</script>` nur noch `</body></html>`), und der Text "child name" oder "node name" darf nicht vorkommen. Keine Kommentare, keine Docstrings, keine eigenen Tests.''',
     "hidden": {"hidden_dashboard_3.py": S3}},
]
