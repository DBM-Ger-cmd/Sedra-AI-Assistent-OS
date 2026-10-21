"""Shell D (Paperclip) – die dritte Form (SPEC_SHELL_E_UND_MODULE_v1 §5).

Was D neu belastet: mehrere Werkzeuge zu mehreren Objekten auf einer Seite, ein Gespräch, das nicht immer sichtbar ist, und
ein Suchfeld, das kein zweites Gespräch sein darf. Hier stehen die reinen Teile und die Zusage, die alle drei Shells
zusammenhält: **dieselben Werkzeuge, drei Formen, kein Werkzeug geändert.**"""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
PAPERCLIP = UIX / 'shells' / 'paperclip'
ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


def run_js(files, code):
    box = ';'.join(f"require({json.dumps(str(f))})" for f in files)
    out = subprocess.run(['node', '-e', f'const box = globalThis; {box}; {code}'], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr.strip()[:400])
    return json.loads(out.stdout.strip().splitlines()[-1])


class Manifest(unittest.TestCase):
    def test_the_shell_declares_what_it_does_and_lists_its_routes(self):
        doc = yaml.safe_load((PAPERCLIP / 'shell.yaml').read_text(encoding='utf-8'))['shell']
        self.assertEqual(doc['id'], PAPERCLIP.name)
        self.assertIn('inbox', doc['provides'], 'der Posteingang ist ihr Kennzeichen')
        for route in ('GET /api/strip', 'GET /api/decisions', 'POST /api/decisions/answer'):
            self.assertIn(route, doc['api'])
        self.assertTrue(doc['entry']['js'][-1].endswith('shell.js'))

    def test_the_shell_reaches_for_no_tool_module_but_the_gespraech(self):
        found = []
        for js in sorted(PAPERCLIP.glob('*.js')):
            for hit in re.findall(r"tools\.(?:mod|manifest|get)\(\s*'([a-z0-9-]+)'|\bt\.id\s*===\s*'([a-z0-9-]+)'", js.read_text(encoding='utf-8')):
                found.append(f'{js.name}: {hit[0] or hit[1]}')
        self.assertEqual(sorted(set(found)), ['shell.js: talk'], found)

    def test_every_file_stays_under_four_hundred_lines_and_styles_only_pc(self):
        for f in sorted(PAPERCLIP.glob('*.js')):
            with self.subTest(f.name):
                self.assertLessEqual(len(f.read_text(encoding='utf-8').splitlines()), 400)
        css = re.sub(r'/\*.*?\*/', '', (PAPERCLIP / 'shell.css').read_text(encoding='utf-8'), flags=re.S)
        for block in css.split('}'):
            selector = block.split('{')[0].strip()
            if selector and not selector.startswith('@'):
                self.assertTrue(selector.split()[0].split(':')[0].startswith('.pc'), selector)
        self.assertNotIn('rgba(', css, 'ein Schleier ist ein Token (--veil-*), keine eigene Farbe')


