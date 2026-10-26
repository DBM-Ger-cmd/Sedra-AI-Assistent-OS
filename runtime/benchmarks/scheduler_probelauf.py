"""Probelauf des Modell-Schedulers (Spec 2, Checkliste OP-S2-18, Schritte 3 bis 7): Hilfe fuer den Captain am Rechner. Aendert NICHTS.

    python benchmarks/scheduler_probelauf.py vor          Vorpruefung (Schritt 1 und 3): Overlay, Lader, Lab, Prozesse, RAM, GPU, Tests-Hinweis
    python benchmarks/scheduler_probelauf.py beobachten   zeigt alle 3 s nur Aenderungen: SLOT_*- und RESOURCE_DENIED-Ereignisse im Audit, Lease des Labs,
                                                          Schlange der Uebergabe, llama-server mit -np, VRAM und RAM (Strg+C beendet, Zusammenfassung)
    python benchmarks/scheduler_probelauf.py schritte     druckt die Schritte 3 bis 7 mit dem erwarteten Ergebnis zum Abhaken

Optionen: --project <Ordner> (Standard workspace/GUPPI_OS im Paket), --sekunden N (Takt, Standard 3).
Es startet kein Modell, stoppt keinen Prozess und schreibt keine Datei ausser der Ausgabe.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
sys.path.insert(0, str(RUNTIME / "src"))

WATCH_PREFIXES = ("SLOT_", "RESOURCE_DENIED", "MODEL_SCHEDULER", "GPU_")
SCHRITTE = """Schritte 3 bis 7 (Spec 2, Checkliste OP-S2-18). Vorher: `vor` ohne Fehler. In einem zweiten Fenster `beobachten` laufen lassen.

 3. Neustart der Oberflaeche (START_SEDRA.bat --replace, dann Cockpit).
    erwartet: Leiste "Slots 0/0" (Modellserver aus), in der Werkstatt ist kein Modell geladen; `beobachten` zeigt noch keine SLOT_-Ereignisse.
 4. Erster Start: in der Werkstatt ein Rezept laden (Hilfsmodell zuerst, es ist kleiner). GPU-Zeitfenster, RAM-Schutz beachten.
    erwartet: SLOT_SERVER_STARTED (vram_gb, asked_by werkstatt), Lease "gpu" gehalten von sedra-scheduler, Leiste 0/N, genau ein llama-server mit -np N.
 5. Agentenlauf: einen Lauf starten, dann einen zweiten, dann einen dritten.
    erwartet: slot.changed binnen 3 s, Leiste 1/N, 2/N; der dritte wartet (kein_slot), die Seite "slots" zeigt die Schlange; Chat des Captains mit Prioritaet 7.
 6. Uebergabe: einen Benchmark starten, z. B. python benchmarks/context_ladder.py <Projekt> coder.llama_qwen35 --max 8192 --probes 1
    erwartet: Eintrag in der Uebergabe-Schlange, Scheduler auf drain, Server wird gestoppt, Benchmark bekommt die Lease; danach bleibt der Server aus.
    Abbruch jederzeit: Werkstatt "Entladen erzwingen". Die Frist drain_max_s (1800 s) nicht abwarten.
 7. Absturz: nur den eigenen llama-server beenden (PID aus der Ausgabe von `beobachten`, Zeile "llama-server PID").
    erwartet: SLOT_SERVER_EXITED, Leases unterbrochen, der naechste Lauf startet den Server neu (Canary); beim 4. Absturz in 10 Minuten: Entscheidung
    "Modellserver gesperrt, bitte pruefen" (SLOT_SERVER_GESPERRT).

