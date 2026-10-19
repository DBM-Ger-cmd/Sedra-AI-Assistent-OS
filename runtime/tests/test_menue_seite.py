"""Die Seite des Menüs (links oder rechts) im Cockpit: unter dem Baum und im Umschalter, gespeichert pro Browser."""
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


class MenueSeite(unittest.TestCase):
    def test_das_menue_wechselt_die_seite_und_bleibt_nach_dem_neuladen(self):
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
                page.goto(url); wait_until_started(page)
                try:
                    page.wait_for_selector('.ck-tree .tr-menuwahl', timeout=15000)
                    self.assertEqual(page.evaluate("()=>document.documentElement.dataset.menu || 'links'"), 'links')
                    links = page.evaluate("()=>document.querySelector('.ck-tree').getBoundingClientRect().left")
                    # unter dem Baum: auf „Rechts“ klicken
                    page.click('.ck-tree .tr-menuwahl button:has-text("Rechts")')
                    page.wait_for_timeout(300)
                    self.assertEqual(page.evaluate("()=>document.documentElement.dataset.menu"), 'rechts')
                    rechts = page.evaluate("()=>document.querySelector('.ck-tree').getBoundingClientRect().left")
                    self.assertGreater(rechts, links, 'der Baum liegt nach dem Wechsel rechts der Arbeitsfläche')
                    # nach dem Neuladen bleibt die Wahl
                    page.reload(); wait_until_started(page)
                    page.wait_for_selector('.ck-tree .tr-menuwahl', timeout=15000)
                    self.assertEqual(page.evaluate("()=>document.documentElement.dataset.menu"), 'rechts', 'die Wahl bleibt nach dem Neuladen')
                    # im Umschalter unten rechts zurück auf „Links“
                    page.click('.sx-chip'); page.wait_for_selector('.sx-panel:not([hidden])', timeout=5000)
                    page.click('.sx-panel .sx-seg-btn:has-text("Links")')
                    page.wait_for_timeout(300)
                    self.assertEqual(page.evaluate("()=>document.documentElement.dataset.menu"), 'links', 'der Umschalter setzt dieselbe Einstellung')
                    self.assertEqual(fehler, [], 'keine Seitenfehler')
                finally:
                    browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
