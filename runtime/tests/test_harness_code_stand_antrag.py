"""Code-Stand als Antrag im Posteingang (Captain 04.11.2026): statt einer Notiz in jeder neuen Sitzung liegt ein Antrag im Posteingang; der Captain bestätigt einmal, ohne den Code zu lesen.
Gedeckt ist genau der Stand der aufgelisteten Dateien (Bindung); danach geänderter Code braucht wieder eine Bestätigung. Der Antrag nennt, woher der Code kommt (Spur der Harness, git).
Echter CodeStand und ein echtes git-Repo im Temp-Ordner; der Antrag selbst (gated.request) wird abgefangen, das Anwenden ruft den Applier wie die Freigabe-Tür."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sedra_runtime.desk.freigabeklasse import ARTEN, H, ROUTEN_HARNESS, klasse
from sedra_runtime.harness import antraege
from sedra_runtime.harness import projekte as harness_projekte
from sedra_runtime.harness.code_stand import CodeStand

GIT = shutil.which('git')


def git(wurzel, *args):
    subprocess.run(['git', '-C', str(wurzel), '-c', 'user.name=t', '-c', 'user.email=t@t', *args], check=True, capture_output=True)


class Hub:
    def __init__(self, root, offen):
        self.project_root = root
        self._offen = offen
        self.audit = []
        self.ereignisse = []
        self.runtime = SimpleNamespace(audit=SimpleNamespace(append=lambda e, component=None, payload=None, **k: self.audit.append((e, payload))))
        self.events = SimpleNamespace(publish=lambda name, daten: self.ereignisse.append((name, daten)))

    def _open_requests(self):
        return self._offen


@unittest.skipUnless(GIT, 'git fehlt')
class CodeStandAntrag(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / 'sedra'
        (self.root / 'runtime_data' / 'harness').mkdir(parents=True)
        self.wurzel = base / 'projekt'
        (self.wurzel / 'src').mkdir(parents=True)
        (self.wurzel / 'src' / 'a.py').write_text('a = 1\n', encoding='utf-8')
        git(self.wurzel, 'init', '-q')
        git(self.wurzel, 'add', '.')
        git(self.wurzel, 'commit', '-q', '-m', 'Anfang')
        self.projekt = {'id': 'p', 'name': 'Projekt P', 'wurzel': str(self.wurzel.resolve()), 'schreibbereich': ['src/**']}
        self.cs = CodeStand(self.root / 'runtime_data' / 'harness' / 'code_stand', self.projekt['wurzel'], 'p')
        self.assertEqual(self.cs.ungesehen(), [])                                   # beim ersten Gebrauch gilt der Bestand als gesehen
        (self.wurzel / 'src' / 'a.py').write_text('a = 2\n', encoding='utf-8')
        (self.wurzel / 'src' / 'b.py').write_text('b = 1\n', encoding='utf-8')
        git(self.wurzel, 'add', 'src/a.py')
        git(self.wurzel, 'commit', '-q', '-m', 'Aenderung aus anderer Sitzung')     # a.py committet, b.py (neu) nicht
        patcher = mock.patch.object(harness_projekte, 'laden', return_value=[self.projekt])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.hub = Hub(self.root, [])

    def antrag(self, offen=None):
        self.hub._offen = offen or []
        with mock.patch.object(antraege.gated, 'request', return_value={'mission_id': 'M-NEU'}) as anfrage:
            out = antraege.code_stand_antrag(self.hub, self.projekt, self.cs)
        return out, anfrage

    def test_antrag_bindet_genau_die_dateien_und_aendert_nichts(self):
        out, anfrage = self.antrag()
        self.assertEqual((out['mission_id'], out['anzahl'], out['schon_offen']), ('M-NEU', 2, False))
        args, kw = anfrage.call_args
        self.assertEqual(args[1], antraege.KIND_CODE_STAND)
        binding = args[4]
        self.assertEqual((binding['projekt'], [d[0] for d in binding['dateien']]), ('p', ['src/a.py', 'src/b.py']))
        self.assertTrue(kw['exact'])
        self.assertEqual(len(self.cs.ungesehen()), 2, 'der Antrag übernimmt nichts')

    def test_der_antrag_nennt_woher_der_code_kommt(self):
        _, anfrage = self.antrag()
        text = '\n'.join(anfrage.call_args.kwargs['risks'])
        self.assertIn('2 Code-Dateien', text)
        self.assertIn('1 neu', text)
        self.assertIn('keine der Dateien hat die Harness selbst geschrieben', text)
        self.assertIn('Aenderung aus anderer Sitzung', text)                         # Commit-Text aus git log
        self.assertIn('1 der Dateien sind noch nicht committet', text)                # b.py
        self.assertIn('nur diese Fassung ist gedeckt', text)

    def test_von_der_harness_geschriebene_dateien_stehen_als_solche_im_antrag(self):
        self.cs.spur('src/b.py', 'S-AAAAAAAA', 'datei_schreiben')
        zeilen = antraege.code_herkunft(self.projekt['wurzel'], self.cs.ungesehen())
        self.assertTrue(any(z.startswith('Herkunft: 1 von 2 Dateien hat die Harness selbst geschrieben') for z in zeilen), zeilen)

    def test_derselbe_stand_wird_nicht_zweimal_beantragt_ein_anderer_schon(self):
        _, erster = self.antrag()
        offen = [{'kind': antraege.KIND_CODE_STAND, 'mission_id': 'M-ERSTER', 'binding': erster.call_args.args[4]}]
        out, anfrage = self.antrag(offen)
        self.assertEqual((out['mission_id'], out['schon_offen']), ('M-ERSTER', True))
        anfrage.assert_not_called()
        (self.wurzel / 'src' / 'c.py').write_text('c = 1\n', encoding='utf-8')
        out, anfrage = self.antrag(offen)
        self.assertFalse(out['schon_offen'])
        anfrage.assert_called_once()

    def test_ohne_ungesehenen_code_kein_antrag(self):
        self.cs.uebernehmen()
        with mock.patch.object(antraege.gated, 'request') as anfrage:
            with self.assertRaises(ValueError) as ctx:
                antraege.code_stand_antrag(self.hub, self.projekt, self.cs)
        self.assertIn('nichts_ungesehen', str(ctx.exception))
        anfrage.assert_not_called()

    def test_freigabe_uebernimmt_genau_den_gebundenen_stand_und_schreibt_audit(self):
        _, anfrage = self.antrag()
        out = antraege._code_stand_anwenden(self.hub, anfrage.call_args.args[4])
        self.assertEqual(out, {'projekt': 'p', 'anzahl': 2})
        self.assertEqual(self.cs.ungesehen(), [])
        self.assertIn(('HARNESS_CODE_STAND_UEBERNOMMEN', {'projekt': 'p', 'anzahl': 2, 'kanal': 'posteingang'}), self.hub.audit)
        self.assertEqual(self.hub.ereignisse[0][0], 'harness.code_stand')

    def test_hat_sich_code_seit_dem_antrag_geaendert_wird_nichts_uebernommen(self):
        _, anfrage = self.antrag()
        (self.wurzel / 'src' / 'b.py').write_text('b = 99  # nachträglich\n', encoding='utf-8')
        with self.assertRaises(ValueError) as ctx:
            antraege._code_stand_anwenden(self.hub, anfrage.call_args.args[4])
        self.assertEqual(str(ctx.exception), antraege.gated.STALE)
        self.assertEqual(len(self.cs.ungesehen()), 2, 'nichts wurde übernommen')

    def test_ein_fremdes_projekt_in_der_bindung_wird_abgelehnt(self):
        _, anfrage = self.antrag()
        for aenderung in ({'projekt': 'x'}, {'wurzel': str(Path(self.tmp.name) / 'woanders')}):
            with self.assertRaises(ValueError) as ctx:
                antraege._code_stand_anwenden(self.hub, dict(anfrage.call_args.args[4], **aenderung))
            self.assertIn(antraege.gated.REFUSED, str(ctx.exception))
        self.assertEqual(len(self.cs.ungesehen()), 2)


class Einstufung(unittest.TestCase):
    def test_bestaetigung_ist_klasse_h_und_der_weg_ist_ein_antrag(self):
        self.assertEqual(ARTEN['request:harness_code_stand'], H)
        for weg in ('einmal', 'freigeben_und_anwenden'):
            self.assertEqual(klasse('request:harness_code_stand', weg, {}), H)
        self.assertEqual(ROUTEN_HARNESS['POST code_stand/antrag'][0], 'antrag')

    def test_die_art_hat_einen_titel_und_der_applier_ist_registriert(self):
        from sedra_runtime.desk import decisions
        self.assertEqual(decisions.REQUEST_TITLE['harness_code_stand'], 'Code-Stand übernehmen')
        self.assertIn('harness_code_stand', decisions.REQUEST_NOTE)
        registry = SimpleNamespace(frozen=False)
        antraege.registrieren(registry)
        self.assertIs(antraege.gated.applier(antraege.KIND_CODE_STAND), antraege._code_stand_anwenden)


if __name__ == '__main__':
    unittest.main()
