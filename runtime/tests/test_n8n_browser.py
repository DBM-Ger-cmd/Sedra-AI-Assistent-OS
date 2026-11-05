"""Real One Sedra UI on a temporary project; no GPU or external engine."""
import json
import os
from pathlib import Path
import sys
import unittest
from workflow_fixture import sample

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1 for headless UI acceptance')
class WorkflowBrowser(unittest.TestCase):
    def menu(self, app, name):
        app.locator('.t-wf-menu > summary').click()
        app.get_by_role('button', name=name, exact=True).click()

    def test_editor_import_edit_export_and_versions(self):
        from playwright.sync_api import sync_playwright
        from uix_check import start_server
        url, stop = start_server(lambda *a: None, shell='harness')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1400, 'height': 950}, accept_downloads=True)
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url)
                page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
                page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'workflow',id:'alle',title:'Workflows'})")
                page.wait_for_selector('.t-workflow .t-wf-svg')
                app = page.locator('.t-workflow').first
                page.wait_for_function("()=>{const e=document.querySelector('.t-workflow');return e && !e.inert;}")
                self.assertEqual(app.locator('.t-wf-node').count(), 5)
                # Reiter, Themenschalter und Übersicht gehören zur Oberfläche.
                self.assertEqual([t.inner_text() for t in app.get_by_role('tab').all()], ['Übersicht', 'Vorlagen', 'Editor', 'Versionen', 'Ausführungen'])
                theme = app.get_by_role('button', name='Farbthema wechseln', exact=False)
                before = app.get_attribute('data-wf-theme');theme.click()
                self.assertNotEqual(before, app.get_attribute('data-wf-theme'))
                # Actual node editing and graph mutations, including undo.
                app.get_by_role('button', name='Eigenschaften', exact=True).click()
                app.get_by_label('Knoten auswählen', exact=True).select_option(label='Felder setzen')
                app.get_by_label('Knotenname', exact=True).fill('Daten vorbereiten')
                app.get_by_role('button', name='Parameter übernehmen').click()
                self.assertTrue(app.locator('.t-wf-node').filter(has_text='Daten vorbereiten').count())
                app.get_by_role('button', name='Zurück', exact=True).click()
                self.assertTrue(app.locator('.t-wf-node').filter(has_text='Felder setzen').count())
                app.get_by_role('button', name='Knoten hinzufügen', exact=True).click()
                app.get_by_label('Knoten suchen').fill('no operation')
                app.get_by_label('Knoten suchen').press('Enter')
                self.assertEqual(app.locator('.t-wf-node').count(), 6)
                app.get_by_role('button', name='Zurück', exact=True).click()
                self.assertEqual(app.locator('.t-wf-node').count(), 5)
                app.get_by_role('button', name='Speichern', exact=True).click()
                app.get_by_role('status').filter(has_text='Revision 1 gespeichert.').wait_for()
                app.get_by_label('Workflow-Titel').fill('Browser acceptance')
                app.get_by_label('Workflow-Titel').press('Tab')
                app.get_by_role('button', name='Speichern', exact=True).click()
                app.get_by_role('status').filter(has_text='Revision 2 gespeichert.').wait_for()
                app.get_by_label('Frühere Revision', exact=True).select_option('1')
                app.get_by_role('button', name='Revision als Entwurf laden').click()
                page.wait_for_function("()=>document.querySelector('.t-workflow input[aria-label=\"Workflow-Titel\"]').value.includes('Erster')")
                app.get_by_role('button', name='Speichern', exact=True).click()
                app.get_by_role('status').filter(has_text='Revision 3 gespeichert.').wait_for()
                doc = sample();doc['future'] = {'preserve': True};doc['nodes'][1]['type'] = 'community.future'
                app.locator('input[type=file]').set_input_files({'name': 'future.json', 'mimeType': 'application/json', 'buffer': json.dumps(doc).encode()})
                app.get_by_role('status').filter(has_text='Importiert.').wait_for()
                self.assertEqual(app.locator('.unsupported').count(), 1)
                with page.expect_download() as download:
                    self.menu(app, 'Exportieren')
                exported = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
                self.assertEqual(exported, doc)
                self.menu(app, 'Prüfen')
                page.wait_for_function("()=>document.querySelector('.t-wf-report').textContent.includes('unsupported_node')")
                for width in (1400, 1024):
                    page.set_viewport_size({'width': width, 'height': 950})
                    self.assertTrue(app.locator('.t-wf-svg').is_visible())
                # A fresh example is the useful review screenshot.
                self.menu(app, 'Beispiel')
                output = os.environ.get('SEDRA_N8N_SCREENSHOT')
                if output:
                    page.set_viewport_size({'width': 1440, 'height': 1100})
                    app.screenshot(path=output)
                self.assertEqual(errors, [])
                browser.close()
        finally:
            stop()
            import host_isolation
            host_isolation.tearDownModule()
