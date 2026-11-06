"""„Neues Projekt anlegen“ (Captain 04.11.2026): Name und übergeordneter Ordner → Antrag im Posteingang; der Ordner entsteht erst nach der Freigabe und ist dann ein Projekt.
Teil 1: Prüfung und Antrag (harness/projekte.py, harness/antraege.py) mit echten Ordnern im Temp-Ordner. Teil 2: die Oberfläche (projekt.js) mit node."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sedra_runtime.harness import antraege
from sedra_runtime.harness import projekte as harness_projekte


class Hub:
    def __init__(self, root, offen=()):
        self.project_root = root
        self._offen = list(offen)
        self.audit = []
        self.runtime = SimpleNamespace(audit=SimpleNamespace(append=lambda e, component=None, payload=None, **k: self.audit.append((e, payload))))
        self.events = SimpleNamespace(publish=lambda name, daten: None)

    def _open_requests(self):
        return self._offen


class NeuesProjekt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / 'sedra' / 'workspace'
        (self.root / 'runtime_data' / 'harness').mkdir(parents=True)
        self.eltern = base / 'Projekte'
        self.eltern.mkdir()
        self.hub = Hub(self.root)

    def antrag(self, **payload):
        daten = dict({'anlegen': True, 'eltern': str(self.eltern), 'name': 'Mein Neues'}, **payload)
        with mock.patch.object(antraege.gated, 'request', return_value={'mission_id': 'M-NEU'}) as anfrage:
            out = antraege.projekt_antrag(self.hub, daten)
        return out, anfrage

    def test_antrag_legt_nichts_an_und_bindet_den_neuen_ordner(self):
        out, anfrage = self.antrag()
        self.assertEqual(out['projekt']['name'], 'Mein Neues')
        self.assertEqual(Path(out['projekt']['wurzel']), (self.eltern / 'Mein Neues').resolve())
        self.assertFalse((self.eltern / 'Mein Neues').exists(), 'der Antrag legt keinen Ordner an')
        args, kw = anfrage.call_args
        self.assertTrue(args[4]['anlegen'])
        self.assertIn('wird neu angelegt', kw['risks'][0])
        self.assertEqual(kw['describe'], 'Neues Projekt anlegen: Mein Neues')

    def test_ohne_anlegen_bleibt_ordner_oeffnen_wie_es_war(self):
        vorhanden = self.eltern / 'Schon da'
        vorhanden.mkdir()
        with mock.patch.object(antraege.gated, 'request', return_value={'mission_id': 'M-X'}) as anfrage:
            antraege.projekt_antrag(self.hub, {'wurzel': str(vorhanden)})
        self.assertNotIn('anlegen', anfrage.call_args.args[4])
        with self.assertRaisesRegex(ValueError, 'wurzel_ungueltig'):
            with mock.patch.object(antraege.gated, 'request'):
                antraege.projekt_antrag(self.hub, {'wurzel': str(self.eltern / 'gibt es nicht')})        # ohne anlegen entsteht nichts

    def test_eingaben_werden_geprueft(self):
        faelle = [({'eltern': None}, 'eltern_fehlt'), ({'eltern': str(self.eltern / 'fehlt' / 'tief')}, 'eltern_ungueltig'), ({'eltern': 'relativ/pfad'}, 'eltern_ungueltig'),
                  ({'name': ''}, 'name_ungueltig'), ({'name': 'a/b'}, 'name_ungueltig'), ({'name': 'a' + chr(92) + 'b'}, 'name_ungueltig'), ({'name': '..'}, 'name_ungueltig'),
                  ({'name': 'CON'}, 'name_ungueltig'), ({'name': 'Ende.'}, 'name_ungueltig'), ({'name': 'x' * 81}, 'name_ungueltig'),
                  ({'schreibbereich': ['../draussen']}, 'schreibbereich_ungueltig')]
        for aenderung, code in faelle:
            with self.assertRaisesRegex(ValueError, code, msg=str(aenderung)):
                self.antrag(**aenderung)
        (self.eltern / 'Mein Neues').mkdir()
        with self.assertRaisesRegex(ValueError, 'ordner_vorhanden'):
            self.antrag()
        with self.assertRaisesRegex(ValueError, 'wurzel_gesperrt'):                                  # in der Ablage des Captains entsteht kein Projekt
            self.antrag(eltern=str(self.root / 'runtime_data'), name='Hier')

    def test_freigabe_legt_den_ordner_an_und_schreibt_das_projekt(self):
        out, anfrage = self.antrag()
        antraege._projekt_anwenden(self.hub, anfrage.call_args.args[4])
        ordner = self.eltern / 'Mein Neues'
        self.assertTrue(ordner.is_dir())
        ids = [p['id'] for p in harness_projekte.laden(self.root)]
        self.assertIn('mein-neues', ids)
        ereignis = [p for e, p in self.hub.audit if e == 'HARNESS_PROJEKT_ADDED'][0]
        self.assertEqual((ereignis['projekt'], ereignis['angelegt']), ('mein-neues', True))

    def test_ist_der_ordner_inzwischen_da_wird_nichts_geschrieben(self):
        _, anfrage = self.antrag()
        (self.eltern / 'Mein Neues').mkdir()
        with self.assertRaises(ValueError) as ctx:
            antraege._projekt_anwenden(self.hub, anfrage.call_args.args[4])
        self.assertIn(antraege.gated.REFUSED + 'ordner_nicht_angelegt', str(ctx.exception))
        self.assertNotIn('mein-neues', [p['id'] for p in harness_projekte.laden(self.root)])

    def test_zwei_antraege_fuer_denselben_neuen_ordner_werden_abgelehnt(self):
        _, erster = self.antrag()
        self.hub._offen = [{'kind': antraege.KIND_PROJEKT, 'mission_id': 'M-ERSTER', 'binding': erster.call_args.args[4]}]
        with self.assertRaisesRegex(ValueError, 'antrag_liegt_schon_im_posteingang'):
            self.antrag()


JS = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness' / 'projekt.js'

KOPF = """
function el(tag, klasse, text){
  const e = {tag, kinder: [], textContent: text || '', attrs: {}, value: '', hidden: false, disabled: false, title: '', placeholder: '', parentNode: null, focused: false,
    setAttribute(k, v){ e.attrs[k] = v; }, append(...c){ c.forEach(x=>{ x.parentNode = e; e.kinder.push(x); }); }, focus(){ e.focused = true; },
    insertBefore(n, ref){ n.parentNode = e; const i = e.kinder.indexOf(ref); e.kinder.splice(i < 0 ? e.kinder.length : i, 0, n); }, get nextSibling(){ const p = e.parentNode; return p ? p.kinder[p.kinder.indexOf(e) + 1] : null; }};
  Object.defineProperty(e, 'type', {set(v){ e.attrs.type = v; }, get(){ return e.attrs.type; }});
  return e;
}
globalThis.sedraDom = {el};
globalThis.sedraHarness = {};
require(%s);
const P = globalThis.sedraHarness.projekt;
const posts = [], hinweise = [];
const S = {projekte: [{id: 'sedra-entwicklung', wurzel: 'E:' + String.fromCharCode(92) + 'Sedra Umgebung' + String.fromCharCode(92) + 'A1 Sedra'}], hinweis(t){ hinweise.push(t); },
  async api(pfad, opt){ posts.push({pfad, body: opt && opt.body}); if(globalThis.FEHLER) throw new Error('ordner_vorhanden: x'); return {projekt: {name: opt.body.name, wurzel: 'E:/P/' + opt.body.name}}; }};
