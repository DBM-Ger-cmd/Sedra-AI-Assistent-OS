"""KI GateWay: das linke Menü im Browser. Jeder Menüpunkt und jede Kachel muss etwas Sichtbares tun; kein Knopf ohne Wirkung."""
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


class GatewayMenu(unittest.TestCase):
    def test_every_menu_item_and_tile_does_something(self):
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
                    page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'gateway', id:'alle', title:'KI GateWay', collection:true})")
                    page.wait_for_selector('.t-gateway-nav', timeout=15000)

                    # Überblick: vier Kacheln mit Status, Banner mit den Regeln
                    self.assertEqual(page.locator('.t-gateway-tile').count(), 4, 'vier Kacheln wie in der Skizze')
                    self.assertIn('Regeln greifen', page.text_content('.t-gateway-banner'))
                    self.assertTrue(page.query_selector('.t-gateway-navitem.on:has-text("Überblick")'), 'der Überblick ist aktiv')

                    # jeder Menüpunkt öffnet seine Ansicht und ist danach aktiv
                    erwartet = {
                        'Vorgänge': '.t-gateway-new input',
                        'Dateien': '.t-gateway-dateien',
                        'Regeln': '.t-regelbuch-box',
                        'Selbst ausprobieren': '.t-gateway-try',
                        'Verlauf': '.t-gateway-verlauf-liste',
                    }
                    for name, selector in erwartet.items():
                        page.click(f'.t-gateway-nav button:has-text("{name}")')
                        page.wait_for_selector(selector, timeout=15000)
                        self.assertTrue(page.query_selector(f'.t-gateway-navitem.on:has-text("{name}")'), f'{name} ist aktiv')

                    # Selbst ausprobieren: die Frage an SEDRA ist da und antwortet
                    page.click('.t-gateway-nav button:has-text("Selbst ausprobieren")')
                    page.wait_for_selector('.t-gateway-frag input', timeout=15000)
                    page.fill('.t-gateway-frag input', 'Was muss ich als Nächstes machen?'); page.press('.t-gateway-frag input', 'Enter')
                    page.wait_for_selector('.t-gateway-frag-out .s-note', timeout=15000)

                    # Übung anlegen öffnet den Vorgang; „Zur Übersicht“ führt zurück ins Menü
                    page.click('.t-gateway-try button:has-text("Übung anlegen")')
                    page.wait_for_selector('.t-gateway-flow', timeout=15000)
                    page.click('.t-gateway-flow button:has-text("Zur Übersicht")')
                    page.wait_for_selector('.t-gateway-tiles', timeout=15000)

                    # Kachel „Eingang prüfen“ führt in die Vorgänge; Filter lässt sich wieder aufheben
                    page.click('.t-gateway-tile:has-text("Eingang prüfen")')
                    page.wait_for_selector('.t-gateway-new input', timeout=15000)
                    self.assertTrue(page.query_selector('.t-gateway-navitem.on:has-text("Vorgänge")'))
                    self.assertEqual(fehler, [], 'keine Seitenfehler beim Durchklicken')
                finally:
                    browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
