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
import re

import yaml

from .registry import MODULE_ID, Registry

UI_VERSION = (1, 0)
OBJECT_TYPES = ('project', 'intent', 'task', 'candidate', 'file', 'model', 'skill', 'agent', 'decision', 'routine', 'boundary', 'planung',
                'uebersetzung', 'nachrichten', 'transkript',       # Fisch (19.10.2026)
                'aufnahme',                                        # Kern Sprache (19.10.2026): der Rekorder, für jede Shell
                'module', 'logbook', 'meter', 'hardware', 'machine', 'gateway', 'labor', 'entwurf')   # the last six are places of the system; gateway since Build 19; labor: KI Labor (Werkstatt, 16.10.2026)
OBJECT_TYPES += ('issue', 'budget', 'gespraech')                   # Spec 0 D3.2 (issue, budget) und Nachtrag N7 (gespraech)
OBJECT_TYPES += ('wissen',)                                        # Spec 7 D7.9: der Wissensspeicher (Werkzeug wissen, Objekt wissen:speicher)
# Nachtrag N1: ein Eintrag in `handles` ist der Typ, `typ:alle`, `typ:*` oder `typ:<id>` (dasselbe Muster wie ui/schema/tool.schema.json).
HANDLE = re.compile(r'^[a-z0-9-]{2,40}(:(\*|[a-z0-9-]{1,40}))?$')
TOOL_KINDS = ('object', 'instrument', 'panel')
# Ein Hinweis für die Shell, kein Befehl: das Cockpit stellt „inhalt“ nach links und „nachweis“ nach rechts (COCKPIT_MODUL_v1 §1).
# Eine Shell ohne zwei Spalten ignoriert ihn – deshalb ist er ein Wort im Manifest und keine Vorschrift im Vertrag.
SLOTS_TOOL = ('inhalt', 'nachweis')
# Ein Hinweis für die Shell, kein Befehl: das Cockpit stellt „inhalt“ nach links und „nachweis“ nach rechts (COCKPIT_MODUL_v1 §1).
# Eine Shell, die keine zwei Spalten hat, ignoriert ihn – deshalb ist er ein Wort im Manifest und keine Vorschrift im Vertrag.
SLOTS_TOOL = ('inhalt', 'nachweis')
# Vertrag 1.1 (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §3): wie viele Instanzen ein Werkzeug verträgt und welches Gedächtnis es nutzen darf.
INSTANZEN = ('eine', 'viele')
GEDAECHTNIS = ('sitzung', 'ablage')
# Routen, die der Vertrag selbst mitbringt – kein Manifest muss sie nennen: jede Shell meldet und übernimmt den Arbeitsstand (§10.2),
# jedes Werkzeug mit `gedaechtnis: ablage` liest und schreibt nur seine eigene Ablage (§10.3; der Server trennt nach X-SEDRA-Tool).
SHELL_VERTRAG_ROUTES = ('GET /api/arbeitsstand', 'POST /api/arbeitsstand')
ABLAGE_ROUTES = ('POST /api/ablage/lesen', 'POST /api/ablage/schreiben')
TRUST = ('CORE', 'CAPTAIN', 'GUPPI_BUILT', 'COMMUNITY')
SLOTS = ('strip', 'tree', 'dock', 'talk', 'palette', 'windows', 'menubar', 'notify', 'inbox', 'chooser')
OPENS_OBJECTS = ('dock', 'windows')     # a shell that provides neither shows no tool to an object – the acceptance knows
FILE_NAME = re.compile(r'^[a-z0-9_-]{1,60}\.(js|css)$')
SERVE_NAME = re.compile(r'^[a-z0-9_-](?:[a-z0-9_.-]{0,58}[a-z0-9_-])?\.(js|css|json|svg|png|html)$')   # dots inside a name are fine (tool.schema.json); '..' is not a name
SERVE_TYPES = {'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8', 'json': 'application/json; charset=utf-8',
               'svg': 'image/svg+xml', 'png': 'image/png', 'html': 'text/html; charset=utf-8'}
EVENT_NAME = re.compile(r'^[a-z]+(\.[a-z]+){1,2}$')
ROUTE = re.compile(r'^(GET|POST) (/(api|uix)(/[A-Za-z0-9_.-]+)*(/\*)?)$')
VERSION = re.compile(r'^\d+\.\d+\.\d+$')
NEED = re.compile(r'^(>=|<=|>|<|==)?(\d+)(?:\.(\d+))?$')

