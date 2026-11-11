"""AM3-25 (Stück 5): die Seite „Apps“ im Werkzeug „Module“. Das Manifest nennt die neuen Routen, die reinen Hilfen laufen mit node, und jede Route, die das
Werkzeug ruft, steht in seinem Manifest (sonst antwortet der Server 403)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import check_tool

NODE = shutil.which("node")
ORDNER = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "tools" / "modules"


class Seite(unittest.TestCase):
    def test_manifest_ist_gueltig_und_nennt_die_app_routen(self):
        doc = yaml.safe_load((ORDNER / "tool.yaml").read_text(encoding="utf-8"))
        man, fehler = check_tool(doc, ORDNER, "package")
        self.assertEqual(fehler, [])
        for route in ("GET /api/uix/apps", "POST /api/uix/apps/aktivieren", "POST /api/uix/apps/entziehen", "POST /api/uix/apps/rechte"):
            self.assertIn(route, man["api"])

    def test_jede_gerufene_app_route_steht_im_manifest(self):
        js = (ORDNER / "tool.js").read_text(encoding="utf-8")
        gerufen = set(re.findall(r"ctx\.api\('(/api/uix/apps[a-z/]*)'", js))
        self.assertTrue(gerufen)
        doc = yaml.safe_load((ORDNER / "tool.yaml").read_text(encoding="utf-8"))
        erlaubt = {r.split(" ", 1)[1] for r in doc["tool"]["api"]}
        self.assertLessEqual(gerufen, erlaubt)

    @unittest.skipUnless(NODE, "node fehlt")
    def test_reine_hilfen(self):
        skript = ("const m = require(%s); const app = {beantragt: ["
                  "{faehigkeit:'lesen:task', stufe:'A', gewaehrt:false}, {faehigkeit:'verb:task.close', stufe:'B', gewaehrt:false},"
                  "{faehigkeit:'ereignis:system.state', stufe:'A', gewaehrt:true}, {faehigkeit:'dienst:host', stufe:'C', gewaehrt:false}]};"
                  "process.stdout.write(JSON.stringify({offen: m.offeneRechte(app), leer: m.offeneRechte(null), g1: m.appGrund('rechte_nicht_gewaehrt:x'), g2: m.appGrund(null), g3: m.appGrund('unbekannt'), s: m.STUFE.B}));")
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(ORDNER / "tool.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        r = json.loads(out.stdout)
        self.assertEqual(r["offen"], ["lesen:task", "verb:task.close"], "Gewährtes und Stufe C werden nicht beantragt")
        self.assertEqual(r["leer"], [])
        self.assertEqual(r["g1"], "sie beantragt mehr, als gewährt ist")
        self.assertEqual((r["g2"], r["g3"]), ("", "unbekannt"))
        self.assertIn("Freigabe", r["s"])


if __name__ == "__main__":
    unittest.main()
