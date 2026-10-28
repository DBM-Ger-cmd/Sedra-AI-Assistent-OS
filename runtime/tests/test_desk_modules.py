"""Das Werkzeug „Module“ und die vier Routen darunter (Spec SHELL_E_UND_MODULE §2).

Zwei Linien stehen hier auf dem Prüfstand:
    fremder Code  → Gate (das prüft `test_desk_install`)
    eigene Form   → Audit, kein Gate: Shell wechseln, Werkzeug an/aus, aus der Vorlage anlegen
und die Zusage, die beide zusammenhält: **keine dieser Handlungen fasst den Projektordner an.**"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'


class Modules(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-modules-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.project = self.hub.new_project({'name': 'Export'})
        self.workspace = self.hub.runtime.filesystem_tool._resolve(self.project['workspace_path'], must_exist=True)
        (self.workspace / 'README.md').write_text('# Export\n', encoding='utf-8')

    def snapshot(self):
        """Jede Datei des Projektordners mit ihrer Größe – damit „fasst nichts an“ überprüfbar ist und nicht behauptet."""
        return {str(p.relative_to(self.workspace)): p.stat().st_size for p in sorted(self.workspace.rglob('*')) if p.is_file()}

    def kinds(self):
        return [e['event_type'] for e in self.hub.audit_view()['events']]

    def test_the_view_says_what_the_surface_is_made_of(self):
        view = self.hub.modules_view()
        self.assertEqual(view['shell'], 'start', 'der Einstieg, solange nichts gewählt ist')
        self.assertTrue(view['shell_available'])
        self.assertEqual(sorted(s['id'] for s in view['shells']), ['cockpit', 'fisch', 'gateway-kmu', 'gateway-studio', 'guppi-xp', 'harness', 'minimal', 'paperclip', 'start', 'wissensbasis'])   # harness (28.10., Harness-Shell Stufe 1), gateway-kmu (Build 19), fisch (19.10.), wissensbasis (27.10.)
        self.assertTrue(next(s for s in view['shells'] if s['id'] == 'start')['enabled'])
        self.assertIn('modules', [t['id'] for t in view['tools']])
        self.assertEqual(view['rejected'], [])
        for tool in view['tools']:
            self.assertTrue(tool['name'] and tool['trust'] and tool['origin'], tool)
        self.assertEqual(len(view['templates']), 2, 'die beiden Vorlagen stehen im Werkzeug')

    def test_switching_the_shell_is_audited_and_not_a_gate(self):
        out = self.hub.shell_set({'shell': 'minimal'})
        self.assertEqual(out['before'], 'start')
        self.assertEqual(self.hub.gateway.manifest()['shell']['id'], 'minimal')
        self.assertIn('UIX_SHELL_CHANGED', self.kinds())
        self.assertEqual(self.hub.decisions_view()['summary']['count'], 0, 'eigene Form braucht keine Freigabe')
        with self.assertRaises(ValueError):
            self.hub.shell_set({'shell': 'gibtsnicht'})

    def test_a_tool_can_be_switched_off_and_on_again(self):
        before = len(self.hub.gateway.manifest()['tools'])
        self.hub.tool_enabled({'id': 'meter', 'enabled': False})
        self.assertEqual(len(self.hub.gateway.manifest()['tools']), before - 1)
        self.assertNotIn('meter', [t['id'] for t in self.hub.gateway.manifest()['tools']])
        self.assertFalse(next(t for t in self.hub.modules_view()['tools'] if t['id'] == 'meter')['enabled'])
        self.hub.tool_enabled({'id': 'meter', 'enabled': True})
        self.assertEqual(len(self.hub.gateway.manifest()['tools']), before)
        self.assertIn('UIX_TOOL_DISABLED', self.kinds())
        self.assertIn('UIX_TOOL_ENABLED', self.kinds())
        with self.assertRaises(ValueError):
            self.hub.tool_enabled({'id': 'gibtsnicht', 'enabled': False})

    def test_the_gespraech_and_the_modules_tool_cannot_be_switched_off(self):
        """Ohne Gespräch kein Eingabefeld (Regel 1); ohne „Module“ käme der Captain nur über die Datei zurück."""
        for tool in ('talk', 'modules'):
            with self.subTest(tool), self.assertRaises(ValueError) as caught:
                self.hub.tool_enabled({'id': tool, 'enabled': False})
            self.assertIn('tool_is_required', str(caught.exception))
        required = sorted(t['id'] for t in self.hub.modules_view()['tools'] if t['required'])
        self.assertEqual(required, ['modules', 'talk'], 'die Liste sagt dem Werkzeug, wo kein Schalter hingehört')

    def test_a_module_from_the_template_loads_right_away(self):
        out = self.hub.module_scaffold({'kind': 'tool', 'id': 'routinen', 'name': 'Routinen'})
        folder = Path(out['folder'])
        self.assertTrue((folder / 'tool.yaml').is_file())
        manifest = self.hub.gateway.manifest()
        self.assertIn('routinen', [t['id'] for t in manifest['tools']], manifest['rejected'])
        self.assertEqual(manifest['rejected'], [], 'was angelegt wird, lädt auch – sonst entsteht es gar nicht erst')
        made = next(t for t in manifest['tools'] if t['id'] == 'routinen')
        self.assertEqual(made['trust'], 'CAPTAIN', 'ein eigenes Modul ist nie CORE')
        self.assertEqual(made['origin'], 'local')
        self.assertIn('UIX_MODULE_SCAFFOLDED', self.kinds())
        self.assertEqual(self.hub.decisions_view()['summary']['count'], 0, 'die eigene Vorlage ist kein Gate')

    def test_an_own_shell_from_the_template_loads_runs_and_can_be_removed_but_not_while_active(self):
        out = self.hub.module_scaffold({'kind': 'shell', 'id': 'meine-bruecke', 'name': 'Meine Brücke'})
        self.assertEqual(out['kind'], 'shells')
        shells = self.hub.modules_view()['shells']
        mine = next(s for s in shells if s['id'] == 'meine-bruecke')
        self.assertEqual(mine['trust'], 'CAPTAIN')
        self.assertEqual(mine['origin'], 'local')
        js = (Path(out['folder']) / 'shell.js').read_text(encoding='utf-8')
        self.assertIn("id: 'meine-bruecke'", js, 'die Vorlage ist umbenannt, nicht nur kopiert')
        self.assertNotIn('beispiel', js)
        self.hub.shell_set({'shell': 'meine-bruecke'})
        self.assertEqual(self.hub.gateway.manifest()['shell']['id'], 'meine-bruecke', 'die eigene Shell lädt')
        with self.assertRaises(ValueError) as caught:
            self.hub.install_remove({'kind': 'shell', 'id': 'meine-bruecke'})
        self.assertIn('shell_is_active', str(caught.exception))
        self.hub.shell_set({'shell': 'cockpit'})
        self.hub.install_remove({'kind': 'shell', 'id': 'meine-bruecke'})
        self.assertNotIn('meine-bruecke', [s['id'] for s in self.hub.modules_view()['shells']])

    def test_a_half_built_module_never_stays_behind(self):
        self.hub.module_scaffold({'kind': 'tool', 'id': 'routinen'})
        with self.assertRaises(ValueError):
            self.hub.module_scaffold({'kind': 'tool', 'id': 'routinen'})
        for bad in ('Routinen', 'a', 'mit leerzeichen', '../weg'):
            with self.subTest(bad), self.assertRaises(ValueError):
                self.hub.module_scaffold({'kind': 'tool', 'id': bad})
        leftovers = list((self.root / 'local_config' / 'tools').glob('.im-bau*'))
        self.assertEqual(leftovers, [], 'kein halber Ordner bleibt liegen')

    def test_none_of_the_three_touches_the_project_folder(self):
        """Die Zusage des Werkzeugs: geschrieben wird nur in local_config. Deshalb berührt keine davon eine Grenze."""
        before = self.snapshot()
        self.hub.shell_set({'shell': 'minimal'})
        self.hub.tool_enabled({'id': 'meter', 'enabled': False})
        self.hub.module_scaffold({'kind': 'tool', 'id': 'routinen'})
        self.assertEqual(self.snapshot(), before, 'der Projektordner ist unberührt')
        self.assertTrue((self.root / 'local_config' / 'uix.yaml').is_file())
        self.assertTrue((self.root / 'local_config' / 'tools' / 'routinen').is_dir())

    def test_a_broken_config_is_reported_not_guessed_around(self):
        (self.root / 'local_config').mkdir(parents=True, exist_ok=True)
        (self.root / 'local_config' / 'uix.yaml').write_text('uix: {shell: 17}\n', encoding='utf-8')
        with self.assertRaises(Exception):
            self.hub.modules_view()


class ToolItself(unittest.TestCase):
    def test_a_rejection_is_explained_in_words(self):
        out = subprocess.run(['node', '-e', f'''
          const t = require({json.dumps(str(UIX / 'tools' / 'modules' / 'tool.js'))});
          console.log(JSON.stringify({{a: t.reason('id_must_match_folder'), b: t.reason('needs_ui_not_met'),
                                       c: t.reason('etwas_ganz_neues'), trust: t.TRUST.COMMUNITY}}));
        '''], capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[:300])
        data = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertIn('Ordnername', data['a'])
        self.assertIn('Vertrags', data['b'])
        self.assertEqual(data['c'], 'etwas_ganz_neues', 'was wir nicht kennen, steht wörtlich da – nicht beschönigt')
        self.assertIn('Leserouten', data['trust'])

    def test_the_tool_is_reachable_from_both_shells(self):
        """Der Ort steht im Vertrag (ui/places.js) – damit kennen ihn Palette, Menü und das Gespräch."""
        places = (UIX / 'ui' / 'places.js').read_text(encoding='utf-8')
        self.assertIn("type: 'module'", places)
        tree = (UIX / 'shells' / 'cockpit' / 'tree.js').read_text(encoding='utf-8')
        self.assertIn("type: 'module'", tree, 'im Cockpit steht es unter System')


if __name__ == '__main__':
    unittest.main()
