"""SPEC_UIX_STUFE6_RAHMEN_v1 (R1 bis R8): Leiste ordnet sich, Prüfwerkzeuge nur mit Schalter, Mini-Hub als schwebendes Fenster,
„Leeren“ mit Rückfrage, eine Zahl „offen“, Nachweis-Spalte schmal als Reiter und leer eingeklappt, KMU-Kopf kompakt."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_uix_contract import NODE, UIX, run_js

TESTS = Path(__file__).resolve().parent
BENCH = TESTS.parent / 'benchmarks'


class Rein(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest('node is not installed')

    def test_r1_verteilen(self):
        out = run_js([UIX / 'ui' / 'leiste.js'], """
          const V = box.sedraLeiste.verteilen;
          const z = (id, order, breite, ton)=>({id, order, breite, ton: ton || ''});
          const zellen = [z('state', 10, 120), z('model', 11, 170), z('gpu', 12, 110), z('decisions', 13, 150, 'warn'), z('tasks', 14, 100), z('slots', 60, 100)];
          const fest = zellen.map(x=>Object.assign({}, x, x.id === 'slots' ? {fest: true} : {}));
          console.log(JSON.stringify([V(zellen, 2000, 50, 6), V(zellen, 600, 50, 6), V(zellen, 300, 50, 6), V([], 100, 50, 6), V(fest, 600, 50, 6)]));
        """)
        self.assertNotIn('slots', out[4]['mehr'], 'eine feste Zelle (Rahmen) zieht nie um')
        self.assertEqual(out[0]['mehr'], [])
        self.assertEqual(out[1]['mehr'], ['gpu', 'tasks', 'slots'], 'die höchsten order zuerst hinaus, bis es passt')
        self.assertIn('decisions', out[2]['sichtbar'], 'warn bleibt immer sichtbar')
        self.assertEqual(out[3], {'sichtbar': [], 'mehr': []})

    def test_mini_hub_lage_rein(self):
        out = run_js([UIX / 'ui' / 'wechsel.js'], """
          const L = box.sedraWechsel.hubLage;
          console.log(JSON.stringify([L('{"x":5000,"y":-3,"klein":true}', 1400, 860, 220, 120), L('kaputt', 1400, 860), L('{"klein":true}', 1400, 860), L('[1,2]', 1400, 860)]));
        """)
        self.assertEqual(out[0], {'x': 1176, 'y': 4, 'klein': True}, 'ins Fenster begrenzt')
        self.assertIsNone(out[1]); self.assertEqual(out[2], {'x': None, 'y': None, 'klein': True}); self.assertIsNone(out[3])

    def test_r4_r5_gespraech(self):
        talk = UIX / 'tools' / 'talk'
        run = subprocess.run([NODE, '-r', str(TESTS / 'uix_spec_dom.js'), 'test.spec.js'], cwd=talk, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        text = (talk / 'tool.js').read_text(encoding='utf-8')
        self.assertNotIn("'Grüne zuerst'", text, 'S6-E2: kein Knopf mehr')
        self.assertIn("'Geprüft schnell ✓'", text)


class Server(unittest.TestCase):
    def test_r2_pruefwerkzeug_nur_mit_schalter(self):
        from guppi_runtime.desk.gateway import Gateway
        with tempfile.TemporaryDirectory() as tmp:
            g = Gateway(Path(tmp))
            m = g.manifest()
            self.assertNotIn('rahmen-probe', [t['id'] for t in m['tools']])
            self.assertIn('rahmen-probe', m['pruefung'])
            g.entwicklung = True
            m = g.manifest()
            self.assertIn('rahmen-probe', [t['id'] for t in m['tools']])
            self.assertEqual(m['pruefung'], [])

    def test_r6_antraege_sind_keine_aufgaben(self):
        from host_isolation import setUpModule, tearDownModule
        setUpModule(); self.addCleanup(tearDownModule)
        sys.path.insert(0, str(BENCH))
        from guppi_runtime.uix_server import UIXHub
        from test_wissen_desk import ARCH, switch_on
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            project = Path(tmp) / 'p'
            switch_on(project)
            (project / 'notizen').mkdir(parents=True)
            (project / 'notizen' / 'a.md').write_text('# A\n\nText.\n', encoding='utf-8')
            hub = UIXHub(project, ARCH)
            self.addCleanup(hub.close)
            out = hub.act({'type': 'wissen', 'verb': 'quelle_beantragen', 'args': {'adapter': 'markdown', 'wurzel': 'projekt', 'pfad': 'notizen/a.md', 'stufe': 1}})['result']
            missions = hub.missions()
            antrag = [m for m in missions if m['antrag']]
            self.assertEqual(len(antrag), 1)
            self.assertFalse(antrag[0]['offen'])
            self.assertEqual(hub.objects_view({'type': 'task'})['items'], [], 'ein Antrag steht nicht unter Aufgaben')
            self.assertEqual(hub.strip_view()['tasks']['value'], 0)
            self.assertTrue(any(d['id'] == out['decision_id'] for d in hub.decisions_view()['items']), 'er steht im Posteingang')


class ImBrowser(unittest.TestCase):
    """R1, R3, R7, R8 über alle Shells (Chromium aus playwright)."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest('playwright fehlt')
        sys.path.insert(0, str(BENCH))
        import uix_check
        cls.uix = uix_check
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as exc:
            cls.pw.stop()
            raise unittest.SkipTest(f'kein Browser: {exc}')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def seite(self, shell, breite, hoehe=700, **kw):
        url, stop = self.uix.start_server(lambda *_: None, shell=shell, **kw)
        self.addCleanup(stop)
        page = self.browser.new_page(viewport={'width': breite, 'height': hoehe})
        self.addCleanup(page.close)
        fehler = []
        page.on('pageerror', lambda e: fehler.append(str(e)))
        page.goto(url); self.uix.wait_until_started(page); page.wait_for_timeout(2200)
        return page, fehler

    def test_r1_leiste_und_mini_hub_in_jeder_shell(self):
        """R1 und der Mini-Hub (Captain 27.10.2026, 11:02 – ersetzt S6-E1): Rekorder und Umschalter schweben als eigenes Fenster."""
        for shell in ('cockpit', 'wissensbasis', 'paperclip', 'minimal', 'gateway-kmu'):
            for breite in (1400, 1024):
                with self.subTest(shell=shell, breite=breite):
                    page, fehler = self.seite(shell, breite)
                    page.wait_for_selector('.sx-hub .sx-hub-shell', timeout=5000)
                    hub = page.evaluate("""()=>{const h=document.querySelector('.sx-hub'), r=h.getBoundingClientRect();
                        return {fix: getComputedStyle(h).position, shells: h.querySelectorAll('.sx-hub-shell').length, an: (h.querySelector('.sx-hub-shell.on')||{}).textContent,
                                rek: !!h.querySelector('.sx-hub-leiste .sx-chip:not(.sx-umschalter)'), drin: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight}}""")
                    self.assertEqual(hub['fix'], 'fixed'); self.assertGreaterEqual(hub['shells'], 2); self.assertTrue(hub['an']); self.assertTrue(hub['rek']); self.assertTrue(hub['drin'])
                    self.assertEqual(page.evaluate("()=>document.documentElement.scrollWidth - innerWidth"), 0)
                    if shell == 'cockpit':
                        leiste = page.evaluate("()=>{const h=document.querySelector('.ck-strip'); return [h.scrollWidth - h.clientWidth, [...h.querySelectorAll('.ck-gauge b')].filter(b=>b.offsetParent && b.scrollWidth > b.clientWidth + 1).length]}")
                        self.assertEqual(leiste, [0, 0], 'kein Wert abgeschnitten, kein Überhang')
                        self.assertEqual(page.locator('[data-tool="rahmen-probe"]').count(), 0, 'R2: ohne Schalter kein Prüfwerkzeug')
                    self.assertEqual(fehler, [])

    def test_mini_hub_ziehen_klappen_merken_wechseln(self):
        page, fehler = self.seite('cockpit', 1400, 860)
        page.wait_for_selector('.sx-hub .sx-hub-shell', timeout=5000)
        kopf = page.locator('.sx-hub-kopf').bounding_box()
        page.mouse.move(kopf['x'] + 60, kopf['y'] + 8); page.mouse.down(); page.mouse.move(300, 120, steps=5); page.mouse.up()
        oben = page.evaluate("()=>Math.round(document.querySelector('.sx-hub').getBoundingClientRect().top)")
        self.assertLess(oben, 200, 'gezogen')
        page.locator('.sx-hub-zu').click()
        self.assertTrue(page.locator('.sx-hub-klein').is_visible()); self.assertFalse(page.locator('.sx-hub-fenster').is_visible())
        page.reload(); self.uix.wait_until_started(page); page.wait_for_timeout(1500)
        self.assertTrue(page.locator('.sx-hub-klein').is_visible(), 'zusammengeklappt bleibt es nach dem Neuladen')
        self.assertLess(page.evaluate("()=>Math.round(document.querySelector('.sx-hub').getBoundingClientRect().top)"), 200, 'die Lage bleibt')
        page.locator('.sx-hub-klein').click()
        page.locator('.sx-hub-kopf').dblclick()
        self.assertGreater(page.evaluate("()=>document.querySelector('.sx-hub').getBoundingClientRect().top"), 400, 'Doppelklick: zurück nach unten rechts')
        page.locator('.sx-hub-shell', has_text='Paperclip').click(); page.wait_for_timeout(2500)
        self.uix.wait_until_started(page)
        self.assertEqual(page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.id"), 'paperclip', 'ein Klick wechselt die Oberfläche')
        self.assertEqual(fehler, [])

    def test_r1_mehr_zeigt_die_uebrigen(self):
        page, fehler = self.seite('cockpit', 1024)
        mehr = page.locator('.ck-strip .lst-mehr')
        self.assertTrue(mehr.is_visible())
        n = int(mehr.locator('b').inner_text().strip('+ ▾'))
        mehr.click(); page.wait_for_timeout(200)
        self.assertEqual(page.locator('.lst-panel .ck-gauge').count(), n)
        page.keyboard.press('Escape'); page.wait_for_timeout(200)
        self.assertTrue(page.evaluate("()=>document.querySelector('.lst-panel').hidden"))
        self.assertEqual(fehler, [])

    def test_r7_fundstelle_schmal_und_leer(self):
        from test_uix_wissen_v2 import mit_quelle
        page, fehler = self.seite('wissensbasis', 1400, 860, prepare=mit_quelle, switches={'wissen': True})
        breite = lambda: page.evaluate("()=>{const n=document.querySelector('.fr-nachweis'); return n ? Math.round(n.getBoundingClientRect().width) : -1}")
        self.assertLessEqual(breite(), 40, 'ohne Treffer ist die Fundstelle eingeklappt')
        page.fill('.t-wissen input.t-wissen-frage', 'Lease'); page.press('.t-wissen input.t-wissen-frage', 'Enter'); page.wait_for_timeout(1200)
        page.locator('.t-wissen-treffer').first.locator('button', has_text='Fundstelle').click(); page.wait_for_timeout(900)
        self.assertGreaterEqual(breite(), 280, 'mit Treffer klappt sie auf')
        page.set_viewport_size({'width': 1024, 'height': 700}); page.wait_for_timeout(600)
        self.assertTrue(page.locator('.fr-seg-schmal').is_visible(), 'schmal: Reiter')
        self.assertEqual(page.evaluate("()=>document.querySelector('.fr-body').dataset.zeige"), 'inhalt')
        page.press('.t-wissen input.t-wissen-frage', 'Enter'); page.wait_for_timeout(1200)          # neue Suche: der Treffer ist wieder zu
        page.locator('.t-wissen-treffer').first.locator('button', has_text='Fundstelle').click(); page.wait_for_timeout(900)
        self.assertEqual(page.evaluate("()=>document.querySelector('.fr-body').dataset.zeige"), 'nachweis', 'ein Treffer schaltet auf die Fundstelle')
        self.assertIn('Vor dem Laden', page.locator('.t-fundstelle').inner_text())
        self.assertEqual(fehler, [])

    def test_r8_kmu_arbeitsbereich(self):
        page, fehler = self.seite('gateway-kmu', 1024, 700)
        anteil = page.evaluate("()=>document.querySelector('.sh-gateway-kmu-body').getBoundingClientRect().height / innerHeight")
        self.assertGreaterEqual(anteil, 0.55)
        self.assertEqual(fehler, [])


if __name__ == '__main__':
    unittest.main()
