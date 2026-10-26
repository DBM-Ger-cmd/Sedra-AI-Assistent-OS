r"""Die Nachtkette von A1 (Umzug nach A1, U2-11b, docs/UMSTIEG_A1_PLATTFORM_PLAN_2026-10-26.md Abschnitt 5a): Bau-Specs nacheinander über den einen Bauweg bauen, nachts, nur mit Freigabe.

    .venv\Scripts\python.exe benchmarks/night_chain.py <project_dir> --bis 2026-11-30 [--dry-run] [--once]
    optionen: --order <Datei> (Vorgabe <project>/local_config/nacht_auftraege.json)  --start-hour 22  --stop-hour 7  --min-free-ram-gb 14  --timeout-h 4

Was sie tut: Läuft nur, wenn (1) das Enddatum --bis nicht überschritten ist, (2) die Freigabedatei `<project>/local_config/nacht_frei.txt` existiert (ohne sie startet nie ein Lauf; Löschen der Datei hält die
Kette vor dem nächsten Auftrag an), (3) die Uhrzeit im Fenster liegt (Vorgabe 22:00 bis 07:00). Aufträge stehen in der Auftragsdatei (Liste von {"spec", "seed", "from_stage", "review", "rework"}, nur "spec" ist
Pflicht); jeder Auftrag wird höchstens einmal versucht (Ergebnis in summary.json) und nur gebaut, wenn der Spec-Stempel gültig ist (`spec_check.py <spec> --vm --project <project>` schreibt ihn). Gebaut wird mit
`devvm_build.py <project> --spec <spec> --profile standard` (Eigner `nachtkette`, `TESTLAB_PRIORITY=1`); die GPU-Lease ist solange reserviert (Priorität 1), wie die Kette Arbeit hat. Vor jedem Bau müssen
--min-free-ram-gb Arbeitsspeicher frei sein (das Hauptmodell hält rund 12 GB im RAM), sonst wartet die Kette. Ein fehlgeschlagener GPU-Canary stoppt die Kette. Nichts wird integriert: Ergebnisse stehen als
Kandidaten in runtime_data/devvm_candidates, Protokoll und Zusammenfassung in runtime_data/measurements/night_<datum>/.
--dry-run: zeigt, was sie täte (Freigabe, Fenster, Aufträge mit Stempelstatus, RAM, Lease), startet nichts und schreibt nichts. --once: ein Durchgang und Ende, statt bis zum Enddatum zu laufen."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
BENCH = RUNTIME / "benchmarks"
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(BENCH))

GATE = "nacht_frei.txt"
ORDER = "nacht_auftraege.json"
OWNER = "nachtkette"


def in_window(now, start_hour, stop_hour):
    """Liegt `now` im Fenster? Das Fenster darf über Mitternacht gehen (22 bis 7)."""
    h = now.hour
    return (start_hour <= h < stop_hour) if start_hour < stop_hour else (h >= start_hour or h < stop_hour)


def decide(now, bis, gate_exists, start_hour, stop_hour):
    """('ende' | 'warten' | 'arbeiten', Grund)."""
    if now.date() > bis:
        return "ende", "befristung_abgelaufen"
    if not gate_exists:
        return "ende", "nicht_freigegeben"
    if not in_window(now, start_hour, stop_hour):
        return "warten", "ausserhalb_des_fensters"
    return "arbeiten", ""


def read_order(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    return [i for i in data if isinstance(i, dict) and isinstance(i.get("spec"), str)] if isinstance(data, list) else []


def item_status(project, item, done):
    """(Status, Grund): 'bereit', 'erledigt', 'spec_fehlt', 'ohne_stempel'."""
    spec = item["spec"]
    if spec in done:
        return "erledigt", ""
    if not (BENCH / "devvm_specs" / f"{spec}.py").is_file():
        return "spec_fehlt", ""
    import spec_stamp
    reason, _ = spec_stamp.check(project, spec)
    return ("bereit", "") if reason is None else ("ohne_stempel", reason)


def build_argv(project, item, python):
    argv = [python, str(BENCH / "devvm_build.py"), str(project), "--spec", item["spec"], "--profile", "standard"]
    if item.get("rework") is not None:
        argv += ["--rework", str(int(item["rework"]))]
    if item.get("from_stage"):
        argv += ["--from-stage", str(item["from_stage"])]
    for key, flag in (("seed", "--seed"), ("review", "--review")):
        if item.get(key):
            argv += [flag, str(RUNTIME.parent / item[key])]
    return argv


def venv_python():
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        p = RUNTIME / rel
        if p.is_file():
            return str(p)
    return sys.executable


def lease_ro(project):
    """GPU-Lease rein lesend (SQLite immutable): None = frei oder verwaist, sonst Text. Öffnet TestLab nie (das migriert die Datenbank beim Öffnen)."""
    db = Path(project) / "runtime_data" / "testlab" / "testlab.db"
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect("file:" + db.as_posix() + "?mode=ro&immutable=1", uri=True)
        try:
            row = conn.execute("SELECT owner, purpose, heartbeat, ttl_s FROM lease WHERE name = 'gpu'").fetchone()
        finally:
            conn.close()
    except Exception as exc:
        return f"nicht lesbar ({str(exc)[:60]})"
    return f"{row[0]} ({row[1]})" if row and (time.time() - float(row[2])) <= float(row[3]) else None


def free_ram_gb():
    from kurzstart import ram
    return ram()[0]


def canary_failed():
    from guppi_runtime.models import gpu_canary
    state = gpu_canary.read_state()
    return state.get("passed") is False and state.get("result") != "port_in_use"


def real_runner(argv, env, log_path, timeout_s):
    """Startet den Bau, schreibt die Ausgabe ins Protokoll, gibt (Rückgabecode, Dauer s, letzte Zeilen) zurück."""
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        try:
            done = subprocess.run(argv, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout_s)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = -1
    tail = Path(log_path).read_text(encoding="utf-8", errors="replace").strip().splitlines()[-6:]
    return code, round(time.time() - t0), tail


def work_pass(project, order, args, *, now=datetime.datetime.now, runner=real_runner, canary=canary_failed, ram=free_ram_gb, sleep=time.sleep, say=print):
    """Ein Durchgang über die offenen Aufträge; (Liste der Zeilen, Stoppgrund oder None). Hält die Lease-Reservierung, solange gebaut wird."""
    from guppi_runtime.jobs.testlab import TestLab, default_path
    project = Path(project)
    out = project / "runtime_data" / "measurements" / f"night_{now().date().isoformat()}"
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"specs": {}}
    done = set(summary["specs"])
    rows, stopped = [], None
    gate = project / "local_config" / GATE
    python = venv_python()
    lab = TestLab(default_path(project))
    with lab.reserve(OWNER, "Nachtkette aus A1", priority=1):
        for item in order:
            state, _ = decide(now(), args.bis, gate.is_file(), args.start_hour, args.stop_hour)
            if state != "arbeiten":
                say(f"Kette hält an: {_}")
                break
            status, reason = item_status(project, item, done)
            if status != "bereit":
                if status in ("spec_fehlt", "ohne_stempel") and item["spec"] not in summary["specs"]:
                    say(f"  {item['spec']}: übersprungen ({status} {reason})")
                continue
            waited = 0
            while ram() < args.min_free_ram_gb and waited < 600:
                sleep(30)
                waited += 30
            if ram() < args.min_free_ram_gb:
                say(f"  {item['spec']}: zu wenig freier RAM, nicht gebaut")
                break
            env = {**os.environ, "TESTLAB_OWNER": OWNER, "TESTLAB_PRIORITY": "1", "PYTHONIOENCODING": "utf-8"}
            code, seconds, tail = runner(build_argv(project, item, python), env, out / f"build_{item['spec']}.log", int(args.timeout_h * 3600))
            row = {"spec": item["spec"], "returncode": code, "seconds": seconds, "finished": now().isoformat(timespec="seconds"), "tail": tail}
            summary["specs"][item["spec"]] = row
            summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
            rows.append(row)
            say(f"  {item['spec']}: Rückgabecode {code}, {seconds} s")
            if canary():
                stopped = "gpu_canary_fehlgeschlagen"
                summary["stopped"] = stopped
                summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
                say("GPU-CANARY FEHLGESCHLAGEN: Kette gestoppt (NVIDIA-Debugmodus an?)")
                break
    return rows, stopped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--bis", required=True, help="Enddatum JJJJ-MM-TT (die Kette läuft nie darüber hinaus)")
    ap.add_argument("--order", default=None)
    ap.add_argument("--start-hour", type=int, default=22)
    ap.add_argument("--stop-hour", type=int, default=7)
    ap.add_argument("--min-free-ram-gb", type=float, default=14.0)
    ap.add_argument("--timeout-h", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv)
    args.bis = datetime.date.fromisoformat(args.bis)
    project = Path(args.project)
    order = read_order(args.order or project / "local_config" / ORDER)
    now = datetime.datetime.now()
    gate = (project / "local_config" / GATE).is_file()
    state, why = decide(now, args.bis, gate, args.start_hour, args.stop_hour)
    if args.dry_run:
        summary_path = project / "runtime_data" / "measurements" / f"night_{now.date().isoformat()}" / "summary.json"
        done = set(json.loads(summary_path.read_text(encoding="utf-8"))["specs"]) if summary_path.exists() else set()
        print(f"Nachtkette (Trockenlauf): jetzt {now:%Y-%m-%d %H:%M}, Enddatum {args.bis}, Fenster {args.start_hour}:00 bis {args.stop_hour}:00")
        print(f"Freigabedatei {project / 'local_config' / GATE}: {'vorhanden' if gate else 'FEHLT (es startet nichts)'}")
        print(f"Entscheidung jetzt: {state}" + (f" ({why})" if why else ""))
        print(f"Projekt {project} | Python {venv_python()} | freier RAM {free_ram_gb()} GB (Bau ab {args.min_free_ram_gb} GB) | GPU-Lease: {lease_ro(project) or 'frei'}")
        print(f"Aufträge ({len(order)}):")
        for item in order:
            status, reason = item_status(project, item, done)
            print(f"  {item['spec']:30s} {status}{' ' + reason if reason else ''}")
            if status == "bereit":
                print("    würde starten: " + " ".join(build_argv(project, item, venv_python())))
        print("Nichts gestartet, nichts geschrieben.")
        return 0
    while True:
        state, why = decide(datetime.datetime.now(), args.bis, (project / "local_config" / GATE).is_file(), args.start_hour, args.stop_hour)
        if state == "ende":
            print(f"Nachtkette beendet: {why}", flush=True)
            return 0
        if state == "arbeiten":
            rows, stopped = work_pass(project, read_order(args.order or project / "local_config" / ORDER), args, say=lambda s: print(s, flush=True))
            if stopped:
                return 3
            if args.once:
                return 0
        elif args.once:
            print(f"Nachtkette: nichts zu tun ({why})", flush=True)
            return 0
        time.sleep(300 if state == "arbeiten" else 60)


if __name__ == "__main__":
    sys.exit(main())
