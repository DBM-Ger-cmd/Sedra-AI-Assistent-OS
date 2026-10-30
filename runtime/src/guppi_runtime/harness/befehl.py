"""Das Werkzeug `befehl` der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-20, G2 §3.4, D-E1, G3 Stufe 2 U6).

Auf dem Host, nur im Harness-Projekt, **ohne** Shell-Interpreter: die Zeile wird mit `shlex` (Windows-Modus) zerlegt und direkt gestartet;
`|`, `>`, `<`, `&`, `;`, Backtick und `$(` sind Fehler. Der Ordner liegt in der Projektwurzel. Umgebung wie `ShellTool._safe_env` plus
`PYTHONIOENCODING=utf-8`; `python` ist der Python dieser Runtime. Zeitlimit höchstens 600 s, Ausgabe höchstens 20 000 Zeichen (Anfang und
Ende). Stopp oder Zeitlimit beenden den ganzen Prozessbaum.

Jeder Befehl braucht ein Token des Guard für genau diese Zeile in genau diesem Ordner (Aktion `harness_befehl`, kennt der Guard nicht →
CAPTAIN_REQUIRED). Ob die Harness das Token selbst holt (Katalog `frei`) oder der Captain es auf der Karte gibt, entscheidet `freigabe.py`.
Diese Datei ist Harness-Code (Vorbehalt): SEDRA ändert sie nicht an sich selbst."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import herkunft

AKTION = 'harness_befehl'
ZEITLIMIT_MAX = 600
AUSGABE_MAX = 20_000
INTERPRETER = re.compile(r'[|<>&;`]|\$\(')
ERLAUBT_ENV = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'LANG', 'LC_ALL', 'VIRTUAL_ENV'}


class BefehlFehler(ValueError):
    pass


class Ruecknahme:
    """Stufe 3 G2 §4.4, offener Punkt aus dem Baubericht Stufe 3 (Befund 7): wird eine Aufgabe zurückgenommen, endet auch ein `befehl`,
    der unter ihr läuft – nicht erst der nächste Aufruf. Je Aufgabe ein Ereignis; `ausfuehren` sieht es neben dem Abbruch der Antwort."""
    def __init__(self):
        self._events, self._lock = {}, threading.Lock()

    def ereignis(self, aufgabe_id):
        if not aufgabe_id:
            return None
        with self._lock:
            return self._events.setdefault(str(aufgabe_id), threading.Event())

    def ausloesen(self, aufgabe_id):
        e = self.ereignis(aufgabe_id)
        if e is not None:
            e.set()
        return e

    def vergessen(self, aufgabe_id):
        with self._lock:
            self._events.pop(str(aufgabe_id or ''), None)


RUECKNAHME = Ruecknahme()


def _ausserhalb_anfuehrung(zeile):
    """Die Zeile ohne den Text in Anführungszeichen: `python -c "a; b"` ist ein Argument, kein zweiter Befehl (es gibt keine Shell)."""
    out, zeichen = [], None
    for c in zeile:
        if zeichen:
            if c == zeichen: zeichen = None
        elif c in '"\'':
            zeichen = c
        else:
            out.append(c)
    return ''.join(out)


def zerlegen(zeile):
    """Die Argumente einer Zeile – oder BefehlFehler (Interpreterzeichen, leer, ungültige Anführungszeichen)."""
    zeile = str(zeile or '').strip()
    if not zeile or '\n' in zeile or '\r' in zeile:
        raise BefehlFehler('befehl_eine_zeile: genau eine nicht leere Zeile')
    if INTERPRETER.search(_ausserhalb_anfuehrung(zeile)):
        raise BefehlFehler('befehl_ohne_shell: keine Pipes, Umleitungen, „&&“ oder „;“ – ein Befehl je Aufruf')
    try:
        teile = shlex.split(zeile, posix=False)
    except ValueError as exc:
        raise BefehlFehler(f'befehl_unlesbar: {exc}') from exc
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in '"\'' else t for t in teile]


def ordner_in(wurzel, ordner):
    """Der Arbeitsordner (absolut) – nur innerhalb der Projektwurzel."""
    wurzel = Path(wurzel).resolve()
    ziel = (wurzel / str(ordner or '.')).resolve()
    try:
        ziel.relative_to(wurzel)
    except ValueError as exc:
        raise BefehlFehler('ordner_ausserhalb: der Ordner liegt nicht im Projekt') from exc
    if not ziel.is_dir():
        raise BefehlFehler('ordner_fehlt')
    return ziel


def bindung(zeile, ordner_rel):
    """Woran das Token gebunden ist: genau diese Zeile in genau diesem Ordner."""
    return {'befehl': ' '.join(str(zeile).split()), 'ordner': str(ordner_rel or '.').replace('\\', '/')}


def ziel_text(zeile, ordner_rel):
    b = bindung(zeile, ordner_rel)
    return f"{b['ordner']}> {b['befehl']}"


def umgebung():
    env = {k: v for k, v in os.environ.items() if k.upper() in ERLAUBT_ENV}
    env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONIOENCODING='utf-8')
    return env


def kuerzen(text):
    if len(text) <= AUSGABE_MAX:
        return text, False
    halb = AUSGABE_MAX // 2
    return text[:halb] + f'\n… [{len(text) - AUSGABE_MAX} Zeichen ausgelassen] …\n' + text[-halb:], True


def _beenden(proc):
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)], capture_output=True)
    else:
        import signal
        try: os.killpg(proc.pid, signal.SIGKILL)
        except OSError: proc.kill()


def ausfuehren(wurzel, zeile, ordner='.', zeitlimit_s=120, *, guard, mission_id, token, abbruch=None, aufgabe_id=None, clock=time.monotonic):
    """Führt den Befehl aus, wenn das Token genau dazu passt. Rückgabe {status, exitcode, ausgabe, gekuerzt, dauer_s};
    status ∈ ok, fehler (exitcode ≠ 0), zeitlimit, abgebrochen, zurueckgenommen, nicht_erlaubt. `aufgabe_id`: läuft der Befehl unter einer
    Aufgaben-Freigabe, endet er mit deren Rücknahme (RUECKNAHME)."""
    argv = zerlegen(zeile)
    cwd = ordner_in(wurzel, ordner)
    rel = cwd.relative_to(Path(wurzel).resolve()).as_posix() or '.'
    try:
        zeitlimit = max(1, min(ZEITLIMIT_MAX, int(zeitlimit_s)))
    except (TypeError, ValueError) as exc:
        raise BefehlFehler('zeitlimit_ungueltig') from exc
    auth = guard.authorize(token, mission_id=mission_id, action=AKTION, target=ziel_text(zeile, rel), request_binding=bindung(zeile, rel))
    if not auth.get('authorized'):
        return {'status': 'nicht_erlaubt', 'exitcode': None, 'ausgabe': 'Kein passendes Token: ' + str(auth.get('reason')), 'gekuerzt': False, 'dauer_s': 0}
    if argv[0].lower() in ('python', 'python.exe', 'py'):
        argv[0] = sys.executable
    else:
        gefunden = shutil.which(argv[0], path=umgebung().get('PATH'))
        if not gefunden:
            return {'status': 'fehler', 'exitcode': None, 'ausgabe': f'Programm nicht gefunden: {argv[0]}', 'gekuerzt': False, 'dauer_s': 0}
        argv[0] = gefunden
    kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    t0 = clock()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=umgebung(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
    herkunft.REGISTER.registrieren(proc.pid)          # Stufe 3, S7: Anfragen aus diesem Prozess (und seinen Kindern) dürfen keine Freigabe beantworten
    stuecke = []
    leser = threading.Thread(target=lambda: stuecke.append(proc.stdout.read()), daemon=True)
    leser.start()
    status = None
    ruecknahme = RUECKNAHME.ereignis(aufgabe_id)
    while proc.poll() is None:
        if abbruch is not None and abbruch.is_set():
            status = 'abgebrochen'; _beenden(proc); break
        if ruecknahme is not None and ruecknahme.is_set():
            status = 'zurueckgenommen'; _beenden(proc); break
        if clock() - t0 > zeitlimit:
            status = 'zeitlimit'; _beenden(proc); break
        time.sleep(0.05)
    proc.wait(timeout=30)
    herkunft.REGISTER.austragen(proc.pid)
    leser.join(timeout=10)
    roh = b''.join(stuecke).decode('utf-8', errors='replace')
    ausgabe, gekuerzt = kuerzen(roh)
    if status is None:
        status = 'ok' if proc.returncode == 0 else 'fehler'
    return {'status': status, 'exitcode': proc.returncode, 'ausgabe': ausgabe, 'gekuerzt': gekuerzt, 'dauer_s': round(clock() - t0, 2)}
