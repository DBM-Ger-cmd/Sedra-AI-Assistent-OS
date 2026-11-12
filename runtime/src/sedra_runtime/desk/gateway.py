"""The gateway between the runtime and the desktop modules (SHELL_WERKZEUG_VERTRAG_v1 §3, §6, §10).

- checks every `shell.yaml` / `tool.yaml` against the contract (the JSON schemas in `uix/ui/schema` describe the same rules for humans
  and editors; this file is the one that decides),
- answers `GET /uix/manifest` with the active shell and the usable tools,
- names the one file a URL `/uix/{ui,shells,tools}/…` may serve (only from registered folders, no `..`, code and styles only),
- decides the API allowlist: a request that carries `X-SEDRA-Tool: <id>` (or `X-SEDRA-Shell: <id>`) may only use the routes its manifest lists.

Honest limit: tools run in the same page as the shell. The allowlist stops a tool that uses its own `ctx.api` outside its routes and
makes that visible in the audit; it is no sandbox against a tool that calls `fetch` itself. That is what the install check (Build 9:
no `eval`, no own `fetch`, no foreign `import()`) and the trust levels are for."""
from __future__ import annotations

from pathlib import Path
import os
import re

import yaml

from .registry import MODULE_ID, Registry
from .herkunft import HerkunftsPruefer, lesen as herkunft_lesen
from . import app_speicher
from . import orte as orte_mod
from . import grundfunktionen as gf
from .berechtigung import ladeentscheidung
from .rechte_diff import rechte_zu_faehigkeiten, stufe as rechte_stufe
from .manifest_felder import filtere, pruefe_profile, pruefe_shells, pruefe_zelle
from .routen_pruefung import pruefe_routen
from .shell_regeln import pruefe_shell

UI_VERSION = (1, 1)
OBJECT_TYPES = ('project', 'intent', 'task', 'candidate', 'file', 'model', 'skill', 'agent', 'decision', 'routine', 'boundary', 'planung',
                'uebersetzung', 'nachrichten', 'transkript',       # Fisch (19.10.2026)
                'aufnahme',                                        # Kern Sprache (19.10.2026): der Rekorder, für jede Shell
                'module', 'logbook', 'meter', 'hardware', 'machine', 'gateway', 'labor', 'entwurf')   # the last six are places of the system; gateway since Build 19; labor: KI Labor (Werkstatt, 16.10.2026)
OBJECT_TYPES += ('issue', 'budget', 'gespraech')                   # Spec 0 D3.2 (issue, budget) und Nachtrag N7 (gespraech)
OBJECT_TYPES += ('wissen',)                                        # Spec 7 D7.9: der Wissensspeicher (Werkzeug wissen, Objekt wissen:speicher)
OBJECT_TYPES += ('translator',)                                  # A3: die App Translator (SPEC_APP_TRANSLATOR_v1); ihre vier Modi nutzen die schon bekannten Typen
OBJECT_TYPES += ('workflow',)                                      # n8n interchange app; execution stays in the mission core
OBJECT_TYPES += ('scenario',)                                      # scenario app shares the process store, not the editor surface
# Nachtrag N1: ein Eintrag in `handles` ist der Typ, `typ:alle`, `typ:*` oder `typ:<id>` (dasselbe Muster wie ui/schema/tool.schema.json).
HANDLE = re.compile(r'^[a-z0-9-]{2,40}(:(\*|[a-z0-9-]{1,40}))?$')
TOOL_KINDS = ('object', 'instrument', 'panel', 'dienst')
# Ein Hinweis für die Shell, kein Befehl: das Cockpit stellt „inhalt“ nach links und „nachweis“ nach rechts (COCKPIT_MODUL_v1 §1).
# Eine Shell ohne zwei Spalten ignoriert ihn – deshalb ist er ein Wort im Manifest und keine Vorschrift im Vertrag.
SLOTS_TOOL = ('inhalt', 'nachweis')
# Ein Hinweis für die Shell, kein Befehl: das Cockpit stellt „inhalt“ nach links und „nachweis“ nach rechts (COCKPIT_MODUL_v1 §1).
# Eine Shell, die keine zwei Spalten hat, ignoriert ihn – deshalb ist er ein Wort im Manifest und keine Vorschrift im Vertrag.
SLOTS_TOOL = ('inhalt', 'nachweis')
# Vertrag 1.1 (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3): wie viele Instanzen ein Werkzeug verträgt und welches Gedächtnis es nutzen darf.
INSTANZEN = ('eine', 'viele')
GEDAECHTNIS = ('sitzung', 'ablage')
ZWECK = ('betrieb', 'pruefung')          # SPEC_UIX_STUFE6 §2.2: ein Prüfwerkzeug lädt nur mit dem Schalter `entwicklung`
# Vertrag Nachtrag N2 (SPEC_HARNESS_SHELL_v1 G2 Stufe 4 §3.2): ein Werkzeug darf sagen, in welche Gruppe des Start-Menüs es gehört;
# ohne das Feld ordnet die Shell es nach ihrer Datei ein. Nachtrag N3: eine Shell darf den Alt+S-Chip durch ihr eigenes Menü ersetzen.
GRUPPEN = ('arbeit', 'modelle', 'wissen', 'system', 'pruefung')
UMSCHALTER = ('chip', 'menue')
# Routen, die der Vertrag selbst mitbringt – kein Manifest muss sie nennen: jede Shell meldet und übernimmt den Arbeitsstand (§10.2),
# jedes Werkzeug mit `gedaechtnis: ablage` liest und schreibt nur seine eigene Ablage (§10.3; der Server trennt nach X-SEDRA-Tool).
SHELL_VERTRAG_ROUTES = ('GET /api/arbeitsstand', 'POST /api/arbeitsstand')
ABLAGE_ROUTES = ('POST /api/ablage/lesen', 'POST /api/ablage/schreiben')
TRUST = ('CORE', 'CAPTAIN', 'SEDRA_BUILT', 'COMMUNITY')
SLOTS = ('strip', 'tree', 'dock', 'talk', 'palette', 'windows', 'menubar', 'notify', 'inbox', 'chooser',
         'seite', 'reiter', 'flaeche', 'eingabe', 'taskleiste')      # die fünf Zonen der Harness-Shell (SPEC_HARNESS_SHELL_v1 G2 §6, HS-01)
