"""Eingabe während der Antwort (03.11.2026): das Feld bleibt frei; Enter merkt die Nachricht vor, sie bleibt bis zum Absenden änderbar und geht raus, sobald die Antwort
der Sitzung fertig ist (eingabe.js, mit node und Attrappen für Feld und Sitzung)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness' / 'eingabe.js'

KOPF = """
globalThis.sedraDom = {};
require(%s);
const E = globalThis.sedraHarness.eingabe;
const knopf = ()=>({hidden: true, textContent: '', classList: {toggle(){}}, setAttribute(){}, title: ''});
function bau(laeuft){
  const gesendet = [];
  const a = {id: 'S-00000001', _l: laeuft, laeuft(){ return this._l; }, async senden(text){ gesendet.push(text); return true; }, stoppen(){ this._l = false; }};
  const feld = {value: '', setAttribute(){}, focus(){}};
  const S = {aktive: ()=>a, _groesse(){}, hinweis(){}, _eingabe: {feld, senden: knopf(), vormerk: knopf(), vorgemerkt: knopf(), projektZeile: {hidden: true}, ordner: null, projekt: {value: ''}, vorlage: {value: ''}, vorschlag: {hidden: true, childNodes: [], replaceChildren(){}}}};
  return {S, a, feld, gesendet};
}
const tick = ()=>new Promise(r=>setTimeout(r, 5));
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class VormerkenTests(unittest.TestCase):
    def node(self, code):
        r = subprocess.run(['node', '-e', KOPF % json.dumps(str(JS)) + code], capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_waehrend_der_antwort_wird_vorgemerkt_und_danach_gesendet(self):
        out = self.node("""
(async()=>{
  const {S, a, feld, gesendet} = bau(true);
  feld.value = 'Ja, setze den Auftrag um.';
  E.zustand(S);
  const knopfDa = !S._eingabe.vormerk.hidden;
  await E.absenden(S);
  const vorgemerkt = !S._eingabe.vorgemerkt.hidden, nochNichts = gesendet.length;
  feld.value = 'Ja, setze den Auftrag um. Committe nichts.';      // solange nicht abgesendet: änderbar
  a._l = false; E.zustand(S); await tick();
  console.log(JSON.stringify({knopfDa, vorgemerkt, nochNichts, gesendet, danachVersteckt: S._eingabe.vorgemerkt.hidden, feldLeer: feld.value === ''}));
})();
""")
        self.assertTrue(out['knopfDa'])
        self.assertTrue(out['vorgemerkt'])
        self.assertEqual(out['nochNichts'], 0)
        self.assertEqual(out['gesendet'], ['Ja, setze den Auftrag um. Committe nichts.'])
        self.assertTrue(out['danachVersteckt'])
        self.assertTrue(out['feldLeer'])

    def test_zuruecknehmen_und_leeren_heben_die_vormerkung_auf(self):
        out = self.node("""
(async()=>{
  const {S, a, feld, gesendet} = bau(true);
  feld.value = 'später';
  await E.absenden(S);
  E.vormerken(S, false);
  a._l = false; E.zustand(S); await tick();
  const nachRuecknahme = gesendet.length, textBleibt = feld.value;
  const zwei = bau(true);
  zwei.feld.value = 'x'; await E.absenden(zwei.S);
  zwei.feld.value = ''; zwei.a._l = false; E.zustand(zwei.S); await tick();
  console.log(JSON.stringify({nachRuecknahme, textBleibt, leer: zwei.gesendet.length}));
})();
""")
        self.assertEqual((out['nachRuecknahme'], out['textBleibt'], out['leer']), (0, 'später', 0))

    def test_eine_andere_sitzung_nimmt_die_vormerkung_nicht_mit(self):
        out = self.node("""
(async()=>{
  const {S, a, feld, gesendet} = bau(true);
  feld.value = 'für S1';
  await E.absenden(S);
  const b = {id: 'S-00000002', laeuft(){ return false; }, async senden(t){ gesendet.push(t); return true; }};
  S.aktive = ()=>b; E.zustand(S); await tick();
  console.log(JSON.stringify({gesendet, vorgemerkt: !S._eingabe.vorgemerkt.hidden, text: feld.value}));
})();
""")
        self.assertEqual((out['gesendet'], out['vorgemerkt'], out['text']), ([], False, 'für S1'))

    def test_ohne_antwort_geht_es_sofort_raus(self):
        out = self.node("""
(async()=>{
  const {S, a, feld, gesendet} = bau(false);
  feld.value = 'gleich';
  await E.absenden(S);
  console.log(JSON.stringify({gesendet, vorgemerkt: !S._eingabe.vorgemerkt.hidden}));
})();
""")
        self.assertEqual((out['gesendet'], out['vorgemerkt']), (['gleich'], False))


if __name__ == '__main__':
    unittest.main()
