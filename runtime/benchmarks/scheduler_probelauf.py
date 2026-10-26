"""Probelauf des Modell-Schedulers (Spec 2, Checkliste OP-S2-18, Schritte 3 bis 7): Hilfe fuer den Captain am Rechner. Aendert NICHTS.

    python benchmarks/scheduler_probelauf.py vor          Vorpruefung (Schritt 1 und 3): Overlay, Lader, Lab, Prozesse, RAM, GPU, Tests-Hinweis
    python benchmarks/scheduler_probelauf.py beobachten   zeigt alle 3 s nur Aenderungen: SLOT_*- und RESOURCE_DENIED-Ereignisse im Audit, Lease des Labs,
                                                          Schlange der Uebergabe, llama-server mit -np, VRAM und RAM (Strg+C beendet, Zusammenfassung)
    python benchmarks/scheduler_probelauf.py schritte     druckt die Schritte 3 bis 7 mit dem erwarteten Ergebnis zum Abhaken
    python benchmarks/scheduler_probelauf.py stunde       die erste Betriebsstunde (--minuten 60): misst alle 10 s (VRAM, Temperatur, freier RAM, llama-server, Lease, Aufgaben),
                                                          zaehlt SLOT_*/JOB_*-Ereignisse des Audits, schreibt jede Messung sofort in
                                                          runtime_data/measurements/beobachtung_<datum>.jsonl und druckt am Ende den Bericht mit Bestanden/Nicht bestanden

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


def task_counts(project):
    import sqlite3
    path = project / "runtime_data" / "orchestra" / "orchestra.db"
    if not path.exists():
        return {}
    con = sqlite3.connect(f"file:{path.as_posix()}?immutable=1", uri=True)
    try:
        return dict(con.execute("SELECT state, COUNT(*) FROM tasks GROUP BY state").fetchall())
    except sqlite3.Error:
        return {}
    finally:
        con.close()


def cmd_stunde(project, minuten, takt=10.0):
    """Die erste Betriebsstunde mit echten Aufgaben (Spec 2 OP-S2-18): nur messen und zaehlen, nichts aendern."""
    path = audit_path(project)
    pos = path.stat().st_size if path.exists() else 0
    out_dir = project / "runtime_data" / "measurements"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"beobachtung_{time.strftime('%Y-%m-%d_%H%M')}.jsonl"
    start = time.time()
    tasks_start = task_counts(project)
    counts, failed_classes = {}, {}
    vram_max = temp_max = 0
    ram_min = None
    max_servers = max_np = 0
    server_seen_s = 0.0
    samples = 0
    print(f"Beobachte {minuten} min, Takt {takt:.0f} s, schreibe {out_path}. Strg+C beendet frueher mit Bericht.")
    try:
        with out_path.open("a", encoding="utf-8") as sink:
            while time.time() - start < minuten * 60:
                servers_now = servers()
                g, ram = vram(), free_ram_gb()
                lab = lab_state(project)
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
                        if typ.startswith(("SLOT_", "JOB_", "RESOURCE_", "ORCHESTRA")):
                            counts[typ] = counts.get(typ, 0) + 1
                            payload = ev.get("payload") or {}
                            if typ == "JOB_FAILED":
                                cls = payload.get("failure_class", "?")
                                failed_classes[cls] = failed_classes.get(cls, 0) + 1
                            if typ.startswith("SLOT_") and typ not in ("SLOT_SERVER_STARTED", "SLOT_SERVER_STOPPED"):
                                print(f"{time.strftime('%H:%M:%S')} AUDIT {typ} {json.dumps(payload, ensure_ascii=False)[:160]}", flush=True)
                if g:
                    vram_max, temp_max = max(vram_max, g["used_mib"]), max(temp_max, g["temp_c"])
                ram_min = ram if ram_min is None else (min(ram_min, ram) if ram is not None else ram_min)
                max_servers = max(max_servers, len(servers_now))
                for srv in servers_now:
                    try:
                        max_np = max(max_np, int(srv["np"]))
                    except ValueError:
                        pass
                server_seen_s += takt if servers_now else 0
                samples += 1
                row = {"t": time.strftime("%H:%M:%S"), "vram_mib": g and g["used_mib"], "temp_c": g and g["temp_c"], "ram_free_gb": ram,
                       "servers": [s["pid"] for s in servers_now], "np": [s["np"] for s in servers_now], "lease": lab["lease"] and lab["lease"]["owner"],
                       "handover": lab["handover"], "tasks": task_counts(project)}
                sink.write(json.dumps(row, ensure_ascii=False) + chr(10))
                sink.flush()
                time.sleep(takt)
    except KeyboardInterrupt:
        pass
    minutes = (time.time() - start) / 60
    tasks_end = task_counts(project)
    verdict = []

    def check(ok, text):
        verdict.append((ok, text))

    check(counts.get("SLOT_POLL_FAILED", 0) == 0, f"kein SLOT_POLL_FAILED ({counts.get('SLOT_POLL_FAILED', 0)})")
    check(counts.get("SLOT_SERVER_GESPERRT", 0) == 0, f"Server nie gesperrt ({counts.get('SLOT_SERVER_GESPERRT', 0)})")
    check(counts.get("SLOT_SERVER_GARBAGE", 0) == 0, f"keine Ausgabe-Muellmeldung ({counts.get('SLOT_SERVER_GARBAGE', 0)})")
    check(counts.get("SLOT_GPU_LEASE_LOST", 0) == 0, f"keine verlorene Lease ({counts.get('SLOT_GPU_LEASE_LOST', 0)})")
    check(counts.get("SLOT_SERVER_EXITED", 0) == 0, f"kein unerwarteter Serverabsturz ({counts.get('SLOT_SERVER_EXITED', 0)})")
    check(max_servers <= 1, f"nie mehr als ein llama-server gleichzeitig ({max_servers})")
    check(vram_max <= 11776, f"VRAM-Spitze unter 11,5 GiB ({vram_max} MiB)")
    check(temp_max < 85, f"Temperatur unter 85 Grad ({temp_max})")
    check(ram_min is None or ram_min >= 2.0, f"freier RAM nie unter 2 GB ({ram_min})")
    check(counts.get("RESOURCE_DENIED", 0) == 0, f"keine abgelehnte Reservierung ({counts.get('RESOURCE_DENIED', 0)})")
    check(not failed_classes, f"keine fehlgeschlagenen Jobs ({failed_classes or 'keine'})")
    check(counts.get("JOB_CREATED", 0) > 0, f"es gab Aufgaben der Agenten ({counts.get('JOB_CREATED', 0)} Jobs)")
    print(f"--- Bericht der Beobachtung ({minutes:.0f} min, {samples} Messungen) ---")
    print(f"Server sichtbar: {server_seen_s / 60:.0f} min, groesstes -np: {max_np}, Aufgaben vorher {tasks_start} nachher {tasks_end}")
    print("Ereignisse:", {k: v for k, v in sorted(counts.items()) if k.startswith(("SLOT_", "RESOURCE_", "JOB_FAILED", "JOB_CREATED", "JOB_PARKED"))})
    for ok, text in verdict:
        print(("  bestanden   " if ok else "  NICHT BESTANDEN ") + text)
    bad = [t for ok, t in verdict if not ok]
    print("Ergebnis:", "bestanden" if not bad else f"{len(bad)} Punkt(e) zu pruefen")
    print("Messreihe:", out_path)
    return 1 if bad else 0


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
    ap.add_argument("modus", choices=("vor", "beobachten", "schritte", "stunde"))
    ap.add_argument("--project", default=None)
    ap.add_argument("--sekunden", type=float, default=3.0)
    ap.add_argument("--minuten", type=float, default=60.0)
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
    if args.modus == "stunde":
        return cmd_stunde(project, args.minuten)
    return cmd_beobachten(project, args.sekunden)


if __name__ == "__main__":
    sys.exit(main())