OPENS_OBJECTS = ('dock', 'windows')     # a shell that provides neither shows no tool to an object – the acceptance knows
FILE_NAME = re.compile(r'^[a-z0-9_-]{1,60}\.(js|css)$')
SERVE_NAME = re.compile(r'^[a-z0-9_-](?:[a-z0-9_.-]{0,58}[a-z0-9_-])?\.(js|css|json|svg|png|html)$')   # dots inside a name are fine (tool.schema.json); '..' is not a name
SERVE_TYPES = {'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8', 'json': 'application/json; charset=utf-8',
               'svg': 'image/svg+xml', 'png': 'image/png', 'html': 'text/html; charset=utf-8'}
EVENT_NAME = re.compile(r'^[a-z]+(\.[a-z]+){1,2}$')
ROUTE = re.compile(r'^(GET|POST|PATCH|DELETE) (/(api|uix)(/[A-Za-z0-9_.-]+)*(/\*)?)$')     # PATCH/DELETE beantwortet der Server nur unter /api/harness/
VERSION = re.compile(r'^\d+\.\d+\.\d+$')
NEED = re.compile(r'^(>=|<=|>|<|==)?(\d+)(?:\.(\d+))?$')

TOOL_KEYS = {'id', 'name', 'version', 'handles', 'kind', 'entry', 'api', 'events', 'trust', 'tests', 'needs', 'description', 'order', 'slot', 'instanzen', 'gedaechtnis', 'zweck', 'gruppe',
             'shells', 'profile', 'zelle', 'rechte', 'ort', 'grundfunktion', 'rollen', 'dienst'}       # Vertrag 1.1 (AM1); `rechte` AM3-01
SHELL_KEYS = {'id', 'name', 'version', 'entry', 'provides', 'layout', 'trust', 'needs', 'api', 'description', 'vorgabe', 'umschalter', 'grundfunktionen', 'archiv', 'einstieg'}
# Eine Shell aus einer Vorgabe (SPEC_SHELL_AUS_VORGABE_v1): kein Code im Ordner, nur `shell.vorgabe.yaml`; den Bildschirm baut der
# Rahmen `ui/frame.js`. Was er darf, steht hier – nicht in der Datei des Autors –, denn der Rahmen ist Vertragscode.
VORGABE_FILE = 'shell.vorgabe.yaml'
FRAME_API = ['GET /api/strip', 'GET /api/decisions', 'POST /api/decisions/answer', 'GET /api/missions', 'GET /api/boundaries',
             'POST /api/objects']
FRAME_ZONES = ('leiste', 'orte', 'werkstueck', 'gespraech', 'entscheidungen', 'leer')


def _files(value, field, errors):
    files = [value] if isinstance(value, str) else value
    if not isinstance(files, list) or not files:
        errors.append(f'{field}_must_be_a_file_or_list'); return []
    bad = [f for f in files if not isinstance(f, str) or not FILE_NAME.match(f)]
    if bad:
        errors.append(f'{field}_bad_file_name:{bad[0]}')
    return [f for f in files if isinstance(f, str) and FILE_NAME.match(f)]


def needs_ok(spec, version=UI_VERSION):
    """'>=1.0 <2' style ranges against the contract version (major, minor)."""
    if not isinstance(spec, str) or not spec.strip():
        return False
    for part in spec.split():
        m = NEED.match(part)
        if not m:
            return False
        op, want = m.group(1) or '==', (int(m.group(2)), int(m.group(3) or 0))
        if not {'>=': version >= want, '<=': version <= want, '>': version > want, '<': version < want, '==': version == want}[op]:
            return False
    return True


def _common(doc, kind, folder, origin, errors):
    keys = TOOL_KEYS if kind == 'tool' else SHELL_KEYS
    extra = sorted(set(doc) - keys)
    if extra:
        errors.append('unknown_field:' + extra[0])
    mid = doc.get('id')
    if not isinstance(mid, str) or not MODULE_ID.match(mid):
        errors.append('id_invalid')
    elif mid != folder.name:
        errors.append('id_must_match_folder')
    if not isinstance(doc.get('name'), str) or not 1 <= len(doc['name']) <= 60:
        errors.append('name_invalid')
    if not isinstance(doc.get('version'), str) or not VERSION.match(doc['version']):
        errors.append('version_invalid')
    trust = doc.get('trust')
    if trust not in TRUST:
        errors.append('trust_invalid')
    elif origin == 'local' and trust == 'CORE':
        errors.append('local_module_cannot_be_core')
    if not needs_ok((doc.get('needs') or {}).get('ui') if isinstance(doc.get('needs'), dict) else None):
        errors.append('needs_ui_not_met')
    entry = doc.get('entry')
    js = css = []
    if entry is None and (doc.get('vorgabe') is not None or doc.get('kind') == 'dienst'):
        pass                                                        # eine Shell aus Vorgabe und ein Dienst (AM4-05) haben keine Fläche
    elif not isinstance(entry, dict) or 'js' not in entry:
        errors.append('entry_js_required')
    else:
        js = _files(entry['js'], 'entry_js', errors)
        css = _files(entry['css'], 'entry_css', errors) if entry.get('css') else []
        if set(entry) - {'js', 'css'}:
            errors.append('entry_unknown_field')
    for f in js + css:
        if not (folder / f).is_file():
            errors.append('file_missing:' + f)
    routes = doc.get('api') or []
    if not isinstance(routes, list) or not all(isinstance(r, str) and ROUTE.match(r) for r in routes):
        errors.append('api_route_invalid')
        routes = []
    errors.extend(pruefe_routen(routes, origin, trust))                  # AM0-03: zu breite Platzhalter, Sperrliste für fremde Module (vor dem GET-Filter)
    if trust == 'COMMUNITY':
        routes = [r for r in routes if r.startswith('GET ')]           # foreign modules read; writing needs the Captain's review
    return js, css, routes


