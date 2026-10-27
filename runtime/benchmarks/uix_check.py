r"""Browser check of the UIX: the Cockpit runs in a real (headless) Chromium, every tool is opened in the dock, and what the Captain
would see is measured. This is the acceptance of SHELL_WERKZEUG_VERTRAG_v1 §8 – a UIX candidate passes only if `result ok` is printed.

    .venv\Scripts\python.exe benchmarks/uix_check.py [--shell cockpit|minimal] [--tool <id>] [--url URL] [--shots DIR] [--browser …] [--headed]

Without --url the script starts its own uix_server on a temporary project (no GPU, no model; the host programs are isolated the way the
tests do it), so it can run on any PC. Needs the Python package `playwright` (pip install playwright) and a browser: the bundled Chromium
(`python -m playwright install chromium`) or the Edge/Chrome already on the PC (--browser msedge / chrome).

Why (Claude 2026-10-13): the chat window opened without title bar and toolbar for days; reading the code and the static tests did not
show that. Since Build 7 the same idea checks the contract instead of windows: a tool must fill its container, clean up after itself
and stay inside its allowlist.

Checks (each line of the report is one check, `ok` or `FAIL`):
  load          page, contract files and every module file load; shell and tools registered; no JavaScript error
  zones         the zones of this shell are there and inside the viewport (cockpit: strip/tree/dock/talk, minimal: menubar/desk/shelf)
  strip         every instrument drew a value (no empty cell)
  tool:<id>     opened in the dock: container filled, no console error, actions offered, unmount empties it again, no foreign route called
  talk          a line typed into the Gespräch reaches the log and the input keeps the focus
  palette       Strg+K opens, a navigation phrase offers the place first, Escape closes
  layout        the dock remembers the open tabs across a reload
  nav, windows, idle   Shell D only (Spec 4): every navigation entry, the stack of agent windows, no polling (uix_check_team.py)
  retro         the old desktop (/retro) still loads
  console       no console error apart from the allowed ones
Exit code 0 when every check is ok."""
import argparse
import json
import sys
import tempfile
import threading
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))          # uix_check_team, uix_fixture_orchestra liegen daneben
LAST_HUB = None
TEAM_AGENT = 'A-UA'                                                 # der Unterarbeiter der Fixture (uix_fixture_orchestra.AGENTS)
ALLOWED_FAILURES = ('/api/processes',)
# Werkzeuge, deren Objekt im Prüfprojekt wirklich Verben hat: dort muss die Werkbank-Zeile welche zeigen (Cockpit-Regel 3).
# Ein Nachweis, eine Liste oder ein Objekt ohne mögliche Handlung (die Werkstatt ohne geladenes Modell) ist richtig so.
VERB_TOOLS = ('candidate',)      # PowerShell is missing on a non-Windows host; the window says so and goes on

# which object each tool is opened with (the dock asks the registry, this is the object the Captain would pick)
OBJECTS = {
    'task': {'type': 'task', 'id': 'alle', 'title': 'Aufgaben'},
    'decisions': {'type': 'decision', 'id': 'alle', 'title': 'Entscheidungen'},
    'files': {'type': 'project', 'id': 'projekt', 'title': 'Projekt'},
    'workshop': {'type': 'model', 'id': 'alle', 'title': 'Werkstatt'},
    'library': {'type': 'skill', 'id': 'own', 'title': 'Bibliothek'},
    'crew': {'type': 'agent', 'id': 'rollen', 'title': 'Agenten', 'collection': True},      # Spec 4: die Rollenliste (agent:rollen)
    'meter': {'type': 'meter', 'id': 'meter', 'title': 'Guppy-Meter'},
    'logbook': {'type': 'logbook', 'id': 'audit', 'title': 'Logbuch'},
    'system': {'type': 'machine', 'id': 'machine', 'title': 'Maschinenraum'},
    # Build 9
    'intent': {'type': 'intent', 'id': 'alle', 'title': 'Vorhaben', 'collection': True},
    'boundaries': {'type': 'boundary', 'id': 'projekt', 'title': 'Modus und Grenzen'},
    'modules': {'type': 'module', 'id': 'alle', 'title': 'Module', 'collection': True},
    # Build 19: das KI GateWay – die Liste der Vorgänge; `schutz` ist der Nachweis daneben
    'gateway': {'type': 'gateway', 'id': 'alle', 'title': 'KI GateWay', 'collection': True},
    'schutz': {'type': 'gateway', 'id': None, 'title': 'Vorgang'},          # der Nachweis steht neben einem Vorgang, nicht neben der Liste
    # Build 8: diese drei stehen neben einem Werkstück, nicht allein – uix_check öffnet sie über ihr Objekt
    'candidate': {'type': 'candidate', 'id': None, 'title': 'Kandidat'},
    'tests': {'type': 'candidate', 'id': None, 'title': 'Kandidat'},
    'live': {'type': 'task', 'id': None, 'title': 'Aufgabe'},
    'costs': {'type': 'task', 'id': None, 'title': 'Aufgabe'},
    # Spec 4 (D4.4): die Werkzeuge des Agenten-Teams; ein Agent öffnet sich als Fenster im Stapel (id aus der Fixture)
    'org': {'type': 'agent', 'id': 'alle', 'title': 'Organigramm', 'collection': True},
    'board': {'type': 'issue', 'id': 'alle', 'title': 'Issues', 'collection': True},
    'routines': {'type': 'routine', 'id': 'alle', 'title': 'Routinen', 'collection': True},
    'slots': {'type': 'model', 'id': 'alle', 'title': 'Modelle und Slots', 'collection': True},
    'agentfenster': {'type': 'agent', 'id': None, 'title': 'Agent'},
    'labor': {'type': 'labor', 'id': 'labor', 'title': 'KI-Labor'},
    'wissen': {'type': 'wissen', 'id': 'speicher', 'title': 'Wissen'},                   # Spec 7 (D7.9): der Wissensspeicher
    'fundstelle': {'type': 'wissen', 'id': 'speicher', 'title': 'Wissen'},               # SPEC_SHELL_WISSEN_v1 §4.2: Nachweis neben dem Wissen
}

