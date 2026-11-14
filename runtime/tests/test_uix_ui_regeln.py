"""X4/X5 UI-Regeln: keine Hex-Farben in Shell-CSS, textContent statt innerHTML,
setInterval nur in Taskleiste/Start-Menü, Dateien höchstens 400 Zeilen. Rein."""
import json
import re
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


class UITest(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_keine_hex_farben(self):
        for name in ('command.js', 'sprache_wahl.js'):
            js = (UIX_DIR / 'js' / name).read_text(encoding='utf-8')
            hex_farben = re.findall(r'#[0-9a-fA-F]{3,6}', js)
            self.assertEqual(hex_farben, [], 'Hex-Farben in ' + name + ': ' + str(hex_farben))

    def test_textcontent_statt_innerhtml(self):
        for name in ('command.js', 'sprache_wahl.js'):
            js = (UIX_DIR / 'js' / name).read_text(encoding='utf-8')
            self.assertNotIn('innerHTML', js, name + ' enthält innerHTML')

    def test_setinterval_nur_taskleiste_startmenue(self):
        for name in ('command.js', 'sprache_wahl.js'):
            js = (UIX_DIR / 'js' / name).read_text(encoding='utf-8')
            self.assertNotIn('setInterval', js, name + ' enthält setInterval')

    def test_dateien_max_400_zeilen(self):
        for name in ('command.js', 'core.js', 'desktop.js', 'sprache_wahl.js'):
            text = (UIX_DIR / 'js' / name).read_text(encoding='utf-8')
            zeilen = len(text.splitlines())
            self.assertLessEqual(zeilen, 400, name + ': ' + str(zeilen) + ' Zeilen')

    def test_sprachdateien_vorhanden(self):
        de = UIX_DIR / 'js' / 'strings_de.json'
        en = UIX_DIR / 'js' / 'strings_en.json'
        self.assertTrue(de.is_file(), 'strings_de.json fehlt')
        self.assertTrue(en.is_file(), 'strings_en.json de fehlt')
        import json as _json
        _json.loads(de.read_text(encoding='utf-8'))
        _json.loads(en.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
