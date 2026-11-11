"""AM1 (SPEC_APPS_v1_AM1_G2 §3, G3 S14): die Taskleiste von One Sedra liest ihre Zellen aus den Manifesten der Instrumente und aus leiste.json.
Die echten Manifeste und die echte Datei ergeben genau die Liste, die die Taskleiste vorher fest eingebaut hatte (ZELLEN_RUECKFALL)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import Gateway

HARNESS = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "shells" / "harness"
NODE = shutil.which("node")

SKRIPT = """
const z = require(process.argv[1]);
const eingabe = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const aus = {};
for (const [name, args] of Object.entries(eingabe)) aus[name] = z[args[0]](...args.slice(1));
process.stdout.write(JSON.stringify(aus));
"""


def node(aufrufe):
    out = subprocess.run([NODE, "-e", SKRIPT, str(HARNESS / "zellen.js")], input=json.dumps(aufrufe), capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node fehlt")
class Leiste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="am1-leiste-")
        root = Path(cls.tmp.name)
        (root / "local_config").mkdir()
        (root / "local_config" / "uix.yaml").write_text("shell: harness\n", encoding="utf-8")
        man = Gateway(root).manifest()
        cls.instrumente = [t for t in man["tools"] if t["kind"] == "instrument"]
        cls.auswahl = json.loads((HARNESS / "leiste.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_echte_manifeste_und_datei_ergeben_die_eingebaute_liste(self):
        z = node({"z": ["zellenAusManifest", self.instrumente, self.auswahl]})["z"]
        rueck = json.loads(subprocess.run([NODE, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1]).ZELLEN_RUECKFALL))", str(HARNESS / "zellen.js")],
                                          capture_output=True, text=True, encoding="utf-8", timeout=60).stdout)
        self.assertEqual(z["fehlend"], [])
        self.assertEqual(z["ohneZelle"], [])
        self.assertEqual(z["zellen"], rueck)
        self.assertEqual([c["feld"] for c in z["zellen"]], ["decisions", "model", "temp", "vram", "ram", "server", "scheduler", "state"])

    def test_das_cockpit_bekommt_die_neuen_zellen_nicht(self):
        root = Path(self.tmp.name) / "cockpit"
        (root / "local_config").mkdir(parents=True)
        (root / "local_config" / "uix.yaml").write_text("shell: cockpit\n", encoding="utf-8")
        ids = {t["id"] for t in Gateway(root).manifest()["tools"]}
        for neu in ("gauge-temp", "gauge-vram", "gauge-ram", "gauge-server", "gauge-scheduler"):
            self.assertNotIn(neu, ids)
        for alt in ("gauge-decisions", "gauge-gpu", "gauge-state"):
            self.assertIn(alt, ids)

    def test_neue_zelle_ohne_codeaenderung(self):
        auswahl = {"zellen": self.auswahl["zellen"] + ["gauge-tasks"]}
        z = node({"z": ["zellenAusManifest", self.instrumente, auswahl]})["z"]
        self.assertEqual(z["zellen"][-1], {"id": "gauge-tasks", "feld": "tasks", "label": "Aufgaben", "ort": "tasks", "aktion": None, "quelle": None})

    def test_fremde_instrumente_werden_uebergangen(self):
        fremd = [dict(i, trust="COMMUNITY") for i in self.instrumente]
        z = node({"z": ["zellenAusManifest", fremd, self.auswahl]})["z"]
        self.assertEqual(z["zellen"], [])
        self.assertEqual(z["fehlend"], self.auswahl["zellen"])

    def test_fehlendes_instrument_steht_unter_fehlend(self):
        z = node({"z": ["zellenAusManifest", self.instrumente, {"zellen": ["gauge-ram", "gauge-gibt-es-nicht"]}]})["z"]
        self.assertEqual([c["feld"] for c in z["zellen"]], ["ram"])
        self.assertEqual(z["fehlend"], ["gauge-gibt-es-nicht"])

    def test_kaputte_datei_wirft_einen_satz(self):
        for roh, satz in (("{kaputt", "Leiste: Datei ist kein gueltiges JSON"), ({"zellen": []}, "Leiste: zellen ist leer"), ({"x": 1}, "Leiste: zellen fehlt oder ist keine Liste")):
            out = subprocess.run([NODE, "-e", "try{require(process.argv[1]).pruefeAuswahl(JSON.parse(process.argv[2]))}catch(e){process.stdout.write(e.message)}", str(HARNESS / "zellen.js"), json.dumps(roh)],
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(out.stdout, satz)

    def test_instrument_namens_constructor_gilt_nicht_als_doppelt(self):
        out = subprocess.run([NODE, "-e", "process.stdout.write(JSON.stringify(require(process.argv[1]).pruefeAuswahl({zellen:['constructor','ab']})))", str(HARNESS / "zellen.js")],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(json.loads(out.stdout), {"zellen": ["constructor", "ab"]})

    def test_aktion_vor_ort(self):
        z = node({"a": ["aktionZiel", {"aktion": "modellmenue", "ort": "models"}], "b": ["aktionZiel", {"aktion": "einstellungen:system"}], "c": ["aktionZiel", {"ort": "hardware"}],
                  "d": ["aktionZiel", {"aktion": "kaputt", "ort": "slots"}], "e": ["aktionZiel", {}]})
        self.assertEqual(z["a"], {"art": "modellmenue"})
        self.assertEqual(z["b"], {"art": "einstellungen", "gruppe": "system", "punkt": None})
        self.assertEqual(z["c"], {"art": "ort", "ort": "hardware"})
        self.assertEqual(z["d"], {"art": "ort", "ort": "slots"})
        self.assertEqual(z["e"], {"art": "keine"})

    def test_dateien_der_shell(self):
        yaml_text = (HARNESS / "shell.yaml").read_text(encoding="utf-8")
        self.assertLess(yaml_text.index("zellen.js"), yaml_text.index("taskleiste.js"), "zellen.js muss vor taskleiste.js laden")
        self.assertTrue((HARNESS / "leiste.json").is_file())


if __name__ == "__main__":
    unittest.main()
