"""AM0-03 (SPEC_APPS_v1_AM0_G2 §3): Routenregeln für Module aus local_config – zu breite Platzhalter und die Sperrliste für fremde Module.
Pakete (origin 'package') bleiben unberührt; alle Manifeste des Pakets müssen weiter gültig sein."""
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import check_shell, check_tool
from sedra_runtime.desk.routen_pruefung import SENSIBEL_COMMUNITY, pruefe_routen, route_sensibel, route_zu_breit

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"

TOOL = {"id": "probe", "name": "Probe", "version": "1.0.0", "kind": "object", "handles": ["task"], "entry": {"js": "tool.js"},
        "api": ["GET /api/strip"], "events": {"emits": [], "listens": []}, "trust": "COMMUNITY", "needs": {"ui": ">=1.0 <2"}}


class Funktionen(unittest.TestCase):
    def test_zu_breit(self):
        self.assertTrue(route_zu_breit("GET /api/*"))
        self.assertTrue(route_zu_breit("POST /uix/*"))
        self.assertFalse(route_zu_breit("GET /api/gateway/*"))
        self.assertFalse(route_zu_breit("GET /api/x/api/*"))
        self.assertFalse(route_zu_breit("GET /uix/frame/*"))
        self.assertFalse(route_zu_breit(None))

    def test_sensibel_in_beide_richtungen(self):
        self.assertTrue(route_sensibel("GET /api/audit"))
        self.assertTrue(route_sensibel("GET /api/fisch/*"))
        self.assertTrue(route_sensibel("GET /api/fisch/transkripte"))
        self.assertFalse(route_sensibel("GET /api/strip"))
        self.assertEqual(len(SENSIBEL_COMMUNITY), 18)

    def test_pruefe_routen(self):
        self.assertEqual(pruefe_routen(["GET /api/*"], "local", "COMMUNITY"), ["api_route_too_broad:GET /api/*", "api_route_sensitive:GET /api/*"])
        self.assertEqual(pruefe_routen(["GET /api/*"], "local", "CAPTAIN"), ["api_route_too_broad:GET /api/*"])
        self.assertEqual(pruefe_routen(["GET /api/audit"], "local", "CAPTAIN"), [])
        self.assertEqual(pruefe_routen(["GET /api/*"], "package", "COMMUNITY"), [])


class Manifeste(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am0-routen-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "probe"
        self.folder.mkdir()
        (self.folder / "tool.js").write_text("// probe\n", encoding="utf-8")

    def fehler(self, **changes):
        doc = {"tool": dict(TOOL, **changes)}
        return check_tool(doc, self.folder, "local")[1]

    def test_gueltige_leseroute_bleibt_gueltig(self):
        self.assertEqual(self.fehler(), [])

    def test_breit_wird_abgewiesen(self):
        self.assertIn("api_route_too_broad:GET /api/*", self.fehler(api=["GET /api/*"], trust="CAPTAIN"))

    def test_sperrliste_nur_fuer_fremde(self):
        self.assertIn("api_route_sensitive:GET /api/audit", self.fehler(api=["GET /api/audit"]))
        self.assertEqual(self.fehler(api=["GET /api/audit"], trust="CAPTAIN"), [])

    def test_sperrliste_trifft_praefix(self):
        self.assertIn("api_route_sensitive:GET /api/gateway/*", self.fehler(api=["GET /api/gateway/*"]))

    def test_nicht_get_route_fremder_wird_geprueft_bevor_sie_entfaellt(self):
        self.assertIn("api_route_too_broad:POST /api/*", self.fehler(api=["POST /api/*"]))


class Paket(unittest.TestCase):
    def test_alle_paket_manifeste_bleiben_gueltig(self):
        gepruft = 0
        for datei in sorted(PACKAGE.glob("tools/*/tool.yaml")):
            if datei.parent.name.startswith("_"):
                continue
            doc = yaml.safe_load(datei.read_text(encoding="utf-8"))
            fehler = check_tool(doc, datei.parent, "package")[1]
            self.assertEqual(fehler, [], datei.parent.name)
            gepruft += 1
        for datei in sorted(PACKAGE.glob("shells/*/shell.yaml")):
            if datei.parent.name.startswith("_"):
                continue
            doc = yaml.safe_load(datei.read_text(encoding="utf-8"))
            self.assertEqual(check_shell(doc, datei.parent, "package")[1], [], datei.parent.name)
            gepruft += 1
        self.assertGreater(gepruft, 40)


if __name__ == "__main__":
    unittest.main()
