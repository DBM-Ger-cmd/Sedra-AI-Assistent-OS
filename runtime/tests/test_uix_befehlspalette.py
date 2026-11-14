"""X4 Befehlspalette: öffnen, Befehle auflisten, Suche filtern, Befehl ausführen,
Schreibwerkzeug ohne Freigabe → Antrag, Schreibwerkzeug mit Freigabe → Ausführung,
Vorschläge, Historie. Rein (node, vm), keine Browser-Tests."""
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


class BefehlspaletteTest(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_palette_oeffnen_per_kuerzel(self):
        out = _run(['command.js'], '''console.log(JSON.stringify({k: box.KUERZEL.find(k=>k.aktion==='palette öffnen').kuerzel}));''')
        self.assertEqual(out['k'], 'Strg+K')

    def test_palette_listet_befehle(self):
        out_deck = _run(['command.js'], '''console.log(JSON.stringify(box.matchCommands('deck').map(c=>c.id)));''')
        self.assertIn('deck', out_deck)
        out_chat = _run(['command.js'], '''console.log(JSON.stringify(box.matchCommands('chat').map(c=>c.id)));''')
        self.assertIn('chat', out_chat)
        out_models = _run(['command.js'], '''console.log(JSON.stringify(box.matchCommands('modell').map(c=>c.id)));''')
        self.assertIn('models', out_models)

    def test_palette_suche_filtert(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.matchCommands('modell').map(c=>c.id)));''')
        treffer = out
        self.assertIn('models', treffer)
        self.assertIn('model_add', treffer)

    def test_befehl_ausfuehren(self):
        out = _run(['command.js'], '''const r=box.routeCommand('neues modell');console.log(JSON.stringify({kind:r.kind,id:r.id}));''')
        self.assertEqual((out['kind'], out['id']), ('command', 'model_add'))

    def test_schreibwerkzeug_ohne_freigabe_ablehnen(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.schreibwerkzeugAntrag('datei_schreiben','schreib was')));''')
        self.assertTrue(out['gate_required'])
        self.assertEqual(out['befehlId'], 'datei_schreiben')
        self.assertIn('Freigabe', out['hinweis'])

    def test_schreibwerkzeug_mit_freigabe_ausfuehren(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.schreibwerkzeugAusfuehren('datei_schreiben', true)));''')
        self.assertTrue(out['ausgefuehrt'])
        self.assertFalse(out['gate_required'])

        out2 = _run(['command.js'], '''console.log(JSON.stringify(box.schreibwerkzeugAusfuehren('datei_schreiben', false)));''')
        self.assertFalse(out2['ausgefuehrt'])
        self.assertTrue(out2['gate_required'])

    def test_schreibwerkzeug_erkannt(self):
        out = _run(['command.js'], '''console.log(JSON.stringify({schreiben:box.befehlIstSchreibwerkzeug('datei_schreiben'),aendern:box.befehlIstSchreibwerkzeug('datei_aendern'),desktop:box.befehlIstSchreibwerkzeug('desktop_aendern'),lesen:box.befehlIstSchreibwerkzeug('datei_lesen')}));''')
        self.assertTrue(out['schreiben'])
        self.assertTrue(out['aendern'])
        self.assertTrue(out['desktop'])
        self.assertFalse(out['lesen'])

    def test_vorschlaege_in_palette(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.vorschlaege('bau').map(v=>v.id)));''')
        self.assertIn('bauagent', out)

    def test_historie_letzte_befehle(self):
        out = _run(['command.js'], '''box.histHinzufuegen('deck');box.histHinzufuegen('chat');box.histHinzufuegen('models');console.log(JSON.stringify(box.historie()));''')
        self.assertEqual(out, ['models', 'chat', 'deck'])

    def test_historie_max_10(self):
        out = _run(['command.js'], '''for(let i=0;i<15;i++)box.histHinzufuegen('b'+i);console.log(JSON.stringify(box.historie().length));''')
        self.assertEqual(out, 10)

    def test_kuerzel_doppelt_erkannt(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.kuerzelPruefen([{kuerzel:'x',key:'k',ctrl:true,aktion:'a'},{kuerzel:'x',key:'k',ctrl:true,aktion:'b'}])));''')
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['kuerzel'], 'Strg+K')

    def test_kuerzel_keine_doppelbelegung_im_default(self):
        out = _run(['command.js'], '''console.log(JSON.stringify(box.kuerzelPruefen()));''')
        self.assertEqual(len(out), 0)


if __name__ == '__main__':
    unittest.main()
