"""Die Gesetze des Managers: Cloud-Aufgaben, Captain-Rechte, Untergebene und das Journal."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.manager import Manager, VerfassungsVerstoss


class ManagerGesetze(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.journal = self.tmp / "journal.jsonl"
        self.m = Manager("manager", {"datei_lesen", "bau_start"}, journal=self.journal)

    def test_cloud_nur_fuer_erlaubte_aufgaben(self):
        self.m.pruefe_auftrag("code_und_spec_des_baus", cloud=True)
        with self.assertRaises(VerfassungsVerstoss) as ctx:
            self.m.pruefe_auftrag("persoenliche_daten", cloud=True)
        self.assertEqual(ctx.exception.gesetz, "cloud_aufgaben")

    def test_captain_rechte_bleiben_beim_captain(self):
        with self.assertRaises(VerfassungsVerstoss) as ctx:
            self.m.pruefe_auftrag("bau", recht="freigabe_erteilen")
        self.assertEqual(ctx.exception.gesetz, "nur_captain")

    def test_recht_das_der_manager_nicht_hat(self):
        with self.assertRaises(VerfassungsVerstoss) as ctx:
            self.m.pruefe_auftrag("bau", recht="loeschen")
        self.assertEqual(ctx.exception.gesetz, "nur_captain")

    def test_untergebener_erbt_hoechstens_die_rechte_des_managers(self):
        u = self.m.delegiere("bauagent", {"datei_lesen"})
        self.assertEqual(u.rechte, {"datei_lesen"})
        with self.assertRaises(VerfassungsVerstoss):
            self.m.delegiere("pruefer", {"datei_lesen", "bau_start", "web_zugriff"})

    def test_tiefe_begrenzt(self):
        u = self.m.delegiere("bauagent", {"datei_lesen"})
        enkel = u.delegiere("helfer", {"datei_lesen"})
        self.assertEqual(enkel.tiefe, 2)
        with self.assertRaises(VerfassungsVerstoss) as ctx:
            enkel.delegiere("zu_tief", {"datei_lesen"})
        self.assertEqual(ctx.exception.gesetz, "untergebene")

    def test_journal_haelt_jede_entscheidung_fest(self):
        self.m.pruefe_auftrag("code_und_spec_des_baus", cloud=True)
        with self.assertRaises(VerfassungsVerstoss):
            self.m.pruefe_auftrag("bau", recht="freigabe_erteilen")
        zeilen = self.journal.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(zeilen), 2)
        self.assertIn('"ok": false', zeilen[1])


if __name__ == "__main__":
    unittest.main()
