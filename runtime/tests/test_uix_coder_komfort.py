"""App Coder, Ausbau: Editor-Komfort. Der Vertrag steht im Quelltext: alles bleibt im Text des Editors (kein Server, kein Netz, kein Speicher des Browsers),
die Tasten sind die dokumentierten, und die Texte gibt es in beiden Sprachen."""
import re
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "src/sedra_runtime/uix/tools/coder"
KOMFORT = (TOOL / "komfort.js").read_text(encoding="utf-8")


class Komfort(unittest.TestCase):
    def test_bleibt_im_editor(self):
        for verboten in ("ctx.api", "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "eval(", "Function(", "innerHTML", "localStorage", "sessionStorage"):
            self.assertNotIn(verboten, KOMFORT, verboten)

    def test_tasten(self):
        tasten = set(re.findall(r"^\s{4}'?([A-Za-z/]+)'?: function \(ta, ev\)", KOMFORT, re.M))
        self.assertEqual(tasten, {"Enter", "Backspace", "/", "ArrowUp", "ArrowDown", "K", "k", "d"})

    def test_texte_in_beiden_sprachen(self):
        for sprache in ("de", "en"):
            text = (TOOL / f"texte_{sprache}.js").read_text(encoding="utf-8")
            for key in re.findall(r"T\('(kf_[a-z_]+)'", KOMFORT):
                self.assertIn(key + ":", text, (sprache, key))

    def test_strg_f_oeffnet_die_suche_in_der_datei(self):
        befehle = (TOOL / "befehle.js").read_text(encoding="utf-8")
        self.assertIn("S.komfort.finde()", befehle)
        self.assertIn("komfort.js", (TOOL / "tool.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
