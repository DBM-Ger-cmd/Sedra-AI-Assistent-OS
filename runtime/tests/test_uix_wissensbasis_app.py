"""A3, App Wissensbasis (U3): das Werkzeug `wissen` ist schon die Sammel-App – fünf Ansichten (Suche, Quellen, Vorschläge, Eigenes, Messung) in einem Reiter, die Fundstelle als Nachweis.
Im Start-Menü der Harness steht deshalb nur noch ein Eintrag „Wissen“; die Ansichts-Orte bleiben für Suche und Chat (`öffne wissenssuche`) und führen in dieselbe App."""
import json
import re
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
ANSICHTS_ORTE = ["wissen-suche", "wissen-quellen", "wissen-vorschlaege", "wissen-eigenes", "wissen-messung", "wissen-index", "wissen-nachmessung"]


class Wissensbasis(unittest.TestCase):
    def test_nur_ein_menue_eintrag_die_ansichts_orte_bleiben_erreichbar(self):
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        for ort in ANSICHTS_ORTE:
            self.assertIn(ort, gruppen["ausblenden"], ort)
        self.assertNotIn("wissen", gruppen["ausblenden"])
        self.assertEqual(gruppen["zuordnung"]["wissen"], "wissen")
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        for ort in ["wissen"] + ANSICHTS_ORTE:
            self.assertEqual((orte[ort]["object"]["type"], orte[ort]["object"]["id"]), ("wissen", "speicher"), "alle Orte führen in dieselbe App")

    def test_das_werkzeug_hat_die_fuenf_ansichten_und_die_fundstelle_den_nachweis(self):
        js = (UIX / "tools" / "wissen" / "tool.js").read_text(encoding="utf-8")
        ids = re.findall(r"\['(\w+)', '[^']+'\]", re.search(r"const ANSICHTEN = \[(.*?)\];", js).group(1))
        self.assertEqual(ids, ["suche", "quellen", "vorschlaege", "eigenes", "messung"])
        for ort in ANSICHTS_ORTE:                                          # jede Ansicht eines versteckten Orts ist eine Ansicht des Werkzeugs (direkt oder über UM)
            view = next(o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"] if o["id"] == ort)["object"].get("view")
            if view:
                self.assertTrue(view in ids or re.search(r"\b%s\b" % view, js), (ort, view))
        self.assertIn("slot: nachweis", (UIX / "tools" / "fundstelle" / "tool.yaml").read_text(encoding="utf-8"))

    def test_chat_woerter_der_ansichten_bleiben(self):
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        self.assertIn("wissenssuche", orte["wissen-suche"]["words"])
        self.assertIn("wissensquellen", orte["wissen-quellen"]["words"])


if __name__ == "__main__":
    unittest.main()
