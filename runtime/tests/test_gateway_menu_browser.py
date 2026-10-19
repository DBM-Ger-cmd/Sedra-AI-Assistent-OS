"""KI GateWay im Cockpit: das Menü steht links im Baum, jede Ansicht hat eine Funktion, kein zweites Menü und kein Panel rechts."""
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


class GatewayImBaum(unittest.TestCase):
    def test_every_entry_in_the_tree_opens_its_view_and_nothing_is_doubled(self):
        sync_playwright = browser_or_skip()
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='cockpit')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1400, 'height': 860})
                fehler = []
                page.on('pageerror', lambda e: fehler.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url); wait_until_started(page); page.wait_for_timeout(800)
                try:
                    # Der Baum links hat die Gruppe „KI GateWay“ mit sechs Einträgen
                    page.wait_for_selector('.ck-tree .tr-row:has-text("Selbst ausprobieren")', timeout=15000)
                    for name in ['Überblick', 'Vorgänge', 'Dateien', 'Regeln', 'Selbst ausprobieren', 'Verlauf']:
                        self.assertTrue(page.query_selector(f'.ck-tree .tr-row:has-text("{name}")'), f'„{name}“ steht im Baum')

                    # Kein zweites Menü im Werkzeug, kein Nachweis-Panel rechts neben dem GateWay
                    page.click('.ck-tree .tr-row:has-text("Überblick")')
                    page.wait_for_selector('.t-gateway-schutz .t-schutz-station', timeout=15000)
                    self.assertEqual(page.locator('.t-gateway-nav').count(), 0, 'das Menü steht nur links, nicht noch einmal im Werkzeug')
                    self.assertEqual(page.locator('.dk-pane-evidence').count(), 0, 'rechts kein Nachweis-Panel beim GateWay')
                    self.assertFalse(page.is_visible('.t-schutz-tabs'), 'die Reiter des Schutzes entfallen, das Menü links hat sie')

                    # Überblick: die vier Stationen mit Funktion
                    stationen = page.locator('.t-gateway-schutz .t-schutz-station strong').all_inner_texts()
                    self.assertEqual(stationen, ['Eingang prüfen', 'Entscheiden', 'KI', 'Antwort prüfen'])

                    # jeder Eintrag zeigt seine Ansicht
                    erwartet = {
                        'Vorgänge': '.t-gateway-new input',
                        'Dateien': '.t-gateway-dateien',
                        'Regeln': '.t-regelbuch-box',
                        'Selbst ausprobieren': '.t-gateway-try',
                        'Verlauf': '.t-gateway-verlauf-liste',
                    }
                    for name, selector in erwartet.items():
                        page.click(f'.ck-tree .tr-row:has-text("{name}")')
                        page.wait_for_selector(selector, timeout=15000)
                        self.assertTrue(page.query_selector(f'.ck-tree .tr-row.on:has-text("{name}")'), f'„{name}“ ist im Baum markiert')

                    # Selbst ausprobieren: die Frage an SEDRA antwortet
                    page.click('.ck-tree .tr-row:has-text("Selbst ausprobieren")')
                    page.wait_for_selector('.t-gateway-frag input', timeout=15000)
                    page.fill('.t-gateway-frag input', 'Was muss ich als Nächstes machen?'); page.press('.t-gateway-frag input', 'Enter')
                    page.wait_for_selector('.t-gateway-frag-out .s-note', timeout=15000)

                    # Übung anlegen öffnet den Vorgang; „Zur Übersicht“ führt zurück zu den Stationen
                    page.click('.t-gateway-try button:has-text("Übung anlegen")')
                    page.wait_for_selector('.t-gateway-flow', timeout=15000)
                    page.click('.t-gateway-flow button:has-text("Zur Übersicht")')
                    page.wait_for_selector('.t-gateway-schutz .t-schutz-station', timeout=15000)
                    self.assertEqual(fehler, [], 'keine Seitenfehler beim Durchklicken')
                finally:
                    browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