ROLLE = re.compile(r'^[a-z][a-z0-9-]{1,29}$')
APP_ID = re.compile(r'^[a-z0-9-]{2,40}$')
NEED_RANGE = re.compile(r'^(?:(?:>=|<=|>|<|==)?\d+(?:\.\d+)?)(?: (?:>=|<=|>|<|==)?\d+(?:\.\d+)?)*$')


def check_tool(doc, folder: Path, origin='package', shell=None):
    """(manifest, errors) for a tool.yaml document. `shell`: der Name der Shell, wenn die App aus `…/shells/<shell>/apps/` kommt (AM2-07)."""
    errors = []
    if not isinstance(doc, dict) or not isinstance(doc.get('tool'), dict):
        return None, ['tool_mapping_required']
    t = doc['tool']
    js, css, routes = _common(t, 'tool', folder, origin, errors)
    kind = t.get('kind')
    if kind not in TOOL_KINDS:
        errors.append('kind_invalid')
    handles = t.get('handles') or []
    # Ein Werkzeug aus dem Paket (CORE) spricht das Vokabular des Vertrags. Ein eigenes oder fremdes darf einen **eigenen**
    # Objekttyp mitbringen (`gateway`, `rechnung`): die Shells öffnen jeden Typ über die Registrierung, der Baum und die Palette
    # kennen ihn nicht – das steht dann im Werkzeug „Module“. Gefunden mit der ersten externen Lieferung (KI GateWay, 15.10.2026).
    trust_for_types = t.get('trust')
    own_types = []
    if not isinstance(handles, list) or not all(isinstance(h, str) and HANDLE.match(h) for h in handles):
        errors.append('handles_unknown_type')
        handles = []
    else:
        own_types = list(dict.fromkeys(b for b in (h.partition(':')[0] for h in handles) if b not in OBJECT_TYPES))
        if own_types and (trust_for_types == 'CORE' or origin == 'package'):
            errors.append('handles_unknown_type')          # im Paket gibt es keine Privatsprache
            handles = []
    if kind == 'object' and not handles:
        errors.append('object_tool_needs_handles')
    events = t.get('events') or {}
    if not isinstance(events, dict) or set(events) - {'emits', 'listens'}:
        errors.append('events_invalid'); events = {}
    for side in ('emits', 'listens'):
        names = events.get(side) or []
        if not isinstance(names, list) or not all(isinstance(n, str) and EVENT_NAME.match(n) for n in names):
            errors.append(f'events_{side}_invalid')
    # Härtung 30.10. (Nachtrag N3): Ereignisse des Stroms sendet kein Werkzeug – ein Manifest, das sie in `emits` nennt, wird abgewiesen
    reserviert = [n for n in (events.get('emits') or []) if isinstance(n, str) and (n in EVENTS_NUR_STROM or n.startswith('harness.'))]
    if reserviert:
        errors.append('events_emits_reserved:' + ','.join(reserviert))
    tests = t.get('tests') or []
    if not isinstance(tests, list) or not all(isinstance(x, str) and re.match(r'^[a-z0-9_.-]+\.js$', x) for x in tests):
        errors.append('tests_invalid')
    order = t.get('order', 100)
    if type(order) is not int or not 0 <= order <= 1000:
        errors.append('order_invalid')
    slot = t.get('slot', 'inhalt')
    if slot not in SLOTS_TOOL:
        errors.append('slot_invalid')
    instanzen = t.get('instanzen', 'eine')
    if instanzen not in INSTANZEN:
        errors.append('instanzen_invalid')
    gedaechtnis = t.get('gedaechtnis') or []
    if isinstance(gedaechtnis, str):
        gedaechtnis = [gedaechtnis]
    if not isinstance(gedaechtnis, list) or not all(g in GEDAECHTNIS for g in gedaechtnis):
        errors.append('gedaechtnis_invalid'); gedaechtnis = []
    zweck = t.get('zweck', 'betrieb')
    if zweck not in ZWECK:
        errors.append('zweck_invalid')
    gruppe = t.get('gruppe')
    if gruppe is not None and gruppe not in GRUPPEN:
        errors.append('gruppe_invalid')
    faehigkeiten = []
    if t.get('rechte') is not None:                                  # AM3-01: nur fremde Module; Schlüssel und Werte prüft rechte_diff, Stufe C wird abgewiesen
        if t.get('trust') == 'CORE' or origin == 'package':
            errors.append('rechte_nur_fremd')
        else:
            try:
                faehigkeiten = rechte_zu_faehigkeiten(t.get('rechte'))
            except ValueError as exc:
                errors.append(str(exc))
            stufe_c = [f for f in faehigkeiten if rechte_stufe(f) == 'C']
            if stufe_c:
                errors.append('rechte_stufe_c:' + ','.join(stufe_c))
    errors.extend(pruefe_shells(t.get('shells'))[0])                  # Vertrag 1.1 (AM1): Verfügbarkeit je Shell und Profil, Zelle der Taskleiste
    errors.extend(pruefe_profile(t.get('profile'))[0])
    errors.extend(orte_mod.pruefe_ort(t.get('ort'), handles, t.get('id')))        # AM2-02/03: Ort der App
    errors.extend(gf.pruefe_tool_feld(t.get('grundfunktion'), t.get('trust'), origin))      # AM2-13
    dienst = None
    if kind == 'dienst':                                                    # AM4-05/07: ein Dienst hat keine Fläche und keinen Ort; der Block `dienst` wird streng geprüft
        from .dienste import pruefe_dienst
        dienst, d_fehler = pruefe_dienst(t.get('dienst'), t.get('trust'), folder)
        errors.extend(d_fehler)
        if t.get('ort') is not None:
            errors.append('dienst_hat_keinen_ort')
        if t.get('instanzen') is not None or t.get('slot') is not None:
            errors.append('dienst_hat_keine_flaeche')
    elif t.get('dienst') is not None:
        errors.append('dienst_nur_bei_kind_dienst')
    needs_apps = {}
    roh = (t.get('needs') or {}).get('apps') if isinstance(t.get('needs'), dict) else None
    if roh is not None:                                                    # AM2-19: needs.apps {<id>: "<bereich>"} – geprüft wird beim Laden aller Werkzeuge
        if not isinstance(roh, dict) or not all(isinstance(k, str) and APP_ID.match(k) and isinstance(v, str) and NEED_RANGE.match(v.strip()) for k, v in roh.items()):
            errors.append('needs_apps_invalid')
        else:
            needs_apps = dict(roh)
    rollen = t.get('rollen')
    if rollen is not None and (not isinstance(rollen, list) or len(rollen) > 20 or not all(isinstance(r, str) and ROLLE.match(r) for r in rollen)):
        errors.append('rollen_invalid')                                    # AM2-20: erlaubt, bis AM7 ohne Wirkung
    if shell is not None:                                                   # AM2-07/09: eine Shell-App gilt nur in ihrer Shell; eingebaut ist sie COMMUNITY, auch wenn die Shell CAPTAIN ist
        if t.get('shells') not in (None, [shell]):
            errors.append('shell_app_shells_fest')
        if origin == 'local' and t.get('trust') != 'COMMUNITY':
            errors.append('shell_app_vertrauen_community')
    from .. import chat_tools
    errors.extend(pruefe_zelle(t.get('zelle'), kind, list(chat_tools.PLACES)))
    if errors:
        return None, errors
    return {'id': t['id'], 'name': t['name'], 'version': t['version'], 'kind': kind, 'handles': handles, 'trust': t['trust'],
            'origin': origin, 'order': order, 'slot': slot, 'description': str(t.get('description') or ''),
            'own_types': own_types, 'instanzen': instanzen, 'gedaechtnis': list(dict.fromkeys(gedaechtnis)), 'zweck': zweck, 'gruppe': gruppe,
            'events': {'emits': list(events.get('emits') or []), 'listens': list(events.get('listens') or [])},
            'shells': [shell] if shell is not None else t.get('shells'), 'shell_app': shell, 'profile': t.get('profile'), 'zelle': t.get('zelle'), 'ort': t.get('ort'), 'grundfunktion': t.get('grundfunktion'), 'dienst': dienst, 'rollen': list(rollen or []), 'needs_apps': needs_apps, 'rechte': t.get('rechte'), 'faehigkeiten': faehigkeiten,
            'js': js, 'css': css, 'api': routes, 'tests': tests}, []