MEASURE_ZONES = """(names) => {
  const z = {};
  for(const name of names){
    const el = document.querySelector('.' + name);
    if(!el){ z[name] = {missing:true}; continue; }
    const r = el.getBoundingClientRect();
    z[name] = {w: Math.round(r.width), h: Math.round(r.height), inside: r.top >= -1 && r.bottom <= innerHeight + 1 && r.right <= innerWidth + 1};
  }
  return z;
}"""

MEASURE_PANE = """(tool) => {
  const body = document.querySelector('.dk-group .dk-body');
  const verbs = document.querySelector('.dk-group .dk-verbs');
  if(!body) return {missing:true};
  // Stufe 2: je Reiter eine Fläche; gemessen wird die sichtbare (versteckt eingehängte Reiter zählen nicht)
  const pane = body.querySelector(':scope > .dk-pane-box:not([hidden])') || body;
  const own = pane.querySelector('.dk-tool[data-tool="' + tool + '"]');
  if(!own) return {missing:true, note:'das Werkzeug hat keinen Container in diesem Reiter'};
  const slots = [...pane.querySelectorAll('.dk-tool')];
  const r = body.getBoundingClientRect();
  return {text: own.innerText.trim().length, slots: slots.length,
          filled: own.innerText.trim().length > 0 || own.childElementCount > 0,
          evidence: !!own.closest('.dk-pane-evidence'),
          actions: verbs ? verbs.querySelectorAll('button').length : 0, inside: r.bottom <= innerHeight + 1, scroll: Math.round(body.scrollTop)};
}"""


MEASURE_PANE_MINIMAL = """(tool) => {
  const slot = document.querySelector('.sh-min-win .sh-min-tool[data-tool="' + tool + '"]');
  if(!slot) return {missing:true, note:'das Werkzeug hat kein Fenster'};
  const win = slot.closest('.sh-min-win');
  const r = win.getBoundingClientRect();
  const segs = [...win.querySelectorAll('.sh-min-seg-item')];
  const at = segs.findIndex(s => s.dataset.tool === tool);
  // Nachweis heißt: der Reiter steht hinter allen Inhalt-Reitern des Fensters. Zwei Inhalt-Werkzeuge auf demselben Objekt
  // (model:alle: slots und workshop, Spec 4 D4.1) sind beide Werkstück, auch das zweite.
  const all = window.sedraBoot.ctx.tools.all();
  const inhalt = segs.filter(s => ((all.find(t => t.id === s.dataset.tool) || {}).slot || 'inhalt') !== 'nachweis').length;
  return {text: slot.innerText.trim().length, slots: win.querySelectorAll('.sh-min-tool').length,
          filled: slot.innerText.trim().length > 0 || slot.childElementCount > 0,
          evidence: at >= inhalt,
          actions: win.querySelectorAll('.sh-min-verbs button').length,
          inside: r.bottom <= innerHeight + 1 && r.right <= innerWidth + 1, scroll: 0};
}"""

MEASURE_PANE_PAPERCLIP = """(tool) => {
  const slot = document.querySelector('.pc-page .pc-tool[data-tool="' + tool + '"], .pc-stack .pc-win:not([hidden]) .pc-tool[data-tool="' + tool + '"]');
  if(!slot) return {missing:true, note:'das Werkzeug hat keinen Container auf dieser Seite'};
  const r = slot.getBoundingClientRect();
  return {text: slot.innerText.trim().length, slots: document.querySelectorAll('.pc-page .pc-tool').length,
          filled: slot.innerText.trim().length > 0 || slot.childElementCount > 0,
          evidence: !!slot.closest('.pc-side'),
          actions: document.querySelectorAll('.pc-verbs button').length,
          inside: r.right <= innerWidth + 1, scroll: 0};
}"""

MEASURE_PANE_GENERIC = """(tool) => {
  const slot = document.querySelector('[data-tool="' + tool + '"]');
  if(!slot) return {missing:true, note:'kein Container mit data-tool – die Shell markiert ihre Container nicht (Vertrag)'};
  // „im Rahmen“ heißt: der nächste scrollende Vorfahr liegt im Bild – ein langes Werkzeug darf darin nach unten laufen
  let frame = slot;
  while(frame && frame !== document.body){
    const o = getComputedStyle(frame).overflowY;
    if(o === 'auto' || o === 'scroll') break;
    frame = frame.parentElement;
  }
  const r = (frame || slot).getBoundingClientRect();
  return {text: slot.innerText.trim().length, slots: document.querySelectorAll('[data-tool]').length,
          filled: slot.innerText.trim().length > 0 || slot.childElementCount > 0,
          evidence: !!slot.closest('[data-slot="nachweis"]'),
          actions: document.querySelectorAll('[data-verbs] button').length,
          inside: r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1, scroll: 0};
}"""

# Für jede Shell, die hier niemand kennt: nur die Vertragsmarken (data-tool, data-verbs, data-slot) – und wo das Profil nichts
# weiß, sagt der Bericht „nicht geprüft“ statt zu raten. Eine eigene Shell bekommt so eine ehrliche Abnahme, nicht keine.
GENERIC = {
    'zones': (), 'gauges': '[data-tool^="gauge-"]', 'pane': MEASURE_PANE_GENERIC, 'segment': None,
    'leftovers': None, 'count': None, 'count_word': '', 'menu': None,
}

