"""Dritte Ebene: Arbeitsanweisungen duerfen nur einschraenken, nie erweitern."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.manager import Manager, VerfassungsVerstoss, lade_arbeitsanweisung


def _datei(tmp, kopf, text="Text"):
    p = Path(tmp) / "x.md"
    p.write_text(f"---\n{kopf}\n---\n{text}\n", encoding="utf-8")
    return p


class Arbeitsanweisung(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.m = Manager("manager", {"datei_lesen"}, journal=Path(self.tmp) / "j.jsonl")

    def test_bau_anweisung_laedt_und_schraenkt_ein(self):
        a, wz = self.m.arbeitsanweisung("bau")
        self.assertIn("bau_starten", wz)
        self.assertNotIn("auftraege_verteilen", wz)
        self.assertTrue(wz < self.m.werkzeuge)
        self.assertFalse(a["cloud"])
        self.assertIn("Spec lesen", a["text"])

    def test_werkzeug_ausserhalb_der_gesetze_wird_abgelehnt(self):
        p = _datei(self.tmp, "werkzeuge: [bau_starten, shell_ausfuehren]")
        with self.assertRaises(VerfassungsVerstoss) as ctx:
            lade_arbeitsanweisung("bau", pfad=p)
        self.assertEqual(ctx.exception.gesetz, "arbeitsanweisungen")

    def test_cloud_nur_fuer_freigegebene_typen(self):
        with self.assertRaises(VerfassungsVerstoss):
            lade_arbeitsanweisung("bau", pfad=_datei(self.tmp, "cloud: true"))
        a = lade_arbeitsanweisung("code_und_spec_des_baus", pfad=_datei(self.tmp, "cloud: true"))
        self.assertTrue(a["cloud"])

    def test_rechte_koennen_nicht_vergeben_werden(self):
        with self.assertRaises(VerfassungsVerstoss):
            lade_arbeitsanweisung("bau", pfad=_datei(self.tmp, "rechte: [loeschen]"))

    def test_unbekannter_oder_boeser_typ(self):
        for typ in ("gibt_es_nicht", "../verfassung", ""):
            with self.assertRaises(VerfassungsVerstoss):
                self.m.arbeitsanweisung(typ)

    def test_verstoss_kommt_ins_journal(self):
        with self.assertRaises(VerfassungsVerstoss):
            self.m.arbeitsanweisung("gibt_es_nicht")
        self.assertIn('"ok": false', (Path(self.tmp) / "j.jsonl").read_text(encoding="utf-8"))


class Anschluss(unittest.TestCase):
    """Die Arbeitsanweisung erreicht den Coder: Harness-Vorlagen und Cloud-Kanal."""

    def test_alle_mitgelieferten_anweisungen_sind_gueltig(self):
        for typ in ("bau", "bau_coder", "manager", "code_und_spec_des_baus"):
            self.assertTrue(lade_arbeitsanweisung(typ)["text"])

    def test_bauagent_vorlage_enthaelt_die_arbeitsanweisung(self):
        from sedra_runtime.harness import vorlagen
        v = {i: vorlagen.laden(tempfile.mkdtemp(), i) for i in ("bauagent", "manager")}
        self.assertIn("Arbeitsanweisung (dritte Ebene", v["bauagent"]["system"])
        self.assertIn("Spec lesen", v["bauagent"]["system"])
        self.assertIn("Arbeitsanweisung (dritte Ebene", v["manager"]["system"])

    def test_ungueltiges_feld_in_der_vorlage(self):
        from sedra_runtime.harness import vorlagen
        doc = {"harness_vorlage": {"id": "t", "name": "T", "werkzeuge": ["datei_lesen"], "arbeitsanweisung": "../verfassung"}}
        with self.assertRaises(vorlagen.VorlageFehler):
            vorlagen.pruefen(doc, "Text")

    def test_cloud_coder_bekommt_die_anweisung_vor_dem_auftrag(self):
        from sedra_runtime.manager import kanal
        tmp = Path(tempfile.mkdtemp())
        gesendet = {}
        vor = kanal.Vorarbeiter(tmp, manager=Manager("v", set(), journal=tmp / "j.jsonl"))
        kanal.waehle_modell = lambda typ, ordner: "modell-x"
        vor._senden = lambda typ, modell, nachricht: gesendet.update(n=nachricht) or {"ok": True}
        try:
            self.assertTrue(vor.auftrag("code_und_spec_des_baus", "Baue foo")["ok"])
        finally:
            import importlib
            importlib.reload(kanal)
        self.assertTrue(gesendet["n"].startswith("Arbeitsanweisung"))
        self.assertIn("Du bist der Coder", gesendet["n"])
        self.assertTrue(gesendet["n"].endswith("Baue foo"))

    def test_bau_pipeline_reicht_die_anweisung_an_den_entwickler(self):
        """bau_schleife ruft devvm_build immer mit --arbeitsanweisung auf, devvm_build haengt den Text an Aufgabe und Nacharbeit."""
        bench = Path(__file__).resolve().parents[1] / "benchmarks"
        schleife = (bench / "bau_schleife.py").read_text(encoding="utf-8")
        bau = (bench / "devvm_build.py").read_text(encoding="utf-8")
        self.assertIn('"--arbeitsanweisung", ARBEITSANWEISUNG', schleife)
        self.assertIn('ARBEITSANWEISUNG = "bau_coder"', schleife)
        self.assertEqual(lade_arbeitsanweisung("bau_coder")["typ"], "bau_coder")
        self.assertIn('team.run(stage["task"] + addendum, lessons)', bau)
        self.assertIn('REWORK_TASK.format(task=stage["task"] + addendum', bau)

    def test_typ_ohne_anweisung_laeuft_unveraendert(self):
        m = Manager("v", set())
        self.assertEqual(m.arbeitsanweisung("text_und_recherche_ohne_personenbezug", pflicht=False), (None, m.werkzeuge))


if __name__ == "__main__":
    unittest.main()
