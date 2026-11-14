"""X4 Tastaturkürzel: globale Kürzel, Builder-Kürzel, Doppelbelegung, Überschreiben-Warnung, Barrierefreiheit.
Rein (node, vm), keine Browser-Tests."""
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


class TastaturKuerzelTest(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_globale_kuerzel(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.KUERZEL.filter(k=>!k.builder).map(k=>k.kuerzel)));''')
        self.assertIn('Strg+K', out)
        self.assertIn('Esc', out)
        self.assertIn('Strg+S', out)

    def test_builder_kuerzel(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.KUERZEL.filter(k=>k.builder).map(k=>k.aktion)));''')
        self.assertIn('rückgängig', out)
        self.assertIn('wiederholen', out)

    def test_kuerzel_doppelt_erkannt(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.kuerzelPruefen([{key:'k',ctrl:true,aktion:'a'},{key:'k',ctrl:true,aktion:'b'}])));''')
        self.assertEqual(len(out), 1)

    def test_kuerzel_ueberschreiben_warnt(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.kuerzelPruefen(box.KUERZEL.concat([{key:'k',ctrl:true,aktion:'neu belegt'}]))));''')
        self.assertEqual(len(out), 1)

    def test_kuerzel_barrierefrei(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.KUERZEL.every(k=>k.aktion && k.beschreibung)));''')
        self.assertTrue(out)


if __name__ == '__main__':
    unittest.main()
