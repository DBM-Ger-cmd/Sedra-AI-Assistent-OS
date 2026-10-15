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
    js = '\n'.join(f.read_text(encoding='utf-8') for f in files)
    head = "const vm=require('vm');const box={};box.globalThis=box;vm.createContext(box);vm.runInContext(process.argv[1],box);"
    run = subprocess.run([NODE, '-e', head + probe, js], capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


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
                run = subprocess.run([NODE, '--check', str(f)], capture_output=True, text=True, timeout=60)
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
        out = run_js([UIX / 'ui' / 'places.js'], "console.log(JSON.stringify(box.sedraPlaces.PLACES.map(p=>p.object.type)));")
        import yaml
        handled = set()
        for manifest in sorted((UIX / 'tools').glob('*/tool.yaml')):
            handled.update(yaml.safe_load(manifest.read_text(encoding='utf-8'))['tool'].get('handles') or [])
        for kind in out:
            self.assertIn(kind, handled, f'the palette opens {kind}, but no tool draws it')

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
