"""App Coder, Editorkern. Das Textmodell und die Auswahlen laufen in Node (kern_pruefung.js, ohne Browser); der Vertrag der Dateien steht im Quelltext:
alles bleibt im Text des Editors (kein Server, kein Netz, kein Speicher des Browsers), die Tasten sind die dokumentierten, die Texte gibt es in beiden Sprachen."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "src/sedra_runtime/uix/tools/coder"
NODE = shutil.which("node")
KERN = ("kern_modell.js", "kern_auswahl.js", "kern_ansicht.js", "kern_eingabe.js", "komfort.js")
QUELLEN = {n: (TOOL / n).read_text(encoding="utf-8") for n in KERN}


class Kern(unittest.TestCase):
    @unittest.skipUnless(NODE, "node nicht installiert")
    def test_modell_und_auswahlen_in_node(self):
        r = subprocess.run([NODE, str(Path(__file__).with_name("kern_pruefung.js")), str(TOOL)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kern ok", r.stdout)

    def test_bleibt_im_editor(self):
        for name, text in QUELLEN.items():
            for verboten in ("ctx.api", "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "eval(", "Function(", "innerHTML", "localStorage", "sessionStorage", "outerHTML", "insertAdjacentHTML"):
                self.assertNotIn(verboten, text, f"{name}: {verboten}")

    def test_tasten_des_editors(self):
        eingabe = QUELLEN["kern_eingabe.js"]
        for fest in ("Enter", "Backspace", "Delete", "Tab", "Escape", "ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End",
                     "naechstesVorkommen", "alleVorkommen", "zeileLoeschen", "kommentar", "cursorDazu", "zeileVerschieben", "zeileDoppeln", "faltUm", "umbruchUm"):
            self.assertIn(fest, eingabe, fest)

    def test_texte_in_beiden_sprachen(self):
        for sprache in ("de", "en"):
            text = (TOOL / f"texte_{sprache}.js").read_text(encoding="utf-8")
            for key in re.findall(r"T\('(kf_[a-z_]+)'", QUELLEN["komfort.js"]) + ["ed_umbruch_an", "ed_umbruch_aus", "bf_umbruch", "bf_faltAlleZu", "bf_faltAlleAuf"]:
                self.assertIn(key + ":", text, (sprache, key))

    def test_strg_f_oeffnet_die_suche_in_der_datei_und_die_reihenfolge_stimmt(self):
        befehle = (TOOL / "befehle.js").read_text(encoding="utf-8")
        self.assertIn("S.komfort.finde()", befehle)
        yaml = (TOOL / "tool.yaml").read_text(encoding="utf-8")
        reihe = [yaml.index(n) for n in ("kern_modell.js", "kern_auswahl.js", "kern_ansicht.js", "kern_eingabe.js", "editor.js", "komfort.js")]
        self.assertEqual(reihe, sorted(reihe), "Kern vor Editor vor Suchleiste")

    def test_editor_hat_keine_textflaeche_mehr(self):
        editor = (TOOL / "editor.js").read_text(encoding="utf-8")
        self.assertNotIn("selectionStart", editor)
        self.assertNotIn("setRangeText", editor)
        self.assertIn("K.ansicht(", editor)


if __name__ == "__main__":
    unittest.main()
