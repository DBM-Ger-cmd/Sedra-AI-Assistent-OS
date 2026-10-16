import json
import shutil
import tempfile
import unittest
from pathlib import Path

from guppi_runtime import auftrag, laufdefinition, vorarbeiter

BEISPIEL = Path(__file__).resolve().parents[2] / "docs" / "auftrag_beispiel"


def _manifest(**over):
    m = json.loads((BEISPIEL / "auftrag.json").read_text(encoding="utf-8"))
    m.update(over)
    return m


class ManifestTest(unittest.TestCase):
    def test_beispiel_ist_gueltig(self):
        m = auftrag.manifest_pruefen(json.loads((BEISPIEL / "auftrag.json").read_text(encoding="utf-8")))
        self.assertEqual(m["name"], "bewerte-beispiel")
        self.assertEqual(m["schreibbereich"], ["out"])

    def test_format_und_version(self):
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(format="anderes"))
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(version=2))

    def test_pflichtfeld_fehlt(self):
        m = _manifest()
        del m["ausgaben"]
        with self.assertRaises(ValueError) as ctx:
            auftrag.manifest_pruefen(m)
        self.assertEqual(str(ctx.exception), "pflichtfeld_fehlt:ausgaben")

    def test_pfade_nur_relativ(self):
        for bad in ["../x", "/etc", "C:\\x", "out/../../x"]:
            with self.subTest(pfad=bad):
                with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(eingaben=[bad]))
                with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(lab=bad))
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(spezifikation="../spez.md"))
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(spezifikation="spez.txt"))

    def test_ausgabe_muss_im_schreibbereich_liegen(self):
        with self.assertRaises(ValueError):
            auftrag.manifest_pruefen(_manifest(ausgaben=["quelle/x.md"]))

    def test_pruefregeln_aus_fester_liste(self):
        with self.assertRaises(ValueError) as ctx:
            auftrag.manifest_pruefen(_manifest(pruefregeln=["schreibbereich", "ausgaben_vollstaendig", "frei_erfunden"]))
        self.assertTrue(str(ctx.exception).startswith("pruefregel_unbekannt"))
        with self.assertRaises(ValueError) as ctx:
            auftrag.manifest_pruefen(_manifest(pruefregeln=["ausgaben_vollstaendig"]))
        self.assertEqual(str(ctx.exception), "pruefregel_pflicht_fehlt")

    def test_abbruchregeln_nicht_ueber_obergrenze(self):
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(abbruchregeln={"max_schritte": 41}))
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(abbruchregeln={"max_wiederholungen": 3}))
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(abbruchregeln={"schritt_timeout_s": 0}))
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(abbruchregeln={"unbekannt": 1}))

    def test_modell_und_name_gelten_wie_bei_laeufen(self):
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(_manifest(name="Mit Leerzeichen"))
        m = _manifest()
        m["modell"] = {"provider": "nvidia", "model": "x"}
        with self.assertRaises(ValueError): auftrag.manifest_pruefen(m)


class OrdnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ordner = Path(self.tmp.name) / "auftrag"
        shutil.copytree(BEISPIEL, self.ordner)

    def tearDown(self):
        self.tmp.cleanup()

    def test_laden_und_als_laufdefinition(self):
        manifest, text = auftrag.laden(self.ordner)
        self.assertIn("Lies die Datei quelle/README.md", text)
        d = auftrag.als_laufdefinition(self.ordner)
        self.assertIn("Eingaben (nur lesen): quelle/README.md", d["task"])
        self.assertEqual(d["allow"], ["out"])
        laufdefinition.pruefen(d)   # die Definition ist für den Lauf gültig

    def test_spezifikation_fehlt_oder_ist_zu_lang(self):
        (self.ordner / "spezifikation.md").unlink()
        with self.assertRaises(ValueError) as ctx:
            auftrag.laden(self.ordner)
        self.assertEqual(str(ctx.exception), "spezifikation_fehlt")
        (self.ordner / "spezifikation.md").write_text("x" * 4001, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            auftrag.laden(self.ordner)
        self.assertEqual(str(ctx.exception), "auftrag_zu_lang")

    def test_anlegen_ueber_vorarbeiter(self):
        root = Path(self.tmp.name) / "werkstatt"
        out = vorarbeiter.aktion(root, "lauf_anlegen", auftrag.als_laufdefinition(self.ordner))
        self.assertEqual(out["angelegt"], "bewerte-beispiel")
        self.assertEqual(laufdefinition.laden(root, "bewerte-beispiel")["model"], "nvidia/nemotron-3.5-super-vl-120b-a12b")


class PortabilitaetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ordner = Path(self.tmp.name) / "auftrag"
        shutil.copytree(BEISPIEL, self.ordner)

    def tearDown(self):
        self.tmp.cleanup()

    def test_beispiel_ist_portabel(self):
        self.assertEqual(auftrag.portabel_pruefen(self.ordner), [])

    def test_maschinenpfad_wird_gefunden_platzhalter_nicht(self):
        spez = self.ordner / "spezifikation.md"
        spez.write_text(spez.read_text(encoding="utf-8") + "\nSiehe C:\\Users\\David\\notizen.txt\n", encoding="utf-8")
        (self.ordner / "auftrag.json").write_text(
            (self.ordner / "auftrag.json").read_text(encoding="utf-8").replace('"nvidia/', '"<modelle>/'), encoding="utf-8")
        fund = auftrag.portabel_pruefen(self.ordner)
        self.assertEqual([f["datei"] for f in fund], ["spezifikation.md"])   # Platzhalter im Manifest bleibt unbeanstandet

    def test_paket_kopiert_nur_portable_auftraege(self):
        ziel = Path(self.tmp.name) / "kopie"
        self.assertEqual(sorted(auftrag.paket(self.ordner, ziel)), ["auftrag.json", "spezifikation.md"])
        self.assertTrue((ziel / "auftrag.json").is_file())
        with self.assertRaises(ValueError) as ctx:
            auftrag.paket(self.ordner, ziel)
        self.assertEqual(str(ctx.exception), "ziel_vergeben")
        (self.ordner / "spezifikation.md").write_text("Lies /home/david/x.md", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            auftrag.paket(self.ordner, Path(self.tmp.name) / "kopie2")
        self.assertEqual(str(ctx.exception), "nicht_portabel")


class PruefungTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.box = Path(self.tmp.name) / "box"
        (self.box / "out").mkdir(parents=True)
        self.manifest = auftrag.manifest_pruefen(_manifest())

    def tearDown(self):
        self.tmp.cleanup()

    def _status(self, befunde):
        return {b["regel"]: b["status"] for b in befunde}

    def test_alles_in_ordnung(self):
        (self.box / "out" / "bewertung.md").write_text("# Bericht\n", encoding="utf-8")
        writes = [{"path": "out/bewertung.md", "bytes": 9}]
        befunde = auftrag.pruefe_ausgaben(self.box, self.manifest, writes)
        self.assertEqual(self._status(befunde)["schreibbereich"], "bestanden")
        self.assertEqual(self._status(befunde)["ausgaben_vollstaendig"], "bestanden")
        self.assertEqual(self._status(befunde)["belege"], "manuell")
        self.assertEqual(auftrag.ergebnis(befunde), "maschinell_ok")

    def test_fremder_schreibvorgang_und_fehlende_ausgabe(self):
        writes = [{"path": "quelle/README.md", "bytes": 3}]
        befunde = auftrag.pruefe_ausgaben(self.box, self.manifest, writes)
        st = self._status(befunde)
        self.assertEqual(st["schreibbereich"], "nicht_bestanden")
        self.assertEqual(st["ausgaben_vollstaendig"], "nicht_bestanden")
        self.assertEqual(auftrag.ergebnis(befunde), "nacharbeit")

    def test_projektregeln_fuer_js(self):
        m = auftrag.manifest_pruefen(_manifest(
            ausgaben=["out/app.js"],
            pruefregeln=["schreibbereich", "ausgaben_vollstaendig", "zeilen_max_400", "keine_fetch_localstorage"]))
        (self.box / "out" / "app.js").write_text("const x = localStorage.getItem('a');\n", encoding="utf-8")
        befunde = auftrag.pruefe_ausgaben(self.box, m, [{"path": "out/app.js", "bytes": 1}])
        self.assertEqual(self._status(befunde)["keine_fetch_localstorage"], "nicht_bestanden")
        (self.box / "out" / "app.js").write_text("\n" * 401, encoding="utf-8")
        befunde = auftrag.pruefe_ausgaben(self.box, m, [{"path": "out/app.js", "bytes": 1}])
        self.assertEqual(self._status(befunde)["zeilen_max_400"], "nicht_bestanden")

    def test_fehlendes_node_ist_nicht_geprueft_kein_fehlschlag(self):
        from unittest import mock
        m = auftrag.manifest_pruefen(_manifest(ausgaben=["out/app.js"], pruefregeln=["schreibbereich", "ausgaben_vollstaendig", "syntax_js"]))
        (self.box / "out" / "app.js").write_text("let a = 1;\n", encoding="utf-8")
        with mock.patch("guppi_runtime.auftrag.shutil.which", return_value=None):
            befunde = auftrag.pruefe_ausgaben(self.box, m, [{"path": "out/app.js", "bytes": 1}])
        self.assertEqual(self._status(befunde)["syntax_js"], "nicht_geprueft")
        self.assertEqual(auftrag.ergebnis(befunde), "maschinell_ok")


if __name__ == "__main__":
    unittest.main()
