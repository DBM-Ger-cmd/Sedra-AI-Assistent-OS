"""Anzeige des Wissens im Chat von One Sedra (SPEC_WISSEN_KERN_v1 WK-14, WK-15, WK-13; G2 K1K2 §3.4): die Zeile „Aus dem Wissen“ unter
der Antwort entsteht rein aus den Daten (Kennungen, genannte, fremde, Hinweis), Text nur über sedraDom.el (nie HTML); ohne Kennungen keine
Zeile; der Block ohne Modell; der Schalter „Wissen zuerst“ steht in den Gesprächsoptionen. Node mit einem kleinen DOM-Ersatz, kein Browser."""
import unittest
from pathlib import Path

from test_uix_contract import NODE, run_js

HARNESS = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness'
DOM = """
  box.sedraDom = {el(tag, cls, text){
    const n = {tag, cls: cls || '', text: text === undefined ? '' : String(text), kinder: [], title: '', type: '', onclick: null,
               append(...k){ this.kinder.push(...k); }};
    Object.defineProperty(n, 'childNodes', {get(){ return n.kinder; }});
    return n;
  }};
  const flach = n => n ? {tag: n.tag, cls: n.cls, text: n.text, kinder: n.kinder.map(flach)} : null;
"""


@unittest.skipUnless(NODE, 'node fehlt')
class Zeile(unittest.TestCase):
    def lauf(self, probe):
        return run_js([HARNESS / 'zeilen.js'], DOM + probe)

    def test_fundstellen_genannt_und_fremd(self):
        out = self.lauf("""
          const Z = box.sedraHarness.zeilen;
          const z = Z.wissenZeile({ids: ['Wa', 'Wb'], belegt: ['Wa'], fremd: ['Wx'], hinweis: 'Nur Volltextsuche'}, ()=>{});
          console.log(JSON.stringify(flach(z)));
        """)
        self.assertIn('warn', out['cls'])
        self.assertEqual(out['kinder'][0]['text'], '▣ Aus dem Wissen: 2 Fundstellen · 1 Kennung nicht aus dem Wissen')
        body = out['kinder'][1]['kinder']
        self.assertEqual([(k['text'], 'belegt' in k['cls']) for k in body[:2]], [('Wa', True), ('Wb', False)])
        self.assertIn('Nicht aus dem Wissen: Wx', body[2]['text'])
        self.assertEqual(body[3]['text'], 'Nur Volltextsuche')
        self.assertEqual(body[4]['text'], 'Im Wissen öffnen')

    def test_ohne_kennungen_keine_zeile_und_ende_haengt_sie_an(self):
        out = self.lauf("""
          const Z = box.sedraHarness.zeilen;
          const leer = Z.wissenZeile({ids: [], fremd: []});
          const block = box.sedraDom.el('div', 'hs-antwort');
          Z.ende(block, {ende: 'antwort', zuege: 1, wissen: {ids: ['Wa'], belegt: [], fremd: []}}, null);
          const ohne = box.sedraDom.el('div', 'hs-antwort');
          Z.ende(ohne, {ende: 'antwort', zuege: 1});
          console.log(JSON.stringify({leer, klassen: block.kinder.map(k=>k.cls), ohne: ohne.kinder.map(k=>k.cls),
                                      einzahl: block.kinder[1].kinder[0].text, knopf: block.kinder[1].kinder[1].kinder.length}));
        """)
        self.assertIsNone(out['leer'])
        self.assertEqual(out['klassen'], ['hs-fuss', 'hs-wissen'])
        self.assertEqual(out['ohne'], ['hs-fuss'])
        self.assertEqual(out['einzahl'], '▣ Aus dem Wissen: 1 Fundstelle')
        self.assertEqual(out['knopf'], 1, 'ohne Rückruf kein Knopf')

    def test_block_ohne_modell(self):
        out = self.lauf("""
          const b = box.sedraHarness.zeilen.wissenBlock('Das habe ich im Wissen gefunden: [Wa] <b>x</b>');
          console.log(JSON.stringify(flach(b)));
        """)
        self.assertEqual(out['kinder'][1]['text'], 'Das habe ich im Wissen gefunden: [Wa] <b>x</b>', 'Text bleibt Text')
        self.assertIn('Kein Modell geladen', out['kinder'][0]['text'])

    def test_schalter_in_den_gespraechsoptionen(self):
        out = run_js([HARNESS / 'tokenseite.js', HARNESS / 'gespraechsoptionen.js'],
                     DOM + "console.log(JSON.stringify(box.sedraHarness.gespraechsoptionen.zeilen().map(z=>[z.schluessel, z.wahl.map(w=>w[0])])));")
        self.assertIn(['wissen_zuerst', ['an', 'aus']], out)


class Quelltext(unittest.TestCase):
    def test_kein_innerhtml_und_hoechstens_400_zeilen(self):
        for name in ('zeilen.js', 'verlauf.js', 'gespraechsoptionen.js'):
            text = (HARNESS / name).read_text(encoding='utf-8')
            self.assertNotIn('innerHTML', text, name)
            self.assertLessEqual(len(text.splitlines()), 400, name)


if __name__ == '__main__':
    unittest.main()
