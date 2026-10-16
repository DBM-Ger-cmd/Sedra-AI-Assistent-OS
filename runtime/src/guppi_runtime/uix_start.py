"""The one standard start of GUPPI's UIX (all START_*.bat call this): check what is already running, clear leftovers, then serve.

1. A second UIX is not started next to a running one (two servers fight over the GPU lease and the llama-server port).
2. A GUPPI llama-server whose starter is gone (UIX killed, window crashed) is a leftover: it holds the VRAM and the UIX does not own it,
   so every model load fails with hardware_pressure. Such leftovers are stopped; a server with a live starter (a benchmark run) is only reported.
3. The GPU lease holder is shown, so a busy card is explained before the first model load fails."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import gpu_preflight
from .uix_server import serve


def process_rows(run=subprocess.run, platform=sys.platform):
    """The python/llama-server processes of this PC. Only Windows has the PowerShell inventory; on macOS and Linux the start does not
    know other processes and therefore neither stops leftovers nor refuses a second UIX (2026-10-14: start for Mac users)."""
    if platform != "win32":
        return []
    text = gpu_preflight._powershell(
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'llama-server.exe','python.exe','pythonw.exe' } | "
        "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress", run)
    data = json.loads(text) if text else []
    return data if isinstance(data, list) else [data]


def other_uix_pids(rows, own_pids):
    """Pids of running UIX servers except this process and its launcher (the venv python.exe starts the real interpreter as a child)."""
    return [int(r['ProcessId']) for r in rows
            if 'guppi_runtime.uix_server' in (r.get('CommandLine') or '') + ' ' and int(r['ProcessId']) not in own_pids]


def describe_running(rows, pid):
    """Woher ein laufender UIX kommt: der Ordner seines Interpreters – so sieht der Captain sofort, ob ein altes Paket läuft
    (15.10.2026: SEDRA „startete in die alte Oberfläche“ – es war das Fenster eines noch laufenden früheren Builds)."""
    row = next((r for r in rows if int(r.get('ProcessId') or 0) == pid), {})
    exe = str(row.get('ExecutablePath') or '').replace('/', '\\')
    folder = exe.split('\\runtime\\')[0] if '\\runtime\\' in exe else (exe or 'Ordner unbekannt')
    return f'PID {pid}, aus {folder}'


def preflight(rows, own_pids, *, replace=False, say=print, stop=gpu_preflight._stop, run=subprocess.run):
    """Returns an exit code: 0 = go on, 3 = a UIX is already running."""
    others = other_uix_pids(rows, own_pids)
    if others and not replace:
        say('SEDRA läuft bereits: ' + '; '.join(describe_running(rows, pid) for pid in others) + '.')
        say('Das ist das Fenster, das du siehst – womöglich ein älteres Paket. Sein Fenster schließen, oder mit "--replace" starten, um es zu beenden.')
        return 3
    for pid in others:
        say(f'Beende laufende UIX (PID {pid}).')
        stop(pid, run)
    alive = {int(r['ProcessId']) for r in rows} - set(others)
    by_pid = {int(r['ProcessId']): r for r in rows}
    for pid, info in gpu_preflight.guppi_llama_servers(run).items():
        parent = int(by_pid.get(pid, {}).get('ParentProcessId') or 0)
        if parent in alive:
            say(f'llama-server PID {pid} gehört zu einem laufenden Prozess (PID {parent}); unberührt gelassen.')
            continue
        say(f'Übriggebliebener GUPPI-llama-server PID {pid} ({gpu_preflight._alias(info)}) wird beendet.')
        stop(pid, run)
    return 0


def show_lease(say=print):
    try:
        from .testlab import TestLab, default_path
        holder = TestLab(default_path()).holder()
    except Exception:
        return
    if holder: say(f'GPU-Lease: gehalten von {holder.get("owner")} ({holder.get("purpose")}){" – abgelaufen" if holder.get("stale") else ""}.')
    else: say('GPU-Lease: frei.')


def write_standard_shell(root, shell_id):
    """Schreibt `uix.shell` in local_config/uix.yaml: die Oberfläche, die künftig ohne Wahl startet. Gibt den Namen zurück.
    Unbekannte Ids werden mit ValueError abgelehnt."""
    import yaml
    known = dict(list_shells())
    if shell_id not in known: raise ValueError('unknown_shell')
    path = Path(root) / 'local_config' / 'uix.yaml'
    data = (yaml.safe_load(path.read_text(encoding='utf-8')) or {}) if path.is_file() else {}
    data.setdefault('uix', {})['shell'] = shell_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
    return known[shell_id]


def set_standard_shell(root, shell_id):
    """Der Weg aus der Startdatei (`--als-standard`): wie write_standard_shell, mit Ausgabe für die Konsole."""
    try:
        name = write_standard_shell(root, shell_id)
    except ValueError:
        print(f'Unbekannte Oberfläche: {shell_id}'); return 2
    print(f'Standard ist jetzt: {name} ({shell_id})')
    return 0


def list_shells():
    """Die Oberflächen, die man beim Start wählen kann: id und Name. Vorlagen (_…) und der Einstieg 'start' fehlen."""
    import yaml
    rows = []
    for folder in sorted((Path(__file__).resolve().parent / 'uix' / 'shells').iterdir()):
        man = folder / 'shell.yaml'
        if not folder.is_dir() or folder.name.startswith('_') or folder.name == 'start' or not man.is_file():
            continue
        name = (yaml.safe_load(man.read_text(encoding='utf-8')) or {}).get('shell', {}).get('name') or folder.name
        rows.append((folder.name, str(name)))
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(prog='guppi-start')
    p.add_argument('--liste', action='store_true', help='print the shells that can be chosen at start: id|name per line, then exit')
    p.add_argument('--root')
    p.add_argument('--architecture')
    p.add_argument('--open', action='store_true', help='open in the normal browser instead of GUPPI\'s own window')
    p.add_argument('--replace', action='store_true', help='stop an already running UIX first')
    p.add_argument('--shell', help='start directly in this shell (this start only; the choice in uix.yaml stays)')
    p.add_argument('--uebersicht', action='store_true', help='start in the shell overview (Start), whatever uix.yaml says')
    p.add_argument('--als-standard', help='write this shell into uix.yaml as the default, then exit (no start)')
    args = p.parse_args(argv)
    if args.liste:
        for sid, name in list_shells():
            print(f'{sid}|{name}')
        return 0
    if not args.root or not args.architecture:
        p.error('--root und --architecture sind nötig')
    if args.als_standard:
        return set_standard_shell(args.root, args.als_standard)
    if args.shell and args.uebersicht:
        print('Entweder --shell <id> oder --uebersicht.'); return 2
    shell = 'start' if args.uebersicht else args.shell
    if sys.platform != "win32":
        print("Hinweis: Prozessprüfung und Aufräumen alter Modell-Server gibt es nur unter Windows; hier startet die Oberfläche direkt.")
    code = preflight(process_rows(), {os.getpid(), os.getppid()}, replace=args.replace)
    if code: return code
    show_lease()
    return serve(Path(args.root), Path(args.architecture), 0, args.open, not args.open, shell=shell) or 0


if __name__ == '__main__':
    raise SystemExit(main())