def check_shell(doc, folder: Path, origin='package'):
    errors = []
    if not isinstance(doc, dict) or not isinstance(doc.get('shell'), dict):
        return None, ['shell_mapping_required']
    s = doc['shell']
    js, css, routes = _common(s, 'shell', folder, origin, errors)
    if s.get('trust') == 'COMMUNITY':                               # AM0-06: eine fremde Shell ist nur eine Vorgabe – kein Code, kein eigenes CSS
        errors.extend(pruefe_shell(s, 'COMMUNITY', [p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()]))
    if s.get('vorgabe') is not None:
        return _check_frame_shell(s, folder, origin, errors)
    provides = s.get('provides') or []
    if not isinstance(provides, list) or not provides or not all(p in SLOTS for p in provides):
        errors.append('provides_invalid')
    layout = s.get('layout') or {'persist': 'browser'}
    if not isinstance(layout, dict) or layout.get('persist') not in ('browser', 'none'):
        errors.append('layout_invalid')
    umschalter = s.get('umschalter', 'chip')
    if umschalter not in UMSCHALTER:
        errors.append('umschalter_invalid')
    erklaerung = s.get('grundfunktionen')
    errors.extend(gf.pruefe_erklaerung(erklaerung, provides if isinstance(provides, list) else []))        # AM2-14
    for flag in ('archiv', 'einstieg'):
        if flag in s and not isinstance(s[flag], bool):
            errors.append(flag + '_invalid')
    if s.get('archiv') is True and s.get('einstieg') is True:
        errors.append('archiv_und_einstieg')
    if errors:
        return None, errors
    erklaerung = dict(erklaerung or {})
    return {'id': s['id'], 'name': s['name'], 'version': s['version'], 'provides': provides, 'layout': layout, 'trust': s['trust'],
            'origin': origin, 'description': str(s.get('description') or ''), 'js': js, 'css': css, 'api': routes,
            'umschalter': umschalter, 'grundfunktionen': erklaerung, 'archiv': s.get('archiv') is True, 'einstieg': s.get('einstieg') is True,
            'grundfunktionen_warnungen': gf.warnungen(erklaerung, provides, s.get('archiv') is True, s.get('einstieg') is True)}, []


