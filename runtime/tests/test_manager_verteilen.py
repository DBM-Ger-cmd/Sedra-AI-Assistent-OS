"""Werkzeug `auftraege_verteilen`: der Manager gibt Teilaufträge an den Hilfs-Coder in der Cloud (manager/kanal.py)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sedra_runtime.manager import Manager, VerfassungsVerstoss, werkzeuge


class VerteilenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.m = Manager("manager", set(), journal=self.tmp / "journal.jsonl")
        patch = mock.patch("sedra_runtime.manager.kanal.waehle_modell", return_value="anbieter/modell")
        patch.start(); self.addCleanup(patch.stop)
        send = mock.patch("sedra_runtime.manager.kanal.Vorarbeiter._senden",
                          side_effect=lambda typ, modell, text: {"ok": True, "modell": modell, "typ": typ, "antwort": "ANTWORT: " + text, "sekunden": 0.1})
        self.senden = send.start(); self.addCleanup(send.stop)

    def test_auftraege_gehen_in_reihenfolge_an_den_kanal(self):
        out = werkzeuge.auftraege_verteilen(self.m, self.tmp, [{"typ": "code_und_spec_des_baus", "text": "eins"}, {"typ": "code_und_spec_des_baus", "text": "zwei"}])
        self.assertEqual([x["antwort"] for x in out], ["ANTWORT: eins", "ANTWORT: zwei"])
        self.assertTrue(all(x["ok"] for x in out))

    def test_fremder_aufgabentyp_wird_abgelehnt_und_stoppt_die_anderen_nicht(self):
        out = werkzeuge.auftraege_verteilen(self.m, self.tmp, [{"typ": "persoenliche_daten", "text": "x"}, {"typ": "code_und_spec_des_baus", "text": "y"}])
        self.assertFalse(out[0]["ok"]); self.assertIn("Gesetz", out[0]["grund"])
        self.assertTrue(out[1]["ok"])
        self.assertEqual(self.senden.call_count, 1, "der abgelehnte Auftrag erreicht die Cloud nie")

    def test_manager_ohne_das_werkzeug_darf_nicht(self):
        ohne = Manager("untergebener", set(), journal=self.tmp / "j2.jsonl", werkzeuge={"taschenrechner"})
        with self.assertRaises(VerfassungsVerstoss):
            werkzeuge.auftraege_verteilen(ohne, self.tmp, [{"typ": "code_und_spec_des_baus", "text": "x"}])
        self.senden.assert_not_called()

    def test_eingabe_wird_geprueft(self):
        for bad in ([], "text", [{"typ": "code_und_spec_des_baus"}], [{"typ": 1, "text": "x"}], [{"typ": "code_und_spec_des_baus", "text": "x" * 12001}],
                    [{"typ": "code_und_spec_des_baus", "text": "x"}] * (werkzeuge.MAX_AUFTRAEGE + 1)):
            with self.assertRaises(ValueError, msg=str(bad)[:40]):
                werkzeuge.auftraege_verteilen(self.m, self.tmp, bad)
        self.senden.assert_not_called()

    def test_jeder_auftrag_steht_im_journal(self):
        werkzeuge.auftraege_verteilen(self.m, self.tmp, [{"typ": "code_und_spec_des_baus", "text": "x"}])
        zeilen = (self.tmp / "journal.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertTrue(any("werkzeug:auftraege_verteilen" in z for z in zeilen))


if __name__ == "__main__":
    unittest.main()
