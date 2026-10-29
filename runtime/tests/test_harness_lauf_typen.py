"""N6 der Harness-Shell Stufe 3: Lauf-Typen – Laden und Prüfen der Datei, `argv_bauen` mit den Grenzen (kein Shell-Interpreter, Muster ganz, Ordner im Projekt)."""
import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.harness import katalog, lauf


def typ(**kw):
    t = {'id': 't', 'argv': ['python', 'x.py', '{a}'], 'parameter': {'a': {'muster': '[a-z]{1,5}'}}, 'ordner': 'runtime'}
    t.update(kw)
    return t


def doc(*typen):
    return {'harness_laeufe': {'version': 1, 'laeufe': list(typen) or [typ()]}}


class DateiTests(unittest.TestCase):
    def test_die_mitgelieferte_datei_ist_gueltig(self):
        d = lauf.laden()
        self.assertEqual(sorted(d['laeufe']), ['devvm_build', 'harness_abnahme', 'nachtlauf_3d', 'run_tests', 'spec_check'])
        b = d['laeufe']['devvm_build']
        self.assertEqual((b['gpu'], b['modell_weg'], b['braucht_modell'], b['modell']), ('exklusiv', True, True, 'coder.local_primary'))
        t = d['laeufe']['run_tests']
        self.assertEqual((t['gpu'], t['modell_weg'], t['braucht_modell']), ('keine', False, False))
        self.assertTrue(t['parameter']['gruppen']['mehrere'])

    def test_lauf_ids_passen_zu_katalog_regeln(self):
        # Das Ziel einer Einstufung ist die Lauf-ID; sie muss als Glob-Ziel taugen (kein /)
        for lid in lauf.laden()['laeufe']:
            regeln = katalog.pruefen({'freigabe_katalog': {'regeln': [{'id': 'r', 'werkzeug': 'lauf_starten', 'muster': [lid], 'stufe': 'frei', 'begruendung': 'x'}]}})
            self.assertEqual(katalog.einstufen(regeln, 'lauf_starten', lid)['stufe'], 'frei')

    def test_fehler_je_grund(self):
        def fehler(**kw):
            t = typ(**kw)
            for k, v in list(t.items()):
                if v is None: del t[k]
            with self.assertRaises(lauf.LaufFehler) as cm:
                lauf.pruefen(doc(t))
            return str(cm.exception)

        with self.assertRaises(lauf.LaufFehler):
            lauf.pruefen({})
        self.assertIn('id_ungueltig', fehler(id='Ungültig!'))
        self.assertIn('argv_ungueltig', fehler(argv=[]))
        self.assertIn('argv_ungueltig', fehler(argv=['python', 5]))
        self.assertIn('programm_ungueltig', fehler(argv=['C:/x/python.exe', '{a}']))
        self.assertIn('platzhalter_ungueltig', fehler(argv=['python', 'x{a}.py']))
        self.assertIn('parameter_fehlt', fehler(argv=['python', 'x.py', '{b}']))
        self.assertIn('unbenutzt', fehler(argv=['python', 'x.py']))
        self.assertIn('muster_ungueltig', fehler(parameter={'a': {'muster': '[a-'}}))
        self.assertIn('vorgabe_passt_nicht', fehler(parameter={'a': {'muster': '[a-z]+', 'vorgabe': '123'}}))
        self.assertIn('ordner_ungueltig', fehler(ordner='../draussen'))
        self.assertIn('ordner_ungueltig', fehler(ordner='C:/x'))
        self.assertIn('gpu_unbekannt', fehler(gpu='viel'))
        self.assertIn('modell_fehlt', fehler(braucht_modell=True))
        self.assertIn('fortschritt_art_unbekannt', fehler(fortschritt={'art': 'magie'}))
        self.assertIn('fortschritt_gruppen', fehler(fortschritt={'art': 'zeilen', 'regex': r'(\d+)'}))
        self.assertIn('fortschritt_regex_ungueltig', fehler(fortschritt={'art': 'prozent', 'regex': '(['}))
        self.assertIn('zeitlimit_ungueltig', fehler(zeitlimit_min=0))
        self.assertIn('zeitlimit_ungueltig', fehler(zeitlimit_min=601))
        with self.assertRaisesRegex(lauf.LaufFehler, 'doppelt'):
            lauf.pruefen(doc(typ(), typ()))

    def test_kaputte_datei_ist_ein_fehler_kein_rueckfall(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'l.yaml'
            p.write_text('harness_laeufe: [kaputt\n', encoding='utf-8')
            with self.assertRaisesRegex(lauf.LaufFehler, 'datei_unlesbar'):
                lauf.laden(p)
            with self.assertRaisesRegex(lauf.LaufFehler, 'datei_unlesbar'):
                lauf.laden(Path(tmp) / 'fehlt.yaml')
            p.write_text(yaml.safe_dump(doc(typ())), encoding='utf-8')
            self.assertEqual(list(lauf.laden(p)['laeufe']), ['t'])


class ArgvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lauf-typen-')
        self.addCleanup(self.tmp.cleanup)
        self.wurzel = Path(self.tmp.name)
        (self.wurzel / 'runtime').mkdir()
        self.typen = lauf.laden()['laeufe']

    def bauen(self, lid, parameter=None):
        return lauf.argv_bauen(self.typen[lid], parameter, self.wurzel)

    def test_run_tests_mit_vorgabe_und_mehreren_gruppen(self):
        a = self.bauen('run_tests')
        self.assertEqual(a['argv'], ['python', 'benchmarks/run_tests.py', 'harness'])
        self.assertEqual((a['ziel'], a['ordner']), ('run_tests', (self.wurzel / 'runtime').resolve()))
        self.assertEqual(self.bauen('run_tests', {'gruppen': 'scheduler desk  harness'})['argv'][2:], ['scheduler', 'desk', 'harness'])
        self.assertEqual(a['bindung'], {'lauf': 'run_tests', 'argv': a['argv'], 'ordner': 'runtime'})

    def test_feste_argumente_bleiben_und_parameter_werden_eingesetzt(self):
        a = self.bauen('devvm_build', {'spec': 'harness_katalog'})
        self.assertEqual(a['argv'], ['python', 'benchmarks/devvm_build.py', '../workspace/GUPPI_OS', '--spec', 'harness_katalog', '--profile', 'standard'])
        self.assertEqual(self.bauen('nachtlauf_3d')['argv'][-1], '6')

    def test_parameter_grenzen(self):
        def fehler(lid, parameter):
            with self.assertRaises(lauf.LaufFehler) as cm:
                self.bauen(lid, parameter)
            return str(cm.exception)

        for boese in ('a; b', 'a | b', 'a && b', 'a > x', 'a`b', 'a$b', 'a(b)', 'a"b', "a'b", 'a\nb'):
            self.assertIn('parameter_spec_ungueltig', fehler('spec_check', {'spec': boese}), boese)
        self.assertIn('unerlaubtes Zeichen', fehler('spec_check', {'spec': '--vm'}))
        self.assertIn('unerlaubtes Zeichen', fehler('spec_check', {'spec': '../x'}))
        self.assertIn('parameter_spec_muster', fehler('spec_check', {'spec': 'GROSS'}))
        self.assertIn('parameter_spec_muster', fehler('spec_check', {'spec': 'a' * 62}))
        self.assertIn('parameter_fehlt: spec', fehler('spec_check', {}))
        self.assertIn('parameter_unbekannt: extra', fehler('spec_check', {'spec': 'x', 'extra': '1'}))
        self.assertIn('parameter_spec_ungueltig', fehler('spec_check', {'spec': ['a']}))
        self.assertIn('parameter_spec_ungueltig', fehler('spec_check', {'spec': True}))
        self.assertIn('parameter_spec_ungueltig', fehler('spec_check', {'spec': '  '}))
        self.assertIn('höchstens 10', fehler('run_tests', {'gruppen': ' '.join(['a'] * 11)}))
        self.assertIn('parameter_stunden_muster', fehler('nachtlauf_3d', {'stunden': '13'}))
        self.assertIn('parameter_stunden_ungueltig', fehler('nachtlauf_3d', {'stunden': '6 7'}))
        self.assertIn('parameter_stunden_muster', fehler('nachtlauf_3d', {'stunden': '0'}))
        self.assertEqual(self.bauen('nachtlauf_3d', {'stunden': 12})['argv'][-1], '12')
        self.assertIn('parameter_kein_objekt', fehler('run_tests', ['x']))
        # die Datei wird durch Fehlversuche nicht verändert
        self.assertEqual(self.typen, lauf.laden()['laeufe'])

    def test_url_des_abnahmelaufs_nur_lokal(self):
        gut = 'http://127.0.0.1:8123/#' + 'a' * 20
        self.assertEqual(self.bauen('harness_abnahme', {'url': gut})['argv'][-1], gut)
        for boese in ('http://example.com:80/#' + 'a' * 20, 'http://127.0.0.1:8123/#kurz', 'file:///c:/x'):
            with self.assertRaises(lauf.LaufFehler, msg=boese):
                self.bauen('harness_abnahme', {'url': boese})

    def test_ordner_im_projekt(self):
        with self.assertRaisesRegex(lauf.LaufFehler, 'ordner_fehlt'):
            lauf.argv_bauen(self.typen['run_tests'], None, self.wurzel / 'runtime')       # dort gibt es kein „runtime“
        t = copy.deepcopy(self.typen['run_tests'])
        t['ordner'] = 'runtime/../..'
        with self.assertRaisesRegex(lauf.LaufFehler, 'ordner_ausserhalb'):
            lauf.argv_bauen(t, None, self.wurzel)


if __name__ == '__main__':
    unittest.main()
