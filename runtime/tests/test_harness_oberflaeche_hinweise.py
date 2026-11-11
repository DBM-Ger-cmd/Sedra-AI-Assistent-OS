"""O3 G3 (SPEC_APPS_v1_O3PLUS_G9_G2 §2.4): Hinweise im Diff. Hinzukommende Zeilen mit Mustern aus `desk/install.py` bekommen `⚠ <Hinweis>`; gilt für die Sammelkarte (G2) und die G4-Karte;
die Karte sagt, dass Hinweise nur eine Lesehilfe sind."""
import os
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import install
from sedra_runtime.harness.code_stand import CodeStand
from sedra_runtime.harness.oberflaeche import Oberflaeche


class Hinweise(unittest.TestCase):
    def test_hinzukommende_zeilen_mit_mustern_werden_markiert_andere_nicht(self):
        aus = install.hinweise_im_diff(["--- a", "+++ b", "+eval(x)", "+let a = 1;", " fetch(y)", "-fetch(z)", "+fetch('/api/x')"])
        self.assertEqual(aus[0:2], ["--- a", "+++ b"], "Kopfzeilen nie")
        self.assertIn("⚠ baut Code zur Laufzeit zusammen", aus[2])
        self.assertEqual(aus[3], "+let a = 1;")
        self.assertEqual(aus[4:6], [" fetch(y)", "-fetch(z)"], "Kontext und entfernte Zeilen bleiben unmarkiert")
        self.assertIn("⚠ geht an der Allowlist vorbei ins Netz", aus[6])

    def test_freigabe_wege_werden_erkannt(self):
        for text, wort in (("post('/api/decisions/answer')", "decisions/answer"), ("x('/api/mission/approve')", "mission/approve"), ("'/api/harness/karten/K-1'", "harness/karten"),
                           ("'/api/harness/aufgaben'", "harness/aufgaben"), ("'/api/harness/vorarbeiter/x'", "harness/vorarbeiter"), ("{erlaubnisse_bestaetigt: true}", "Sitzungs-Erlaubnis"),
                           ("api('/api/uix/install')", "Einbau von Modulen"), ("api('/api/uix/trust')", "Schreibrechte"), ("  trust: CORE", "Schreibrechte")):
            with self.subTest(text=text):
                self.assertTrue(any(wort in h for h in install.hinweis_fuer_zeile(text)), install.hinweis_fuer_zeile(text))

    def test_harmloser_text_hat_keinen_hinweis(self):
        self.assertEqual(install.hinweis_fuer_zeile("const farbe = 'rot'; // trustworthy ist kein Muster"), [])

    def test_satz_ueber_die_grenzen_der_hinweise(self):
        self.assertEqual(install.HINWEIS_SATZ, "Hinweise sind eine Lesehilfe. Sie finden nicht alles, und ein Treffer ist kein Beweis.")


class Sammelkarte(unittest.TestCase):
    def test_vorschau_der_sammelkarte_traegt_hinweise_und_satz(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            uix = t / "uix"
            (uix / "tools").mkdir(parents=True)
            datei = uix / "tools" / "a.js"
            datei.write_bytes(b"alt\n")
            o = Oberflaeche(t / "ablage", uix)
            o.zurueckhalten(datei)
            datei.write_bytes(b"alt\nfetch('/api/harness/karten')\n")
            text, _zu_gross = o.vorschau()
        self.assertIn(install.HINWEIS_SATZ, text)
        self.assertIn("+fetch('/api/harness/karten')  ⚠", text)
        self.assertIn("harness/karten", text)


class G4Karte(unittest.TestCase):
    def test_vorschau_des_code_stands_traegt_hinweise_und_satz(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            wurzel = t / "projekt"
            wurzel.mkdir()
            (wurzel / "bestand.js").write_bytes(b"alt\n")
            cs = CodeStand(t / "ablage", wurzel, "p")
            self.assertEqual(cs.ungesehen(), [])                  # beim ersten Gebrauch gilt der vorhandene Stand als gesehen
            (wurzel / "neu.js").write_bytes(b"eval('x')\nconst a = 1;\n")
            liste = cs.ungesehen()
            text, _zu_gross = cs.vorschau(liste)
        self.assertIn(install.HINWEIS_SATZ, text)
        self.assertIn("+eval('x')  ⚠ baut Code zur Laufzeit zusammen", text)
        self.assertIn("+const a = 1;", text)
        self.assertNotIn("+const a = 1;  ⚠", text)


if __name__ == "__main__":
    unittest.main()
