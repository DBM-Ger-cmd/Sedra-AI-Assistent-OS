import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.uix_server import UIXHub, quelle_pruefen
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = Path(__file__).resolve().parents[2] / "architecture/GUPPI_Architecture_v1.17_RUNTIME_SYNC"
MINIMAL = Path(__file__).resolve().parents[1] / "src/guppi_runtime/uix/shells/minimal"


def _kopie(ziel, neue_id):
    """Eine Kopie der Shell minimal unter neuer Kennung, damit sie nicht mit der eingebauten zusammenstößt."""
    shutil.copytree(MINIMAL, ziel)
    doc = yaml.safe_load((ziel / "shell.yaml").read_text(encoding="utf-8"))
    doc["shell"]["id"] = neue_id
    (ziel / "shell.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return ziel


class ImportEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.quelle = _kopie(Path(self.tmp.name) / "quelle" / "minimal-test", "minimal-test")

    def test_vorlegen_freigabe_einbau(self):
        out = self.hub.install_request({"kind": "shell", "source": str(self.quelle)})
        mid, gate = out["mission_id"], out["gate"]
        with self.assertRaises(ValueError):                       # ohne Freigabe nichts einbauen
            self.hub.install_apply({"mission_id": mid})
        self.hub.approve_gate({"mission_id": mid, "gate_id": gate["gate_id"]})
        done = self.hub.install_apply({"mission_id": mid})
        self.assertTrue(done)
        ziel = Path(self.hub.project_root) / "local_config" / "shells" / "minimal-test"
        self.assertTrue((ziel / "shell.yaml").is_file())

    def test_schon_vergebene_kennung_wird_erklaert(self):
        ziel = _kopie(Path(self.tmp.name) / "quelle" / "dublette" / "minimal", "minimal")   # der Ordnername muss zur id passen
        with self.assertRaises(ValueError) as ctx:
            self.hub.install_request({"kind": "shell", "source": str(ziel)})
        self.assertIn("schon vergeben", str(ctx.exception))
        self.assertIn("„minimal“", str(ctx.exception))


class QuellePruefenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ordner = self.root / "meine-shell"
        self.ordner.mkdir()
        (self.ordner / "shell.yaml").write_text("shell:\n  id: meine\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_gueltige_quelle(self):
        kind, folder = quelle_pruefen({"kind": "shell", "source": str(self.ordner)})
        self.assertEqual(kind, "shell")
        self.assertEqual(folder, self.ordner)

    def test_art_fehlt(self):
        with self.assertRaises(ValueError) as ctx:
            quelle_pruefen({"source": str(self.ordner)})
        self.assertIn("Shell oder ein Werkzeug", str(ctx.exception))

    def test_pfad_fehlt(self):
        with self.assertRaises(ValueError) as ctx:
            quelle_pruefen({"kind": "shell", "source": "  "})
        self.assertIn("Ordnerpfad", str(ctx.exception))

    def test_pfad_nicht_vollstaendig(self):
        with self.assertRaises(ValueError) as ctx:
            quelle_pruefen({"kind": "shell", "source": "meine-shell"})
        self.assertIn("vollständig", str(ctx.exception))

    def test_ordner_gibt_es_nicht(self):
        with self.assertRaises(ValueError) as ctx:
            quelle_pruefen({"kind": "shell", "source": str(self.root / "fehlt")})
        self.assertIn("gibt es nicht", str(ctx.exception))

    def test_manifest_fehlt(self):
        leer = self.root / "leer"
        leer.mkdir()
        with self.assertRaises(ValueError) as ctx:
            quelle_pruefen({"kind": "shell", "source": str(leer)})
        self.assertIn("shell.yaml", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
