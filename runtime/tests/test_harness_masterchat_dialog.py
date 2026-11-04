"""MasterChat, Oberfläche bis Server (04.11.2026): Beim Anlegen einer Sitzung mit weitreichenden Freigaben fragt verlauf.js den Captain; nur sein Ja schickt `erlaubnisse_bestaetigt: true`
an POST /api/harness/sitzungen, ohne Ja geht nichts hinaus. Vorlagen ohne Erlaubnisse fragen nicht und schicken das Feld nicht. verlauf.js läuft hier mit node und einer Attrappe der Oberfläche."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells' / 'harness'

KOPF = """
function el(tag, klasse, text){
  const e = {tag, kinder: [], textContent: text || '', attrs: {}, dataset: {}, scrollHeight: 0, scrollTop: 0, clientHeight: 0, className: klasse || '',
    classList: {toggle(){}, contains: ()=>false, add(){}, remove(){}}, setAttribute(k, v){ e.attrs[k] = v; }, append(...c){ e.kinder.push(...c); },
    replaceChildren(...c){ e.kinder = c; }, addEventListener(){}, querySelector: ()=>null, querySelectorAll: ()=>[], remove(){}, closest: ()=>null};
  return e;
}
globalThis.requestAnimationFrame = f=>0;
globalThis.document = {createElementNS: (ns, tag)=>el(tag), addEventListener(){}, removeEventListener(){}};
globalThis.sedraDom = {el};
globalThis.sedraHarness = {markdown: {}, zeilen: {}, reiter: {ID: /^S-[0-9A-F]{8}$/, umbenennen(){}}, eingabe: {modellMenue(){}}};
require(%s);
require(%s);
const gefragt = [], posts = [], notizen = [];
const S = {modell: {name: 'm'}, ansichten: new Map(), sitzungenLaden(){}, leerGeaendert(){}, hinweis(){}, _eingabe: {},
  vorlagen: [{id: 'masterchat', name: 'MasterChat', hinweis: 'h', erlaubnisse: [{werkzeug: 'datei_schreiben', muster: 'docs/**'}]}, {id: 'bauagent', name: 'Bauagent', hinweis: '', erlaubnisse: []}],
  async api(pfad, opt){
    if(opt && opt.method === 'POST' && pfad === '/api/harness/sitzungen'){ posts.push(opt.body); return {id: 'S-AABBCCDD'}; }
    if(opt && opt.method === 'POST') return {antwort_id: 'A-1'};
    return {};
  }};
async function lauf(vorlage, antwort){
  gefragt.length = 0; posts.length = 0; notizen.length = 0;
  globalThis.sedraHarness.vorlagenhinweis.bestaetigen = async (s, v)=>{ gefragt.push(v.id); return antwort; };
  const a = globalThis.sedraHarness.verlauf.ansicht(S, 'neu-' + vorlage + '-' + antwort);
  a.strom = ()=>{}; a.codeHinweis = ()=>{}; a.notiz = (t)=>{ notizen.push(t); };
  const ok = await a.senden('Hallo', 'sedra-entwicklung', vorlage);
  return {ok, gefragt: gefragt.slice(), posts: posts.slice(), notizen: notizen.slice()};
}
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class DialogZumServer(unittest.TestCase):
    def node(self, code):
        kopf = KOPF % (json.dumps(str(HARNESS / 'vorlagenhinweis.js')), json.dumps(str(HARNESS / 'verlauf.js')))
        r = subprocess.run(['node', '-e', kopf + code], capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_mit_ja_geht_erlaubnisse_bestaetigt_true_an_den_server(self):
        out = self.node("(async()=>{ console.log(JSON.stringify(await lauf('masterchat', true))); })();")
        self.assertEqual(out['gefragt'], ['masterchat'])
        self.assertEqual(out['posts'], [{'projekt': 'sedra-entwicklung', 'vorlage': 'masterchat', 'erlaubnisse_bestaetigt': True}])
        self.assertTrue(out['ok'])

    def test_ohne_ja_geht_nichts_an_den_server_und_der_captain_erfaehrt_es(self):
        out = self.node("(async()=>{ console.log(JSON.stringify(await lauf('masterchat', false))); })();")
        self.assertEqual(out['gefragt'], ['masterchat'])
        self.assertEqual(out['posts'], [])
        self.assertFalse(out['ok'])
        self.assertTrue(any('ohne die Freigaben' in n for n in out['notizen']), out['notizen'])

    def test_vorlage_ohne_erlaubnisse_fragt_nicht_und_schickt_das_feld_nicht(self):
        out = self.node("(async()=>{ console.log(JSON.stringify(await lauf('bauagent', true))); })();")
        self.assertEqual(out['gefragt'], [])
        self.assertEqual(out['posts'], [{'projekt': 'sedra-entwicklung', 'vorlage': 'bauagent'}])


if __name__ == '__main__':
    unittest.main()