Erste Stunde beobachten: kein SLOT_POLL_FAILED, keine slot_wait_timeout, Rest-VRAM nach dem Entladen nahe der Ausgangslage.
Rueckweg: workspace/GUPPI_OS/local_config/model_scheduler.yaml loeschen (oder enabled: false), Oberflaeche neu starten; haengt eine Lease: testlab_cli.py clean.
"""


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""


def vram():
    out = sh(["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"]).strip().splitlines()
    if not out:
        return None
    used, total, temp = [x.strip() for x in out[0].split(",")]
    return {"used_mib": int(used), "total_mib": int(total), "temp_c": int(temp)}


def free_ram_gb():
    out = sh(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"]).strip()
    return round(int(out) / 1048576, 1) if out.isdigit() else None


def servers():
    out = sh(["powershell", "-NoProfile", "-Command",
              "Get-CimInstance Win32_Process -Filter \"Name like 'llama-server%'\" | ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"])
    found = []
    for line in out.splitlines():
        pid, _, cmd = line.partition("|")
        if pid.strip().isdigit():
            parts = cmd.split()
            np_ = next((parts[i + 1] for i, p in enumerate(parts[:-1]) if p in ("-np", "--parallel")), "?")
            found.append({"pid": int(pid), "np": np_})
    return found


def project_dir(arg):
    return Path(arg) if arg else RUNTIME.parent / "workspace" / "GUPPI_OS"


def lab(project):
    from guppi_runtime.jobs.testlab import TestLab, default_path
    return TestLab(default_path(project))


def lab_state(project):
    """Read-only via a plain SQLite connection (immutable): the lab file is not migrated or locked by this tool."""
    import sqlite3
    path = project / "runtime_data" / "testlab" / "testlab.db"
    if not path.exists():
        return {"lease": None, "handover": 0}
    con = sqlite3.connect(f"file:{path.as_posix()}?immutable=1", uri=True)
    try:
        row = con.execute("SELECT owner, purpose, pid FROM lease WHERE name='gpu'").fetchone()
        try:
            handover = con.execute("SELECT COUNT(*) FROM handover_requests").fetchone()[0]
        except sqlite3.Error:
            handover = None
        return {"lease": {"owner": row[0], "purpose": row[1], "pid": row[2]} if row else None, "handover": handover}
    finally:
        con.close()


def cmd_vor(project):
    import yaml
    from guppi_runtime.jobs.model_scheduler_config import ModelSchedulerConfig
    bad = 0

    def line(ok, text):
        nonlocal bad
        print(("  ok   " if ok else "  FEHLT ") + text)
        bad += 0 if ok else 1

    overlay = project / "local_config" / "model_scheduler.yaml"
    try:
        cfg = ModelSchedulerConfig.load(RUNTIME / "config" / "model_scheduler.yaml", overlay)
        line(cfg.enabled, f"Lader nimmt Konfiguration an, enabled={cfg.enabled} (Overlay {'da' if overlay.exists() else 'fehlt'})")
    except ValueError as e:
        line(False, f"Lader lehnt ab: {e}")
    state = lab_state(project)
    line(state["lease"] is None, f"Lab: Lease gpu frei ({state['lease'] or 'frei'})")
    line(not state["handover"], f"Lab: keine wartenden Uebergaben ({state['handover']})")
    srv = servers()
    line(not srv, f"kein llama-server vorhanden ({srv or 'keiner'})")
    v = vram()
    line(v is not None and v["used_mib"] < 3000, f"GPU frei genug: {v}")
    ram = free_ram_gb()
    line(ram is not None and ram >= 13, f"freier RAM {ram} GB (Hauptmodell braucht rund 11 GB, Hilfsmodell rund 1,3 GB)")
    routing = yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]
    line(routing.get("enabled") is True, "role_routing enabled")
    print("Tests vorher: python benchmarks/run_tests.py scheduler desk orchestra uix   und   uix_check --shell paperclip --fixture orchestra")
    print("Ergebnis:", "alles bereit" if not bad else f"{bad} Punkt(e) pruefen, nicht starten")
    return 1 if bad else 0


def audit_path(project):
    return project / "runtime_data" / "audit" / "events.jsonl"


def cmd_beobachten(project, takt):
    path = audit_path(project)
    pos = path.stat().st_size if path.exists() else 0
    last = None
    counts = {}
    print(f"Beobachte {project} alle {takt} s. Strg+C beendet.")
    try:
        while True:
            now = {"lab": lab_state(project), "servers": servers(), "gpu": vram(), "ram_gb": free_ram_gb()}
            key = json.dumps([now["lab"], now["servers"]], sort_keys=True)
            stamp = time.strftime("%H:%M:%S")
            if key != last:
                last = key
                lease = now["lab"]["lease"]
                print(f"{stamp} Lease gpu: {lease['owner'] + ' / ' + lease['purpose'] if lease else 'frei'} | Uebergaben wartend: {now['lab']['handover']}")
                for s in now["servers"]:
                    print(f"{stamp}   llama-server PID {s['pid']} -np {s['np']}")
                if not now["servers"]:
                    print(f"{stamp}   kein llama-server")
            if path.exists() and path.stat().st_size > pos:
                with path.open("rb") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                for raw in chunk.splitlines():
                    try:
                        ev = json.loads(raw)
                    except ValueError:
                        continue
                    typ = ev.get("event_type", "")
                    if typ.startswith(WATCH_PREFIXES):
                        counts[typ] = counts.get(typ, 0) + 1
                        print(f"{stamp} AUDIT {typ} {json.dumps(ev.get('payload'), ensure_ascii=False)[:200]}")
                        if typ == "SLOT_POLL_FAILED":
                            print(f"{stamp}   !!! SLOT_POLL_FAILED darf nicht auftreten")
            g = now["gpu"]
            if g and g["temp_c"] >= 83:
                print(f"{stamp} !!! GPU {g['temp_c']} Grad, VRAM {g['used_mib']} MiB")
            time.sleep(takt)
    except KeyboardInterrupt:
        print("Zusammenfassung AUDIT:", counts or "keine SLOT_-Ereignisse")
        g, ram = vram(), free_ram_gb()
        print(f"Ende: VRAM {g['used_mib'] if g else '?'} MiB, freier RAM {ram} GB, Server {servers() or 'keine'}")
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modus", choices=("vor", "beobachten", "schritte"))
    ap.add_argument("--project", default=None)
    ap.add_argument("--sekunden", type=float, default=3.0)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    project = project_dir(args.project)
    if args.modus == "schritte":
        print(SCHRITTE)
        return 0
    if args.modus == "vor":
        return cmd_vor(project)
    return cmd_beobachten(project, args.sekunden)


if __name__ == "__main__":
    sys.exit(main())