def read_vorgabe(folder: Path):
    """(vorgabe, errors) – die Datei gelesen und gegen ui/schema/vorgabe.schema.json geprüft (dieselbe flache Teilmenge, mit der
    ein lokales Modell gezwungen wird; models/structured.py)."""
    path = folder / VORGABE_FILE
    if not path.is_file():
        return None, ['vorgabe_missing']
    try:
        doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return None, [f'vorgabe_unreadable:{type(exc).__name__}']
    from .vorgabe import check                                   # eine Prüfung – für die Datei wie für das Modell
    problems = check(doc)
    if problems:
        return None, ['vorgabe_invalid:' + problems[0]]
    return doc, []


def _check_frame_shell(s, folder, origin, errors):
    if s.get('vorgabe') != VORGABE_FILE:
        errors.append('vorgabe_must_be_' + VORGABE_FILE)
    for key in ('entry', 'api', 'provides'):
        if key in s:
            errors.append('vorgabe_shell_has_no_' + key)          # Code, Routen und Slots gehören dem Rahmen, nicht der Datei
    vorgabe, problems = read_vorgabe(folder)
    errors += problems
    if vorgabe is not None and vorgabe['id'] != s.get('id'):
        errors.append('vorgabe_id_must_match')
    layout = s.get('layout') or {'persist': 'browser'}
    if not isinstance(layout, dict) or layout.get('persist') not in ('browser', 'none'):
        errors.append('layout_invalid')
    if errors:
        return None, errors
    zones = [z for row in vorgabe['raster'] for z in row.split('|')]
    provides = ['dock', 'talk']
    if 'leiste' in zones: provides.append('strip')
    if 'orte' in zones: provides.append('tree')
    if vorgabe.get('suche', 'strg-k') == 'strg-k': provides.append('palette')
    if vorgabe.get('entscheidungen', 'karte') == 'karte': provides.append('inbox')
    css = ['shell.css'] if (folder / 'shell.css').is_file() else []
    return {'id': s['id'], 'name': s['name'], 'version': s['version'], 'provides': provides, 'layout': layout, 'trust': s['trust'],
            'origin': origin, 'description': str(s.get('description') or ''), 'js': [], 'css': css, 'api': list(FRAME_API),
            'frame': True, 'vorgabe': vorgabe, 'grundfunktionen': gf.aus_rahmen(provides), 'archiv': False, 'einstieg': False,
            'grundfunktionen_warnungen': gf.warnungen(gf.aus_rahmen(provides), provides)}, []


EVENTS_NUR_STROM = frozenset({'task.changed', 'model.changed', 'system.state', 'desk.error', 'desk.resync', 'tools.refresh',
                              'agent.changed', 'issue.changed', 'budget.warning', 'slot.changed'})     # wie ui/bus.js NUR_STROM


def route_allowed(routes, method, path):
    """Exact 'METHOD /path' or a prefix entry ending in '/*'. Paths with '..' or '//' never match."""
    if '..' in path or '//' in path:
        return False
    for r in routes:
        m, _, p = r.partition(' ')
        if m != method:
            continue
        if p.endswith('/*'):
            if path.startswith(p[:-1]) and len(path) > len(p) - 1:
                return True
        elif path == p:
            return True
    return False


def abgeleitete_routen(wirksam):
    """AM3-02: die Routen, die zu den wirksamen Fähigkeiten gehören (`ablage:<n>` → die beiden Ablage-Routen)."""
    routen = []
    if any(f.startswith('ablage:') for f in wirksam):
        routen.extend(ABLAGE_ROUTES)
    if any(f.startswith('lesen:') for f in wirksam):
        routen.append('POST /api/objects')
    if any(f.startswith('verb:') for f in wirksam):
        routen.append('POST /api/actions')
    return routen


