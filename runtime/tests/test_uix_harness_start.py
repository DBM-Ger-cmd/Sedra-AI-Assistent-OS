"""Harness-Shell Stufe 4 (SPEC_HARNESS_SHELL_v1 G2/G3 Stufe 4): Umschalter als Menü (N1), App-Liste (N3), Start-Menü und App-Reiter
(N4/N5 – der Browser-Teil läuft in benchmarks/uix_check.py --shell harness). Reine Teile mit node, ohne Browser."""
import unittest

from test_uix_contract import NODE, UIX, run_js

HARNESS = UIX / 'shells' / 'harness'


class UmschalterAlsMenue(unittest.TestCase):
    """Vertrag Nachtrag N3: `umschalter: menue` – kein Chip, Alt+S ruft den Haken der Shell."""

    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_modus_aus_dem_manifest(self):
        out = run_js([UIX / 'ui' / 'wechsel.js'], """
          const W = box.sedraWechsel;
          console.log(JSON.stringify([W.modus({shell: {umschalter: 'menue'}}), W.modus({shell: {umschalter: 'chip'}}), W.modus({shell: {}}), W.modus(null), W.modus({shell: {umschalter: 'anders'}})]));
        """)
        self.assertEqual(out, ['menue', 'chip', 'chip', 'chip', 'chip'], 'nur „menue“ schaltet um; alles andere bleibt der Chip')

    def test_menue_haengt_keinen_chip_an_und_alt_s_ruft_den_haken(self):
        out = run_js([UIX / 'ui' / 'wechsel.js'], """
          const W = box.sedraWechsel;
          const handler = [];
          box.document = {addEventListener: (name, fn)=>handler.push([name, fn]), querySelector: ()=>null, documentElement: {dataset: {}}, body: {append(){}}};
          let gerufen = 0;
          W.menueHaken(()=>{ gerufen += 1; });
          const r = W.mount({shell: {id: 'harness', name: 'Harness', umschalter: 'menue'}});
          const key = handler.find(h=>h[0] === 'keydown')[1];
          let verhindert = 0;
          key({altKey: true, ctrlKey: false, metaKey: false, key: 's', preventDefault(){ verhindert += 1; }});
          key({altKey: false, ctrlKey: false, metaKey: false, key: 's', preventDefault(){ verhindert += 1; }});
          key({altKey: true, ctrlKey: true, metaKey: false, key: 'S', preventDefault(){ verhindert += 1; }});
          console.log(JSON.stringify({menue: r && r.menue === true, chip: 'chip' in (r || {}), gerufen, verhindert, hub: handler.some(h=>h[0] === 'click')}));
        """)
        self.assertEqual(out, {'menue': True, 'chip': False, 'gerufen': 1, 'verhindert': 1, 'hub': False},
                         'nur Alt+S allein ruft das Menü; kein Chip, kein Hub, kein Klick-Handler der Seite')

    def test_die_wege_des_wechsels_sind_exportiert(self):
        out = run_js([UIX / 'ui' / 'wechsel.js'], """
          const W = box.sedraWechsel;
          console.log(JSON.stringify(['wechseln', 'uebersicht', 'leeren', 'menueHaken', 'setScale', 'entries', 'modus'].map(k=>typeof W[k])));
        """)
        self.assertEqual(out, ['function'] * 7, 'eine Shell mit Menü baut keinen zweiten Wechsel: sie ruft diese Funktionen')


