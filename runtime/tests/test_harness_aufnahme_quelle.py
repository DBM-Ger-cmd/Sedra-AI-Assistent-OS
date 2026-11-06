"""Aufnahme-Knopf der Taskleiste mit kleiner Quellenwahl (Captain 04.11.2026): Standard ist „beides“ (PC-Ton und Mikrofon); die Auswahl daneben wählt PC-Ton oder Mikrofon allein.
Nur eine abweichende Wahl geht als `quelle` an den Kern (so greift beim Standard dessen Rückfall auf das Mikrofon); die Wahl wird gemerkt; während der Aufnahme ist sie gesperrt.
schnell.js läuft mit node und einer Attrappe der Oberfläche."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness' / 'schnell.js'

KOPF = """
function el(tag, klasse, text){
  const e = {tag, kinder: [], textContent: text || '', attrs: {}, value: '', disabled: false, title: '', _k: new Set(klasse ? klasse.split(' ') : []),
    classList: {toggle: (k, an)=>{ (an === undefined ? !e._k.has(k) : an) ? e._k.add(k) : e._k.delete(k); }, contains: k=>e._k.has(k)},
    setAttribute(k, v){ e.attrs[k] = v; }, append(...c){ e.kinder.push(...c); }, replaceChildren(...c){ e.kinder = c; }, querySelector: ()=>null};
  Object.defineProperty(e, 'type', {set(v){ e.attrs.type = v; }, get(){ return e.attrs.type; }});
  return e;
}
const speicher = globalThis.SPEICHER = {};
if(!globalThis.OHNE_SPEICHER) globalThis.localStorage = {getItem: k=>(k in speicher ? speicher[k] : null), setItem: (k, v)=>{ speicher[k] = String(v); }};
else globalThis.localStorage = {getItem(){ throw new Error('gesperrt'); }, setItem(){ throw new Error('gesperrt'); }};
globalThis.document = {hidden: true};
globalThis.performance = {now: ()=>0};
globalThis.sedraDom = {el};
globalThis.sedraPlaces = {PLACES: []};
globalThis.sedraHarness = {};
require(%s);
const SC = globalThis.sedraHarness.schnell;
const aufrufe = [];
let stand = {status: 'aus'};
const S = {hinweis(){}, async api(pfad, opt){ aufrufe.push({pfad, methode: (opt && opt.method) || 'GET', body: opt && opt.body});
  if(pfad === '/api/sprache/kern/stand') return stand;
  if(pfad === '/api/sprache/kern/start'){ stand = {status: 'laeuft', sekunden: 0}; return stand; }
  return {titel: 'x', dauer: 3}; }};
const tick = ()=>new Promise(r=>setImmediate(r));
const alle = n=>[n].concat(...(n.kinder || []).map(alle));
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class AufnahmeQuelle(unittest.TestCase):
    def node(self, code, vorher=''):
        r = subprocess.run(['node', '-e', vorher + KOPF % json.dumps(str(JS)) + '(async()=>{' + code + '})().catch(e=>{ console.error(e); process.exit(1); });'],
                           capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_knopf_und_kleine_auswahl_mit_beides_als_standard(self):
        out = self.node("""
const g = SC.knopf(S); await tick();
const q = alle(g).find(x=>x.tag === 'select');
console.log(JSON.stringify({klasse: [...g._k], kinder: g.kinder.map(k=>k.tag), werte: q.kinder.map(o=>o.value), namen: q.kinder.map(o=>o.textContent), wert: q.value, label: q.attrs['aria-label']}));
""")
        self.assertEqual(out['kinder'], ['button', 'select'])
        self.assertEqual(out['werte'], ['beides', 'pc_ton', 'mikrofon'])
        self.assertEqual(out['namen'], ['Beides', 'PC-Ton', 'Mikro'])
        self.assertEqual(out['wert'], 'beides')
        self.assertEqual(out['label'], 'Quelle der Aufnahme')

    def test_standard_schickt_keine_quelle_eine_andere_wahl_schon(self):
        out = self.node("""
const g = SC.knopf(S); await tick();
const [k, q] = g.kinder;
k.onclick({}); await tick(); await tick();
const standard = aufrufe.filter(a=>a.pfad === '/api/sprache/kern/start').map(a=>a.body);
stand = {status: 'aus'}; await SC.lesen(S); aufrufe.length = 0;
q.value = 'pc_ton'; q.onchange(); k.onclick({}); await tick(); await tick();
const pc = aufrufe.filter(a=>a.pfad === '/api/sprache/kern/start').map(a=>a.body);
console.log(JSON.stringify({standard, pc}));
""")
        self.assertEqual(out['standard'], [{'titel': '', 'sprache': 'de'}])
        self.assertEqual(out['pc'], [{'titel': '', 'sprache': 'de', 'quelle': 'pc_ton'}])

    def test_die_wahl_wird_gemerkt_und_ein_unbekannter_wert_faellt_auf_beides(self):
        out = self.node("""
const g = SC.knopf(S); await tick();
const q = g.kinder[1]; q.value = 'mikrofon'; q.onchange();
const gespeichert = SPEICHER['sedra.harness.aufnahme.quelle'];
const neu = SC.knopf(S).kinder[1].value;
SPEICHER['sedra.harness.aufnahme.quelle'] = 'radio';
const kaputt = SC.knopf(S).kinder[1].value;
console.log(JSON.stringify({gespeichert, neu, kaputt}));
""")
        self.assertEqual(out, {'gespeichert': 'mikrofon', 'neu': 'mikrofon', 'kaputt': 'beides'})

    def test_ohne_speicher_bleibt_es_beim_standard_und_nichts_bricht(self):
        out = self.node("""
const g = SC.knopf(S); await tick();
const q = g.kinder[1]; const vorher = q.value; q.value = 'pc_ton'; q.onchange();
console.log(JSON.stringify({vorher}));
""", vorher='globalThis.OHNE_SPEICHER = true;')
        self.assertEqual(out, {'vorher': 'beides'})

    def test_waehrend_der_aufnahme_ist_die_auswahl_gesperrt(self):
        out = self.node("""
const g = SC.knopf(S); await tick();
const [k, q] = g.kinder;
const davor = q.disabled;
k.onclick({}); await tick(); await tick();
const laeuft = q.disabled;
stand = {status: 'aus'}; await SC.lesen(S);
console.log(JSON.stringify({davor, laeuft, danach: q.disabled}));
""")
        self.assertEqual(out, {'davor': False, 'laeuft': True, 'danach': False})


if __name__ == '__main__':
    unittest.main()
