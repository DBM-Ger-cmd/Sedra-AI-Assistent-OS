"""AM0-04 und AM0-05 (SPEC_APPS_v1_AM0_G2 §4, §5): die Rahmenseite hat eine eigene, strenge CSP; das Sandbox-Attribut des Rahmens ist eine Konstante
mit genau dem Wert `allow-scripts`."""
import json
import re
import subprocess
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import uix_server

UI = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "ui"
LOADER = UI / "loader.js"
VERBOTEN = ("allow-same-origin", "allow-top-navigation", "allow-popups", "allow-forms", "allow-modals")


def node():
    import shutil
    return shutil.which("node")


class Sandbox(unittest.TestCase):
    def test_konstante_hat_genau_den_wert(self):
        text = LOADER.read_text(encoding="utf-8")
        self.assertIn("const RAHMEN_SANDBOX = 'allow-scripts';", text)
        self.assertIn("setAttribute('sandbox', RAHMEN_SANDBOX)", text)

    def test_loader_nennt_keine_der_gefaehrlichen_erlaubnisse_im_code(self):
        code = "\n".join(re.sub(r"//.*", "", zeile) for zeile in LOADER.read_text(encoding="utf-8").splitlines())      # Kommentare zählen nicht
        for wort in VERBOTEN:
            self.assertNotIn(wort, code, wort)

    @unittest.skipUnless(node(), "node fehlt")
    def test_exportierter_wert_unter_node(self):
        out = subprocess.run([node(), "-e", f"const m=require({json.dumps(str(LOADER))});process.stdout.write(JSON.stringify(m.RAHMEN_SANDBOX))"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(json.loads(out.stdout), "allow-scripts", out.stderr)


@unittest.skipUnless(node(), "node fehlt")
class Lader(unittest.TestCase):
    def sperre(self, shell):
        out = subprocess.run([node(), "-e", f"const m=require({json.dumps(str(LOADER))});process.stdout.write(JSON.stringify(m.shellSperre({json.dumps(shell)})))"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_fremde_shell_ohne_vorgabe_wird_nie_geladen(self):
        self.assertEqual(self.sperre({"trust": "COMMUNITY"}), "Eine fremde Shell ohne Vorgabe wird nicht geladen.")

    def test_fremde_vorgabe_shell_laedt(self):
        self.assertEqual(self.sperre({"trust": "COMMUNITY", "frame": True}), "")

    def test_eigene_und_kern_shells_laden_wie_bisher(self):
        for trust in ("CORE", "CAPTAIN", "SEDRA_BUILT"):
            self.assertEqual(self.sperre({"trust": trust}), "", trust)
        self.assertEqual(self.sperre(None), "")

    def test_boot_ruft_die_sperre_vor_dem_laden_auf(self):
        text = LOADER.read_text(encoding="utf-8")
        self.assertLess(text.index("shellSperre(manifest.shell)"), text.index("manifest.shell.js) await addScript"))


class Csp(unittest.TestCase):
    def test_rahmenrichtlinie(self):
        teile = {t.split(" ", 1)[0]: t.split(" ", 1)[1] for t in uix_server.RAHMEN_CSP.split("; ")}
        self.assertEqual(teile["default-src"], "'none'")
        self.assertEqual(teile["connect-src"], "'none'")
        self.assertEqual(teile["form-action"], "'none'")
        self.assertEqual(teile["frame-src"], "'none'")
        self.assertEqual(teile["worker-src"], "'none'")
        self.assertEqual(teile["base-uri"], "'none'")
        self.assertEqual(teile["frame-ancestors"], "'self'")
        self.assertEqual(teile["script-src"], "'self'")
        self.assertNotIn("unsafe-inline", teile["script-src"])

    def test_nur_die_rahmenseite_nutzt_sie(self):
        quelle = Path(uix_server.__file__).read_text(encoding="utf-8")
        self.assertEqual(quelle.count("csp=RAHMEN_CSP"), 1)
        self.assertIn("frame_self=True, csp=RAHMEN_CSP", quelle)


if __name__ == "__main__":
    unittest.main()
