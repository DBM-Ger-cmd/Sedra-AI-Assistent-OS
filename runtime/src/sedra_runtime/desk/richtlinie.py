"""Die Richtlinie des Betreibers (SPEC_APPS_v1_AM7_UNTERNEHMEN, Betriebsart A: je Person ein Rechner mit eigener SEDRA, der Betreiber verteilt eine Datei).

`local_config/richtlinie.yaml` legt fest: die Rolle dieser Installation, die verantwortliche Person, die erlaubten Apps (Positivliste), die erlaubten Shells, Obergrenzen, erlaubte Anbieter und Agenten,
sichtbare Grundfunktionen je Rolle und die Aufbewahrung. Ist sie aktiv, gilt sie **über** der Gewährung der Person (AM7-05): was nicht darauf steht, wird nicht geladen.

Ehrliche Grenze (AM7 §2): Gegen eine Person mit Administratorrechten am eigenen Rechner kann SEDRA die Richtlinie nicht durchsetzen; ob die Datei vor ihr geschützt ist, entscheidet das Betriebssystem.
SEDRA bietet keine Route und keinen Antrag, sie zu ändern (AM7-06); es erkennt eine Änderung am Hash und protokolliert sie. Eine KI-Kennzeichnung der Entwürfe (R-14) kann die Richtlinie nicht abschalten:
das Feld gibt es nicht (AM7-16), ein unbekanntes Feld macht die Richtlinie ungültig. Rechtliche Begriffe sind Einordnung, keine Rechtsprüfung.

Reiner Baustein: lesen, prüfen, fragen. Wer ihn ruft (Gateway, Hub), setzt die Folgen durch."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

ROLLEN = ('betreiber', 'pruefung', 'sachbearbeitung')          # AM7-01: feste Rollen in v1
OBERGRENZEN = ('community', 'dienste', 'zellen_fremd', 'ereignisse_inhalt')
GRUNDFUNKTIONEN = ('entscheidungen', 'gespraech', 'aufgaben', 'logbuch', 'modus_grenzen', 'module_berechtigungen', 'einstellungen_zustand')
DATEI = Path('local_config') / 'richtlinie.yaml'
HASH_DATEI = Path('runtime_data') / 'richtlinie' / 'hash.txt'
ID = re.compile(r'^[a-z0-9-]{2,40}$')
KEYS = {'schema', 'rolle', 'person', 'apps', 'shells', 'obergrenzen', 'anbieter', 'agenten', 'grundfunktionen_sichtbar', 'aufbewahrung', 'gespraech'}
AUFBEWAHRUNG = ('gespraeche_tage', 'entwuerfe_stunden', 'audit_export_tage')
OEFFENTLICH = ('system.state', 'model.changed', 'desk.resync', 'tools.refresh', 'slot.changed')


def pfad(project_root) -> Path:
    return Path(project_root) / DATEI


def hash_von(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def pruefen(doc) -> tuple[dict | None, list]:
    """(normalisierte Richtlinie, Fehler). Streng: ein unbekanntes Feld, eine falsche Form oder ein unbekannter Wert macht die Richtlinie ungültig."""
    if not isinstance(doc, dict) or not isinstance(doc.get('richtlinie'), dict):
        return None, ['richtlinie_mapping_fehlt']
    r = doc['richtlinie']
    fehler = []
    for k in sorted(set(r) - KEYS):
        fehler.append('richtlinie_unbekanntes_feld:' + str(k))               # auch `kennzeichnung`: die KI-Kennzeichnung (R-14) lässt sich nicht abschalten (AM7-16)
    if r.get('schema') != 1:
        fehler.append('richtlinie_schema_ungueltig')
    if r.get('rolle') not in ROLLEN:
        fehler.append('richtlinie_rolle_ungueltig')
    person = r.get('person')
    if not isinstance(person, str) or not 1 <= len(' '.join(person.split())) <= 80:
        fehler.append('richtlinie_person_ungueltig')
    apps = r.get('apps', [])
    norm_apps = []
    if not isinstance(apps, list):
        fehler.append('richtlinie_apps_ungueltig')
    else:
        for a in apps:
            if not isinstance(a, dict) or set(a) - {'id', 'version', 'sha256'} or not isinstance(a.get('id'), str) or not ID.match(a['id']):
                fehler.append('richtlinie_app_ungueltig')
                continue
            if 'version' in a and not isinstance(a['version'], str):
                fehler.append('richtlinie_app_ungueltig')
                continue
            if 'sha256' in a and not (isinstance(a['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', a['sha256'])):
                fehler.append('richtlinie_app_ungueltig')
                continue
            norm_apps.append({'id': a['id'], 'version': a.get('version'), 'sha256': a.get('sha256')})
    shells = r.get('shells', {})
    norm_shells = {'erlaubt': None, 'start': None}
    if not isinstance(shells, dict) or set(shells) - {'erlaubt', 'start'}:
        fehler.append('richtlinie_shells_ungueltig')
    else:
        erlaubt = shells.get('erlaubt')
        if erlaubt is not None and (not isinstance(erlaubt, list) or not all(isinstance(x, str) and ID.match(x) for x in erlaubt)):
            fehler.append('richtlinie_shells_ungueltig')
        else:
            norm_shells['erlaubt'] = list(erlaubt) if erlaubt is not None else None
        start = shells.get('start')
        if start is not None and (not isinstance(start, str) or not ID.match(start) or (norm_shells['erlaubt'] is not None and start not in norm_shells['erlaubt'])):
            fehler.append('richtlinie_shell_start_ungueltig')
        else:
            norm_shells['start'] = start
    ober = r.get('obergrenzen', {})
    norm_ober = {}
    if not isinstance(ober, dict) or set(ober) - set(OBERGRENZEN) or not all(v in ('verboten', 'erlaubt') for v in ober.values()):
        fehler.append('richtlinie_obergrenzen_ungueltig')
    else:
        norm_ober = {k: ober.get(k, 'erlaubt') for k in OBERGRENZEN}
    for feld in ('anbieter', 'agenten'):
        v = r.get(feld, {})
        if not isinstance(v, dict) or set(v) - {'erlaubt'} or (v.get('erlaubt') is not None and not (isinstance(v['erlaubt'], list) and all(isinstance(x, str) for x in v['erlaubt']))):
            fehler.append(f'richtlinie_{feld}_ungueltig')
    gf = r.get('grundfunktionen_sichtbar', {})
    if not isinstance(gf, dict) or set(gf) - set(ROLLEN) or not all(isinstance(v, list) and set(v) <= set(GRUNDFUNKTIONEN) for v in gf.values()):
        fehler.append('richtlinie_grundfunktionen_ungueltig')
    auf = r.get('aufbewahrung', {})
    if not isinstance(auf, dict) or set(auf) - set(AUFBEWAHRUNG) or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in auf.values()):
        fehler.append('richtlinie_aufbewahrung_ungueltig')
    gespraech = r.get('gespraech', 'nur_gateway')                        # AM7-E4: Vorgabe: nur der Gateway-Ablauf
    if gespraech not in ('nur_gateway', 'frei'):
        fehler.append('richtlinie_gespraech_ungueltig')
    if fehler:
        return None, fehler
    return {'rolle': r['rolle'], 'person': ' '.join(person.split()), 'apps': norm_apps, 'shells': norm_shells, 'obergrenzen': norm_ober,
            'anbieter': (r.get('anbieter') or {}).get('erlaubt'), 'agenten': (r.get('agenten') or {}).get('erlaubt'),
            'grundfunktionen_sichtbar': {k: list(v) for k, v in gf.items()}, 'aufbewahrung': dict(auf), 'gespraech': gespraech}, []


class Richtlinie:
    """Die geladene Richtlinie. `aktiv` ist nur wahr, wenn die Datei da und gültig ist; eine ungültige Datei (`fehler`) lässt SEDRA nicht stillschweigend offen: der Hub meldet es."""

    def __init__(self, daten=None, hash=None, fehler=None, vorhanden=False):
        self.daten, self.hash, self.fehler, self.vorhanden = daten, hash, list(fehler or []), vorhanden

    @property
    def aktiv(self) -> bool:
        return self.daten is not None

    @property
    def rolle(self):
        return (self.daten or {}).get('rolle')

    @property
    def person(self):
        return (self.daten or {}).get('person')

    # ---- Fragen (AM7-05)
    def app_erlaubt(self, app_id, version=None, sha256=None):
        """None = erlaubt, sonst der Grund (`richtlinie_app_nicht_erlaubt`, `richtlinie_app_version`, `richtlinie_app_hash`)."""
        if not self.aktiv:
            return None
        for a in self.daten['apps']:
            if a['id'] != app_id:
                continue
            if a['version'] and version and not _version_passt(a['version'], version):
                return 'richtlinie_app_version'
            if a['sha256'] and sha256 and a['sha256'] != sha256:
                return 'richtlinie_app_hash'
            return None
        return 'richtlinie_app_nicht_erlaubt'

    def shell_erlaubt(self, shell_id):
        if not self.aktiv or self.daten['shells']['erlaubt'] is None:
            return True
        return shell_id in self.daten['shells']['erlaubt']

    def verboten(self, obergrenze):
        return self.aktiv and self.daten['obergrenzen'].get(obergrenze) == 'verboten'

    def start_shell(self):
        return (self.daten or {}).get('shells', {}).get('start')

    def anbieter_erlaubt(self, anbieter):
        if not self.aktiv or self.daten['anbieter'] is None:
            return True
        return anbieter in self.daten['anbieter']

    def grundfunktionen(self):
        """Die Grundfunktionen, die diese Rolle sieht; ohne Angabe alle."""
        if not self.aktiv:
            return list(GRUNDFUNKTIONEN)
        return list(self.daten['grundfunktionen_sichtbar'].get(self.rolle, GRUNDFUNKTIONEN))

    def beschreibung(self):
        """Für Anzeige und Export: nichts Geheimes, alles aus der Datei."""
        return {'aktiv': self.aktiv, 'vorhanden': self.vorhanden, 'hash': self.hash, 'fehler': list(self.fehler), **(self.daten or {})}


def _version_passt(bereich, version):
    """'>=1.0 <2' gegen 'x.y.z' (rein, wie needs.ui): Teile durch Leerzeichen, alle müssen passen."""
    try:
        have = tuple(int(x) for x in str(version).split('.')[:3])
        for teil in str(bereich).split():
            m = re.fullmatch(r'(>=|<=|>|<|==)?(\d+)(?:\.(\d+))?(?:\.(\d+))?', teil)
            if not m:
                return False
            op = m.group(1) or '=='
            want = tuple(int(x) for x in m.groups()[1:] if x is not None)
            cmp = have[:len(want)]
            ok = {'>=': cmp >= want, '<=': cmp <= want, '>': cmp > want, '<': cmp < want, '==': cmp == want}[op]
            if not ok:
                return False
        return True
    except ValueError:
        return False


def laden(project_root) -> Richtlinie:
    """Liest `local_config/richtlinie.yaml`. Keine Datei: nicht vorhanden (Einzelplatzbetrieb wie heute). Eine kaputte oder ungültige Datei: vorhanden, nicht aktiv, mit den Fehlern."""
    p = pfad(project_root)
    try:
        roh = p.read_bytes()
    except FileNotFoundError:
        return Richtlinie()
    except OSError as exc:
        return Richtlinie(fehler=['richtlinie_nicht_lesbar:' + type(exc).__name__], vorhanden=True)
    h = hash_von(roh)
    try:
        doc = yaml.safe_load(roh.decode('utf-8'))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return Richtlinie(hash=h, fehler=['richtlinie_nicht_lesbar:' + type(exc).__name__], vorhanden=True)
    daten, fehler = pruefen(doc)
    return Richtlinie(daten, h, fehler, vorhanden=True)


def aenderung_pruefen(project_root, richtlinie: Richtlinie, audit=None):
    """AM7-06: erkennt eine Änderung der Datei am Hash und protokolliert `RICHTLINIE_GEAENDERT {alt_hash, neu_hash}` (ohne Inhalt). Rückgabe: (alt, neu) oder None."""
    p = Path(project_root) / HASH_DATEI
    try:
        alt = p.read_text(encoding='utf-8').strip() or None
    except OSError:
        alt = None
    neu = richtlinie.hash
    if alt == neu:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(neu or '', encoding='utf-8')
    if audit is not None:
        try:
            audit('RICHTLINIE_GEAENDERT', {'alt_hash': alt, 'neu_hash': neu})
        except Exception:
            pass
    return alt, neu
