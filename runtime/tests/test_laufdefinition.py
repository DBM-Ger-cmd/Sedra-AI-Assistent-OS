import tempfile
import unittest
from pathlib import Path

from guppi_runtime import laufdefinition, vorarbeiter


def _defn(**over):
    d = {"name": "bewerte-xy", "art": "bewerten", "beschreibung": "Bewertung XY", "lab": "xy_lab",
         "provider": "nvidia", "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
         "task": "Lies source/README.md und schreibe out/bewertung.md. Beende mit finish.",
         "allow": ["out"], "outputs": ["out/bewertung.md"]}
    d.update(over)
    return d


class PruefenTest(unittest.TestCase):
    def test_gueltige_definition_wird_bereinigt(self):
        d = laufdefinition.pruefen(_defn())
        self.assertEqual(d["name"], "bewerte-xy")
        self.assertEqual(d["allow"], ["out"])

    def test_unzulaessige_pfade_werden_abgelehnt(self):
        for bad in ["../x", "/etc", "C:\\x", "out/../../x"]:
            with self.subTest(pfad=bad):
                with self.assertRaises(ValueError):
                    laufdefinition.pruefen(_defn(lab=bad))
                with self.assertRaises(ValueError):
                    laufdefinition.pruefen(_defn(allow=[bad]))

    def test_name_und_art(self):
        with self.assertRaises(ValueError): laufdefinition.pruefen(_defn(name="Mit Leerzeichen"))
        with self.assertRaises(ValueError): laufdefinition.pruefen(_defn(art="irgendwas"))

    def test_ausgabe_muss_im_schreibbereich_liegen(self):
        with self.assertRaises(ValueError):
            laufdefinition.pruefen(_defn(allow=["out"], outputs=["src/x.js"]))

    def test_leerer_schreibbereich_und_leerer_auftrag(self):
        with self.assertRaises(ValueError): laufdefinition.pruefen(_defn(allow=[]))
        with self.assertRaises(ValueError): laufdefinition.pruefen(_defn(task="  "))


class SpeichernTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_anlegen_und_laden(self):
        laufdefinition.anlegen(self.root, _defn())
        d = laufdefinition.laden(self.root, "bewerte-xy")
        self.assertEqual(d["model"], "nvidia/nemotron-3.5-super-vl-120b-a12b")
        self.assertEqual([x["name"] for x in laufdefinition.liste(self.root)], ["bewerte-xy"])

    def test_name_wird_nicht_ueberschrieben(self):
        laufdefinition.anlegen(self.root, _defn())
        with self.assertRaises(ValueError) as ctx:
            laufdefinition.anlegen(self.root, _defn())
        self.assertEqual(str(ctx.exception), "name_vergeben")

    def test_unbekannter_lauf(self):
        with self.assertRaises(ValueError) as ctx:
            laufdefinition.laden(self.root, "gibt-es-nicht")
        self.assertEqual(str(ctx.exception), "lauf_unbekannt")

    def test_vorarbeiter_legt_an_und_meldet_fehler(self):
        out = vorarbeiter.aktion(self.root, "lauf_anlegen", _defn())
        self.assertEqual(out["angelegt"], "bewerte-xy")
        with self.assertRaises(ValueError):
            vorarbeiter.aktion(self.root, "lauf_anlegen", _defn(lab="../x"))


class RendernTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "redesign" / "workbench").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_unzulaessige_eingaben(self):
        for ordner, datei in [("drache_lab", "x.scad"), ("workbench", "../x.scad"), ("workbench", "x.js"), ("workbench", "fehlt.scad")]:
            with self.subTest(ordner=ordner, datei=datei):
                with self.assertRaises(ValueError):
                    vorarbeiter.aktion(self.root, "rendern", {"ordner": ordner, "datei": datei})

    def test_rendert_eine_scad_datei_mit_openscad(self):
        import os
        if not vorarbeiter.openscad_exe().is_file():
            self.skipTest("OpenSCAD nicht installiert")
        (self.root / "redesign" / "workbench" / "wuerfel.scad").write_text("cube(10);\n", encoding="utf-8")
        out = vorarbeiter.aktion(self.root, "rendern", {"ordner": "workbench", "datei": "wuerfel.scad"})
        self.assertEqual(out["code"], 0, out["meldung"])
        self.assertTrue((self.root / "redesign" / "workbench" / "wuerfel.stl").exists())


if __name__ == "__main__":
    unittest.main()