class Gateway:
    def __init__(self, project_root: Path, registry: Registry | None = None):
        self.registry = registry or Registry(project_root)
        self.project_root = Path(project_root)
        self.app_berechtigung = False                         # AM3: Schalter `app_berechtigung` (local_config/switches.yaml), Standard aus bis zur Abnahme
        self.herkunft_pruefen = True                          # AM0-02: Schalter `herkunft_pruefen` (local_config/switches.yaml), Standard an
        self.melden = None                                    # der Hub setzt eine Funktion (kind, id, gruende), die UIX_MODULE_TAMPERED ins Audit schreibt
        self._pruefer = HerkunftsPruefer()
        self._gemeldet = set()

    def _aktives_profil(self):
        """Das Profil des Desktop Builders (`runtime_data/harness/desktop.json`); ohne Wahl oder bei einem Lesefehler None (= 'standard')."""
        try:
            from ..harness import desktop
            return desktop.laden(self.project_root).get('profil') or None
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            return None

    def _grundfunktionen(self):
        """Werkzeuge, die eine Grundfunktion tragen: in jedem Profil sichtbar (ENTWURF_APPS_MODELL §2.2a). Gelesen aus dem Desktop Builder."""
        try:
            from ..harness import desktop
            return set(desktop.GRUND_START) | {'gauge-' + z for z in desktop.GRUND_ZELLEN}
        except ImportError:
            return {'decisions', 'tasks', 'wissen', 'gauge-decisions'}

    def _herkunft(self, area, folder):
        """Gründe, warum die Herkunft eines COMMUNITY-Moduls nicht stimmt (leer = in Ordnung)."""
        try:
            eintrag = herkunft_lesen(self.project_root, area, folder.name)
        except ValueError:
            return ['herkunft_unlesbar']
        if eintrag is None:
            return ['herkunft_fehlt']
        return self._pruefer.pruefen(folder, area, eintrag)

    def _berechtigung(self, folder, man):
        eintrag = app_speicher.lesen(self.project_root).get(man['id'])
        return ladeentscheidung(eintrag, man.get('faehigkeiten') or [], app_speicher.manifest_hash(folder / 'tool.yaml'))

    def app_pruefung(self, module, path, payload):
        """AM3-11: der Körper einer Anfrage einer fremden App gegen ihre wirksamen Rechte. None = in Ordnung, sonst der Fehlercode
        (`typ_nicht_gewaehrt`, `verb_nicht_gewaehrt`). Ohne Schalter oder für eine App ohne `rechte` prüft das Gateway hier nichts."""
        if not self.app_berechtigung:
            return None
        eintrag = self.tools().get(module)
        if eintrag is None:
            return None
        man = eintrag[1]
        if man.get('trust') != 'COMMUNITY' or man.get('rechte') is None:
            return None
        wirksam = set(man.get('wirksam') or [])
        p = payload if isinstance(payload, dict) else {}
        typ = str(p.get('type') or '').strip()
        if path == '/api/objects':
            if 'lesen:' + typ in wirksam or typ in (man.get('own_types') or []):       # AM3-12: eigene Typen gelten als gewährtes Lesen
                return None
            return 'typ_nicht_gewaehrt'
        if path == '/api/actions':
            verb = str(p.get('verb') or '').strip()
            return None if 'verb:' + typ + '.' + verb in wirksam else 'verb_nicht_gewaehrt'
        return None

    def apps_uebersicht_beantragt(self, mid):
        for a in self.apps_uebersicht():
            if a['id'] == mid:
                return [b['faehigkeit'] for b in a['beantragt']]
        return []

    def _rechte_app(self, man):
        return bool(self.app_berechtigung and man.get('trust') == 'COMMUNITY' and man.get('rechte') is not None)

    def ablage_grenze(self, module):
        """AM3: die Größe der Ablage einer App in Byte (höchstens 1 MB, die gewährte Fähigkeit `ablage:<n>`); None, wenn das Werkzeug keine App mit `rechte` ist (dann gelten die Grenzen des Kerns)."""
        man = (self.tools().get(module) or (None, {}))[1]
        if not man or not self._rechte_app(man):
            return None
        zahlen = [int(f[7:]) for f in man.get('wirksam') or [] if f.startswith('ablage:') and f[7:].isdigit()]
        return min(max(zahlen), 1048576) if zahlen else 0

    def abgelehnt_grund(self, kind, module):
        """Der Grund, warum ein Modul nicht geladen ist (für die Antwort 403), oder None."""
        for r in self._load('tools' if kind == 'tool' else 'shells')[1]:
            if r['id'] == module and r['reasons']:
                return r['reasons'][0]
        return None

    def apps_uebersicht(self):
        """Die fremden Apps mit `rechte`: beantragt (mit Stufe), gewährt, aktiv und der Grund, falls sie nicht laden (AM3-26, Seite „Module“)."""
        geladen, abgelehnt = self._load('tools')
        speicher = app_speicher.lesen(self.project_root)
        liste = []
        for folder, origin, problem in self.registry.module_dirs('tools'):
            if problem or origin != 'local' or not (folder / 'tool.yaml').is_file():
                continue
            try:
                doc = yaml.safe_load((folder / 'tool.yaml').read_text(encoding='utf-8'))
                man, fehler = check_tool(doc, folder, origin)
            except (yaml.YAMLError, UnicodeDecodeError, OSError):
                continue
            t = doc.get('tool') if isinstance(doc, dict) else None
            if not isinstance(t, dict) or t.get('trust') != 'COMMUNITY' or t.get('rechte') is None:
                continue
            eintrag = speicher.get(folder.name)
            beantragt = (man or {}).get('faehigkeiten') or []
            urteil = ladeentscheidung(eintrag, beantragt, app_speicher.manifest_hash(folder / 'tool.yaml')) if man else {'laden': False, 'grund': (fehler or ['ungueltig'])[0]}
            liste.append({'id': folder.name, 'name': (man or t).get('name'), 'version': (man or t).get('version'),
                          'beantragt': [{'faehigkeit': f, 'stufe': rechte_stufe(f), 'gewaehrt': f in ((eintrag or {}).get('gewaehrt') or [])} for f in beantragt],
                          'aktiv': bool(eintrag and eintrag.get('aktiv') is True), 'laedt': folder.name in geladen, 'grund': urteil.get('grund')})
        return sorted(liste, key=lambda a: a['id'])

    def _load(self, kind):
        """{id: (folder, manifest)} and the rejected folders with their reasons."""
        name, check = ('tool.yaml', check_tool) if kind == 'tools' else ('shell.yaml', check_shell)
        ok, rejected = {}, []
        kandidaten = [(f, o, p, None) for f, o, p in self.registry.module_dirs(kind)]
        if kind == 'tools':                                          # AM2-07/08: Apps, die Shells mitbringen; ihre id ist global eindeutig – eine Shell-App verdrängt nie ein Werkzeug
            namen = [f.name for f, _o, _p, _s in kandidaten]
            for f, o, s in self.registry.shell_app_dirs():
                namen.append(f.name)
                kandidaten.append((f, o, None, s))
            doppelt = {n for n in namen if namen.count(n) > 1}
            kandidaten = [(f, o, ('id_doppelt' if s is not None and f.name in doppelt else p), s) for f, o, p, s in kandidaten]
        for folder, origin, problem, shell_app in kandidaten:
            if problem:
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': [problem]}); continue
            path = folder / name
            if not path.is_file():
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': [name + '_missing']}); continue
            try:
                doc = yaml.safe_load(path.read_text(encoding='utf-8'))
            except (yaml.YAMLError, UnicodeDecodeError) as exc:
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': [f'yaml_unreadable:{type(exc).__name__}']}); continue
            man, errors = check(doc, folder, origin) if shell_app is None else check_tool(doc, folder, origin, shell_app)
            if errors:
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': errors}); continue
            if origin == 'local' and man.get('trust') == 'COMMUNITY' and self.herkunft_pruefen:
                gruende = self._herkunft(kind, folder)
                if gruende:
                    rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': gruende})
                    schluessel = (kind, folder.name, tuple(gruende))
                    if self.melden is not None and schluessel not in self._gemeldet:
                        self._gemeldet.add(schluessel)
                        self.melden(kind[:-1], folder.name, list(gruende))
                    continue
            if kind == 'tools' and self.app_berechtigung and man.get('trust') == 'COMMUNITY' and man.get('rechte') is not None:
                urteil = self._berechtigung(folder, man)                  # AM3-06/08: gewährt, aktiv und zur Fassung passend – sonst nicht geladen
                if not urteil['laden']:
                    rejected.append({'kind': 'tool', 'id': folder.name, 'origin': origin, 'reasons': [urteil['grund']]})
                    continue
                man['wirksam'] = urteil['wirksam']
                man['api'] = list(man['api']) + abgeleitete_routen(urteil['wirksam'])      # AM3-02: lesen → POST /api/objects, verben → POST /api/actions
            ok[man['id']] = (folder, man)
        if kind == 'tools':                                           # AM2-19: needs.apps – fehlt die App oder passt die Version nicht, wird die abhängige abgewiesen (bis nichts mehr wegfällt)
            geaendert = True
            while geaendert:
                geaendert = False
                for tid, (_f, m) in list(ok.items()):
                    for dep, bereich in (m.get('needs_apps') or {}).items():
                        if dep not in ok:
                            grund = 'needs_app_fehlt:' + dep
                        else:
                            v = ok[dep][1]['version'].split('.')
                            grund = None if needs_ok(bereich, (int(v[0]), int(v[1]))) else 'needs_app_version:' + dep
                        if grund:
                            ok.pop(tid)
                            rejected.append({'kind': 'tool', 'id': tid, 'origin': m['origin'], 'reasons': [grund]})
                            geaendert = True
                            break
        if kind == 'tools':                                           # AM2-03: dieselbe Ort-id bei zwei Apps – beide abgewiesen, wie bei `id_doppelt`
            belegt = {}
            for tid, (_f, m) in ok.items():
                if m.get('ort'):
                    belegt.setdefault(m['ort']['id'], []).append(tid)
            for oid, tids in belegt.items():
                if len(tids) > 1:
                    for tid in tids:
                        ok.pop(tid, None)
                        rejected.append({'kind': 'tool', 'id': tid, 'origin': 'local', 'reasons': ['ort_id_belegt']})
        return ok, rejected

    def tools(self):
        return self._load('tools')[0]

    def shells(self):
        return self._load('shells')[0]

    def orte(self, shell=None):
        """AM2-04: Kernorte plus die Orte der Apps, die in dieser Shell verfügbar und geladen sind. (orte, warnungen); ohne Angabe die aktive Shell."""
        cfg = self.registry.config()
        tools = self.tools()
        shell = shell or cfg['shell']
        disabled = set(cfg['disabled'])
        apps = [(t, m['ort']) for t, (_f, m) in sorted(tools.items(), key=lambda kv: (kv[1][1]['order'], kv[0]))
                if m.get('ort') and t not in disabled and (m.get('shells') is None or shell in m['shells'])]
        return orte_mod.zusammensetzen(apps)

    def manifest(self):
        cfg = self.registry.config()
        shells, rej_s = self._load('shells')
        tools, rej_t = self._load('tools')
        rejected = rej_s + rej_t
        active = cfg['shell'] if cfg['shell'] in shells else None
        if active is None:
            rejected.append({'kind': 'shell', 'id': cfg['shell'], 'origin': 'config', 'reasons': ['active_shell_not_available']})
        disabled = set(cfg['disabled'])
        # Stufe 6 (S6-E4): Prüfwerkzeuge nur mit dem Schalter `entwicklung` (Hub setzt `entwicklung`); sonst stehen sie unter `pruefung`
        pruefung = {t for t in tools if tools[t][1].get('zweck') == 'pruefung'} if not getattr(self, 'entwicklung', False) else set()
        ids = [t for t in tools if t not in disabled and t not in pruefung and tools[t][1].get('kind') != 'dienst']       # ein Dienst hat keine Fläche: er steht nicht in der Oberfläche
        ids.sort(key=lambda t: (tools[t][1]['order'], t))
        ids = self.registry.ordered(ids) if cfg['order'] else ids
        # Vertrag 1.1 (AM1): Sichtbarkeit je Shell und Profil – kein Recht, `allowed` lädt über `_load` und bleibt unberührt
        grund = self._grundfunktionen() | {t for t in tools if tools[t][1].get('grundfunktion')}       # AM2-13: immer verfügbar, `shells` gilt nicht
        liste = [{'id': t, 'name': tools[t][1]['name'], 'shells': tools[t][1].get('shells'), 'profile': tools[t][1].get('profile')} for t in ids]
        profil = self._aktives_profil() if any(e['profile'] for e in liste) else None
        sichtbar, nicht_shell, nicht_profil = filtere(liste, active, profil, grund)
        for e in nicht_shell + nicht_profil:                         # S15: die Shell sagt im Leerzustand, wo ein Objekttyp verfügbar ist – dazu braucht sie die Typen des Werkzeugs
            e['handles'] = list(tools[e['id']][1].get('handles') or [])
        ids = [e['id'] for e in sichtbar]
        warnungen = []
        for t in tools:
            man = tools[t][1]
            for w in pruefe_shells(man.get('shells'), sorted(shells))[1] + pruefe_profile(man.get('profile'), None, t in grund)[1]:
                warnungen.append({'id': t, 'grund': w})

        orte, orte_warnungen = self.orte(active) if active else (orte_mod.kern(), [])
        for sid, (_f, sman) in shells.items():                       # AM2-15: im Vertrag 1.1 nur Warnungen, sichtbar im Werkzeug „Module“
            warnungen.extend({'id': sid, 'grund': w} for w in sman.get('grundfunktionen_warnungen') or [])
        warnungen.extend({'id': 'orte', 'grund': w} for w in orte_warnungen)

        def public(kind, man):
            pub = {k: v for k, v in man.items() if k not in ('api', 'js', 'css')}
            pub['js'] = [f'/uix/{kind}/{man["id"]}/{f}' for f in man['js']]
            pub['css'] = [f'/uix/{kind}/{man["id"]}/{f}' for f in man['css']]
            if man.get('frame'):                                  # der Rahmen ist Vertragscode: er kommt aus ui/, nicht aus dem Ordner
                pub['js'] = ['/uix/ui/frame.js'] + pub['js']
                pub['css'] = ['/uix/ui/frame.css'] + pub['css']
            if kind == 'tools' and man.get('trust') != 'CORE':      # Stufe C: die Brücke des Kerns prüft die Routen dieses Werkzeugs
                pub['api'] = list(man.get('api') or [])
            return pub
        return {'ui': '%d.%d' % UI_VERSION,
                # Härtung E4 (30.10.): der Prüfzugang der Seite (`window.sedraBoot.ctx`, die lebenden Registrierungen `sedra.tools/.shells`)
                # existiert nur, wenn der Schalter `entwicklung` an ist oder eine Prüfung ihn verlangt (SEDRA_PRUEFZUGANG=1 im Prozess der Prüfung)
                'pruefzugang': bool(getattr(self, 'entwicklung', False)) or os.environ.get('SEDRA_PRUEFZUGANG') == '1',
                'shell': public('shells', shells[active][1]) if active else None,
                'shells': sorted(shells),
                'tools': [public('tools', tools[t][1]) for t in ids],
                'disabled': sorted(disabled & set(tools)),
                'pruefung': sorted(pruefung),
                'orte': orte,
                'nicht_in_dieser_shell': nicht_shell,
                'nicht_in_diesem_profil': nicht_profil,
                'warnungen': warnungen,
                'rejected': rejected,
                'config': {'shell': cfg['shell'], 'from_file': cfg['from_file']}}

    def frame_page(self, tool_id):
        """Stufe C: die Seite des Rahmens für ein Nicht-CORE-Werkzeug. Ohne Token und ohne Daten; die Dateien des Werkzeugs
        stehen im Manifest. None, wenn es das Werkzeug nicht gibt oder es zum Paket gehört (CORE läuft in der Seite)."""
        import html as _html
        import json as _json
        t = {x['id']: x for x in self.manifest()['tools']}.get(tool_id)
        if not t or t.get('trust') == 'CORE':
            return None
        links = ''.join(f'<link rel="stylesheet" href="{_html.escape(h)}">' for h in t['css'])
        scripts = ''.join(f'<script src="{_html.escape(h)}"></script>' for h in ['/uix/ui/dom.js', '/uix/ui/rahmen.js'] + t['js'])
        info = _json.dumps({'id': t['id'], 'name': t['name'], 'api': t.get('api', []), 'events': t.get('events', {})}, ensure_ascii=False)
        # Härtung E3 (30.10.): kein Inline-Script – das Manifest steht als Attribut am Container, rahmen.js startet beim Laden (CSP script-src 'self')
        return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{_html.escape(t["name"])}</title>{links}</head>'
                f'<body><div id="werk" data-manifest="{_html.escape(info, quote=True)}"></div>' + scripts + '</body></html>')

    def file(self, area, module, name):
        """The path of a file a URL may serve, or None. area: 'ui', 'shells' or 'tools'."""
        if not isinstance(name, str) or not SERVE_NAME.match(name):
            return None
        if area == 'ui':
            base = self.registry.package_dir / 'ui'
            path = base / name if module is None else (base / module / name if module == 'schema' else None)
        elif area in ('shells', 'tools'):
            loaded = self._load(area)[0]
            if module not in loaded:
                return None
            path = loaded[module][0] / name
        else:
            return None
        if path is None or not path.is_file():
            return None
        # Härtung: eine Verknüpfung im Modulordner zeigt aus ihm heraus – ausgeliefert wird sie nicht, auch wenn der Name
        # stimmt. Der Einbau weist Verknüpfungen schon ab; hier steht die zweite Sperre, falls ein Ordner von Hand entsteht.
        try:
            base = (self.registry.package_dir / 'ui' if area == 'ui' else path.parent).resolve()
            if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(base):
                return None
        except (OSError, ValueError):
            return None
        return path

    def allowed(self, kind, module, method, path):
        """True when the module of that kind ('tool' or 'shell') lists the route. An unknown or rejected module is never allowed."""
        loaded = self._load('tools' if kind == 'tool' else 'shells')[0]
        if module not in loaded:
            return False
        man = loaded[module][1]
        if kind == 'shell' and route_allowed(SHELL_VERTRAG_ROUTES, method, path):
            return True
        if kind == 'tool' and 'ablage' in (man.get('gedaechtnis') or []) and not self._rechte_app(man) and route_allowed(ABLAGE_ROUTES, method, path):      # eine App mit `rechte` bekommt die Ablage nur über `ablage:<n>`
            return True
        return route_allowed(man['api'], method, path)
