"""The one standard start of SEDRA's UIX (all START_*.bat call this): check what is already running, clear leftovers, then serve.

1. A second UIX is not started next to a running one (two servers fight over the GPU lease and the llama-server port).
2. A SEDRA llama-server whose starter is gone (UIX killed, window crashed) is a leftover: it holds the VRAM and the UIX does not own it,
   so every model load fails with hardware_pressure. Such leftovers are stopped; a server with a live starter (a benchmark run) is only reported.
3. The GPU lease holder is shown, so a busy card is explained before the first model load fails."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from .models import gpu_preflight
from .uix_server import serve


class ProcessInventoryError(RuntimeError):
    """Windows process inventory could not be trusted for a safe second-start check."""


# Match actual Python module invocations, not a module name embedded in
# a script argument or in another program's command line.
_UIX_MODULE_COMMAND = re.compile(
    r'^\s*(?:"[^"\r\n]*?(?:[\\/])?pythonw?(?:\.exe)?"|'
    r'(?:\S*[\\/])?pythonw?(?:\.exe)?)\s+'
    r'(?:(?:-[IBEsSOuq])\s+)*'
    r'-m\s+(?:sedra_runtime|sedra_runtime)\.(?:uix_start|uix_server)(?=\s|$)',
    re.IGNORECASE,
)


def _pid(value):
    """Return a valid positive PID, or None for incomplete inventory rows."""
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number > 0 else None


def process_rows(run=subprocess.run, platform=sys.platform):
    """Return Windows process rows, fail closed if PowerShell cannot inventory them.

    Unix has no PowerShell inventory in this launcher; do not report it as a
    successful duplicate check there.
    """
    if platform != "win32":
        return []
    try:
        raw = gpu_preflight._powershell(
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'llama-server.exe','python.exe','pythonw.exe' } | "
            "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress", run)
        data = json.loads(raw) if raw else None
    except (ValueError, TypeError, OSError, subprocess.SubprocessError) as exc:
        raise ProcessInventoryError('Windows process inventory unavailable') from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ProcessInventoryError('Windows process inventory returned invalid JSON')
    rows = [item for item in data if isinstance(item, dict)]
    if not rows:
        raise ProcessInventoryError('Windows process inventory returned no process rows')
    return rows


def other_uix_pids(rows, own_pids):
    """Identify only Python processes invoking known SEDRA/legacy UIX modules."""
    excluded = {_pid(pid) for pid in own_pids}
    matches, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = _pid(row.get('ProcessId'))
        if pid is None or pid in excluded or pid in seen:
            continue
        name = str(row.get('Name') or '').lower()
        if name and name not in {'python', 'pythonw', 'python.exe', 'pythonw.exe'}:
            continue
        cmd = row.get('CommandLine')
        if isinstance(cmd, str) and _UIX_MODULE_COMMAND.match(cmd):
            matches.append(pid)
            seen.add(pid)
    return matches


def wait_port_free(port: int, host: str = "127.0.0.1", timeout: float = 10.0) -> bool:
    """Wartet bis Port frei ist (Connection Refused)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                time.sleep(0.2)  # Port noch belegt
        except ConnectionRefusedError:
            return True  # Port frei
        except OSError:
            time.sleep(0.2)
    return False  # Timeout


def describe_running(rows, pid):
    """Show the package location of a detected UIX even with partial rows."""
    row = next((r for r in rows if isinstance(r, dict) and _pid(r.get('ProcessId')) == pid), {})
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
        # Warte kurz, damit der Prozess seinen Port freigeben kann
        time.sleep(0.5)
    by_pid = {_pid(r.get('ProcessId')): r for r in rows
              if isinstance(r, dict) and _pid(r.get('ProcessId')) is not None}
    alive = set(by_pid) - set(others)
    for pid, info in gpu_preflight.sedra_llama_servers(run).items():
        proc = by_pid.get(pid)
        parent = _pid(proc.get('ParentProcessId')) if proc else None
        if parent is None:
            say(f'llama-server PID {pid}: Besitzverhaeltnis nicht verifiziert; unberuehrt gelassen.')
            continue
        if parent in alive:
            say(f'llama-server PID {pid} gehört zu einem laufenden Prozess (PID {parent}); unberührt gelassen.')
            continue
        say(f'Übriggebliebener SEDRA-llama-server PID {pid} ({gpu_preflight._alias(info)}) wird beendet.')
        stop(pid, run)
    return 0


def show_lease(say=print):
    try:
        from .jobs.testlab import TestLab, default_path
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
    p = argparse.ArgumentParser(prog='sedra-start')
    p.add_argument('--liste', action='store_true', help='print the shells that can be chosen at start: id|name per line, then exit')
    p.add_argument('--root')
    p.add_argument('--architecture')
    p.add_argument('--open', action='store_true', help='open in the normal browser instead of SEDRA\'s own window')
    p.add_argument('--replace', action='store_true', help='stop an already running UIX first')
    p.add_argument('--ohne-fenster', action='store_true', help='serve without any window or browser (for clients such as the Orca bridge); stop with Ctrl+C or by ending the process')
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
    try:
        rows = process_rows()
    except ProcessInventoryError as exc:
        print(f'SEDRA-Start verweigert: Prozesspruefung fehlgeschlagen ({exc}).')
        return 4
    code = preflight(rows, {os.getpid(), os.getppid()}, replace=args.replace)
    if code: return code
    show_lease()
    return serve(Path(args.root), Path(args.architecture), 0, args.open, not (args.open or args.ohne_fenster), shell=shell) or 0


if __name__ == '__main__':
    raise SystemExit(main())
