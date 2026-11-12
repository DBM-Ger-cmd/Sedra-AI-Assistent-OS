"""Dienst-Apps (SPEC_APPS_v1_AM4_DIENSTE Teil B, AM4-05 bis AM4-10, AM4-12): ein eigener Prozess, den der Kern startet und stoppt und der nur über Desk-Objekte und -Verben spricht.

Ehrliche Grenze (AM4 §1): Auf dem Host läuft ein Dienst unter demselben Konto wie SEDRA. Der eigene Token und seine Gewährung sind dort Ordnung und Nachweis, keine Sicherheitsgrenze gegen einen
bösartigen Dienst. Darum läuft auf dem Host nur Code des Captains (`CAPTAIN`) oder von SEDRA Gebautes (`SEDRA_BUILT`); fremde Dienste (`COMMUNITY`) nur in der microVM – und die ist in v1 nicht
angebunden (AM4-07, B7), also gibt es fremde Dienste nicht.

Kein Shell-Aufruf: `subprocess` mit Liste, `shell=False`, Arbeitsordner = Ordner der App, Umgebung minimal. Ausgaben gehen in ein rollierendes Protokoll, nie ins Audit.
v1 startet nur Python-Dateien (`.py`, mit dem Interpreter von SEDRA); andere Programmarten sind `dienst_start_art`."""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from ..core.util import atomic_write_json

KIND_DIENST = 'dienst_start'                 # Antrag im Posteingang (Gate), Klasse H
ORTE = ('host', 'microvm')
NEUSTART = ('nie', 'bei_fehler')
SHELLZEICHEN = re.compile(r'[|&;<>$`\n\r"\'%^!*?\[\]{}()~]')
PROTOKOLL_VORGABE_KB, PROTOKOLL_MIN_KB, PROTOKOLL_MAX_KB = 512, 16, 4096
NEUSTARTS_JE_STUNDE = 3
STOPP_WARTE_S = 5.0
ARGS_MAX = 16
ENV_ERLAUBT = ('PATH', 'SYSTEMROOT', 'SEDRA_DESK_PORT', 'SEDRA_DIENST_TOKEN_DATEI')


def pruefe_dienst(block, trust, ordner) -> tuple[dict | None, list]:
    """(normalisierter Block, Fehler) für `dienst:` im Manifest (AM4-05, AM4-07). `ordner` ist der Ordner der App."""
    fehler = []
    if not isinstance(block, dict):
        return None, ['dienst_block_fehlt']
    unbekannt = sorted(set(block) - {'start', 'ort', 'neustart', 'protokoll_max'})
    if unbekannt:
        fehler.append('dienst_unbekanntes_feld:' + unbekannt[0])
    start = block.get('start')
    if (not isinstance(start, list) or not 1 <= len(start) <= ARGS_MAX or not all(isinstance(x, str) and x and len(x) <= 200 for x in start)):
        fehler.append('dienst_start_ungueltig')
        start = None
    elif any(SHELLZEICHEN.search(x) for x in start):
        fehler.append('dienst_start_shellzeichen')
    else:
        erste = start[0].replace('\\', '/')
        if erste.startswith('/') or re.match(r'^[A-Za-z]:', erste) or '..' in erste.split('/'):
            fehler.append('dienst_start_pfad')
        elif not str(erste).lower().endswith('.py'):
            fehler.append('dienst_start_art')
        else:
            try:
                datei = (Path(ordner) / erste).resolve()
                datei.relative_to(Path(ordner).resolve())
                if not datei.is_file():
                    fehler.append('dienst_start_fehlt')
            except (ValueError, OSError):
                fehler.append('dienst_start_pfad')
    ort = block.get('ort', 'host')
    if ort not in ORTE:
        fehler.append('dienst_ort_ungueltig')
    elif trust == 'COMMUNITY':
        fehler.append('dienst_fremd_nur_microvm')                 # AM4-07: ein fremder Dienst läuft nie auf dem Host …
    elif ort == 'microvm':
        fehler.append('dienst_microvm_nicht_verfuegbar')          # … und die microVM ist in v1 nicht angebunden (B7); damit gibt es fremde Dienste nicht
    elif trust not in ('CAPTAIN', 'SEDRA_BUILT'):
        fehler.append('dienst_host_vertrauen')
    neustart = block.get('neustart', 'nie')
    if neustart not in NEUSTART:
        fehler.append('dienst_neustart_ungueltig')
    kb = block.get('protokoll_max', PROTOKOLL_VORGABE_KB)
    if isinstance(kb, bool) or not isinstance(kb, int) or not PROTOKOLL_MIN_KB <= kb <= PROTOKOLL_MAX_KB:
        fehler.append('dienst_protokoll_max_ungueltig')
        kb = PROTOKOLL_VORGABE_KB
    if fehler:
        return None, fehler
    return {'start': list(start), 'ort': ort, 'neustart': neustart, 'protokoll_max': kb}, []


