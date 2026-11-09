"""Import-Einstieg auf der Startseite: Einfügen, Datei, Vorschau, Entwurf öffnen, Fehlerfall (echte Oberfläche, ohne GPU)."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))

N8N = {
    'name': 'Rechnungsprüfung Demo', 'active': False,
    'nodes': [
        {'id': 'a1', 'name': 'Formular', 'type': 'n8n-nodes-base.formTrigger', 'typeVersion': 2, 'position': [0, 0], 'parameters': {}},
        {'id': 'a2', 'name': 'Agent', 'type': '@n8n/n8n-nodes-langchain.agent', 'typeVersion': 2.2, 'position': [300, 0], 'parameters': {}},
        {'id': 'a3', 'name': 'Modell', 'type': '@n8n/n8n-nodes-langchain.lmChatAnthropic', 'typeVersion': 1.3, 'position': [300, 200], 'parameters': {}, 'credentials': {'anthropicApi': {'id': '1', 'name': 'x'}}},
        {'id': 'a4', 'name': 'Prüfung', 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': [600, 0], 'parameters': {}},
    ],
    'connections': {'Formular': {'main': [[{'node': 'Agent', 'type': 'main', 'index': 0}]]},
                    'Modell': {'ai_languageModel': [[{'node': 'Agent', 'type': 'ai_languageModel', 'index': 0}]]},
                    'Agent': {'main': [[{'node': 'Prüfung', 'type': 'main', 'index': 0}]]}},
}


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1 for headless UI acceptance')
class WorkflowImportBrowser(unittest.TestCase):
    def test_einstieg_vorschau_und_entwurf(self):
        from playwright.sync_api import sync_playwright
        from uix_check import start_server
        url, stop = start_server(lambda *a: None, shell='harness')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1400, 'height': 1000})
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url)
                page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
                page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'workflow',id:'alle',title:'Workflows'})")
                page.wait_for_function("()=>{const e=document.querySelector('.t-workflow');return e && !e.inert;}")
                app = page.locator('.t-workflow').first
                app.get_by_role('tab', name='Übersicht').click()
                self.assertTrue(app.locator('.t-wf-start').filter(has_text='n8n-Workflow importieren').count())
                # Leere Eingabe: freundlicher Satz, nichts passiert.
                app.get_by_role('button', name='Vorschau zeigen').click()
                self.assertIn('noch nichts', app.locator('.t-wf-imp-ziel').inner_text())
                # Kein Workflow: klarer Satz statt Fehlercode.
                app.get_by_label('n8n-JSON einfügen').fill('{"hinweis": "nur Daten"}')
                app.get_by_role('button', name='Vorschau zeigen').click()
                app.locator('.t-wf-imp-karte.bad').wait_for()
                self.assertIn('nicht nach einem n8n-Workflow', app.locator('.t-wf-imp-ziel').inner_text())
                # Einfügen: Vorschau mit Urteil, Bild und Liste.
                app.get_by_label('n8n-JSON einfügen').fill(json.dumps(N8N))
                app.get_by_role('button', name='Vorschau zeigen').click()
                app.locator('.t-wf-imp-karte.teilweise').wait_for()
                ziel = app.locator('.t-wf-imp-ziel')
                self.assertIn('Rechnungsprüfung Demo', ziel.inner_text())
                self.assertEqual(app.locator('.t-wf-imp-knoten').count(), 4)
                self.assertEqual(app.locator('.t-wf-imp-kante').count(), 3)
                self.assertEqual(app.locator('.t-wf-imp-knoten.unterstuetzt').count(), 1)
                self.assertIn('Zugangsdaten', ziel.inner_text())
                # Nur gelesen: noch nichts im Editor oder gespeichert.
                app.get_by_role('tab', name='Versionen').click()
                app.get_by_role('tab', name='Übersicht').click()
                # Datei wählen.
                tmp = Path(os.environ.get('TEMP', '.')) / 'sedra_import_test.json'
                tmp.write_text(json.dumps(dict(N8N, name='Aus Datei')), encoding='utf-8')
                with page.expect_file_chooser() as fc:
                    app.locator('.t-wf-imp-zone').click()
                fc.value.set_files(str(tmp))
                app.locator('.t-wf-imp-karte strong').filter(has_text='Aus Datei').wait_for()
                # Als Entwurf öffnen: Editor zeigt alle vier Knoten, Name übernommen.
                app.get_by_role('button', name='Als Entwurf öffnen').click()
                app.get_by_label('Workflow-Titel').wait_for()
                self.assertEqual(app.get_by_label('Workflow-Titel').input_value(), 'Aus Datei')
                self.assertEqual(app.locator('.t-wf-node').count(), 4)
                self.assertEqual(errors, [])
                browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
