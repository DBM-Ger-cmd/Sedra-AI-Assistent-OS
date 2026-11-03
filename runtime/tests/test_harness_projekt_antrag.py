"""projekt_antrag (02.11.2026): ein zweiter Antrag für denselben Ordner, solange der erste offen ist, wird abgelehnt (vorher endeten die weiteren in `binding_stale`)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.harness import antraege


class Hub:
    def __init__(self, root, offen):
        self.project_root = root
        self._offen = offen

    def _open_requests(self):
        return self._offen


class ProjektAntragDuplikat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'sedra'
        self.root.mkdir()
        self.ordner = Path(self.tmp.name) / 'Baut'
        self.ordner.mkdir()
        self.anderer = Path(self.tmp.name) / 'Anderer'
        self.anderer.mkdir()

    def antrag(self, offen, ordner):
        with mock.patch.object(antraege.gated, 'request', return_value={'mission_id': 'M-NEU'}) as anfrage:
            out = antraege.projekt_antrag(Hub(self.root, offen), {'wurzel': str(ordner), 'name': 'X'})
        return out, anfrage

    def test_ohne_offenen_antrag_wird_er_gestellt(self):
        out, anfrage = self.antrag([], self.ordner)
        self.assertEqual(out['mission_id'], 'M-NEU')
        anfrage.assert_called_once()

    def test_derselbe_ordner_noch_einmal_wird_abgelehnt_und_sagt_wo_er_liegt(self):
        _, erster = self.antrag([], self.ordner)
        projekt = erster.call_args.args[4]['projekt']                       # die Bindung des ersten Antrags
        offen = [{'kind': antraege.KIND_PROJEKT, 'mission_id': 'M-ERSTER', 'binding': {'projekt': projekt}}]
        with mock.patch.object(antraege.gated, 'request') as anfrage:
            with self.assertRaises(ValueError) as ctx:
                antraege.projekt_antrag(Hub(self.root, offen), {'wurzel': str(self.ordner)})
        self.assertIn('antrag_liegt_schon_im_posteingang', str(ctx.exception))
        self.assertIn('M-ERSTER', str(ctx.exception))
        anfrage.assert_not_called()
        out, _ = self.antrag(offen, self.anderer)                          # ein anderer Ordner ist nicht betroffen
        self.assertEqual(out['mission_id'], 'M-NEU')

    def test_ein_ordner_der_schon_ein_projekt_ist_sagt_dem_modell_was_zu_tun_ist(self):
        """Log 02.11.2026: „ordner_schon_projekt: earth-2140“ allein führte das Modell in die Irre; es versuchte den Antrag immer wieder."""
        from guppi_runtime.harness import projekte as harness_projekte
        gesamt = [{'id': 'baut', 'name': 'Baut', 'wurzel': str(self.ordner.resolve()), 'schreibbereich': ['**']}]
        with mock.patch.object(harness_projekte, 'laden', return_value=gesamt), mock.patch.object(antraege.gated, 'request') as anfrage:
            with self.assertRaises(ValueError) as ctx:
                antraege.projekt_antrag(Hub(self.root, []), {'wurzel': str(self.ordner)})
        self.assertIn('ordner_schon_projekt: baut', str(ctx.exception))
        self.assertIn('braucht keinen Antrag', str(ctx.exception))
        self.assertIn('diese_sitzung', str(ctx.exception))
        anfrage.assert_not_called()

    def test_ein_modell_flutet_den_posteingang_nicht(self):
        offen = [{'kind': antraege.KIND_PROJEKT, 'mission_id': f'M-{i}', 'binding': {'projekt': {'wurzel': f'X:/{i}'}}} for i in range(antraege.PROJEKT_ANTRAEGE_MAX)]
        with mock.patch.object(antraege.gated, 'request') as anfrage:
            with self.assertRaises(ValueError) as ctx:
                antraege.projekt_antrag(Hub(self.root, offen), {'wurzel': str(self.anderer)})
        self.assertIn('zu_viele_offene_antraege', str(ctx.exception))
        anfrage.assert_not_called()


if __name__ == '__main__':
    unittest.main()
