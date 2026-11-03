"""Der gelbe Hinweis einer Vorlage (MasterChat) ist einklappbar (03.11.2026): Kopfzeile als Knopf, der Text darunter; die Wahl wird je Vorlage gemerkt (vorlagenhinweis.js, mit node)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells' / 'harness' / 'vorlagenhinweis.js'

KOPF = """
const speicher = {};
globalThis.localStorage = {getItem: k=>(k in speicher ? speicher[k] : null), setItem: (k, v)=>{ speicher[k] = String(v); }, removeItem: k=>{ delete speicher[k]; }};
function el(tag, klasse, text){
  const e = {tag, kinder: [], hidden: false, textContent: text || '', attrs: {}, _k: new Set(klasse ? klasse.split(' ') : []),
    classList: {toggle: (k, an)=>{ (an === undefined ? !e._k.has(k) : an) ? e._k.add(k) : e._k.delete(k); }, contains: k=>e._k.has(k)},
    setAttribute(k, v){ e.attrs[k] = v; }, append(...c){ e.kinder.push(...c); }, replaceChildren(...c){ e.kinder = c; }};
  return e;
}
globalThis.sedraDom = {el};
require(%s);
const V = globalThis.sedraHarness.vorlagenhinweis;
const S = {vorlagen: [{id: 'masterchat', name: 'MasterChat', hinweis: 'Der MasterChat dient zur Anpassung.', erlaubnisse: [{werkzeug: 'datei_schreiben', muster: 'docs/**'}]},
                      {id: 'frei', name: 'Frei', hinweis: '', erlaubnisse: []}],
           _eingabe: {vorlage: {value: 'masterchat'}, vorlageHinweis: el('div', 'hs-vorlage-hinweis')}};
const zustand = ()=>{ const b = S._eingabe.vorlageHinweis, kopf = b.kinder[0], text = b.kinder[1]; return {hidden: b.hidden, warn: b.classList.contains('warn'), zu: b.classList.contains('zu'), kopf: kopf && kopf.textContent, expanded: kopf && kopf.attrs['aria-expanded'], textHidden: text && text.hidden, text: text && text.textContent}; };
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class HinweisKlappen(unittest.TestCase):
    def node(self, code):
        r = subprocess.run(['node', '-e', KOPF % json.dumps(str(JS)) + code], capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_standardmaessig_aufgeklappt_und_ein_klick_klappt_zu_und_wieder_auf(self):
        out = self.node("""
V.zeigen(S);
const offen = zustand();
S._eingabe.vorlageHinweis.kinder[0].onclick();
const zu = zustand();
S._eingabe.vorlageHinweis.kinder[0].onclick();
console.log(JSON.stringify({offen, zu, wieder: zustand()}));
""")
        self.assertEqual((out['offen']['zu'], out['offen']['textHidden'], out['offen']['expanded']), (False, False, 'true'))
        self.assertEqual(out['offen']['text'], 'Der MasterChat dient zur Anpassung.')
        self.assertTrue(out['offen']['warn'])
        self.assertEqual((out['zu']['zu'], out['zu']['textHidden'], out['zu']['expanded']), (True, True, 'false'))
        self.assertIn('Hinweis anzeigen', out['zu']['kopf'])
        self.assertEqual((out['wieder']['zu'], out['wieder']['textHidden']), (False, False))

    def test_zugeklappt_bleibt_es_beim_naechsten_mal(self):
        out = self.node("""
V.zeigen(S);
S._eingabe.vorlageHinweis.kinder[0].onclick();
V.zeigen(S);                                   // z. B. nach dem Wechsel der Vorlage und zurück
console.log(JSON.stringify(zustand()));
""")
        self.assertEqual((out['zu'], out['textHidden']), (True, True))

    def test_ohne_hinweistext_ist_nichts_zu_sehen(self):
        out = self.node("""
S._eingabe.vorlage.value = 'frei';
V.zeigen(S);
console.log(JSON.stringify(zustand()));
""")
        self.assertTrue(out['hidden'])
        self.assertNotIn('kopf', out)


if __name__ == '__main__':
    unittest.main()
