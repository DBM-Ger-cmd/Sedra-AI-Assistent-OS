"""Zwei Fehlerarten der Übersetzungsumstellung (X5), die der Browser-Durchlauf `test_uix_harness_browser` erst spät zeigte (16.11.2026), hier ohne Browser:
1. Eine Datei der Harness-Shell ruft `T('schluessel')` auf und überdeckt `T` irgendwo mit einem Objekt (`const T = root.sedraHarness.taskleiste`): „T is not a function“ bei jedem Aufruf.
2. Code setzt Klammern um einen Text, der sie schon trägt (`' (' + T('karte_vorarbeiter') + ')'` bei `karte_vorarbeiter:'(Vorarbeiter)'`): „Erlaubt ((Vorarbeiter))“."""
import re
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "shells" / "harness"
RUFT_T = re.compile(r"(?<![A-Za-z0-9_.$'\"])T\('")
T_ALS_OBJEKT = re.compile(r"\b(?:const|let|var)\s+T\s*=\s*root\.sedraHarness\.")
KLAMMER_UM_T = re.compile(r"'\s\('\s*\+\s*T\('([a-z0-9_]+)'\)\s*\+\s*'\)'")
STRING = re.compile(r"^\s*([a-z0-9_]+):\s*'([^']*)'", re.M)


class Uebersetzung(unittest.TestCase):
    def test_t_wird_nirgends_mit_einem_objekt_ueberdeckt(self):
        fehler = []
        for datei in sorted(HARNESS.glob("*.js")):
            text = datei.read_text(encoding="utf-8")
            if RUFT_T.search(text) and T_ALS_OBJEKT.search(text):
                fehler.append(datei.name)
        self.assertEqual(fehler, [], "diese Dateien rufen T('…') auf und setzen T zugleich auf ein Harness-Objekt (anderen Namen wählen, z. B. TL)")

    def test_keine_doppelten_klammern_um_texte_mit_klammern(self):
        texte = {}
        for name in ("strings_de2.js", "strings_en2.js"):
            texte[name] = dict(STRING.findall((HARNESS / name).read_text(encoding="utf-8")))
        fehler = []
        for datei in sorted(HARNESS.glob("*.js")):
            for schluessel in KLAMMER_UM_T.findall(datei.read_text(encoding="utf-8")):
                for name, werte in texte.items():
                    wert = werte.get(schluessel)
                    if wert is not None and wert.startswith("(") and wert.endswith(")"):
                        fehler.append(f"{datei.name}: '{schluessel}' in {name} = {wert!r}")
        self.assertEqual(fehler, [], "Klammern stehen schon im Text, der Code darf sie nicht noch einmal setzen")

    def test_die_beiden_regeln_finden_den_alten_fehler(self):
        """Gegenprobe: die Muster erkennen die beiden Fehler wirklich."""
        self.assertTrue(T_ALS_OBJEKT.search("    const T = root.sedraHarness.taskleiste;"))
        self.assertTrue(RUFT_T.search("tab.title = x + T('sl_antwort_laeuft');"))
        self.assertFalse(RUFT_T.search("const x = foo.T('a');"))
        self.assertEqual(KLAMMER_UM_T.findall("(vorarbeiter ? ' (' + T('karte_vorarbeiter') + ')' : '')"), ["karte_vorarbeiter"])


if __name__ == "__main__":
    unittest.main()
