"""Stufe C, Schritt C3/C5 im Browser: der Rahmen für ein Nicht-CORE-Werkzeug (Pilot „Rahmen-Probe“).

Geklickt wird im Rahmen selbst. Erlaubt ist nur, was das Manifest nennt; alles andere muss verweigert werden und darf nichts ändern.
Der Test startet einen echten Server mit der Cockpit-Shell (dort steht das Instrument in der Leiste)."""
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


class Rahmen(unittest.TestCase):
    def test_der_rahmen_darf_nur_was_das_manifest_nennt(self):
        sync_playwright = browser_or_skip()
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='cockpit', switches={'entwicklung': True})   # Stufe 6: Prüfwerkzeuge nur mit Schalter
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1400, 'height': 860})
                fehler = []
                page.on('pageerror', lambda e: fehler.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url); wait_until_started(page)
                try:
                    # 1. der Rahmen ist da, und sein Code steht NICHT in der Seite der Shell
                    page.wait_for_selector('iframe.sx-rahmen[title="Rahmen-Probe"]', timeout=15000)
                    seite_skripte = page.evaluate("()=>[...document.scripts].map(s=>s.src).filter(s=>s.includes('rahmen-probe'))")
                    self.assertEqual(seite_skripte, [], 'der Code des Rahmen-Werkzeugs läuft nicht in der Seite')
                    self.assertEqual(page.evaluate("()=>typeof window.sedraApi"), 'undefined', 'der Token-Zugang ist aus der Seite entfernt')
                    rahmen_el = page.query_selector('iframe.sx-rahmen[title="Rahmen-Probe"]')
                    self.assertEqual(rahmen_el.get_attribute('sandbox'), 'allow-scripts', 'Sandbox ohne allow-same-origin')
                    rahmen = None
                    for _ in range(100):
                        rahmen = next((f for f in page.frames if '/uix/frame/rahmen-probe' in f.url), None)
                        if rahmen:
                            break
                        page.wait_for_timeout(100)
                    self.assertIsNotNone(rahmen, 'der Rahmen lädt die Seite /uix/frame/rahmen-probe')
                    rahmen.wait_for_selector('button', timeout=15000)

                    def klick(name, erwartet):
                        rahmen.get_by_role('button', name=name).click()
                        # Warten in Python: die CSP der Seite verbietet Ausdrücke als Text (unsafe-eval), daher kein wait_for_function
                        for _ in range(100):
                            text = rahmen.evaluate('document.body.innerText')
                            if erwartet in text:
                                return text
                            rahmen.wait_for_timeout(100)
                        self.fail(f'„{erwartet}“ erscheint nicht im Rahmen: {text!r}')

                    text = klick('Status lesen (erlaubt)', 'erlaubt, ')
                    self.assertIn('Status lesen (erlaubt): erlaubt', text)

                    text = klick('Fremde Route (nicht im Manifest)', 'Fremde Route (nicht im Manifest): verweigert')
                    self.assertNotIn('gelungen (Fehler', text)

                    text = klick('Freigabe erteilen', 'Freigabe erteilen: verweigert')
                    self.assertNotIn('Freigabe erteilen: gelungen', text)

                    text = klick('Seite der Shell lesen', 'Seite der Shell lesen: verweigert')
                    self.assertNotIn('Seite der Shell lesen: gelungen', text)

                    text = klick('Token-Zugang suchen', 'Token-Zugang suchen: nicht vorhanden')
                    self.assertIn('Token-Zugang suchen: nicht vorhanden', text)

                    text = klick('Hinweis an die Shell (erlaubt)', 'Hinweis an die Shell (erlaubt): angekommen')
                    self.assertIn('angekommen', text)

                    # 2. die Shell hat die Hinweise nicht verloren und die Seite lief ohne Fehler
                    self.assertEqual(fehler, [], 'keine Seitenfehler')
                finally:
                    browser.close()
        finally:
            stop()

    def test_angriffe_aus_dem_rahmen_scheitern(self):
        """AM0-10 (G3 S10): ein Prüf-Modul versucht aus dem Rahmen heraus Netz, Speicher, Fenster und Seite zu erreichen. Jeder Versuch muss scheitern; die Gegenproben müssen gelingen,
        sonst wäre der Rahmen nur kaputt. Wo es eine CSP-Verletzung gibt, nennt der Rahmen die Richtlinie – so ist belegt, dass die CSP blockiert hat und nicht ein fehlendes Netz."""
        sync_playwright = browser_or_skip()
        import shutil
        from uix_check import start_server, wait_until_started
        fixture = Path(__file__).resolve().parent / 'fixtures' / 'rahmen_angriff'

        def vorbereiten(hub):
            shutil.copytree(fixture, hub.project_root / 'local_config' / 'tools' / 'rahmen-angriff')      # nicht im Paket: der Vertragstest verbietet fetch( dort

        url, stop = start_server(lambda *a: None, shell='cockpit', switches={'entwicklung': True}, prepare=vorbereiten)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1400, 'height': 860})
                fehler = []
                page.on('pageerror', lambda e: fehler.append(str(e)))
                antworten, gescheitert = [], []                           # Anfragen an die fremde Adresse: Chromium meldet auch eine von der CSP blockierte als Anfrage – wichtig ist, dass keine Antwort kam
                page.on('response', lambda r: antworten.append(r.url) if 'example.org' in r.url else None)
                page.on('requestfailed', lambda r: gescheitert.append((r.url, r.failure)) if 'example.org' in r.url else None)
                page.on('dialog', lambda d: d.accept())
                page.goto(url); wait_until_started(page)
                try:
                    page.wait_for_selector('iframe.sx-rahmen[title="Rahmen-Angriff"]', timeout=15000)
                    rahmen = None
                    for _ in range(100):
                        rahmen = next((f for f in page.frames if '/uix/frame/rahmen-angriff' in f.url), None)
                        if rahmen:
                            break
                        page.wait_for_timeout(100)
                    self.assertIsNotNone(rahmen, 'der Rahmen lädt die Seite /uix/frame/rahmen-angriff')
                    rahmen.wait_for_selector('button', timeout=15000)

                    def versuch(name, erwartet):
                        rahmen.get_by_role('button', name=name, exact=True).click()
                        text = ''
                        for _ in range(120):
                            text = rahmen.evaluate('document.body.innerText')
                            zeilen = [z for z in text.splitlines() if z.startswith(name + ':')]
                            if zeilen:
                                self.assertIn(erwartet, zeilen[-1], zeilen[-1])
                                self.assertNotIn('GELUNGEN', zeilen[-1], zeilen[-1])
                                return zeilen[-1]
                            rahmen.wait_for_timeout(100)
                        self.fail(f'„{name}“ ergibt keine Zeile im Rahmen: {text!r}')

                    # Gegenproben: was erlaubt ist, geht
                    self.assertIn('erlaubt', versuch('Gegenprobe Status lesen', 'erlaubt, '))
                    self.assertIn('erlaubt', versuch('Gegenprobe Bild aus data', 'erlaubt, Bild geladen'))
                    # Netz: die CSP des Rahmens (connect-src, img-src) blockiert, nicht ein fehlendes Netz
                    versuch('fetch eigene Adresse', 'connect-src')
                    versuch('fetch Manifest', 'connect-src')
                    versuch('fetch fremde Adresse', 'connect-src')
                    versuch('Bild von fremder Adresse', 'img-src')
                    versuch('WebSocket zur eigenen Adresse', 'blockiert')
                    # Fenster und Seite: die Sandbox (ohne allow-popups, allow-top-navigation, allow-same-origin, allow-forms)
                    versuch('Fenster öffnen', 'blockiert – kein Fenster')
                    versuch('Seite der Shell wechseln', 'blockiert')
                    versuch('Seite der Shell lesen', 'blockiert')
                    versuch('Speicher der Seite lesen', 'blockiert')
                    versuch('Formular absenden', 'blockiert – Seite blieb stehen')

                    self.assertEqual(antworten, [], 'von einer fremden Adresse kam nie eine Antwort')
                    for adresse, grund in gescheitert:
                        self.assertIn('csp', str(grund).lower(), (adresse, grund))                 # jede Anfrage dorthin endete an der CSP, nicht am fehlenden Netz
                    self.assertEqual(page.evaluate('() => location.hostname'), '127.0.0.1', 'die Seite der Shell wurde nicht weggeleitet')
                    self.assertEqual(len(page.context.pages), 1, 'es wurde kein zweites Fenster geöffnet')
                    self.assertEqual(fehler, [], 'keine Seitenfehler')
                finally:
                    browser.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
