"""Der Reiter Live der Workflow-Apps im echten Browser: Prozesse melden ihren Schritt, im Diagramm leuchtet er (fertig, läuft, wartet, Fehler)."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sedra_runtime.workflows import live  # noqa: E402

P = 'vollautomatischer-bau'


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1')
class LiveImBrowser(unittest.TestCase):
    def session(self, run, melden=None):
        from playwright.sync_api import sync_playwright
        from uix_check import start_server
        from sedra_runtime.workflows import selbstabbild
        from sedra_runtime.workflows.store import WorkflowStore
        stand = {}

        def vorbereiten(hub):
            selbstabbild.anlegen(WorkflowStore(hub.project_root))
            stand['root'] = hub.project_root
            if melden:
                melden(hub.project_root)
        url, stop = start_server(lambda *a: None, shell='harness', prepare=vorbereiten)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1500, 'height': 1050})
                fehler = []
                page.on('pageerror', lambda e: fehler.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url)
                page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
                run(page, stand['root'])
                self.assertEqual(fehler, [])
                browser.close()
        finally:
            stop()
            import host_isolation
            host_isolation.tearDownModule()

    def live_tab(self, page, kind='workflow'):
        page.evaluate("kind=>window.sedraBoot.ctx.bus.emit('object.open',{type:kind,id:'alle',title:kind==='scenario'?'Szenario Studio':'n8n Workflows'})", kind)
        sel = '.t-scenario' if kind == 'scenario' else '.t-n8n-workflow'
        app = page.locator(sel).first
        app.locator('.t-wf-svg').wait_for()
        page.wait_for_function("s=>{const e=document.querySelector(s);return e && !e.inert;}", arg=sel)
        app.get_by_role('tab', name='Live').click()
        return app

    def test_ohne_meldung_steht_ein_klarer_leerzustand(self):
        def run(page, root):
            app = self.live_tab(page)
            app.locator('.t-wf-live-summe').filter(has_text='Gerade läuft nichts').wait_for(timeout=15000)
            self.assertTrue(app.locator('.t-wf-live-leer').is_visible())
            self.assertEqual(app.locator('.t-wf-live-karte').count(), 0)
        self.session(run)

    def test_schritt_leuchtet_und_folgt_der_meldung(self):
        def melden(root):
            live.melde(root, P, 'auftrag', 'laeuft')
            live.melde(root, P, 'spec', 'laeuft', text='Spec wird geprüft')
            live.melde(root, P, 'bauen', 'laeuft', text='Stufe S1, Versuch 1 von 6')

        def run(page, root):
            app = self.live_tab(page)
            karte = app.locator('.t-wf-live-karte')
            karte.wait_for(timeout=20000)
            self.assertEqual(karte.locator('.t-wf-live-chip').inner_text(), 'läuft')
            self.assertIn('Stufe bauen', karte.locator('.t-wf-live-schritt').inner_text())
            self.assertIn('Versuch 1 von 6', karte.locator('.t-wf-live-text').inner_text())
            page.wait_for_function("()=>document.querySelectorAll('.t-wf-live-karte .t-wf-node.live-laeuft').length===1", timeout=20000)
            self.assertEqual(karte.locator('.t-wf-node.live-fertig').count(), 2)
            # der Prozess geht weiter: Stufe bauen ist fertig, der Test läuft; die Anzeige folgt ohne Neuladen
            live.melde(root, P, 'stufe-ok', 'laeuft', text='Versteckter Test')
            page.wait_for_function("()=>document.querySelectorAll('.t-wf-live-karte .t-wf-node.live-fertig').length===3", timeout=15000)
            self.assertIn('Versteckter Test', karte.locator('.t-wf-live-text').inner_text())
            # ein Fehler im Test: der Schritt bleibt rot markiert
            live.melde(root, P, 'stufe-ok', 'fehler', text='Test fehlgeschlagen')
            page.wait_for_function("()=>document.querySelectorAll('.t-wf-live-karte .t-wf-node.live-fehler').length===1", timeout=15000)
            self.assertEqual(karte.locator('.t-wf-live-chip').inner_text(), 'Fehler')
            self.assertIn('Test', karte.locator('.t-wf-live-eintrag').first.inner_text())
        self.session(run, melden)

    def test_wartet_auf_den_captain_und_ende(self):
        def melden(root):
            live.melde(root, P, 'pruefung', 'wartet', text='Das Produkt wartet auf deine Prüfung')

        def run(page, root):
            app = self.live_tab(page)
            app.locator('.t-wf-live-chip').wait_for(timeout=20000)
            self.assertEqual(app.locator('.t-wf-live-chip').inner_text(), 'wartet auf dich')
            self.assertIn('1 wartet auf dich', app.locator('.t-wf-live-summe').inner_text())
            page.wait_for_function("()=>document.querySelectorAll('.t-wf-live-karte .t-wf-node.live-wartet').length===1", timeout=20000)
            live.melde(root, P, None, 'fertig')
            page.wait_for_function("()=>!!document.querySelector('.t-wf-live-chip[data-zustand=fertig]')", timeout=15000)
            self.assertEqual(app.locator('.t-wf-live-karte .t-wf-node.live-wartet').count(), 0)
        self.session(run, melden)

    def test_alte_meldung_steht_als_keine_meldung(self):
        def melden(root):
            alt = (datetime.now(timezone.utc) - timedelta(seconds=900)).isoformat(timespec='seconds')
            live.melde(root, P, 'bauen', 'laeuft', zeit=alt)

        def run(page, root):
            app = self.live_tab(page)
            app.locator('.t-wf-live-chip').wait_for(timeout=20000)
            self.assertEqual(app.locator('.t-wf-live-chip').inner_text(), 'keine Meldung')
            self.assertIn('zuletzt gemeldet vor', app.locator('.t-wf-live-schritt').inner_text())
            self.assertIn('1 ohne Meldung', app.locator('.t-wf-live-summe').inner_text())
        self.session(run, melden)

    def test_szenario_studio_hat_denselben_reiter(self):
        def melden(root):
            live.melde(root, P, 'spec', 'laeuft')

        def run(page, root):
            app = self.live_tab(page, 'scenario')
            app.locator('.t-wf-live-karte').wait_for(timeout=20000)
            page.wait_for_function("()=>document.querySelectorAll('.t-scenario .t-wf-live-karte .t-wf-node.live-laeuft').length===1", timeout=20000)
        self.session(run, melden)

    def test_der_reiter_fragt_nur_solange_er_offen_ist(self):
        def run(page, root):
            app = self.live_tab(page)
            app.locator('.t-wf-live-summe').filter(has_text='Gerade läuft nichts').wait_for(timeout=15000)
            page.evaluate("""()=>{window.__n = 0; const f = window.fetch;
                window.fetch = function(u, o){ if(o && o.body && String(o.body).indexOf('"verb":"live"') >= 0) window.__n++; return f.apply(this, arguments); }; }""")
            app.get_by_role('tab', name='Editor').click()
            page.wait_for_timeout(500)
            n0 = page.evaluate('()=>window.__n')
            page.wait_for_timeout(6000)
            self.assertEqual(page.evaluate('()=>window.__n'), n0, 'im Editor-Reiter wird nicht mehr abgefragt')
        self.session(run)


if __name__ == '__main__':
    unittest.main()