# Was an einer Shell shell-eigen ist, steht hier im Prüfwerkzeug – nicht in der Shell. Eine Shell, die ihre eigene Prüfung
# mitbringt, prüft sich selbst (Spec SHELL_E §1.5). Alles andere (Werkzeuge, talk, console, allowlist, retro) gilt für jede Shell.
PROFILES = {
    'cockpit': {
        'zones': ('ck-strip', 'ck-tree', 'ck-bench', 'ck-talk'),
        'gauges': '.ck-gauge:not(.ck-hint)',
        'pane': MEASURE_PANE,
        'segment': None,                       # im Cockpit stehen Werkstück und Nachweise zugleich im Reiter
        'eingebettet': ('schutz',),            # Build 19: der Schutz läuft im Menü des GateWay, hat hier keinen eigenen Reiter (nicht geprüft)
        'leftovers': "()=>[...document.querySelectorAll('.dk-body > .dk-pane-box:not([hidden]) .dk-tool, .dk-body > .dk-tool')].map(s=>s.dataset.tool)",
        'count': "()=>document.querySelectorAll('.dk-tab').length",
        'count_word': 'Reiter',
        'menu': {'box': '.pal', 'input': '.pal-box input', 'rows': "()=>[...document.querySelectorAll('.pal-row b')].map(b=>b.textContent)",
                 'closed': "()=>!!document.querySelector('.pal').hidden"},
    },
    'paperclip': {
        'zones': ('pc-nav', 'pc-top', 'pc-page'),
        'gauges': '.pc-kpi',
        'pane': MEASURE_PANE_PAPERCLIP,
        'segment': None,                       # Werkstück und Nachweise stehen zugleich auf der Seite
        # Spec 4: ein Fenster im Stapel zählt mit – nach dem Messen eines Agentenfensters schließt `after_tool` es wieder
        'leftovers': "()=>[...document.querySelectorAll('.pc-page .pc-tool, .pc-stack .pc-tool')].map(s=>s.dataset.tool)",
        'after_tool': "()=>{ const w = window.sedra.shells.get('paperclip').windows; w.list().forEach(x=>w.close(x.id)); }",
        'team': True,                          # die Prüfzeilen nav, windows, idle (uix_check_team.py)
        'count': "()=>{ try{ return JSON.parse(localStorage.getItem('sedra.paperclip.history') || '[]').length; }catch(e){ return 0; } }",
        'count_word': 'Seiten im Verlauf',
        'menu': {'box': '.pc-search-results', 'input': '.pc-search input', 'rows': "()=>[...document.querySelectorAll('.pc-search-row b')].map(b=>b.textContent)",
                 'closed': "()=>!!document.querySelector('.pc-search-results').hidden"},
        'before_tools': "()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'dashboard', id:'start', title:'Dashboard'})",
        'before_talk': "()=>{ const f = document.querySelector('.pc-fab'); if(f && getComputedStyle(f).display !== 'none') f.click(); }",
    },
    # GUPPI XP (Build 18): der Build-6-Desktop als Wahl. Er hat Fenster, aber keine des Vertrags – geprüft wird nur, dass die
    # alte Seite mit Desktop lädt (siehe run_checks, Zweig /retro); alles andere „nicht geprüft“.
    'guppi-xp': dict(GENERIC, archive='/retro'),
    'minimal': {
        'zones': ('sh-min-bar-top', 'sh-min-desk', 'sh-min-shelf'),
        'gauges': '.sh-min-gauge',
        'pane': MEASURE_PANE_MINIMAL,
        'segment': "(tool)=>{const s = document.querySelector('.sh-min-seg-item[data-tool=\"' + tool + '\"]'); if(s) s.click(); return !!s;}",
        'leftovers': "()=>[...document.querySelectorAll('.sh-min-win.on .sh-min-tool')].map(s=>s.dataset.tool)",
        'count': "()=>document.querySelectorAll('.sh-min-win').length",
        'count_word': 'Fenster',
        'menu': {'box': '.sh-min-menu', 'input': '.sh-min-menu input', 'rows': "()=>[...document.querySelectorAll('.sh-min-menu-item b')].map(b=>b.textContent)",
                 'closed': "()=>!document.querySelector('.sh-min-menu')"},
    },
    # Shell „Fisch“ (19.10.2026): Kopf, Glas, Wolke, Blasen; das Gespräch ist eine Schublade (Knopf unten rechts), Nachweise in der Blase
    'fisch': {
        'zones': ('fi-kopf', 'fi-glas', 'fi-wolke', 'fi-blasen'),
        'gauges': '[data-tool^="gauge-"]',
        'pane': MEASURE_PANE_GENERIC,
        'segment': None,
        'leftovers': "()=>[...document.querySelectorAll('.fi-blasen .fi-tool')].map(s=>s.dataset.tool)",
        'count': None,                     # eine Blase zur Zeit; was ein Neuladen übersteht, ist der Modus (test_uix_shell_fisch)
        'count_word': '',
        'menu': None,
        'before_talk': "()=>{ const f = document.querySelector('.fi-fab'); if(f && getComputedStyle(f).display !== 'none') f.click(); }",
    },
    # Shell „KI Gateway für KMU“ (Folien-Design): Kopf, Werkstück, Gespräch; die vier Schritte des Ablaufs sind ihre Messwerte
    'gateway-kmu': {
        'zones': ('sh-gateway-kmu-kopf', 'sh-gateway-kmu-body', 'sh-gateway-kmu-talk'),
        'gauges': '.sh-gateway-kmu-schritt',
        'pane': "(tool) => {const slot = document.querySelector('.sh-gateway-kmu-tool[data-tool=\"' + tool + '\"]'); if(!slot) return {missing:true, note:'das Werkzeug hat keinen Container'}; const r = slot.getBoundingClientRect(); return {text: slot.innerText.trim().length, slots: document.querySelectorAll('.sh-gateway-kmu-tool').length, filled: slot.innerText.trim().length > 0 || slot.childElementCount > 0, evidence: false, actions: document.querySelectorAll('.sh-gateway-kmu-verbs button').length, inside: r.right <= innerWidth + 1, scroll: 0};}",
        'segment': None,
        'leftovers': "()=>[...document.querySelectorAll('.sh-gateway-kmu-werkstueck .sh-gateway-kmu-tool')].map(s=>s.dataset.tool)",
        'no_evidence': True,     # die Shell zeigt Nachweise (slot: nachweis) bewusst nicht daneben – das Gateway hat seinen Überblick selbst
        'count': None,
        'count_word': '',
        'menu': None,
    },
}


