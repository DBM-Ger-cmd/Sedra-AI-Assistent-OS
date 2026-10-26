"""Stufe 2: das Cockpit-Dock ohne Neuaufbau (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §4, §9.6, §10.4; Abnahme A3, A4, A5, A6, A14, A16).

Rein mit node: `sanitizeLayout` (dock.js) und `ordnen`/`uebernahme` (ui/stand.js). Im Browser mit dem Prüfprojekt von uix_check:
ein Reiterwechsel hängt in der anderen Gruppe nichts ein, ein Einzelstück zeichnet nie in zwei Gruppen, ein Neuladen bringt die
Reiter aus dem Arbeitsstand zurück, und ein kaputtes Layout im Browser bricht die Werkbank nicht."""
import sys
import unittest
from pathlib import Path

from test_uix_contract import NODE, UIX, run_js

COCKPIT = UIX / 'shells' / 'cockpit'
BENCH = Path(__file__).resolve().parents[1] / 'benchmarks'


@unittest.skipUnless(NODE, 'node fehlt')
class Rein(unittest.TestCase):
    def test_layout_wird_geprueft(self):
        """A14: kaputt, fremd, zu tief, doppelt → nur Gültiges bleibt; nichts Gültiges → null."""
        out = run_js([COCKPIT / 'dock.js'], """
          const dk = box.sedraDock, g = (id, panes, active)=>({kind:'group', id, panes, active});
          const p = (type, id)=>({key: type + ':' + id, object: {type, id, title: id, böse: 'x'}});
          const tief = {kind:'split', direction:'row', children:[{kind:'split', direction:'row', children:[{kind:'split', direction:'row', children:[{kind:'split', direction:'row', children:[{kind:'split', direction:'row', children:[g('g9', [p('task','T')], 'task:T')]}]}]}]}]};
          console.log(JSON.stringify({
            leer: dk.sanitizeLayout(null), text: dk.sanitizeLayout('kaputt'), ohneReiter: dk.sanitizeLayout(g('g1', [], null)),
            gut: dk.sanitizeLayout({kind:'split', direction:'row', children:[g('g1', [p('task','A'), p('task','A'), p('logbook','audit')], 'task:X'), g('g1', [p('model','alle')], null), {kind:'weird'}]}),
            tief: dk.sanitizeLayout(tief), fremd: dk.sanitizeLayout(g('g1', [{key:'x', object:{type:'<script>', id:'1'}}], null))
          }));
        """)
        self.assertIsNone(out['leer']); self.assertIsNone(out['text']); self.assertIsNone(out['ohneReiter'])
        self.assertIsNone(out['tief']); self.assertIsNone(out['fremd'])
        gut = out['gut']
        self.assertEqual(gut['kind'], 'split'); self.assertEqual(len(gut['children']), 2)
        links, rechts = gut['children']
        self.assertEqual([x['key'] for x in links['panes']], ['task:A', 'logbook:audit'])          # doppelt entfernt
        self.assertEqual(links['active'], 'task:A')                                                  # unbekannter aktiver → erster
        self.assertNotEqual(links['id'], rechts['id'])                                               # doppelte Gruppen-ID ersetzt
        self.assertNotIn('böse', links['panes'][0]['object'])

    def test_arbeitsstand_ordnen_und_uebernehmen(self):
        """§10.4/A20: das jüngste vorn; was die Shell nicht zeichnen kann, übernimmt sie nicht und meldet es nicht als geschlossen."""
        out = run_js([UIX / 'ui' / 'stand.js'], """
          const S = box.sedraStand;
          const o = (type, id)=>({type, id, title: id, unsinn: 1});
          console.log(JSON.stringify({
            ordnung: S.ordnen([o('task','A'), o('task','B'), o('task','A'), o('logbook','audit')], {'task:B': 5, 'logbook:audit': 3}).map(S.schluessel),
            sauber: Object.keys(S.ordnen([o('task','A')])[0]).sort(),
            ueber: S.uebernahme({offen: [o('wissen','speicher'), o('task','A'), o('gateway','alle')], vorn: 'gateway:alle', shell: 'paperclip'},
                                [o('task','A')], x=>x.type !== 'gateway')
          }));
        """)
        self.assertEqual(out['ordnung'], ['task:B', 'logbook:audit', 'task:A'])
        self.assertEqual(out['sauber'], ['id', 'title', 'type'])
        u = out['ueber']
        self.assertEqual([x['type'] for x in u['neu']], ['wissen']); self.assertEqual([x['type'] for x in u['ohne']], ['gateway'])
        self.assertIsNone(u['vorn'])                       # was vorn lag, kann diese Shell nicht zeichnen
        self.assertEqual(u['von'], 'paperclip')


