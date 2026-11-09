"""Der rote Knopf: Haltemarke, Sperre beim Start von Läufen, Notaus-Ablauf (erst Marke, alles parallel stoppen, Fehler halten nichts auf), Verben."""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sedra_runtime.workflows import desk, fabrik  # noqa: E402


class Haltemarke(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_ohne_datei_laeuft_alles(self):
        self.assertIsNone(fabrik.angehalten(self.root))
        self.assertFalse(fabrik.freigeben(self.root))

    def test_anhalten_und_freigeben(self):
        m = fabrik.anhalten(self.root, 'Etwas läuft aus dem Ruder', von='captain')
        self.assertEqual((m['grund'], m['von']), ('Etwas läuft aus dem Ruder', 'captain'))
        self.assertEqual(fabrik.angehalten(self.root)['grund'], 'Etwas läuft aus dem Ruder')
        self.assertEqual(list(fabrik.halt_pfad(self.root).parent.glob('*.tmp')), [])
        self.assertTrue(fabrik.freigeben(self.root))
        self.assertIsNone(fabrik.angehalten(self.root))

    def test_kaputte_marke_gilt_nicht_als_halt_aber_ein_zweiter_halt_ueberschreibt(self):
        fabrik.halt_pfad(self.root).parent.mkdir(parents=True)
        fabrik.halt_pfad(self.root).write_text('{kaputt', encoding='utf-8')
        self.assertIsNone(fabrik.angehalten(self.root))
        fabrik.anhalten(self.root, 'neu')
        self.assertEqual(fabrik.angehalten(self.root)['grund'], 'neu')

    def test_grund_ist_begrenzt(self):
        self.assertLessEqual(len(fabrik.anhalten(self.root, 'x' * 1000)['grund']), 200)


class LaufStartSperre(unittest.TestCase):
    def test_gestoppte_fabrik_startet_keinen_lauf(self):
        from sedra_runtime.harness import lauf as hl
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gestartet = []
            laeufe = hl.Laeufe(root / 'runtime_data' / 'harness' / 'laeufe', typen={}, starten=lambda d: gestartet.append(d) or (None, None))
            typ = {'id': 'run_tests', 'name': 'Tests', 'gpu': 'keine', 'modell_weg': False, 'zeitlimit_min': 5}
            info = {'argv': ['python', 'x'], 'ordner': root}
            fabrik.anhalten(root, 'Notaus')
            with self.assertRaises(hl.LaufFehler) as c:
                laeufe.starten(typ, info)
            self.assertIn('fabrik_angehalten', str(c.exception))
            self.assertEqual(gestartet, [], 'es wurde nichts angelegt oder gestartet')
            self.assertEqual(laeufe.alle(), [])
            fabrik.freigeben(root)
            self.assertEqual(laeufe.starten(typ, info)['status'], 'laeuft')
            self.assertEqual(len(gestartet), 1)


class Fake:
    """Eine Harness aus Attrappen, die festhält, was der Notaus tut."""

    def __init__(self, root, laeufe=(), aufgaben=(), antworten=(), dauer=0.0, kaputt=()):
        self.root, self.dauer, self.kaputt = root, dauer, set(kaputt)
        self.ereignisse, self.marke_vorher = [], {}
        outer = self

        class Laeufe:
            def laufende(self_):
                return [{'id': i} for i in laeufe]

            def alle(self_):
                return []

            def belegt(self_):
                return None

            def stoppen(self_, lid, grund='', warten_s=10):
                outer.marke_vorher[lid] = fabrik.angehalten(root) is not None
                time.sleep(outer.dauer)
                if lid in outer.kaputt:
                    raise ValueError('nicht_laufend')
                outer.ereignisse.append(('lauf', lid))

        class Aufgaben:
            def alle(self_, status=None):
                return [{'id': i} for i in aufgaben]

            def zuruecknehmen(self_, tid, grund=None):
                outer.marke_vorher[tid] = fabrik.angehalten(root) is not None
                if tid in outer.kaputt:
                    raise ValueError('nicht_aktiv')
                outer.ereignisse.append(('aufgabe', tid))

        class Antwort:
            def __init__(self_, i):
                self_.id = i

            def stoppen(self_):
                outer.ereignisse.append(('antwort', self_.id))

        class Stroeme:
            def laufende(self_):
                return [Antwort(i) for i in antworten]
        self.laeufe, self.aufgaben, self.stroeme = Laeufe(), Aufgaben(), Stroeme()

    def _lauf_namen(self):
        return {}

    def _audit(self, event, payload):
        self.ereignisse.append(('audit', event, payload))


class NotausAblauf(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_marke_zuerst_dann_alles_gestoppt_und_zurueckgenommen(self):
        h = Fake(self.root, laeufe=['L-1', 'L-2'], aufgaben=['T-1'], antworten=['A-1'])
        b = fabrik.notaus(h, self.root, 'Test', warten_s=1)
        self.assertEqual((sorted(b['laeufe']), b['aufgaben'], b['antworten'], b['fehler']), (['L-1', 'L-2'], ['T-1'], ['A-1'], []))
        self.assertTrue(all(h.marke_vorher.values()), 'die Haltemarke stand schon, bevor etwas gestoppt wurde')
        self.assertIsNotNone(fabrik.angehalten(self.root))
        audit = [e for e in h.ereignisse if e[0] == 'audit']
        self.assertEqual(audit[0][1], 'FABRIK_NOTAUS')
        self.assertEqual(sorted(audit[0][2]['laeufe']), ['L-1', 'L-2'])

    def test_laeufe_werden_gleichzeitig_gestoppt(self):
        h = Fake(self.root, laeufe=['L-1', 'L-2', 'L-3', 'L-4'], dauer=1.0)
        t = time.monotonic()
        b = fabrik.notaus(h, self.root, 'Test', warten_s=1)
        self.assertEqual(len(b['laeufe']), 4)
        self.assertLess(time.monotonic() - t, 2.8, 'vier Läufe zu je 1 s dauern zusammen nicht 4 s')

    def test_ein_fehler_haelt_die_anderen_nicht_auf(self):
        h = Fake(self.root, laeufe=['L-1', 'L-2'], aufgaben=['T-1', 'T-2'], kaputt=['L-1', 'T-2'])
        b = fabrik.notaus(h, self.root, 'Test', warten_s=1)
        self.assertEqual((b['laeufe'], b['aufgaben']), (['L-2'], ['T-1']))
        self.assertEqual(len(b['fehler']), 2)
        self.assertTrue(any('L-1' in f for f in b['fehler']) and any('T-2' in f for f in b['fehler']))
        self.assertIsNotNone(fabrik.angehalten(self.root), 'die Marke steht trotz der Fehler')

    def test_prozesse_im_live_reiter_stehen_danach_als_angehalten_da(self):
        from sedra_runtime.workflows import live
        live.melde(self.root, 'vollautomatischer-bau', 'bauen', 'laeuft')
        live.melde(self.root, 'anderer-ablauf', 'a', 'fertig')
        b = fabrik.notaus(Fake(self.root), self.root, 'Test', warten_s=1)
        self.assertEqual(b['prozesse'], ['vollautomatischer-bau'])
        stand = {s['prozess']: s for s in live.lesen(self.root)}
        self.assertEqual((stand['vollautomatischer-bau']['zustand'], stand['vollautomatischer-bau']['text']), ('fehler', 'Fabrik angehalten (Notaus)'))
        self.assertEqual(stand['anderer-ablauf']['zustand'], 'fertig', 'ein beendeter Lauf bleibt, wie er war')

    def test_leere_fabrik_wird_trotzdem_angehalten(self):
        b = fabrik.notaus(Fake(self.root), self.root, 'Test', warten_s=1)
        self.assertEqual((b['laeufe'], b['aufgaben'], b['antworten'], b['fehler']), ([], [], [], []))
        self.assertIsNotNone(fabrik.angehalten(self.root))

    def test_wiederholter_notaus_ist_harmlos(self):
        h = Fake(self.root, laeufe=['L-1'])
        fabrik.notaus(h, self.root, 'a', warten_s=1)
        b = fabrik.notaus(h, self.root, 'b', warten_s=1)
        self.assertEqual(fabrik.angehalten(self.root)['grund'], 'b')
        self.assertEqual(b['fehler'], [])


class VerbenAmHub(unittest.TestCase):
    def test_stopp_freigeben_und_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            class Hub:
                project_root = root
                harness = Fake(root, laeufe=['L-1'], aufgaben=['T-1'])
            self.assertIsNone(desk._fabrik_status(Hub, None, {})['angehalten'])
            out = desk._fabrik_stopp(Hub, None, {})
            self.assertEqual((out['status'], out['laeufe'], out['aufgaben']), ('erledigt', ['L-1'], ['T-1']))
            st = desk._fabrik_status(Hub, None, {})['angehalten']
            self.assertIn('roter Knopf', st['grund'])
            self.assertTrue(desk._fabrik_freigeben(Hub, None, {})['war_angehalten'])
            self.assertIsNone(desk._fabrik_status(Hub, None, {})['angehalten'])
            self.assertFalse(desk._fabrik_freigeben(Hub, None, {})['war_angehalten'])
            audit = [e[1] for e in Hub.harness.ereignisse if e[0] == 'audit']
            self.assertEqual(audit, ['FABRIK_NOTAUS', 'FABRIK_FREIGEGEBEN'])

    def test_ohne_harness_gibt_es_trotzdem_eine_marke(self):
        with tempfile.TemporaryDirectory() as tmp:
            class Hub:
                project_root = Path(tmp)
            out = desk._fabrik_stopp(Hub, None, {})
            self.assertEqual(out['status'], 'erledigt')
            self.assertIsNotNone(fabrik.angehalten(Path(tmp)))

    def test_fabrik_verb_meldet_die_marke(self):
        with tempfile.TemporaryDirectory() as tmp:
            class Hub:
                project_root = Path(tmp)
                harness = Fake(Path(tmp))

                def decisions_view(self):
                    return {'items': []}
            hub = Hub()
            fabrik.anhalten(tmp, 'Probe')
            self.assertEqual(desk._fabrik(hub, None, {})['angehalten']['grund'], 'Probe')


class BauProzess(unittest.TestCase):
    """Der Bau läuft als eigener Prozess (Sperrdatei mit PID); der Notaus beendet ihn, aber nur, wenn die PID wirklich zu bau_schleife gehört."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'runtime_data').mkdir()

    def sperre(self, pid):
        (self.root / 'runtime_data' / 'bau_schleife.lock').write_text(str(pid), encoding='utf-8')

    def test_ohne_sperrdatei_kein_bau(self):
        self.assertIsNone(fabrik.bau_prozess(self.root))

    def test_pid_zaehlt_nur_mit_passender_befehlszeile(self):
        self.sperre(4711)
        self.assertEqual(fabrik.bau_prozess(self.root, befehlszeile=lambda p: 'python benchmarks/bau_schleife.py --projekt x start y'), 4711)
        self.assertIsNone(fabrik.bau_prozess(self.root, befehlszeile=lambda p: 'notepad.exe datei.txt'), 'eine weitergegebene PID trifft keinen fremden Prozess')
        self.assertIsNone(fabrik.bau_prozess(self.root, befehlszeile=lambda p: None), 'ein toter Prozess hat keine Befehlszeile')

    def test_kaputte_oder_eigene_pid_wird_ignoriert(self):
        import os
        for inhalt in ('abc', '', '12 34', str(os.getpid())):
            self.sperre(inhalt)
            self.assertIsNone(fabrik.bau_prozess(self.root, befehlszeile=lambda p: 'bau_schleife'), inhalt)

    def test_echter_prozess_wird_erkannt_und_beendet_ein_fremder_nicht(self):
        import subprocess
        bau = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)', 'bau_schleife.py'])
        fremd = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
        self.addCleanup(lambda: [(p.kill() if p.poll() is None else None, p.wait()) for p in (bau, fremd)])
        self.sperre(bau.pid)
        self.assertEqual(fabrik.bau_prozess(self.root), bau.pid)
        self.sperre(fremd.pid)
        self.assertIsNone(fabrik.bau_prozess(self.root), 'ein Prozess ohne bau_schleife in der Befehlszeile bleibt unberührt')
        self.sperre(bau.pid)
        self.assertTrue(fabrik.bau_beenden(fabrik.bau_prozess(self.root)))
        bau.wait(timeout=20)
        self.assertIsNotNone(bau.poll())
        self.assertIsNone(fremd.poll(), 'der fremde Prozess läuft weiter')

    def test_notaus_beendet_den_bau_und_meldet_ihn(self):
        import subprocess
        bau = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)', 'bau_schleife.py'])
        self.addCleanup(lambda: (bau.kill() if bau.poll() is None else None, bau.wait()))
        self.sperre(bau.pid)
        b = fabrik.notaus(Fake(self.root), self.root, 'Test', warten_s=1)
        self.assertEqual(b['bau'], bau.pid)
        bau.wait(timeout=20)
        self.assertIsNotNone(bau.poll())

    def test_notaus_ohne_bau_meldet_keinen(self):
        self.assertIsNone(fabrik.notaus(Fake(self.root), self.root, 'Test', warten_s=1)['bau'])

    def test_manager_startet_bei_angehaltener_fabrik_keinen_bau(self):
        from sedra_runtime.manager import werkzeuge
        fabrik.anhalten(self.root, 'Notaus')
        out = werkzeuge.bau_starten(self.root, 'Spec ZAHLEN')
        self.assertFalse(out['gestartet'])
        self.assertIn('Fabrik ist angehalten', out['grund'])


class NodeTest(unittest.TestCase):
    def test_reine_teile_des_knopfes_und_dateigroessen(self):
        import json
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        ui = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'ui'
        run = subprocess.run(['node', 'workflow-notaus.test.js'], cwd=ui, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-800:] + run.stderr[-300:])
        ergebnis = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(ergebnis['failed'], 0)
        self.assertLessEqual(ergebnis['checks'], 20)
        for name in ('workflow-notaus.js', 'workflow-live.js', 'workflow-editor.js'):
            self.assertLess(len((ui / name).read_text(encoding='utf-8').splitlines()), 400, name)


if __name__ == '__main__':
    unittest.main()
