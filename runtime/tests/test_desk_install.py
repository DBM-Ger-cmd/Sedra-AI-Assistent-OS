"""Ein fremdes Modul einbauen, und Vorhaben (desk/install.py, desk/intents.py; Vertrag §6, §7, Cockpit-Regel 8).

Die Zusagen: vor der Freigabe wird nichts kopiert, im Gate steht jede Datei mit ihrem Hash und jeder Fund der Durchsicht, ein
fremdes Modul bekommt nur Leserouten, und zwischen Vorlegen und Einbauen darf sich keine Datei geändert haben."""
import os
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import install, intents

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'

MANIFEST = '''tool:
  id: fremd
  name: "Fremdes Werkzeug"
  version: 1.0.0
  kind: object
  handles: [task]
  entry: {js: tool.js}
  api:
    - GET /api/missions
    - POST /api/mission/run
  events: {emits: [object.open], listens: [task.changed]}
  trust: COMMUNITY
  needs: {ui: ">=1.0 <2"}
'''

CODE = '''(function(){
  const tool = {id:'fremd', mount(el){ el.textContent = 'hallo'; }, unmount(){}};
  if(window.sedra) window.sedra.registerTool(tool);
})();
'''

SNEAKY = CODE.replace("if(window.sedra)", "fetch('https://beispiel.invalid/sammeln');\n  eval('1+1');\n  if(window.sedra)")


def module(folder, code=CODE, manifest=MANIFEST):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'tool.yaml').write_text(manifest, encoding='utf-8')
    (folder / 'tool.js').write_text(code, encoding='utf-8')
    return folder