class PureParts(unittest.TestCase):
    def test_a_collection_and_a_single_object_get_different_pages(self):
        out = run_js([PAPERCLIP / 'pages.js'], """
          const p = require(%s);
          console.log(JSON.stringify({
            none: p.pageFor(null).kind, dash: p.pageFor({type:'dashboard', id:'start'}).kind,
            all: p.pageFor({type:'task', id:'alle', collection:true}).kind, one: p.pageFor({type:'task', id:'M-1'}).kind,
            cards: p.CARDS.map(c=>c.object.type)
          }));
        """ % json.dumps(str(PAPERCLIP / 'pages.js')))
        self.assertEqual(out['none'], 'dashboard')
        self.assertEqual(out['dash'], 'dashboard')
        self.assertEqual(out['all'], 'collection')
        self.assertEqual(out['one'], 'object')
        self.assertEqual(out['cards'], ['intent', 'decision', 'agent', 'task'], 'Ziele, Posteingang, Organigramm, Issues – Objekte, keine Werkzeugnamen')

    def test_the_history_skips_repeats_and_never_grows_without_end(self):
        out = run_js([PAPERCLIP / 'pages.js'], """
          const p = require(%s);
          let h = [];
          for(let i = 0; i < 100; i++) h = p.pushHistory(h, {type:'task', id:'M-' + (i %% 3)});
          const twice = p.pushHistory(p.pushHistory([], {type:'a', id:'1'}), {type:'a', id:'1'});
          console.log(JSON.stringify({len: h.length, max: p.MAX_HISTORY, twice: twice.length}));
        """ % json.dumps(str(PAPERCLIP / 'pages.js')))
        self.assertEqual(out['twice'], 1, 'dieselbe Seite nicht zweimal hintereinander')
        self.assertLessEqual(out['len'], out['max'])

    def test_the_navigation_names_only_objects_a_tool_can_draw(self):
        out = run_js([PAPERCLIP / 'nav.js'], """
          const n = require(%s);
          console.log(JSON.stringify({types: [...new Set(n.NAV.filter(x=>x.object).map(x=>x.object.type))],
                                      on: n.activeIndex(n.NAV, {type:'task', id:'alle'}), off: n.activeIndex(n.NAV, null)}));
        """ % json.dumps(str(PAPERCLIP / 'nav.js')))
        from guppi_runtime.desk.gateway import OBJECT_TYPES
        for t in out['types']:
            # `issue` kommt als Desk-Typ mit G2-S0-12; bis dahin öffnet „Issues“ die Missionen (issuesTarget, D4.1)
            self.assertIn(t, list(OBJECT_TYPES) + ['dashboard', 'issue'], f'{t} ist kein Objekttyp des Vertrags')
        self.assertGreaterEqual(out['on'], 0)
        self.assertEqual(out['off'], -1)
        self.assertIn('routine', out['types'], 'Spec 4 (G2-S4-01): Routinen stehen wieder da – ohne Werkzeug mit Leerzustand (UIX-10)')
        self.assertNotIn('gateway', out['types'], 'Build 24 (Klaus 19:34): das KI GateWay bleibt in seiner eigenen Oberfläche')

    def test_the_badge_counts_open_decisions(self):
        out = run_js([PAPERCLIP / 'nav.js'], """
          const n = require(%s);
          console.log(JSON.stringify({summary: n.badgeCounts({summary:{count: 2}}), items: n.badgeCounts({items:[{}, {}, {}]}), none: n.badgeCounts(null),
                                      badges: n.NAV.filter(x=>x.badge).map(x=>x.badge)}));
        """ % json.dumps(str(PAPERCLIP / 'nav.js')))
        self.assertEqual(out['summary'], {'decisions': 2}); self.assertEqual(out['items'], {'decisions': 3}); self.assertEqual(out['none'], {'decisions': 0})
        self.assertEqual(out['badges'], ['decisions'])


def real_manifests():
    out = []
    for f in sorted((UIX / 'tools').glob('*/tool.yaml')):
        if not f.parent.name.startswith('_'):
            t = yaml.safe_load(f.read_text(encoding='utf-8'))['tool']
            out.append({k: t.get(k) for k in ('id', 'kind', 'handles', 'slot')})
    return out


LOADER = UIX / 'ui' / 'loader.js'
# Spec 4, D4.1: welches Werkzeug jeden Eintrag zeichnen soll, und was bis dahin zeichnet (None: Leerzustand der Shell)
DESIGN = {'Posteingang': ('decisions', 'decisions'), 'Issues': ('board', 'task'), 'Ziele': ('intent', 'intent'),
          'Routinen': ('routines', None), 'Organigramm': ('org', 'crew'), 'Agenten': ('crew', 'crew'), 'Kosten': ('meter', 'meter'),
          'Modelle und Slots': ('slots', 'workshop'), 'KI-Labor': ('labor', 'labor')}


