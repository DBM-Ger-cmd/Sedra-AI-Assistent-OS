"""Der Rekorder der Leiste: das Pult nimmt in dieser Seite auf – ohne Popup-Fenster. Start, Stopp und Speichern laufen über die Leiste und den Kern."""
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


def browser_or_skip():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return sync_playwright
    except Exception:
        raise unittest.SkipTest('playwright fehlt – pip install playwright && python -m playwright install chromium')


class RekorderLeiste(unittest.TestCase):
    def test_die_leiste_nimmt_in_der_seite_auf_ohne_popup_und_stoppt_sauber(self):
        sync_playwright = browser_or_skip()
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='fisch')
        import uix_check, _kern_fake
        _kern_fake.installieren(uix_check.LAST_HUB)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
                ctx = browser.new_context(permissions=['microphone'])
                p = ctx.new_page(); fehler = []
                p.on('pageerror', lambda e: fehler.append(str(e)))
                p.goto(url); wait_until_started(p); p.wait_for_timeout(1500)
                try:
                    p.click('.sx-host .sx-chip >> nth=0')
                    p.fill('.sx-rekorder-panel input', 'Testrunde')
                    p.click('.sx-rekorder-panel:not([hidden]) button:has-text("Start")')
                    p.wait_for_function("()=>document.querySelector('.sx-rek-status').textContent.includes('Nimmt auf')", timeout=15000)
                    p.wait_for_timeout(2000)
                    self.assertEqual(len(ctx.pages), 1, 'kein Popup-Fenster – die Aufnahme läuft in dieser Seite')
                    p.click('.sx-rekorder-panel:not([hidden]) button:has-text("Stopp")')
                    p.wait_for_function("()=>document.querySelector('.sx-rekorder-panel .sx-foot').textContent.includes('Gesichert')", timeout=20000)
                    self.assertEqual(fehler, [], 'keine Seitenfehler')
                finally:
                    browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
