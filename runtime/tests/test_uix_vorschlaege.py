"""X4 Vorschläge aus Dateien und Vorlagen für die Palette. Rein (node, vm)."""
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


class VorschlaegeTest(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_dateivorschlag_mit_vorschau(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.vorschlaege('vorar').map(v=>({id:v.id,titel:v.titel,vorschau:v.vorschau}))));''')
        ids = [v['id'] for v in out]
        self.assertIn('vorarbeiter', ids)

    def test_vorlage_vorschlag_laden(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.vorschlaege('master').map(v=>v.aktion)));''')
        self.assertIn('vorlage_laden', out)

    def test_rechtsklick_module(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.VORLAGEN.includes('rueckblick')));''')
        self.assertTrue(out)


if __name__ == '__main__':
    unittest.main()
