"""Die Fabrikhalle (workflows/fabrik.py): Läufe, Aufgaben und wartende Freigaben als schlanke Übersicht; das Verb am echten Hub."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sedra_runtime.workflows import fabrik  # noqa: E402

JETZT = datetime(2026, 11, 9, 12, 0, 0, tzinfo=timezone.utc)


def lauf(lid, status, gestartet, ende=None, **extra):
    d = {'id': lid, 'lauf': 'run_tests', 'name': 'Tests', 'status': status, 'gestartet': gestartet, 'ende': ende, 'argv': ['python', 'x'], 'ordner_abs': 'E:\\geheim',
         'parameter': {'a': 'b'}, 'fortschritt': {'prozent': None, 'text': ''}, 'gpu': 'keine', 'aufgabe_id': None, 'grund': None}
    d.update(extra)
    return d


class Uebersicht(unittest.TestCase):
    def test_laufend_zuerst_dann_die_letzten_ohne_pfade(self):
        laeufe = [lauf('L-1', 'laeuft', '2026-11-09T11:50:00+00:00', fortschritt={'prozent': 42, 'text': 'Stand 42/100'}),
                  lauf('L-2', 'fertig', '2026-11-09T09:00:00+00:00', '2026-11-09T09:10:00+00:00'),
                  lauf('L-3', 'fehler', '2026-11-09T10:00:00+00:00', '2026-11-09T10:05:00+00:00', grund='exit 1')]
        out = fabrik.uebersicht(laeufe, [], [], None, JETZT)
        self.assertEqual([l['id'] for l in out['laeufe']['laufend']], ['L-1'])
        self.assertEqual([l['id'] for l in out['laeufe']['zuletzt']], ['L-3', 'L-2'], 'neueste Ende zuerst')
        a = out['laeufe']['laufend'][0]
        self.assertEqual((a['prozent'], a['text'], a['dauer_s']), (42, 'Stand 42/100', 600))
        self.assertNotIn('argv', a); self.assertNotIn('ordner_abs', a); self.assertNotIn('parameter', a)
        self.assertEqual(out['laeufe']['zuletzt'][0]['dauer_s'], 300)
        self.assertEqual(out['zaehler'], {'laeuft': 1, 'aufgaben': 0, 'freigaben': 0, 'fehler': 1})

    def test_nur_sechs_beendete_und_kaputte_eintraege_werden_uebergangen(self):
        laeufe = [lauf('L-%d' % i, 'fertig', '2026-11-09T0%d:00:00+00:00' % (i % 9), '2026-11-09T0%d:30:00+00:00' % (i % 9)) for i in range(12)] + ['kaputt', None]
        out = fabrik.uebersicht(laeufe, None, None, None, JETZT)
        self.assertEqual(len(out['laeufe']['zuletzt']), fabrik.LETZTE)
        self.assertEqual(out['aufgaben'], [])
        self.assertEqual(out['freigaben'], {'anzahl': 0, 'neueste': []})

    def test_fortschritt_wird_begrenzt_und_geprueft(self):
        l = fabrik.lauf_schlank(lauf('L-1', 'laeuft', '2026-11-09T11:00:00+00:00', fortschritt={'prozent': 250, 'text': 'x ' * 400}), JETZT)
        self.assertIsNone(l['prozent'])
        self.assertLessEqual(len(l['text']), fabrik.MAX_TEXT)
        l = fabrik.lauf_schlank(lauf('L-1', 'laeuft', 'kein datum'), JETZT)
        self.assertIsNone(l['dauer_s'])
        self.assertEqual(fabrik.lauf_schlank(lauf('L-1', 'laeuft', '2026-11-09T11:00:00', None), JETZT)['dauer_s'], 3600, 'Zeit ohne Zone gilt als UTC')

    def test_aufgaben_freigaben_und_belegung(self):
        aufg = [{'id': 'T-1', 'titel': 'Abnahme', 'zweck_anzeige': 'Tests laufen lassen', 'projekt': 'p', 'rest_aufrufe': 8, 'rest_min': 30, 'aufrufe': 2, 'erlaubt': [{'x': 1}]}]
        karten = [{'karte_id': 'K-%d' % i, 'werkzeug': 'lauf_starten', 'ziel': 'run_tests', 'begruendung': 'b', 'angelegt': '2026-11-09T11:0%d:00+00:00' % i, 'args': {'geheim': 1}} for i in range(5)]
        out = fabrik.uebersicht([], aufg, karten, {'id': 'L-9', 'name': 'Build'}, JETZT)
        self.assertEqual(out['aufgaben'][0], {'id': 'T-1', 'titel': 'Abnahme', 'zweck': 'Tests laufen lassen', 'projekt': 'p', 'rest_aufrufe': 8, 'rest_min': 30, 'aufrufe': 2})
        self.assertEqual(out['freigaben']['anzahl'], 5)
        self.assertEqual([k['karte_id'] for k in out['freigaben']['neueste']], ['K-4', 'K-3', 'K-2'])
        self.assertNotIn('args', out['freigaben']['neueste'][0])
        self.assertEqual(out['belegung'], {'id': 'L-9', 'name': 'Build'})
        self.assertIsNone(fabrik.uebersicht([], [], [], None, JETZT)['belegung'])


class VerbAmEchtenHarness(unittest.TestCase):
    def test_verb_mit_laeufen_aufgaben_und_freigaben(self):
        from sedra_runtime.workflows import desk
        with tempfile.TemporaryDirectory() as tmp:
            class Harness:
                def __init__(self):
                    from sedra_runtime.harness import lauf as hl, aufgabe as ha
                    self.laeufe = hl.Laeufe(Path(tmp) / 'laeufe', typen={})
                    self.aufgaben = ha.Aufgaben(Path(tmp) / 'aufgaben')

                def _lauf_namen(self):
                    return {}

                def entscheidungen(self):
                    return [{'karte_id': 'K-1', 'werkzeug': 'wissen_beantragen', 'ziel': 'docs', 'begruendung': 'Quelle', 'angelegt': '2026-11-09T11:00:00+00:00'}]

            class Hub:
                harness = Harness()
                project_root = Path(tmp)
            out = desk._fabrik(Hub, None, {})
        self.assertEqual(out['status'], 'erledigt')
        self.assertEqual(out['laeufe'], {'laufend': [], 'zuletzt': []})
        self.assertEqual(out['zaehler']['freigaben'], 1)

    def test_ohne_harness_leere_uebersicht(self):
        from sedra_runtime.workflows import desk

        class Hub:
            project_root = Path('.')
        out = desk._fabrik(Hub, None, {})
        self.assertEqual((out['status'], out['zaehler']['laeuft'], out['freigaben']['anzahl']), ('erledigt', 0, 0))


class NodeTest(unittest.TestCase):
    def test_reine_teile_der_fabrikhalle(self):
        import json
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        ui = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'ui'
        run = subprocess.run(['node', 'workflow-live.test.js'], cwd=ui, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-800:] + run.stderr[-300:])
        ergebnis = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(ergebnis['failed'], 0)
        self.assertLessEqual(ergebnis['checks'], 20)
        for name in ('workflow-live.js', 'workflow-editor.js', 'workflow-canvas.js'):
            self.assertLess(len((ui / name).read_text(encoding='utf-8').splitlines()), 400, name)


if __name__ == '__main__':
    unittest.main()
