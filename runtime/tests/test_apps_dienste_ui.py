"""AM4-04 und AM4-06 in der Oberfläche: die Seite Dienste im Werkzeug „Module“ und die Berechtigung der Zugänge unter Einstellungen → Integrationen → MCP."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import check_shell, check_tool

NODE = shutil.which("node")
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
MODULES = UIX / "tools" / "modules"
HARNESS = UIX / "shells" / "harness"


class Seiten(unittest.TestCase):
    def test_manifeste_bleiben_gueltig_und_nennen_die_routen(self):
        man, fehler = check_tool(yaml.safe_load((MODULES / "tool.yaml").read_text(encoding="utf-8")), MODULES, "package")
        self.assertEqual(fehler, [])
        for r in ("GET /api/uix/dienste", "POST /api/uix/dienste/start", "POST /api/uix/dienste/stopp"):
            self.assertIn(r, man["api"])
        self.assertIn("dienste.js", man["js"])
        sman, fehler = check_shell(yaml.safe_load((HARNESS / "shell.yaml").read_text(encoding="utf-8")), HARNESS, "package")
        self.assertEqual(fehler, [])
        self.assertIn("GET /api/uix/zugaenge", sman["api"])

    def test_mcp_seite_zeigt_die_berechtigung_und_den_satz(self):
        js = (HARNESS / "einstellungen.js").read_text(encoding="utf-8")
        self.assertIn("/api/uix/zugaenge", js)
        self.assertIn("Berechtigung mcp", js)
        self.assertNotIn("Zu konfigurieren gibt es nichts", js, "AM4-04: statt „nichts zu konfigurieren“ die Berechtigung")
        self.assertLessEqual(len(js.splitlines()), 400)

    def test_jeder_gerufene_dienste_weg_steht_im_manifest(self):
        import re
        js = (MODULES / "dienste.js").read_text(encoding="utf-8") + (MODULES / "tool.js").read_text(encoding="utf-8")
        gerufen = set(re.findall(r"api\('(/api/uix/dienste[a-z/]*)'", js))
        erlaubt = {r.split(" ", 1)[1] for r in yaml.safe_load((MODULES / "tool.yaml").read_text(encoding="utf-8"))["tool"]["api"]}
        self.assertTrue(gerufen)
        self.assertLessEqual(gerufen, erlaubt)

    @unittest.skipUnless(NODE, "node fehlt")
    def test_reine_saetze(self):
        skript = ("const m = require(%s); process.stdout.write(JSON.stringify([m.zustandSatz({laeuft: true, pid: 42}), m.zustandSatz({laeuft: false}), m.zustandSatz({laeuft: false, grund: 'zu_oft_abgestuerzt'}),"
                  "m.zustandSatz({laeuft: false, grund: 'abgestuerzt:3'}), m.zustandSatz({laeuft: false, grund: 'captain'}), m.abgewiesenSatz(['dienst_fremd_nur_microvm', 'dienst_start_pfad'])]));")
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(MODULES / "dienste.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        r = json.loads(out.stdout)
        self.assertEqual(r[:5], ["läuft · PID 42", "läuft nicht", "läuft nicht · zu oft abgestürzt – aus", "läuft nicht · abgestürzt (Exitcode 3)", "läuft nicht · von dir gestoppt"])
        self.assertIn("microVM", r[5])
        self.assertIn("dienst_start_pfad", r[5])
        self.assertLessEqual(len((MODULES / "tool.js").read_text(encoding="utf-8").splitlines()), 400)



class BetriebSeite(unittest.TestCase):
    def test_manifest_nennt_die_betrieb_wege_und_laedt_die_datei(self):
        man, fehler = check_tool(yaml.safe_load((MODULES / "tool.yaml").read_text(encoding="utf-8")), MODULES, "package")
        self.assertEqual(fehler, [])
        for r in ("GET /api/uix/betrieb", "GET /api/uix/betrieb/export", "GET /api/uix/betrieb/eingaben"):
            self.assertIn(r, man["api"])
        self.assertEqual(man["js"], ["dienste.js", "betrieb.js", "tool.js"])
        text = (MODULES / "betrieb.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", text)
        self.assertNotIn("method: 'POST'", text, "AM7-06: es gibt keinen Weg, die Richtlinie über SEDRA zu ändern")

    @unittest.skipUnless(NODE, "node fehlt")
    def test_saetze(self):
        skript = ("const m = require(%s); process.stdout.write(JSON.stringify([m.richtlinieSatz(null), m.richtlinieSatz({schalter: true, richtlinie: {aktiv: true, rolle: 'pruefung', person: 'X', hash: 'abcdef1234567890'}}),"
                  "m.richtlinieSatz({schalter: true, richtlinie: {aktiv: false, vorhanden: true, fehler: ['richtlinie_rolle_ungueltig']}}), m.richtlinieSatz({schalter: true, richtlinie: {}})]));")
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(MODULES / "betrieb.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        r = json.loads(out.stdout)
        self.assertIn("Einzelplatzbetrieb", r[0])
        self.assertEqual(r[1], "Richtlinie aktiv · Prüfung · X · Prüfsumme abcdef123456")
        self.assertIn("nicht gültig", r[2])
        self.assertIn("richtlinie_rolle_ungueltig", r[2])
        self.assertIn("Keine Richtlinie", r[3])


if __name__ == "__main__":
    unittest.main()