const alle = n=>[n].concat(...(n.kinder || []).map(alle));
const tick = ()=>new Promise(r=>setImmediate(r));
function aufbauen(){
  const eltern = el('div'), zeile = el('div'); eltern.append(zeile);
  const wahl = {value: 'sedra-entwicklung'};
  const k = P.knoepfe(S, zeile, wahl);
  return {eltern, zeile, k};
}
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class Oberflaeche(unittest.TestCase):
    def node(self, code):
        r = subprocess.run(['node', '-e', KOPF % json.dumps(str(JS)) + '(async()=>{' + code + '})().catch(e=>{ console.error(e); process.exit(1); });'],
                           capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_der_knopf_steht_neben_ordner_oeffnen_und_das_formular_ist_vorbelegt(self):
        out = self.node("""
const {zeile, k} = aufbauen();
const namen = zeile.kinder.map(b=>b.textContent);
k.neu.onclick();
const feld = alle(k.formularNeu.box).filter(x=>x.tag === 'input');
console.log(JSON.stringify({namen, offen: !k.formularNeu.box.hidden, andere_zu: k.formular.box.hidden, eltern: feld[1].value, name_fokus: feld[0].focused}));
""")
        self.assertEqual(out['namen'], ['Ordner öffnen …', 'Neues Projekt …', 'Als Vorgabe merken'])
        self.assertTrue(out['offen'])
        self.assertTrue(out['andere_zu'])
        self.assertEqual(out['eltern'], 'E:' + chr(92) + 'Sedra Umgebung')
        self.assertTrue(out['name_fokus'])

    def test_antrag_schickt_anlegen_name_eltern_und_schreibbereich(self):
        out = self.node("""
const {k} = aufbauen(); k.neu.onclick();
const [name, eltern, bereich] = alle(k.formularNeu.box).filter(x=>x.tag === 'input');
name.value = ' Mein Neues '; bereich.value = 'src/**, docs/**';
await k.formularNeu.box.onsubmit({preventDefault(){}}); await tick();
const stand = alle(k.formularNeu.box).find(x=>x.attrs.role === 'status').textContent;
console.log(JSON.stringify({posts, stand}));
""")
        self.assertEqual(len(out['posts']), 1)
        self.assertEqual(out['posts'][0]['pfad'], '/api/harness/projekte')
        self.assertEqual(out['posts'][0]['body'], {'anlegen': True, 'name': 'Mein Neues', 'eltern': 'E:' + chr(92) + 'Sedra Umgebung', 'schreibbereich': ['src/**', 'docs/**']})
        self.assertIn('Antrag gestellt: „Mein Neues“', out['stand'])
        self.assertIn('Posteingang', out['stand'])

    def test_ohne_name_oder_ordner_geht_nichts_hinaus_und_ein_fehler_bleibt_sichtbar(self):
        out = self.node("""
const {k} = aufbauen(); k.neu.onclick();
const [name, eltern] = alle(k.formularNeu.box).filter(x=>x.tag === 'input');
const stand = ()=>alle(k.formularNeu.box).find(x=>x.attrs.role === 'status').textContent;
await k.formularNeu.box.onsubmit({preventDefault(){}}); const ohneName = stand();
name.value = 'X'; eltern.value = ''; await k.formularNeu.box.onsubmit({preventDefault(){}}); const ohneEltern = stand();
eltern.value = 'E:/P'; globalThis.FEHLER = true; await k.formularNeu.box.onsubmit({preventDefault(){}}); await tick();
console.log(JSON.stringify({ohneName, ohneEltern, posts: posts.length, fehler: stand()}));
""")
        self.assertEqual(out['ohneName'], 'Ein Name fehlt.')
        self.assertEqual(out['ohneEltern'], 'Der übergeordnete Ordner fehlt.')
        self.assertEqual(out['posts'], 1)
        self.assertEqual(out['fehler'], 'Nicht gestellt: ordner_vorhanden: x')

    def test_die_beiden_formulare_schliessen_einander(self):
        out = self.node("""
const {k} = aufbauen();
k.auf.onclick(); const a = [k.formular.box.hidden, k.formularNeu.box.hidden];
k.neu.onclick(); const b = [k.formular.box.hidden, k.formularNeu.box.hidden];
k.auf.onclick(); const c = [k.formular.box.hidden, k.formularNeu.box.hidden];
console.log(JSON.stringify({a, b, c}));
""")
        self.assertEqual(out, {'a': [False, True], 'b': [True, False], 'c': [False, True]})


if __name__ == '__main__':
    unittest.main()
