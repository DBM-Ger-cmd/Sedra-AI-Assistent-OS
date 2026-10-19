"""Die Start-Shell – der Einstieg – und die allgemeine Abnahme für jede Shell, die niemand im Prüfwerkzeug kennt.

Zwei Zusagen: ohne Wahl lädt der Einstieg, und eine eigene Shell aus der Vorlage bekommt eine ehrliche Abnahme –
`result ok` für das, was die Vertragsmarken hergeben, und „nicht geprüft“ für den Rest, statt gar nichts."""
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


class Manifest(unittest.TestCase):
    def test_start_opens_no_objects_and_says_so(self):
        doc = yaml.safe_load((UIX / 'shells' / 'start' / 'shell.yaml').read_text(encoding='utf-8'))['shell']
        self.assertIn('chooser', doc['provides'])
        self.assertFalse(any(p in doc['provides'] for p in ('dock', 'windows')), 'der Einstieg zeigt die Auswahl, keine Objekte')
        for route in ('GET /api/uix/modules', 'POST /api/uix/shell', 'POST /api/uix/scaffold', 'POST /api/uix/install'):
            self.assertIn(route, doc['api'])

    def test_without_a_choice_the_entry_loads_and_a_choice_sticks(self):
        from guppi_runtime.uix_server import UIXHub
        with tempfile.TemporaryDirectory(prefix='start-') as tmp:
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                self.assertEqual(hub.gateway.manifest()['shell']['id'], 'start')
                hub.shell_set({'shell': 'cockpit'})
                self.assertEqual(hub.gateway.manifest()['shell']['id'], 'cockpit', 'einmal gewählt, startet SEDRA direkt dort')
                self.assertNotIn('start', hub.gateway.registry.config()['disabled'])
            finally:
                hub.close()


class DirectStart(unittest.TestCase):
    """START_SEDRA <id>: die Shell nur für diesen Start; eine ausdrückliche Wahl hebt das auf; eine unbekannte ist ein Satz."""

    def test_the_override_holds_until_the_captain_chooses(self):
        from guppi_runtime.uix_server import UIXHub, choose_start_shell
        with tempfile.TemporaryDirectory(prefix='start-') as tmp:
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                hub.shell_set({'shell': 'cockpit'})
                self.assertEqual(choose_start_shell(hub, 'start'), 'start')
                self.assertEqual(hub.gateway.manifest()['shell']['id'], 'start', '--uebersicht: die Übersicht, obwohl cockpit gewählt ist')
                self.assertEqual(hub.gateway.registry.config()['shell'], 'start')
                hub.shell_set({'shell': 'minimal'})
                self.assertEqual(hub.gateway.manifest()['shell']['id'], 'minimal', 'die Wahl im Einstieg schlägt den Start-Override')
                self.assertIsNone(choose_start_shell(hub, None))
                with self.assertRaises(ValueError) as ctx:
                    choose_start_shell(hub, 'gibt-es-nicht')
                self.assertIn('Vorhanden: cockpit, gateway-studio, guppi-xp, minimal, paperclip, start', str(ctx.exception))
                self.assertEqual(hub.gateway.manifest()['shell']['id'], 'minimal', 'ein Fehler ändert nichts')
            finally:
                hub.close()

    def test_guppi_xp_is_a_choice_that_leads_to_the_archive(self):
        man = yaml.safe_load((UIX / 'shells' / 'guppi-xp' / 'shell.yaml').read_text(encoding='utf-8'))['shell']
        self.assertEqual(man['trust'], 'CORE')
        self.assertEqual(man['api'], [], 'der alte Desktop ruft mit seinem eigenen Token, nicht über den Vertrag')
        js = (UIX / 'shells' / 'guppi-xp' / 'shell.js').read_text(encoding='utf-8')
        self.assertIn("location.replace('/retro' + location.hash)", js)
        self.assertTrue((UIX / 'shells' / 'guppi-xp' / 'preview.png').is_file(), 'die Karte im Einstieg hat ein Bild')


def browser_or_skip():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception:
        raise unittest.SkipTest('playwright fehlt')


