"""Die Shell „Fisch“ (19.10.2026) im Browser: Glas, Fisch, Wolke, drei Modi; der Satz aus der Wolke geht in den Modus – ein
Fake-Modell übersetzt, ein importiertes Transkript wird aus der Wolke durchsucht; das Gespräch ist eine Schublade. Dazu die reinen
Teile (Modus je Objekttyp) und die Vertragsregel: kein Hex in der Shell."""
import json
import re
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
SHELL = UIX / 'shells' / 'fisch'
SRT = "1\n00:00:01,000 --> 00:00:03,500\nGuten Morgen, Frau Musterfrau.\n\n2\n00:00:04,000 --> 00:00:06,000\nDie Lieferung kommt am Montag.\n"


class Files(unittest.TestCase):
    def test_no_hex_in_the_shell_and_every_mode_has_a_tool(self):
        css = (SHELL / 'shell.css').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r':\s*#[0-9a-fA-F]{3,8}', css), [], 'Farben nur über Tokens')
        js = (SHELL / 'shell.js').read_text(encoding='utf-8')
        for t in ('uebersetzung', 'nachrichten', 'transkript'):
            self.assertIn(f"type: '{t}'", js)
            manifests = [p for p in (UIX / 'tools').glob('*/tool.yaml') if f'[{t}]' in p.read_text(encoding='utf-8')]
            self.assertEqual(len(manifests), 1, f'genau ein Werkzeug zeichnet {t}')


class InTheBrowser(unittest.TestCase):
    def test_cloud_modes_translation_and_transcript_search(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest('playwright fehlt')
        import uix_check
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='fisch')
        try:
            hub = uix_check.LAST_HUB
            class FakeServer:
                def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]
            seen = []
            def execute(mission, request):
                seen.append(request)
                return {'status': 'completed', 'model_result': {'content': 'ÜBERSETZUNG:\nWir liefern am Montag; die Uhrzeit stimmen wir noch ab.\nUNSICHERHEITEN:\n- Uhrzeit fehlt\nHINWEISE:\n- keine', 'finish_reason': 'stop'}}
            hub.runtime.llama_server = FakeServer(); hub.runtime.control.execute = execute
            with sync_playwright() as pw:
                b = pw.chromium.launch(); page = b.new_page(viewport={'width': 1400, 'height': 860})
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url); wait_until_started(page); page.wait_for_timeout(1200)
                for sel in ('.fi-glas', '.fi-fisch', '.fi-wolke textarea', '.fi-modus-btn[data-modus="news"]'):
                    self.assertTrue(page.query_selector(sel), sel)
                # Übersetzen: der Satz aus der Wolke geht ins Werkzeug und läuft sofort
                page.wait_for_selector('.fi-blase [data-tool="uebersetzer"]', timeout=15000)
                page.fill('.fi-wolke textarea', 'Das Zeug kommt Montag, wann genau weiß ich nicht'); page.keyboard.press('Enter')
                page.wait_for_selector('.t-ue-ergebnis', timeout=20000)
                self.assertIn('Wir liefern am Montag', page.text_content('.t-ue-text'))
                self.assertIn('Uhrzeit fehlt', page.text_content('.t-ue-liste.warn'))
                self.assertIn('Zielrolle', seen[0]['messages'][0]['content'])
                self.assertIn(page.get_attribute('.fi-fisch', 'data-zustand'), ('thinking', 'answering'))
                # Transkript: importieren, dann aus der Wolke suchen
                page.click('.fi-modus-btn[data-modus="transkript"]')
                page.wait_for_selector('.t-tk-import', timeout=15000)
                page.fill('.t-tk-import input', 'Kundengespräch'); page.fill('.t-tk-import textarea', SRT)
                page.click('.t-tk-import button:has-text("Importieren")')
                page.wait_for_selector('.t-tk-cue', timeout=15000)
                self.assertEqual(page.locator('.t-tk-cue').count(), 2)
                page.fill('.fi-wolke textarea', 'Montag'); page.keyboard.press('Enter')
                page.wait_for_selector('.t-tk-cue.hit', timeout=15000)
                self.assertEqual(page.locator('.t-tk-cue.hit').count(), 1)
                # der Record: pseudonymisieren, prüfen, freigeben
                page.on('dialog', lambda d: d.accept())
                page.click('.t-tk-verbs button:has-text("Pseudonymisieren")'); page.wait_for_timeout(1200)
                self.assertNotIn('Musterfrau', page.text_content('.t-tk-cues'))
                page.click('.t-tk-verbs button:has-text("Als geprüft markieren")'); page.wait_for_timeout(1000)
                page.click('.t-tk-verbs button:has-text("Freigeben")'); page.wait_for_timeout(1200)
                self.assertIn('Golden Record', page.text_content('.t-tk-kopf'))
                # der Modus übersteht ein Neuladen (Layout der Shell)
                page.reload(); wait_until_started(page); page.wait_for_timeout(1200)
                self.assertTrue(page.query_selector('.fi-modus-btn.on[data-modus="transkript"]'), 'der Modus bleibt gemerkt')
                # das Gespräch ist eine Schublade
                page.click('.fi-fab'); page.wait_for_timeout(400)
                self.assertFalse(page.evaluate("()=>document.querySelector('.fi-drawer').hidden"))
                self.assertTrue(page.query_selector('.fi-drawer [data-tool="talk"]'))
                self.assertEqual(errors, [])
                b.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