def frame_profile(vorgabe):
    """Eine Shell aus Vorgabe (ui/frame.js) bringt ihr Profil mit: die Zonen stehen im Raster, die Flächen heißen fr-…, und was
    der Rahmen merkt, steht in localStorage. Deshalb wird sie ganz geprüft – nichts „nicht geprüft“."""
    zones = [z for row in (vorgabe.get('raster') or []) for z in str(row).split('|')]
    rand = {z for z in ('orte', 'leiste') if (vorgabe.get(z) or {}).get('einblenden') == 'rand'}   # am Rand verborgen: nicht als Zone messen
    zones = [z for z in zones if z not in rand]
    gesp = (vorgabe.get('gespraech') or {}).get('art', 'zone')
    nachweise = (vorgabe.get('werkstueck') or {}).get('nachweise', 'seitenleiste')
    key = 'sedra.frame.' + vorgabe['id']
    p = {
        'zones': tuple('fr-zone-' + z for z in zones if z != 'gespraech' or gesp == 'zone'),
        'gauges': '.fr-gauge', 'pane': MEASURE_PANE_GENERIC,
        'segment': "(tool)=>{const s = document.querySelector('.fr-seg-item[data-seg=\"' + tool + '\"]'); if(s) s.click(); return !!s;}" if nachweise == 'umschalter' else None,
        'leftovers': "()=>[...document.querySelectorAll('.fr-body .fr-tool')].map(s=>s.dataset.tool)",
        'count': "()=>{ try{ return (JSON.parse(localStorage.getItem('" + key + "') || '{}').history || []).length; }catch(e){ return 0; } }",
        'count_word': 'Orte im Verlauf',
        'menu': {'box': '.fr-pal', 'input': '.fr-pal-box input', 'rows': "()=>[...document.querySelectorAll('.fr-pal-row b')].map(b=>b.textContent)",
                 'closed': "()=>!!document.querySelector('.fr-pal').hidden"} if vorgabe.get('suche', 'strg-k') == 'strg-k' else None,
    }
    if vorgabe.get('suche', 'strg-k') == 'feld':
        p['search_field'] = '.fr-search'
    if vorgabe.get('suche', 'strg-k') == 'keine':
        p['no_search'] = 'die Vorgabe hat keine Suche (suche: keine) – das Gespräch ist der Weg'
    if gesp == 'schublade':
        p['before_talk'] = "()=>{ const b = document.querySelector('.fr-drawer-btn'); if(b && !document.querySelector('.fr-drawer.on')) b.click(); }"
    return p


def start_server(say, shell=None, prepare=None, switches=None):
    """A UIXHub on a temporary project with one project folder and one mission; returns (url, stop).
    `prepare(hub)` darf das Prüfprojekt vorher umbauen – etwa ein fremdes Modul einbauen, bevor der Browser es sieht.
    `switches` ({name: bool}) steht vor dem Start in local_config/switches.yaml – der Hub liest die Schalter beim Start."""
    sys.path.insert(0, str(RUNTIME / 'src')); sys.path.insert(0, str(RUNTIME / 'tests'))
    try:
        import host_isolation
        host_isolation.setUpModule()
    except Exception as exc:                     # the check still works, it just talks to the real nvidia-smi etc.
        say(f'note: host isolation not active ({exc})')
    from guppi_runtime.uix_server import UIXHub, make_server
    arch = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
    tmp = tempfile.TemporaryDirectory(prefix='guppi-uix-check-')
    if switches:
        config = Path(tmp.name) / 'project' / 'local_config'
        config.mkdir(parents=True, exist_ok=True)
        (config / 'switches.yaml').write_text('switches:\n' + ''.join(f'  {k}: {{enabled: {"true" if v else "false"}}}\n' for k, v in switches.items()), encoding='utf-8')
    hub = UIXHub(Path(tmp.name) / 'project', arch)
    if shell:                                   # genau diese Shell prüfen (uix.yaml, wie auf dem PC)
        config = Path(tmp.name) / 'project' / 'local_config'
        config.mkdir(parents=True, exist_ok=True)
        (config / 'uix.yaml').write_text(f'uix:\n  shell: {shell}\n', encoding='utf-8')
    project = hub.new_project({'name': 'Prüfprojekt'})
    ws = hub.runtime.filesystem_tool._resolve(project['workspace_path'], must_exist=True)
    (ws / 'README.md').write_text('# Prüfprojekt\n', encoding='utf-8')
    hub.create_chat_mission({'intent': 'Create a GUPPI demo artifact', 'project_id': project['project_id']})
    _candidate(hub, ws)
    _vorgang(hub)
    if prepare: prepare(hub)
    server, url = make_server(hub)
    global LAST_HUB
    LAST_HUB = hub                                # ein Test darf das Prüfprojekt umbauen (eine eigene Shell anlegen), bevor er prüft
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.25}, daemon=True); thread.start()

    def stop():
        server.shutdown(); server.server_close(); hub.close(); tmp.cleanup()
    return url, stop


