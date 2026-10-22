"""Prüfmittel für die Tests des Wissensspeichers (Spec 7): ein Fake-Embedding-Server auf 127.0.0.1 mit festen Vektoren (Wortfelder,
Dimension 8), ein Fake-Prozess für den Starter, ein Prüfprojekt mit drei Quellen (Markdown-Ordner, knowledge-JSON-Zeilen,
Arbeitsumfeld- und Gateway-SQLite) und eine Konfiguration, die auf den Fake zeigt. Nie der Goldsatz, kein Netz, kein Modell."""
import hashlib
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from guppi_runtime.wissen import konfig as konfig_mod
from guppi_runtime.wissen import speicher as speicher_mod

DIM = 8
# Wortfelder: jedes Feld eine Dimension; „Videospeicher“ und „VRAM“ liegen so im selben Feld (die Wortsuche findet das nicht)
FELDER = (("videospeicher", "vram", "grafikspeicher", "gpu"), ("lease", "sperre", "halter", "testlabor"), ("logbuch", "eintrag", "zeile"),
          ("regel", "regelbuch", "pflicht"), ("karte", "kreditkarte", "kartendaten"), ("notiz", "lektion", "lesson"), ("ordner", "datei", "pfad"),
          ("geheim", "vertraulich"))


def vektor_fuer(text):
    t = text.lower()
    werte = [float(sum(t.count(w) for w in feld)) for feld in FELDER]
    if not any(werte):
        h = hashlib.sha256(t.encode("utf-8")).digest()
        werte = [0.01 * (b / 255.0 + 0.1) for b in h[:DIM]]
    return werte


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return None

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.server.kaputt:
            return self._send({"error": "kaputt"}, 500)
        if self.path == "/health":
            return self._send({"status": "ok"})
        if self.path == "/v1/models":
            return self._send({"data": [{"id": self.server.alias}]})
        self._send({"error": "unbekannt"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        self.server.anfragen.append(body)
        if self.server.kaputt:
            return self._send({"error": "kaputt"}, 500)
        texte = body.get("input")
        if isinstance(texte, str):
            texte = [texte]
        if self.server.falsche_dim:
            return self._send({"data": [{"index": i, "embedding": [1.0] * (DIM + 1)} for i in range(len(texte))]})
        self._send({"data": [{"index": i, "embedding": vektor_fuer(t)} for i, t in enumerate(texte)]})


class _Server(HTTPServer):
    def handle_error(self, request, client_address):
        return None                                       # ein abgebrochener Aufruf (Zeitgrenze des Clients) ist kein Fehler des Fakes


class FakeEmbedServer:
    """`with FakeEmbedServer() as s: s.port` – antwortet wie `llama-server --embeddings` (Teilmenge)."""

    def __init__(self, alias="wissen-embed", lazy=False):
        self.server = _Server(("127.0.0.1", 0), _Handler)
        self.server.anfragen, self.server.kaputt, self.server.falsche_dim, self.server.alias = [], False, False, alias
        self.port = self.server.server_address[1]
        self.lazy = lazy
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)

    def starten(self):
        """Der „Prozess“ geht an: ab jetzt antwortet der Port (lazy=True wartet darauf, dass der Starter ruft)."""
        if not self.thread.is_alive():
            self.thread.start()

    def __enter__(self):
        if not self.lazy:
            self.starten()
        return self

    def __exit__(self, *exc):
        if self.thread.is_alive():
            self.server.shutdown()
        self.server.server_close()

    @property
    def anfragen(self):
        return self.server.anfragen


class FakeProc:
    """Was `subprocess.Popen` liefert, ohne Prozess: der Fake-Server läuft schon."""
    naechste_pid = 40000

    def __init__(self, cmd, **kw):
        FakeProc.naechste_pid += 1
        self.pid, self.cmd, self.beendet = FakeProc.naechste_pid, list(cmd), False

    def poll(self):
        return 0 if self.beendet else None

    def terminate(self):
        self.beendet = True

    def kill(self):
        self.beendet = True

    def wait(self, timeout=None):
        return 0


class Starter:
    """Ersetzt `subprocess.Popen`: merkt den Befehl, startet den Fake-Server (wenn er einen hat) und gibt einen Fake-Prozess."""

    def __init__(self, server=None):
        self.gestartet, self.server = [], server

    def __call__(self, cmd, **kw):
        p = FakeProc(cmd, **kw)
        self.gestartet.append(p)
        if self.server is not None:
            self.server.starten()
        return p


DOCS = {
    "docs/GPU.md": "# GPU-Regeln\n\n## Videospeicher\n\nEin Modell darf höchstens 11,5 GB VRAM belegen; darüber greift hardware_pressure.\n\n"
                   "## Lease\n\nVor dem Laden die Lease des Testlabors holen; der Halter wird nie beendet.\n",
    "docs/LOGBUCH_AGENT_MANAGER.md": "# Logbuch Agent Manager\n\nEinleitung zum Logbuch.\n\n| Zeit | Art | Eintrag |\n| --- | --- | --- |\n"
                                     "| 2026-10-20 09:00 | BAU | Erster Bau der Werkbank |\n| 2026-10-21 10:00 | ENTSCHEIDUNG | Regel für Ordnerfreigaben |\n",
    "docs/GEHEIM.md": "# Vertraulich\n\n## Eigene Ordner\n\nDer Ordner der Steuerunterlagen ist vertraulich und bleibt lokal.\n",
    "notizen/plan.txt": "Erster Absatz über Ordner und Pfade.\n\nZweiter Absatz über die Karte des Geländes.\n",
}


def repo_anlegen(root):
    root = Path(root)
    for rel, text in DOCS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def speicher_anlegen(projekt):
    """Die drei bestehenden Speicher als Dateien, wie ihre Klassen sie schreiben (nur Form, eigene Inhalte)."""
    projekt = Path(projekt)
    kn = projekt / "runtime_data" / "knowledge" / "records.jsonl"
    kn.parent.mkdir(parents=True, exist_ok=True)
    zeilen = [
        {"schema": 1, "id": "KN-1", "type": "note", "title": "Notiz zum Logbuch", "content": {"summary": "Jeder Eintrag im Logbuch bekommt die Uhrzeit aus date.", "data": {}},
         "provenance": {"created_at": "2026-10-20T08:00:00Z"}, "scope": {"project": "GUPPI", "tags": ["logbuch"]}, "status": "active"},
        {"schema": 1, "id": "KN-2", "type": "coding_lesson", "title": "Regex sauber", "content": {"summary": "Use re.fullmatch for whole-string checks.", "data": {}},
         "provenance": {"created_at": "2026-10-20T09:00:00Z"}, "scope": {"project": "GUPPI", "tags": ["re.match(", "regex"]}, "status": "active"},
        {"schema": 1, "id": "KN-3", "type": "note", "title": "Alt", "content": {"summary": "Veraltete Notiz.", "data": {}},
         "provenance": {"created_at": "2026-10-01T09:00:00Z"}, "scope": {"project": "GUPPI", "tags": []}, "status": "retired"},
    ]
    kn.write_text("".join(json.dumps(z) + "\n" for z in zeilen), encoding="utf-8")
    au = projekt / "local_config" / "arbeitsumfeld" / "wissen.sqlite"
    au.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(au))
    db.execute("CREATE TABLE IF NOT EXISTS wissen (id TEXT PRIMARY KEY, art TEXT, titel TEXT, text TEXT, quelle TEXT, version TEXT)")
    db.execute("INSERT INTO wissen VALUES ('AU-1', 'ordner', 'Ordner local_config', 'Einstellungen und Zustände: Modelle, Gateway, Schalter.', 'Platte', '1')")
    db.execute("INSERT INTO wissen VALUES ('AU-2', 'aktion', 'Vorarbeiter-Aktion Lease holen', 'Vor dem Laden eines Modells wird die Lease des Testlabors geholt.', 'Regelwerk', '1')")
    db.commit()
    db.close()
    gw = projekt / "local_config" / "gateway" / "wissen.sqlite"
    gw.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(gw))
    db.execute("CREATE TABLE IF NOT EXISTS wissen (id TEXT PRIMARY KEY, art TEXT, titel TEXT, text TEXT, tun TEXT, stichworte TEXT, version TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS eigene (id INTEGER PRIMARY KEY AUTOINCREMENT, frage TEXT, antwort TEXT, erstellt TEXT)")
    db.execute("INSERT INTO wissen VALUES ('R-07', 'regel', 'Regel R-07 Kartendaten', 'Kartendaten mit Prüfwert gehen nie an einen Anbieter.', 'Entwurf pseudonymisieren', 'karte', '1')")
    db.execute("INSERT INTO eigene (frage, antwort, erstellt) VALUES ('Wo liegt die Steuernummer?', 'Im vertraulichen Ordner.', '2026-10-21T12:00:00Z')")
    db.commit()
    db.close()
    return projekt


