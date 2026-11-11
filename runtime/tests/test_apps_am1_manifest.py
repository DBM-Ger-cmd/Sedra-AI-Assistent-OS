"""AM1 (Vertrag 1.1, SPEC_APPS_v1_AM1_G2 §1, G3 §4): die Manifest-Felder shells, profile und zelle – Prüfung, Filter nach Shell und Profil, Warnungen.
Sichtbarkeit, kein Recht: die Allowlist (`Gateway.allowed`) bleibt für ein nicht sichtbares Werkzeug dieselbe."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import UI_VERSION, Gateway, check_tool
from sedra_runtime.desk.manifest_felder import filtere, pruefe_profile, pruefe_shells, pruefe_zelle

SCHEMA = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "ui" / "schema" / "tool.schema.json"

BASIS = {"id": "probe", "name": "Probe", "version": "1.0.0", "kind": "instrument", "entry": {"js": "tool.js"}, "api": [], "handles": [],
         "events": {"emits": [], "listens": []}, "trust": "CAPTAIN", "needs": {"ui": ">=1.0 <2"}}


def lege(root, tid, **mehr):
    folder = root / "local_config" / "tools" / tid
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"tool": dict(BASIS, id=tid, name=tid.title(), **mehr)}
    (folder / "tool.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    (folder / "tool.js").write_text("// probe\n", encoding="utf-8")
    return folder


class Funktionen(unittest.TestCase):
    def test_shells(self):
        self.assertEqual(pruefe_shells(None), ([], []))
        self.assertEqual(pruefe_shells(["harness", "xp"], ["harness"]), ([], ["shells_unbekannt:xp"]))
        for falsch in ([], "harness", ["H"], ["a", "a"], [5]):
            self.assertEqual(pruefe_shells(falsch), (["shells_invalid"], []), falsch)

    def test_profile(self):
        self.assertEqual(pruefe_profile(["standard", "kmu"], ["kmu"]), ([], []))
        self.assertEqual(pruefe_profile(["kmu", "stick"], ["kmu"]), ([], ["profil_unbekannt:stick"]))
        self.assertEqual(pruefe_profile(["kmu"], None, True), ([], ["grundfunktion_ignoriert_profil"]))
        self.assertEqual(pruefe_profile([], None), (["profile_invalid"], []))

    def test_zelle(self):
        orte = ["models", "hardware"]
        self.assertEqual(pruefe_zelle({"feld": "ram", "label": "RAM frei", "ort": "hardware", "aktion": "modellmenue"}, "instrument", orte), [])
        self.assertEqual(pruefe_zelle({"feld": "ram", "label": "x"}, "object", orte), ["zelle_nur_fuer_instrument"])
        self.assertEqual(pruefe_zelle({"feld": "R", "label": "", "ort": "x", "aktion": "y", "b": 1}, "instrument", orte),
                         ["zelle_feld_invalid", "zelle_label_invalid", "zelle_ort_unbekannt", "zelle_aktion_invalid", "zelle_unbekannt:b"])

    def test_zelle_ort_als_liste_wirft_nicht(self):
        self.assertEqual(pruefe_zelle({"feld": "ram", "label": "x", "ort": ["a"]}, "instrument", {"models"}), ["zelle_ort_unbekannt"])

    def test_filter(self):
        tools = [{"id": "a", "name": "A"}, {"id": "b", "name": "B", "shells": ["cockpit"]}, {"id": "c", "name": "C", "profile": ["kmu"]},
                 {"id": "decisions", "name": "D", "shells": ["cockpit"], "profile": ["kmu"]}]
        sichtbar, nicht_shell, nicht_profil = filtere(tools, "harness", None, ["decisions"])
        self.assertEqual([t["id"] for t in sichtbar], ["a", "decisions"])
        self.assertEqual(nicht_shell, [{"id": "b", "name": "B", "shells": ["cockpit"]}])
        self.assertEqual(nicht_profil, [{"id": "c", "name": "C", "profile": ["kmu"]}])


class Manifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am1-manifest-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "local_config").mkdir(parents=True, exist_ok=True)
        (self.root / "local_config" / "uix.yaml").write_text("shell: harness\n", encoding="utf-8")

    def check(self, **mehr):
        folder = lege(self.root, "probe", **mehr)
        return check_tool(yaml.safe_load((folder / "tool.yaml").read_text(encoding="utf-8")), folder, "local")

    def test_version(self):
        self.assertEqual(UI_VERSION, (1, 1))
        self.assertEqual(Gateway(self.root).manifest()["ui"], "1.1")

    def test_gueltige_felder_kommen_im_manifest_an(self):
        man, fehler = self.check(shells=["harness"], profile=["standard", "kmu"], zelle={"feld": "ram", "label": "RAM", "ort": "hardware"})
        self.assertEqual(fehler, [])
        self.assertEqual((man["shells"], man["profile"], man["zelle"]["feld"]), (["harness"], ["standard", "kmu"], "ram"))

    def test_fehlende_felder_sind_none(self):
        man, fehler = self.check()
        self.assertEqual(fehler, [])
        self.assertEqual((man["shells"], man["profile"], man["zelle"]), (None, None, None))

    def test_jede_fehlermeldung(self):
        self.assertIn("shells_invalid", self.check(shells=[])[1])
        self.assertIn("profile_invalid", self.check(profile=["A"])[1])
        self.assertIn("zelle_feld_invalid", self.check(zelle={"feld": "R", "label": "x"})[1])
        self.assertIn("zelle_ort_unbekannt", self.check(zelle={"feld": "ram", "label": "x", "ort": "nirgends"})[1])
        self.assertIn("zelle_nur_fuer_instrument", self.check(kind="object", handles=["task"], zelle={"feld": "ram", "label": "x"})[1])

    def test_filter_nach_shell(self):
        lege(self.root, "nur-cockpit", shells=["cockpit"])
        lege(self.root, "nur-harness", shells=["harness"])
        lege(self.root, "ueberall")
        gw = Gateway(self.root)
        man = gw.manifest()
        ids = [t["id"] for t in man["tools"]]
        self.assertIn("nur-harness", ids)
        self.assertIn("ueberall", ids)
        self.assertNotIn("nur-cockpit", ids)
        self.assertIn("nur-cockpit", [t["id"] for t in man["nicht_in_dieser_shell"]])

    def test_nicht_in_dieser_shell_nennt_die_objekttypen_fuer_den_leerzustand(self):
        lege(self.root, "nur-cockpit", shells=["cockpit"], kind="object", handles=["task"])
        eintrag = next(t for t in Gateway(self.root).manifest()["nicht_in_dieser_shell"] if t["id"] == "nur-cockpit")
        self.assertEqual(eintrag["handles"], ["task"])
        self.assertEqual(eintrag["shells"], ["cockpit"])

    def test_filter_aendert_die_allowlist_nicht(self):
        lege(self.root, "nur-cockpit", shells=["cockpit"], api=["GET /api/strip"])
        gw = Gateway(self.root)
        self.assertNotIn("nur-cockpit", [t["id"] for t in gw.manifest()["tools"]])
        self.assertTrue(gw.allowed("tool", "nur-cockpit", "GET", "/api/strip"))

    def test_filter_nach_profil(self):
        lege(self.root, "fuer-kmu", profile=["kmu"])
        lege(self.root, "fuer-stick", profile=["stick"])
        gw = Gateway(self.root)
        gw._aktives_profil = lambda: "stick"
        man = gw.manifest()
        ids = [t["id"] for t in man["tools"]]
        self.assertIn("fuer-stick", ids)
        self.assertNotIn("fuer-kmu", ids)
        self.assertEqual([t["id"] for t in man["nicht_in_diesem_profil"]], ["fuer-kmu"])

    def test_ohne_profilwahl_gilt_standard(self):
        lege(self.root, "fuer-standard", profile=["standard"])
        lege(self.root, "fuer-kmu", profile=["kmu"])
        ids = [t["id"] for t in Gateway(self.root).manifest()["tools"]]
        self.assertIn("fuer-standard", ids)
        self.assertNotIn("fuer-kmu", ids)

    def test_grundfunktion_ignoriert_das_profil(self):
        lege(self.root, "meine-grund", profile=["kmu"])
        gw = Gateway(self.root)
        gw._aktives_profil = lambda: "stick"
        gw._grundfunktionen = lambda: {"meine-grund"}
        man = gw.manifest()
        self.assertIn("meine-grund", [t["id"] for t in man["tools"]])
        self.assertIn({"id": "meine-grund", "grund": "grundfunktion_ignoriert_profil"}, man["warnungen"])

    def test_unbekannte_shell_ist_nur_eine_warnung(self):
        lege(self.root, "fuer-xp", shells=["harness", "xp"])
        man = Gateway(self.root).manifest()
        self.assertIn("fuer-xp", [t["id"] for t in man["tools"]])
        self.assertIn({"id": "fuer-xp", "grund": "shells_unbekannt:xp"}, man["warnungen"])


class Schema(unittest.TestCase):
    def test_schema_kennt_die_felder(self):
        props = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["tool"]["properties"]
        for feld in ("shells", "profile", "zelle"):
            self.assertIn(feld, props)


if __name__ == "__main__":
    unittest.main()