class InTheBrowser(unittest.TestCase):
    def test_choosing_and_creating_from_the_entry(self):
        sync_playwright = browser_or_skip()
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='start')
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch(); page = b.new_page(viewport={'width': 1400, 'height': 860})
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url); wait_until_started(page); page.wait_for_timeout(1200)
                names = page.evaluate("()=>[...document.querySelectorAll('.st-card h2')].map(h=>h.textContent)")
                self.assertEqual(sorted(names), ['Cockpit', 'GUPPI XP', 'KI GateWay Studio', 'Minimal', 'Paperclip'], 'die Auswahl selbst steht nicht zur Wahl; der alte Desktop schon')
                page.fill('.st-make-row input[aria-label="Name der neuen Oberfläche"]', 'meine-bruecke')
                page.click('.st-make-row button:has-text("Anlegen")'); page.wait_for_timeout(1200)
                names = page.evaluate("()=>[...document.querySelectorAll('.st-card h2')].map(h=>h.textContent)")
                self.assertIn('meine-bruecke', names, 'die eigene Oberfläche erscheint als Karte')
                page.click('.st-card:has(h2:has-text("Cockpit")) button'); page.wait_for_timeout(2500); wait_until_started(page); page.wait_for_timeout(1000)
                self.assertEqual(page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.id"), 'cockpit', 'gewählt, neu geladen, da')
                self.assertEqual(errors, [])
                b.close()
        finally:
            stop()

    def test_an_own_shell_from_the_template_gets_an_honest_acceptance(self):
        """Punkt 4: eine Shell ohne Profil – geprüft wird, was die Vertragsmarken hergeben; der Rest heißt „nicht geprüft“."""
        browser_or_skip()
        from uix_check import start_server, run_checks
        url, stop = start_server(lambda *a: None, shell='start')
        try:
            # die eigene Shell entsteht wie beim Captain: aus der Vorlage, dann gewählt
            import uix_check
            hub = uix_check.LAST_HUB
            self.assertIsNotNone(hub, 'start_server merkt sich das Prüfprojekt')
            hub.module_scaffold({'kind': 'shell', 'id': 'meine-bruecke'})
            hub.shell_set({'shell': 'meine-bruecke'})
            lines = []
            results = run_checks(url, say=lines.append, shell='meine-bruecke')
            by = {n: (ok, d) for n, ok, d in results}
            self.assertTrue(by['load'][0], by['load'][1])
            self.assertTrue(by['talk'][0], 'die Vorlage zeigt das Gespräch – das Werkzeug navigiert auch dort')
            self.assertTrue(by['allowlist'][0])
            self.assertIsNone(by['zones'][0], 'wo das Profil nichts weiß, steht „nicht geprüft“')
            self.assertIsNone(by['profil'][0])
            self.assertFalse([n for n, ok, d in results if ok is False], [l for l in lines if 'FAIL' in l])
            tool_lines = [n for n, ok, d in results if n.startswith('tool:')]
            self.assertTrue(tool_lines, 'die Vorlage öffnet Objekte (dock) – also werden die Werkzeuge geprüft, über data-tool')
        finally:
            stop()

    def test_a_shell_from_a_vorgabe_in_the_entry_template_and_guppi(self):
        """Build 17: „Eigene Oberfläche aus einer Vorgabe“ – eine Vorlage wählen, Skizze sehen, anlegen, sie läuft (Rahmen);
        und der Satz an GUPPI: ein Fake-Modell liefert die Vorgabe, geprüft gegen das Schema, nichts angelegt, bis der Captain es sagt."""
        sync_playwright = browser_or_skip()
        import uix_check
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='start')
        try:
            hub = uix_check.LAST_HUB
            from test_model_structured import Scripted
            hub.runtime.model_router.register(Scripted(['{"raster":["werkstueck"],"gespraech":{"art":"schublade"},"suche":"keine","start":{"type":"logbook","id":"audit"}}']))
            with sync_playwright() as pw:
                b = pw.chromium.launch(); page = b.new_page(viewport={'width': 1400, 'height': 900})
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url); wait_until_started(page); page.wait_for_timeout(1500)
                # der Satz an GUPPI
                page.fill('.vg-text', 'nur das Werkstück, das Gespräch als Schublade, keine Suche, Start im Logbuch')
                page.fill('.vg input[aria-label="id der Oberfläche"]', 'schlicht')
                page.click('.vg button:has-text("GUPPI fragen")')
                page.wait_for_function("()=>{ const e=document.querySelector('.vg-sentence'); return e && e.textContent.length > 0; }", timeout=20000)
                sentence = page.evaluate("()=>(document.querySelector('.vg-sentence') || {}).textContent || ''")
                self.assertIn('Schublade', sentence); self.assertIn('Logbuch', sentence)
                self.assertEqual(page.evaluate("()=>document.querySelectorAll('.vg-sketch .vg-cell').length"), 1)
                self.assertNotIn('schlicht', hub.gateway.shells(), 'ein Vorschlag legt nichts an')
                # eine Vorlage, dann anlegen – der Einstieg nimmt sie und lädt neu
                page.click('.vg button:has-text("Reiter")'); page.wait_for_timeout(400)
                self.assertEqual(page.evaluate("()=>document.querySelectorAll('.vg-sketch .vg-row').length"), 3)
                page.fill('.vg input[aria-label="id der Oberfläche"]', 'bruecke')
                page.click('.vg button:has-text("So anlegen")'); page.wait_for_timeout(2500); wait_until_started(page); page.wait_for_timeout(1200)
                self.assertEqual(page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.id"), 'bruecke')
                self.assertTrue(page.evaluate("()=>!!document.querySelector('.fr-zone-werkstueck [data-tool]')"), 'der Rahmen läuft und zeigt ein Werkzeug')
                self.assertEqual(sorted(p.name for p in (Path(hub.project_root) / 'local_config' / 'shells' / 'bruecke').iterdir()), ['README.md', 'shell.vorgabe.yaml', 'shell.yaml'])
                self.assertEqual(errors, [])
                b.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
