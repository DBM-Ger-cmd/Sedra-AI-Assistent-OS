"""X4 Harness-Shell: Befehlspalette (Strg+K) und Tastaturkürzel für die Harness-Overlay-Eingabe.

Reine Teile (node, vm): Zeilenbau, Suche, Schreibwerkzeug-Antrag, Kürzel-Tabelle, Historie.
UI-Regeln: keine Hex-Farben in palette.css, kein innerHTML/setInterval in palette.js,
Dateien <= 400 Zeilen.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

UIX_DIR = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix'
PALETTE_JS = UIX_DIR / 'shells' / 'harness' / 'palette.js'
PALETTE_CSS = UIX_DIR / 'shells' / 'harness' / 'palette.css'
NODE = shutil.which('node')

P = 'box.sedraHarness.palette'


def _run(probe):
    js = PALETTE_JS.read_text(encoding='utf-8')
    head = "const vm=require('vm');const box={};vm.createContext(box);vm.runInContext(process.argv[1],box);"
    run = subprocess.run([NODE, '-e', head + probe, js], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


class HarnessPaletteTests(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_zeilen_listet_shell_aktionen(self):
        out = _run('console.log(JSON.stringify(' + P + '.zeilen("").map(z=>z.id)));')
        self.assertIn('sit_neu', out)
        self.assertIn('posteingang', out)
        self.assertIn('einstellungen', out)
        self.assertIn('startmenue', out)

    def test_zeilen_listet_werkzeuge(self):
        out = _run('console.log(JSON.stringify(' + P + '.zeilen("").map(z=>z.id)));')
        self.assertIn('datei_lesen', out)
        self.assertIn('suchen', out)
        self.assertIn('lauf_status', out)

    def test_zeilen_suche_filtert(self):
        alle = _run('console.log(JSON.stringify(' + P + '.zeilen("").map(z=>z.id)));')
        treffer = _run('console.log(JSON.stringify(' + P + '.zeilen("lesen").map(z=>z.id)));')
        self.assertIn('datei_lesen', treffer)
        self.assertLess(len(treffer), len(alle))

    def test_zeilen_historie_oben(self):
        out = _run(P + '.histHinzufuegen("datei_lesen");' + P + '.histHinzufuegen("sit_neu");console.log(JSON.stringify(' + P + '.zeilen("").map(z=>z.id)));')
        self.assertEqual(out[0], 'hist:sit_neu')
        self.assertEqual(out[1], 'hist:datei_lesen')

    def test_schreibwerkzeug_erkannt(self):
        probe = 'console.log(JSON.stringify({schreiben:' + P + '.befehlIstSchreibwerkzeug("datei_schreiben"),aendern:' + P + '.befehlIstSchreibwerkzeug("datei_aendern"),desktop:' + P + '.befehlIstSchreibwerkzeug("desktop_aendern"),lesen:' + P + '.befehlIstSchreibwerkzeug("datei_lesen")}));'
        out = _run(probe)
        self.assertTrue(out['schreiben'])
        self.assertTrue(out['aendern'])
        self.assertTrue(out['desktop'])
        self.assertFalse(out['lesen'])

    def test_schreibwerkzeug_antrag_gate_required(self):
        out = _run('console.log(JSON.stringify(' + P + '.schreibwerkzeugAntrag("datei_schreiben","inhalt")));')
        self.assertTrue(out['gate_required'])
        self.assertEqual(out['befehlId'], 'datei_schreiben')
        self.assertIn('Freigabe', out['hinweis'])

    def test_schreibwerkzeug_ausfuehren_nach_freigabe(self):
        out = _run('console.log(JSON.stringify(' + P + '.schreibwerkzeugAusfuehren("datei_schreiben", true)));')
        self.assertTrue(out['ausgefuehrt'])
        self.assertFalse(out['gate_required'])
        out2 = _run('console.log(JSON.stringify(' + P + '.schreibwerkzeugAusfuehren("datei_schreiben", false)));')
        self.assertFalse(out2['ausgefuehrt'])
        self.assertTrue(out2['gate_required'])

    def test_historie_max_10(self):
        out = _run('for(let i=0;i<14;i++)' + P + '.histHinzufuegen("b"+i);console.log(JSON.stringify(' + P + '.historie().length));')
        self.assertEqual(out, 10)

    def test_kuerzel_strg_k_registriert(self):
        out = _run('console.log(JSON.stringify(' + P + '.kuerzelListe().map(k=>k.kuerzel)));')
        self.assertIn('Strg+K', out)
        self.assertIn('Esc', out)

    def test_kuerzel_keine_doppelbelegung(self):
        out = _run('console.log(JSON.stringify(' + P + '.kuerzelPruefen()));')
        self.assertEqual(len(out), 0)

    def test_kuerzel_doppelt_erkannt(self):
        probe = 'console.log(JSON.stringify(' + P + '.kuerzelPruefen(' + P + '.kuerzelListe().concat([{key:\'k\',ctrl:true,aktion:\'doppelt\'}]))));'
        out = _run(probe)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['kuerzel'], 'Strg+K')


class PaletteUiRegelnTests(unittest.TestCase):
    def test_keine_hex_farben_in_css(self):
        css = PALETTE_CSS.read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', css), 'kein Hex-Wert in palette.css')

    def test_kein_innerhtml_in_js(self):
        js = PALETTE_JS.read_text(encoding='utf-8')
        self.assertNotIn('innerHTML', js)
        self.assertNotIn('insertAdjacentHTML', js)

    def test_kein_setinterval_in_js(self):
        js = PALETTE_JS.read_text(encoding='utf-8')
        self.assertNotIn('setInterval', js)

    def test_dateien_max_400_zeilen(self):
        for pfad in (PALETTE_JS, PALETTE_CSS):
            zeilen = len(pfad.read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(zeilen, 400, pfad.name + ': ' + str(zeilen) + ' Zeilen')


if __name__ == '__main__':
    unittest.main()
