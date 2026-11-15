"""Die Arbeitsanweisung des Managers nennt `team_verteilen` (Abnahme am PC, 15.11.2026): ohne den Hinweis verlangte das Modell vom Captain
ausformulierte Teilaufträge und kannte nur die Cloud-Verteilung. Geprüft wird die Endfassung, so wie die Vorlage sie dem Modell gibt."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.harness import vorlagen
from sedra_runtime.manager import verfassung


class ManagerTeamAnweisung(unittest.TestCase):
    def setUp(self):
        self.vorlage = vorlagen.laden(Path(tempfile.mkdtemp()), 'manager')

    def test_systemtext_der_vorlage_nennt_beide_wege_und_ihre_grenze(self):
        s = self.vorlage['system']
        self.assertIn('`team_verteilen`', s)
        self.assertIn('bis zu drei lokale Helfer', s)
        self.assertIn('`auftraege_verteilen` ist nur für die Cloud', s)
        self.assertIn('Das ist kein Erfinden', s)
        self.assertIn('du gibst nichts frei', s)
        self.assertIn('ungeprüft', s)

    def test_vorlage_bietet_das_werkzeug_an_das_die_anweisung_nennt(self):
        self.assertIn('team_verteilen', self.vorlage['werkzeuge'])
        self.assertIn('auftraege_verteilen', self.vorlage['werkzeuge'])

    def test_anweisung_bleibt_kurz_und_vergibt_keine_rechte(self):
        datei = verfassung.CONFIG / 'arbeitsanweisungen' / 'manager.md'
        self.assertLess(datei.stat().st_size, verfassung.MAX_DATEI)
        kopf = datei.read_text(encoding='utf-8').split('---')[1]
        self.assertNotIn('rechte', kopf)
        self.assertIn('cloud: false', kopf)


if __name__ == '__main__':
    unittest.main()
