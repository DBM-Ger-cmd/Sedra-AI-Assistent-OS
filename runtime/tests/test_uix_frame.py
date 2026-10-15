"""Build 17, Schritt 2: eine Shell aus einer Vorgabe (ui/frame.js, ui/schema/vorgabe.schema.json, SPEC_SHELL_AUS_VORGABE_v1).

Der Vermittler prüft die Vorgabe und leitet Slots und Routen ab; der Rahmen ist Vertragscode; das Gerüst legt eine Shell aus
Vorgabe an; die reinen Teile des Rahmens laufen in node. Der Browser-Teil ist `uix_check --vorgabe <datei>` (drei Formen, 27/27)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.desk import gateway
from guppi_runtime.models import structured
from host_isolation import setUpModule, tearDownModule  # noqa: F401

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
NODE = shutil.which('node')
VORGABE = {'id': 'bruecke', 'name': 'Brücke', 'raster': ['leiste', 'orte|werkstueck', 'gespraech'],
           'orte': {'breite': 220}, 'werkstueck': {'nachweise': 'seitenleiste'}, 'gespraech': {'art': 'zone', 'hoehe': 112},
           'entscheidungen': 'karte', 'suche': 'strg-k', 'start': {'type': 'task', 'id': 'alle', 'title': 'Aufgaben'}}
SHELL = {'shell': {'id': 'bruecke', 'name': 'Brücke', 'version': '1.0.0', 'vorgabe': 'shell.vorgabe.yaml', 'trust': 'CAPTAIN',
                   'needs': {'ui': '>=1.0 <2'}}}


def folder(tmp, vorgabe=VORGABE, shell=SHELL, name='bruecke'):
    f = Path(tmp) / name
    f.mkdir()
    (f / 'shell.yaml').write_text(yaml.safe_dump(shell, allow_unicode=True), encoding='utf-8')
    if vorgabe is not None:
        (f / 'shell.vorgabe.yaml').write_text(yaml.safe_dump(vorgabe, allow_unicode=True), encoding='utf-8')
    return f


class DasSchema(unittest.TestCase):
    def test_the_schema_stays_in_the_subset_a_local_model_can_be_forced_to(self):
        schema = json.loads((UIX / 'ui' / 'schema' / 'vorgabe.schema.json').read_text(encoding='utf-8'))
        structured.check_schema(schema)
        self.assertEqual(structured.validate(VORGABE, schema), [])
        self.assertTrue(structured.validate({'id': 'x', 'name': 'X', 'raster': ['werkstueck'], 'fenster': 3}, schema))


class DerVermittler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def check(self, **kw):
        f = folder(self.tmp.name, **kw)
        return gateway.check_shell(yaml.safe_load((f / 'shell.yaml').read_text(encoding='utf-8')), f, 'local')

    def test_a_shell_from_a_vorgabe_needs_no_code_and_gets_slots_and_routes_from_the_frame(self):
        man, errors = self.check()
        self.assertEqual(errors, [])
        self.assertTrue(man['frame'])
        self.assertEqual(man['js'], [])
        self.assertEqual(man['api'], gateway.FRAME_API)
        self.assertEqual(man['provides'], ['dock', 'talk', 'strip', 'tree', 'palette', 'inbox'])
        self.assertEqual(man['vorgabe']['raster'], VORGABE['raster'])

    def test_slots_follow_the_vorgabe(self):
        v = dict(VORGABE, raster=['werkstueck'], gespraech={'art': 'schublade'}, entscheidungen='werkzeug', suche='keine')
        man, errors = self.check(vorgabe=v)
        self.assertEqual(errors, [])
        self.assertEqual(man['provides'], ['dock', 'talk'])
        shutil.rmtree(Path(self.tmp.name) / 'bruecke')
        man, errors = self.check(vorgabe=dict(v, suche='feld'))
        self.assertEqual(errors, ['vorgabe_invalid:$.suche: ein Suchfeld braucht die Zone leiste'])

    def test_what_is_refused_and_why(self):
        cases = [
            (dict(VORGABE, fenster=3), 'vorgabe_invalid:$: Feld „fenster“ gibt es nicht'),
            (dict(VORGABE, raster=['leiste', 'gespraech']), 'vorgabe_invalid:$.raster: werkstueck fehlt'),
            (dict(VORGABE, raster=['werkstueck', 'werkstueck|gespraech']), 'vorgabe_invalid:$.raster: eine Zone kommt zweimal vor'),
            (dict(VORGABE, raster=['werkstueck']), 'vorgabe_invalid:$.raster: gespraech fehlt (oder gespraech.art: schublade)'),
            (dict(VORGABE, raster=['werkstueck|bank', 'gespraech']), 'vorgabe_invalid:$.raster[0]: passt nicht zum Muster'),
            (dict(VORGABE, id='andere'), 'vorgabe_id_must_match'),
            (dict(VORGABE, orte={'breite': 20}), 'vorgabe_invalid:$.orte.breite: mindestens 140'),
        ]
        for v, expected in cases:
            shutil.rmtree(Path(self.tmp.name) / 'bruecke', ignore_errors=True)
            man, errors = self.check(vorgabe=v)
            self.assertIsNone(man, expected)
            self.assertTrue(any(e.startswith(expected) for e in errors), (expected, errors))

    def test_code_routes_and_slots_in_the_file_are_refused_they_belong_to_the_frame(self):
        s = {'shell': dict(SHELL['shell'], api=['GET /api/switches'], provides=['dock'])}
        man, errors = self.check(shell=s)
        self.assertIsNone(man)
        self.assertIn('vorgabe_shell_has_no_api', errors)
        self.assertIn('vorgabe_shell_has_no_provides', errors)

    def test_a_missing_vorgabe_file_is_named(self):
        man, errors = self.check(vorgabe=None)
        self.assertEqual(errors, ['vorgabe_missing'])

    def test_the_manifest_serves_the_frame_from_ui(self):
        from guppi_runtime.desk.registry import Registry
        project = Path(self.tmp.name) / 'project'
        (project / 'local_config' / 'shells').mkdir(parents=True)
        folder(project / 'local_config' / 'shells')
        (project / 'local_config' / 'uix.yaml').write_text('uix:\n  shell: bruecke\n', encoding='utf-8')
        man = gateway.Gateway(project, Registry(project)).manifest()
        self.assertEqual(man['shell']['id'], 'bruecke')
        self.assertEqual(man['shell']['js'], ['/uix/ui/frame.js'])
        self.assertEqual(man['shell']['css'], ['/uix/ui/frame.css'])
        self.assertEqual(man['shell']['vorgabe']['id'], 'bruecke')
        self.assertTrue(gateway.route_allowed(gateway.FRAME_API, 'GET', '/api/strip'))
        self.assertFalse(gateway.route_allowed(gateway.FRAME_API, 'GET', '/api/switches'))


class DasGeruest(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-frame-'); self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH); self.addCleanup(self.hub.close)

    def test_a_shell_from_the_template_vorgabe_is_created_without_code(self):
        out = self.hub.module_scaffold({'kind': 'shell', 'id': 'meine', 'name': 'Meine', 'vorgabe': True})
        f = Path(out['folder'])
        self.assertEqual(sorted(p.name for p in f.iterdir()), ['README.md', 'shell.vorgabe.yaml', 'shell.yaml'])
        v = yaml.safe_load((f / 'shell.vorgabe.yaml').read_text(encoding='utf-8'))
        self.assertEqual((v['id'], v['name']), ('meine', 'Meine'))
        self.assertIn('meine', self.hub.gateway.shells())
        self.assertIn('ohne Code', out['note'])

    def test_a_shell_from_a_given_vorgabe(self):
        out = self.hub.module_scaffold({'kind': 'shell', 'id': 'seiten', 'name': 'Seiten',
                                        'vorgabe': dict(VORGABE, raster=['orte|werkstueck|entscheidungen', 'gespraech'], werkstueck={'nachweise': 'spalten'})})
        man = self.hub.gateway.shells()['seiten'][1]
        self.assertEqual(man['vorgabe']['werkstueck'], {'nachweise': 'spalten'})
        self.assertEqual(man['provides'], ['dock', 'talk', 'tree', 'palette', 'inbox'])
        self.assertIn('UIX_MODULE_SCAFFOLDED', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_a_bad_vorgabe_leaves_nothing_behind(self):
        with self.assertRaises(ValueError) as ctx:
            self.hub.module_scaffold({'kind': 'shell', 'id': 'kaputt', 'vorgabe': dict(VORGABE, raster=['leiste'])})
        self.assertIn('werkstueck fehlt', str(ctx.exception))
        self.assertFalse((Path(self.tmp.name) / 'project' / 'local_config' / 'shells' / 'kaputt').exists())
        with self.assertRaises(ValueError):
            self.hub.module_scaffold({'kind': 'tool', 'id': 'werk', 'vorgabe': True})


class DerRahmen(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def run_js(self, probe):
        js = (UIX / 'ui' / 'frame.js').read_text(encoding='utf-8')
        head = "const vm=require('vm');const box={};box.globalThis=box;vm.createContext(box);vm.runInContext(process.argv[1],box);"
        run = subprocess.run([NODE, '-e', head + probe, js], capture_output=True, text=True, timeout=60)
        if run.returncode != 0:
            raise AssertionError(run.stderr)
        return json.loads(run.stdout)

    def test_the_raster_becomes_rows_of_columns_and_every_assumption_has_one_place(self):
        out = self.run_js("""
          const f = box.sedraFrame;
          const L = f.layoutOf({raster: ['leiste', 'orte|werkstueck', 'gespraech'], orte: {breite: 200}});
          const M = f.layoutOf({raster: ['werkstueck|fenster'], gespraech: {art: 'schublade'}, suche: 'feld'});
          console.log(JSON.stringify({rows: L.rows, zones: L.zones, breite: L.orte.breite, nachweise: L.nachweise, hoehe: L.gespraech.hoehe,
            ent: L.entscheidungen, suche: L.suche, start: L.start.type, hasOrte: L.hasZone('orte'),
            mRows: M.rows, mArt: M.gespraech.art, mSuche: M.suche}));
        """)
        self.assertEqual(out['rows'], [['leiste'], ['orte', 'werkstueck'], ['gespraech']])
        self.assertEqual(out['zones'], ['leiste', 'orte', 'werkstueck', 'gespraech'])
        self.assertEqual((out['breite'], out['nachweise'], out['hoehe'], out['ent'], out['suche'], out['start']), (200, 'seitenleiste', 112, 'karte', 'strg-k', 'task'))
        self.assertTrue(out['hasOrte'])
        self.assertEqual(out['mRows'], [['werkstueck']], 'eine unbekannte Zone fällt weg – der Vermittler hat sie vorher abgewiesen')
        self.assertEqual((out['mArt'], out['mSuche']), ('schublade', 'feld'))

    def test_the_sketch_of_the_creator_follows_the_raster(self):
        js = (UIX / 'ui' / 'vorgabe.js').read_text(encoding='utf-8')
        head = "const vm=require('vm');const box={};box.globalThis=box;vm.createContext(box);vm.runInContext(process.argv[1],box);"
        run = subprocess.run([NODE, '-e', head + "console.log(JSON.stringify(box.sedraVorgabe.sketchRows({raster:['leiste','orte|werkstueck|entscheidungen']})))", js],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = json.loads(run.stdout)
        self.assertEqual([[c['label'] for c in r] for r in rows], [['Instrumente'], ['Orte', 'Werkstück', 'Entscheidungen']])
        self.assertGreater(rows[1][1]['weight'], rows[1][0]['weight'])

    def test_the_frame_is_contract_code_no_fetch_no_eval_one_global(self):
        text = (UIX / 'ui' / 'frame.js').read_text(encoding='utf-8')
        for forbidden in ('fetch(', 'XMLHttpRequest', 'eval(', 'new Function', 'import('):
            self.assertNotIn(forbidden, text)
        self.assertLessEqual(len(text.splitlines()), 400)
        self.assertEqual(text.count('root.sedraFrame ='), 1)


if __name__ == '__main__':
    unittest.main()
