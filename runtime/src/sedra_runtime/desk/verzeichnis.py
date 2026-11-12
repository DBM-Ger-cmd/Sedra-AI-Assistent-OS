"""Das Verzeichnis aller Erweiterungen (SPEC_APPS_v1_AM8_VERZEICHNIS AM8-01 bis AM8-04): die acht Erweiterungswege (E1 bis E8) bleiben, wie sie sind – hier steht nur eine gemeinsame Sicht.

Nur lesen. Je Quelle eine kleine Lesefunktion; ist eine Quelle nicht lesbar, steht ihre Art mit `zustand: unbekannt` und dem Grund in der Liste – nichts fehlt still (AM8-02).
Die Wirkungsklassen sind eine Anzeigesprache (`runtime/config/wirkungsklassen.yaml`); sie ersetzen keine Entscheidung."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ARTEN = ('werkzeug', 'shell', 'kern_erweiterung', 'architektur_modul', 'faehigkeit', 'agenten_vorlage', 'harness_vorlage', 'daten')
HERKUENFTE = ('paket', 'captain', 'eingebaut', 'selbst_gebaut', 'importiert')
KLASSEN_DATEI = Path(__file__).resolve().parents[3] / 'config' / 'wirkungsklassen.yaml'
REIHENFOLGE = ('read_only', 'proposal_only', 'preview', 'reversible_write', 'destructive_write', 'external_side_effect', 'privileged')


def klassen():
    """AM8-09: die Tabelle der Wirkungsklassen (Bedeutung, Lesehilfe) aus der Datei; fehlt sie, ein leeres Wörterbuch mit Grund."""
    try:
        d = yaml.safe_load(KLASSEN_DATEI.read_text(encoding='utf-8'))['wirkungsklassen']['klassen']
        return {k: dict(v) for k, v in d.items()}
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        return {}


def _eintrag(art, id, name=None, herkunft='paket', vertrauen=None, version=None, faehigkeiten=None, abhaengigkeiten=None, zustand='aktiv', grund=None, stelle=None):
    return {'art': art, 'id': str(id), 'name': name or str(id), 'herkunft': herkunft, 'vertrauen': vertrauen, 'version': version,
            'faehigkeiten': faehigkeiten or [], 'abhaengigkeiten': abhaengigkeiten or [], 'zustand': zustand, 'grund': grund, 'stelle': stelle}


def _unbekannt(art, grund):
    return [_eintrag(art, art, name=f'Quelle „{art}“ nicht lesbar', herkunft='paket', zustand='unbekannt', grund=str(grund)[:200])]


def wirkung_der_faehigkeit(f):
    """Die Wirkungsklasse einer Fähigkeit einer App (AM3: lesen:, verb:, ereignis:, zelle:, ablage:, dienst:) – Anzeige."""
    art, _, rest = str(f).partition(':')
    if art in ('lesen', 'ereignis', 'zelle'):
        return 'read_only'
    if art == 'verb':
        from .rechte_diff import VERBEN_NIE
        return 'privileged' if rest in VERBEN_NIE else 'reversible_write'
    if art == 'ablage':
        return 'reversible_write'
    if art == 'dienst':
        return 'external_side_effect' if rest == 'host' else 'reversible_write'
    return 'privileged'


def wirkung_der_route(route):
    return 'read_only' if str(route).startswith('GET ') else 'reversible_write'


def _herkunft(man):
    if man.get('origin') == 'package':
        return 'paket'
    return {'CAPTAIN': 'captain', 'SEDRA_BUILT': 'selbst_gebaut'}.get(man.get('trust'), 'eingebaut')


# ---- E1/E2: Werkzeuge und Shells
def _werkzeuge_und_shells(hub):
    erg = []
    for art, kind in (('werkzeug', 'tools'), ('shell', 'shells')):
        try:
            ok, abgelehnt = hub.gateway._load(kind)
        except Exception as exc:
            erg += _unbekannt(art, exc)
            continue
        aus = set(hub.gateway.registry.config().get('disabled') or []) if art == 'werkzeug' else set()
        for mid, (_ordner, man) in sorted(ok.items()):
            if man.get('faehigkeiten'):                                         # eine fremde App mit `rechte` (AM3)
                f = [{'name': x, 'wirkungsklasse': wirkung_der_faehigkeit(x)} for x in man['faehigkeiten']]
            else:
                f = [{'name': r, 'wirkungsklasse': wirkung_der_route(r)} for r in (man.get('api') or [])]
            dep = [f'app:{k}' for k in (man.get('needs_apps') or {})] + ([f'shell:{man["shell_app"]}'] if man.get('shell_app') else [])
            erg.append(_eintrag(art, mid, man.get('name'), _herkunft(man), man.get('trust'), man.get('version'), f, dep, 'aus' if mid in aus else 'aktiv',
                                stelle='Module' if art == 'werkzeug' else 'Module → Shells'))
        for r in abgelehnt:
            erg.append(_eintrag(art, r['id'], r['id'], 'eingebaut' if r.get('origin') == 'local' else 'paket', zustand='abgewiesen', grund=', '.join(r.get('reasons') or [])[:200]))
    return erg


# ---- E3: Kern-Erweiterungen (desk/extensions.MODULES)
def _kern(hub):
    from . import extensions
    erg = []
    for name in extensions.MODULES:
        try:
            gefunden = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError) as exc:
            erg.append(_eintrag('kern_erweiterung', name, name, zustand='unbekannt', grund=str(exc)))
            continue
        erg.append(_eintrag('kern_erweiterung', name, name.rsplit('.', 1)[-1], 'paket', 'CORE', zustand='aktiv' if gefunden else 'abgewiesen', grund=None if gefunden else 'Modul nicht gefunden',
                            faehigkeiten=[{'name': 'registriert Objekttypen und Verben im Desk', 'wirkungsklasse': 'reversible_write'}]))
    return erg


# ---- E4: Architektur-Module
def _architektur(hub):
    from ..core.registry import Registry
    r = Registry(hub.architecture_root)
    r.load()
    erg = []
    for mid, meta in sorted(r.modules.items()):
        d = meta.get('data') or {}
        erg.append(_eintrag('architektur_modul', mid, d.get('name') or mid, 'paket', None, str(d.get('version') or '') or None, [], [str(x) for x in (d.get('dependencies') or [])][:10]))
    return erg


# ---- E5: Fähigkeiten (capabilities/)
def _faehigkeiten(hub):
    pfad = Path(__file__).resolve().parents[1] / 'capabilities'
    return [_eintrag('faehigkeit', p.stem, p.stem.replace('_', ' '), 'paket', 'CORE', faehigkeiten=[{'name': 'Selbstdiagnose und Fenster', 'wirkungsklasse': 'read_only'}])
            for p in sorted(pfad.glob('*.py')) if p.stem != '__init__']


# ---- E6: Agenten-Vorlagen
def _agenten(hub):
    """Aus der Ansicht des Agenten-Managers (`agents_view`): Vorlage `ref`, `role`, `trust`, `ok`, `problems`. Importierte Vorlagen sind immer UNVERIFIED; ihre Wirkungsklassen prüft der Import (agent_import.py) und zeigt diese Ansicht nicht."""
    erg = []
    for t in hub.agents_view().get('templates') or []:
        if not isinstance(t, dict):
            continue
        ok = bool(t.get('ok'))
        erg.append(_eintrag('agenten_vorlage', t.get('ref') or '?', t.get('role'), 'importiert', t.get('trust') or 'UNVERIFIED', None, [], [], 'aktiv' if ok else 'abgewiesen',
                            None if ok else ', '.join(str(x) for x in (t.get('problems') or []))[:200] or 'Vorschau nicht bestanden', stelle='Besatzung'))
    return erg


# ---- E7: Harness-Vorlagen
def _harness_vorlagen(hub):
    from ..harness import vorlagen as harness_vorlagen
    erg = []
    for v in harness_vorlagen.liste(hub.project_root):
        if v.get('fehler'):
            erg.append(_eintrag('harness_vorlage', v.get('id'), v.get('id'), 'paket', zustand='abgewiesen', grund=str(v['fehler'])[:200]))
            continue
        erg.append(_eintrag('harness_vorlage', v['id'], v.get('name'), 'paket', None, None,
                            [{'name': w, 'wirkungsklasse': _harness_klasse(w)} for w in (v.get('werkzeuge') or [])], stelle='Einstellungen → Agent'))
    return erg


def _harness_klasse(werkzeug):
    from ..harness.werkzeuge import WIRKUNGSKLASSE
    return WIRKUNGSKLASSE.get(werkzeug, 'privileged')           # was nicht eingestuft ist, gilt in der Anzeige als das Strengste


# ---- E8: Daten (Skill-Bibliotheken, Cloud-Anbieter, Wissen)
def _daten(hub):
    wurzel = Path(__file__).resolve().parents[3] / 'config'
    erg = []
    try:
        libs = yaml.safe_load((wurzel / 'skill_library.yaml').read_text(encoding='utf-8'))['skill_library']['libraries']
        for name, meta in sorted(libs.items()):
            erg.append(_eintrag('daten', 'skills:' + name, 'Skill-Bibliothek ' + name, 'importiert' if meta.get('sources') else 'paket', None, None,
                                [{'name': 'Text für das Modell', 'wirkungsklasse': 'proposal_only'}], stelle='Bibliothek'))
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        erg += _unbekannt('daten', 'skill_library.yaml: ' + str(exc))
    try:
        d = yaml.safe_load((wurzel / 'cloud_providers.yaml').read_text(encoding='utf-8'))['cloud_providers']
        for name, meta in sorted((d.get('providers') or {}).items()):
            an = bool(d.get('enabled')) and bool((meta or {}).get('enabled'))
            erg.append(_eintrag('daten', 'cloud:' + name, 'Cloud-Anbieter ' + name, 'paket', None, None,
                                [{'name': 'Aufruf durch den Inhaltsschutz', 'wirkungsklasse': 'external_side_effect'}], zustand='aktiv' if an else 'aus', stelle='Integrationen'))
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        erg += _unbekannt('daten', 'cloud_providers.yaml: ' + str(exc))
    return erg


QUELLEN = (('werkzeug/shell', _werkzeuge_und_shells), ('kern_erweiterung', _kern), ('architektur_modul', _architektur), ('faehigkeit', _faehigkeiten),
           ('agenten_vorlage', _agenten), ('harness_vorlage', _harness_vorlagen), ('daten', _daten))


def verzeichnis(hub):
    """AM8-01: {eintraege, arten, klassen, quellen}. `arten`: Zahl je Art; `quellen`: die Quellen, die nicht lesbar waren."""
    eintraege, unlesbar = [], []
    for name, fn in QUELLEN:
        try:
            eintraege += fn(hub)
        except Exception as exc:                                             # eine Quelle, die nicht lesbar ist, steht mit Grund da, nichts fehlt still
            art = name.split('/')[0]
            eintraege += _unbekannt(art, f'{type(exc).__name__}: {exc}')
            unlesbar.append({'quelle': name, 'grund': str(exc)[:200]})
    eintraege.sort(key=lambda e: (ARTEN.index(e['art']) if e['art'] in ARTEN else 99, e['id']))
    return {'eintraege': eintraege, 'arten': {a: sum(1 for e in eintraege if e['art'] == a) for a in ARTEN}, 'klassen': klassen(), 'unlesbar': unlesbar}


def filtern(v, art=None, herkunft=None, klasse=None, zustand=None):
    """AM8-03: Filter nach Art, Herkunft, Wirkungsklasse und Zustand (rein)."""
    def passt(e):
        return ((not art or e['art'] == art) and (not herkunft or e['herkunft'] == herkunft) and (not zustand or e['zustand'] == zustand)
                and (not klasse or any(f['wirkungsklasse'] == klasse for f in e['faehigkeiten'])))
    return [e for e in v['eintraege'] if passt(e)]


def stufe_hoechste(e):
    """Die höchste Wirkungsklasse eines Eintrags (für die Anzeige); None ohne Fähigkeiten."""
    rang = [REIHENFOLGE.index(f['wirkungsklasse']) for f in e['faehigkeiten'] if f['wirkungsklasse'] in REIHENFOLGE]
    return REIHENFOLGE[max(rang)] if rang else None


def lesbar(v):
    """AM8-04: der Export als Text für Nachweis und Prüfung."""
    zeilen = ['Verzeichnis der Erweiterungen · ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), '']
    zeilen.append('Arten: ' + ', '.join(f'{a} {n}' for a, n in v['arten'].items() if n))
    for e in v['eintraege']:
        kopf = f"[{e['art']}] {e['id']} · {e['name']} · Herkunft {e['herkunft']}" + (f" · Vertrauen {e['vertrauen']}" if e['vertrauen'] else '') + (f" · Version {e['version']}" if e['version'] else '') + f" · {e['zustand']}"
        zeilen.append(kopf + (f" ({e['grund']})" if e['grund'] else ''))
        h = stufe_hoechste(e)
        if h:
            zeilen.append(f"    höchste Wirkung: {h}")
        for f in e['faehigkeiten'][:12]:
            zeilen.append(f"    - {f['name']} → {f['wirkungsklasse']}")
        if e['abhaengigkeiten']:
            zeilen.append('    braucht: ' + ', '.join(e['abhaengigkeiten']))
    if v['unlesbar']:
        zeilen += ['', 'Nicht lesbare Quellen: ' + '; '.join(f"{u['quelle']} ({u['grund']})" for u in v['unlesbar'])]
    return '\n'.join(zeilen)


def export(hub):
    v = verzeichnis(hub)
    return {'json': v, 'text': lesbar(v)}
