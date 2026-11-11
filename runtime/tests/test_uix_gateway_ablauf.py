"""A3, App Gateway: der Ablauf-Kopf im Werkzeug GateWay – dieselben fünf Schritte wie im Kopf der KMU-Shell, der Zustand des Vorgangs bestimmt den aktuellen Schritt."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

NODE = shutil.which("node")
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"


@unittest.skipUnless(NODE, "node fehlt")
class Ablauf(unittest.TestCase):
    def pure(self):
        skript = "const G = require(%s); process.stdout.write(JSON.stringify({ablauf: G.ABLAUF, schritt: Object.fromEntries(['NEU','GESPERRT','WARTET','ENTWURF','GEPRUEFT','ABGESCHLOSSEN','VERWORFEN','FEHLER','irgendwas',undefined].map(z=>[String(z), G.ablaufSchritt(z)]))}));"
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(UIX / "tools" / "gateway" / "tool.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_gleiche_schritte_wie_die_kmu_shell(self):
        kmu = re.search(r"const ABLAUF = \[(.*?)\];", (UIX / "shells" / "gateway-kmu" / "shell.js").read_text(encoding="utf-8")).group(1)
        schritte = [s.strip().strip("'").rstrip(".") for s in kmu.split("', '")]
        self.assertEqual(self.pure()["ablauf"], schritte)

    def test_zustand_bestimmt_den_schritt(self):
        s = self.pure()["schritt"]
        self.assertEqual((s["NEU"], s["GESPERRT"], s["WARTET"], s["ENTWURF"], s["GEPRUEFT"], s["ABGESCHLOSSEN"]), (1, 2, 3, 4, 5, 6))
        self.assertEqual((s["VERWORFEN"], s["FEHLER"]), (0, 0), "abgebrochen")
        self.assertEqual((s["irgendwas"], s["undefined"]), (1, 1), "unbekannt beginnt vorn")

    def test_der_kopf_steht_in_beiden_ansichten(self):
        js = (UIX / "tools" / "gateway" / "tool.js").read_text(encoding="utf-8")
        self.assertIn("this.ablaufKopf(v)", js)
        self.assertIn("this.ablaufKopf(null)", js)
        self.assertLessEqual(len(js.splitlines()), 400)


if __name__ == "__main__":
    unittest.main()