def modell_dateien(root):
    """Eine Fake-Engine und eine Fake-GGUF mit bekannter Prüfsumme."""
    root = Path(root)
    engine = root / "engine" / "llama-server"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    gguf = root / "modelle" / "fake-embed-q8_0.gguf"
    gguf.parent.mkdir(parents=True, exist_ok=True)
    gguf.write_bytes(b"GGUF-FAKE-" + b"0" * 100)
    return engine, gguf, hashlib.sha256(gguf.read_bytes()).hexdigest()


def konfig_fuer(root, port, *, sha=None, takt_an=False):
    engine, gguf, echte_sha = modell_dateien(root)
    k = konfig_mod.load(Path(__file__).resolve().parents[1] / "config" / "wissen.yaml")
    k.engine, k.modell, k.modell_sha256, k.modell_name, k.port, k.dim = str(engine), str(gguf), sha or echte_sha, "fake-embed", port, DIM
    k.takt_an = takt_an
    k.anfrage_timeout_s = 3.0
    k.start_warten_s = 1.0
    return k


class Audit:
    def __init__(self):
        self.events = []

    def __call__(self, event, payload):
        self.events.append((event, payload))

    def nur(self, event):
        return [p for e, p in self.events if e == event]


def oeffnen(tmp, port, *, sha=None, uhr=None, gpu=None, server=None, **kw):
    """Ein Speicher im Prüfprojekt `<tmp>/projekt` mit Repo `<tmp>/repo`, Starter mit Fake-Prozess (startet `server`, wenn gegeben)."""
    tmp = Path(tmp)
    repo = repo_anlegen(tmp / "repo")
    projekt = speicher_anlegen(tmp / "projekt")
    audit, starter = Audit(), Starter(server)
    sp = speicher_mod.WissenSpeicher(konfig_fuer(tmp, port, sha=sha), projekt_root=projekt, repo_root=repo, audit=audit, uhr=uhr, gpu=gpu, starter=starter, **kw)
    sp.test_audit, sp.test_starter = audit, starter
    return sp


def freigeben(sp, adapter, pfad, *, wurzel="repo", stufe=1, projekt=None, personenbezug=0, muster=None, gate="HG-test", mission="M-test"):
    b = {"adapter": adapter, "wurzel": wurzel, "pfad": pfad, "stufe": stufe, "projekt": projekt, "personenbezug": personenbezug}
    if muster:
        b["muster"] = muster
    return sp.quelle_freigeben(b, gate_id=gate, mission_id=mission)


def alle_freigeben(sp):
    return [freigeben(sp, "markdown", "docs"), freigeben(sp, "logbuch", "docs/LOGBUCH_AGENT_MANAGER.md"),
            freigeben(sp, "knowledge", "runtime_data/knowledge/records.jsonl", wurzel="projekt"),
            freigeben(sp, "arbeitsumfeld", "local_config/arbeitsumfeld/wissen.sqlite", wurzel="projekt"),
            freigeben(sp, "gateway", "local_config/gateway/wissen.sqlite#wissen", wurzel="projekt"),
            freigeben(sp, "gateway", "local_config/gateway/wissen.sqlite#eigene", wurzel="projekt", stufe=3, personenbezug=1)]
