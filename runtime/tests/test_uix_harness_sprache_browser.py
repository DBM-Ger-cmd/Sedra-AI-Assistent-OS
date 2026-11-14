"""X5 Browser-Test: Sprachumschalter in der Harness-Shell (Einstellungen).
Echtes One Sedra UI auf temporärem Projekt; kein GPU oder externer Engine.
Wird nur mit SEDRA_BROWSER=1 ausgeführt.
"""
import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Set SEDRA_BROWSER=1 for headless UI acceptance')
class SpracheBrowserTest(unittest.TestCase):
    def test_sprache_umschalter_in_einstellungen(self):
        """Einstellungen über echte Klicks öffnen, auf English umschalten, Kopf erscheint englisch, zurück auf Deutsch."""
        from playwright.sync_api import sync_playwright
        from uix_check import start_server
        url, stop = start_server(lambda *a: None, shell='harness')
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1400, 'height': 950})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url)
                page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
                # Beide String-Listen sind geladen und haben identische Schlüssel (X5-01, X5-04)
                keys = page.evaluate('''()=>{
                  const S = window.sedraI18nStrings || {};
                  return {de: Object.keys(S.de || {}).sort(), en: Object.keys(S.en || {}).sort()};
                }''')
                self.assertEqual(keys['de'], keys['en'], 'DE und EN müssen identische Schlüssel haben')
                self.assertGreater(len(keys['de']), 0, 'mindestens ein String muss vorhanden sein')
                # t() liefert deutschen Standardwert
                de = page.evaluate('''()=>window.sedraI18n ? window.sedraI18n.t('lbl_sedra') : null''')
                self.assertEqual(de, 'SEDRA')
                # Einstellungen-Ansicht erstellen und an DOM hängen
                page.evaluate('''()=>{
                  const S = window.sedraBoot.ctx;
                  const T = window.sedraHarness.einstellungen;
                  const a = T.ansicht(S, 'einstellungen:start');
                  const host = document.getElementById('sedra-root');
                  if(a.box && !host.querySelector('.hs-einst')) {
                    host.appendChild(a.box);
                  }
                }''')
                page.wait_for_function('()=>document.querySelector(".hs-einst-kopf-name")')
                # Kopf steht auf Deutsch
                kopf = page.evaluate('''()=>document.querySelector(".hs-einst-kopf-name").textContent''')
                self.assertEqual(kopf, 'Einstellungen', 'Kopf auf Deutsch: ' + kopf)
                # Auf Allgemein in der Navigation klicken
                page.click('.hs-einst-punkt[data-gruppe="allgemein"]')
                page.wait_for_function('()=>document.querySelector(".hs-einst-reihen .hs-einst-reihe")')
                # Auf „Sprache der Oberfläche“ klicken (echter Klick über DOM)
                page.evaluate('''()=>{
                    const r = Array.from(document.querySelectorAll('.hs-einst-reihe')).find(x=>x.textContent && x.textContent.includes('Sprache der Oberfläche'));
                    if(r) r.click();
                }''')
                page.wait_for_function('()=>document.querySelector(".hs-start-seg-btn")')
                # Auf „Englisch“ klicken (echter Klick über DOM)
                page.evaluate('''()=>{
                    const b = Array.from(document.querySelectorAll('.hs-start-seg-btn')).find(x=>x.textContent === 'Englisch');
                    if(b) b.click();
                }''')
                page.wait_for_function('()=>document.querySelector(".hs-einst-kopf-name").textContent === "Settings"')
                kopf_en = page.evaluate('''()=>document.querySelector(".hs-einst-kopf-name").textContent''')
                self.assertEqual(kopf_en, 'Settings', 'Kopf auf Englisch: ' + kopf_en)
                # Navigation enthält nicht mehr „Startseite“ (sondern englisch)
                nav = page.evaluate('''()=>document.querySelector(".hs-einst-nav").textContent''')
                self.assertNotIn('Startseite', nav, 'Navigation sollte nicht mehr deutsch sein: ' + nav)
                # Zurück auf Deutsch klicken
                page.click('text=German')
                page.wait_for_function('()=>document.querySelector(".hs-einst-kopf-name").textContent === "Einstellungen"')
                kopf_de = page.evaluate('''()=>document.querySelector(".hs-einst-kopf-name").textContent''')
                self.assertEqual(kopf_de, 'Einstellungen', 'Zurück auf Deutsch: ' + kopf_de)
                self.assertEqual(errors, [])
                browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
