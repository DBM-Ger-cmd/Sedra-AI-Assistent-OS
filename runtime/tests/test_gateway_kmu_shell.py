"""Shell „KI Gateway für KMU“ im Browser: startet, zeigt den Ablauf und die Zeichnung, trägt das Gateway in der Mitte und das
Gespräch unten, und die Farben kommen aus den Tokens (kein Hex in der Shell)."""
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
SHELL = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells' / 'gateway-kmu'


def browser_or_skip():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return sync_playwright
    except Exception:
        raise unittest.SkipTest('playwright fehlt – pip install playwright && python -m playwright install chromium')


class GatewayKmuShell(unittest.TestCase):
    def test_die_shell_zeigt_kopf_werkstueck_und_gespraech(self):
        sync_playwright = browser_or_skip()
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='gateway-kmu')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1400, 'height': 860})
                fehler = []
                page.on('pageerror', lambda e: fehler.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url); wait_until_started(page)
                try:
                    page.wait_for_selector('.sh-gateway-kmu', timeout=15000)
                    self.assertEqual(page.text_content('.sh-gateway-kmu-titel'), 'KI Gateway für KMU')
                    schritte = page.locator('.sh-gateway-kmu-schritt').all_inner_texts()
                    self.assertEqual(schritte, ['Aufgabe eingeben', 'Schutz prüfen', 'Entwurf erzeugen', 'Ergebnis prüfen', 'selbst entscheiden.'])
                    self.assertTrue(page.query_selector('.sh-gateway-kmu-grafik'), 'die eigene Zeichnung ist da')
                    # das Gateway-Werkzeug steht in der Mitte, das Gespräch unten
                    page.wait_for_selector('.sh-gateway-kmu-werkstueck [data-tool="gateway"]', timeout=15000)
                    self.assertTrue(page.query_selector('.sh-gateway-kmu-talk'), 'das Gespräch hat seine Zone unten')
                    # die Farben kommen aus den Tokens: der Titel hat die Titelfarbe der Folien
                    farbe = page.evaluate("()=>getComputedStyle(document.querySelector('.sh-gateway-kmu-titel')).color")
                    self.assertEqual(farbe, 'rgb(255, 255, 255)')
                    import tempfile
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / 'kmu_shell_test.png'))
                    self.assertEqual(fehler, [], 'keine Seitenfehler')
                finally:
                    browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
