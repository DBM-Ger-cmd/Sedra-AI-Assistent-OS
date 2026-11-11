"""O3 G2/G7 (SPEC_APPS_v1_O3PLUS_G9_G2): der Baustein `harness/oberflaeche.py` – zurückhalten, ausliefern, übernehmen, zurücksetzen, zurücknehmen. Dateien in einem Wegwerf-Ordner."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness.oberflaeche import INHALT_MAX, Oberflaeche, sha


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="o3-oberflaeche-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.uix = t / "programm" / "uix"
        (self.uix / "shells" / "harness").mkdir(parents=True)
        self.ablage = t / "projekt" / "runtime_data" / "harness" / "oberflaeche"
        self.audit = []
        self.o = Oberflaeche(self.ablage, self.uix, audit=lambda e, p: self.audit.append((e, p)))
        self.datei = self.uix / "shells" / "harness" / "app.js"
        self.datei.write_bytes(("alt\n").encode("utf-8"))

    def schreibe(self, text, datei=None):
        (datei or self.datei).write_bytes((text).encode("utf-8"))


class Zurueckhalten(Basis):
    def test_erste_aenderung_merkt_die_bestaetigte_fassung_weitere_aendern_sie_nicht(self):
        self.assertTrue(self.o.zurueckhalten(self.datei, "S-1", "T-1"))
        self.schreibe("neu eins\n")
        self.assertTrue(self.o.zurueckhalten(self.datei, "S-2", "T-1"))
        self.schreibe("neu zwei\n")
        e = self.o.stand()["dateien"]["shells/harness/app.js"]
        self.assertEqual((e["bestaetigt_sha"], e["sitzung"]), (sha(b"alt\n"), "S-1"))
        self.assertEqual(self.o.gehalten(self.datei), (True, b"alt\n"))

    def test_nur_unter_dem_uix_ordner_des_laufenden_programms(self):
        fremd = Path(self.tmp.name) / "anderes_projekt" / "uix" / "x.js"
        fremd.parent.mkdir(parents=True)
        fremd.write_bytes(("x").encode("utf-8"))
        self.assertFalse(self.o.zurueckhalten(fremd))
        self.assertEqual(self.o.gehalten(fremd), (False, None))
        self.assertIsNone(self.o.rel(self.uix.parent / "ausserhalb.js"))
        self.assertIsNone(self.o.rel(self.uix / ".." / "x"))

    def test_neue_datei_wird_geliefert_als_gab_es_nicht(self):
        neu = self.uix / "tools" / "neu" / "tool.js"
        self.assertTrue(self.o.zurueckhalten(neu))
        neu.parent.mkdir(parents=True)
        neu.write_bytes(("neu").encode("utf-8"))
        self.assertEqual(self.o.gehalten(neu), (True, None), "None = 404")

    def test_nicht_zurueckgehaltene_datei_kommt_von_der_platte(self):
        self.assertEqual(self.o.gehalten(self.datei), (False, None))

    def test_zu_grosse_datei_wird_nicht_zurueckgehalten_sondern_gemeldet(self):
        self.datei.write_bytes(b"x" * (INHALT_MAX + 1))
        self.assertIsNone(self.o.zurueckhalten(self.datei), "die Schreibaktion wird zur Karte")
        self.assertEqual(self.o.stand()["dateien"], {})

    def test_stand_ist_atomar_und_lesbar(self):
        self.o.zurueckhalten(self.datei)
        d = json.loads((self.ablage / "stand.json").read_text(encoding="utf-8"))
        self.assertEqual(d["schema"], 1)
        self.assertTrue((self.ablage / "inhalt" / sha(b"alt\n")).is_file())
        (self.ablage / "stand.json").write_bytes(("kaputt").encode("utf-8"))
        self.assertEqual(self.o.stand()["dateien"], {}, "ein kaputter Stand gilt als leer, nie als Absturz")


class Uebernehmen(Basis):
    def halten_und_aendern(self, text="neu\n"):
        self.o.zurueckhalten(self.datei, "S-1", "T-1")
        self.schreibe(text)

    def test_liste_und_bindung(self):
        self.halten_und_aendern()
        [e] = self.o.liste()
        self.assertEqual((e["rel"], e["neu"], e["geaendert"], e["sha_jetzt"]), ("shells/harness/app.js", False, True, sha(b"neu\n")))
        self.assertEqual(self.o.bindung(), [["shells/harness/app.js", sha(b"neu\n")]])

    def test_vorschau_zeigt_den_diff_bestaetigt_nach_jetzt_und_laesst_hinweise_zu(self):
        self.halten_und_aendern("neu\nfetch(x)\n")
        text, zu_gross = self.o.vorschau(hinweise=lambda zeilen: [z + "  ⚠ fetch" if z.startswith("+") and "fetch" in z else z for z in zeilen])
        self.assertFalse(zu_gross)
        self.assertIn("-alt", text)
        self.assertIn("+neu", text)
        self.assertIn("+fetch(x)  ⚠ fetch", text)
        self.assertIn("bestätigt/shells/harness/app.js", text)

    def test_vorschau_grenzen(self):
        for i in range(31):
            d = self.uix / "shells" / "harness" / f"f{i}.js"
            d.write_bytes(("a\n").encode("utf-8"))
            self.o.zurueckhalten(d)
            d.write_bytes(("b\n").encode("utf-8"))
        _text, zu_gross = self.o.vorschau()
        self.assertTrue(zu_gross, "mehr als 30 Dateien nur über die Konsole")

    def test_uebernehmen_beendet_das_zurueckhalten_und_schreibt_den_satz(self):
        self.halten_und_aendern()
        gesehen = []
        r = self.o.uebernehmen(self.o.bindung(), kanal="seite", gesehen=gesehen.extend)
        self.assertEqual((r["uebernommen"], r["veraltet"]), (["shells/harness/app.js"], []))
        self.assertEqual(gesehen, ["shells/harness/app.js"])
        self.assertEqual(self.o.stand()["dateien"], {})
        self.assertEqual(self.o.gehalten(self.datei), (False, None), "jetzt liefert der Server die Platte")
        [u] = self.o.uebernahmen()
        self.assertEqual((u["id"], u["kanal"], u["dateien"][0]["alt_sha"], u["dateien"][0]["neu_sha"]), (r["u"], "seite", sha(b"alt\n"), sha(b"neu\n")))
        self.assertIn("HARNESS_OBERFLAECHE_UEBERNOMMEN", [e for e, _p in self.audit])

    def test_geaenderte_datei_nach_der_karte_ist_veraltet_und_bleibt_zurueckgehalten(self):
        self.halten_und_aendern()
        bindung = self.o.bindung()
        self.schreibe("noch ganz anders\n")
        r = self.o.uebernehmen(bindung)
        self.assertEqual((r["uebernommen"], r["veraltet"], r["u"]), ([], ["shells/harness/app.js"], None))
        self.assertIn("shells/harness/app.js", self.o.stand()["dateien"])

    def test_zuruecksetzen_stellt_her_und_verschiebt_neue_dateien_statt_sie_zu_loeschen(self):
        self.halten_und_aendern()
        neu = self.uix / "tools" / "neu" / "tool.js"
        self.o.zurueckhalten(neu)
        neu.parent.mkdir(parents=True)
        neu.write_bytes(("neu").encode("utf-8"))
        r = self.o.zuruecksetzen()
        self.assertEqual((r["hergestellt"], r["verworfen"], r["fehlt"]), (["shells/harness/app.js"], ["tools/neu/tool.js"], []))
        self.assertEqual(self.datei.read_text(encoding="utf-8"), "alt\n")
        self.assertFalse(neu.exists())
        verworfen = list((self.ablage / "verworfen").rglob("tool.js"))
        self.assertEqual(len(verworfen), 1)
        self.assertEqual(verworfen[0].read_text(encoding="utf-8"), "neu", "gelöscht wird nichts")
        self.assertEqual(self.o.stand()["dateien"], {})

    def test_zuruecksetzen_ohne_gemerkten_inhalt_meldet_fehlt_und_laesst_die_datei(self):
        self.halten_und_aendern()
        (self.ablage / "inhalt" / sha(b"alt\n")).unlink()
        r = self.o.zuruecksetzen()
        self.assertEqual(r["fehlt"], ["shells/harness/app.js"])
        self.assertEqual(self.datei.read_text(encoding="utf-8"), "neu\n")
        self.assertIn("shells/harness/app.js", self.o.stand()["dateien"], "bleibt zurückgehalten, nichts geht verloren")


class Zuruecknehmen(Basis):
    def uebernommen(self, text="neu\n"):
        self.o.zurueckhalten(self.datei, "S-1")
        self.schreibe(text)
        return self.o.uebernehmen(self.o.bindung())["u"]

    def test_stellt_die_alte_fassung_her_wenn_die_datei_noch_die_uebernommene_ist(self):
        u = self.uebernommen()
        gesehen = []
        r = self.o.zuruecknehmen(u, kanal="konsole", gesehen=gesehen.extend)
        self.assertEqual((r["hergestellt"], r["geaendert"]), (["shells/harness/app.js"], []))
        self.assertEqual(self.datei.read_text(encoding="utf-8"), "alt\n")
        self.assertEqual(gesehen, ["shells/harness/app.js"])
        self.assertEqual(self.o.uebernahmen(), [], "die Übernahme ist verbraucht")
        self.assertIn(("HARNESS_OBERFLAECHE_ZURUECK", {"u": u, "dateien": 1, "geaendert": 0, "kanal": "konsole"}), self.audit)

    def test_hat_sich_die_datei_seither_geaendert_bleibt_sie_und_wird_genannt(self):
        u = self.uebernommen()
        self.schreibe("spaeter geaendert\n")
        r = self.o.zuruecknehmen(u)
        self.assertEqual((r["hergestellt"], r["geaendert"]), ([], ["shells/harness/app.js"]))
        self.assertEqual(self.datei.read_text(encoding="utf-8"), "spaeter geaendert\n")

    def test_neue_datei_wandert_nach_verworfen(self):
        neu = self.uix / "tools" / "neu" / "tool.js"
        self.o.zurueckhalten(neu)
        neu.parent.mkdir(parents=True)
        neu.write_bytes(("neu").encode("utf-8"))
        u = self.o.uebernehmen(self.o.bindung())["u"]
        r = self.o.zuruecknehmen(u)
        self.assertEqual(r["verworfen"], ["tools/neu/tool.js"])
        self.assertFalse(neu.exists())
        self.assertTrue(list((self.ablage / "verworfen").rglob("tool.js")))

    def test_unbekannte_uebernahme(self):
        with self.assertRaises(ValueError):
            self.o.zuruecknehmen("U-gibt-es-nicht")

    def test_es_bleiben_hoechstens_zwanzig_uebernahmen(self):
        for i in range(22):
            self.o.zurueckhalten(self.datei)
            self.schreibe(f"v{i}\n")
            self.o.uebernehmen(self.o.bindung())
        self.assertEqual(len(self.o.stand()["uebernahmen"]), 20)


if __name__ == "__main__":
    unittest.main()
