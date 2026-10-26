"""Agentenlauf-Probe des Modell-Schedulers (Spec 2, Checkliste OP-S2-18, Schritt 5): mehrere Agentenlaeufe gleichzeitig auf dem Server, 2 Slots belegt.

    python benchmarks/agentenlauf_probe.py                    Trockenlauf: baut das Wegwerf-Projekt und die Oberflaeche, prueft alles, laedt KEIN Modell
    python benchmarks/agentenlauf_probe.py --go               der Lauf (braucht GPU-Zeitfenster und den Start des Captains)
    Optionen: --agents 3 (Zahl der Agenten/Aufgaben, 2 bis 6)  --workers 3 (Zahl der Pool-Threads, nicht mehr als Agenten) 
              --timeout 900 (Sekunden)  --live-project <Ordner> (woher local_config kommt, Standard workspace/GUPPI_OS)

Was es tut: legt in einem WEGWERF-Projekt (Temp-Ordner, wird am Ende geloescht) eine Orchestra-Datenbank mit N Agenten und je einer Aufgabe an, kopiert nur die
Konfiguration (role_routing, routing_profiles, switches, model_scheduler) aus dem Live-Projekt, startet den Worker-Pool des Supervisors und die Laeufe (`start_run`)
und schreibt alle 2 s die Belegung der Slots (Scheduler-Sicht). Am Ende: hoechste gleichzeitige Belegung, Zustand der Aufgaben, Audit SLOT_*.
Es fasst weder die Live-Datenbank noch die Live-Lease an (eigenes Lab im Temp-Projekt: das Live-Lab muss trotzdem frei sein, weil die GPU geteilt wird;
das prueft das Skript). Der Server wird am Ende entladen. Rueckweg bei Abbruch: das Skript beendet nur den Server, den der Scheduler selbst gestartet hat.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
sys.path.insert(0, str(RUNTIME / "src"))
ARCH = RUNTIME.parent / "architecture" / "GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
COPY = ("role_routing.yaml", "routing_profiles.yaml", "switches.yaml", "model_scheduler.yaml")
NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_project(live: Path, agents: int) -> Path:
    import yaml
    project = Path(tempfile.mkdtemp(prefix="sedra-agentenprobe-")) / "project"
    (project / "local_config").mkdir(parents=True)
    for name in COPY:
        source = live / "local_config" / name
        if source.exists():
            shutil.copy2(source, project / "local_config" / name)
    switches_path = project / "local_config" / "switches.yaml"
    raw = yaml.safe_load(switches_path.read_text(encoding="utf-8")) if switches_path.exists() else {}
    raw = raw or {}
    raw.setdefault("switches", {}).setdefault("orchestra", {})["enabled"] = True
    raw["switches"].setdefault("job_supervisor", {})["enabled"] = True
    switches_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    overlay = project / "local_config" / "model_scheduler.yaml"
    if not overlay.exists():
        overlay.write_text("model_scheduler:\n  enabled: true\n", encoding="utf-8")
    from guppi_runtime.orchestra.store import open_db
    conn = open_db(project / "runtime_data" / "orchestra" / "orchestra.db")
    try:
        now = NOW()
        conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, can_delegate, created_at, updated_at)"
                     " VALUES ('A-UA', 'I-0', 'unterarbeiter', 'Unterarbeiter', 'Leitung', NULL, 'aktiv', 4, 1, ?, ?)", (now, now))
        for n in range(1, agents + 1):
            conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at)"
                         " VALUES (?, ?, 'coder', ?, 'coder', 'A-UA', 'aktiv', 2, ?, ?)", (f"A-P{n}", f"I-P{n}", f"Probe {n}", now, now))
    finally:
        conn.commit()
        conn.close()
    return project


def live_lab_free(live: Path):
    path = live / "runtime_data" / "testlab" / "testlab.db"
    if not path.exists():
        return True
    con = sqlite3.connect(f"file:{path.as_posix()}?immutable=1", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM lease WHERE name='gpu'").fetchone()[0] == 0
    finally:
        con.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--agents", type=int, default=3)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--live-project", default=str(RUNTIME.parent / "workspace" / "GUPPI_OS"))
    args = ap.parse_args(argv)
    if not 2 <= args.agents <= 6:
        print("--agents 2 bis 6"); return 2
    workers = args.workers or args.agents
    live = Path(args.live_project)
    print(f"Live-Lab frei: {live_lab_free(live)}")
    if not live_lab_free(live):
        print("Abbruch: das Live-Lab haelt die GPU-Lease (ein Lauf oder die Oberflaeche). Erst freigeben."); return 3
    project = build_project(live, args.agents)
    print(f"Wegwerf-Projekt: {project}")
    from guppi_runtime.uix_server import UIXHub
    from guppi_runtime.desk import orchestra_runner
    from guppi_runtime.orchestra import board, heartbeat
    hub = pool = None
    try:
        hub = UIXHub(project, ARCH)
        orch = hub.runtime.orchestra
        sup = orch.supervisor
        sched = hub._scheduler()
        print(f"Supervisor enabled={getattr(sup, 'enabled', None)} Scheduler an={sched is not None} Worker-Grenze vorher={sup._worker_limit() if sup else None}")
        if sup is None or sched is None:
            print("Abbruch: Supervisor oder Scheduler nicht an im Wegwerf-Projekt."); return 4
        sup.config.workers = workers
        print(f"Worker-Grenze jetzt: {sup._worker_limit()} (nur fuer diesen Probelauf im Speicher gesetzt, die Datei bleibt)")
        for n in range(1, args.agents + 1):
            board.create(orch.conn, dict(title=f"Probe {n}: Kurzantwort", description=f"Beantworte in zwei Saetzen: Was ist ein Fahrradgetriebe? (Probe {n})",
                                         assignee=f"A-P{n}", origin="captain"), NOW(), "captain")
        tasks = [dict(r) for r in orch.conn.execute("SELECT * FROM tasks ORDER BY id")]
        print(f"{len(tasks)} Aufgaben angelegt; Das Rezept waehlt die Rollen-Aufloesung (role_routing, aktives Profil) - ob Haupt- oder Hilfsmodell, zeigt die Ausgabe mit --go.")
        if not args.go:
            print("Trockenlauf beendet: es wurde kein Modell geladen und kein Lauf gestartet. Mit --go ausfuehren (GPU-Zeitfenster, RAM >= 13 GB frei)."); return 0
        pool = orchestra_runner.start_pool(hub, orch, idle_sleep_s=0.5)
        print(f"Pool gestartet: {len(pool.workers)} Worker")
        for task in tasks:
            agent = dict(orch.conn.execute("SELECT * FROM agents WHERE id = ?", (task["assignee"],)).fetchone())
            wid = heartbeat.enqueue(orch.conn, agent["id"], "zugewiesen", f"assign:{task['id']}:{task['revision']}", NOW(), 0, task_id=task["id"])
            wake = dict(orch.conn.execute("SELECT * FROM wakeups WHERE id = ?", (wid,)).fetchone())
            orchestra_runner.start_run(orch, agent, dict(orch.conn.execute("SELECT * FROM tasks WHERE id = ?", (task["id"],)).fetchone()), wake, "einmal")
        end = time.time() + args.timeout
        maxheld, last = 0, None
        while time.time() < end:
            hub.scheduler_poll()
            view = hub.slots_view() or {}
            held, queue = len(view.get("belegt") or []), len(view.get("schlange") or [])
            maxheld = max(maxheld, held)
            state = (held, queue, (view.get("server") or {}).get("state"))
            if state != last:
                last = state
                print(f"{time.strftime('%H:%M:%S')} Slots belegt {held}/{view.get('gesamt')} wartend {queue} Server {state[2]}", flush=True)
            states = [r[0] for r in orch.conn.execute("SELECT state FROM tasks")]
            if all(s not in ("zugewiesen", "in_arbeit", "offen") for s in states):
                break
            time.sleep(2)
        states = {r["id"]: r["state"] for r in orch.conn.execute("SELECT id, state FROM tasks")}
        print(f"Hoechste gleichzeitige Belegung: {maxheld} Slot(s); Aufgaben: {states}")
        print("Ergebnis:", "2 Slots gleichzeitig belegt" if maxheld >= 2 else "nie mehr als 1 Slot belegt (siehe Ausgabe oben)")
        return 0
    finally:
        try:
            if pool is not None:
                pool.stop()
            if hub is not None:
                try:
                    hub.unload_model({})
                except Exception as exc:
                    print("Entladen:", type(exc).__name__, exc)
                hub.close()
        finally:
            shutil.rmtree(project.parent, ignore_errors=True)
            print("Wegwerf-Projekt entfernt.")


if __name__ == "__main__":
    sys.exit(main())