class ShellD(unittest.TestCase):
    """Spec 4, S4.2: Navigation, Seitenart `window`, Verlauf mit Ansicht, Ereignisse ohne Zeitgeber (D4.4)."""

    def nav(self, extra=()):
        return run_js([LOADER, PAPERCLIP / 'nav.js'], """
          const n = require(%s), L = require(%s);
          const reg = L.makeRegistry(%s.map(m=>({manifest: m})));
          console.log(JSON.stringify({sections: n.NAV.filter(x=>x.section).map(x=>x.section),
            rows: n.NAV.filter(x=>x.object && x.object.type !== 'dashboard').map(x=>{ const t = n.target(x, reg);
              return {label: x.label, type: t.type + ':' + t.id, tools: reg.forObject(t).filter(m=>m.slot !== 'nachweis').map(m=>m.id)}; })}));
        """ % (json.dumps(str(PAPERCLIP / 'nav.js')), json.dumps(str(LOADER)), json.dumps(real_manifests() + list(extra))))

    def test_the_navigation_has_the_sections_of_the_design(self):
        out = self.nav()
        self.assertEqual(out['sections'], ['Arbeit', 'Team', 'Betrieb', 'Assistenten', 'Werkzeuge', 'Projekt'])
        labels = [r['label'] for r in out['rows']]
        for label in DESIGN:
            self.assertIn(label, labels)
        self.assertNotIn('Werkstatt (Modelle)', labels, 'derselbe Ort hat nur eine Zeile – die Werkstatt steht unter „Modelle und Slots“')
        self.assertEqual(len({r['type'] for r in out['rows']}), len(out['rows']), 'kein Ort zweimal in der Navigation')

    def test_every_entry_has_its_tool_or_the_stand_in_of_today(self):
        """UIX-02: jeder Eintrag öffnet etwas. Fehlt das Werkzeug des Designs, zeichnet der Ersatz – oder die Shell zeigt den Leerzustand."""
        have = {m['id'] for m in real_manifests()}
        for row in self.nav()['rows']:
            with self.subTest(row['label']):
                soll, ersatz = DESIGN.get(row['label'], (None, None))
                if soll in have:
                    self.assertIn(soll, row['tools'])
                elif soll:
                    self.assertEqual(row['tools'][:1], [ersatz] if ersatz else [])
                else:
                    self.assertTrue(row['tools'], f"{row['label']} ({row['type']}) zeichnet kein Werkzeug")

    def test_issues_open_the_missions_until_a_tool_draws_the_issue_list(self):
        board = {'id': 'board', 'kind': 'object', 'handles': ['issue:alle', 'issue:*'], 'slot': 'inhalt'}
        side = {'id': 'nur-nachweis', 'kind': 'object', 'handles': ['issue:alle'], 'slot': 'nachweis'}
        rows = lambda extra: {r['label']: r for r in self.nav(extra)['rows']}
        self.assertEqual(rows([])['Issues']['type'], 'task:alle')
        self.assertEqual(rows([side])['Issues']['type'], 'task:alle', 'ein Nachweis allein zeichnet keine Liste')
        self.assertEqual(rows([board])['Issues'], {'label': 'Issues', 'type': 'issue:alle', 'tools': ['board']})

    def test_an_agent_is_a_window_and_the_view_is_part_of_the_history(self):
        out = run_js([PAPERCLIP / 'pages.js', PAPERCLIP / 'nav.js'], """
          const p = require(%s), n = require(%s);
          const h1 = p.pushHistory(p.pushHistory([], {type:'agent', id:'alle'}), {type:'agent', id:'alle', view:'liste'});
          const h2 = p.pushHistory(h1, {type:'agent', id:'alle', view:'liste'});
          console.log(JSON.stringify({one: p.pageFor({type:'agent', id:'A-1'}).kind, all: p.pageFor({type:'agent', id:'alle'}).kind,
            roles: p.pageFor({type:'agent', id:'rollen', collection:true}).kind, task: p.pageFor({type:'task', id:'M-1'}).kind,
            views: h1.length, same: h2.length, lit: n.activeIndex(n.NAV, {type:'agent', id:'alle', view:'liste'}) === n.activeIndex(n.NAV, {type:'agent', id:'alle'}),
            issuesLit: n.activeIndex(n.NAV, {type:'task', id:'alle'}) === n.activeIndex(n.NAV, {type:'issue', id:'alle'})}));
        """ % (json.dumps(str(PAPERCLIP / 'pages.js')), json.dumps(str(PAPERCLIP / 'nav.js'))))
        self.assertEqual((out['one'], out['all'], out['roles'], out['task']), ('window', 'collection', 'collection', 'object'))
        self.assertEqual(out['views'], 2, 'Baum und Liste sind zwei Schritte im Verlauf (N5, OP-S4-9)')
        self.assertEqual(out['same'], 2, 'dieselbe Ansicht nicht zweimal')
        self.assertTrue(out['lit'], 'die Ansicht ändert nicht, welche Zeile leuchtet')
        self.assertTrue(out['issuesLit'], '„Issues“ leuchtet für beide Ziele')

    def test_the_shell_hears_the_team_and_keeps_no_timer(self):
        shell = (PAPERCLIP / 'shell.js').read_text(encoding='utf-8')
        for name in ('agent.changed', 'issue.changed', 'budget.warning', 'slot.changed', 'desk.resync'):
            self.assertIn(f"bus.on('{name}'", shell)
        for js in sorted(PAPERCLIP.glob('*.js')):
            if js.name.endswith('.test.js'):
                continue
            self.assertIsNone(re.search(r'\bset(Interval|Timeout)\s*\(', js.read_text(encoding='utf-8')), f'{js.name}: kein Zeitgeber (UIX-05)')
        doc = yaml.safe_load((PAPERCLIP / 'shell.yaml').read_text(encoding='utf-8'))['shell']
        self.assertEqual(doc['version'], '1.2.0')
        self.assertEqual(doc['entry']['js'][-2:], ['windows.js', 'shell.js'])
        self.assertIn('windows', doc['provides'])
        css = (PAPERCLIP / 'shell.css').read_text(encoding='utf-8')
        self.assertIn('.pc-stack', css)

    def test_the_fixture_speaks_the_desk_form_and_passes_other_types_on(self):
        """Prüfmittel (G2-S4-17): das Team im Prüfprojekt, in der Form von §10.1 mit `quelle` (N7); alles andere geht an den Hub."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('uix_fixture_orchestra', UIX.parents[2] / 'benchmarks' / 'uix_fixture_orchestra.py')
        fx = importlib.util.module_from_spec(spec); spec.loader.exec_module(fx)

        class Hub:
            def objects_view(self, payload):
                return {'type': payload['type'], 'items': [{'id': 'R-1'}]}
        hub = fx.install(Hub(), 'orchestra')
        agents = hub.objects_view({'type': 'agent'})
        self.assertEqual(agents['quelle']['zustand'], 'bereit')
        self.assertEqual(len(agents['items']), 4)
        self.assertEqual(sum(1 for a in agents['items'] if a['reports_to'] is None), 1, 'eine Wurzel unter dem Captain (OP-6)')
        self.assertEqual({a['status'] for a in agents['items']}, {'aktiv', 'pausiert'})
        talk = hub.objects_view({'type': 'gespraech', 'agent': 'A-CO'})['items']
        self.assertEqual((len(talk), [m['route'] for m in talk].count('cloud')), (3, 1))
        self.assertTrue(hub.objects_view({'type': 'issue', 'id': 'gibts-nicht'})['missing'])
        self.assertEqual(hub.objects_view({'type': 'model'})['slots']['gesamt'], 3)
        self.assertEqual(hub.objects_view({'type': 'task'}), {'type': 'task', 'items': [{'id': 'R-1'}]})
        off = fx.install(Hub(), 'orchestra-aus').objects_view({'type': 'agent'})
        self.assertEqual((off['items'], off['quelle']['zustand']), ([], 'aus'))
        self.assertNotIn('slots', fx.install(Hub(), 'orchestra-fehler').objects_view({'type': 'model'}))


class ThreeShells(unittest.TestCase):
    def test_all_three_shells_load_the_same_tools(self):
        from guppi_runtime.uix_server import UIXHub
        seen = {}
        for shell in ('cockpit', 'minimal', 'paperclip'):
            with tempfile.TemporaryDirectory(prefix=f'shell-{shell}-') as tmp:
                config = Path(tmp) / 'project' / 'local_config'
                config.mkdir(parents=True)
                (config / 'uix.yaml').write_text(f'uix:\n  shell: {shell}\n', encoding='utf-8')
                hub = UIXHub(Path(tmp) / 'project', ARCH)
                try:
                    manifest = hub.gateway.manifest()
                    self.assertEqual((manifest['shell'] or {}).get('id'), shell, manifest['rejected'])
                    self.assertEqual(manifest['rejected'], [])
                    seen[shell] = sorted(t['id'] for t in manifest['tools'])
                finally:
                    hub.close()
        self.assertEqual(seen['cockpit'], seen['minimal'])
        self.assertEqual(seen['cockpit'], seen['paperclip'], 'drei Formen, dieselben Werkzeuge')

    def test_the_acceptance_knows_every_shell_in_the_package(self):
        """Eine Shell ohne Profil im Prüfwerkzeug wäre eine Shell ohne Abnahme."""
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location('uix_check', UIX.parents[2] / 'benchmarks' / 'uix_check.py')
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        shells = sorted(p.name for p in (UIX / 'shells').iterdir() if p.is_dir() and not p.name.startswith('_'))
        for shell in shells:
            doc = yaml.safe_load((UIX / 'shells' / shell / 'shell.yaml').read_text(encoding='utf-8'))['shell']
            if doc.get('vorgabe'):
                continue                                   # eine Shell aus Vorgabe bringt ihr Profil mit (frame_profile, Build 17)
            opens = any(p in doc['provides'] for p in ('dock', 'windows'))
            if opens:
                self.assertIn(shell, mod.PROFILES, f'{shell} öffnet Objekte – dafür braucht die Abnahme ein Profil')
            else:
                self.assertNotIn(shell, mod.PROFILES, f'{shell} öffnet keine Objekte – das allgemeine Profil genügt')


if __name__ == '__main__':
    unittest.main()
