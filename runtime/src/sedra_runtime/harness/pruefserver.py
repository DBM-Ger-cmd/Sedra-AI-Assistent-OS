"""Die Vorschau der Oberfläche als Prüfserver (SPEC_APPS_v1_O3PLUS_G9_G2 G2-09).

`POST /api/harness/oberflaeche/vorschau {shell?}` startet einen **eigenen Prozess** `python -m sedra_runtime.uix_server --root <leeres Prüfprojekt> --architecture <wie Betrieb> --port 0 [--shell …]`
und nennt seine Adresse. Code, den die Harness an der Oberfläche geändert hat und der noch zurückgehalten wird (G2-03), liegt auf der Platte; der Prüfserver liest ihn von dort, der Betriebsserver
liefert weiter die bestätigte Fassung. Der Prüfserver erreicht nichts Echtes: eigener Token (jeder Server würfelt einen), eigener Port (`--port 0`), leeres Projekt (ein frischer Ordner, kein Arbeitsstand,
keine Entscheidungen, keine Sitzungen); er kennt den Zurückhalte-Stand des Betriebsservers nicht (G2-04). Er bekommt die Schlüssel des Betriebs nicht mit: die Umgebung ist eine **Positivliste**
(`UMGEBUNG_ERLAUBT`, Captain 16.11.2026 nach der Durchsicht der Übernahme): nur das, was ein Python-Prozess unter Windows zum Laufen braucht; jede andere Variable – gleich unter welchem Namen
(`NVIDIA_API_KEY`, `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `SEDRA_SECRET_*`) – wird nicht vererbt.

Höchstens einer zugleich. Ende: nach 30 Minuten, beim Beantworten der Sammelkarte (übernehmen, zurücksetzen), beim Ende des Betriebsservers oder auf Wunsch. Das leere Prüfprojekt wird gelöscht.
Der Start ist ein Prozess mit Wirkung (ein Server hört auf einem Port): die Route gehört zu den geschützten Wegen (Herkunftsprüfung, `harness/api.py` GESCHUETZT)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

SHELL_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
DAUER_S = 30 * 60
START_S = 90
ADRESSE = re.compile(r'(https?://127\.0\.0\.1:\d+/\S*)')
# Positivliste der Umgebung (Namen in Großbuchstaben; Windows ignoriert die Schreibweise). Dazu setzt `starten` PYTHONPATH und PYTHONIOENCODING.
UMGEBUNG_ERLAUBT = frozenset({'PATH', 'PATHEXT', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA',
                              'PROGRAMFILES', 'PROGRAMFILES(X86)', 'COMMONPROGRAMFILES', 'HOMEDRIVE', 'HOMEPATH', 'USERNAME', 'USERDOMAIN', 'COMPUTERNAME', 'OS',
                              'PROCESSOR_ARCHITECTURE', 'PROCESSOR_ARCHITEW6432', 'NUMBER_OF_PROCESSORS', 'LANG', 'LC_ALL', 'TZ', 'HOME', 'PYTHONUTF8'})


def umgebung_vererbt(umgebung):
    """Nur die Variablen der Positivliste (`UMGEBUNG_ERLAUBT`) – alles andere, auch ein Schlüssel unter anderem Namen, bleibt beim Betriebsserver."""
    return {k: v for k, v in umgebung.items() if k.upper() in UMGEBUNG_ERLAUBT}


class PruefserverFehler(ValueError):
    """Der Prüfserver ließ sich nicht starten; der Text ist der Grund."""


class Pruefserver:
    def __init__(self, ablage, architektur, quellen, *, dauer_s=DAUER_S, start_s=START_S, popen=subprocess.Popen, audit=None, uhr=time.time):
        self.ablage, self.architektur, self.quellen = Path(ablage), Path(architektur), Path(quellen)
        self.dauer_s, self.start_s, self._popen, self._audit, self._uhr = dauer_s, start_s, popen, audit, uhr
        self._proc = None
        self._projekt = None
        self._timer = None
        self._info = None
        self._sperre = threading.RLock()

    def _log(self, event, **payload):
        if self._audit is not None:
            try:
                self._audit(event, payload)
            except Exception:
                pass

    def status(self):
        """{laeuft, adresse, shell, bis} – `laeuft` ist falsch, sobald der Prozess endete."""
        with self._sperre:
            if self._proc is not None and self._proc.poll() is not None:
                self._aufraeumen()
            return dict(self._info) if self._info else {'laeuft': False}

    def starten(self, shell=None):
        """Startet den Prüfserver (einen laufenden zuvor beendet) und liefert {laeuft, adresse, shell, bis, pid}."""
        if shell is not None and not (isinstance(shell, str) and SHELL_ID.match(shell)):
            raise PruefserverFehler('shell_ungueltig: Kennung der Oberfläche, a-z, 0-9 und Bindestrich')
        with self._sperre:
            self.beenden('neu')
            self.ablage.mkdir(parents=True, exist_ok=True)
            projekt = Path(tempfile.mkdtemp(prefix='pruef-', dir=str(self.ablage)))
            argv = [sys.executable, '-u', '-m', 'sedra_runtime.uix_server', '--root', str(projekt), '--architecture', str(self.architektur), '--port', '0']
            if shell:
                argv += ['--shell', shell]
            env = umgebung_vererbt(os.environ)
            env['PYTHONPATH'] = str(self.quellen)                              # nur die Quellen des Betriebs, kein fremdes PYTHONPATH
            env['PYTHONIOENCODING'] = 'utf-8'
            try:
                proc = self._popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env, cwd=str(projekt))
            except OSError as exc:
                shutil.rmtree(projekt, ignore_errors=True)
                raise PruefserverFehler(f'start_fehlgeschlagen: {exc}') from exc
            adresse = self._adresse(proc)
            if adresse is None:
                self._stoppen(proc)
                shutil.rmtree(projekt, ignore_errors=True)
                raise PruefserverFehler('start_ohne_adresse: der Prüfserver nannte binnen %d s keine Adresse' % self.start_s)
            self._proc, self._projekt = proc, projekt
            bis = (datetime.now().astimezone() + timedelta(seconds=self.dauer_s)).isoformat(timespec='seconds')
            self._info = {'laeuft': True, 'adresse': adresse, 'shell': shell, 'bis': bis, 'pid': getattr(proc, 'pid', None)}
            self._timer = threading.Timer(self.dauer_s, self.beenden, args=('zeit',))
            self._timer.daemon = True
            self._timer.start()
            self._log('HARNESS_VORSCHAU_START', shell=shell, pid=self._info['pid'], dauer_s=self.dauer_s)
            return dict(self._info)

    def _adresse(self, proc):
        """Liest die ersten Zeilen, bis die Adresse kommt (Zeile „SEDRA Desktop (UIX): <url>“); danach liest ein Thread weiter, damit die Pipe nie voll läuft."""
        gefunden = []
        fertig = threading.Event()

        def lesen():
            try:
                for zeile in proc.stdout:
                    if not gefunden:
                        m = ADRESSE.search(zeile)
                        if m:
                            gefunden.append(m.group(1))
                            fertig.set()
            except (OSError, ValueError):
                pass
            fertig.set()
        threading.Thread(target=lesen, daemon=True).start()
        fertig.wait(self.start_s)
        return gefunden[0] if gefunden else None

    @staticmethod
    def _stoppen(proc):
        """Beendet den Prozess – unter Windows den ganzen Baum (der Start über den Python-Starter erzeugt einen Kindprozess, `terminate()` träfe nur den Starter). Nur für echte Prozesse:
        eine Attrappe mit erfundener PID darf nie einen fremden Prozess treffen."""
        try:
            if os.name == 'nt' and isinstance(proc, subprocess.Popen) and getattr(proc, 'pid', None):
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=15)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        except Exception:
            pass

    @staticmethod
    def _loeschen(projekt):
        """Löscht das Prüfprojekt; unter Windows geben beendete Prozesse ihre Dateien einen Augenblick später frei, deshalb ein paar kurze Wiederholungen."""
        for _ in range(20):
            shutil.rmtree(projekt, ignore_errors=True)
            if not Path(projekt).exists():
                return
            time.sleep(0.25)

    def _aufraeumen(self):
        if self._timer is not None:
            self._timer.cancel()
        if self._projekt is not None:
            self._loeschen(self._projekt)
        self._proc = self._projekt = self._timer = self._info = None

    def beenden(self, grund='wunsch'):
        """Beendet den laufenden Prüfserver und löscht das Prüfprojekt; liefert True, wenn einer lief."""
        with self._sperre:
            if self._proc is None:
                return False
            if self._proc.poll() is None:
                self._stoppen(self._proc)
            self._log('HARNESS_VORSCHAU_ENDE', grund=grund)
            self._aufraeumen()
            return True
