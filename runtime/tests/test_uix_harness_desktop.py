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
          const S = {_desktop: Object.assign(D.LEER(), {start: {ausblenden: ['wissen'], zuordnung: {models: 'system'}}})};
          const k = D.startKonfig(S, konfig);
          console.log(JSON.stringify({gleich, ausblenden: k.ausblenden, zuordnung: k.zuordnung, gruppen: k.gruppen, vorgabeUnveraendert: konfig.ausblenden}));
        """)
        self.assertTrue(out['gleich'], 'ohne Wahl bleibt die Vorgabe dieselbe')
        self.assertEqual(out['ausblenden'], ['hardware', 'wissen'])
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


if __name__ == '__main__':
    unittest.main()