TOOL_KEYS = {'id', 'name', 'version', 'handles', 'kind', 'entry', 'api', 'events', 'trust', 'tests', 'needs', 'description', 'order', 'slot', 'instanzen', 'gedaechtnis'}
SHELL_KEYS = {'id', 'name', 'version', 'entry', 'provides', 'layout', 'trust', 'needs', 'api', 'description', 'vorgabe'}
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
    if entry is None and doc.get('vorgabe') is not None:
        pass                                                        # eine Shell aus Vorgabe hat keinen eigenen Code
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
    if trust == 'COMMUNITY':
        routes = [r for r in routes if r.startswith('GET ')]           # foreign modules read; writing needs the Captain's review
    return js, css, routes


def check_tool(doc, folder: Path, origin='package'):
    """(manifest, errors) for a tool.yaml document."""
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
    if errors:
        return None, errors
    return {'id': t['id'], 'name': t['name'], 'version': t['version'], 'kind': kind, 'handles': handles, 'trust': t['trust'],
            'origin': origin, 'order': order, 'slot': slot, 'description': str(t.get('description') or ''),
            'own_types': own_types, 'instanzen': instanzen, 'gedaechtnis': list(dict.fromkeys(gedaechtnis)),
            'events': {'emits': list(events.get('emits') or []), 'listens': list(events.get('listens') or [])},
            'js': js, 'css': css, 'api': routes, 'tests': tests}, []


def check_shell(doc, folder: Path, origin='package'):
    errors = []
    if not isinstance(doc, dict) or not isinstance(doc.get('shell'), dict):
        return None, ['shell_mapping_required']
    s = doc['shell']
    js, css, routes = _common(s, 'shell', folder, origin, errors)
    if s.get('vorgabe') is not None:
        return _check_frame_shell(s, folder, origin, errors)
    provides = s.get('provides') or []
    if not isinstance(provides, list) or not provides or not all(p in SLOTS for p in provides):
        errors.append('provides_invalid')
    layout = s.get('layout') or {'persist': 'browser'}
    if not isinstance(layout, dict) or layout.get('persist') not in ('browser', 'none'):
        errors.append('layout_invalid')
    if errors:
        return None, errors
    return {'id': s['id'], 'name': s['name'], 'version': s['version'], 'provides': provides, 'layout': layout, 'trust': s['trust'],
            'origin': origin, 'description': str(s.get('description') or ''), 'js': js, 'css': css, 'api': routes}, []


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
            'frame': True, 'vorgabe': vorgabe}, []


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


class Gateway:
    def __init__(self, project_root: Path, registry: Registry | None = None):
        self.registry = registry or Registry(project_root)

    def _load(self, kind):
        """{id: (folder, manifest)} and the rejected folders with their reasons."""
        name, check = ('tool.yaml', check_tool) if kind == 'tools' else ('shell.yaml', check_shell)
        ok, rejected = {}, []
        for folder, origin, problem in self.registry.module_dirs(kind):
            if problem:
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': [problem]}); continue
            path = folder / name
            if not path.is_file():
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': [name + '_missing']}); continue
            try:
                doc = yaml.safe_load(path.read_text(encoding='utf-8'))
            except (yaml.YAMLError, UnicodeDecodeError) as exc:
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': [f'yaml_unreadable:{type(exc).__name__}']}); continue
            man, errors = check(doc, folder, origin)
            if errors:
                rejected.append({'kind': kind[:-1], 'id': folder.name, 'origin': origin, 'reasons': errors}); continue
            ok[man['id']] = (folder, man)
        return ok, rejected

    def tools(self):
        return self._load('tools')[0]

    def shells(self):
        return self._load('shells')[0]

    def manifest(self):
        cfg = self.registry.config()
        shells, rej_s = self._load('shells')
        tools, rej_t = self._load('tools')
        rejected = rej_s + rej_t
        active = cfg['shell'] if cfg['shell'] in shells else None
        if active is None:
            rejected.append({'kind': 'shell', 'id': cfg['shell'], 'origin': 'config', 'reasons': ['active_shell_not_available']})
        disabled = set(cfg['disabled'])
        ids = [t for t in tools if t not in disabled]
        ids.sort(key=lambda t: (tools[t][1]['order'], t))
        ids = self.registry.ordered(ids) if cfg['order'] else ids

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
                'shell': public('shells', shells[active][1]) if active else None,
                'shells': sorted(shells),
                'tools': [public('tools', tools[t][1]) for t in ids],
                'disabled': sorted(disabled & set(tools)),
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
        info = info.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{_html.escape(t["name"])}</title>{links}</head>'
                '<body><div id="werk"></div>' + scripts + f'<script>sedraRahmen.start({info});</script></body></html>')

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
        if kind == 'tool' and 'ablage' in (man.get('gedaechtnis') or []) and route_allowed(ABLAGE_ROUTES, method, path):
            return True
        return route_allowed(man['api'], method, path)
