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
    out = subprocess.run(['node', '-e', f'const box = globalThis; {box}; {code}'], capture_output=True, text=True, timeout=60)
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
        self.assertEqual(out['cards'], ['decision', 'agent', 'task'], 'Posteingang, Organigramm, Issues – Objekte, keine Werkzeugnamen')

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
            self.assertIn(t, list(OBJECT_TYPES) + ['dashboard'], f'{t} ist kein Objekttyp des Vertrags')
        self.assertGreaterEqual(out['on'], 0)
        self.assertEqual(out['off'], -1)


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
