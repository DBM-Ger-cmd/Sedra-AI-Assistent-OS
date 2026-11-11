"""Konsens ueber mehrere Kandidaten (benchmarks/konsens.py): Mehrheit je Fall, Streitfaelle, Gleichstand, Abdruck gegen die Referenz."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
import konsens  # noqa: E402

REF = RUNTIME / "benchmarks" / "devvm_refs" / "am0_gate_texte" / "gate_texte.py"


def ab(*werte):
    return {("f", i): ("ok", w) for i, w in enumerate(werte)}


class Waehlen(unittest.TestCase):
    def test_die_mehrheit_entscheidet_je_fall(self):
        erg = konsens.waehle([ab("a", "b", "c"), ab("a", "b", "X"), ab("a", "Y", "X")])
        # Fall 0 einstimmig; Fall 1 Mehrheit "b" (Kandidat 3 weicht ab); Fall 2 Mehrheit "X" (Kandidat 1 weicht ab)
        self.assertEqual(erg["abweichungen"], [1, 0, 1])
        self.assertEqual(erg["gewaehlt"], 1)

    def test_zwei_gegen_einen(self):
        erg = konsens.waehle([ab("a", "b"), ab("a", "z"), ab("a", "b")])
        self.assertEqual(erg["abweichungen"], [0, 1, 0])
        self.assertEqual(erg["gewaehlt"], 0)
        self.assertTrue(erg["gleichstand"])        # 0 und 2 gleich gut, der fruehste gilt
        self.assertEqual((erg["einstimmig"], erg["faelle"]), (1, 2))

    def test_gleichstand_zwischen_zwei_kandidaten_ist_ein_streitfall(self):
        erg = konsens.waehle([ab("a", "b"), ab("a", "z")])
        self.assertEqual(erg["abweichungen"], [0, 0])
        self.assertEqual(len(erg["streitfaelle"]), 1)
        self.assertEqual(erg["streitfaelle"][0][0], ("f", 1))

    def test_alle_verschieden_ist_streit_und_zaehlt_nicht(self):
        erg = konsens.waehle([ab("a"), ab("b"), ab("c")])
        self.assertEqual(erg["abweichungen"], [0, 0, 0])
        self.assertEqual(len(erg["streitfaelle"]), 1)

    def test_einstimmig(self):
        erg = konsens.waehle([ab("a", "b")] * 3)
        self.assertEqual((erg["einstimmig"], erg["streitfaelle"], erg["gewaehlt"]), (2, [], 0))

    def test_ausnahmen_und_mutation_sind_verhalten(self):
        r = {("f", 0): ("ok", "a")}
        e = {("f", 0): ("fehler", "ValueError:x")}
        m = {("f", 0): ("MUTIERT", None)}
        erg = konsens.waehle([r, r, e, m, r])
        self.assertEqual(erg["abweichungen"], [0, 0, 1, 1, 0])

    def test_ohne_kandidaten(self):
        with self.assertRaises(ValueError):
            konsens.waehle([])


def bf(datei, zeile, art="isdigit", text="x"):
    return {"datei": datei, "zeile": zeile, "art": art, "text": text}


class Befunde(unittest.TestCase):
    def test_nur_was_mehrere_laeufe_nennen_ist_bestaetigt(self):
        erg = konsens.befunde([[bf("a.py", 10), bf("a.py", 50)], [bf("a.py", 11)], [bf("b.py", 5)]])
        self.assertEqual([e["befund"]["zeile"] for e in erg["bestaetigt"]], [10])
        self.assertEqual(erg["bestaetigt"][0]["laeufe"], [0, 1])
        self.assertEqual(sorted((e["befund"]["datei"], e["befund"]["zeile"]) for e in erg["unsicher"]), [("a.py", 50), ("b.py", 5)])

    def test_gleicher_lauf_zaehlt_nur_einmal(self):
        erg = konsens.befunde([[bf("a.py", 10), bf("a.py", 11)], []])
        self.assertEqual(erg["bestaetigt"], [])
        self.assertEqual(len(erg["unsicher"]), 2)

    def test_art_und_datei_muessen_passen_und_der_abstand_ist_begrenzt(self):
        erg = konsens.befunde([[bf("a.py", 10, "isdigit")], [bf("a.py", 10, "None")], [bf("a.py", 14, "isdigit")], [bf("c.py", 10, "isdigit")]])
        self.assertEqual(erg["bestaetigt"], [])
        erg = konsens.befunde([[bf("a.py", 10)], [bf("a.py", 13)]])
        self.assertEqual(len(erg["bestaetigt"]), 1)

    def test_ohne_zeile_und_schiefe_eintraege(self):
        erg = konsens.befunde([[bf("a.py", None)], [bf("a.py", None)], [bf("a.py", 4)], [None, "x", 5, bf("a.py", None)]])
        self.assertEqual(erg["bestaetigt"][0]["laeufe"], [0, 1, 3])
        self.assertEqual(len(erg["unsicher"]), 1)

    def test_mindest_und_keine_laeufe(self):
        self.assertEqual(konsens.befunde([]), {"bestaetigt": [], "unsicher": []})
        erg = konsens.befunde([[bf("a.py", 1)], [bf("a.py", 1)], [bf("a.py", 1)]], mindest=3)
        self.assertEqual(erg["bestaetigt"][0]["anzahl"], 3)
        with self.assertRaises(ValueError):
            konsens.befunde([], mindest=0)


def ok(wert):
    return ("ok", json.dumps(wert))


class Vorschlaege(unittest.TestCase):
    REF = {("f", 0): ok(["a", "b"]), ("f", 1): ok(["a"]), ("f", 2): ok("x")}

    def test_gemeinsamer_fehler_wird_zusammengefasst_und_einzelfehler_nicht(self):
        gleich = {("f", 0): ok(["a"]), ("f", 1): ok(["a"]), ("f", 2): ok("x")}
        k1, k2 = dict(gleich), dict(gleich)
        einzel = {("f", 0): ok(["a", "b"]), ("f", 1): ok(["a"]), ("f", 2): ok("falsch")}
        erg = konsens.fehlermuster([k1, k2, einzel], self.REF)
        self.assertEqual(len(erg), 1)
        self.assertEqual((erg[0]["kandidaten"], erg[0]["von"], erg[0]["faelle"]), (2, 3, 1))
        self.assertIn("es fehlt b", erg[0]["muster"])
        self.assertTrue(erg[0]["loesung"].startswith("offen"))
        self.assertEqual(len(erg[0]["orte"]), 3)

    def test_ausnahmen_gleichen_typs_gehoeren_zusammen_egal_welcher_typname(self):
        a = {("f", 0): ("fehler", "AttributeError:'int' object has no attribute 'lower'"), ("f", 1): self.REF[("f", 1)], ("f", 2): self.REF[("f", 2)]}
        b = {("f", 0): ("fehler", "AttributeError:'NoneType' object has no attribute 'lower'"), ("f", 1): self.REF[("f", 1)], ("f", 2): self.REF[("f", 2)]}
        erg = konsens.fehlermuster([a, b], self.REF)
        self.assertEqual(len(erg), 1)
        self.assertIn("wirft eine Ausnahme", erg[0]["muster"])
        self.assertEqual(erg[0]["kandidaten"], 2)

    def test_keine_abweichung_kein_vorschlag_und_mutation_ist_eine_art(self):
        self.assertEqual(konsens.fehlermuster([dict(self.REF), dict(self.REF)], self.REF), [])
        m = {**self.REF, ("f", 2): ("MUTIERT", None)}
        erg = konsens.fehlermuster([m, m], self.REF)
        self.assertIn("veraendert seine Eingabe", erg[0]["muster"])

    def test_streitfaelle_je_funktion(self):
        erg = konsens.waehle([ab("a", "b"), ab("a", "z")])
        v = konsens.streit_vorschlaege(erg)
        self.assertEqual((v[0]["muster"], v[0]["faelle"]), ("Streit f", 1))
        self.assertTrue(v[0]["loesung"].startswith("offen"))


class AbdruckAusKandidaten(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _kandidat(self, name, aendern=None):
        ordner = self.tmp / name
        ordner.mkdir()
        shutil.copy(REF, ordner / "gate_texte.py")
        if aendern:
            p = ordner / "gate_texte.py"
            p.write_text(aendern(p.read_text(encoding="utf-8")), encoding="utf-8")
        return ordner

    def test_wahl_unter_drei_kandidaten_mit_einem_fehler(self):
        gut1, gut2 = self._kandidat("a"), self._kandidat("b")
        schlecht = self._kandidat("c", lambda t: t.replace("r.startswith('GET ')", "r.upper().startswith('GET ')"))
        abd = [konsens.abdruck("am0_gate_texte", k) for k in (schlecht, gut1, gut2)]
        erg = konsens.waehle(abd)
        self.assertIn(erg["gewaehlt"], (1, 2))
        self.assertGreater(erg["abweichungen"][0], 0)
        self.assertEqual(erg["abweichungen"][1:], [0, 0])

    def test_keine_pool_datei_und_fehlende_moduldatei(self):
        self.assertIsNone(konsens.abdruck("gibt_es_nicht", self.tmp))
        self.assertIsNone(konsens.abdruck("am0_gate_texte", self.tmp))


if __name__ == "__main__":
    unittest.main()