class Review(unittest.TestCase):
    def test_the_scan_finds_what_the_allowlist_cannot(self):
        found = {f['flag'] for f in install.scan_text(SNEAKY, 'tool.js')}
        self.assertIn('fetch', found)
        self.assertIn('eval', found)
        self.assertIn('fremde Adresse', found)
        self.assertEqual(install.scan_text(CODE, 'tool.js'), [], 'ein sauberes Modul hat keine Funde')

    def test_a_word_in_a_comment_is_not_a_finding(self):
        self.assertEqual(install.scan_text('// hier stand mal ein eval( und ein fetch(\nconst x = 1;\n'), [])

    def test_the_finding_carries_the_line_so_it_can_be_read(self):
        [first] = [f for f in install.scan_text('const x = eval("1");\n', 'tool.js') if f['flag'] == 'eval']
        self.assertEqual(first['line'], 1)
        self.assertIn('eval', first['text'])
        self.assertTrue(first['warum'])

    def test_the_summary_never_pretends(self):
        self.assertIn('nichts gefunden', install.summary([]))
        text = install.summary([{'flag': 'eval'}, {'flag': 'fetch'}])
        self.assertIn('2 Stelle', text)
        self.assertIn('kein Urteil', text)

    def test_reading_a_module_refuses_what_does_not_belong(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = module(Path(tmp) / 'fremd')
            read = install.read_module(folder, 'tools')
            self.assertEqual(sorted(f['path'] for f in read['files']), ['tool.js', 'tool.yaml'])
            self.assertTrue(all(len(f['sha256']) == 64 for f in read['files']))
            (folder / 'böse.exe').write_bytes(b'MZ')
            with self.assertRaises(ValueError):
                install.read_module(folder, 'tools')

    def test_a_module_without_a_manifest_is_not_a_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'leer'
            folder.mkdir()
            with self.assertRaises(ValueError):
                install.read_module(folder, 'tools')


class ThroughTheHub(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-install-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.source = module(Path(self.tmp.name) / 'quelle' / 'fremd', SNEAKY)
        self.installed = Path(self.tmp.name) / 'project' / 'local_config' / 'tools' / 'fremd'

    def test_nothing_is_copied_before_the_captain_decides(self):
        request = self.hub.install_request({'kind': 'tool', 'source': str(self.source)})
        self.assertFalse(self.installed.exists())
        binding = request['binding']
        self.assertEqual(len(binding['files']), 2)
        self.assertTrue(all(len(f['sha256']) == 64 for f in binding['files']))
        self.assertEqual(binding['routes'], ['GET /api/missions'], 'ein fremdes Modul bekommt nur Leserouten')
        risks = request['gate']['request']['risks']
        self.assertIn('fremder Code läuft danach in derselben Seite wie die Shell', risks)
        self.assertTrue(any('eval' in r for r in risks), risks)

    def test_the_whole_way_is_one_decision(self):
        self.hub.install_request({'kind': 'tool', 'source': str(self.source)})
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'request:install')
        self.assertEqual(item['ways'], ['freigeben_und_anwenden', 'ablehnen'])
        self.hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        self.assertTrue((self.installed / 'tool.js').is_file())
        manifest = self.hub.gateway.manifest()
        self.assertIn('fremd', [t['id'] for t in manifest['tools']])
        self.assertTrue(self.hub.gateway.allowed('tool', 'fremd', 'GET', '/api/missions'))
        self.assertFalse(self.hub.gateway.allowed('tool', 'fremd', 'POST', '/api/mission/run'))
        self.assertIn('UIX_MODULE_INSTALLED', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_a_module_that_changed_after_the_request_is_not_installed(self):
        self.hub.install_request({'kind': 'tool', 'source': str(self.source)})
        (self.source / 'tool.js').write_text(CODE + '\n// anders als beim Vorlegen\n', encoding='utf-8')
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'request:install')
        with self.assertRaises(ValueError):
            self.hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        self.assertFalse(self.installed.exists())

    def test_a_broken_manifest_never_reaches_the_captain(self):
        bad = module(Path(self.tmp.name) / 'quelle' / 'kaputt', CODE, MANIFEST.replace('1.0.0', 'nope'))
        with self.assertRaises(ValueError):
            self.hub.install_request({'kind': 'tool', 'source': str(bad)})
        self.assertEqual(self.hub.decisions_view()['summary']['count'], 0)

    def test_a_module_cannot_claim_a_name_that_exists(self):
        taken = module(Path(self.tmp.name) / 'quelle' / 'task', CODE, MANIFEST.replace('id: fremd', 'id: task'))
        with self.assertRaises(ValueError):
            self.hub.install_request({'kind': 'tool', 'source': str(taken)})

    def test_removing_is_no_gate_but_leaves_a_trace(self):
        self.hub.install_request({'kind': 'tool', 'source': str(self.source)})
        item = next(d for d in self.hub.decisions_view()['items'] if d['kind'] == 'request:install')
        self.hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        self.hub.install_remove({'kind': 'tool', 'id': 'fremd'})
        self.assertFalse(self.installed.exists())
        self.assertIn('UIX_MODULE_REMOVED', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_the_templates_are_never_loaded_but_keep_the_contract(self):
        """`_template` ist eine Vorlage, kein Modul – und muss trotzdem bestehen, sonst taugt sie nicht als Anfang (§7.4)."""
        import yaml
        from guppi_runtime.desk.gateway import check_shell, check_tool
        uix = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
        self.assertNotIn('beispiel', [t['id'] for t in self.hub.gateway.manifest()['tools']])
        for folder, check, name, key in ((uix / 'tools' / '_template', check_tool, 'tool.yaml', 'tool'),
                                         (uix / 'shells' / '_template', check_shell, 'shell.yaml', 'shell')):
            with self.subTest(folder.parent.name):
                doc = yaml.safe_load((folder / name).read_text(encoding='utf-8'))
                # Eine Vorlage kann genau eine Regel nicht erfüllen: `id` muss der Ordnername sein. Das erledigt das Umbenennen
                # beim Kopieren (Schritt 1 der README). Dafür wird hier so geprüft, wie es nach dem Kopieren aussähe.
                copied = folder.with_name(doc[key]['id'])
                _, errors = check(doc, folder, 'local')
                self.assertEqual(errors, ['id_must_match_folder'], f'{copied.name}: nur diese eine Abweichung ist erlaubt')
                self.assertTrue((folder / 'README.md').is_file())
                entry = doc[key]['entry']['js']
                for script in ([entry] if isinstance(entry, str) else entry):
                    self.assertEqual(install.scan_text((folder / script).read_text(encoding='utf-8')), [],
                                     'die Vorlage selbst hält sich an das, was sie lehrt')


class Intents(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-intent-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.hub.new_project({'name': 'Export'})

    def test_a_vorhaben_costs_nothing_and_runs_nothing(self):
        entry = self.hub.intent_create({'title': 'CSV-Export aufräumen', 'text': 'Semikolon und Umlaute.'})
        self.assertTrue(intents.ID.match(entry['id']))
        obj = self.hub.object_view('intent', entry['id'])
        self.assertEqual(obj['state'], 'noch keine Aufgabe')
        self.assertEqual(obj['tasks'], [])
        self.assertEqual(self.hub.decisions_view()['summary']['count'], 0, 'ein Vorhaben braucht keine Freigabe')

    def test_guppi_makes_a_task_out_of_it(self):
        entry = self.hub.intent_create({'title': 'CSV-Export aufräumen', 'text': 'Semikolon und Umlaute.'})
        out = self.hub.act({'type': 'intent', 'id': entry['id'], 'verb': 'aufgabe_machen'})
        mission_id = out['result']['mission_id']
        self.assertEqual(self.hub.object_view('task', mission_id)['state'], 'bereit', 'geplant, nicht ausgeführt')
        obj = self.hub.object_view('intent', entry['id'])
        self.assertEqual(obj['tasks'], [mission_id])
        self.assertEqual(obj['state'], 'in Arbeit')
        self.assertIn('INTENT_TASK_CREATED', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_the_state_of_a_vorhaben_comes_from_its_tasks(self):
        missions = {'M-1': {'mission_id': 'M-1', 'status': 'active', 'pending_gates': 1, 'phase': 'EXECUTE'},
                    'M-2': {'mission_id': 'M-2', 'status': 'closed', 'pending_gates': 0, 'phase': 'COMPLETE'}}
        self.assertEqual(intents.state_of({'tasks': []}, missions)[0], 'noch keine Aufgabe')
        self.assertEqual(intents.state_of({'tasks': ['M-1', 'M-2']}, missions)[0], 'wartet auf dich')
        self.assertEqual(intents.state_of({'tasks': ['M-2']}, missions)[0], 'fertig')

    def test_a_vorhaben_needs_a_title(self):
        with self.assertRaises(ValueError):
            self.hub.intent_create({'title': '   ', 'text': 'egal'})


def _links_moeglich():
    """Windows erlaubt symbolische Links nur mit Administratorrechten oder Entwicklermodus. Ohne sie ist der Test nicht ausführbar."""
    with tempfile.TemporaryDirectory() as d:
        try:
            (Path(d) / 'ziel').write_text('x', encoding='utf-8')
            os.symlink(Path(d) / 'ziel', Path(d) / 'link')
            return True
        except OSError:
            return False


LINKS_DA = _links_moeglich()

class Hardening(unittest.TestCase):
    """Härtungsrunde 14.10. (abends): was ein fremdes Modul versuchen könnte, und was die Durchsicht nicht übersehen darf."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-hard-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'fremd'
        self.root.mkdir(parents=True)
        (self.root / 'tool.yaml').write_text('tool: {}\n', encoding='utf-8')
        (self.root / 'tool.js').write_text('const a = 1;\n', encoding='utf-8')

    @unittest.skipUnless(LINKS_DA, 'Symbolische Links brauchen Administratorrechte oder den Entwicklermodus (Windows)')
    def test_a_link_out_of_the_module_is_refused_not_followed(self):
        """Sonst käme eine fremde Datei mit – und das Gateway lieferte sie aus, weil sie auf `.js` endet."""
        secret = Path(self.tmp.name) / 'geheim.txt'
        secret.write_text('PRIVATE KEY\n', encoding='utf-8')
        (self.root / 'schlüssel.js').symlink_to(secret)
        with self.assertRaises(ValueError) as caught:
            install.read_module(self.root)
        self.assertIn('symlink_refused', str(caught.exception))

    @unittest.skipUnless(LINKS_DA, 'Symbolische Links brauchen Administratorrechte oder den Entwicklermodus (Windows)')
    def test_a_linked_folder_is_refused_instead_of_silently_skipped(self):
        anders = Path(self.tmp.name) / 'anderswo'
        anders.mkdir()
        (anders / 'mehr.js').write_text('const b = 2;\n', encoding='utf-8')
        (self.root / 'teil').symlink_to(anders)
        with self.assertRaises(ValueError):
            install.read_module(self.root)

    def test_a_block_comment_does_not_hide_a_finding(self):
        """`*/ eval(x)` beginnt mit einem Stern und ist trotzdem Code – und `#feld = eval(x)` ist es auch."""
        self.assertTrue(install.is_comment('// eval(x)'))
        self.assertTrue(install.is_comment(' * nur Text'))
        self.assertFalse(install.is_comment('*/ eval(x)'))
        self.assertFalse(install.is_comment('#feld = eval(x)'))
        found = [f['flag'] for f in install.scan_text('*/ eval(x)\n#f = new Function(y)\n// eval(z)\n')]
        self.assertEqual(found, ['eval', 'new Function'])

    def test_a_url_survives_the_comment_rule(self):
        """Nach `//` wird nichts abgeschnitten – in `https://…` steckt der Fund selbst."""
        found = [f['flag'] for f in install.scan_text("const u = 'https://fremd.example/x';\n")]
        self.assertEqual(found, ['fremde Adresse'])

    def test_a_foreign_module_is_community_whatever_it_claims(self):
        """Gefunden mit der ersten externen Lieferung: ihr Manifest sagte `trust: CAPTAIN` – und hätte so seine Schreibrouten behalten."""
        from guppi_runtime.uix_server import UIXHub
        hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(hub.close)
        claims = MANIFEST.replace('trust: COMMUNITY', 'trust: CAPTAIN')
        source = module(Path(self.tmp.name) / 'quelle' / 'fremd', CODE, claims)
        request = hub.install_request({'kind': 'tool', 'source': str(source)})
        self.assertEqual(request['binding']['trust'], 'COMMUNITY')
        self.assertEqual(request['binding']['routes'], ['GET /api/missions'], 'die POST-Route ist weg, bevor der Captain entscheidet')
        self.assertIn('als COMMUNITY', request['binding']['describe'])
        item = next(d for d in hub.decisions_view()['items'] if d['kind'] == 'request:install')
        hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        installed = Path(self.tmp.name) / 'project' / 'local_config' / 'tools' / 'fremd' / 'tool.yaml'
        self.assertIn('trust: COMMUNITY', installed.read_text(encoding='utf-8'), 'auch die eingebaute Datei sagt es')
        self.assertIn('trust: CAPTAIN', (source / 'tool.yaml').read_text(encoding='utf-8'), 'die Quelle bleibt, wie sie war')
        self.assertFalse(hub.gateway.allowed('tool', 'fremd', 'POST', '/api/mission/run'))

    def test_write_routes_are_granted_only_through_a_gate_that_names_them(self):
        """Captain-Entscheidung 15.10.2026: ein fremdes Modul schreibt erst, wenn genau seine Routen freigegeben sind."""
        from guppi_runtime.uix_server import UIXHub
        hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(hub.close)
        source = module(Path(self.tmp.name) / 'quelle' / 'fremd', CODE)
        hub.install_request({'kind': 'tool', 'source': str(source)})
        item = next(d for d in hub.decisions_view()['items'] if d['kind'] == 'request:install')
        hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        self.assertFalse(hub.gateway.allowed('tool', 'fremd', 'POST', '/api/mission/run'), 'eingebaut heißt: lesen')
        request = hub.trust_request({'kind': 'tool', 'id': 'fremd'})
        self.assertEqual(request['binding']['routes'], ['POST /api/mission/run'], 'das Gate nennt genau die Routen')
        self.assertIn('POST /api/mission/run', request['gate']['request']['risks'])
        self.assertFalse(hub.gateway.allowed('tool', 'fremd', 'POST', '/api/mission/run'), 'vor der Freigabe ändert sich nichts')
        item = next(d for d in hub.decisions_view()['items'] if d['kind'] == 'request:trust')
        self.assertEqual(item['ways'], ['freigeben_und_anwenden', 'ablehnen'])
        hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        self.assertTrue(hub.gateway.allowed('tool', 'fremd', 'POST', '/api/mission/run'))
        self.assertFalse(hub.gateway.allowed('tool', 'fremd', 'POST', '/api/switches'), 'nichts darüber hinaus')
        self.assertIn('UIX_MODULE_WRITE_ROUTES_GRANTED', [e['event_type'] for e in hub.audit_view()['events']])
        with self.assertRaises(ValueError):
            hub.trust_request({'kind': 'tool', 'id': 'fremd'})          # ist jetzt CAPTAIN – nichts mehr zu heben

    def test_a_manifest_changed_after_the_trust_request_is_not_raised(self):
        from guppi_runtime.uix_server import UIXHub
        hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(hub.close)
        source = module(Path(self.tmp.name) / 'quelle' / 'fremd', CODE)
        hub.install_request({'kind': 'tool', 'source': str(source)})
        item = next(d for d in hub.decisions_view()['items'] if d['kind'] == 'request:install')
        hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        hub.trust_request({'kind': 'tool', 'id': 'fremd'})
        installed = Path(self.tmp.name) / 'project' / 'local_config' / 'tools' / 'fremd' / 'tool.yaml'
        installed.write_text(installed.read_text(encoding='utf-8').replace('POST /api/mission/run', 'POST /api/mission/run\n    - POST /api/switches'), encoding='utf-8')
        item = next(d for d in hub.decisions_view()['items'] if d['kind'] == 'request:trust')
        with self.assertRaises(ValueError) as caught:
            hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        self.assertIn('manifest_changed_since_the_request', str(caught.exception))
        self.assertFalse(hub.gateway.allowed('tool', 'fremd', 'POST', '/api/switches'))

    def test_what_is_copied_is_hashed_again(self):
        """Geprüft ist, was jetzt dort steht – nicht, was eben noch dort stand."""
        from guppi_runtime.uix_server import UIXHub
        hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(hub.close)
        source = module(Path(self.tmp.name) / 'quelle' / 'fremd', CODE)
        hub.install_request({'kind': 'tool', 'source': str(source)})
        item = next(d for d in hub.decisions_view()['items'] if d['kind'] == 'request:install')
        hub.decide({'id': item['id'], 'way': 'freigeben_und_anwenden'})
        installed = Path(self.tmp.name) / 'project' / 'local_config' / 'tools' / 'fremd'
        self.assertTrue((installed / 'tool.js').is_file())
        self.assertFalse(installed.with_name(installed.name + '.im-bau').exists(), 'kein halber Ordner bleibt liegen')

    def test_the_file_of_vorhaben_does_not_grow_without_end(self):
        store = intents.Store(Path(self.tmp.name) / 'p')
        items = {f'V-{n:08X}': {'title': 't', 'text': '', 'project_id': 'P', 'created_at': '2026', 'tasks': []}
                 for n in range(intents.MAX_INTENTS)}
        store._write(items)
        with self.assertRaises(ValueError):
            store.add('noch eins', '', 'P', '2026-10-14T20:00:00Z')


if __name__ == '__main__':
    unittest.main()
