"""Hülle eines Laufs der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-31, G2 Stufe 3 §6.3, G3 Stufe 3 N7).

Wird vom Starter (`lauf.Laeufe.starten`) losgelöst gestartet: `python lauf_huelle.py <lauf-ordner>`. Sie ist **eigenständig** (nur Standardbibliothek), damit sie auch
ohne den Suchpfad der Runtime läuft und den Neustart des Servers überlebt. Sie liest `lauf.json` (argv, Arbeitsordner, Zeitlimit), startet das Ziel ohne Shell
mit der Ausgabe in `ausgabe.log` und schreibt am Ende `ende.json` {exit, grund, zeit}. Eine Datei `stopp.txt` im Lauf-Ordner beendet den Lauf (Prozessbaum) – so stoppt
auch ein Server, der den Lauf nach einem Neustart nur wiederfindet. Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def beenden(proc):
    """Beendet den Prozessbaum des Ziels (nur die eigene PID, nie per Namensmuster)."""
    if os.name == 'nt':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)], capture_output=True)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()


def main(ordner):
    ordner = Path(ordner)
    lauf = json.loads((ordner / 'lauf.json').read_text(encoding='utf-8'))
    kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    grund, exitcode = None, None
    t0 = time.monotonic()
    zeitlimit = float(lauf.get('zeitlimit_min') or 60) * 60
    with open(ordner / 'ausgabe.log', 'ab', buffering=0) as log:
        try:
            proc = subprocess.Popen(lauf['argv'], cwd=lauf['ordner_abs'], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
        except OSError as exc:
            log.write(f'Start fehlgeschlagen: {type(exc).__name__}: {exc}\n'.encode('utf-8'))
            grund, exitcode = 'start_fehlgeschlagen', None
        else:
            while proc.poll() is None:
                if (ordner / 'stopp.txt').exists():
                    grund = 'gestoppt'; beenden(proc); break
                if time.monotonic() - t0 > zeitlimit:
                    grund = 'zeitlimit'; beenden(proc); break
                time.sleep(0.2)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            exitcode = proc.returncode
            grund = grund or ('ok' if exitcode == 0 else 'fehler')
    ende = {'exit': exitcode, 'grund': grund, 'zeit': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    tmp = ordner / 'ende.tmp'
    tmp.write_text(json.dumps(ende), encoding='utf-8')
    os.replace(tmp, ordner / 'ende.json')


if __name__ == '__main__':
    main(sys.argv[1])
