"""Live-Meldungen laufender Prozesse: Datei, Zustände der Knoten, Veralten, Eingabeprüfung, Befehlszeile, Verb im Desk."""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from sedra_runtime.workflows import live  # noqa: E402

P = 'vollautomatischer-bau'


class Meldungen(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_melden_schreibt_atomar_und_behaelt_den_verlauf(self):
        live.melde(self.root, P, 'spec', 'laeuft', text='Spec prüfen')
        s = live.melde(self.root, P, 'bauen', 'laeuft', text='Stufe S1, Versuch 1 von 6')
        self.assertEqual((s['schritt'], s['zustand'], s['text']), ('bauen', 'laeuft', 'Stufe S1, Versuch 1 von 6'))
        self.assertEqual([e['schritt'] for e in s['verlauf']], ['spec', 'bauen'])
        self.assertEqual(list((self.root / 'runtime_data' / 'live').glob('*.tmp')), [])

    def test_knoten_fertig_laeuft_fehler(self):
        for schritt, z in (('auftrag', 'laeuft'), ('spec', 'laeuft'), ('bauen', 'laeuft'), ('test', 'fehler'), ('fehler', 'laeuft')):
            s = live.melde(self.root, P, schritt, z)
        k = live.knoten(s)
        self.assertEqual(k, {'sa-%s-auftrag' % P: 'fertig', 'sa-%s-spec' % P: 'fertig', 'sa-%s-bauen' % P: 'fertig',
                             'sa-%s-test' % P: 'fehler', 'sa-%s-fehler' % P: 'laeuft'})

    def test_schleife_derselbe_schritt_wieder_zaehlt_als_aktuell(self):
        for schritt in ('bauen', 'test', 'bauen'):
            s = live.melde(self.root, P, schritt, 'laeuft')
        k = live.knoten(s)
        self.assertEqual((k['sa-%s-bauen' % P], k['sa-%s-test' % P]), ('laeuft', 'fertig'))

    def test_wartet_auf_den_menschen_und_ende(self):
        s = live.melde(self.root, P, 'captain', 'wartet', text='Produkt wartet auf deine Prüfung')
        self.assertEqual(live.knoten(s)['sa-%s-captain' % P], 'wartet')
        s = live.melde(self.root, P, None, 'fertig')
        self.assertEqual(live.knoten(s)['sa-%s-captain' % P], 'fertig')
        self.assertIsNone(s['schritt'])

    def test_nach_dem_ende_beginnt_ein_neuer_lauf(self):
        live.melde(self.root, P, 'spec', 'laeuft')
        live.melde(self.root, P, None, 'fertig')
        s = live.melde(self.root, P, 'auftrag', 'laeuft')
        self.assertEqual([e['schritt'] for e in s['verlauf']], ['auftrag'])
        s = live.melde(self.root, P, 'spec', 'laeuft', neu=True)
        self.assertEqual([e['schritt'] for e in s['verlauf']], ['spec'])

    def test_eingaben_werden_geprueft(self):
        for args in (('../x', 'a', 'laeuft'), ('Gross', 'a', 'laeuft'), (P, '../a', 'laeuft'), (P, 'a', 'kaputt'), (P, None, 'laeuft'), (P, '', 'laeuft'), ('', 'a', 'laeuft')):
            with self.assertRaises(ValueError, msg=str(args)):
                live.melde(self.root, *args)
        self.assertFalse((self.root / 'runtime_data').exists())

    def test_text_und_verlauf_sind_begrenzt(self):
        for i in range(live.MAX_VERLAUF + 30):
            s = live.melde(self.root, P, 'bauen', 'laeuft', text='x' * 1000)
        self.assertEqual(len(s['verlauf']), live.MAX_VERLAUF)
        self.assertLessEqual(len(s['verlauf'][-1]['text']), live.MAX_TEXT)

    def test_lesen_veraltet_und_kaputte_dateien(self):
        alt = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat(timespec='seconds')
        live.melde(self.root, P, 'bauen', 'laeuft', zeit=alt)
        live.melde(self.root, 'anderer-prozess', 'a', 'fertig', zeit=alt)
        (self.root / 'runtime_data' / 'live' / 'kaputt.json').write_text('{nicht json', encoding='utf-8')
        (self.root / 'runtime_data' / 'live' / 'fremd.json').write_text('{"schema": 2}', encoding='utf-8')
        liste = {s['prozess']: s for s in live.lesen(self.root)}
        self.assertEqual(sorted(liste), ['anderer-prozess', P])
        self.assertTrue(liste[P]['veraltet'])
        self.assertFalse(liste['anderer-prozess']['veraltet'], 'ein beendeter Lauf veraltet nicht')
        frisch = live.melde(self.root, P, 'bauen', 'laeuft')
        self.assertFalse([s for s in live.lesen(self.root) if s['prozess'] == P][0]['veraltet'], frisch['aktualisiert'])

    def test_lesen_ohne_ordner(self):
        self.assertEqual(live.lesen(self.root), [])

    def test_befehlszeile_ohne_warnung_und_mit_fehlercode(self):
        cmd = [sys.executable, '-B', '-m', 'sedra_runtime.workflows.live', 'melde', '--projekt', str(self.root), '--prozess', P, '--schritt', 'spec', '--zustand', 'laeuft', '--text', 'Spec prüfen']
        env = {'PYTHONPATH': str(SRC), 'PYTHONUTF8': '1', 'SYSTEMROOT': __import__('os').environ.get('SYSTEMROOT', '')}
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('Warning', r.stderr)
        self.assertEqual(json.loads((self.root / 'runtime_data' / 'live' / (P + '.json')).read_text(encoding='utf-8'))['schritt'], 'spec')
        r = subprocess.run(cmd[:-6] + ['--schritt', '../x', '--zustand', 'laeuft'], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2)
        self.assertIn('live_schritt_ungueltig', r.stderr)


class VerbImDesk(unittest.TestCase):
    def test_verb_liefert_prozess_mit_diagramm_und_zaehlern(self):
        from sedra_runtime.workflows import desk, selbstabbild
        from sedra_runtime.workflows.store import WorkflowStore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = WorkflowStore(root)
            ids = {a['ablauf']: a['id'] for a in selbstabbild.anlegen(store)}
            live.melde(root, P, 'spec', 'laeuft', text='Spec prüfen')
            live.melde(root, P, 'bauen', 'laeuft', text='Stufe S1')

            class Hub:
                project_root = root
            out = desk._live(Hub, None, {})
        self.assertEqual(out['status'], 'erledigt')
        p = out['prozesse'][0]
        self.assertEqual((p['workflow_id'], p['schritt'], p['zustand']), (ids[P], 'bauen', 'laeuft'))
        self.assertIn('Stufe bauen', p['schritt_name'])
        self.assertEqual(out['zaehler']['laeuft'], 1)
        self.assertEqual(p['knoten']['sa-%s-spec' % P], 'fertig')
        self.assertTrue(all('schritt_name' in e for e in p['verlauf']))

    def test_unbekannter_schritt_hat_keinen_namen(self):
        from sedra_runtime.workflows import desk, selbstabbild
        from sedra_runtime.workflows.store import WorkflowStore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selbstabbild.anlegen(WorkflowStore(root))
            live.melde(root, P, 'gibt-es-nicht', 'laeuft')

            class Hub:
                project_root = root
            p = desk._live(Hub, None, {})['prozesse'][0]
        self.assertIsNotNone(p['workflow_id'])
        self.assertIsNone(p['schritt_name'])

    def test_ohne_diagramm_bleibt_die_meldung_sichtbar(self):
        from sedra_runtime.workflows import desk
        with tempfile.TemporaryDirectory() as tmp:
            live.melde(tmp, 'ohne-bild', 'a', 'wartet')

            class Hub:
                project_root = Path(tmp)
            out = desk._live(Hub, None, {})
        self.assertEqual(out['prozesse'][0]['workflow_id'], None)
        self.assertEqual(out['prozesse'][0]['titel'], 'ohne-bild')
        self.assertEqual(out['zaehler']['wartet'], 1)


if __name__ == '__main__':
    unittest.main()
