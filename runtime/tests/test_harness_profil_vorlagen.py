"""Profil-Vorlagen im Paket (SPEC_PROFILE_v1 PR-30, PR-34, PR-35, PR-E2): die Vorlage „Minimal“ ersetzt die Minimal-Shell als Profil. Jede Vorlage besteht die Prüfung, nennt nur Orte,
die es gibt, lässt Grundfunktionen sichtbar; Übernehmen kopiert einmal in die Profile des Projekts und wendet an, eine vorhandene Kopie bleibt."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import desktop as dt

UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
ORTE = [o["id"] for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]]
ACHT = ("tasks", "intents", "project", "models", "crew", "library", "logbook", "machine")      # die Felder der Minimal-Ablage (shelf.js)
ZELLEN = ("gauge-decisions", "gauge-model", "gauge-temp", "gauge-vram", "gauge-ram", "gauge-server", "gauge-scheduler", "gauge-state")      # leiste.json


def projekt():
    return tempfile.mkdtemp(prefix="vorlage-")


class Vorlagen(unittest.TestCase):
    def test_vorlagen_liegen_im_paket_und_bestehen_die_pruefung(self):
        ids = [v["id"] for v in dt.vorlagen_liste()]
        self.assertIn("minimal", ids)
        dateien = sorted(p.stem for p in dt.VORLAGEN.glob("*.json"))
        self.assertEqual(ids, dateien, "PR-30: jede Datei im Ordner ist eine gültige Vorlage, keine fällt still aus")
        for vid in ids:
            v = dt.vorlage_lesen(vid)
            self.assertEqual(dt.pruefen({k: v[k] for k in dt.TEILE}), {k: v[k] for k in dt.TEILE}, vid)

    def test_vorlage_nennt_nur_orte_und_zellen_die_es_gibt(self):
        """PR-35: ein Name, den es nicht gibt, ist ein Testfehler und kein stiller Ausfall."""
        for vid in [v["id"] for v in dt.vorlagen_liste()]:
            v = dt.vorlage_lesen(vid)
            for ort in v["start"]["ausblenden"] + list(v["start"]["zuordnung"]) + ([v["startseite"]["ort"]] if v["startseite"]["ort"] else []):
                self.assertIn(ort, ORTE, f"{vid}: Ort {ort}")
            for zelle in v["zellen"]["ausblenden"] + v["zellen"]["reihenfolge"]:
                self.assertIn(zelle, ZELLEN, f"{vid}: Zelle {zelle}")

    def test_minimal_zeigt_die_acht_felder_und_die_grundfunktionen(self):
        v = dt.vorlage_lesen("minimal")
        sichtbar = [o for o in ORTE if o not in v["start"]["ausblenden"]]
        for ort in ACHT:
            self.assertIn(ort, sichtbar, ort)
        for ort in dt.GRUND_START + ("boundary", "modules"):
            self.assertIn(ort, sichtbar, f"Grundfunktion {ort}")
        self.assertNotIn("team", sichtbar)
        self.assertEqual([z for z in ZELLEN if z not in v["zellen"]["ausblenden"]], ["gauge-decisions", "gauge-model"], "Taskleiste: nur Freigaben und Modell")
        self.assertEqual(sorted(v["layout"]["menue"]["ausblenden"]), ["blick", "zuletzt"])
        self.assertNotIn("gruppen", v["layout"]["menue"]["ausblenden"])

    def test_uebernehmen_kopiert_einmal_und_wendet_an(self):
        p = projekt()
        w = dt.aktion(p, {"aktion": "vorlage_uebernehmen", "id": "minimal"})
        self.assertEqual(w["profil"], "minimal")
        self.assertIn("minimal", [x["id"] for x in w["profile"]])
        self.assertIn("minimal", [x["id"] for x in w["vorlagen"]])
        self.assertEqual(w["start"]["ausblenden"], dt.vorlage_lesen("minimal")["start"]["ausblenden"])
        self.assertTrue((Path(p) / "runtime_data" / "harness" / "profile" / "minimal.json").exists())

    def test_eine_vorhandene_kopie_bleibt_wie_sie_ist(self):
        """PR-E2: der Nutzer hat die Kopie geändert; erneutes Übernehmen überschreibt sie nicht."""
        p = projekt()
        dt.vorlage_uebernehmen(p, "minimal")
        eigen = dt.profil_lesen(p, "minimal")
        dt.profil_speichern(p, "minimal", "Mein Minimal", wahl=dict({k: eigen[k] for k in dt.TEILE}, marke={"name": "Meine Marke", "akzent": "", "logo": "", "schrift": ""}))
        w = dt.vorlage_uebernehmen(p, "minimal")
        self.assertEqual(w["marke"]["name"], "Meine Marke")
        self.assertEqual(dt.profil_lesen(p, "minimal")["name"], "Mein Minimal")

    def test_unbekannte_und_ungueltige_vorlage(self):
        for bad in ("gibtsnicht", "../x", "", None, 5):
            with self.subTest(bad), self.assertRaises(ValueError):
                dt.vorlage_uebernehmen(projekt(), bad)

    def test_laden_nennt_die_vorlagen_und_die_oberflaeche_hat_den_knopf(self):
        self.assertIn("minimal", [v["id"] for v in dt.laden(projekt())["vorlagen"]])
        js = (UIX / "shells" / "harness" / "builder.js").read_text(encoding="utf-8")
        self.assertIn("vorlage_uebernehmen", js)
        self.assertIsNone(re.search(r"innerHTML", js))


if __name__ == "__main__":
    unittest.main()
