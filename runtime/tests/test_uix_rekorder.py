"""Der Rekorder (Kern Sprache, 19.10.2026) im Browser: in der Shell „Fisch“ (Modus Aufnahme) nimmt Chromium mit einem Fake-Mikrofon
auf, die Stücke kommen am Kern an, die Aufnahme liegt im Projekt; ohne Provider sagt das Werkzeug das und die Abschrift von Hand
wird ein Transkript, das „Transkript öffnen“ im Modus Transkript zeigt – samt „Erkenntnisse mit SEDRA“ aus einem Fake-Modell.
Dazu: der Rekorder ist ein Ort für jede Shell (places.js, Cockpit-Baum, Paperclip-Navigation), und ui/sprache.js ist reines Vertragscode."""
import re
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'


class Files(unittest.TestCase):
    def test_the_recorder_is_a_place_of_every_shell_and_the_helper_is_contract_code(self):
        self.assertIn("type: 'aufnahme', id: 'rekorder'", (UIX / 'ui' / 'places.js').read_text(encoding='utf-8'))
        self.assertIn("type: 'aufnahme'", (UIX / 'shells' / 'cockpit' / 'tree.js').read_text(encoding='utf-8'))
        self.assertIn("type: 'aufnahme'", (UIX / 'shells' / 'paperclip' / 'nav.js').read_text(encoding='utf-8'))
        self.assertIn("type: 'aufnahme'", (UIX / 'shells' / 'fisch' / 'shell.js').read_text(encoding='utf-8'))
        self.assertIn('/uix/ui/sprache.js', (UIX / 'desk.html').read_text(encoding='utf-8'))
        helper = (UIX / 'ui' / 'sprache.js').read_text(encoding='utf-8')
        self.assertNotIn('fetch(', helper, 'die Stücke gehen über die api() des Werkzeugs, nie direkt')
        tool = (UIX / 'tools' / 'rekorder' / 'tool.js').read_text(encoding='utf-8')
        self.assertNotIn('getUserMedia', tool, 'das Mikrofon öffnet nur der Kern-Helfer')
        for f in ('tool.js', 'tool.css'):
            self.assertLess(len((UIX / 'tools' / 'rekorder' / f).read_text(encoding='utf-8').splitlines()), 400)
        css = (UIX / 'tools' / 'rekorder' / 'tool.css').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r':\s*#[0-9a-fA-F]{3,8}', css), [], 'Farben nur über Tokens')
        self.assertNotIn('@keyframes', css)


class InTheBrowser(unittest.TestCase):
    def test_record_with_a_fake_microphone_then_hand_transcript_and_insights(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest('playwright fehlt')
        import uix_check
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='fisch')
        try:
            hub = uix_check.LAST_HUB
            hub.sprache.which = lambda n: None           # kein Provider – der Weg ist die Abschrift von Hand
            class FakeServer:
                def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]
            def execute(mission, request):
                return {'status': 'completed', 'model_result': {'content': 'ZUSAMMENFASSUNG:\nDie Lieferung ist für Montag vereinbart.\nENTSCHEIDUNGEN:\n- Lieferung Montag\nOFFENE FRAGEN:\n- Uhrzeit\nAUFGABEN:\n- Kunden anrufen und Uhrzeit klären', 'finish_reason': 'stop'}}
            hub.runtime.llama_server = FakeServer(); hub.runtime.control.execute = execute
            with sync_playwright() as pw:
                b = pw.chromium.launch(args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
                ctx = b.new_context(viewport={'width': 1400, 'height': 900}, permissions=['microphone'])
                page = ctx.new_page()
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url); wait_until_started(page); page.wait_for_timeout(1000)
                page.click('.fi-modus-btn[data-modus="aufnahme"]')
                page.wait_for_selector('.fi-blase [data-tool="rekorder"] .t-rk-knopf', timeout=15000)
                self.assertIn('kein Provider', page.text_content('.t-rk-provider'))
                self.assertIn('pip install whisperx', page.text_content('.t-rk-install'))
                # der Satz aus der Wolke wird der Titel
                page.fill('.fi-wolke textarea', 'Kundengespräch Montag'); page.keyboard.press('Enter'); page.wait_for_timeout(200)
                self.assertEqual(page.input_value('.t-rk-zeile input'), 'Kundengespräch Montag')
                # aufnehmen mit dem Fake-Mikrofon: die Stücke kommen an
                page.click('.t-rk-knopf'); page.wait_for_selector('.t-rk-pult.laeuft', timeout=10000)
                page.wait_for_timeout(5200)
                self.assertNotEqual(page.text_content('.t-rk-uhr'), '00:00')
                page.click('.t-rk-verbs button:has-text("Pause")'); page.wait_for_timeout(300)
                self.assertTrue(page.query_selector('.t-rk-pult.pause'))
                page.click('.t-rk-verbs button:has-text("Weiter")'); page.wait_for_timeout(300)
                page.click('.t-rk-knopf')                      # Stopp
                page.wait_for_selector('.t-rk-karte', timeout=15000)
                self.assertIn('Gesichert', page.text_content('.t-rk-meldung'))
                rec = hub.sprache.aufnahmen()['aufnahmen']
                self.assertEqual(len(rec), 1); self.assertEqual(rec[0]['titel'], 'Kundengespräch Montag')
                self.assertGreater(rec[0]['groesse'], 0); self.assertGreater(rec[0]['dauer'], 4)
                self.assertTrue((Path(hub.project_root) / 'sprache' / 'aufnahmen' / (rec[0]['id'] + '.webm')).is_file())
                # ohne Provider: kein Knopf, der so tut; die Abschrift von Hand wird ein Transkript
                self.assertFalse(page.query_selector('.t-rk-karte button:has-text("Sprache → Text")'))
                page.click('.t-rk-karte button:has-text("Abspielen")'); page.wait_for_selector('.t-rk-audio audio', timeout=10000)
                page.fill('.t-rk-abschrift textarea', 'Guten Morgen. Die Lieferung kommt am Montag, die Uhrzeit ist offen.')
                page.click('.t-rk-abschrift button'); page.wait_for_selector('.t-rk-karte button:has-text("Transkript öffnen")', timeout=15000)
                self.assertIn('Transkript da', page.text_content('.t-rk-karte .t-rk-pill'))
                page.click('.t-rk-karte button:has-text("Transkript öffnen")')
                page.wait_for_selector('.t-tk-kopf', timeout=15000)
                self.assertTrue(page.query_selector('.fi-modus-btn.on[data-modus="transkript"]'), 'der Modus folgt dem Objekt')
                self.assertIn('manuell', page.text_content('.t-tk-kopf'))
                self.assertIn('sprache/aufnahmen', page.text_content('.t-tk-kopf'))
                # SEDRA-KI-Zugang: Erkenntnisse aus dem Fake-Modell, an die Fassung gebunden, Aufgabe → Auftrag
                page.click('.t-tk-erk-kopf button:has-text("Fassung lesen")')
                page.wait_for_selector('.t-tk-erk-text', timeout=15000)
                self.assertIn('Montag', page.text_content('.t-tk-erk-text'))
                self.assertIn('Uhrzeit', page.text_content('.t-tk-erk'))
                self.assertTrue(page.query_selector('.t-tk-erk-row button:has-text("Als Auftrag anlegen")'))
                self.assertEqual(errors, [])
                b.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