LAST_VORGANG = None


def _vorgang(hub):
    """Ein geprüfter GateWay-Vorgang im Prüfprojekt (Build 19), damit das Werkzeug und sein Nachweis an Daten gemessen werden."""
    global LAST_VORGANG
    try:
        v = hub.gateway_new({'titel': 'Projektabstimmung vorbereiten', 'wunsch': 'local'})
        hub.gateway_pruefen({'id': v['id'], 'anfrage': 'Lena Beispiel von der Nordwerk Muster GmbH fragt per lena@example.com nach dem Stand von NORD-42. Kundennummer: K-1042.'})
        LAST_VORGANG = v['id']
    except Exception:
        LAST_VORGANG = None


def _candidate(hub, workspace):
    """Ein echter Kandidat im Prüfprojekt, damit Diff, Tests und Kosten an Daten gemessen werden und nicht an einer leeren Seite."""
    import hashlib
    rt = hub.runtime
    folder = rt.filesystem_tool.root / 'demo'
    folder.mkdir(parents=True, exist_ok=True)
    old = 'def greet(name):\n    return name\n'
    new = 'def greet(name):\n    return "Hallo " + name\n'
    (folder / 'app.py').write_text(old, encoding='utf-8')
    request = {'project_path': 'demo', 'files': ['app.py'],
               'changes': [{'path': 'app.py', 'expected_sha256': hashlib.sha256(old.encode()).hexdigest(), 'content': new}]}
    try:
        mission = rt.brain.create_mission('Ändere Code als Kandidat', inputs=request)
        return rt.brain.run(mission['identity']['mission_id'])['identity']['mission_id']
    except Exception:
        return None


def launch(pw, browser, headed):
    """The bundled Chromium, or the Edge/Chrome of this PC when asked for or when the bundled one is missing."""
    order = [browser] if browser != 'auto' else ['chromium', 'msedge', 'chrome']
    last = None
    for name in order:
        try:
            if name == 'chromium': return pw.chromium.launch(headless=not headed)
            return pw.chromium.launch(channel=name, headless=not headed)
        except Exception as exc:
            last = exc
    raise RuntimeError(f'no browser could be started ({last}); run `python -m playwright install chromium` or use --browser msedge')


def wait_until_started(page, ms=15000):
    """Warten, bis die Shell wirklich steht – nicht eine feste Zahl Millisekunden.

    Ein fester Wert war ein Rennen: mit vielen wiederhergestellten Fenstern war die Minimal-Shell nach 2,5 s noch nicht fertig,
    und die Prüfung brach mit einem TypeError ab statt einen Befund zu melden (15.10.2026)."""
    try:
        page.wait_for_function('()=>!!(window.sedraBoot && window.sedraBoot.ctx)', timeout=ms)
    except Exception:
        pass            # kein Abbruch: die Prüfung `load` meldet gleich selbst, dass keine Shell da ist


