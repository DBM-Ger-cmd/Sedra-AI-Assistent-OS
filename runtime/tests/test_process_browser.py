"""Two independent apps share process versions, not their configuration forms."""
import json
import os
from pathlib import Path
import sys
import unittest
from workflow_fixture import process_sample

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1')
class ProcessBrowser(unittest.TestCase):
    def session(self, run):
        from playwright.sync_api import sync_playwright
        from uix_check import start_server
        url, stop = start_server(lambda *a: None, shell='harness')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1500, 'height': 1050}, accept_downloads=True)
                errors = [];page.on('pageerror', lambda e: errors.append(str(e)));page.on('dialog', lambda d: d.accept())
                page.goto(url);page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
                run(page, url)
                self.assertEqual(errors, [])
                browser.close()
        finally:
            stop()
            import host_isolation
            host_isolation.tearDownModule()

    def open(self, page, kind):
        page.evaluate("kind=>window.sedraBoot.ctx.bus.emit('object.open',{type:kind,id:'alle',title:kind==='scenario'?'Szenario Studio':'n8n Workflows'})", kind)
        app = page.locator('.t-scenario' if kind == 'scenario' else '.t-n8n-workflow').first
        app.locator('.t-wf-svg').wait_for()
        page.wait_for_function("selector=>{const e=document.querySelector(selector);return e && !e.inert;}", arg='.t-scenario' if kind == 'scenario' else '.t-n8n-workflow')
        return app

    def import_doc(self, app, doc):
        app.locator('input[type=file]').set_input_files({'name': 'process.json', 'mimeType': 'application/json', 'buffer': json.dumps(doc).encode()})
        app.get_by_role('status').filter(has_text='Importiert.').wait_for()

    def save(self, app, revision, note):
        app.get_by_label('Änderungsgrund', exact=True).fill(note)
        app.get_by_role('button', name='Speichern', exact=True).click()
        app.get_by_role('status').filter(has_text=f'Revision {revision} gespeichert.').wait_for()

    def test_shared_history_and_independent_forms(self):
        def run(page, url):
            app = self.open(page, 'workflow'); self.import_doc(app, process_sample())
            self.assertEqual(app.locator('.t-wf-node').count(), 2)
            self.assertFalse(app.get_by_role('button', name='Lauf zur Freigabe vorlegen').is_visible())
            app.get_by_label('Prozessansicht').select_option('sipoc')
            self.assertIn('Anfragende Stelle', app.locator('.t-wf-table').inner_text())
            self.save(app, 1, 'Ausgangsfassung')
            app.get_by_role('button', name='Set', exact=True).dblclick()
            app.get_by_label('Zuständige Rolle', exact=True).fill('Neue Prüfrolle')
            app.get_by_role('button', name='Prozessbeschreibung übernehmen').click()
            self.save(app, 2, 'Verantwortung präzisiert')
            app.get_by_role('tab', name='Versionen').click()
            app.get_by_role('button', name='Versionen vergleichen', exact=True).click()
            page.wait_for_function("()=>document.querySelector('.t-wf-history').textContent.includes('Zuständige Rolle')")
            self.assertIn('Neue Prüfrolle', app.locator('.t-wf-history').inner_text())
            app.get_by_role('tab', name='Editor').click()
            app.get_by_role('button', name='In Szenario Studio öffnen').click()
            scenario = page.locator('.t-scenario').first;scenario.locator('.t-wf-svg.scenario').wait_for()
            page.wait_for_function("()=>{const e=document.querySelector('.t-scenario');return e && !e.inert && e.querySelector('.t-wf-toolbar input[aria-label=\"Workflow-Titel\"]').value==='Local test';}")
            self.assertEqual(scenario.locator('.t-wf-module-ring').count(), 2)
            scenario.get_by_role('button', name='Set', exact=True).dblclick()
            self.assertEqual(scenario.get_by_label('Zuständige Rolle', exact=True).input_value(), 'Neue Prüfrolle')
            self.assertEqual(scenario.get_by_label('Zielfeld', exact=True).count(), 1)
            self.assertEqual(scenario.get_by_label('Knotenparameter als JSON', exact=True).count(), 0)
            scenario.get_by_label('Wert oder Feldpfad', exact=True).fill('Revised data')
            scenario.get_by_role('button', name='Feldzuordnung übernehmen').click()
            self.save(scenario, 3, 'Feldzuordnung geändert')
            # Return to the other app; the shared latest revision must be visible.
            scenario.get_by_role('button', name='In n8n Workflows öffnen').click()
            app = page.locator('.t-n8n-workflow:visible').last
            app.locator('.t-wf-history').get_by_text('Feldzuordnung geändert', exact=True).wait_for(state='attached')
            page.reload();page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
            app = self.open(page, 'workflow')
            app.get_by_label('Gespeicherte Workflows').select_option(index=1)
            page.wait_for_function("()=>document.querySelector('.t-n8n-workflow .t-wf-hint').textContent || true")
            app.locator('.t-wf-history').get_by_text('Feldzuordnung geändert', exact=True).wait_for(state='attached')
        self.session(run)

    def test_templates_bottom_bar_and_anchored_panel(self):
        def run(page, url):
            scenario = self.open(page, 'scenario')
            # Vorlage aus der Übersicht anlegen
            scenario.get_by_role('tab', name='Szenarien').click()
            self.assertGreaterEqual(scenario.get_by_role('button', name='Vorlage verwenden').count(), 3)
            scenario.get_by_role('button', name='Vorlage verwenden').nth(1).click()
            page.wait_for_function("()=>document.querySelectorAll('.t-scenario .t-wf-node').length===3")
            self.assertIn('Einfache Weitergabe', scenario.get_by_label('Workflow-Titel').input_value())
            # Untere Leiste: Zeitplan bleibt aus, Ausführung nur zur Freigabe
            self.assertTrue(scenario.get_by_role('button', name='Einmal ausführen').is_visible())
            self.assertTrue(scenario.get_by_role('button', name='Zeitplan: aus').is_disabled())
            scenario.get_by_role('button', name='Einmal ausführen').click()
            scenario.get_by_role('status').filter(has_text='Workflow zuerst speichern.').wait_for()
            # Doppelklick öffnet das Panel am Modul (nicht fest rechts)
            scenario.get_by_role('button', name='Daten setzen', exact=True).dblclick()
            panel = scenario.locator('.t-wf-inspector')
            panel.wait_for(state='visible')
            page.wait_for_function("()=>{const p=document.querySelector('.t-scenario .t-wf-inspector');return p && p.style.left!=='';}")
            panel.get_by_role('button', name='Eigenschaften schließen').click()
            self.assertFalse(panel.is_visible())
            # Knotenauswahl mit Suche
            scenario.get_by_role('button', name='Knoten hinzufügen').click()
            scenario.get_by_label('Knoten suchen').fill('mensch')
            scenario.get_by_label('Knoten suchen').press('Enter')
            page.wait_for_function("()=>document.querySelectorAll('.t-scenario .t-wf-node').length===4")
        self.session(run)

    def test_course_symbols_and_pattern_c(self):
        def run(page, url):
            from guppi_runtime.workflows.process import PREFIX
            app = self.open(page, 'workflow')
            # Muster C aus der Vorlagengalerie: Prozessmodell mit Kandidaten-Markierung, speicherbar, nicht ausführbar
            app.get_by_role('tab', name='Übersicht').click()
            app.get_by_role('article', name='Vorlage Muster C: Auslöser, KI-Schritt, Aktion (Prozessmodell)').get_by_role('button', name='Vorlage verwenden').click()
            page.wait_for_function("()=>document.querySelectorAll('.t-n8n-workflow .t-wf-node').length===4")
            self.assertEqual(app.locator('.t-wf-candidate').count(), 1)
            self.save(app, 1, 'Muster C angelegt')
            # Symbolsatz: Raute, Parallelogramm, Zylinder, Oval
            doc = process_sample()
            kinds = ['data', 'store']
            for node, kind in zip(doc['nodes'], kinds):
                meta = json.loads(node['notes'][len(PREFIX):]); meta['kind'] = kind; node['notes'] = PREFIX + json.dumps(meta)
            app.locator('.t-wf-menu > summary').click(); app.get_by_role('button', name='Importieren', exact=True).click()
            self.import_doc(app, doc)
            page.wait_for_function("()=>document.querySelectorAll('.t-n8n-workflow polygon.t-wf-tile').length===1 && document.querySelectorAll('.t-n8n-workflow path.t-wf-tile').length===1")
        self.session(run)

    def test_external_process_in_both_apps_and_roundtrip(self):
        path = os.environ.get('SEDRA_PROCESS_FIXTURE')
        doc = json.loads(Path(path).read_text(encoding='utf-8')) if path else process_sample()
        def run(page, url):
            app = self.open(page, 'workflow')
            prior = os.environ.get('SEDRA_PROCESS_PREVIOUS_FIXTURE')
            if prior:
                self.import_doc(app, json.loads(Path(prior).read_text(encoding='utf-8')));self.save(app, 1, 'Ausgangsmodell')
                with page.expect_file_chooser() as chooser:
                    app.locator('.t-wf-menu > summary').click();app.get_by_role('button', name='Als neue Version importieren').click()
                chooser.value.set_files({'name': 'revision.json', 'mimeType': 'application/json', 'buffer': json.dumps(doc).encode()})
                app.get_by_role('status').filter(has_text='Als Entwurf zur aktuellen Version importiert.').wait_for()
                self.save(app, 2, 'Prüf- und Übergabepfade ergänzt')
            else:
                self.import_doc(app, doc);self.save(app, 1, 'Prozessmodell importiert')
            with page.expect_download() as download:
                app.locator('.t-wf-menu > summary').click();app.get_by_role('button', name='Exportieren', exact=True).click()
            self.assertEqual(json.loads(Path(download.value.path()).read_text(encoding='utf-8')), doc)
            screenshot = os.environ.get('SEDRA_PROCESS_SCREENSHOT')
            if screenshot:
                page.set_viewport_size({'width': 1600, 'height': 1550});app.screenshot(path=screenshot)
            app.get_by_role('button', name='In Szenario Studio öffnen').click()
            scenario = page.locator('.t-scenario').first;scenario.locator('.t-wf-svg.scenario').wait_for()
            page.wait_for_function("name=>{const e=document.querySelector('.t-scenario');return e && !e.inert && e.querySelector('input[aria-label=\"Workflow-Titel\"]').value===name;}", arg=doc['name'])
            self.assertFalse(scenario.locator('.t-wf-run').is_visible())
            screenshot = os.environ.get('SEDRA_SCENARIO_SCREENSHOT')
            if screenshot:scenario.screenshot(path=screenshot)
            scenario.get_by_label('Prozessansicht').select_option('details')
            self.assertGreater(scenario.locator('tbody tr').count(), 1)
        self.session(run)