class ImBrowser(unittest.TestCase):
    """A3, A5, A6, A16 im echten Browser (Chromium aus playwright), auf dem Prüfprojekt von uix_check."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest('playwright fehlt')
        sys.path.insert(0, str(BENCH))
        import uix_check
        cls.uix = uix_check
        cls.url, cls.stop = uix_check.start_server(lambda *_: None, shell='cockpit')
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as exc:
            cls.pw.stop(); cls.stop()
            raise unittest.SkipTest(f'kein Browser: {exc}')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.stop()

    def seite(self):
        page = self.browser.new_page(viewport={'width': 1400, 'height': 900})
        self.fehler = []
        page.on('pageerror', lambda e: self.fehler.append(str(e)))
        page.goto(self.url); self.uix.wait_until_started(page)
        # jeder Test beginnt leer: Arbeitsstand und Ablage auf dem Server, Layout und Sitzung im Browser
        page.evaluate("""async()=>{ await fetch('/api/arbeitsstand/leeren', {method: 'POST', body: '{}', headers: {'Content-Type': 'application/json',
                         'X-GUPPI-Token': decodeURIComponent(location.hash.slice(1))}}); localStorage.clear(); sessionStorage.clear(); }""")
        page.reload(); self.uix.wait_until_started(page); page.wait_for_timeout(1200)
        self.addCleanup(page.close)
        return page

    def oeffnen(self, page, obj, gruppe=None):
        page.evaluate("([o, g])=>window.sedra.shells.get('cockpit').dock.open(o, g || undefined)", [obj, gruppe])
        page.wait_for_timeout(700)

    def aufgaben(self, page):
        return page.evaluate("async()=>(await window.sedraBoot.ctx.api('/api/missions')).filter(m=>m.status==='active').map(m=>m.mission_id)")

    def zaehlen(self, page):
        page.evaluate("""()=>{ if(window.__m) return; window.__m = []; const L = window.sedraLifecycle, o = L.mountTool;
                         L.mountTool = function(mod, el, ctx){ window.__m.push(mod.id + '@' + ((ctx.object || {}).type || '') + ':' + ((ctx.object || {}).id || '')); return o.apply(this, arguments); }; }""")
        page.evaluate("()=>{ window.__m.length = 0; }")

    def sichtbar(self, page):
        return page.evaluate("""()=>[...document.querySelectorAll('.dk-group')].map(g=>{
            const b = g.querySelector('.dk-body > .dk-pane-box:not([hidden])'); return b ? b.innerText.slice(0, 200) : ''; })""")

    def test_reiterwechsel_haengt_die_andere_gruppe_nicht_neu_ein(self):
        """A3/A6: geteilt, rechts das Logbuch; links zwischen Grenzen und Modulen wechseln → rechts keine Einhängung."""
        page = self.seite()
        self.oeffnen(page, {'type': 'boundary', 'id': 'projekt', 'title': 'Modus und Grenzen'})
        page.locator('.dk-split-btn').first.click(); page.wait_for_timeout(400)
        self.oeffnen(page, {'type': 'logbook', 'id': 'audit', 'title': 'Logbuch'}, 'g2')
        self.oeffnen(page, {'type': 'module', 'id': 'alle', 'title': 'Module', 'collection': True}, 'g1')
        self.zaehlen(page)
        links = page.locator('.dk-group').first
        links.locator('.dk-tab', has_text='Modus und Grenzen').click(); page.wait_for_timeout(600)
        links.locator('.dk-tab', has_text='Module').click(); page.wait_for_timeout(600)
        m = page.evaluate('window.__m')
        self.assertFalse([x for x in m if x.startswith('logbook')], m)           # die rechte Gruppe bleibt, wie sie ist
        self.assertLessEqual(len(m), 2, m)                                       # ≤ 1 je Wechsel
        self.assertEqual(self.fehler, [])

    def test_ein_einzelstueck_zeichnet_nie_in_zwei_gruppen(self):
        """A5/D2-3: zwei Aufgaben nebeneinander → eine zeigt die Aufgabe, die andere den Hinweis; „Hierher holen“ tauscht."""
        page = self.seite()
        a, b = self.aufgaben(page)[:2]
        self.oeffnen(page, {'type': 'task', 'id': a, 'title': 'Erste'})
        page.locator('.dk-split-btn').first.click(); page.wait_for_timeout(400)
        self.oeffnen(page, {'type': 'task', 'id': b, 'title': 'Zweite'}, 'g2')
        links, rechts = self.sichtbar(page)
        self.assertIn('nur ein Objekt zugleich', links); self.assertNotIn('nur ein Objekt zugleich', rechts)
        page.locator('.dk-group').first.locator('.dk-hinweis button').click(); page.wait_for_timeout(900)
        links, rechts = self.sichtbar(page)
        self.assertNotIn('nur ein Objekt zugleich', links); self.assertIn('nur ein Objekt zugleich', rechts)
        self.assertEqual(page.evaluate("()=>document.querySelectorAll('.dk-pane-box:not([hidden]) .dk-tool[data-tool=\"task\"]').length"), 1)
        self.assertEqual(self.fehler, [])

    def test_neuladen_bringt_die_reiter_aus_dem_arbeitsstand_zurueck(self):
        """A16 (Cockpit): offene Reiter stehen im Arbeitsstand; nach Neuladen ohne gespeichertes Layout sind sie wieder da."""
        page = self.seite()
        self.oeffnen(page, {'type': 'logbook', 'id': 'audit', 'title': 'Logbuch'})
        self.oeffnen(page, {'type': 'module', 'id': 'alle', 'title': 'Module', 'collection': True})
        page.wait_for_timeout(900)                                               # das Melden ist gebündelt (500 ms)
        stand = page.evaluate("()=>window.sedraBoot.ctx.api('/api/arbeitsstand')")
        keys = [o['type'] + ':' + o['id'] for o in stand['offen']]
        self.assertIn('logbook:audit', keys); self.assertEqual(stand['vorn'], 'module:alle')
        page.evaluate("()=>localStorage.removeItem('sedra.cockpit.layout')")     # wie eine andere Shell vorher: kein eigenes Layout
        page.reload(); self.uix.wait_until_started(page); page.wait_for_timeout(1500)
        tabs = page.evaluate("()=>[...document.querySelectorAll('.dk-tab span')].map(s=>s.textContent)")
        self.assertIn('Logbuch', tabs); self.assertIn('Module', tabs)
        self.assertEqual(page.evaluate("()=>(document.querySelector('.dk-tab.on span')||{}).textContent"), 'Module')

    def test_kaputtes_layout_bricht_die_werkbank_nicht(self):
        """A14 im Browser: Unsinn in localStorage → die Werkbank startet, ohne Fehler auf der Seite."""
        page = self.seite()
        page.evaluate("()=>localStorage.setItem('sedra.cockpit.layout', JSON.stringify({layout:{kind:'split', children:[{kind:'group', panes:[{object:{type:'<x>'}}]}]}, v:1}))")
        page.reload(); self.uix.wait_until_started(page); page.wait_for_timeout(1500)
        self.assertGreaterEqual(page.evaluate("()=>document.querySelectorAll('.dk-tab').length"), 1)
        self.assertEqual(self.fehler, [])

    def test_schliessen_meldet_und_vergisst(self):
        """A11 im Browser: Schließen sendet object.close und nimmt das Objekt aus dem Arbeitsstand."""
        page = self.seite()
        self.oeffnen(page, {'type': 'logbook', 'id': 'audit', 'title': 'Logbuch'})
        page.evaluate("()=>{ window.__zu = []; window.sedraBoot.ctx.bus.on('object.close', e=>window.__zu.push(e.type + ':' + e.id)); }")
        page.locator('.dk-tab', has_text='Logbuch').locator('.dk-x').click(); page.wait_for_timeout(900)
        self.assertEqual(page.evaluate('window.__zu'), ['logbook:audit'])
        stand = page.evaluate("()=>window.sedraBoot.ctx.api('/api/arbeitsstand')")
        self.assertNotIn('logbook:audit', [o['type'] + ':' + o['id'] for o in stand['offen']])


if __name__ == '__main__':
    unittest.main()