class AppListe(unittest.TestCase):
    """N3: die App-Liste des Start-Menüs (startliste.js, rein). Orte aus ui/places.js, Werkzeuge wie /api/uix/modules sie gibt."""

    KOPF = """
      const L = box.sedraStartliste;
      const orte = [
        {id: 'tasks', label: 'Aufgaben', hint: 'was läuft', words: ['aufgabe', 'aufgaben', 'karte'], object: {type: 'task', id: 'alle'}},
        {id: 'models', label: 'Werkstatt: Modelle', hint: 'Modelle und Rezepte', words: ['modell', 'modelle', 'werkstatt'], object: {type: 'model', id: 'alle'}},
        {id: 'wissen', label: 'Wissen', hint: 'suchen, Quellen', words: ['wissen', 'rag'], object: {type: 'wissen', id: 'speicher'}},
        {id: 'wissen-suche', label: 'Wissen · Suche', hint: 'eine Frage', words: ['wissenssuche'], object: {type: 'wissen', id: 'speicher', view: 'suche'}},
        {id: 'logbook', label: 'Logbuch', hint: 'Audit', words: ['logbuch', 'audit'], object: {type: 'logbook', id: 'audit'}},
        {id: 'hardware', label: 'Hardware', hint: 'GPU, RAM', words: ['hardware', 'gpu'], object: {type: 'hardware', id: 'hardware'}},
        {id: 'verwaist', label: 'Verwaist', hint: 'kein Werkzeug', words: ['verwaist'], object: {type: 'routine', id: 'alle'}},
        {id: 'gespraech', label: 'Gespräch', hint: 'talk', words: ['gespräch'], object: {type: 'talk', id: 'talk'}},
      ];
      const werkzeuge = [
        {id: 'task', kind: 'object', handles: ['task'], enabled: true, name: 'Aufgabe'},
        {id: 'workshop', kind: 'object', handles: ['model'], enabled: true, name: 'Werkstatt'},
        {id: 'wissen', kind: 'object', handles: ['wissen'], enabled: true, name: 'Wissen'},
        {id: 'logbook', kind: 'object', handles: ['logbook'], enabled: true, name: 'Logbuch'},
        {id: 'system', kind: 'object', handles: ['hardware'], enabled: true, name: 'System', gruppe: 'system'},
        {id: 'gauge-gpu', kind: 'instrument', handles: ['hardware'], enabled: true, name: 'GPU'},
        {id: 'talk', kind: 'panel', handles: ['talk'], enabled: true, name: 'Gespräch'},
        {id: 'rechnung', kind: 'object', handles: ['rechnung'], enabled: true, name: 'Rechnungen', description: 'eigener Typ'},
        {id: 'aus', kind: 'object', handles: ['issue'], enabled: false, name: 'Aus'},
        {id: 'rahmen-probe', kind: 'object', handles: ['task'], enabled: true, name: 'Probe', zweck: 'pruefung'},
      ];
      const zeichnet = o=>werkzeuge.filter(w=>w.enabled !== false && w.handles.some(h=>h.split(':')[0] === o.type));
      const konfig = {gruppen: ['arbeit', 'modelle', 'wissen', 'system', 'pruefung'], zuordnung: {tasks: 'arbeit', models: 'modelle', wissen: 'wissen', 'wissen-suche': 'wissen', logbook: 'system', hardware: 'modelle', rechnung: 'arbeit'}, zuletzt_max: 2};
    """

    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def liste(self, probe, kopf=None):
        return run_js([HARNESS / 'startliste.js'], (kopf or self.KOPF) + probe)

    def test_01_ort_ohne_werkzeug_fehlt_und_talk_instrument_nie(self):
        out = self.liste("const l = L.bauen(orte, werkzeuge, zeichnet, konfig, []); console.log(JSON.stringify(l.apps.map(a=>a.id)));")
        self.assertNotIn('verwaist', out, 'UIX-10: ein Ort ohne Werkzeug steht nicht im Menü')
        self.assertNotIn('gespraech', out, 'das Gespräch ist in der Harness die Mitte, keine App')
        self.assertNotIn('werkzeug-gauge-gpu', out, 'Instrumente sind keine Apps (HS-43)')
        self.assertNotIn('werkzeug-aus', out, 'abgeschaltete Werkzeuge fehlen')

    def test_02_werkzeug_ohne_ort_bekommt_einen(self):
        out = self.liste("const l = L.bauen(orte, werkzeuge, zeichnet, konfig, []); console.log(JSON.stringify(l.apps.find(a=>a.id === 'werkzeug-rechnung')));")
        self.assertEqual(out['object'], {'type': 'rechnung', 'id': 'alle', 'title': 'Rechnungen'})
        self.assertEqual((out['gruppe'], out['hint']), ('arbeit', 'eigener Typ'))

    def test_03_manifest_feld_schlaegt_datei(self):
        out = self.liste("const l = L.bauen(orte, werkzeuge, zeichnet, konfig, []); console.log(JSON.stringify(l.apps.find(a=>a.id === 'hardware').gruppe));")
        self.assertEqual(out, 'system', 'das Werkzeug `system` sagt gruppe: system – die Datei sagt modelle; das Feld gewinnt (N2)')

    def test_04_unbekannt_ist_arbeit(self):
        out = self.liste("const l = L.bauen(orte, werkzeuge, zeichnet, {zuordnung: {}}, []); console.log(JSON.stringify(l.apps.map(a=>[a.id, a.gruppe])));")
        self.assertTrue(all(g == 'arbeit' for i, g in out if i != 'hardware'), out)
        self.assertEqual(dict(out)['hardware'], 'system', 'nur das Manifest-Feld ordnet noch ein')

    def test_05_pruefung_nur_fuer_reine_pruef_orte(self):
        out = self.liste("""
          const ohne = L.bauen(orte, werkzeuge.filter(w=>w.zweck !== 'pruefung'), o=>werkzeuge.filter(w=>w.zweck !== 'pruefung' && w.enabled !== false && w.handles.some(h=>h.split(':')[0] === o.type)), konfig, []);
          const mit = L.bauen(orte.concat([{id: 'probe', label: 'Probe', hint: '', words: ['probe'], object: {type: 'task', id: 'probe'}}]), werkzeuge, o=>o.id === 'probe' ? [werkzeuge.find(w=>w.id === 'rahmen-probe')] : zeichnet(o).filter(w=>w.zweck !== 'pruefung'), konfig, []);
          console.log(JSON.stringify([ohne.gruppen.map(g=>g.id), mit.gruppen.map(g=>g.id), mit.apps.find(a=>a.id === 'probe').gruppe]));
        """)
        self.assertNotIn('pruefung', out[0])
        self.assertIn('pruefung', out[1]); self.assertEqual(out[2], 'pruefung')

    def test_06_leere_gruppe_fehlt_und_reihenfolge_stabil(self):
        out = self.liste("const l = L.bauen(orte, werkzeuge, zeichnet, konfig, []); console.log(JSON.stringify([l.gruppen.map(g=>g.id), l.gruppen.map(g=>g.apps.map(a=>a.id))]));")
        self.assertEqual(out[0], ['arbeit', 'modelle', 'wissen', 'system'])
        self.assertEqual(out[1], [['tasks', 'werkzeug-rechnung'], ['models'], ['wissen', 'wissen-suche'], ['logbook', 'hardware']], 'Menü-Reihenfolge = Reihenfolge der Orte, dann der Werkzeuge')

    def test_07_suche_ueber_woerter_name_hinweis(self):
        out = self.liste("""
          const l = L.bauen(orte, werkzeuge, zeichnet, konfig, []);
          console.log(JSON.stringify([L.suchen(l, 'rag').map(a=>a.id), L.suchen(l, 'wis').map(a=>a.id), L.suchen(l, 'GPU, RAM').map(a=>a.id), L.suchen(l, '').length, L.suchen(l, 'xyz').length]));
        """)
        self.assertEqual(out[0], ['wissen'], 'ein Suchwort trifft genau')
        self.assertEqual(out[1], ['wissen', 'wissen-suche'], 'Anfang eines Worts, Menü-Reihenfolge bei Gleichstand')
        self.assertEqual(out[2], ['hardware'], 'der Hinweis zählt auch, Satzzeichen stören nicht')
        self.assertEqual(out[3:], [0, 0])

    def test_08_kaputte_zuordnung_ist_ein_satz(self):
        out = self.liste("""
          const f = k=>{ try{ L.bauen(orte, werkzeuge, zeichnet, k, []); return null; }catch(e){ return e.message; } };
          console.log(JSON.stringify([f({zuordnung: {tasks: 'spiele'}}), f({zuordnung: []}), f({gruppen: ['dings']}), f('kaputt'), f({})]));
        """)
        self.assertIn('spiele', out[0]); self.assertIn('zuordnung', out[1]); self.assertIn('dings', out[2]); self.assertIn('Objekt', out[3])
        self.assertIsNone(out[4], 'eine leere Datei ist gültig: alles in arbeit')

    def test_09_zuletzt_hoechstens_max_und_unbekannte_uebersprungen(self):
        out = self.liste("""
          const l = L.bauen(orte, werkzeuge, zeichnet, konfig, ['wissen', 'gibt-es-nicht', 'tasks', 'logbook']);
          console.log(JSON.stringify([l.zuletzt.map(a=>a.id), l.zuletzt_max]));
        """)
        self.assertEqual(out, [['wissen', 'tasks'], 2])

    def test_10_zuletzt_nachfuehren(self):
        out = self.liste("console.log(JSON.stringify([L.zuletztNach(['a', 'b', 'c'], 'b', 3), L.zuletztNach([], 'x', 2), L.zuletztNach(['a', 'b'], 'c', 2)]));")
        self.assertEqual(out, [['b', 'a', 'c'], ['x'], ['c', 'a']])

    def test_11_ablage_eintraege_fuer_den_server(self):
        out = self.liste("""
          const l = L.bauen(orte, werkzeuge, zeichnet, konfig, []);
          console.log(JSON.stringify(L.alsAblage(l, ['models', 'nix', 'wissen-suche'])));
        """)
        self.assertEqual(out, [{'kind': 'place', 'label': 'Werkstatt: Modelle', 'icon': 'modelle', 'place': 'models'},
                               {'kind': 'place', 'label': 'Wissen · Suche', 'icon': 'wissen', 'place': 'wissen-suche'}])
        self.assertTrue(all(len(e['label']) <= 24 for e in out))

    def test_12_die_echte_datei_und_die_echten_orte(self):
        import json
        konfig = json.loads((HARNESS / 'start_gruppen.json').read_text(encoding='utf-8'))
        out = run_js([UIX / 'ui' / 'places.js', HARNESS / 'startliste.js'], """
          const L = box.sedraStartliste, P = box.sedraPlaces;
          const konfig = %s;
          const alle = o=>[{id: 'x', kind: 'object', handles: [o.type]}];
          const l = L.bauen(P.PLACES, [], alle, konfig, []);
          console.log(JSON.stringify({gruppen: l.gruppen.map(g=>[g.id, g.apps.length]), ohne: l.apps.filter(a=>a.gruppe === 'arbeit' && !konfig.zuordnung[a.id] && !konfig.zuordnung[a.object.type]).map(a=>a.id)}));
        """ % json.dumps(konfig))
        self.assertEqual(out['ohne'], [], 'jeder echte Ort hat einen Platz in der Datei (sonst still in Arbeit)')
        self.assertEqual([g for g, _ in out['gruppen']], ['arbeit', 'modelle', 'wissen', 'system'])


if __name__ == '__main__':
    unittest.main()
