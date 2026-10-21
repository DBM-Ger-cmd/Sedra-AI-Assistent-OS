"""The UI contract itself (SHELL_WERKZEUG_VERTRAG_v1 §2, §4, §5, §8): the rules that make a module exchangeable.

Two kinds of check here: the files (size, no cross-imports, no inline code, every tool has a README) and the pure JavaScript of the
contract and the shell, judged with node in a bare context – no browser, no DOM. The browser side is `uix_check.py` (§8)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
NODE = shutil.which('node')
MAX_LINES = 400


def tool_files(pattern='*.js'):
    """Die Dateien der geladenen Werkzeuge. `_template` ist eine Vorlage und kein Werkzeug: sie erklärt die Regeln im Kommentar
    („kein eigenes fetch, kein localStorage“) und würde an einer Textsuche scheitern. Geprüft wird sie in test_desk_install,
    dort mit dem Scanner, der Kommentare auslässt."""
    return sorted(p for p in (UIX / 'tools').rglob(pattern) if not p.parent.name.startswith('_'))


def run_js(files, probe):
    """The named files in one bare context, then `probe` – which prints JSON."""
    import os, tempfile
    js = '\n'.join(f.read_text(encoding='utf-8') for f in files)
    # The source goes through a file, not the command line: Windows refuses a command line of this length (WinError 206).
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as fh:
        fh.write(js)
    try:
        head = ("const vm=require('vm');const fs=require('fs');const box={};box.globalThis=box;vm.createContext(box);"
                "vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),box);")
        run = subprocess.run([NODE, '-e', head + probe, fh.name], capture_output=True, text=True, encoding='utf-8', timeout=60)
    finally:
        os.unlink(fh.name)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


def real_manifests():
    """Die Manifeste der Werkzeuge im Paket, so wie der Lader sie bekommt (id, kind, handles, slot, order)."""
    import yaml
    out = []
    for f in sorted((UIX / 'tools').glob('*/tool.yaml')):
        if f.parent.name.startswith('_'):
            continue
        t = yaml.safe_load(f.read_text(encoding='utf-8'))['tool']
        out.append({k: t.get(k) for k in ('id', 'kind', 'handles', 'slot', 'order', 'api', 'events')})
    return out


class Files(unittest.TestCase):
    def test_no_file_of_the_contract_a_shell_or_a_tool_is_longer_than_400_lines(self):
        too_long = []
        for f in sorted(UIX.rglob('*.js')):
            lines = len(f.read_text(encoding='utf-8').splitlines())
            if lines > MAX_LINES:
                too_long.append(f'{f.relative_to(UIX)}: {lines}')
        self.assertEqual(too_long, [], 'split the file, the contract allows 400 lines')

    def test_every_script_parses(self):
        if not NODE:
            self.skipTest('node is not installed')
        for f in sorted(UIX.rglob('*.js')):
            with self.subTest(str(f.relative_to(UIX))):
                run = subprocess.run([NODE, '--check', str(f)], capture_output=True, text=True, encoding='utf-8', timeout=60)
                self.assertEqual(run.returncode, 0, run.stderr)

    def test_a_tool_imports_nothing_of_another_tool_or_of_the_shell(self):
        """Die verbotenen Namen werden nicht aufgezählt, sondern gesucht: jedes `root.sedraX` einer Shell ist für ein Werkzeug tabu.

        Eine Liste von Hand war zu schwach – `sedraPalette` stand nicht darin, und das Gespräch griff genau danach. In jeder
        anderen Shell verstummte damit die Navigation (gefunden beim Bau von Shell E, 14.10.2026)."""
        shell_globals = set()
        for f in sorted((UIX / 'shells').rglob('*.js')):
            shell_globals.update(re.findall(r'root\.(sedra[A-Za-z]+)\s*=', f.read_text(encoding='utf-8')))
        self.assertIn('sedraPalette', shell_globals, 'die Suche findet die Namen der Shells')
        bad = []
        for f in tool_files():
            text = f.read_text(encoding='utf-8')
            for name in sorted(shell_globals) + ["document.getElementById('sedra-root')"]:
                if name in text:
                    bad.append(f'{f.relative_to(UIX)} greift auf {name} zu')
            for other in (UIX / 'tools').iterdir():
                if other.is_dir() and other.name != f.parent.name and f'tools/{other.name}' in text:
                    bad.append(f'{f.relative_to(UIX)} kennt das Werkzeug {other.name}')
        self.assertEqual(bad, [], 'tools talk through ui/ and the bus only')

    def test_a_tool_never_calls_fetch_or_localstorage_itself(self):
        """ctx.api() is the one way out (§4); storage belongs to the shell, which owns the layout."""
        bad = []
        for f in tool_files():
            text = f.read_text(encoding='utf-8')
            for forbidden in ('fetch(', 'localStorage', 'XMLHttpRequest', 'EventSource'):
                if forbidden in text:
                    bad.append(f'{f.relative_to(UIX)}: {forbidden}')
        self.assertEqual(bad, [])

    def test_every_api_route_a_module_names_exists_in_the_server(self):
        """Das Schutz-Werkzeug der Lieferung rief `/api/guard/group` und `/api/guard/demo` – Routen, die der Server bewusst nicht
        hat (Build 16: die Schärfe kommt aus dem Modus). Ein Knopf, der ins Leere läuft, fällt sonst erst dem Captain auf. Statisch:
        jede `/api/…`-Zeichenkette in Shell und Werkzeug muss im Server als Route stehen."""
        server = (UIX.parent / 'uix_server.py').read_text(encoding='utf-8')
        routes = set(re.findall(r"'(/api/[A-Za-z0-9_/.-]+)'\s*:", server)) | set(re.findall(r"path\s*==\s*'(/api/[A-Za-z0-9_/.-]+)'", server))
        self.assertIn('/api/guard/status', routes, 'die Routen des Servers werden gelesen')
        bad = []
        for f in sorted(p for p in UIX.rglob('*.js') if not p.parent.name.startswith('_')):
            for route in sorted(set(re.findall(r"'(/api/[A-Za-z0-9_/.-]+)'", f.read_text(encoding='utf-8')))):
                if route not in routes:
                    bad.append(f'{f.relative_to(UIX)}: {route}')
        self.assertEqual(bad, [], 'eine Route, die der Server nicht kennt, ist ein toter Knopf')

    def test_every_route_a_tool_calls_stands_in_its_own_manifest(self):
        """Der Server lässt ein Werkzeug nur auf die Routen seines Manifests (§6, X-SEDRA-Tool). Das Gespräch rief für „lade …“
        `/api/models` und `/api/model/load`, die nicht im Manifest standen – der Befehl endete in einem 403 (Verbindungsprüfung 19.10.2026).
        Statisch: jede `/api/…`-Zeichenkette im JS eines Werkzeugs steht in seiner api-Liste. Die Rahmen-Probe ruft absichtlich eine fremde
        Route (sie prüft genau dieses Nein) und bleibt außen vor."""
        import yaml
        bad = []
        for man in sorted(p for p in (UIX / 'tools').glob('*/tool.yaml') if not p.parent.name.startswith('_') and p.parent.name != 'rahmen-probe'):
            tool = yaml.safe_load(man.read_text(encoding='utf-8'))['tool']
            allowed = {r.split()[1] for r in tool.get('api') or []}
            for js in sorted(man.parent.glob('*.js')):
                for route in sorted(set(re.findall(r"'(/api/[A-Za-z0-9_/.-]+)", js.read_text(encoding='utf-8')))):
                    if route not in allowed:
                        bad.append(f'{tool["id"]}: {route}')
        self.assertEqual(bad, [], 'eine Route außerhalb des Manifests ist ein Knopf, der 403 bekommt')

    def test_the_page_carries_no_inline_code_and_loads_only_the_contract(self):
        html = (UIX / 'desk.html').read_text(encoding='utf-8')
        self.assertNotIn('onclick=', html)
        self.assertEqual(re.findall(r'<script(?![^>]*\bsrc=)', html), [], 'no inline script (CSP self, Regel: Top-Level-Code nur in start.js)')
        for src in re.findall(r'<script src="([^"]+)"', html):
            self.assertTrue(src.startswith('/uix/ui/'), f'the page may only load the contract, not {src}')
        self.assertIn('/retro', (UIX.parent / 'uix_server.py').read_text(encoding='utf-8'), 'the old desktop stays reachable')

    def test_a_tool_styles_only_its_own_container(self):
        bad = []
        for css in tool_files('*.css'):
            text = re.sub(r'/\*.*?\*/', '', css.read_text(encoding='utf-8'), flags=re.S)
            # Jede Regel endet an ihrer schließenden Klammer; davor steht der Selektor. (Ein Muster über `^…{` verschluckte
            # bei mehrzeiligen Regeln die Klammer der vorigen und meldete gültiges CSS als Fehler – 15.10.2026.)
            for block in text.split('}'):
                selector = block.split('{')[0].strip()
                if not selector or selector.startswith('@'):
                    continue
                first = selector.split()[0].split(':')[0].split(',')[0]
                if not first.startswith('.t-'):
                    bad.append(f'{css.relative_to(UIX)}: {selector[:40]}')
        self.assertEqual(bad, [], 'a tool styles .t-<id> and nothing else')

    def test_colours_are_tokens_everywhere_but_in_the_token_file(self):
        bad = []
        # the shell of Build 6 (uix/css/desktop.css) keeps its own :root block; the contract starts at ui/, shells/ and tools/
        for css in sorted(list((UIX / 'ui').rglob('*.css')) + list((UIX / 'shells').rglob('*.css')) + list((UIX / 'tools').rglob('*.css'))):
            if css.name == 'tokens.css':
                continue
            for value in re.findall(r':\s*(#[0-9a-fA-F]{3,8})', css.read_text(encoding='utf-8')):
                bad.append(f'{css.relative_to(UIX)}: {value}')
        self.assertEqual(bad, [], 'a colour needs a token in ui/tokens.css (UIX_STYLE_MANIFEST)')

    def test_the_evidence_tools_say_so_in_their_manifest(self):
        import yaml
        slots = {}
        for manifest in sorted((UIX / 'tools').glob('*/tool.yaml')):
            tool = yaml.safe_load(manifest.read_text(encoding='utf-8'))['tool']
            slots[tool['id']] = tool.get('slot', 'inhalt')
        for tid in ('live', 'costs', 'tests'):
            self.assertEqual(slots.get(tid), 'nachweis', tid)
        for tid in ('task', 'candidate', 'decisions', 'workshop'):
            self.assertEqual(slots.get(tid), 'inhalt', tid)

    def test_every_module_has_a_readme(self):
        missing = [str(p.relative_to(UIX)) for p in sorted(list((UIX / 'tools').iterdir()) + list((UIX / 'shells').iterdir()))
                   if p.is_dir() and not (p / 'README.md').is_file()]      # auch die Vorlagen haben eine
        self.assertEqual(missing, [], 'every module says in a README what it is for (§8)')


class Contract(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_the_bus_refuses_an_unknown_event_a_deep_payload_and_a_tool_that_oversteps(self):
        out = run_js([UIX / 'ui' / 'bus.js'], """
          const b = box.sedraBus;
          console.log(JSON.stringify({
            ok: b.checkEvent('object.open', {type:'task', id:'1', title:'x'}, ['object.open']),
            unknown: b.checkEvent('object.explode', {}, null),
            missing: b.checkEvent('object.open', {type:'task'}, null),
            fn: b.checkEvent('task.changed', {id:'1', run:()=>1}, null),
            deep: b.checkEvent('task.changed', {id:'1', a:{b:{c:1}}}, null),
            notAllowed: b.checkEvent('decision.answered', {id:'1'}, ['object.open'])
          }));
        """)
        self.assertEqual(out['ok'], '')
        for key in ('unknown', 'missing', 'fn', 'deep', 'notAllowed'):
            self.assertNotEqual(out[key], '', key)

    def test_the_bus_delivers_to_listeners_and_a_broken_listener_does_not_stop_the_others(self):
        out = run_js([UIX / 'ui' / 'bus.js'], """
          const refused = [];
          const bus = box.sedraBus.makeBus((n, why)=>refused.push(n + ': ' + why));
          const seen = [];
          bus.on('task.changed', ()=>{ throw new Error('kaputt'); });
          bus.on('task.changed', e=>seen.push(e.id));
          const tool = bus.forModule(['object.open']);
          bus.emit('task.changed', {id:'M-1'});
          const blocked = tool.emit('task.changed', {id:'M-2'});
          const allowed = tool.emit('object.open', {type:'task', id:'M-3', title:'x'});
          console.log(JSON.stringify({seen, blocked, allowed, refused}));
        """)
        self.assertEqual(out['seen'], ['M-1'])
        self.assertFalse(out['blocked'])
        self.assertTrue(out['allowed'])
        self.assertEqual(len(out['refused']), 2, 'the broken listener and the overstepping tool are both reported')

    def test_the_lifecycle_demands_mount_and_unmount(self):
        out = run_js([UIX / 'ui' / 'lifecycle.js'], """
          const l = box.sedraLifecycle;
          console.log(JSON.stringify({
            ok: l.checkModule({id:'probe', mount(){}, unmount(){}}, 'tool'),
            noMount: l.checkModule({id:'probe', unmount(){}}, 'tool'),
            noUnmount: l.checkModule({id:'probe', mount(){}}, 'tool'),
            badId: l.checkModule({id:'Probe!', mount(){}, unmount(){}}, 'tool'),
            shellOk: l.checkModule({id:'cockpit', start(){}}, 'shell'),
            shellNoStart: l.checkModule({id:'cockpit'}, 'shell')
          }));
        """)
        self.assertEqual(out['ok'], '')
        self.assertEqual(out['shellOk'], '')
        for key in ('noMount', 'noUnmount', 'badId', 'shellNoStart'):
            self.assertNotEqual(out[key], '', key)

    def test_unmounting_runs_the_tools_unmount_and_drops_its_listeners(self):
        out = run_js([UIX / 'ui' / 'lifecycle.js'], """
          const l = box.sedraLifecycle;
          const log = [];
          const el = {replaceChildren(){ log.push('cleared'); }};
          const ctx = {_offs: [()=>log.push('off')]};
          const mod = {id:'probe', mount(){ log.push('mounted'); }, unmount(){ log.push('unmounted'); },
                       actions(){ return [{label:'Erneut testen', run(){}}, {label:'kaputt'}]; }};
          const state = l.mountTool(mod, el, ctx, ()=>log.push('problem'));
          const actions = l.actionsOf(state).map(a=>a.label);
          l.unmountTool(state, ()=>log.push('problem'));
          l.unmountTool(state, ()=>log.push('problem'));
          console.log(JSON.stringify({log, actions}));
        """)
        self.assertEqual(out['log'], ['mounted', 'unmounted', 'cleared', 'off'])
        self.assertEqual(out['actions'], ['Erneut testen'], 'an action without run() is not offered')

    def test_a_tool_that_throws_in_mount_is_reported_not_swallowed(self):
        out = run_js([UIX / 'ui' / 'lifecycle.js'], """
          const l = box.sedraLifecycle;
          const problems = [];
          const state = l.mountTool({id:'probe', mount(){ throw new Error('kaputt'); }, unmount(){}}, {replaceChildren(){}}, {}, (id, err)=>problems.push(id + ': ' + err.message));
          console.log(JSON.stringify({problems, mounted: state.mounted}));
        """)
        self.assertEqual(out['problems'], ['probe: kaputt'])
        self.assertFalse(out['mounted'])

    def test_the_small_helpers_format_as_the_captain_reads(self):
        out = run_js([UIX / 'ui' / 'dom.js'], """
          const d = box.sedraDom;
          console.log(JSON.stringify({n: d.fmtNumber(4120), none: d.fmtNumber(null), b: d.fmtBytes(2048),
                                      dur: [d.fmtDuration(9.8), d.fmtDuration(100), d.fmtDuration(3700)],
                                      ago: [d.fmtAgo(new Date(1000000).toISOString(), 1000000 + 30000), d.fmtAgo(new Date(1000000).toISOString(), 1000000 + 7200000)]}));
        """)
        self.assertEqual(out['n'], '4.120')
        self.assertEqual(out['none'], '–')
        self.assertEqual(out['b'], '2.0 KB')
        self.assertEqual(out['dur'], ['10 s', '1 Min 40 s', '1 Std 1 Min'])
        self.assertEqual(out['ago'], ['gerade eben', 'vor 2 Std'])


    def test_the_diff_of_the_candidate_is_computed_without_a_library(self):
        """Der Kandidat rechnet seinen Diff selbst (diff2html lag nur als Vorschlag im Konzept); gerechnet wird mit dem, was da ist."""
        out = run_js([UIX / 'tools' / 'candidate' / 'tool.js'], """
          const c = box.sedraCandidatePure;
          const rows = c.diffLines('a\\nb\\nc\\n', 'a\\nB\\nc\\n');
          const neu = c.diffLines('', 'x\\ny\\n');
          const gleich = c.diffLines('a\\n', 'a\\n');
          const lang = Array.from({length: 40}, (_, i)=>'z' + i).join('\\n');
          const collapsed = c.collapse(c.diffLines(lang, lang.replace('z20', 'ZZ')));
          console.log(JSON.stringify({
            rows: rows.map(r=>r.kind), counts: c.counts(rows),
            neu: neu.filter(r=>r.kind === 'rein').length, gleich: gleich.every(r=>r.kind === 'gleich'),
            collapsed: collapsed.filter(r=>r.kind === 'luecke').length, sichtbar: collapsed.length
          }));
        """)
        self.assertEqual(out['rows'][:4], ['gleich', 'raus', 'rein', 'gleich'])
        self.assertEqual(out['counts'], {'rein': 1, 'raus': 1})
        self.assertEqual(out['neu'], 2)
        self.assertTrue(out['gleich'])
        self.assertEqual(out['collapsed'], 2, 'lange gleiche Strecken werden gefaltet')
        self.assertLess(out['sichtbar'], 20, 'aus 40 Zeilen bleibt ein lesbarer Ausschnitt')

    def test_the_tests_tool_never_calls_an_untested_candidate_green(self):
        out = run_js([UIX / 'tools' / 'tests' / 'tool.js'], """
          const v = box.sedraTestsPure.verdict;
          console.log(JSON.stringify({
            keiner: v(null),
            ungetestet: v({exists: true, tests_executed: false, ready_for_merge: false}),
            bereit: v({exists: true, tests_executed: true, ready_for_merge: true}),
            host: v({exists: true, tests_executed: true, host_code_executed: true})
          }));
        """)
        self.assertEqual(out['ungetestet']['tone'], 'warn')
        self.assertIn('kein grünes Licht', out['ungetestet']['text'])
        self.assertEqual(out['bereit']['tone'], 'ok')
        self.assertEqual(out['host']['tone'], 'warn', 'auf dem Rechner getestet ist nicht dasselbe wie isoliert getestet')

    def test_the_coins_of_the_costs_tool_match_the_meter(self):
        out = run_js([UIX / 'tools' / 'costs' / 'tool.js'], """
          const c = box.sedraCostsPure;
          console.log(JSON.stringify({klein: c.coins(4120), gross: c.coins(120000000),
                                      gemeldet: c.sourceText(['provider']), geschaetzt: c.sourceText(['estimate']),
                                      gemischt: c.sourceText(['provider', 'estimate']), leer: c.sourceText([])}));
        """)
        self.assertEqual(out['klein'], {'gold': 0, 'silver': 0, 'copper': 4})
        self.assertEqual(out['gross']['gold'], 12)
        self.assertIn('exakt', out['gemeldet'])
        self.assertIn('Geschätzt', out['geschaetzt'])
        self.assertIn('Untergrenze', out['gemischt'])


class CockpitPure(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')
        self.cockpit = UIX / 'shells' / 'cockpit'

    def test_the_loader_refuses_a_shell_api_that_is_not_one(self):
        """Das Cockpit gab zwei Builds lang seine api-Funktion als „Shell“ weiter; `ctx.shell.open()` war in jedem Reiter tot.
        Kein Test sah es, weil nur das Gespräch (richtig gemountet) navigierte. Jetzt prüft der Loader, was eine Shell hergibt."""
        out = run_js([UIX / 'ui' / 'loader.js'], """
          const l = box.sedraLoader;
          const said = [];
          const say = (where, err)=>said.push(err.message);
          console.log(JSON.stringify({
            fn: l.checkShellApi(function(){}, {id: 'x'}, say), empty: l.checkShellApi({}, {id: 'y'}, say),
            half: l.checkShellApi({open(){}}, {id: 'z'}, say), full: l.checkShellApi({open(){}, notify(){}, decide(){}}, {id: 'ok'}, say),
            said
          }));
        """)
        self.assertFalse(out['fn']); self.assertFalse(out['empty']); self.assertFalse(out['half']); self.assertTrue(out['full'])
        self.assertEqual(len(out['said']), 3)
        self.assertIn('notify, decide fehlt', out['said'][2])

    def test_the_router_sends_a_place_to_the_dock_and_everything_else_to_guppi(self):
        out = run_js([UIX / 'ui' / 'places.js'], """
          const p = box.sedraPlaces;
          const r = t=>{ const x = p.routeText(t); return x ? (x.kind === 'place' ? 'place:' + x.id : 'talk' + (x.order ? ':order' : '')) : 'nichts'; };
          console.log(JSON.stringify({
            modelle: r('Modelle'), entscheidungen: r('entscheidungen'), logbuch: r('logbuch'),
            frage: r('Was macht die Werkstatt?'), auftrag: r('Baue einen CSV-Parser'), slash: r('/status'),
            leer: r('   '), satz: r('zeig mir die Modelle von gestern')
          }));
        """)
        self.assertEqual(out['modelle'], 'place:models')
        self.assertEqual(out['entscheidungen'], 'place:decisions')
        self.assertEqual(out['logbuch'], 'place:logbook')
        self.assertEqual(out['frage'], 'talk')
        self.assertEqual(out['auftrag'], 'talk:order')
        self.assertEqual(out['slash'], 'talk')
        self.assertEqual(out['leer'], 'nichts')
        self.assertEqual(out['satz'], 'talk')

    def test_the_palette_offers_the_place_first_when_the_text_looks_like_navigation(self):
        out = run_js([UIX / 'ui' / 'places.js'], """
          const p = box.sedraPlaces;
          const first = t=>p.paletteRows(t).map(r=>r.id).slice(0, 2);
          console.log(JSON.stringify({halb: first('entscheid'), auftrag: first('Baue einen Parser'), leer: p.paletteRows('').length}));
        """)
        self.assertEqual(out['halb'][0], 'decisions')
        self.assertEqual(out['auftrag'][0], '__talk')
        self.assertGreaterEqual(out['leer'], 5)

    def test_every_place_of_the_palette_opens_an_object_a_tool_handles(self):
        """Spec 4 (G2-S4-21): ein Ort darf auf sein Werkzeug warten – dann zeigt die Shell den Leerzustand. Die Ausnahme verschwindet
        mit dem Werkzeug: steht es da, schlägt die zweite Prüfung an, bis die Zeile hier gestrichen ist."""
        waiting = {'routines': 'S4.6, Werkzeug routines'}
        out = run_js([UIX / 'ui' / 'loader.js', UIX / 'ui' / 'places.js'], """
          const reg = box.sedraLoader.makeRegistry(%s.map(m=>({manifest: m})));
          console.log(JSON.stringify(box.sedraPlaces.PLACES.map(p=>[p.id, reg.forObject(p.object).map(m=>m.id)])));
        """ % json.dumps(real_manifests()))
        for place, tools in out:
            if place in waiting:
                self.assertEqual(tools, [], f'{place} hat jetzt ein Werkzeug – Ausnahme streichen ({waiting[place]})')
            else:
                self.assertTrue(tools, f'the palette opens {place}, but no tool draws it')

    def test_the_dock_opens_closes_moves_and_never_opens_the_same_object_twice(self):
        out = run_js([self.cockpit / 'dock.js'], """
          const dk = box.sedraDock;
          let l = dk.newLayout();
          dk.addPane(l, {type:'task', id:'M-1', title:'Parser'});
          dk.addPane(l, {type:'model', id:'alle', title:'Werkstatt'});
          const again = dk.addPane(l, {type:'task', id:'M-1', title:'Parser'});
          const first = dk.firstGroup(l);
          l = dk.splitGroup(l, first.id, 'row', 'g2');
          const moved = dk.movePane(l, 'model:alle', 'g2');
          const keys = [];
          dk.eachGroup(l, g=>g.panes.forEach(p=>keys.push(g.id + '/' + p.key)));
          dk.removePane(l, 'task:M-1');
          l = dk.prune(l);
          const after = [];
          dk.eachGroup(l, g=>g.panes.forEach(p=>after.push(p.key)));
          console.log(JSON.stringify({created: again.created, split: l.kind, keys, moved, after}));
        """)
        self.assertFalse(out['created'], 'an object that is already open is only brought to the front')
        self.assertEqual(sorted(out['keys']), ['g1/task:M-1', 'g2/model:alle'])
        self.assertTrue(out['moved'])
        self.assertEqual(out['after'], ['model:alle'])
        self.assertEqual(out['split'], 'group', 'an empty group disappears again')

    def test_the_tree_shows_every_zone_and_marks_what_waits(self):
        out = run_js([self.cockpit / 'tree.js'], """
          const rows = box.sedraTree.treeModel({
            project: {name:'Export', path:'D:\\\\Projekte\\\\Export'},
            missions: [{mission_id:'M-1', intent:'CSV-Parser', status:'active', pending_gates:1, steps:['a','b'], steps_done:1, phase:'EXECUTE'},
                       {mission_id:'M-2', intent:'Doku', status:'active', pending_gates:0, steps:['a'], steps_done:0, phase:'PLAN'}],
            models: {recipes:[{id:'coder.local_primary', loaded:true}]},
            library: {own:[1,2], custom:[1]}, agents: {instances:[]}
          });
          console.log(JSON.stringify({heads: rows.filter(r=>r.kind==='head').map(r=>r.title),
                                      warn: rows.filter(r=>r.tone==='warn').map(r=>r.title),
                                      types: [...new Set(rows.filter(r=>r.object).map(r=>r.object.type))]}));
        """)
        for head in ('Vorhaben', 'Werkstatt', 'Besatzung', 'Bibliothek', 'System'):
            self.assertTrue(any(h.startswith(head) for h in out['heads']), head)
        self.assertEqual(out['warn'], ['CSV-Parser'])
        self.assertIn('task', out['types'])
        self.assertIn('logbook', out['types'])
        self.assertNotIn('routine', out['types'], 'Build 24 (B6-G-06): kein Eintrag ohne Werkzeug dahinter')
        self.assertIn('gateway', out['types'], 'das KI GateWay steht links im Baum mit seinen Ansichten (Captain-Entscheidung 19.10.2026)')

    def test_the_tree_opens_the_workshop_sections_it_promises(self):
        # Build 24 (B6-G-06): „Modell hinzufügen“ und „Teststrecke“ sind Objekte, die die Werkstatt als Abschnitt öffnet (sectionFor)
        out = run_js([self.cockpit / 'tree.js', UIX / 'tools' / 'workshop' / 'tool.js'], """
          const rows = box.sedraTree.treeModel({missions: [], models: {recipes: [{id: 'coder.x', loaded: true}]}, library: {}, agents: {}});
          const ids = rows.filter(r=>r.object && r.object.type === 'model').map(r=>[r.object.id, box.sedraWorkshopPure.sectionFor(r.object), r.note]);
          console.log(JSON.stringify(ids));
        """)
        self.assertEqual([x[:2] for x in out], [['alle', None], ['neu', 'neu'], ['teststrecke', 'teststrecke']])
        self.assertIn('coder.x', out[2][2])


class ShellDContract(unittest.TestCase):
    """Spec 4, S4.1: die Vertragsnachträge N1 bis N4 im Vertragscode (D4.4)."""
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_handles_match_reads_the_type_and_the_three_forms(self):
        cases = [
            ('agent', {'type': 'agent', 'id': 'alle'}, True), ('agent', {'type': 'agent', 'id': 'A-1'}, True),
            ('agent', {'type': 'issue', 'id': 'alle'}, False),
            ('agent:alle', {'type': 'agent', 'id': 'alle', 'collection': True}, True), ('agent:alle', {'type': 'agent', 'id': 'A-1'}, False),
            ('agent:*', {'type': 'agent', 'id': 'A-1'}, True), ('agent:*', {'type': 'agent', 'id': 'alle'}, False),
            ('agent:*', {'type': 'agent', 'id': 'rollen', 'collection': True}, False),
            ('agent:rollen', {'type': 'agent', 'id': 'rollen', 'collection': True}, True), ('agent:rollen', {'type': 'agent', 'id': 'alle'}, False),
            ('agent:*', {'type': 'agent', 'id': None}, True), ('issue:*', {'type': 'agent', 'id': 'A-1'}, False),
            ('agent', None, False), (None, {'type': 'agent', 'id': 'A-1'}, False),
        ]
        out = run_js([UIX / 'ui' / 'loader.js'], "console.log(JSON.stringify(%s.map(c=>box.sedraLoader.handlesMatch(c[0], c[1]))));" % json.dumps(cases))
        for (entry, obj, want), got in zip(cases, out):
            self.assertEqual(got, want, f'{entry} gegen {obj}')

    def test_every_manifest_of_the_package_keeps_its_meaning(self):
        """N1: ohne Zusatz zeichnet ein Werkzeug jedes Objekt seines Typs – forObject liefert dasselbe wie das alte for(type)."""
        manifests = real_manifests()
        objects = [{'type': t, 'id': i, 'collection': i in ('alle', 'rollen')} for t in sorted({h for m in manifests for h in (m['handles'] or [])})
                   for i in ('alle', 'X-1', 'rollen')]
        out = run_js([UIX / 'ui' / 'loader.js'], """
          const reg = box.sedraLoader.makeRegistry(%s.map(m=>({manifest: m})));
          console.log(JSON.stringify(%s.map(o=>[reg.forObject(o).map(m=>m.id), reg.for(o.type).map(m=>m.id)])));
        """ % (json.dumps(manifests), json.dumps(objects)))
        for obj, (by_object, by_type) in zip(objects, out):
            old = [m['id'] for m in manifests if m['kind'] == 'object' and obj['type'] in (m['handles'] or [])]
            self.assertEqual(by_object, old, obj)
            self.assertEqual(by_type, old, obj)

    def test_the_registry_gives_each_object_its_one_tool(self):
        """Falle 1 aus G1: Organigramm, Rollenliste und Fenster handeln denselben Typ, zeichnen aber je ein anderes Objekt."""
        out = run_js([UIX / 'ui' / 'loader.js'], """
          const m = (id, handles)=>({manifest: {id, kind: 'object', handles}});
          const reg = box.sedraLoader.makeRegistry([m('org', ['agent:alle']), m('crew', ['agent:rollen']), m('fenster', ['agent:*']), m('alt', ['task'])]);
          const ids = o=>reg.forObject(o).map(x=>x.id);
          console.log(JSON.stringify({alle: ids({type:'agent', id:'alle', collection:true}), rollen: ids({type:'agent', id:'rollen', collection:true}),
                                      eins: ids({type:'agent', id:'A-7'}), typ: reg.for('agent').map(x=>x.id), task: ids({type:'task', id:'M-1'})}));
        """)
        self.assertEqual(out['alle'], ['org'])
        self.assertEqual(out['rollen'], ['crew'])
        self.assertEqual(out['eins'], ['fenster'])
        self.assertEqual(out['typ'], ['org', 'crew', 'fenster'], 'for(type) ohne Objekt nennt jede Form')
        self.assertEqual(out['task'], ['alt'])

    def test_the_schema_allows_the_three_forms_and_every_manifest_fits(self):
        schema = json.loads((UIX / 'ui' / 'schema' / 'tool.schema.json').read_text(encoding='utf-8'))
        pattern = schema['properties']['tool']['properties']['handles']['items']['pattern']
        for ok in ('agent', 'agent:alle', 'agent:*', 'agent:rollen', 'gauge-x'):
            self.assertRegex(ok, pattern)
        for bad in ('Agent', 'agent:', 'agent:*x', 'a:b:c', 'a', 'agent:Alle'):
            self.assertNotRegex(bad, pattern)
        for m in real_manifests():
            for h in m['handles'] or []:
                self.assertRegex(h, pattern, m['id'])

    def test_the_bus_knows_the_four_team_events_and_every_manifest_names_known_ones(self):
        out = run_js([UIX / 'ui' / 'bus.js'], """
          const c = box.sedraBus.checkEvent;
          console.log(JSON.stringify({names: Object.keys(box.sedraBus.EVENTS),
            agent: c('agent.changed', {id: 'A-1'}, null), agentNoId: c('agent.changed', {}, null), issue: c('issue.changed', {id: 'I-1'}, null),
            budget: c('budget.warning', {agent_id: 'A-1', prozent: 80, stufe: 'warnung'}, null), budgetNoAgent: c('budget.warning', {prozent: 80}, null),
            slot: c('slot.changed', {}, null), pending: c('decision.pending', {id: 'D-1', agent_id: 'A-1'}, null),
            pendingOld: c('decision.pending', {id: 'D-1'}, null), toolSends: c('agent.changed', {id: 'A-1'}, ['object.open'])}));
        """)
        for key in ('agent', 'issue', 'budget', 'slot', 'pending', 'pendingOld'):
            self.assertEqual(out[key], '', key)
        for key in ('agentNoId', 'budgetNoAgent', 'toolSends'):
            self.assertNotEqual(out[key], '', key)
        for m in real_manifests():
            for name in ((m['events'] or {}).get('emits') or []) + ((m['events'] or {}).get('listens') or []):
                self.assertIn(name, out['names'], f'{m["id"]} nennt ein Ereignis, das der Bus nicht kennt')

    def test_unmount_and_actions_get_the_container_so_one_tool_runs_twice(self):
        """N2: ein Werkzeug mit einer Instanz je Container (Map nach el) – zwei Fenster, jedes baut sein eigenes ab."""
        out = run_js([UIX / 'ui' / 'lifecycle.js'], """
          const l = box.sedraLifecycle;
          const inst = new Map(), log = [];
          const mod = {id: 'fenster', mount(el, ctx){ inst.set(el, ctx.object.id); },
                       unmount(el){ log.push('ab ' + inst.get(el)); inst.delete(el); },
                       actions(el){ return [{label: 'An ' + inst.get(el), run(){}}]; }};
          const el = ()=>({replaceChildren(){}});
          const a = l.mountTool(mod, el(), {object: {id: 'A-1'}, _offs: []}), b = l.mountTool(mod, el(), {object: {id: 'A-2'}, _offs: []});
          const labels = [l.actionsOf(a)[0].label, l.actionsOf(b)[0].label];
          l.unmountTool(b);
          const old = {id: 'alt', mount(){}, unmount(){ log.push('alt ohne Argument'); }};
          l.unmountTool(l.mountTool(old, el(), {_offs: []}));
          console.log(JSON.stringify({labels, log, left: [...inst.values()]}));
        """)
        self.assertEqual(out['labels'], ['An A-1', 'An A-2'])
        self.assertEqual(out['log'], ['ab A-2', 'alt ohne Argument'])
        self.assertEqual(out['left'], ['A-1'])


class ToolsPure(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_a_task_is_told_as_a_sentence(self):
        out = run_js([UIX / 'tools' / 'task' / 'tool.js'], """
          const t = box.sedraTaskPure;
          console.log(JSON.stringify({
            waiting: t.taskSentence({intent:'CSV-Parser', phase:'EXECUTE', pending_gates:1, steps:['a','b'], steps_done:1}),
            running: t.taskSentence({intent:'CSV-Parser', phase:'EXECUTE', steps:['a','b','c'], steps_done:2}),
            done: t.taskSentence({intent:'CSV-Parser', phase:'COMPLETE'}),
            failed: t.taskSentence({intent:'CSV-Parser', phase:'FAILED'}),
            gone: t.taskSentence(null),
            progress: t.progress({steps:['a','b','c','d'], steps_done:1})
          }));
        """)
        self.assertEqual(out['waiting'], 'CSV-Parser – wartet auf deine Freigabe.')
        self.assertEqual(out['running'], 'CSV-Parser – läuft, Schritt 3 von 3.')
        self.assertEqual(out['done'], 'CSV-Parser – fertig.')
        self.assertIn('Logbuch', out['failed'])
        self.assertEqual(out['progress'], {'steps': 4, 'done': 1, 'percent': 25})

    def test_the_gespraech_understands_a_short_yes_and_nothing_more(self):
        out = run_js([UIX / 'tools' / 'talk' / 'tool.js'], """
          const y = box.sedraTalkPure.yesNo;
          console.log(JSON.stringify({ja: y('einmal ja'), ja2: y('Ja.'), nein: y('nein'), ablehnen: y('ablehnen'),
                                      satz: y('ja, aber bitte vorher die Tests laufen lassen'), leer: y('')}));
        """)
        self.assertEqual(out['ja'], 'einmal')
        self.assertEqual(out['ja2'], 'einmal')
        self.assertEqual(out['nein'], 'ablehnen')
        self.assertEqual(out['ablehnen'], 'ablehnen')
        self.assertEqual(out['satz'], '', 'a sentence is for the model, not a blanket approval')

    def test_the_meter_turns_tokens_into_coins(self):
        out = run_js([UIX / 'tools' / 'meter' / 'tool.js'], """
          const m = box.sedraMeterPure;
          console.log(JSON.stringify({klein: m.coins(4120), gross: m.coins(120000000), line: m.coinLine(41000)}));
        """)
        self.assertEqual(out['klein'], {'gold': 0, 'silver': 0, 'copper': 4})
        self.assertEqual(out['gross']['gold'], 12)
        self.assertEqual(out['line'], 'Kupfer 41 · Silber 0 · Gold 0')

    def test_the_logbook_says_the_events_in_words(self):
        out = run_js([UIX / 'tools' / 'logbook' / 'tool.js'], """
          const w = box.sedraLogbookPure.words;
          console.log(JSON.stringify({gate: w('GATE_APPROVED'), denied: w('UIX_TOOL_DENIED'), unknown: w('SOMETHING_NEW')}));
        """)
        self.assertEqual(out['gate'], 'freigegeben')
        self.assertEqual(out['denied'], 'Werkzeug abgewiesen')
        self.assertEqual(out['unknown'], 'something new')

    def test_the_crew_reads_the_roles_out_of_the_recipes(self):
        out = run_js([UIX / 'tools' / 'crew' / 'tool.js'], """
          const r = box.sedraCrewPure.rolesFromRecipes([{id:'coder.local_primary', roles:['coder','reviewer'], loaded:true, enabled:true},
                                                        {id:'verifier.local_kev', roles:['verifier'], loaded:false, enabled:false}]);
          console.log(JSON.stringify(r.map(x=>x.role + ':' + x.recipes.length)));
        """)
        self.assertEqual(out, ['Coder:1', 'Reviewer:1', 'Verifier:1'])

    def test_the_files_tool_sorts_folders_first(self):
        out = run_js([UIX / 'tools' / 'files' / 'tool.js'], """
          const s = box.sedraFilesPure.sortEntries([{name:'b.py', kind:'file'}, {name:'src', kind:'dir'}, {name:'a.py', kind:'file'}]);
          console.log(JSON.stringify(s.map(e=>e.name)));
        """)
        self.assertEqual(out, ['src', 'a.py', 'b.py'])


if __name__ == '__main__':
    unittest.main()


class WorkshopAndFilesPure(unittest.TestCase):
    """Build 24 (Ticket B6-G-06): die reinen Teile der Werkstatt (Neues Modell, Teststrecke) und des Projekt-Werkzeugs."""
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_the_workshop_opens_the_section_the_tree_promises(self):
        out = run_js([UIX / 'tools' / 'workshop' / 'tool.js'], """
          const w = box.sedraWorkshopPure;
          console.log(JSON.stringify({
            neu: w.sectionFor({type:'model', id:'neu'}), test: w.sectionFor({type:'model', id:'teststrecke'}),
            alle: w.sectionFor({type:'model', id:'alle', collection:true}), none: w.sectionFor(null),
            err: [w.explainAddError('ValueError: recipe_id_taken'), w.explainAddError('no_model_loaded'), w.explainAddError('x_unbekannt')],
            lines: w.stdResultLines({results:[{status:'ok', context:8192, tokens_per_s:31.2, stable:true}, {status:'failed', context:32768}]}),
            line: w.recipeLine({model:'D:\\\\Modelle\\\\q.gguf', context_recommended:8192, size_gb:4.1, enabled:true})
          }));
        """)
        self.assertEqual(out['neu'], 'neu')
        self.assertEqual(out['test'], 'teststrecke')
        self.assertIsNone(out['alle'])
        self.assertIsNone(out['none'])
        self.assertIn('Rezept-ID gibt es schon', out['err'][0])
        self.assertIn('Kein Modell geladen', out['err'][1])
        self.assertEqual(out['err'][2], 'x_unbekannt', 'ein unbekanntes Wort bleibt, wie es ist – nichts wird erfunden')
        self.assertEqual(out['lines'], ['Kontext 8192 · 31.2 Token/s · stabil', 'Kontext 32768: nicht geladen'])
        self.assertEqual(out['line'], 'q.gguf · Kontext 8192 · 4.1 GB')

    def test_the_project_tool_names_projects_and_checks_the_name(self):
        out = run_js([UIX / 'tools' / 'files' / 'tool.js'], """
          const f = box.sedraFilesPure;
          console.log(JSON.stringify({
            label: [f.projectLabel({display_name:'Export', project_id:'PRJ-1'}), f.projectLabel({name:'Alt', project_id:'PRJ-2'}), f.projectLabel({project_id:'PRJ-3'}), f.projectLabel(null)],
            ok: [f.nameOk('Export'), f.nameOk('   '), f.nameOk(''), f.nameOk('x'.repeat(80)), f.nameOk('x'.repeat(81))]
          }));
        """)
        self.assertEqual(out['label'], ['Export', 'Alt', 'PRJ-3', 'Projekt'])
        self.assertEqual(out['ok'], [True, False, False, True, False])
