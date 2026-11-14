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
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_keine_hardcodierten_strings(self):
        js = (UIX_DIR / 'js' / 'sprache_wahl.js').read_text(encoding='utf-8')
        self.assertIn('STRINGS_DE', js)
        self.assertIn('STRINGS_EN', js)
        self.assertIn('function t(', js)

    def test_sprache_umschalten(self):
        out = _run(['sprache_wahl.js'], '''console.log(JSON.stringify(box.spracheUmschalten('en')));''')
        self.assertEqual(out['code'], 'en')
        out2 = _run(['sprache_wahl.js'], '''console.log(JSON.stringify(box.t('lbl_sedra')));''')
        self.assertEqual(out2, 'SEDRA')
        out3 = _run(['sprache_wahl.js'], '''box.spracheUmschalten('de');console.log(JSON.stringify(box.t('lbl_sedra')));''')
        self.assertEqual(out3, 'SEDRA')

    def test_standardsprache_de(self):
        out = _run(['sprache_wahl.js'], '''console.log(JSON.stringify(box.spracheAktuell()));''')
        self.assertEqual(out['code'], 'de')
        self.assertEqual(out['name'], 'Deutsch')

    def test_alle_strings_bereitschaft(self):
        out = _run(['sprache_wahl.js'], '''console.log(JSON.stringify(box.alleStringsBereit()));''')
        self.assertTrue(out['bereit'])
        self.assertEqual(out['fehlend'], [])

    def test_sprache_in_einstellungen(self):
        out = _run(['sprache_wahl.js'], '''console.log(JSON.stringify(box.t('lbl_sprache') + ' | ' + box.t('lbl_deutsch') + ' | ' + box.t('lbl_englisch')));''')
        self.assertEqual(out, 'Sprache | Deutsch | Englisch')
        out2 = _run(['sprache_wahl.js'], '''box.spracheUmschalten('en');console.log(JSON.stringify(box.t('lbl_sprache') + ' | ' + box.t('lbl_deutsch') + ' | ' + box.t('lbl_englisch')));''')
        self.assertEqual(out2, 'Language | German | English')


if __name__ == '__main__':
    unittest.main()