def anwenden(hub, binding):
    """Der Applier der Freigabe (Art `dienst_start`): startet den Dienst – nur, wenn das Manifest noch dasselbe ist wie im Antrag und der Schalter an ist."""
    from . import app_speicher
    if not getattr(hub, 'dienste_an', False):
        raise ValueError('guard_refused:dienste_aus')
    eintrag = hub.gateway._load('tools')[0].get(binding.get('id'))
    if eintrag is None or eintrag[1].get('kind') != 'dienst':
        raise ValueError('guard_refused:dienst_unbekannt')
    folder, man = eintrag
    if app_speicher.manifest_hash(folder / 'tool.yaml') != binding.get('manifest_sha256'):
        raise ValueError('binding_stale')                            # das Manifest hat sich seit dem Antrag geändert: nichts wird gestartet
    return hub.dienste.start(binding['id'], folder, man['dienst'], man['trust'])


class Dienste:
    def __init__(self, project_root, port=0, *, audit=None, uhr=time.time, popen=subprocess.Popen):
        self.root = Path(project_root)
        self.port = port
        self.audit = audit
        self.uhr = uhr
        self.popen = popen
        self.lock = threading.RLock()
        self.laufend = {}                    # id -> {proc, token, folder, dienst, trust, seit, log, thread}
        self.aus = {}                        # id -> Grund, warum der Dienst nicht (mehr) läuft
        self.neustarts = {}                  # id -> [Zeitpunkte]

    # ---- Hilfen
    def _melden(self, event, payload):
        if self.audit:
            try:
                self.audit(event, payload)
            except Exception:
                pass

    def ordner(self, app_id) -> Path:
        return self.root / 'runtime_data' / 'dienste' / app_id

    def klasse(self, token) -> str | None:
        """AM4-08: der Client-Name zu einem Dienst-Token (`dienst:<id>`) oder None – ein entzogener oder fremder Token ist ungültig."""
        if not token:
            return None
        with self.lock:
            for app_id, d in self.laufend.items():
                if secrets.compare_digest(str(token), d['token']):
                    return 'dienst:' + app_id
        return None

    def dienst_von_klasse(self, klasse):
        return self.laufend.get(str(klasse)[7:]) if str(klasse).startswith('dienst:') else None

    # ---- Starten und Stoppen
    def start(self, app_id, folder, dienst, trust):
        """Startet den Dienst. Rückgabe {id, pid}. Schon laufend → ValueError('dienst_laeuft_schon')."""
        if trust not in ('CAPTAIN', 'SEDRA_BUILT') or dienst.get('ort') != 'host':
            raise ValueError('dienst_nicht_startbar')                  # die Prüfung im Manifest steht schon, hier die zweite Sperre
        with self.lock:
            if app_id in self.laufend:
                raise ValueError('dienst_laeuft_schon')
            ordner = self.ordner(app_id)
            ordner.mkdir(parents=True, exist_ok=True)
            token = secrets.token_urlsafe(32)
            datei = self._token_schreiben(app_id, token)
            erste = Path(folder).resolve() / dienst['start'][0]
            argv = [sys.executable, str(erste.resolve()), *dienst['start'][1:]]
            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'SYSTEMROOT')}
            env.update({'SEDRA_DESK_PORT': str(self.port), 'SEDRA_DIENST_TOKEN_DATEI': str(datei)})
            log = ordner / 'protokoll.txt'
            proc = self.popen(argv, cwd=str(Path(folder).resolve()), env=env, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            d = {'proc': proc, 'token': token, 'folder': Path(folder).resolve(), 'dienst': dict(dienst), 'trust': trust, 'seit': self.uhr(), 'log': log, 'datei': datei}
            d['thread'] = threading.Thread(target=self._protokoll, args=(proc, log, dienst['protokoll_max'] * 1024), daemon=True)
            d['thread'].start()
            self.laufend[app_id] = d
            self.aus.pop(app_id, None)
        self._melden('DIENST_GESTARTET', {'id': app_id, 'pid': getattr(proc, 'pid', None), 'ort': dienst['ort'], 'vertrauen': trust})
        return {'id': app_id, 'pid': getattr(proc, 'pid', None)}

    def _token_schreiben(self, app_id, token):
        from ..uix_clients import _protect
        schutz, wert = _protect(token)
        datei = self.ordner(app_id) / 'token.json'
        atomic_write_json(datei, {'client': 'dienst:' + app_id, 'port': int(self.port), 'protection': schutz, 'token': wert})
        if sys.platform != 'win32':
            os.chmod(datei, 0o600)
        return datei

    def _protokoll(self, proc, pfad, grenze):
        """AM4-09: stdout und stderr nach `protokoll.txt`, rollierend auf `grenze` Byte (die Hälfte bleibt, wenn die Grenze erreicht ist). Kein Inhalt ins Audit."""
        f = None
        try:
            f = open(pfad, 'ab')
            while True:
                zeile = proc.stdout.readline() if proc.stdout is not None else b''
                if not zeile:
                    break
                f.write(zeile)
                f.flush()
                if f.tell() > grenze:
                    f.close()
                    Path(pfad).write_bytes(Path(pfad).read_bytes()[-(grenze // 2):])
                    f = open(pfad, 'ab')
        except (OSError, ValueError):
            pass
        finally:
            if f is not None:
                try:
                    f.close()
                except OSError:
                    pass

    def _entziehen(self, app_id):
        d = self.laufend.pop(app_id, None)
        if d is not None:
            try:
                Path(d['datei']).unlink()
            except OSError:
                pass
            self._melden('DIENST_TOKEN_ENTZOGEN', {'id': app_id})
        return d

    def stop(self, app_id, grund='captain', warte=STOPP_WARTE_S):
        """AM4-06: erst bitten (terminate), nach `warte` Sekunden beenden (kill); der Token ist sofort ungültig. Rückgabe True, wenn er lief."""
        with self.lock:
            d = self.laufend.get(app_id)
            if d is None:
                return False
            self._entziehen(app_id)                                       # zuerst: ab jetzt 403
            self.aus[app_id] = grund
        proc = d['proc']
        try:
            proc.terminate()
            try:
                proc.wait(timeout=warte)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=warte)
        except OSError:
            pass
        self._melden('DIENST_GESTOPPT', {'id': app_id, 'grund': grund})
        return True

    def stop_alle(self, grund='ende'):
        for app_id in list(self.laufend):
            self.stop(app_id, grund)

    # ---- Überwachen
    def pruefen(self):
        """AM4-10: abgestürzte Dienste erkennen (`DIENST_ABGESTUERZT {exitcode}`); `neustart: bei_fehler` startet höchstens 3 Mal je Stunde neu, dann aus mit Hinweis. Rückgabe: die abgestürzten ids."""
        abgestuerzt = []
        for app_id, d in list(self.laufend.items()):
            code = d['proc'].poll()
            if code is None:
                continue
            with self.lock:
                self._entziehen(app_id)
                self.aus[app_id] = f'abgestuerzt:{code}'
            self._melden('DIENST_ABGESTUERZT', {'id': app_id, 'exitcode': code})
            abgestuerzt.append(app_id)
            if d['dienst'].get('neustart') == 'bei_fehler' and code != 0:
                jetzt = self.uhr()
                liste = [t for t in self.neustarts.get(app_id, []) if jetzt - t < 3600]
                if len(liste) >= NEUSTARTS_JE_STUNDE:
                    self.aus[app_id] = 'zu_oft_abgestuerzt'
                    self._melden('DIENST_GESTOPPT', {'id': app_id, 'grund': 'zu_oft_abgestuerzt'})
                else:
                    liste.append(jetzt)
                    self.neustarts[app_id] = liste
                    try:
                        self.start(app_id, d['folder'], d['dienst'], d['trust'])
                    except Exception as exc:
                        self.aus[app_id] = 'neustart_fehlgeschlagen:' + type(exc).__name__
        return abgestuerzt

    def zustand(self):
        """Für die Seite: {id: {laeuft, pid, seit, grund}} der bekannten Dienste (laufende und gestoppte)."""
        out = {}
        for app_id, d in self.laufend.items():
            out[app_id] = {'laeuft': True, 'pid': getattr(d['proc'], 'pid', None), 'seit': d['seit'], 'grund': None}
        for app_id, grund in self.aus.items():
            out.setdefault(app_id, {'laeuft': False, 'pid': None, 'seit': None, 'grund': grund})
        return out