def run_checks(url, say=print, shots=None, browser='auto', headed=False, only=None, shell='cockpit', fixture=None):
    """Runs every check against a running UIX; returns the list of (name, ok, detail)."""
    profile = PROFILES.get(shell, GENERIC)
    generic = shell not in PROFILES or bool(profile.get('archive'))
    from playwright.sync_api import sync_playwright
    results, errors, console, failed, calls = [], [], [], [], []

    def check(name, ok, detail=''):
        # ok=None heißt „nicht geprüft“: die Prüfung gibt es für diese Shell nicht – das steht im Bericht, zählt aber nicht als ok
        results.append((name, None if ok is None else bool(ok), detail))
        say(f'{name:<22} {"–" if ok is None else ("ok" if ok else "FAIL")}  {detail}'.rstrip())

    with sync_playwright() as pw:
        b = launch(pw, browser, headed)
        page = b.new_page(viewport={'width': 1400, 'height': 860})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: console.append(m.text) if m.type == 'error' and not any(a in (m.location or {}).get('url', '') for a in ALLOWED_FAILURES) else None)
        page.on('response', lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None)
        page.on('request', lambda r: calls.append((r.method, r.url.split('#')[0], (r.headers or {}).get('x-sedra-tool', ''), (r.headers or {}).get('x-sedra-shell', ''))) if '/api/' in r.url else None)
        page.on('dialog', lambda d: d.accept() if d.type != 'prompt' else d.dismiss())
        page.goto(url)
        # GUPPI XP (shells/guppi-xp): die Shell führt auf den archivierten Desktop. Dort gibt es keinen Vertrag – geprüft wird nur,
        # dass die alte Seite mit Desktop und Token lädt; alles andere heißt ehrlich „nicht geprüft“.
        try:
            page.wait_for_function("()=>location.pathname === '/retro' || !!(window.sedraBoot && window.sedraBoot.ctx)", timeout=15000)
        except Exception:
            pass
        try:
            page.wait_for_load_state(); on_retro = page.evaluate("()=>location.pathname") == '/retro'
        except Exception:                                   # die Seite wechselt gerade (GUPPI XP leitet weiter): kurz warten, nochmal
            page.wait_for_timeout(1500); on_retro = page.evaluate("()=>location.pathname") == '/retro'
        if on_retro:
            page.wait_for_timeout(1500)
            has_desktop = page.evaluate("()=>!!document.getElementById('desktop')")
            bad = [f for f in failed if not any(a in f[1] for a in ALLOWED_FAILURES)]
            check('load', has_desktop and not bad and not errors, 'GUPPI XP: der alte Desktop (/retro) ist da' if has_desktop else 'kein Desktop auf /retro')
            for name in ('zones', 'strip', 'tools', 'breite', 'unmount', 'talk', 'palette', 'layout'):
                check(name, None, 'nicht geprüft – GUPPI XP ist der alte Desktop ohne Vertragsmarken')
            check('retro', has_desktop, 'HTTP 200' if has_desktop else 'kein Desktop')
            check('console', not console and not errors, '; '.join(console + errors)[:300])
            if shots: page.screenshot(path=str(Path(shots) / '00_guppi_xp.png'))
            b.close(); return results
        page.wait_for_timeout(1500)
        if shots: page.screenshot(path=str(Path(shots) / '00_cockpit.png'))

        manifest = page.evaluate("()=>window.sedraBoot && window.sedraBoot.ctx ? {shell: window.sedraBoot.ctx.manifest.shell.id, tools: window.sedraBoot.ctx.tools.all().map(t=>t.id), slots: Object.fromEntries(window.sedraBoot.ctx.tools.all().map(t=>[t.id, t.slot || 'inhalt'])), rejected: window.sedraBoot.ctx.manifest.rejected, problems: window.sedraBoot.problems, vorgabe: window.sedraBoot.ctx.manifest.shell.vorgabe || null} : null")
        if manifest and manifest.get('vorgabe') and shell not in PROFILES:
            profile, generic = frame_profile(manifest['vorgabe']), False
        manifest_slot = (manifest or {}).get('slots') or {}
        bad = [f for f in failed if not any(a in f[1] for a in ALLOWED_FAILURES)]
        check('load', manifest and not bad and not errors,
              '; '.join([f'{s} {u}' for s, u in bad] + errors + [r['id'] + ': ' + ', '.join(r['reasons']) for r in (manifest or {}).get('rejected', [])] + (manifest or {}).get('problems', []))[:300]
              or (f"Shell {manifest['shell']}, {len(manifest['tools'])} Werkzeuge" if manifest else 'die Shell ist nicht gestartet'))
        if not manifest:
            check('zones', False, 'no shell'); b.close(); return results

        if profile['zones']:
            zones = page.evaluate(MEASURE_ZONES, list(profile['zones']))
            missing = [n for n, z in zones.items() if z.get('missing') or not z.get('inside')]
            check('zones', not missing, ', '.join(missing) or ' · '.join(f'{n} {z["w"]}x{z["h"]}' for n, z in zones.items()))
        else:
            check('zones', None, 'nicht geprüft – kein Profil für diese Shell; die Zonen kennt nur ihr Autor')
        provides = page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.provides || []")
        opens = any(p in provides for p in ('dock', 'windows'))

        if profile.get('before_tools'):
            page.evaluate(profile['before_tools']); page.wait_for_timeout(800)
        # Ein Instrument im abgeschotteten Rahmen zeichnet seinen Wert im Rahmen (eigenes Dokument): die Zelle zählt dann als gefüllt
        strip = page.evaluate("(sel)=>[...document.querySelectorAll(sel)].map(g=>({tool: g.dataset.tool || '?', value: g.querySelector('iframe') ? 'im Rahmen' : ((g.querySelector('b')||{}).textContent || '')}))", profile['gauges'])
        empty = [g['tool'] for g in strip if not g['value'].strip() or g['value'] == '…']
        if not strip and 'strip' not in provides and 'menubar' not in provides:
            check('strip', None, 'nicht geprüft – diese Shell verspricht keine Instrumente (provides ohne strip/menubar)')
        else:
            check('strip', strip and not empty, ', '.join(empty) or f'{len(strip)} Instrumente: ' + ' · '.join(g['value'] for g in strip)[:120])

        # Aufgaben dieses Prüfprojekts: der Kandidat für candidate/tests, die Aufgabe für live/costs
        found = page.evaluate("""async ()=>{
          const ms = await (await fetch('/api/missions', {headers: {'X-GUPPI-Token': decodeURIComponent(location.hash.slice(1))}})).json();
          return {candidate: (ms.find(m=>m.phase === 'CANDIDATE_REVIEW') || {}).mission_id || null, task: (ms[0] || {}).mission_id || null};
        }""")
        # Ein fremdes Werkzeug mit eigenem Objekttyp steht nicht in OBJECTS: sein Objekt ist dann seine Sammlung (handles[0], 'alle')
        own = page.evaluate("()=>Object.fromEntries(window.sedraBoot.ctx.tools.all().filter(t=>t.kind === 'object' && (t.handles || []).length).map(t=>[t.id, {type: t.handles[0], id: 'alle', title: t.name, collection: true}]))")
        for tid, obj in own.items():
            OBJECTS.setdefault(tid, obj)
        wanted = [t for t in manifest['tools'] if t in OBJECTS and (not only or t == only)]
        if not opens:
            check('tools', None, f'nicht geprüft – diese Shell öffnet keine Objekte (provides: {", ".join(provides)})')
            wanted = []
        for i, tid in enumerate(wanted, 1):
            before = len(calls)
            target = dict(OBJECTS[tid])
            if target['id'] is None and target['type'] == 'agent':      # ein Agent gibt es nur mit der Fixture (Spec 4)
                target['id'] = TEAM_AGENT if fixture == 'orchestra' else None
            elif target['id'] is None:
                target['id'] = found['candidate'] if target['type'] == 'candidate' else LAST_VORGANG if target['type'] == 'gateway' else found['task']
            if target['id'] is None:
                check('tool:' + tid, None, 'nicht geprüft – im Prüfprojekt gibt es kein Objekt dieses Typs (kein Fehler des Werkzeugs)')
                continue
            if tid in profile.get('eingebettet', ()):
                check('tool:' + tid, None, 'nicht geprüft – eingebettet im Menü des KI GateWay (kein eigener Reiter, Build 19)')
                continue
            if profile.get('no_evidence') and manifest_slot.get(tid) == 'nachweis':
                check('tool:' + tid, None, 'nicht geprüft – diese Shell zeigt keine Nachweise daneben (Profil)')
                continue
            page.evaluate("(o)=>window.sedraBoot.ctx.bus.emit('object.open', o)", target)
            page.wait_for_timeout(1400)
            if profile['segment']:            # Fenster zeigen eines nach dem anderen: den Nachweis anklicken
                page.evaluate(profile['segment'], tid)
                page.wait_for_timeout(1200)
            m = page.evaluate(profile['pane'], tid)
            if shots: page.screenshot(path=str(Path(shots) / f'{i:02d}_{tid}.png'))
            # Jeder Aufruf nennt seinen Absender: ohne Kopf kann der Server die Allowlist nicht anwenden (§6).
            # Dass in diesem Fenster auch andere Werkzeuge rufen, ist richtig so – in einem Reiter stehen Werkstück und Nachweise nebeneinander.
            nameless = [c for c in calls[before:] if not c[2] and not c[3] and '/api/events' not in c[1]]
            problems = []
            if m.get('missing'): problems.append(m.get('note') or 'kein Container')
            else:
                if not m['filled']: problems.append('Container leer')
                if m['text'] < 10: problems.append('kein Text')
                if not m['actions'] and tid in VERB_TOOLS: problems.append('keine Handlungen, obwohl das Objekt welche hat')
                if not m['inside']: problems.append('ragt aus dem Rahmen')
                if (manifest_slot.get(tid) == 'nachweis') != m['evidence']: problems.append('steht in der falschen Spalte')
            if nameless: problems.append('Aufruf ohne Absender: ' + nameless[0][1].split('/api/')[-1])
            check('tool:' + tid, not problems, ', '.join(problems) or f"{m['slots']} Werkzeug(e) im Reiter, {m['actions']} Handlungen"
                  + (', Nachweisspalte' if m.get('evidence') else ''))
            if profile.get('after_tool'):
                page.evaluate(profile['after_tool']); page.wait_for_timeout(200)

        # Viele Reiter dürfen die Seite nicht breiter machen als den Bildschirm: die Leiste scrollt in sich (gefunden 14.10. in Build 8).
        page_overflow = page.evaluate("(sel)=>({x: document.documentElement.scrollWidth - innerWidth,"
                                      " strip: Math.round(([...document.querySelectorAll(sel)].pop() || {getBoundingClientRect:()=>({right:0})}).getBoundingClientRect().right)})",
                                      profile['gauges'])
        page_count = page.evaluate(profile['count']) if profile['count'] else None
        check('breite', page_overflow['x'] <= 0 and page_overflow['strip'] <= 1400,
              (f"{page_count} {profile['count_word']}, " if page_count is not None else '') + f"Überhang {page_overflow['x']} px")

        # the dock empties a container again (§4): opening another object must not leave the old one behind
        if opens and profile['leftovers']:
            page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'logbook', id:'audit', title:'Logbuch'})")
            page.wait_for_timeout(800)
            leftovers = page.evaluate(profile['leftovers'])
            check('unmount', len(leftovers) <= 1, f'{len(leftovers)} Werkzeuge im sichtbaren Container: ' + ', '.join(leftovers))
        else:
            check('unmount', None, 'nicht geprüft – ' + ('die Shell öffnet keine Objekte' if not opens else 'kein Profil: welcher Container sichtbar ist, weiß nur ihr Autor'))

        if profile.get('team') and not only:      # Spec 4: Navigation, Fensterstapel, Leerlauf (Shell D)
            import uix_check_team
            uix_check_team.run(page, check, errors, console, calls, wait_until_started)
            check('fixture', True if fixture == 'orchestra' else None,
                  f'Team aus der Fixture ({fixture})' if fixture == 'orchestra' else
                  f'nur Leerzustand geprüft ({fixture or "ohne Fixture"}) – mit Daten: --fixture orchestra')

        if profile.get('before_talk'):            # in einer Shell mit Schublade muss das Gespräch erst auf – wie beim Captain
            page.evaluate(profile['before_talk']); page.wait_for_timeout(400)
        page.fill('.t-talk-in input', 'logbuch')
        page.press('.t-talk-in input', 'Enter')
        page.wait_for_timeout(1000)
        talk = page.evaluate("()=>({lines: document.querySelectorAll('.t-talk-line').length, text: document.querySelector('.t-talk-log').innerText.slice(-80), focus: document.activeElement === document.querySelector('.t-talk-in input')})")
        check('talk', talk['lines'] >= 2 and 'Logbuch' in talk['text'], talk['text'].replace('\n', ' ')[-60:])

        menu = profile['menu']
        if menu:
            page.keyboard.press('Control+k'); page.wait_for_timeout(400)
            page.fill(menu['input'], 'werkstatt'); page.wait_for_timeout(400)
            rows = page.evaluate(menu['rows'])
            page.keyboard.press('Escape'); page.wait_for_timeout(300)
            closed = page.evaluate(menu['closed'])
            check('palette', rows and 'Werkstatt' in rows[0] and closed, (rows[0] if rows else 'keine Zeile') + ('' if closed else '; Esc schließt nicht'))
        elif profile.get('search_field'):          # ein Suchfeld statt der Palette: ein Ort tippen, Enter, der Ort ist offen
            page.fill(profile['search_field'], 'werkstatt'); page.press(profile['search_field'], 'Enter'); page.wait_for_timeout(800)
            title = page.evaluate("()=>(document.querySelector('.fr-title') || {}).textContent || ''")
            check('palette', 'Werkstatt' in title, 'Suchfeld: „werkstatt“ öffnet ' + (title or 'nichts'))
        elif profile.get('no_search'):
            check('palette', None, 'nicht geprüft – ' + profile['no_search'])
        else:
            check('palette', None, 'nicht geprüft – kein Profil')

        if opens and profile['count']:
            page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'meter', id:'meter', title:'Guppy-Meter'})")
            page.wait_for_timeout(600)
            tabs_before = page.evaluate(profile['count'])
            page.reload(); wait_until_started(page); page.wait_for_timeout(1500)
            tabs_after = page.evaluate(profile['count'])
            check('layout', tabs_after >= tabs_before and tabs_after > 1,
                  f"{tabs_before} {profile['count_word']} vorher, {tabs_after} nach dem Neuladen")
        else:
            check('layout', None, 'nicht geprüft – was ein Neuladen überstehen muss, weiß nur der Autor der Shell')

        base, _, token = url.partition('#')
        retro = page.goto(base + 'retro#' + token)      # with the token, or Build 6's desktop runs into 403s of its own
        page.wait_for_timeout(1200)
        has_desktop = page.evaluate("()=>!!document.getElementById('desktop')")
        check('retro', retro.status == 200 and has_desktop, f'HTTP {retro.status}' + ('' if has_desktop else ', kein Desktop'))

        if shots: page.screenshot(path=str(Path(shots) / '99_retro.png'))
        check('console', not console and not errors, '; '.join(console + errors)[:300])

        # last, because it provokes the 403s on purpose: no tool reaches a route its manifest does not list (§6)
        page.goto(url); wait_until_started(page); page.wait_for_timeout(1000)
        probe = page.evaluate("""async (tools)=>{
          const out = {};
          for(const t of tools){
            const mod = window.sedraBoot.ctx.tools.mod(t);
            const ctx = window.sedraBoot.ctx.makeContext(window.sedraBoot.ctx.tools.manifest(t), null, {open(){}, notify(){}, decide(){}});
            try{ await ctx.api('/api/switches'); out[t] = 'erlaubt'; }catch(e){ out[t] = e.message.slice(0, 40); }
          }
          return out;
        }""", wanted or [t for t in manifest['tools'] if t in OBJECTS])
        leaky = [t for t, answer in probe.items() if answer == 'erlaubt']
        check('allowlist', not leaky, ', '.join(leaky) or f'{len(probe)} Werkzeuge bekommen 403 auf eine fremde Route')
        if generic:
            check('profil', None, 'kein Profil im Prüfwerkzeug – geprüft wurde nur, was die Vertragsmarken hergeben (data-tool, data-verbs, data-slot)')
        b.close()
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--url', help='a running UIX (the URL printed by uix_start, with #token); default: start one on a temporary project')
    ap.add_argument('--tool', help='check only this tool (the rest of the checks still run)')
    ap.add_argument('--shell', default='cockpit', help='which shell to check (set in the test project); a shell without a profile gets the generic checks')
    ap.add_argument('--vorgabe', help='a shell.vorgabe.yaml: the shell is created from it in the test project (id from the file) and checked')
    ap.add_argument('--shots', help='folder for screenshots of every step')
    ap.add_argument('--browser', default='auto', choices=['auto', 'chromium', 'msedge', 'chrome'])
    ap.add_argument('--headed', action='store_true', help='show the browser window')
    ap.add_argument('--json', action='store_true', help='print the report as JSON as well')
    ap.add_argument('--fixture', choices=['orchestra', 'orchestra-aus', 'orchestra-fehler'],
                    help='Shell D (Spec 4): das Agenten-Team aus benchmarks/uix_fixture_orchestra.py ins Prüfprojekt legen')
    args = ap.parse_args(argv)
    try:
        import playwright  # noqa: F401
    except ImportError:
        print('playwright is not installed: pip install playwright && python -m playwright install chromium'); return 2
    if args.shots: Path(args.shots).mkdir(parents=True, exist_ok=True)
    stop = None
    url = args.url
    prepare = None
    if args.vorgabe:
        import yaml
        v = yaml.safe_load(Path(args.vorgabe).read_text(encoding='utf-8'))
        args.shell = v['id']
        prepare = lambda hub: hub.module_scaffold({'kind': 'shell', 'id': v['id'], 'name': v.get('name'), 'vorgabe': v})
    if args.fixture:
        import uix_fixture_orchestra
        first = prepare
        prepare = lambda hub: (first(hub) if first else None, uix_fixture_orchestra.install(hub, args.fixture))
    if not url:
        url, stop = start_server(print, shell=args.shell, prepare=prepare)
        print('uix', url.split('#')[0], '· Shell', args.shell)
    try:
        results = run_checks(url, shots=args.shots, browser=args.browser, headed=args.headed, only=args.tool, shell=args.shell,
                             fixture=args.fixture)
    finally:
        if stop: stop()
    bad = [r for r in results if r[1] is False]
    skipped = [r for r in results if r[1] is None]
    counted = [r for r in results if r[1] is not None]
    if args.json:
        print(json.dumps([{'check': n, 'ok': ok, 'detail': d} for n, ok, d in results], ensure_ascii=False))
    print(f'result {"ok" if not bad else "FAIL"}  {len(counted) - len(bad)} of {len(counted)} checks ok'
          + (f', {len(skipped)} nicht geprüft' if skipped else ''))
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())
