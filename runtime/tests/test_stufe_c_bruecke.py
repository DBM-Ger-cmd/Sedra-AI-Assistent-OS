"""Stufe C, Schritt C2: die Brücke zwischen Werkzeug-Rahmen und Kern. Die Regeln laufen mit node, ohne Browser."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which('node')
BRUECKE = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'ui' / 'bruecke.js'


def run_node(script):
    out = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout.strip().splitlines()[-1])


HARNESS = """
const b = require(%s);
const manifest = %s;
const aufrufe = [], shellAufrufe = [], rahmenPost = [], abos = [];
const GEHEIM = 'TOKEN-GEHEIM-7731';
const kern = {forModule: (mod)=> async (path, opts)=>{ aufrufe.push({mod, path, opts}); if(path==='/api/boom') throw new Error('serverfehler'); return {pfad: path}; }};
const shell = {open: async(o)=>{ shellAufrufe.push(['open', o]); return 'offen'; }, notify: async(t, ton)=>{ shellAufrufe.push(['notify', t, ton]); return null; }, decide: async()=>{ shellAufrufe.push(['decide']); return 'soll_nie_laufen'; }};
const bus = {on: (name, fn)=>{ abos.push(name); return ()=>{}; }};
const probleme = [];
const br = b.makeBruecke({kern, shell, bus, onProblem: (w, e)=>probleme.push(String(e && e.message || e))});
const fenster = {postMessage: (m)=>rahmenPost.push(m)};
const fremd = {postMessage: ()=>{}};
br.register(fenster, manifest);
const warte = ()=>new Promise(r=>setTimeout(r, 20));
(async()=>{
  const ev = (src, data)=>br.handle({source: src, data});
  const out = {};
  // 1 fremde Quelle wird abgelehnt
  out.fremd = ev(fremd, {id: '1', op: 'api', path: '/api/status'});
  // 2 Route im Manifest: ok, Modul-Kennung kommt vom Kern
  ev(fenster, {id: 'a', op: 'api', path: '/api/status', method: 'GET'});
  await warte();
  // 3 Route nicht im Manifest: abgelehnt, Kern nicht aufgerufen
  const vorher = aufrufe.length;
  ev(fenster, {id: 'b', op: 'api', path: '/api/gateway/regeln/loeschen', method: 'POST', body: {}});
  await warte();
  out.verweigert_aufrufe = aufrufe.length - vorher;
  // 4 decide über die Brücke: nicht erlaubt, Shell nicht aufgerufen
  ev(fenster, {id: 'c', op: 'shell', name: 'decide', args: ['x', 'freigeben']});
  await warte();
  out.decide_aufrufe = shellAufrufe.filter(x=>x[0]==='decide').length;
  // 5 open und notify mit Argumenten
  ev(fenster, {id: 'd', op: 'shell', name: 'open', args: [{type: 'task', id: 't1'}]});
  ev(fenster, {id: 'e', op: 'shell', name: 'notify', args: ['Gemerkt', 'note']});
  await warte();
  out.shell = shellAufrufe.filter(x=>x[0]!=='decide');
  // 6 Antworten gehen nur an den Rahmen, tragen die Kennung und keinen Token
  out.antwort_ids = rahmenPost.filter(m=>m.antwort).map(m=>m.id);
  out.token_in_antwort = JSON.stringify(rahmenPost).indexOf(GEHEIM) >= 0;
  out.kern_mod = aufrufe[0] && aufrufe[0].mod;
  // 7 Ereignisse nur laut Manifest
  out.abos = abos;
  // 8 Fehler im Kern kommt als Antwort, nicht als Absturz
  ev(fenster, {id: 'f', op: 'api', path: '/api/boom', method: 'POST'});
  await warte();
  out.fehler = rahmenPost.filter(m=>m.id==='f').map(m=>m.fehler);
  // 9 ungültige Nachrichten
  ev(fenster, {id: 'g', op: 'api', path: 'http://evil/api/x'});
  ev(fenster, {id: 'h', op: 'eval', code: 'x'});
  ev(fenster, {op: 'api', path: '/api/status'});
  ev(fenster, {id: 'i', op: 'shell', name: 'open', args: 'kein-array'});
  await warte();
  out.ungueltig = ['g','h','i'].map(id=>(rahmenPost.find(m=>m.id===id)||{}).fehler || 'keine');
  out.id_ohne_kennung = rahmenPost.some(m=>m.antwort && m.id==='' && m.fehler);
  // 10 Abmelden löst die Abos
  let geloest = 0;
  const bus2 = {on: (n, f)=>()=>{ geloest++; }};
  const br2 = b.makeBruecke({kern, shell, bus: bus2});
  const f2 = {postMessage: ()=>{}};
  br2.register(f2, {id: 'x', api: [], events: {listens: ['object.open', 'system.state']}});
  br2.abmelden(f2);
  out.geloest = geloest;
  out.probleme = probleme;
  console.log(JSON.stringify(out));
})();
""" % (json.dumps(str(BRUECKE)), json.dumps({
    'id': 'testwerk',
    'api': ['GET /api/status', 'POST /api/boom'],
    'events': {'listens': ['system.state']},
}))


@unittest.skipIf(NODE is None, 'node ist nicht installiert')
class BruecketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run_node(HARNESS)

    def test_fremde_quelle_wird_abgelehnt(self):
        self.assertFalse(self.out['fremd'])

    def test_erlaubte_route_geht_mit_der_kennung_des_moduls(self):
        self.assertEqual(self.out['kern_mod'], {'kind': 'tool', 'id': 'testwerk'})

    def test_verbotene_route_erreicht_den_kern_nicht(self):
        self.assertEqual(self.out['verweigert_aufrufe'], 0)

    def test_decide_ist_ueber_die_bruecke_nie_moeglich(self):
        self.assertEqual(self.out['decide_aufrufe'], 0)

    def test_shell_open_und_notify_mit_argumenten(self):
        self.assertEqual(self.out['shell'], [['open', {'type': 'task', 'id': 't1'}], ['notify', 'Gemerkt', 'note']])

    def test_antworten_tragen_die_kennung_und_keinen_token(self):
        self.assertIn('a', self.out['antwort_ids'])
        self.assertFalse(self.out['token_in_antwort'])

    def test_ereignisse_nur_laut_manifest(self):
        self.assertEqual(self.out['abos'], ['system.state'])

    def test_serverfehler_kommt_als_antwort(self):
        self.assertEqual(self.out['fehler'], ['serverfehler'])

    def test_ungueltige_nachrichten_werden_mit_grund_beantwortet(self):
        self.assertEqual(self.out['ungueltig'], ['pfad_ungueltig', 'op_unbekannt:eval', 'args_keine_liste'])

    def test_nachricht_ohne_kennung_wird_abgelehnt(self):
        self.assertTrue(self.out['id_ohne_kennung'])

    def test_abmelden_loest_die_abos(self):
        # zwei gelistete Ereignisse, zwei Abos, alle werden beim Abmelden gelöst
        self.assertEqual(self.out['geloest'], 2)

    def test_regeln_bei_route_und_methode(self):
        script = 'const b=require(%s);console.log(JSON.stringify([b.routeErlaubt(["GET /api/a"],"GET","/api/a"),b.routeErlaubt(["GET /api/a"],"POST","/api/a"),b.routeErlaubt(["GET /api/a"],"GET","/api/ab")]));' % json.dumps(str(BRUECKE))
        self.assertEqual(run_node(script), [True, False, False])


if __name__ == '__main__':
    unittest.main()
