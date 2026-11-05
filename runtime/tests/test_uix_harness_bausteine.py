"""Baukasten und Raster (bausteine.js, 05.11.2026): Bausteine bleiben im Raster, die Vorgabe sieht aus wie bisher, die Wahl legt Reihenfolge und Sichtbarkeit fest, Grundfunktionen bleiben
im Client wie im Server dieselben. Reine Teile mit node, ohne Browser; die Leisten laufen gegen einen kleinen Stellvertreter des DOM."""
import unittest

from test_uix_contract import NODE, UIX, run_js

HARNESS = UIX / 'shells' / 'harness'
DATEIEN = [HARNESS / 'bausteine.js']

STELLVERTRETER = """
  const knoten = (id)=>{ const k = {dataset: id ? {baustein: id} : {}, style: {}, _aus: false, classList: {toggle(n, an){ k._aus = !!an; }, add(){}, contains(){ return k._aus; }}}; return k; };
  const behaelter = (...ids)=>{ const kinder = ids.map(knoten); return {kinder, querySelectorAll: ()=>kinder}; };
"""


class Baukasten(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_bausteine_bleiben_im_raster(self):
        out = run_js(DATEIEN, """
          const B = box.sedraHarness.bausteine;
          console.log(JSON.stringify({
            raus: B.klemmen({x: 99, y: -4, b: 99, h: 99, sichtbar: true}),
            breit: B.klemmen({x: 10, y: 1, b: 6, h: 1}),
            ungueltig: B.klemmen({x: 'a', y: null, b: undefined, h: NaN}),
            bewegt: B.bewegen({x: 3, y: 3, b: 4, h: 2, sichtbar: true}, -9, 100),
            gross: B.groesse({x: 9, y: 1, b: 3, h: 1, sichtbar: false}, 5, 2)}));
        """)
        self.assertEqual(out['raus'], {'x': 1, 'y': 1, 'b': 12, 'h': 20, 'sichtbar': True})
        self.assertEqual(out['breit'], {'x': 7, 'y': 1, 'b': 6, 'h': 1, 'sichtbar': True}, 'x + b - 1 bleibt höchstens 12')
        self.assertEqual(out['ungueltig'], {'x': 1, 'y': 1, 'b': 1, 'h': 1, 'sichtbar': True}, 'Unsinn wird zur kleinsten Zelle, nie zum Fehler')
        self.assertEqual((out['bewegt']['x'], out['bewegt']['y']), (1, 39), 'y + h - 1 bleibt höchstens 40')
        self.assertEqual((out['gross']['b'], out['gross']['x'], out['gross']['sichtbar']), (8, 5, False), 'wächst die Breite, rutscht x zurück; Sichtbarkeit bleibt')

    def test_die_vorgabe_ist_untereinander_und_die_wahl_liegt_darueber(self):
        out = run_js(DATEIEN, """
          const B = box.sedraHarness.bausteine;
          const vorgabe = B.rasterVon({start: {}});
          const wahl = B.rasterVon({start: {schritte: {x: 4, y: 5, b: 6, h: 3, sichtbar: true}, hilfe: {sichtbar: false}}});
          console.log(JSON.stringify({vorgabe: Object.values(vorgabe).map(b=>[b.x, b.b]), eigenLeer: B.hatEigenesRaster({start: {}}), eigen: B.hatEigenesRaster({start: {hilfe: {}}}),
                                      wahl: wahl.schritte, hilfe: wahl.hilfe.sichtbar, gruss: wahl.gruss, stil: B.rasterStil(wahl.schritte)}));
        """)
        self.assertEqual(out['vorgabe'], [[1, 12], [1, 12], [1, 12]], 'ohne Wahl: volle Breite')
        self.assertEqual((out['eigenLeer'], out['eigen']), (False, True), 'ohne Eintrag bleibt das Aussehen wie bisher (kein Raster)')
        self.assertEqual(out['wahl'], {'x': 4, 'y': 5, 'b': 6, 'h': 3, 'sichtbar': True})
        self.assertFalse(out['hilfe'])
        self.assertEqual(out['gruss']['b'], 12, 'ein nicht genannter Baustein behält die Vorgabe')
        self.assertEqual(out['stil'], {'gridColumn': '4 / span 6', 'gridRow': '5 / span 3'})

    def test_reihenfolge_genannte_zuerst_der_rest_in_vorgabe_reihenfolge(self):
        out = run_js(DATEIEN, """
          const B = box.sedraHarness.bausteine;
          const alle = ['a', 'b', 'c', 'd'];
          console.log(JSON.stringify([B.reihenfolge(alle, []), B.reihenfolge(alle, ['c', 'a']), B.reihenfolge(alle, ['x', 'd'])]));
        """)
        self.assertEqual(out[0], {'a': 10, 'b': 20, 'c': 30, 'd': 40})
        self.assertEqual(out[1], {'c': 10, 'a': 20, 'b': 30, 'd': 40})
        self.assertEqual(out[2], {'d': 10, 'a': 20, 'b': 30, 'c': 40}, 'Unbekanntes wird übergangen')

    def test_leiste_ordnet_blendet_aus_und_laesst_ohne_wahl_alles_wie_es_war(self):
        out = run_js(DATEIEN, STELLVERTRETER + """
          const B = box.sedraHarness.bausteine;
          const a = behaelter('x', 'y', 'z');
          B.reiheAnwenden(a, ['x', 'y', 'z'], {reihenfolge: [], ausblenden: []});
          const ohne = a.kinder.map(k=>[k.style.order, k._aus]);
          const b = behaelter('x', 'y', 'z');
          const lueck = knoten(null);
          B.reiheAnwenden(b, ['x', 'y', 'z'], {reihenfolge: ['z', 'x'], ausblenden: ['y']}, [{el: lueck, vor: 'x'}]);
          console.log(JSON.stringify({ohne, mit: b.kinder.map(k=>[k.dataset.baustein, k.style.order, k._aus]), lueck: lueck.style.order}));
        """)
        self.assertEqual(out['ohne'], [['', False]] * 3, 'ohne Wahl wird nichts gesetzt')
        self.assertEqual(out['mit'], [['x', '20', False], ['y', '30', True], ['z', '10', False]])
        self.assertEqual(out['lueck'], '19', 'ein Teil ohne Kennung folgt seinem Baustein')

    def test_leere_sitzung_ohne_wahl_untereinander_mit_wahl_auf_dem_raster(self):
        out = run_js(DATEIEN, STELLVERTRETER + """
          const B = box.sedraHarness.bausteine;
          const mach = layout=>{
            const kisten = []; const raster = {an: null};
            const kasten = {append(k){ kisten.push(k); }, classList: {toggle(n, an){ raster.an = an; }}};
            const teile = {gruss: knoten(null), schritte: knoten(null), hilfe: knoten(null)};
            const S = {_desktop: {layout}};
            B.startAnwenden(S, kasten, teile);
            return {reihe: kisten.map(k=>k.dataset.baustein), raster: raster.an, stil: teile.schritte.style.gridColumn || '', hilfeAus: teile.hilfe._aus};
          };
          console.log(JSON.stringify([mach(undefined), mach({start: {schritte: {x: 7, y: 2, b: 6, h: 2, sichtbar: true}, hilfe: {sichtbar: false}}})]));
        """)
        self.assertEqual(out[0], {'reihe': ['gruss', 'schritte', 'hilfe'], 'raster': False, 'stil': '', 'hilfeAus': False})
        self.assertEqual((out[1]['raster'], out[1]['stil'], out[1]['hilfeAus']), (True, '7 / span 6', True))

    def test_bausteine_im_client_und_im_server_sind_dieselben(self):
        from guppi_runtime.harness import desktop as server
        out = run_js(DATEIEN, "const B = box.sedraHarness.bausteine; console.log(JSON.stringify([B.START.map(x=>x[0]), B.ZEILE.map(x=>x[0]), B.WERKZEUGE.map(x=>x[0]), B.GRUND_WERKZEUGE, [B.SPALTEN, B.ZEILEN, B.HOEHE], B.MENUE.map(x=>x[0]), B.BLICK.map(x=>x[0]), B.GRUND_MENUE, B.GRUND_BLICK]));")
        self.assertEqual(tuple(out[0]), server.START_BLOECKE)
        self.assertEqual(tuple(out[1]), server.ZEILE_BAUSTEINE)
        self.assertEqual(tuple(out[2]), server.WERKZEUG_BAUSTEINE)
        self.assertEqual(tuple(out[3]), server.GRUND_WERKZEUGE)
        self.assertEqual(out[4], [server.RASTER_SPALTEN, server.RASTER_ZEILEN, server.RASTER_HOEHE])
        self.assertEqual((tuple(out[5]), tuple(out[6]), tuple(out[7]), tuple(out[8])), (server.MENUE_BAUSTEINE, server.BLICK_BAUSTEINE, server.GRUND_MENUE, server.GRUND_BLICK))


if __name__ == '__main__':
    unittest.main()
