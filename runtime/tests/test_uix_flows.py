"""Bedienwege mit echten Klicks, Shell für Shell (Überarbeitung 15.10.2026).

`uix_check` öffnet Objekte über den Bus; das prüft die Werkzeuge, nicht die Bedienung. Hier wird geklickt, getippt und
gedrückt, wie der Captain es tut – vom Knopf bis zur Wirkung. Entstanden, weil genau so der Fehler ans Licht kam, der zwei
Builds lang in `dock.js` saß: jedes Werkzeug an der Werkbank bekam die api-Funktion als „Shell“, und `ctx.shell.open()` war tot."""
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


class Flows(unittest.TestCase):
    def run_in(self, shell, flow, prepare=None):
        sync_playwright = browser_or_skip()
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell=shell, prepare=prepare)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1400, 'height': 860})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('dialog', lambda d: d.accept())
                page.goto(url); wait_until_started(page); page.wait_for_timeout(1200)
                try:
                    flow(page, wait_until_started)
                finally:
                    browser.close()
                self.assertEqual(errors, [], f'{shell}: Seitenfehler')
        finally:
            stop()

    def test_minimal_shelf_menu_and_command(self):
        def flow(page, _wait):
            page.click('.sh-min-app[data-object="model:alle"]'); page.wait_for_timeout(700)
            self.assertTrue(page.query_selector('.sh-min-win[data-object="model:alle"]'), 'die Ablage öffnet ein Fenster')
            page.click('.sh-min-menu-name:has-text("Fenster")'); page.wait_for_timeout(300)
            page.click('.sh-min-menu-item:has-text("Alle schließen")'); page.wait_for_timeout(500)
            left = page.evaluate("()=>[...document.querySelectorAll('.sh-min-win')].map(w=>w.dataset.object)")
            self.assertEqual(left, ['talk:guppi'], 'alles zu – außer dem Gespräch')
            page.keyboard.press('Control+k'); page.wait_for_timeout(300)
            page.keyboard.type('logbuch'); page.keyboard.press('Enter'); page.wait_for_timeout(700)
            self.assertTrue(page.query_selector('.sh-min-win[data-object="logbook:audit"]'), 'Strg+K, Ort, Enter')
        self.run_in('minimal', flow)

    def test_minimal_build19_home_own_shelf_and_guppi_moves(self):
        """PC-Test 15.10.: kein Weg zurück, keine eigenen Felder, und GUPPI konnte kein Fenster öffnen."""
        def fake_model(hub):
            class FakeServer:
                def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]
            calls = []

            def execute(mission, request):
                calls.append(1)
                if len(calls) % 2 == 1:
                    msg = {'content': '', 'tool_calls': [{'id': 'c', 'type': 'function', 'function': {'name': 'open_place', 'arguments': '{"place": "logbook"}'}}]}
                    return {'status': 'completed', 'model_result': {'message': msg, 'finish_reason': 'tool_calls'}}
                return {'status': 'completed', 'model_result': {'content': 'Das Logbuch liegt bereit.', 'finish_reason': 'stop'}}
            hub.runtime.llama_server = FakeServer(); hub.runtime.control.execute = execute
            self.hub = hub

        def flow(page, wait):
            import yaml
            self.assertEqual(page.evaluate("()=>document.querySelectorAll('.sh-min-app svg').length"),
                             page.evaluate("()=>document.querySelectorAll('.sh-min-app').length"), 'jedes Feld hat ein Bildzeichen')
            # GUPPI: ein Satz mit „öffnen“ ist Navigation – ohne Modell
            page.fill('.t-talk-in input', 'kannst du mir ein fenster für maschinenraum öffnen'); page.keyboard.press('Enter'); page.wait_for_timeout(900)
            self.assertTrue(page.query_selector('.sh-min-win[data-object="machine:machine"]'), 'der Maschinenraum ist offen')
            # GUPPI schlägt vor, der Knopf öffnet
            page.fill('.t-talk-in input', 'was steht denn im Verlauf an'); page.keyboard.press('Enter'); page.wait_for_timeout(1500)
            page.click('.t-talk-offer button:has-text("Öffnen: Logbuch")'); page.wait_for_timeout(800)
            self.assertTrue(page.query_selector('.sh-min-win[data-object="logbook:audit"]'), 'der Knopf unter der Antwort öffnet')
            # eigenes Feld: Auftrag an GUPPI mit Bildzeichen, steht danach in uix.yaml
            page.click('.sh-min-app.add'); page.wait_for_timeout(300)
            page.click('.sh-min-edit .sh-min-seg-item:has-text("Auftrag an GUPPI")')
            page.fill('.sh-min-edit textarea', 'öffne die Hardware'); page.fill('.sh-min-edit input', 'Hardware')
            page.click('.sh-min-edit-icon[title="Blitz"]'); page.click('.sh-min-edit button:has-text("Anlegen")'); page.wait_for_timeout(900)
            doc = yaml.safe_load(self.hub.gateway.registry.config_path.read_text(encoding='utf-8'))
            mine = doc['uix']['shelf']['minimal']
            self.assertEqual(mine[-1], {'kind': 'auftrag', 'text': 'öffne die Hardware', 'label': 'Hardware', 'icon': 'blitz'})
            page.click('.sh-min-app.order:has-text("Hardware")'); page.wait_for_timeout(900)
            self.assertTrue(page.query_selector('.sh-min-win[data-object="hardware:hardware"]'), 'der Auftrag ging ins Gespräch und öffnete')
            page.reload(); wait(page); page.wait_for_timeout(1200)
            self.assertTrue(page.query_selector('.sh-min-app.order:has-text("Hardware")'), 'nach dem Neuladen ist das Feld noch da')
            # zurück zur Übersicht: nur dieser Lauf
            page.click('.sh-min-home'); page.wait_for_timeout(1200); wait(page); page.wait_for_timeout(900)
            self.assertEqual(page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.id"), 'start')
            doc = yaml.safe_load(self.hub.gateway.registry.config_path.read_text(encoding='utf-8'))
            self.assertEqual(doc['uix']['shell'], 'minimal', 'die Wahl in uix.yaml bleibt')
        self.run_in('minimal', flow, prepare=fake_model)

    def test_paperclip_navigation_drawer_and_the_decision_from_the_inbox(self):
        def flow(page, _wait):
            page.click('.pc-nav-row:has-text("Issues")'); page.wait_for_timeout(600)
            self.assertEqual(page.text_content('.pc-top h1'), 'Issues')
            page.click('.pc-back'); page.wait_for_timeout(600)
            self.assertEqual(page.text_content('.pc-top h1'), 'Dashboard', 'Zurück führt zum Dashboard')
            page.keyboard.press('Control+k'); page.keyboard.type('Baue einen CSV-Parser'); page.wait_for_timeout(300)
            page.keyboard.press('Enter'); page.wait_for_timeout(1200)
            self.assertFalse(page.evaluate("()=>document.querySelector('.pc-drawer').hidden"), 'ein Auftrag öffnet die Schublade')
            self.assertIn('CSV-Parser', page.text_content('.t-talk-log'), 'gesendet wird im Gespräch')
            page.keyboard.press('Escape'); page.wait_for_timeout(300)
            self.assertTrue(page.evaluate("()=>document.querySelector('.pc-drawer').hidden"))
            # die Entscheidung: Grenzen bestätigen → Badge → Posteingang auf dem Dashboard → freigeben → Kachel sagt Sandbox
            page.click('.pc-nav-row:has-text("Modus und Grenzen")'); page.wait_for_timeout(900)
            page.click('.pc-verbs button:has-text("Bestätigen")'); page.wait_for_timeout(1200)
            self.assertEqual(page.text_content('.pc-badge'), '1', 'die eigene Handlung zählt sofort')
            page.click('.pc-nav-row:has-text("Dashboard")'); page.wait_for_timeout(1000)
            page.click('.pc-card button:has-text("Freigeben und anwenden")'); page.wait_for_timeout(1500)
            self.assertTrue(page.evaluate("()=>document.querySelector('.pc-badge').hidden"))
            self.assertEqual(page.text_content('.pc-kpi[data-tool="gauge-mode"] b'), 'Sandbox')
        self.run_in('paperclip', flow)

    def test_cockpit_switches_the_shell_from_the_modules_tool(self):
        def flow(page, wait):
            page.click('.ck-tree [role=button]:has-text("Module")'); page.wait_for_timeout(900)
            # die Zeile „Minimal“, nicht der erste Knopf: seit Build 18 steht GUPPI XP (der alte Desktop) davor
            page.click('.t-modules-row:has(b:text-is("Minimal")) button:has-text("Diese Shell nehmen")'); page.wait_for_timeout(900)
            self.assertTrue(page.query_selector('.t-modules-reload button'), 'der Hinweis bringt den Knopf mit')
            page.click('.t-modules-reload button'); page.wait_for_timeout(1500); wait(page); page.wait_for_timeout(1200)
            self.assertEqual(page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.id"), 'minimal', 'neu geladen: die andere Shell')
            page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'module', id:'alle', title:'Module', collection:true})")
            page.wait_for_timeout(900)
            switches = page.evaluate("()=>[...document.querySelectorAll('.t-modules-row')].filter(r=>['Gespräch', 'Module'].includes((r.querySelector('b')||{}).textContent)).map(r=>!!r.querySelector('button'))")
            self.assertEqual(switches, [False, False], 'Gespräch und Module haben keinen Schalter')
        self.run_in('cockpit', flow)

    def test_the_gateway_studio_flow_from_request_to_checked_draft(self):
        """Build 19: 01 Wunsch · 02 Anfrage prüfen (Platzhalter rechts) · 03 lokal freigeben = das Gate · 04 Entwurf, geprüft. Kein Versand."""
        import uix_check
        from test_content_guard import FakeAdapter
        def flow(page, wait):
            hub = uix_check.LAST_HUB
            hub.runtime.model_router.register(FakeAdapter(lambda m: 'Sehr geehrte <PERSON_001>, der Stand folgt; offene Punkte sind offen. Kontakt <EMAIL_001>.'))
            page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'gateway', id:'alle', title:'KI GateWay', collection:true})"); page.wait_for_timeout(900)
            page.fill('.t-gateway-new input', 'Projektabstimmung'); page.click('.t-gateway-new button'); page.wait_for_timeout(1200)
            self.assertTrue(page.query_selector('.t-gateway-flow'), 'der neue Vorgang ist offen')
            page.fill('.t-gateway-text', 'Lena Beispiel fragt per lena@example.com nach dem Stand von NORD-42. Kundennummer K-1042.')
            page.fill('.t-gateway-bind input', 'Torsten (Workflow)')          # G-05: die Person steht in der Bindung und im Gate
            page.click('.t-gateway button:has-text("Datenschutz prüfen")'); page.wait_for_timeout(1200)
            right = page.evaluate("()=>document.querySelector('.t-gateway-right .t-gateway-pre').textContent")
            self.assertIn('<PERSON_001>', right); self.assertNotIn('Lena', right)
            self.assertEqual(page.evaluate("()=>document.querySelectorAll('.t-gateway-right .t-gateway-pre .t-gateway-tok').length"), 3, 'drei Platzhalter im Text (die Legende zählt extra)')
            facts = page.evaluate("()=>document.querySelector('.t-gateway-facts').innerText")
            self.assertIn('Torsten (Workflow)', facts); self.assertIn('Antwortentwurf', facts)
            self.assertIn('SK1', facts); self.assertIn('P01', facts)
            # B6-G-03: Regelnummer im Grund, Leitfaden-Schritt an der Station, Leitfaden-Block nennt den aktuellen Schritt
            self.assertIn('R-01', page.evaluate("()=>document.querySelector('.t-gateway-flow').innerText"))
            self.assertIn('Leitfaden Schritt 4', page.evaluate("()=>[...document.querySelectorAll('.t-gateway-lf')].map(e=>e.textContent).join(' ')"))
            self.assertIn('du bist bei Schritt 4', page.evaluate("()=>document.querySelector('.t-gateway-leitfaden summary').textContent"))
            self.assertEqual(page.evaluate("()=>document.querySelectorAll('.t-gateway-leitfaden ol > li').length"), 7)
            # Frag SEDRA: Antwort ohne Modell, mit Knopf
            page.fill('.t-gateway-frag input', 'Was muss ich als Nächstes machen?'); page.click('.t-gateway-frag button:has-text("Fragen")'); page.wait_for_timeout(900)
            self.assertIn('Schritt 4', page.evaluate("()=>document.querySelector('.t-gateway-frag-out').innerText"))
            self.assertEqual(hub.content_guard.counts.get('SG_MODEL_CALL', 0), 0, 'die Wissensbasis ruft kein Modell')
            self.assertEqual(page.evaluate("()=>[...document.querySelectorAll('.t-gateway-release button')].map(b=>b.textContent)"), ['Lokal freigeben →'],
                             'Wunsch lokal: nur der lokale Weg wird angeboten')
            page.click('.t-gateway-release button'); page.wait_for_timeout(2500)
            answer = page.evaluate("()=>(document.querySelector('.t-gateway-answer') || {}).textContent || ''")
            self.assertIn('Lena Beispiel', answer, 'zurückübersetzt – der Captain sieht die echten Namen')
            self.assertIn('lena@example.com', answer)
            self.assertIn('wird gelöscht am 20', page.evaluate("()=>document.querySelector('.t-gateway-foot').innerText"))
            self.assertIn('KI-Entwurf (fake) – menschlich geprüft: nein', page.evaluate("()=>document.querySelector('.t-gateway-kennz').textContent"), 'R-14')
            page.click('.t-gateway button:has-text("Geprüft")'); page.wait_for_timeout(900)
            self.assertIn('Abgeschlossen', page.evaluate("()=>document.querySelector('.t-gateway-head .t-gateway-pill').textContent"))
            self.assertIn('menschlich geprüft: ja', page.evaluate("()=>document.querySelector('.t-gateway-kennz').textContent"))
            self.assertEqual(hub.content_guard.counts.get('SG_MODEL_CALL'), 1, 'genau ein Modellaufruf, durch den Inhaltsschutz')
            # A01 von Hand: ein neuer Vorgang mit Hochrisiko-Kontext wird SK3 mit R-13
            for _ in range(4):                                   # zurück zur Liste: der Reiter des Vorgangs steht noch vorn – zweimal anstoßen ist erlaubt
                page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'gateway', id:'alle', title:'KI GateWay', collection:true})"); page.wait_for_timeout(900)
                if page.query_selector('.t-gateway-new input'): break
            page.fill('.t-gateway-new input', 'Bewerbung'); page.click('.t-gateway-new button'); page.wait_for_timeout(1200)
            page.fill('.t-gateway-text', 'Bitte eine Antwort auf die Bewerbung entwerfen.')
            page.check('.t-gateway-check:has-text("A01") input'); page.click('.t-gateway button:has-text("Datenschutz prüfen")'); page.wait_for_timeout(1200)
            facts = page.evaluate("()=>document.querySelector('.t-gateway-facts').innerText")
            self.assertIn('SK3', facts); self.assertIn('A01', facts)
            self.assertIn('R-13', page.evaluate("()=>document.querySelector('.t-gateway-flow').innerText"))
        self.run_in('cockpit', flow)

    def test_the_switcher_is_in_every_shell_and_leads_to_the_overview(self):
        """B6-G-04 (Klaus 15.10.): in jeder Shell derselbe Knopf – Übersicht, andere Oberfläche, Darstellung, Schrift. Alt+S öffnet ihn."""
        def flow(page, wait):
            self.assertTrue(page.query_selector('.sx-chip'), 'der Umschalter ist da')
            self.assertFalse(page.is_visible('.sx-panel'), 'zu ist zu – auch sichtbar, nicht nur als Attribut')
            self.assertEqual(page.evaluate("()=>document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, 'kein waagerechter Überlauf')
            page.click('.sx-chip'); page.wait_for_timeout(600)
            self.assertTrue(page.is_visible('.sx-panel'))
            labels = page.evaluate("()=>[...document.querySelectorAll('.sx-item b')].map(b=>b.textContent)")
            self.assertEqual(labels[0], 'Übersicht der Oberflächen')
            self.assertTrue(any('Minimal' in l for l in labels) and any('GateWay Studio' in l for l in labels), labels)
            self.assertFalse(any('Cockpit' in l for l in labels), 'die eigene Shell steht nicht zur Wahl')
            page.click('.sx-seg-btn[data-value="nacht"]'); page.click('.sx-seg-btn[data-value="gross"]'); page.wait_for_timeout(200)
            self.assertEqual(page.evaluate("()=>document.documentElement.dataset.theme + '/' + document.documentElement.dataset.scale"), 'nacht/gross')
            self.assertGreaterEqual(float(page.evaluate("()=>getComputedStyle(document.body).fontSize")[:-2]), 16, 'Groß wirkt auf die Grundschrift')
            page.keyboard.press('Escape'); page.wait_for_timeout(200)
            self.assertTrue(page.evaluate("()=>document.querySelector('.sx-panel').hidden"), 'Esc schließt')
            page.keyboard.press('Alt+s'); page.wait_for_timeout(300)
            self.assertFalse(page.evaluate("()=>document.querySelector('.sx-panel').hidden"), 'Alt+S öffnet')
            page.click('.sx-item:has-text("Übersicht der Oberflächen")'); page.wait_for_timeout(2500)
            self.assertTrue(page.query_selector('.st-head-text'), 'die Übersicht der Oberflächen ist da')
            self.assertFalse(page.query_selector('.sx-chip'), 'in der Übersicht gibt es den Umschalter nicht – sie ist selbst die Wahl')
            self.assertEqual(page.evaluate("()=>document.documentElement.dataset.scale"), 'gross', 'die Schriftwahl bleibt über das Neuladen')
        self.run_in('cockpit', flow)

    def test_the_switcher_also_sits_in_a_shell_from_vorgabe(self):
        def flow(page, wait):
            self.assertTrue(page.query_selector('.sx-chip'))
            self.assertIn('GateWay Studio', page.evaluate("()=>document.querySelector('.sx-chip-text').textContent"))
            page.click('.sx-chip'); page.wait_for_timeout(600)
            self.assertTrue(any('Cockpit' in l for l in page.evaluate("()=>[...document.querySelectorAll('.sx-item b')].map(b=>b.textContent)")))
        self.run_in('gateway-studio', flow)

    def test_every_tool_at_the_cockpit_workbench_gets_a_real_shell_api(self):
        """Der Fehler selbst, als Test: ein Werkzeug im Reiter kann die Shell bitten, etwas zu öffnen."""
        def flow(page, _wait):
            page.evaluate("()=>window.sedraBoot.ctx.bus.emit('object.open', {type:'intent', id:'alle', title:'Vorhaben', collection:true})")
            page.wait_for_timeout(900)
            api = page.evaluate("()=>{const t = window.sedra.tools.get('intent'); return [typeof t.ctx.shell.open, typeof t.ctx.shell.notify, typeof t.ctx.shell.decide];}")
            self.assertEqual(api, ['function', 'function', 'function'])
            page.fill('.t-intent-form input', 'Export aufräumen'); page.click('.t-intent-form button'); page.wait_for_timeout(1500)
            tabs = page.evaluate("()=>[...document.querySelectorAll('.dk-tab')].map(t=>t.textContent.trim())")
            self.assertTrue(any('Export aufräumen' in t for t in tabs), f'das neue Vorhaben öffnet als Reiter: {tabs}')
            self.assertEqual(page.evaluate("()=>window.sedraBoot.problems"), [], 'der Loader meldet keine unvollständige Shell-API')
        self.run_in('cockpit', flow)


if __name__ == '__main__':
    unittest.main()


class Build24(unittest.TestCase):
    """Ticket B6-G-06 (Klaus 15.10.2026): keine Dummys in Cockpit und Paperclip – und SEDRA kennt seinen Arbeitsplatz."""
    run_in = Flows.run_in

    def test_cockpit_new_project_new_model_and_test_track_are_real(self):
        def flow(page, _wait):
            # ＋ Neu → Projekt: ein Formular, das anlegt
            page.click('.dk-new'); page.wait_for_timeout(300)
            page.click('.ck-menu-item:has-text("Projekt")'); page.wait_for_timeout(900)
            page.fill('.t-files-input', 'Zweites Projekt'); page.keyboard.press('Enter'); page.wait_for_timeout(1200)
            self.assertIn('ist angelegt', page.text_content('.t-files .s-note.ok'))
            self.assertEqual(page.evaluate("()=>window.sedraApi.api('/api/projects').then(p=>p.length)"), 2, 'der Ordner ist wirklich da')
            page.click('.t-files .s-note.ok button:has-text("Modus und Grenzen")'); page.wait_for_timeout(900)
            self.assertTrue(page.query_selector('.dk-tab.on:has-text("Modus und Grenzen")'), 'der Knopf führt zu den Grenzen')
            # Baum → Modell hinzufügen: der Abschnitt ist offen; ein falscher Pfad gibt einen klaren Satz, kein Rezept
            page.click('.ck-tree [role=button]:has-text("Modell hinzufügen")'); page.wait_for_timeout(900)
            self.assertTrue(page.evaluate("()=>document.querySelector('.t-shop-section[data-section=neu]').open"))
            page.fill('.t-shop-input', '/tmp/gibt-es-nicht.gguf'); page.keyboard.press('Enter'); page.wait_for_timeout(900)
            self.assertIn('GGUF', page.text_content('.t-shop-section[data-section=neu] .s-note.bad'))
            # Baum → Teststrecke: offen, Start gesperrt mit Grund (kein Modell)
            page.click('.ck-tree [role=button]:has-text("Teststrecke")'); page.wait_for_timeout(900)
            self.assertTrue(page.evaluate("()=>document.querySelector('.t-shop-section[data-section=teststrecke]').open"))
            self.assertTrue(page.evaluate("()=>document.querySelector('.t-shop-section[data-section=teststrecke] button.p').disabled"))
            self.assertIn('Kein Modell geladen', page.text_content('.t-shop-section[data-section=teststrecke]'))
            # Baum: keine Routinen, kein GateWay-Block (bleibt im Studio)
            tree = page.text_content('.ck-tree')
            self.assertNotIn('Routinen', tree); self.assertNotIn('KI GateWay', tree)
            # Gespräch: der Arbeitsplatz antwortet ohne Modell, mit Knopf
            page.fill('.t-talk input', 'Was muss ich als Nächstes machen?'); page.keyboard.press('Enter'); page.wait_for_timeout(1500)
            log = page.text_content('.t-talk-log')
            self.assertIn('Cockpit', log); self.assertIn('arbeitsplatz-wissen', log)
            page.click('.t-talk-offer button >> nth=0'); page.wait_for_timeout(900)
            self.assertTrue(page.query_selector('.dk-tab.on'), 'der Knopf öffnet den Ort')
        self.run_in('cockpit', flow)

    def test_paperclip_new_project_and_the_workplace_answers(self):
        def flow(page, _wait):
            nav = page.text_content('.pc-nav')
            self.assertNotIn('Routinen', nav); self.assertNotIn('KI GateWay', nav)
            page.click('.pc-nav-row:has-text("Dateien")'); page.wait_for_timeout(800)
            page.click('.pc-verbs button:has-text("Neues Projekt")'); page.wait_for_timeout(300)
            page.fill('.t-files-input', 'Paperclip-Projekt'); page.click('.t-files-new button:has-text("Anlegen")'); page.wait_for_timeout(1200)
            self.assertIn('Paperclip-Projekt', page.text_content('.t-files .s-note.ok'))
            page.click('.pc-fab'); page.wait_for_timeout(300)
            page.fill('.pc-drawer input', 'Wo finde ich den Posteingang?'); page.keyboard.press('Enter'); page.wait_for_timeout(1500)
            log = page.text_content('.t-talk-log')
            self.assertIn('Entscheidungen', log); self.assertIn('arbeitsplatz-wissen', log)
            page.click('.t-talk-offer button >> nth=0'); page.wait_for_timeout(900)
            self.assertEqual(page.text_content('.pc-top h1'), 'Posteingang', 'der Knopf öffnet den Ort mit dem Paperclip-Wort')
        self.run_in('paperclip', flow)
