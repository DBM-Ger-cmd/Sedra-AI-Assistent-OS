"""X5 Sprache DE/EN: keine hardcodierten Strings, Sprache umschalten, Standard DE,
alle Strings in beiden Sprachen, Sprache in Einstellungen. Rein (node, vm)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

UIX_DIR = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix'
NODE = shutil.which('node')


def _run(script_names, probe):
    js = '\n'.join((UIX_DIR / 'js' / n).read_text(encoding='utf-8') for n in script_names)
    head = "const vm=require('vm');const box={};vm.createContext(box);vm.runInContext(process.argv[1],box);"
    run = subprocess.run([NODE, '-e', head + probe, js], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr)
    return json.loads(run.stdout)


class SpracheTest(unittest.TestCase):
    """Die Textlisten und `t()` der Harness-Shell (shells/harness/strings_de.js, strings_en.js, i18n.js). Die alten Retro-Bausteine
    (uix/js/sprache_wahl.js, strings_*.json) sind entfernt; der Server liefert unter /uix/js nur js und css, die JSON-Dateien wurden nie geladen."""

    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def _harness(self, probe):
        h = UIX_DIR / 'shells' / 'harness'
        code = ("const vm=require('vm');const fs=require('fs');const box={localStorage:{getItem(){return null;},setItem(){}}};vm.createContext(box);"
                + "".join(f"vm.runInContext(fs.readFileSync({str(h / n)!r},'utf-8'),box);" for n in ('strings_de.js', 'strings_en.js', 'i18n.js')) + probe)
        run = subprocess.run([NODE, '-e', code], capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_standard_deutsch_und_umschalten_ohne_neustart(self):
        out = self._harness("console.log(JSON.stringify([box.t('lbl_sprache'), box.sedraI18n.spracheUmschalten('en').ok, box.t('lbl_sprache'), "
                            "box.sedraI18n.spracheUmschalten('de').ok, box.t('lbl_sprache')]));")
        self.assertEqual(out, ['Sprache', True, 'Language', True, 'Sprache'])

    def test_fehlender_schluessel_zeigt_den_deutschen_text_oder_den_schluessel(self):
        out = self._harness("box.sedraI18n.spracheUmschalten('en');console.log(JSON.stringify([box.t('gibt_es_nicht'), box.t('lbl_sprache')]));")
        self.assertEqual(out[0], 'gibt_es_nicht')
        self.assertEqual(out[1], 'Language')

    def test_unbekannte_sprache_wird_abgelehnt(self):
        out = self._harness("console.log(JSON.stringify(box.sedraI18n.spracheUmschalten('fr').ok));")
        self.assertFalse(out)

    def test_alte_retro_bausteine_sind_weg(self):
        for name in ('sprache_wahl.js', 'strings_de.json', 'strings_en.json'):
            self.assertFalse((UIX_DIR / 'js' / name).exists(), name)
        self.assertNotIn('sprache_wahl', (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8'))

    def test_string_dateien_gleiche_schluessel(self):
        """X5-01 / X5-04: strings_de.js und strings_en.js haben identische Schlüssel."""
        node = shutil.which('node')
        self.assertIsNotNone(node, 'node ist nicht installiert')
        head = "const vm=require('vm');const box={};vm.createContext(box);"
        de_js = UIX_DIR / 'shells' / 'harness' / 'strings_de.js'
        en_js = UIX_DIR / 'shells' / 'harness' / 'strings_en.js'
        self.assertTrue(de_js.is_file(), 'strings_de.js fehlt')
        self.assertTrue(en_js.is_file(), 'strings_en.js fehlt')
        probe = (
            "const fs=require('fs');"
            "const de=fs.readFileSync(" + repr(str(de_js)) + ",'utf-8');"
            "const en=fs.readFileSync(" + repr(str(en_js)) + ",'utf-8');"
            "vm.runInContext(de,box);vm.runInContext(en,box);"
            "const S=box.sedraI18nStrings||{};"
            "const dk=Object.keys(S.de||{}).sort();"
            "const ek=Object.keys(S.en||{}).sort();"
            "console.log(JSON.stringify({de:dk,en:ek}));"
        )
        run = subprocess.run([node, '-e', head + probe],
                             capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        aus = json.loads(run.stdout)
        self.assertEqual(aus['de'], aus['en'], 'DE und EN müssen identische Schlüssel haben')
        self.assertGreater(len(aus['de']), 0, 'mindestens ein String muss vorhanden sein')


if __name__ == '__main__':
    unittest.main()
