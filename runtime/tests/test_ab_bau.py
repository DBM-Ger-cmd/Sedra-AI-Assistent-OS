"""A/B-Werkzeug fuer Bau-Vergleiche (benchmarks/ab_bau.py) und der Standard der Arbeitsanweisung in der Bau-Schleife."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
import ab_bau  # noqa: E402
from sedra_runtime.manager import VerfassungsVerstoss, lade_arbeitsanweisung_fuer_modell  # noqa: E402

REF = RUNTIME / "benchmarks" / "devvm_refs" / "am3_rechte_diff" / "rechte_diff.py"

LOG = """   work instruction bau_coder (de): 1464 characters appended to every task
   agent solo developer         qwen3.6-35b-a3b        hand_in      5 calls   20.1 s 835 tokens, 15649 prompt, peak 3707
   agent solo developer (rework 1) qwen3.6-35b-a3b        hand_in      4 calls   20.4 s 980 tokens, 18570 prompt, peak 5373
   stage S1: hidden PASSED (own check accepted=UNJUDGED, own tests none, 62.0 s)
   stage S2: hidden FAILED (x)
# run ended
"""


class Arme(unittest.TestCase):
    def test_gueltige_arme(self):
        self.assertEqual(ab_bau.arme_lesen("ohne,bau_coder:de"), ["ohne", "bau_coder:de"])
        self.assertEqual(ab_bau.arme_lesen("bau_coder:de, bau_coder:en"), ["bau_coder:de", "bau_coder:en"])

    def test_ungueltige_arme(self):
        for bad in ("ohne", "ohne,ohne", "ohne,Bau", "ohne,../x", "ohne,bau:fr", "ohne,"):
            with self.assertRaises(SystemExit, msg=bad):
                ab_bau.arme_lesen(bad)

    def test_befehl_je_arm(self):
        p = Path("proj")
        ohne = ab_bau.befehl_fuer(p, "s", "ohne", "x.pid", "standard", None, None)
        self.assertNotIn("--arbeitsanweisung", ohne)
        self.assertIn("--no-logbook", ohne)
        en = ab_bau.befehl_fuer(p, "s", "bau_coder:en", "x.pid", "standard", "coder.x", 81920)
        self.assertEqual(en[en.index("--arbeitsanweisung") + 1], "bau_coder")
        self.assertEqual(en[en.index("--anweisung-sprache") + 1], "en")
        self.assertEqual(en[en.index("--context") + 1], "81920")
        self.assertEqual(ab_bau.befehl_fuer(p, "s", "bau_coder", "x.pid", "standard", None, None)[-1], "auto")


class Kennzahlen(unittest.TestCase):
    def test_zahlen_aus_dem_log(self):
        k = ab_bau.kennzahlen(LOG)
        self.assertEqual((k["stufen_ok"], k["stufen_gesamt"], k["aufrufe"], k["nacharbeiten"], k["tokens_prompt"], k["anweisung"]), (1, 2, 9, 1, 34219, "de"))

    def test_ohne_anweisung(self):
        self.assertIsNone(ab_bau.kennzahlen("stage S1: hidden PASSED (x)\n")["anweisung"])

    def test_bericht_warnt_bei_wenigen_laeufen_und_zeigt_die_arme(self):
        r = [{"lauf": "1_ohne", "arm": "ohne", "sekunden": 100, "kandidat": "k", "bestanden": True, "aufrufe": 30, "nacharbeiten": 3, "tokens_prompt": 1000, "diff": {"faelle": 5, "abweichungen": ["a"]}},
             {"lauf": "1_x", "arm": "x", "sekunden": 90, "kandidat": "k2", "bestanden": True, "aufrufe": 31, "nacharbeiten": 2, "tokens_prompt": 1200, "diff": {"faelle": 5, "abweichungen": []}}]
        t = ab_bau.bericht("spec", ["ohne", "x"], r, 1)
        self.assertIn("kein Beweis", t)
        self.assertIn("| ohne | 1 | 1/1 |", t)
        self.assertIn("| x | 1 | 1/1 |", t)
        self.assertIn("| 1.0 | 0/1 |", t)        # Arm ohne: eine Abweichung je Lauf, kein Lauf ohne Abweichung


class Differenztest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _kandidat(self, aendern=None):
        shutil.copy(REF, self.tmp / "rechte_diff.py")
        if aendern:
            p = self.tmp / "rechte_diff.py"
            p.write_text(aendern(p.read_text(encoding="utf-8")), encoding="utf-8")
        return self.tmp

    def test_die_referenz_selbst_hat_keine_abweichung(self):
        d = ab_bau.differenz("am3_rechte_diff", self._kandidat())
        self.assertGreater(d["faelle"], 150)
        self.assertEqual(d["abweichungen"], [])

    def test_ein_fehler_im_kandidaten_wird_gefunden(self):
        d = ab_bau.differenz("am3_rechte_diff", self._kandidat(lambda t: t + "\n_orig = stufe\ndef stufe(f):\n    return 'A'\n"))
        self.assertTrue(d["abweichungen"])

    def test_fehlende_datei_und_spec_ohne_faelle(self):
        self.assertEqual(ab_bau.differenz("am3_rechte_diff", self.tmp)["abweichungen"], ["Kandidat hat rechte_diff.py nicht"])
        self.assertIsNone(ab_bau.differenz("gibt_es_nicht", self.tmp))


class VorpruefungUndSprache(unittest.TestCase):
    def test_unbekannte_spec_verbietet(self):
        self.assertTrue(ab_bau.vorpruefung(Path(tempfile.mkdtemp()), "gibt_es_nicht"))

    def test_belegte_gpu_verbietet(self):
        class R:
            returncode = 0
            stdout = "ok"
        with mock.patch.object(ab_bau.subprocess, "run") as run:
            def fake(cmd, **kw):
                r = R()
                if "nvidia-smi" in cmd[0]:
                    r.stdout = "9000\n"
                if cmd[0] == "tasklist":
                    r.stdout = "INFORMATION: keine"
                return r
            run.side_effect = fake
            p = ab_bau.vorpruefung(Path(tempfile.mkdtemp()), "am3_rechte_diff")
        self.assertTrue(any("GPU belegt" in x for x in p), p)

    def _config_ohne_englisch(self):
        from sedra_runtime.manager import verfassung
        tmp = Path(tempfile.mkdtemp()) / "manager"
        shutil.copytree(verfassung.CONFIG, tmp)
        for alt in (tmp / "arbeitsanweisungen").glob("*.en.md"):
            alt.unlink()
        return mock.patch.object(verfassung, "CONFIG", tmp)

    def test_sprache_en_bricht_ohne_gueltige_fassung_ab_und_de_bleibt_deutsch(self):
        with self._config_ohne_englisch():
            with self.assertRaises(VerfassungsVerstoss):
                lade_arbeitsanweisung_fuer_modell("bau_coder", sprache="en")
            self.assertEqual(lade_arbeitsanweisung_fuer_modell("bau_coder", sprache="de")[1], "de")
            self.assertEqual(lade_arbeitsanweisung_fuer_modell("bau_coder")[1], "de")
            with self.assertRaises(VerfassungsVerstoss):
                lade_arbeitsanweisung_fuer_modell("bau_coder", sprache="fr")

    def test_die_ausgelieferte_englische_fassung_ist_frisch_und_gilt(self):
        """Ein freigegebenes bau_coder.en.md im Repo muss zur deutschen Quelle passen: wer bau_coder.md aendert, erzeugt und gibt die englische Fassung neu frei."""
        from sedra_runtime.manager import verfassung
        if not (Path(verfassung.CONFIG) / "arbeitsanweisungen" / "bau_coder.en.md").is_file():
            self.skipTest("keine englische Fassung ausgeliefert")
        a, sprache, gruende = lade_arbeitsanweisung_fuer_modell("bau_coder", sprache="en")
        self.assertEqual((sprache, gruende), ("en", []))
        self.assertIn("credentials or API keys", a["text"])
        self.assertIn("compiles as Python code", a["text"])


class SchleifeStandard(unittest.TestCase):
    def test_arbeitsanweisung_ist_in_der_schleife_standardmaessig_aus(self):
        import bau_schleife
        self.assertIsNone(bau_schleife.ARBEITSANWEISUNG)
        quelle = (RUNTIME / "benchmarks" / "bau_schleife.py").read_text(encoding="utf-8")
        self.assertIn("if ARBEITSANWEISUNG:", quelle)
        self.assertIn('"--arbeitsanweisung" in argv', quelle)

    def test_befehl_der_schleife_traegt_die_anweisung_nur_wenn_gewaehlt(self):
        import bau_schleife
        gesehen = []
        with mock.patch.object(bau_schleife.subprocess, "run", side_effect=lambda b, **k: gesehen.append(b) or mock.Mock(returncode=0)):
            proj = Path(tempfile.mkdtemp())
            (proj / "runtime_data").mkdir()
            bau_schleife.bau_versuch(proj, "S1", None, None, {"name": "x", "coder": "c", "args": []})
            self.assertNotIn("--arbeitsanweisung", gesehen[-1])
            with mock.patch.object(bau_schleife, "ARBEITSANWEISUNG", "bau_coder"):
                bau_schleife.bau_versuch(proj, "S1", None, None, {"name": "x", "coder": "c", "args": []})
            self.assertIn("--arbeitsanweisung", gesehen[-1])


if __name__ == "__main__":
    unittest.main()
