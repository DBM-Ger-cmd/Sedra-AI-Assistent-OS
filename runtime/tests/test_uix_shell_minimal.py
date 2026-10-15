"""Shell E (Minimal) – der Beweis, dass der Werkzeug-Vertrag trägt (SPEC_SHELL_E_UND_MODULE_v1 §1).

Zwei Dinge stehen hier: die reinen Teile der Shell (Geometrie, Reihenfolge der Werkzeuge) und – wichtiger – die Zusage, dass
**beide Shells dieselben Werkzeuge laden, ohne dass an einem Werkzeug etwas geändert werden musste.** Was E beim Bau über den
Vertrag gelernt hat, hält `test_uix_contract` fest; hier steht, was die Shell selbst verspricht."""
import json
import subprocess
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
MINIMAL = UIX / 'shells' / 'minimal'


def run_js(files, code):
    """Die reinen Teile im node laufen lassen – wie bei den anderen Vertragstests."""
    box = ';'.join(f"require({json.dumps(str(f))})" for f in files)
    out = subprocess.run(['node', '-e', f'const box = globalThis; {box}; {code}'],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr.strip()[:400])
    return json.loads(out.stdout.strip().splitlines()[-1])


class Manifest(unittest.TestCase):
    def test_the_shell_declares_what_it_really_does(self):
        doc = yaml.safe_load((MINIMAL / 'shell.yaml').read_text(encoding='utf-8'))['shell']
        self.assertEqual(doc['id'], 'minimal')
        self.assertEqual(doc['id'], MINIMAL.name, 'id ist der Ordnername')
        self.assertIn('windows', doc['provides'])
        self.assertIn('talk', doc['provides'])
        for route in ('GET /api/strip', 'GET /api/decisions', 'POST /api/decisions/answer'):
            self.assertIn(route, doc['api'], 'auch eine Shell braucht ihre Allowlist (Fund aus Build 9)')
        self.assertTrue(doc['entry']['js'][-1].endswith('shell.js'), 'shell.js zuletzt: es registriert')

    def test_the_shell_reaches_for_no_tool_module_but_the_one_the_contract_names(self):
        """Eine Shell darf Objekttypen nennen – sie öffnet ja Objekte. Sie darf sich kein Werkzeug-Modul holen.

        Gesucht wird deshalb der Zugriff (`tools.mod('x')`, `tools.manifest('x')`, `t.id === 'x'`), nicht das bloße Wort:
        `{type: 'task'}` ist ein Objekt, `tools.mod('task')` wäre ein Werkzeug beim Namen."""
        import re
        found = []
        for js in sorted(MINIMAL.glob('*.js')):
            text = js.read_text(encoding='utf-8')
            for hit in re.findall(r"tools\.(?:mod|manifest|get)\(\s*'([a-z0-9-]+)'|\bt\.id\s*===\s*'([a-z0-9-]+)'", text):
                name = hit[0] or hit[1]
                found.append(f'{js.name}: {name}')
        self.assertEqual(sorted(set(found)), ['shell.js: talk'], found)

    def test_every_file_stays_under_four_hundred_lines(self):
        for f in sorted(MINIMAL.glob('*.js')):
            with self.subTest(f.name):
                self.assertLessEqual(len(f.read_text(encoding='utf-8').splitlines()), 400)


class PureParts(unittest.TestCase):
    def test_a_window_always_stays_on_the_screen(self):
        out = run_js([MINIMAL / 'windows.js'], """
          const w = box.module ? box.module.exports : null;
          const m = require(%s);
          const s = {w: 1400, h: 860};
          console.log(JSON.stringify({
            first: m.placeBox(0, s), far: m.clampBox({x: 9000, y: 9000, w: 9000, h: 9000}, s),
            tiny: m.clampBox({x: 0, y: 0, w: 800, h: 600}, {w: 300, h: 200})
          }));
        """ % json.dumps(str(MINIMAL / 'windows.js')))
        self.assertGreaterEqual(out['first']['y'], 32, 'nie unter der Menüleiste')
        self.assertLessEqual(out['far']['x'] + out['far']['w'], 1400)
        self.assertLessEqual(out['far']['y'] + out['far']['h'], 860 - 86, 'nie hinter der Ablage')
        self.assertEqual(out['tiny']['w'], 320, 'kleiner als das Minimum wird ein Fenster nicht')

    def test_the_workpiece_comes_first_and_a_collection_gets_no_evidence(self):
        out = run_js([MINIMAL / 'windows.js'], """
          const m = require(%s);
          const tools = [{id:'tests', slot:'nachweis'}, {id:'task', slot:'inhalt'}, {id:'live', slot:'nachweis'}];
          console.log(JSON.stringify({one: m.orderTools(tools, {collection: false}).map(t=>t.id),
                                      many: m.orderTools(tools, {collection: true}).map(t=>t.id)}));
        """ % json.dumps(str(MINIMAL / 'windows.js')))
        self.assertEqual(out['one'], ['task', 'live', 'tests'])
        self.assertEqual(out['many'], ['task'], '„Live“ und „Kosten“ einer Liste gibt es nicht')


class BothShells(unittest.TestCase):
    """Die eigentliche Zusage: zwei Formen, dieselben Werkzeuge."""

    def test_both_shells_load_the_same_tools(self):
        import tempfile
        from guppi_runtime.uix_server import UIXHub
        arch = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
        seen = {}
        for shell in ('cockpit', 'minimal'):
            with tempfile.TemporaryDirectory(prefix=f'shell-{shell}-') as tmp:
                config = Path(tmp) / 'project' / 'local_config'
                config.mkdir(parents=True)
                (config / 'uix.yaml').write_text(f'uix:\n  shell: {shell}\n', encoding='utf-8')
                hub = UIXHub(Path(tmp) / 'project', arch)
                try:
                    manifest = hub.gateway.manifest()
                    self.assertIsNotNone(manifest['shell'], f'{shell} wurde nicht geladen')
                    self.assertEqual(manifest['shell']['id'], shell)
                    self.assertEqual(manifest['rejected'], [], f'{shell}: {manifest["rejected"]}')
                    seen[shell] = sorted(t['id'] for t in manifest['tools'])
                finally:
                    hub.close()
        self.assertEqual(seen['cockpit'], seen['minimal'], 'eine andere Form, dieselben Werkzeuge')
        self.assertIn('talk', seen['minimal'])

    def test_no_tool_carries_the_class_names_of_a_shell(self):
        """Das Instrument „Zustand“ trug `ck-guppy` und war in jeder anderen Shell unsichtbar (Fund beim Bau von E)."""
        bad = []
        for js in sorted((UIX / 'tools').rglob('*.js')):
            if js.parent.name.startswith('_'):
                continue
            text = js.read_text(encoding='utf-8')
            for prefix in ("'ck-", '"ck-', "'sh-", '"sh-', "'dk-", '"dk-'):
                if prefix in text:
                    bad.append(f'{js.relative_to(UIX)}: {prefix}')
        self.assertEqual(bad, [], 'ein Werkzeug bringt seinen Stil selbst mit (.t-<id>)')


if __name__ == '__main__':
    unittest.main()
