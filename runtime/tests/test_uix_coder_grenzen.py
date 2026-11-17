"""App Coder, Ausbau der bekannten Grenzen: mehrere Projekte, gemerkter Zustand, Schriftgröße. Der Vertrag steht im Quelltext."""
import re
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "src/sedra_runtime/uix/tools/coder"
MERKEN = (TOOL / "merken_echt.js").read_text(encoding="utf-8")


class Grenzen(unittest.TestCase):
    def test_merken_ruft_nur_die_zustandsroute(self):
        for verboten in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "eval(", "innerHTML"):
            self.assertNotIn(verboten, MERKEN, verboten)
        self.assertEqual(re.findall(r"'(zustand)'\]\.join", MERKEN), ["zustand"])

    def test_dateitext_wird_nie_gemerkt(self):
        koerper = MERKEN.split("const zustand = {")[1].split("try { await")[0]
        for feld in ("projekt", "schrift", "weg", "chat", "verlauf", "antraege"):
            self.assertIn(feld + ":", koerper)
        for verboten in ("inhalt", "S.dateien", "gespeichert"):
            self.assertNotIn(verboten, koerper, verboten)

    def test_texte_in_beiden_sprachen(self):
        quellen = "".join((TOOL / n).read_text(encoding="utf-8") for n in ("merken_echt.js", "verwalten_echt.js", "echt.js", "befehle.js"))
        for sprache in ("de", "en"):
            text = (TOOL / f"texte_{sprache}.js").read_text(encoding="utf-8")
            for key in sorted(set(re.findall(r"T\('((?:pj|mk|schrift)_[a-z_]+)'", quellen)) | {"bf_schriftGroesser", "bf_schriftKleiner", "bf_schriftStandard"}):
                self.assertIn(key + ":", text, (sprache, key))

    def test_editor_hat_keine_feste_zeilenhoehe_mehr(self):
        editor = (TOOL / "editor.js").read_text(encoding="utf-8")
        self.assertNotRegex(editor, r"\bLH\b")
        self.assertIn("merken_echt.js", (TOOL / "tool.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
