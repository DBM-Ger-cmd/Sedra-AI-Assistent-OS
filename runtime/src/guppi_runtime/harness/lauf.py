"""Läufe der Harness-Shell, Teil 1: die Lauf-Typen (SPEC_HARNESS_SHELL_v1 HS-20, G2 Stufe 3 §6.1, G3 Stufe 3 N6).

Ein Lauf ist kein freier Befehl. `runtime/config/harness_laeufe.yaml` (Repo, harter Vorbehalt – die Datei ändert nur Claude) nennt die Lauf-Typen; `lauf_starten`
nimmt eine Lauf-ID und Parameter, die ihr Muster **ganz** erfüllen. Hier: laden, prüfen und `argv_bauen` – das fertige Argument-Feld für den Prozess,
ohne Shell-Interpreter. Teil 2 (unten): Starter, Register, Wiederanbinden und Stopp; die Hülle steht in `lauf_huelle.py`.

Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import yaml

DATEI = 'harness_laeufe.yaml'
LAEUFE_DATEI = Path(__file__).resolve().parents[3] / 'config' / DATEI
ID = re.compile(r'[a-z][a-z0-9_]{0,40}')
PLATZHALTER = re.compile(r'\{([a-z][a-z0-9_]*)\}')
PROGRAMM = re.compile(r'[A-Za-z0-9_.-]+')
GPU = ('keine', 'slot', 'exklusiv')
FORTSCHRITT = {'zeilen': 2, 'prozent': 1, 'text': 0}           # Art → Zahl der Gruppen, die die Regel braucht
VERBOTEN = set(';|&<>`$()"\'\n\r\0')                            # in keinem Parameterwert (auch ohne Shell: kein Raum für Tricks)
MEHRERE_MAX = 10
ZEITLIMIT_MAX_MIN = 600


class LaufFehler(ValueError):
    """Die Datei oder der Aufruf ist ungültig; der Text nennt den Grund."""


def _bool(wert, name):
    if not isinstance(wert, bool):
        raise LaufFehler(f'{name}_kein_wahr_falsch')
    return wert


def pruefen(doc):
    """{id: Typ} aus einer gelesenen Datei – oder LaufFehler mit Grund."""
    k = doc.get('harness_laeufe') if isinstance(doc, dict) else None
    if not isinstance(k, dict) or not isinstance(k.get('laeufe'), list) or not k['laeufe']:
        raise LaufFehler('laeufe_fehlen: die Datei braucht „harness_laeufe: laeufe:“ mit mindestens einem Typ')
    out = {}
    for n, t in enumerate(k['laeufe'], 1):
        if not isinstance(t, dict):
            raise LaufFehler(f'lauf_{n}_kein_eintrag')
        lid = t.get('id')
        if not isinstance(lid, str) or not ID.fullmatch(lid):
            raise LaufFehler(f'lauf_{n}_id_ungueltig: kleine Buchstaben, Ziffern und Unterstrich')
        if lid in out:
            raise LaufFehler(f'lauf_{lid}_doppelt')
        argv = t.get('argv')
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
            raise LaufFehler(f'lauf_{lid}_argv_ungueltig: eine Liste von Texten')
        if not PROGRAMM.fullmatch(argv[0]):
            raise LaufFehler(f'lauf_{lid}_programm_ungueltig: ein Programmname ohne Pfad und Platzhalter')
        parameter = t.get('parameter') or {}
        if not isinstance(parameter, dict):
            raise LaufFehler(f'lauf_{lid}_parameter_ungueltig')
        benutzt = set()
        for a in argv[1:]:
            if '{' in a or '}' in a:
                m = PLATZHALTER.fullmatch(a)
                if not m:
                    raise LaufFehler(f'lauf_{lid}_platzhalter_ungueltig: „{a}“ – ein Platzhalter steht als ganzes Element, {{name}}')
                if m.group(1) not in parameter:
                    raise LaufFehler(f'lauf_{lid}_parameter_fehlt: „{m.group(1)}“ steht im argv, aber nicht unter parameter')
                benutzt.add(m.group(1))
        if '{' in argv[0] or '}' in argv[0]:
            raise LaufFehler(f'lauf_{lid}_programm_ungueltig')
        normal = {}
        for name, p in parameter.items():
            if not isinstance(name, str) or not ID.fullmatch(name) or not isinstance(p, dict):
                raise LaufFehler(f'lauf_{lid}_parameter_{name}_ungueltig')
            if name not in benutzt:
                raise LaufFehler(f'lauf_{lid}_parameter_{name}_unbenutzt: er steht nicht im argv')
            muster = p.get('muster')
            try:
                re.compile(muster)
            except (TypeError, re.error):
                raise LaufFehler(f'lauf_{lid}_parameter_{name}_muster_ungueltig') from None
            vorgabe = p.get('vorgabe')
            if vorgabe is not None:
                vorgabe = str(vorgabe)
            normal[name] = {'muster': muster, 'vorgabe': vorgabe, 'mehrere': _bool(p.get('mehrere', False), f'lauf_{lid}_mehrere')}
            if vorgabe is not None:
                for stueck in (vorgabe.split() if normal[name]['mehrere'] else [vorgabe]):
                    if not re.fullmatch(muster, stueck):
                        raise LaufFehler(f'lauf_{lid}_parameter_{name}_vorgabe_passt_nicht_zum_muster')
        ordner = t.get('ordner', '.')
        teile = str(ordner).replace('\\', '/').split('/')
        if not isinstance(ordner, str) or '..' in teile or re.match(r'^([A-Za-z]:|/)', ordner):
            raise LaufFehler(f'lauf_{lid}_ordner_ungueltig: relativ zur Projektwurzel, ohne „..“')
        gpu = t.get('gpu', 'keine')
        if gpu not in GPU:
            raise LaufFehler(f'lauf_{lid}_gpu_unbekannt: {", ".join(GPU)}')
        braucht_modell = _bool(t.get('braucht_modell', False), f'lauf_{lid}_braucht_modell')
        modell = t.get('modell')
        if braucht_modell and (not isinstance(modell, str) or not modell.strip()):
            raise LaufFehler(f'lauf_{lid}_modell_fehlt: wer ein Modell braucht, nennt es (Rezept oder Rolle)')
        fortschritt = t.get('fortschritt')
        if fortschritt is not None:
            art = fortschritt.get('art') if isinstance(fortschritt, dict) else None
            if art not in FORTSCHRITT:
                raise LaufFehler(f'lauf_{lid}_fortschritt_art_unbekannt: {", ".join(FORTSCHRITT)}')
            regex = fortschritt.get('regex')
            if FORTSCHRITT[art]:
                try:
                    if re.compile(regex).groups < FORTSCHRITT[art]:
                        raise LaufFehler(f'lauf_{lid}_fortschritt_gruppen: „{art}“ braucht {FORTSCHRITT[art]} Gruppe(n)')
                except (TypeError, re.error):
                    raise LaufFehler(f'lauf_{lid}_fortschritt_regex_ungueltig') from None
            fortschritt = {'art': art, 'regex': regex if FORTSCHRITT[art] else None}
        zeit = t.get('zeitlimit_min', 60)
        if not isinstance(zeit, int) or isinstance(zeit, bool) or not 1 <= zeit <= ZEITLIMIT_MAX_MIN:
            raise LaufFehler(f'lauf_{lid}_zeitlimit_ungueltig: 1 bis {ZEITLIMIT_MAX_MIN} Minuten')
        out[lid] = {'id': lid, 'name': str(t.get('name') or lid), 'argv': list(argv), 'ordner': ordner, 'parameter': normal, 'gpu': gpu,
                    'modell_weg': _bool(t.get('modell_weg', gpu == 'exklusiv'), f'lauf_{lid}_modell_weg'), 'braucht_modell': braucht_modell,
                    'modell': modell.strip() if isinstance(modell, str) else None, 'fortschritt': fortschritt, 'zeitlimit_min': zeit}
    return out


def laden(datei: Path = LAEUFE_DATEI):
    """{laeufe: {id: Typ}, datei} – ungültig oder nicht lesbar → LaufFehler (kein stiller Rückfall, kein Lauf ohne gültige Typen)."""
    try:
        doc = yaml.safe_load(Path(datei).read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise LaufFehler(f'datei_unlesbar: {Path(datei).name}: {type(exc).__name__}') from exc
    return {'laeufe': pruefen(doc), 'datei': str(datei)}


def _werte(name, p, wert):
    """Die geprüften Stücke eines Parameters (bei `mehrere` mehrere)."""
    if isinstance(wert, bool) or not isinstance(wert, (str, int)):
        raise LaufFehler(f'parameter_{name}_ungueltig: ein Text')
    text = str(wert).strip()
    stuecke = text.split() if p['mehrere'] else [text]
    if not stuecke or (p['mehrere'] and len(stuecke) > MEHRERE_MAX):
        raise LaufFehler(f'parameter_{name}_ungueltig: ' + (f'höchstens {MEHRERE_MAX} Werte' if stuecke else 'leer'))
    for s in stuecke:
        if not s or any(c in VERBOTEN or c.isspace() for c in s) or s.startswith('-') or '..' in s.replace('\\', '/').split('/'):
            raise LaufFehler(f'parameter_{name}_ungueltig: „{s[:40]}“ enthält ein unerlaubtes Zeichen')
        if not re.fullmatch(p['muster'], s):
            raise LaufFehler(f'parameter_{name}_muster: „{s[:40]}“ erfüllt das Muster des Laufs nicht')
    return stuecke


def argv_bauen(typ, parameter, wurzel):
    """{argv, ordner, ziel, bindung, typ} für einen Aufruf – oder LaufFehler. `ziel` ist die Lauf-ID (Einstufung), `bindung` hängt das Guard-Token an genau diesen Lauf
    mit genau diesen Argumenten. Programm `python` ersetzt der Starter durch den Python dieser Runtime (wie bei `befehl`)."""
    parameter = {} if parameter is None else parameter
    if not isinstance(parameter, dict):
        raise LaufFehler('parameter_kein_objekt')
    unbekannt = sorted(set(parameter) - set(typ['parameter']))
    if unbekannt:
        raise LaufFehler(f'parameter_unbekannt: {", ".join(map(str, unbekannt))}')
    werte = {}
    for name, p in typ['parameter'].items():
        wert = parameter.get(name, p['vorgabe'])
        if wert is None:
            raise LaufFehler(f'parameter_fehlt: {name}')
        werte[name] = _werte(name, p, wert)
    argv = [typ['argv'][0]]
    for a in typ['argv'][1:]:
        m = PLATZHALTER.fullmatch(a)
        argv += werte[m.group(1)] if m else [a]
    wurzel_p = Path(wurzel).resolve()
    ordner = (wurzel_p / typ['ordner']).resolve()
    try:
        ordner.relative_to(wurzel_p)
    except ValueError:
        raise LaufFehler('ordner_ausserhalb: der Ordner des Laufs liegt nicht im Projekt') from None
    if not ordner.is_dir():
        raise LaufFehler('ordner_fehlt')
    return {'argv': argv, 'ordner': ordner, 'ziel': typ['id'], 'bindung': {'lauf': typ['id'], 'argv': argv, 'ordner': typ['ordner']}, 'typ': typ}


# ======================================================================== Teil 2: Starter, Register, Wiederanbinden, Stopp (N7)
STATUS_ENDE = ('ok', 'fehler', 'gestoppt', 'abgebrochen', 'verloren', 'zeitlimit')
LAUF_ID = re.compile(r'L-[0-9A-F]{8}')
MAX_LAUFEND = 3                 # je Projekt
HUELLE = Path(__file__).resolve().parent / 'lauf_huelle.py'
LOG_TAIL = 40
FORTSCHRITT_ABSTAND_S = 2.0     # Ereignisse `fortschritt` höchstens so oft


def jetzt_text():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def fortschritt_aus(zeilen, regel):
    """{prozent, text} oder None – siehe `lauf_fortschritt` (Referenz von Claude, ersetzt durch den SEDRA-Bau N8, sobald übernommen). Wirft nie."""
    from .lauf_fortschritt import fortschritt_aus as echt
    return echt(zeilen, regel)


def _pid_lebt(pid, start):
    from . import herkunft
    if not pid or pid not in herkunft.prozess_tabelle():
        return False
    ist = herkunft.startzeit(pid)
    return start is None or ist is None or ist == start


class Laeufe:
    """Das Register der Läufe, die die Harness gestartet hat: `<projekt>/runtime_data/harness/laeufe/L-<8 Hex>/{lauf.json, ausgabe.log, ende.json, stopp.txt}`.
    `melden(name, daten)` und `audit(event, payload)` sind Rückrufe. Ein Lauf überlebt den Neustart des Servers (Hülle); `wiederanbinden` findet ihn wieder
    und trägt ihn erneut im Herkunfts-Register ein. Ein Lauf wird nie als `ok` gemeldet, den niemand enden sah: ohne `ende.json` und ohne Prozess heißt er `verloren`."""

    def __init__(self, ordner: Path, *, typen, projekt_id='p', audit=None, melden=None, starten=None, clock=time.monotonic):
        self.ordner = Path(ordner)
        self.typen, self.projekt_id, self.audit, self.melden, self.clock = typen, projekt_id, audit, melden, clock
        self._starten = starten or self._huelle_starten
        self._sperre = threading.RLock()
        self._zuletzt_gemeldet = {}
        self._thread = None
        self.wiederanbinden()

    # ---- Dateien
    def _dir(self, lid):
        if not isinstance(lid, str) or not LAUF_ID.fullmatch(lid):
            raise KeyError('lauf_unbekannt')
        return self.ordner / lid

    def _schreiben(self, d, lauf):
        tmp = d / 'lauf.tmp'
        tmp.write_text(json.dumps(lauf, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, d / 'lauf.json')
        return lauf

    def _roh(self, lid):
        d = self._dir(lid)
        try:
            return json.loads((d / 'lauf.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise KeyError('lauf_unbekannt') from None

    def _sagen(self, event, lauf, extra=None):
        payload = {'lauf_id': lauf['id'], 'lauf': lauf['lauf'], 'status': lauf['status'], 'sitzung_id': lauf.get('sitzung_id'),
                   'aufgabe_id': lauf.get('aufgabe_id')} | (extra or {})
        for ziel, args in ((self.audit, (event, payload)),):
            if ziel is not None:
                try: ziel(*args)
                except Exception: pass

    def _melden(self, lauf, zustand):
        if self.melden is not None:
            try:
                self.melden('harness.lauf', {'id': lauf['id'], 'lauf': lauf['lauf'], 'name': lauf.get('name'), 'zustand': zustand, 'status': lauf['status'],
                                             'prozent': (lauf.get('fortschritt') or {}).get('prozent'), 'text': (lauf.get('fortschritt') or {}).get('text'),
                                             'modell_weg': lauf.get('modell_weg'), 'sitzung_id': lauf.get('sitzung_id')})
            except Exception:
                pass

    # ---- Starten
    def laufende(self):
        return [l for l in self.alle() if l['status'] == 'laeuft']

    def belegt(self):
        """Der laufende Lauf, der dem Gespräch das Modell wegnimmt (K13) – oder None."""
        return next((l for l in self.laufende() if l.get('modell_weg')), None)

    def starten(self, typ, argv_info, *, sitzung_id=None, antwort_id=None, aufgabe_id=None, karte_id=None, parameter=None, andere_antworten=0):
        """Startet einen Lauf. Grenzen: höchstens MAX_LAUFEND je Projekt, `exklusiv` höchstens einer und nur ohne andere laufende Antwort."""
        with self._sperre:
            laufend = self.laufende()
            if len(laufend) >= MAX_LAUFEND:
                raise LaufFehler(f'zu_viele_laeufe: höchstens {MAX_LAUFEND} Läufe gleichzeitig')
            if typ['gpu'] == 'exklusiv':
                if any(l.get('gpu') == 'exklusiv' for l in laufend):
                    raise LaufFehler('exklusiv_belegt: es läuft schon ein exklusiver Lauf')
                if andere_antworten:
                    raise LaufFehler('exklusiv_andere_antwort_laeuft: ein exklusiver Lauf startet nur, wenn keine andere Antwort läuft')
            while True:
                lid = 'L-' + secrets.token_hex(4).upper()
                if not self._dir(lid).exists():
                    break
            d = self._dir(lid)
            d.mkdir(parents=True)
            argv = list(argv_info['argv'])
            if argv[0].lower() in ('python', 'python.exe', 'py', 'pythonw'):
                argv[0] = sys.executable
            lauf = {'id': lid, 'lauf': typ['id'], 'name': typ['name'], 'parameter': parameter or {}, 'argv': argv, 'ordner_abs': str(argv_info['ordner']),
                    'zeitlimit_min': typ['zeitlimit_min'], 'gpu': typ['gpu'], 'modell_weg': typ['modell_weg'], 'sitzung_id': sitzung_id,
                    'antwort_id': antwort_id, 'aufgabe_id': aufgabe_id, 'karte_id': karte_id, 'projekt': self.projekt_id, 'pid': None, 'start_zeit_pid': None,
                    'gestartet': jetzt_text(), 'ende': None, 'exit': None, 'status': 'laeuft', 'grund': None, 'fortschritt': None,
                    'fortschritt_regel': typ.get('fortschritt')}
            self._schreiben(d, lauf)
            try:
                lauf['pid'], lauf['start_zeit_pid'] = self._starten(d)
            except OSError as exc:
                lauf.update(status='fehler', grund=f'start_fehlgeschlagen: {type(exc).__name__}', ende=jetzt_text())
                self._schreiben(d, lauf)
                self._sagen('HARNESS_LAUF_ENDE', lauf)
                raise LaufFehler('start_fehlgeschlagen') from exc
            self._schreiben(d, lauf)
        self._sagen('HARNESS_LAUF_START', lauf, {'argv': lauf['argv'][1:], 'pid': lauf['pid'], 'karte_id': karte_id})
        self._melden(lauf, 'gestartet')
        self._beobachten()
        return lauf

    def _huelle_starten(self, d):
        """Die Hülle losgelöst starten (überlebt den Server); gibt (PID, Startzeit) zurück. Die Hülle trägt sich im Herkunfts-Register ein."""
        from . import herkunft
        if os.name == 'nt':
            kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'DETACHED_PROCESS', 0x8) | getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)}
        else:
            kw = {'start_new_session': True}
        from .befehl import umgebung
        proc = subprocess.Popen([sys.executable, str(HUELLE), str(d)], cwd=str(d), env=umgebung(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        start = herkunft.startzeit(proc.pid)
        herkunft.REGISTER.registrieren(proc.pid, start)
        return proc.pid, start

    # ---- Lesen und Nachführen
    def alle(self):
        if not self.ordner.is_dir():
            return []
        out = []
        for d in sorted(self.ordner.glob('L-*')):
            if d.is_dir() and LAUF_ID.fullmatch(d.name):
                try:
                    out.append(self.laden(d.name))
                except KeyError:
                    continue
        return sorted(out, key=lambda l: l.get('gestartet') or '')

    def laden(self, lid):
        """Der Lauf, nachgeführt: Ende lesen, Fortschritt aus dem Log, `verloren`, wenn niemand ihn enden sah."""
        with self._sperre:
            lauf = self._roh(lid)
            if lauf['status'] != 'laeuft':
                return lauf
            d = self._dir(lid)
            ende = self._ende_lesen(d)
            geaendert = None
            if ende is not None:
                st = {'ok': 'ok', 'fehler': 'fehler', 'gestoppt': 'abgebrochen' if (d / 'abgebrochen.txt').exists() else 'gestoppt', 'zeitlimit': 'zeitlimit',
                      'start_fehlgeschlagen': 'fehler'}.get(ende.get('grund'), 'fehler')
                lauf.update(status=st, exit=ende.get('exit'), ende=ende.get('zeit') or jetzt_text(), grund=ende.get('grund'))
                geaendert = 'ende'
            elif not _pid_lebt(lauf.get('pid'), lauf.get('start_zeit_pid')):
                lauf.update(status='verloren', ende=jetzt_text(), grund='Prozess weg, kein Ende gemeldet')
                geaendert = 'ende'
            fort = fortschritt_aus(self.tail(lid, 200, roh=True), lauf.get('fortschritt_regel'))
            if fort is not None and fort != lauf.get('fortschritt'):
                lauf['fortschritt'] = fort
                geaendert = geaendert or 'fortschritt'
            if geaendert:
                self._schreiben(d, lauf)
                if geaendert == 'ende':
                    self._sagen('HARNESS_LAUF_ENDE', lauf, {'exit': lauf.get('exit'), 'grund': lauf.get('grund')})
                    self._melden(lauf, 'ende')
                else:
                    jetzt = self.clock()
                    if jetzt - self._zuletzt_gemeldet.get(lid, -1e9) >= FORTSCHRITT_ABSTAND_S:
                        self._zuletzt_gemeldet[lid] = jetzt
                        self._melden(lauf, 'fortschritt')
            return lauf

    @staticmethod
    def _ende_lesen(d):
        try:
            return json.loads((d / 'ende.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def tail(self, lid, n=LOG_TAIL, roh=False):
        """Die letzten n Zeilen der Ausgabe. Das ist **fremder Inhalt** (Daten, keine Anweisung) – der Aufrufer kennzeichnet ihn."""
        pfad = self._dir(lid) / 'ausgabe.log'
        try:
            with open(pfad, 'rb') as f:
                f.seek(0, os.SEEK_END)
                groesse = f.tell()
                f.seek(max(0, groesse - 64_000))
                text = f.read().decode('utf-8', errors='replace')
        except OSError:
            return []
        zeilen = text.splitlines()
        return zeilen[-n:]

    # ---- Stoppen
    def stoppen(self, lid, grund='gestoppt', status_wunsch='gestoppt', warten_s=10):
        """Stoppt einen laufenden Lauf: `stopp.txt` (die Hülle beendet den Baum), nach `warten_s` zur Sicherheit der Baum der Hülle. Gibt den Lauf zurück."""
        with self._sperre:
            lauf = self._roh(lid)
            if lauf['status'] != 'laeuft':
                raise LaufFehler('nicht_laufend')
            d = self._dir(lid)
            if status_wunsch == 'abgebrochen':
                (d / 'abgebrochen.txt').write_text(str(grund)[:300], encoding='utf-8')
            (d / 'stopp.txt').write_text(str(grund)[:300], encoding='utf-8')
        self._sagen('HARNESS_LAUF_STOPP', lauf, {'grund': grund})
        ende = self.clock() + warten_s
        while self.clock() < ende:
            if (d / 'ende.json').exists():
                break
            time.sleep(0.1)
        else:
            self._baum_beenden(lauf.get('pid'))
            (d / 'ende.json').exists() or (d / 'ende.json').write_text(json.dumps({'exit': None, 'grund': 'gestoppt', 'zeit': jetzt_text()}), encoding='utf-8')
        return self.laden(lid)

    @staticmethod
    def _baum_beenden(pid):
        if not pid:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True)
        else:
            try: os.killpg(pid, 9)
            except OSError: pass

    # ---- Neustart, Beobachter
    def wiederanbinden(self):
        """Nach einem Start des Servers: laufende Läufe wiederfinden (Herkunfts-Register), tote ohne Ende als `verloren` markieren."""
        from . import herkunft
        if not self.ordner.is_dir():
            return
        for lauf in self.alle():                      # `alle` führt jeden nach: Ende lesen, `verloren`
            if lauf['status'] == 'laeuft' and lauf.get('pid'):
                herkunft.REGISTER.registrieren(lauf['pid'], lauf.get('start_zeit_pid'))
        if self.laufende():
            self._beobachten()

    def _beobachten(self):
        """Ein Hintergrundfaden führt die laufenden Läufe nach (Fortschritt, Ende, Ereignis `harness.lauf`), solange es welche gibt."""
        with self._sperre:
            if self._thread is not None and self._thread.is_alive():
                return

            def lauf():
                while True:
                    time.sleep(1.0)
                    try:
                        if not self.laufende():
                            return
                    except Exception:
                        return

            self._thread = threading.Thread(target=lauf, name='harness-laeufe', daemon=True)
            self._thread.start()
