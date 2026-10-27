"""Langzeit-Nachtlauf: SEDRA informiert sich ueber 3D-Objekte (Agent Recherche, Orchestra) und erstellt dann OpenSCAD-Objekte (STL).

    python benchmarks/nachtlauf_3d.py                       Trockenlauf: prueft alles, startet nichts
    python benchmarks/nachtlauf_3d.py --go [--stunden 6]    der Lauf (Captain-Auftrag 27.10.2026: laeuft unbeaufsichtigt)

Ablauf: Vorpruefung -> Cockpit im Hintergrund (eigener Prozess, wird am Ende nach seiner eigenen PID beendet) -> Messung alle 30 s (VRAM, Temperatur, RAM) ->
Phase 1: je Quelle eine Recherche-Aufgabe an den Agenten `Recherche Betriebsstunde` (nur Hosts der Hostliste: raw.githubusercontent.com), jede Weckung wird vom Skript
einzeln freigegeben (Gate wake_agent, einmal, nur fuer Aufgaben, die dieses Skript angelegt hat) -> Phase 2: aus den Ergebnissen schreibt das lokale Modell OpenSCAD-Code
je Objekt (bis zu 3 Versuche, Fehlertext von OpenSCAD geht zurueck ans Modell) -> STL und Bericht. Die Agenten haben keine Dateiwerkzeuge: Der Code kommt vom Modell,
nicht vom Agenten; das steht im Bericht.

Sicherheit: Frist (--stunden), Stopp-Datei `STOP.txt` im Ausgabeordner, RAM-Schutz (unter 2 GB frei: Modell entladen und 5 Minuten Pause), Temperatur ab 84 Grad Pause,
hoechstens 40 Modellaufrufe je Objekt-Runde. Es werden keine Dateien ausserhalb des Ausgabeordners geschrieben, nichts geloescht, nichts committet oder gepusht, kein
Rezept und kein Schalter geaendert. Ausgabe: workspace/GUPPI_OS/runtime_data/nachtlauf_3d_<datum>/ (log.jsonl, messung.jsonl, berichte/, objekte/, bericht.md).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import messlauf_basis as basis                # gemeinsame Messbausteine (Skriptordner steht in sys.path)

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
ROOT = RUNTIME.parent
PROJECT = ROOT / "workspace" / "GUPPI_OS"
ARCH = ROOT / "architecture" / "GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
OPENSCAD = ROOT / "engines" / "tools" / "openscad-2021.01" / "openscad.exe"
RES_AGENT = "A-FDB69726"                      # Recherche Betriebsstunde (VERIFIED, eingestellt am 27.10.2026)
RECIPE = "coder.llama_qwen35"
RAW = "https://raw.githubusercontent.com/openscad/openscad/master/"
QUELLEN = [
    ("Grundkoerper und CSG", RAW + "examples/Basics/CSG.scad"),
    ("Extrusion", RAW + "examples/Basics/linear_extrude.scad"),
    ("Rotationskoerper", RAW + "examples/Basics/rotate_extrude.scad"),
    ("Listen und Funktionen", RAW + "examples/Functions/list_comprehensions.scad"),
    ("Projektion", RAW + "examples/Basics/projection.scad"),
    ("Text auf Koerpern", RAW + "examples/Basics/text_on_cube.scad"),
    ("Beispiel Gewinde und Bohrung", RAW + "examples/Old/example006.scad"),
    ("Beispiel Tragwerk", RAW + "examples/Old/example021.scad"),
    ("OpenSCAD Ueberblick", RAW + "README.md"),
    ("BOSL2 Bibliothek", "https://raw.githubusercontent.com/BelfrySCAD/BOSL2/master/README.md"),
]
OBJEKTE = [
    ("wuerfel_mit_kugelloch", "Ein Wuerfel mit 20 mm Kantenlaenge, aus dem eine Kugel mit 13 mm Durchmesser herausgeschnitten ist."),
    ("becher", "Ein zylindrischer Becher: Aussendurchmesser 60 mm, Hoehe 80 mm, Wandstaerke 3 mm, Boden 4 mm, ein Henkel aus einem halben Torus an der Seite."),
    ("vase", "Eine Vase als Rotationskoerper (rotate_extrude eines Profils): Hoehe 120 mm, unten 40 mm, in der Mitte 70 mm, oben 30 mm Durchmesser, 2 mm Wand."),
    ("stufenpyramide", "Eine Stufenpyramide aus fuenf quadratischen Platten (Kantenlaenge 50, 40, 30, 20, 10 mm, je 8 mm hoch), mittig gestapelt."),
    ("schraubenmutter", "Eine Sechskantmutter M8: Schluesselweite 13 mm, Hoehe 6,5 mm, Bohrung 8 mm, an beiden Seiten 0,5 mm Fase."),
    ("zahnscheibe", "Eine Zahnscheibe: Scheibe mit 40 mm Durchmesser, 5 mm dick, 16 rechteckige Zaehne (3 mm hoch, 4 mm breit) gleichmaessig am Rand, zentrale Bohrung 8 mm."),
    ("buecherstuetze", "Eine L-foermige Buecherstuetze: Grundplatte 80x100x4 mm, senkrechte Platte 80x100x4 mm, zwei dreieckige Streben 4 mm dick."),
    ("schachturm", "Ein Schach-Turm: Sockel Zylinder 30 mm Durchmesser, 8 mm hoch, Schaft 22 mm Durchmesser, 30 mm hoch, oben ein Kranz mit sechs Zinnen."),
]
SYSTEM = ("Du schreibst OpenSCAD-Code (Version 2021.01, keine Bibliotheken ausser den eingebauten Funktionen). Antworte NUR mit dem Code in einem Block ```openscad ... ``` "
          "und mit Kommentaren in Deutsch im Code. Der Code muss ohne Fehler zu einem einzigen soliden Koerper rendern (difference/union/rotate_extrude/linear_extrude/cube/cylinder/sphere/translate/rotate). "
          "Masse in Millimetern. Setze $fn = 48 fuer runde Formen. WICHTIG: In OpenSCAD speichert man Geometrie NICHT in Variablen (kein `x = cube(...)`, kein `x;` als Anweisung); "
          "Zahlen duerfen Variablen sein, Koerper schreibt man direkt hin oder packt sie in `module name() { ... }` und ruft `name();` auf. Es gibt kein `center=true` bei sphere. "
          "Beispiel: " + chr(10).join(["```openscad", "$fn = 48;", "kante = 20;", "difference() {", "    cube(kante, center = true);", "    sphere(r = 6.5);", "}", "```"]))


MAX_ABBRUECHE = 3       # Modellabbrueche je Objekt, danach weiter zum naechsten Objekt


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


class Run:
    def __init__(self, out: Path, hours: float):
        self.out = out
        self.deadline = time.time() + hours * 3600
        (out / "berichte").mkdir(parents=True, exist_ok=True)
        (out / "objekte").mkdir(parents=True, exist_ok=True)
        self.log_f = (out / "log.jsonl").open("a", encoding="utf-8")
        self.cockpit = None
        self.base = None
        self.token = None
        self.pause_until = 0.0
        self.metrics = []
        self.stop_metrics = threading.Event()
        self.approved = 0
        self.guard_hits = 0
        self.abort = None
        self.model_calls = 0

    def log(self, kind, **kw):
        row = {"t": now(), "kind": kind, **kw}
        self.log_f.write(json.dumps(row, ensure_ascii=False) + chr(10))
        self.log_f.flush()
        print(row["t"], kind, json.dumps(kw, ensure_ascii=False)[:200], flush=True)

    def stopped(self):
        return time.time() > self.deadline or (self.out / "STOP.txt").exists() or self.abort is not None

    # ---- Cockpit
    def start_cockpit(self):
        code = ("import sys; sys.path.insert(0,'src'); from guppi_runtime.uix_server import main; "
                f"raise SystemExit(main(['--root',r'{PROJECT}','--architecture',r'{ARCH}']))")
        log = (self.out / "cockpit.log").open("w", encoding="utf-8")
        self.cockpit = subprocess.Popen([sys.executable, "-I", "-B", "-c", code], cwd=str(RUNTIME), stdout=log, stderr=subprocess.STDOUT)
        for _ in range(120):
            time.sleep(1)
            text = (self.out / "cockpit.log").read_text(encoding="utf-8", errors="replace")
            m = re.search(r"http://127\.0\.0\.1:(\d+)/#(\S+)", text)
            if m:
                self.base, self.token = f"http://127.0.0.1:{m.group(1)}", m.group(2)
                self.log("cockpit", pid=self.cockpit.pid, port=m.group(1))
                return
            if self.cockpit.poll() is not None:
                break
        raise RuntimeError("cockpit_not_started")

    def call(self, path, payload=None, timeout=900):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers={"X-GUPPI-Token": self.token, "Content-Type": "application/json", "Origin": self.base})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            return {"http": exc.code, "body": exc.read().decode("utf-8", "replace")[:300]}

    def stop_cockpit(self):
        try:
            if self.base:
                self.call("/api/model/unload", {"erzwingen": True}, timeout=120)
        except Exception as exc:
            self.log("unload_failed", error=type(exc).__name__)
        if self.cockpit is not None and self.cockpit.poll() is None:
            self.cockpit.terminate()
            try:
                self.cockpit.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.cockpit.kill()
            self.log("cockpit_beendet", pid=self.cockpit.pid)

    # ---- Messung und Schutz
    def sampler(self):
        low = 0
        while not self.stop_metrics.wait(30):
            gpu, ram = basis.vram(), basis.free_ram_gb()
            if gpu is None or ram is None:
                continue
            row = {"t": now(), "vram_mib": gpu["used_mib"], "temp_c": gpu["temp_c"], "ram_free_gb": ram}
            row["top_prozesse"] = basis.top_prozesse(6)
            row["cockpit_pid"] = self.cockpit.pid if self.cockpit is not None else None
            self.metrics.append(row)
            with (self.out / "messung.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + chr(10))
            low = low + 1 if row["ram_free_gb"] < 2.0 else 0
            if low >= 2 and time.time() > self.pause_until:
                self.log("ram_schutz", ram_free_gb=row["ram_free_gb"])
                try:
                    self.call("/api/model/unload", {"erzwingen": True}, timeout=120)
                except Exception:
                    pass
                self.pause_until = time.time() + 300
                low = 0
                self.guard_hits += 1
                if self.guard_hits >= 2:
                    self.abort = "ram_schutz_zweimal"
                    self.log("abbruch_ram", grund="der RAM-Schutz musste zweimal entladen; Lauf wird beendet statt zu warten")
            if row["temp_c"] >= 84 and time.time() > self.pause_until:
                self.log("temperatur_pause", temp_c=row["temp_c"])
                self.pause_until = time.time() + 300

    def wait_pause(self):
        while time.time() < self.pause_until and not self.stopped():
            time.sleep(5)

    # ---- Phase 1: Recherche ueber den Agenten
    def run_failed(self, task):
        """Fehlercode des gescheiterten Agentenlaufs zu dieser Aufgabe (aus dem Audit), sonst None."""
        path = PROJECT / "runtime_data" / "audit" / "events.jsonl"
        try:
            with open(path, "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 400_000))
                lines = f.read().decode("utf-8", "replace").splitlines()
        except OSError:
            return None
        for line in reversed(lines):
            if task in line and '"ORC_RUN_FAILED"' in line:
                try:
                    return json.loads(line)["payload"].get("code") or "unbekannt"
                except ValueError:
                    return "unbekannt"
        return None

    def research(self, title, url):
        r = self.call("/api/actions", {"type": "issue", "verb": "anlegen", "args": {
            "titel": f"3D-Recherche: {title}",
            "beschreibung": (f"Lies {url} und fasse in hoechstens fuenf Saetzen zusammen, welche Formen, Befehle oder Techniken fuer 3D-Objekte dort gezeigt werden "
                             "und wie man sie benutzt. Trage im Feld lesen als einziges Element genau diese Adresse ein, vollstaendig mit https://, "
                             f"also lesen = [\"{url}\"]."),
            "bearbeiter": RES_AGENT}})
        task = (r.get("result") or {}).get("issue")
        if not task:
            self.log("recherche_anlegen_fehlgeschlagen", title=title, antwort=json.dumps(r)[:200])
            return None
        self.log("recherche_aufgabe", task=task, title=title)
        end = time.time() + 900
        approved_ids = set()
        db = f"file:{(PROJECT / 'runtime_data' / 'orchestra' / 'orchestra.db').as_posix()}?mode=ro"
        while time.time() < end and not self.stopped():
            con = sqlite3.connect(db, uri=True)
            try:
                rows = con.execute("select request_mission_id from wakeups where task_id=? and outcome='antrag' and request_mission_id is not null", (task,)).fetchall()
                comment = con.execute("select text from comments where task_id=? and author_kind='agent' order by id desc limit 1", (task,)).fetchone()
                err = con.execute("select text from comments where task_id=? and author_kind='system' order by id desc limit 1", (task,)).fetchone()
            finally:
                con.close()
            for (rid,) in rows:
                if rid not in approved_ids:
                    res = self.call("/api/decisions/answer", {"id": "request:" + rid, "way": "freigeben_und_anwenden"})
                    approved_ids.add(rid)
                    self.approved += 1
                    self.log("lauf_freigegeben", task=task, antwort=json.dumps(res)[:140])
            if comment:
                self.log("recherche_ergebnis", task=task, zeichen=len(comment[0]))
                (self.out / "berichte" / f"{task}.txt").write_text(f"Quelle: {url}\nThema: {title}\n\n{comment[0]}\n", encoding="utf-8")
                return comment[0]
            if err and "research_invalid" in err[0] and approved_ids:
                self.log("recherche_abgelehnt", task=task, grund=err[0][:80])
                return None
            code = self.run_failed(task)
            if code:                                   # der Lauf ist gescheitert: nicht weiter warten (Fehler im Audit: ORC_RUN_FAILED)
                self.log("recherche_abgelehnt", task=task, grund=code)
                return None
            time.sleep(5)
        self.log("recherche_zeit", task=task)
        return None

    # ---- Phase 2: Objekte
    def ask_model(self, messages, max_tokens=1800):
        self.model_calls += 1
        body = {"model": "x", "messages": messages, "temperature": 0.3, "max_tokens": max_tokens}
        req = urllib.request.Request("http://127.0.0.1:8089/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]

    def ensure_model(self):
        for _ in range(3):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8089/health", timeout=5) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            res = self.call("/api/model/load", {"recipe_id": RECIPE}, timeout=600)
            self.log("modell_laden", antwort=json.dumps(res)[:120])
            time.sleep(3)
        return False

    def render(self, scad: Path, stl: Path):
        p = subprocess.run([str(OPENSCAD), "-o", str(stl), str(scad)], capture_output=True, text=True, timeout=300)
        return p.returncode, (p.stderr or "")[-1200:]

    def make_object(self, name, spec, wissen):
        target = self.out / "objekte"
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Aus der Recherche (Auszug):\n{wissen[:3500]}\n\nAufgabe: {spec}\nSchreibe den OpenSCAD-Code."}]
        attempt, abbrueche = 0, 0           # nur eine Antwort des Modells zaehlt als Versuch; ein Modellabbruch (Treiber-Reset) nicht
        while attempt < 4:
            if self.stopped():
                return {"name": name, "ok": False, "versuche": attempt, "grund": "gestoppt"}
            self.wait_pause()
            if not self.ensure_model():
                return {"name": name, "ok": False, "versuche": attempt, "grund": "kein_modell"}
            try:
                text = self.ask_model(messages)
            except Exception as exc:
                abbrueche += 1
                self.log("modellaufruf_fehler", objekt=name, fehler=type(exc).__name__, abbrueche=abbrueche)
                if abbrueche >= MAX_ABBRUECHE:
                    return {"name": name, "ok": False, "versuche": attempt, "grund": "modell_abbruch"}
                time.sleep(20)
                continue
            attempt += 1
            m = re.search(r"```(?:openscad|scad)?\s*(.*?)```", text, re.S)
            code = (m.group(1) if m else text).strip()
            scad, stl = target / f"{name}.scad", target / f"{name}.stl"
            scad.write_text(code + chr(10), encoding="utf-8")
            try:
                rc, err = self.render(scad, stl)
            except subprocess.TimeoutExpired:
                rc, err = 124, "Zeitueberschreitung beim Rendern"
            if rc == 0 and stl.exists() and stl.stat().st_size > 200:
                tris = stl.read_text(encoding="utf-8", errors="ignore").count("facet normal")
                self.log("objekt_ok", objekt=name, versuch=attempt, stl_bytes=stl.stat().st_size, dreiecke=tris)
                return {"name": name, "ok": True, "versuche": attempt, "stl_bytes": stl.stat().st_size, "dreiecke": tris}
            self.log("objekt_fehler", objekt=name, versuch=attempt, rc=rc, fehler=err[-200:])
            messages += [{"role": "assistant", "content": text}, {"role": "user", "content": f"OpenSCAD meldet einen Fehler:\n{err}\nKorrigiere den Code (Geometrie nie in Variablen speichern, kein center bei sphere) und antworte wieder nur mit dem Code-Block."}]
        return {"name": name, "ok": False, "versuche": attempt, "grund": "render_fehler"}


def preflight():
    problems = []
    if not OPENSCAD.exists():
        problems.append("OpenSCAD fehlt")
    lease = PROJECT / "runtime_data" / "testlab" / "testlab.db"
    if lease.exists():
        con = sqlite3.connect(f"file:{lease.as_posix()}?immutable=1", uri=True)
        try:
            if con.execute("select count(*) from lease where name='gpu'").fetchone()[0]:
                problems.append("GPU-Lease belegt")
        finally:
            con.close()
    gb = subprocess.run(["powershell", "-NoProfile", "-Command", "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)"], capture_output=True, text=True).stdout.strip().replace(",", ".")
    try:
        if float(gb) < 10.0:
            problems.append(f"freier RAM nur {gb} GB (mindestens 10)")
    except ValueError:
        problems.append("RAM nicht lesbar")
    if basis.servers():
        problems.append("ein llama-server laeuft schon")
    return problems, gb


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--stunden", type=float, default=6.0)
    ap.add_argument("--kurz", action="store_true", help="Kurzlauf (3 Quellen, 2 Objekte) zum Beobachten tagsueber; setzt --stunden auf hoechstens 0,6")
    ap.add_argument("--probe", action="store_true", help="nur eine Quelle und ein Objekt (Funktionstest vor dem Nachtlauf)")
    args = ap.parse_args(argv)
    global QUELLEN, OBJEKTE
    if args.probe:
        QUELLEN, OBJEKTE = QUELLEN[:1], OBJEKTE[:1]
    if args.kurz:
        QUELLEN, OBJEKTE = QUELLEN[:3], OBJEKTE[:2]
        args.stunden = min(args.stunden, 0.6)
    problems, gb = preflight()
    print("Vorpruefung:", "ok" if not problems else problems, "| freier RAM", gb, "GB")
    if problems:
        return 3
    if not args.go:
        print(f"Trockenlauf: {len(QUELLEN)} Quellen, {len(OBJEKTE)} Objekte, Frist {args.stunden} h; nichts gestartet.")
        return 0
    out = PROJECT / "runtime_data" / f"nachtlauf_3d_{time.strftime('%Y-%m-%d_%H%M')}"
    run = Run(out, args.stunden)
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)       # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: kein Ruhezustand, solange dieses Skript laeuft
    results, wissen_teile = [], []
    fehlschlaege = 0
    try:
        run.log("start", stunden=args.stunden, ausgabe=str(out))
        run.start_cockpit()
        threading.Thread(target=run.sampler, daemon=True).start()
        for title, url in QUELLEN:
            if run.stopped():
                break
            run.wait_pause()
            text = run.research(title, url)
            if not text and not run.stopped():
                run.log("recherche_zweiter_versuch", title=title)       # das Hilfsmodell nennt die Adresse manchmal falsch (research_invalid:urls)
                text = run.research(title, url)
            if text:
                wissen_teile.append(f"[{title}] {text}")
                fehlschlaege = 0
            else:
                fehlschlaege += 1
                if fehlschlaege >= 3:           # drei Quellen hintereinander ohne Ergebnis: die Recherche selbst ist kaputt, nicht die Quelle
                    run.log("recherche_abbruch", grund="3 Quellen in Folge ohne Ergebnis")
                    break
        run.log("recherche_fertig", quellen_ok=len(wissen_teile), von=len(QUELLEN))
        wissen = chr(10).join(wissen_teile) or "(keine Recherche-Ergebnisse; nur Grundwissen des Modells)"
        for name, spec in OBJEKTE:
            if run.stopped():
                break
            results.append(run.make_object(name, spec, wissen))
    except Exception as exc:
        run.log("abbruch", fehler=f"{type(exc).__name__}: {exc}"[:300])
    finally:
        run.stop_metrics.set()
        run.stop_cockpit()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        ok = [r for r in results if r.get("ok")]
        ram = [m["ram_free_gb"] for m in run.metrics] or [0]
        lines = ["# Nachtlauf 3D (SEDRA)", "", f"Start/Ende: {out.name}, Frist {args.stunden} h", "",
                 f"- Recherche-Aufgaben beim Agenten: {len(QUELLEN)}, mit Ergebnis: {len(wissen_teile)} (Berichte in berichte/)",
                 f"- Freigegebene Laeufe (einzeln durch das Skript): {run.approved}",
                 f"- Modellaufrufe fuer Objekte: {run.model_calls}", f"- Objekte erstellt: {len(ok)} von {len(OBJEKTE)}",
                 f"- VRAM-Spitze {max([m['vram_mib'] for m in run.metrics] or [0])} MiB, Temperatur hoechstens {max([m['temp_c'] for m in run.metrics] or [0])} Grad, freier RAM mindestens {min(ram)} GB", "",
                 f"- Abbruch durch Schutz: {run.abort or 'nein'}; RAM-Schutz hat {run.guard_hits} Mal entladen", "",
                 "Hinweis: Die Agenten haben keine Dateiwerkzeuge; den OpenSCAD-Code hat das lokale Modell aus den Rechercheergebnissen geschrieben.", "",
                 "| Objekt | OK | Versuche | STL (Bytes) | Dreiecke | Grund |", "| --- | --- | --- | --- | --- | --- |"]
        for r in results:
            lines.append(f"| {r['name']} | {'ja' if r.get('ok') else 'nein'} | {r.get('versuche')} | {r.get('stl_bytes', '')} | {r.get('dreiecke', '')} | {r.get('grund', '')} |")
        (out / "bericht.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        run.log("ende", objekte_ok=len(ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
