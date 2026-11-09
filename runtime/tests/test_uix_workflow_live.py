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


def lauf_anlegen(root, lid, status, gestartet, ende=None, name='Tests', log='', pid=None):
    """Einen Eintrag im Register der Harness-Läufe schreiben (so, wie ihn die Harness anlegt)."""
    import json
    ordner = Path(root) / 'runtime_data' / 'harness' / 'laeufe' / lid
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / 'lauf.json').write_text(json.dumps({'id': lid, 'lauf': 'run_tests', 'name': name, 'parameter': {}, 'argv': ['python', 'x'], 'ordner_abs': str(root), 'zeitlimit_min': 30,
                                                 'gpu': 'keine', 'modell_weg': False, 'sitzung_id': None, 'antwort_id': None, 'aufgabe_id': None, 'karte_id': None, 'projekt': 'p',
                                                 'pid': pid, 'start_zeit_pid': None, 'gestartet': gestartet, 'ende': ende, 'exit': 0 if status == 'ok' else (None if status == 'laeuft' else 1),
                                                 'status': status, 'grund': None, 'fortschritt': None, 'fortschritt_regel': {'art': 'text'}}), encoding='utf-8')
    (ordner / 'ausgabe.log').write_text(log, encoding='utf-8')


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1')
class LiveImBrowser(unittest.TestCase):
    def session(self, run, melden=None, mit_hub=None):
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
            if mit_hub:
                mit_hub(hub)
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

    def test_fabrikhalle_zeigt_laeufe_und_die_wartende_freigabe(self):
        jetzt = datetime.now(timezone.utc)
        iso = lambda d: d.isoformat(timespec='seconds')

        def hub_vorbereiten(hub):
            root = hub.project_root
            lauf_anlegen(root, 'L-AAAA0001', 'laeuft', iso(jetzt - timedelta(minutes=3)), name='Tests der Fabrik', log='Gruppe 3 von 6\n', pid=os.getpid())
            lauf_anlegen(root, 'L-AAAA0002', 'ok', iso(jetzt - timedelta(hours=1)), iso(jetzt - timedelta(minutes=50)), name='Selbsttest')
            lauf_anlegen(root, 'L-AAAA0003', 'fehler', iso(jetzt - timedelta(hours=2)), iso(jetzt - timedelta(hours=1, minutes=55)), name='Spec prüfen')
            hub.act({'type': 'wissen', 'verb': 'quelle_beantragen', 'args': {'adapter': 'markdown', 'wurzel': 'repo', 'pfad': 'docs', 'stufe': 1}})

        def run(page, root):
            app = self.live_tab(page)
            halle = app.locator('.t-wf-fabrik')
            halle.locator('[data-art=laeufe]').filter(has_text='1 Lauf läuft').wait_for(timeout=20000)
            self.assertIn('1 Freigabe wartet auf dich', halle.locator('[data-art=freigaben]').inner_text())
            aktiv = halle.locator('.t-wf-fabrik-lauf.aktiv')
            self.assertIn('Tests der Fabrik · läuft', aktiv.inner_text())
            self.assertIn('Gruppe 3 von 6', aktiv.inner_text())
            self.assertEqual(halle.locator('.t-wf-fabrik-lauf[data-status=ok]').count(), 1)
            self.assertEqual(halle.locator('.t-wf-fabrik-lauf[data-status=fehler]').count(), 1)
            self.assertIn('fertig', halle.locator('.t-wf-fabrik-lauf[data-status=ok]').inner_text())
            self.assertNotIn('python', halle.inner_text(), 'Befehl und Pfade bleiben draußen')
            self.assertEqual(halle.locator('.t-wf-fabrik-karte').count(), 1)
            # ein Klick auf die Freigabe führt in den Posteingang
            halle.locator('[data-art=freigaben]').click()
            page.get_by_text('Wissensquelle freigeben', exact=False).first.wait_for(timeout=20000)
        self.session(run, mit_hub=hub_vorbereiten)

    def test_fabrikhalle_ohne_laeufe_sagt_es(self):
        def run(page, root):
            app = self.live_tab(page)
            halle = app.locator('.t-wf-fabrik')
            halle.locator('[data-art=laeufe]').filter(has_text='0 Läufe laufen').wait_for(timeout=20000)
            self.assertIn('Gerade läuft kein Lauf.', halle.inner_text())
            self.assertIn('0 Freigaben warten auf dich', halle.locator('[data-art=freigaben]').inner_text())
            self.assertFalse(halle.locator('[data-art=freigaben]').evaluate("e=>e.classList.contains('wartet')"))
        self.session(run)

    def test_roter_knopf_stoppt_den_lauf_haelt_die_fabrik_an_und_gibt_sie_mit_rueckfrage_frei(self):
        import subprocess
        from sedra_runtime.workflows import fabrik
        kind = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
        self.addCleanup(lambda: kind.poll() is None and kind.kill())
        jetzt = datetime.now(timezone.utc)

        def hub_vorbereiten(hub):
            lauf_anlegen(hub.project_root, 'L-BBBB0001', 'laeuft', (jetzt - timedelta(minutes=4)).isoformat(timespec='seconds'), name='Bau Stufe S2', log='Versuch 3 von 6\n', pid=kind.pid)

        def run(page, root):
            app = self.live_tab(page)
            stopp = app.get_by_role('button', name='Fabrik anhalten (Notaus)')
            app.locator('.t-wf-fabrik-lauf.aktiv').wait_for(timeout=20000)
            self.assertTrue(stopp.is_visible())
            self.assertIsNone(fabrik.angehalten(root))
            stopp.click()
            app.locator('.t-wf-notaus-aus').wait_for(timeout=40000)
            self.assertIn('FABRIK ANGEHALTEN', app.locator('.t-wf-notaus-aus').inner_text())
            self.assertIn('1 Lauf gestoppt', app.locator('.t-wf-notaus-meldung').inner_text())
            self.assertFalse(stopp.is_visible(), 'der rote Knopf weicht dem Zustand')
            self.assertIsNotNone(fabrik.angehalten(root), 'die Haltemarke liegt im Projekt')
            self.assertTrue(kind.poll() is not None)
            app.locator('.t-wf-live-halt').wait_for(timeout=15000)
            page.wait_for_function("()=>!document.querySelector('.t-wf-fabrik-lauf.aktiv')", timeout=15000)
            # Freigeben verlangt eine Rückfrage; Abbrechen lässt die Fabrik angehalten
            app.get_by_role('button', name='Fabrik freigeben …').click()
            self.assertIn('Wirklich freigeben?', app.locator('.t-wf-notaus-rueckfrage').inner_text())
            app.get_by_role('button', name='Abbrechen', exact=True).last.click()
            self.assertIsNotNone(fabrik.angehalten(root))
            app.get_by_role('button', name='Fabrik freigeben …').click()
            app.get_by_role('button', name='Ja, freigeben').click()
            stopp.wait_for(state='visible', timeout=20000)
            self.assertIsNone(fabrik.angehalten(root))
            self.assertIn('wieder freigegeben', app.locator('.t-wf-notaus-meldung').inner_text())
            page.wait_for_function("()=>document.querySelector('.t-wf-live-halt').hidden", timeout=15000)
        self.session(run, mit_hub=hub_vorbereiten)

    def test_der_knopf_ist_in_jedem_reiter_und_im_szenario_studio_da(self):
        def run(page, root):
            app = self.live_tab(page)
            stopp = app.get_by_role('button', name='Fabrik anhalten (Notaus)')
            for reiter in ('Übersicht', 'Vorlagen', 'Editor', 'Versionen', 'Ausführungen', 'Live'):
                app.get_by_role('tab', name=reiter).click()
                self.assertTrue(stopp.is_visible(), 'im Reiter ' + reiter)
            page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open',{type:'scenario',id:'alle',title:'Szenario Studio'})")
            sz = page.locator('.t-scenario').first
            sz.locator('.t-wf-svg').wait_for()
            self.assertTrue(sz.get_by_role('button', name='Fabrik anhalten (Notaus)').is_visible())
        self.session(run)

    def test_eine_schon_angehaltene_fabrik_zeigt_es_gleich_beim_oeffnen(self):
        from sedra_runtime.workflows import fabrik

        def hub_vorbereiten(hub):
            fabrik.anhalten(hub.project_root, 'Vorher angehalten')

        def run(page, root):
            app = self.live_tab(page)
            app.locator('.t-wf-notaus-aus').wait_for(timeout=20000)
            self.assertIn('Vorher angehalten', app.locator('.t-wf-notaus-aus').inner_text())
            self.assertFalse(app.get_by_role('button', name='Fabrik anhalten (Notaus)').is_visible())
        self.session(run, mit_hub=hub_vorbereiten)


if __name__ == '__main__':
    unittest.main()
