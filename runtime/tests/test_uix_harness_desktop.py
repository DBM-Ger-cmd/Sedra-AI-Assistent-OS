"""Desktop Builder, Client (desktop.js): die Wahl liegt ueber der Vorgabe der Shell – ausgeblendete Apps kommen zur Konfiguration, eine gewaehlte Gruppe gilt vor der Vorgabe, Zellen der
Taskleiste fallen weg oder folgen der gewaehlten Reihenfolge. Reine Teile mit node, ohne Browser."""
import unittest

from test_uix_contract import NODE, UIX, run_js

HARNESS = UIX / 'shells' / 'harness'


class DesktopWahl(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_start_konfig_legt_die_wahl_ueber_die_vorgabe(self):
        out = run_js([HARNESS / 'desktop.js'], """
          const D = box.sedraHarness.desktop;
          const konfig = {ausblenden: ['hardware'], zuordnung: {tasks: 'arbeit', models: 'modelle'}, gruppen: ['arbeit']};
          const leer = {};
          const gleich = D.startKonfig(leer, konfig) === konfig;
          const S = {_desktop: Object.assign(D.LEER(), {start: {ausblenden: ['logbook', 'wissen'], zuordnung: {models: 'system'}}})};
          const k = D.startKonfig(S, konfig);
          console.log(JSON.stringify({gleich, ausblenden: k.ausblenden, zuordnung: k.zuordnung, gruppen: k.gruppen, vorgabeUnveraendert: konfig.ausblenden}));
        """)
        self.assertTrue(out['gleich'], 'ohne Wahl bleibt die Vorgabe dieselbe')
        self.assertEqual(out['ausblenden'], ['hardware', 'logbook'], 'eine Grundfunktion (Wissen) fällt auch im Client heraus')
        self.assertEqual(out['zuordnung'], {'tasks': 'arbeit', 'models': 'system'})
        self.assertEqual(out['vorgabeUnveraendert'], ['hardware'], 'die Vorgabe wird nie veraendert')

    def test_zellen_fallen_weg_und_folgen_der_reihenfolge(self):
        out = run_js([HARNESS / 'desktop.js'], """
          const D = box.sedraHarness.desktop;
          const z = k=>({dataset: {zelle: k}});
          const knoten = ['decisions', 'token', 'model', 'ram', 'state'].map(z);
          const ids = (S)=>D.zellenAnwenden(S, knoten).map(k=>k.dataset.zelle);
          const ohne = ids({});
          const aus = ids({_desktop: Object.assign(D.LEER(), {zellen: {ausblenden: ['ram'], reihenfolge: []}})});
          const sortiert = ids({_desktop: Object.assign(D.LEER(), {zellen: {ausblenden: [], reihenfolge: ['state', 'model']}})});
          console.log(JSON.stringify({ohne, aus, sortiert}));
        """)
        self.assertEqual(out['ohne'], ['decisions', 'token', 'model', 'ram', 'state'])
        self.assertEqual(out['aus'], ['decisions', 'token', 'model', 'state'])
        self.assertEqual(out['sortiert'], ['state', 'model', 'decisions', 'token', 'ram'], 'genannte zuerst, die uebrigen behalten ihre Reihenfolge dahinter')

    def test_grundfunktionen_stehen_im_client_wie_im_server(self):
        from guppi_runtime.harness import desktop as server
        out = run_js([HARNESS / 'desktop.js'], "const D = box.sedraHarness.desktop; console.log(JSON.stringify([D.GRUND_START, D.GRUND_ZELLEN]));")
        self.assertEqual((tuple(out[0]), tuple(out[1])), (server.GRUND_START, server.GRUND_ZELLEN))

    def test_begruessung_nimmt_logo_titel_und_text_mit_rueckfall_auf_sedra(self):
        out = run_js([HARNESS / 'desktop.js'], """
          const D = box.sedraHarness.desktop;
          const mit = w=>({_desktop: Object.assign(D.LEER(), w)});
          console.log(JSON.stringify([
            D.begruessung({}),
            D.begruessung(mit({marke: {name: 'Muster', akzent: '', logo: 'data:image/png;base64,AAAA', schrift: ''}})),
            D.begruessung(mit({marke: {name: 'Muster', akzent: '', logo: '', schrift: ''}, startseite: {ort: '', titel: 'Willkommen', text: 'Hallo'}}))]));
        """)
        self.assertEqual(out[0], {'logo': '', 'titel': 'SEDRA', 'text': '', 'marke': ''}, 'ohne Wahl bleibt es bei SEDRA')
        self.assertEqual((out[1]['logo'], out[1]['titel']), ('data:image/png;base64,AAAA', 'Muster'), 'ohne Titel der Startseite gilt der Name der Marke')
        self.assertEqual((out[2]['titel'], out[2]['text']), ('Willkommen', 'Hallo'))

    def test_schriften_im_client_und_im_server_sind_dieselben_und_ohne_netz(self):
        from guppi_runtime.harness import desktop as server
        out = run_js([HARNESS / 'desktop.js'], "const D = box.sedraHarness.desktop; console.log(JSON.stringify([Object.keys(D.SCHRIFTEN), Object.keys(D.SCHRIFT_NAMEN), Object.values(D.SCHRIFTEN)]));")
        self.assertEqual(tuple(out[0]), server.SCHRIFTEN)
        self.assertEqual(out[0], out[1])
        for stapel in out[2]:
            self.assertNotIn('http', stapel, 'keine Schrift aus dem Netz nachladen')
            self.assertNotIn(';', stapel, 'ein Stapel ist nur eine Liste von Familien')

    def test_startseite_oeffnet_nur_bei_leerem_start(self):
        out = run_js([HARNESS / 'desktop.js'], """
          const D = box.sedraHarness.desktop;
          const geoeffnet = [];
          box.sedraPlaces = {PLACES: [{id: 'tasks', label: 'Aufgaben', object: {type: 'task', id: 'alle'}}]};
          box.sedraHarness.app = {oeffnen: (S, p)=>geoeffnet.push(p.id)};
          const lauf = (liste, ort)=>{
            box.sedraHarness.reiter = {liste: ()=>liste};
            const S = {_desktop: Object.assign(D.LEER(), {startseite: {ort, titel: '', text: ''}})};
            return D.startseiteOeffnen(S);
          };
          const r = [lauf(['neu-1'], 'tasks'), lauf(['neu-1', 'S-00000001'], 'tasks'), lauf(['S-00000001'], 'tasks'), lauf(['neu-1'], ''), lauf(['neu-1'], 'gibtsnicht')];
          console.log(JSON.stringify({r, geoeffnet}));
        """)
        self.assertEqual(out['r'], [True, False, False, False, False], 'nur ein neuer Entwurf allein lässt der Startseite den Vortritt; Reiter des Captains bleiben')
        self.assertEqual(out['geoeffnet'], ['tasks'])


if __name__ == '__main__':
    unittest.main()
