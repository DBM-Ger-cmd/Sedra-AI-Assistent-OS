"""App Coder, Entscheidung E5: das Terminal führt keine echten Befehle aus. Es zeigt nur, was der Coder schon geladen hat.
Der Vertrag steht im Quelltext: kein Aufruf des Servers, kein Netz, keine Ausführung von Text; die Befehle sind eine feste Liste."""
import re
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "src/sedra_runtime/uix/tools/coder"
PANEL = (TOOL / "panel.js").read_text(encoding="utf-8")
BEFEHLE = {"hilfe", "help", "ls", "dir", "cat", "type", "open", "oeffne", "echo", "status", "agenten", "clear", "cls"}


class Terminal(unittest.TestCase):
    def test_panel_ruft_weder_server_noch_netz(self):
        for verboten in ("ctx.api", "fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "eval(", "Function(", "innerHTML", "localStorage"):
            self.assertNotIn(verboten, PANEL, verboten)

    def test_feste_befehlsliste(self):
        koerper = PANEL.split("function fuehre(zeile)")[1].split("function terminal()")[0]
        gefunden = set(re.findall(r"b === '([a-z]+)'", koerper))
        self.assertEqual(gefunden, BEFEHLE)

    def test_unbekanntes_wird_nur_gemeldet(self):
        self.assertIn("tm_unbekannt_echt", PANEL)
        for sprache in ("de", "en"):
            text = (TOOL / f"texte_{sprache}.js").read_text(encoding="utf-8")
            for key in ("tm_gruss_echt", "tm_unbekannt_echt", "tm_erst_oeffnen", "tm_ls_hinweis"):
                self.assertIn(key + ":", text, (sprache, key))
            self.assertNotIn("Attrappe", re.search(r"tm_gruss_echt: '[^']*'", text).group(0))


if __name__ == "__main__":
    unittest.main()
