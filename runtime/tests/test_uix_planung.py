"""Der Planungstisch (19.10.2026): die Arbeitsumgebung der KI-Assistenten – im Gespräch mit einer Rolle werden Ziele (Vorhaben mit
Stufen) und Aufträge (Aufgaben) vorgeschlagen; erst der Klick des Captains legt an, nichts wird ausgeführt.

Je Zusage ein Test: propose_intent trägt Stufen, propose_task ist ein Vorschlag, der Planungsmodus nimmt die Rolle in den Systemsatz
und nur die Werkzeuge des Planens; im Browser (Paperclip) macht ein Fake-Modell einen Vorschlag mit Stufen, „Übernehmen“ legt das
Ziel an, und ohne Modell legt „Als Auftrag“ den Satz direkt an."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.chat_tools import ChatTools, PLANUNG_TOOLS, SCHEMAS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


class FakeServer:
    def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]


def fake_model(turns, first_call):
    """Erste Runde: ein Werkzeugaufruf (first_call = (name, args)); zweite Runde: der Satz."""
    def execute(mission, request):
        turns.append(request)
        if len(turns) == 1:
            msg = {'content': '', 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': first_call[0], 'arguments': json.dumps(first_call[1])}}]}
            return {'status': 'completed', 'model_result': {'message': msg, 'finish_reason': 'tool_calls'}}
        return {'status': 'completed', 'model_result': {'content': 'Ich habe dir ein Ziel mit Stufen vorgeschlagen – rechts auf dem Tisch.', 'finish_reason': 'stop'}}
    return execute


class Proposals(unittest.TestCase):
    def test_propose_intent_carries_stages_and_propose_task_is_only_a_proposal(self):
        box = ChatTools(None)
        box.call('propose_intent', {'title': 'Shop', 'text': 'drei Assets', 'stufen': ['Nische', ' Modellieren ', '', 42]})
        box.call('propose_task', {'text': 'Drei Vorschaubilder je Produkt rendern.'})
        self.assertEqual(box.ui_actions[0], {'kind': 'intent', 'title': 'Shop', 'text': 'drei Assets', 'stufen': ['Nische', 'Modellieren', '42']})
        self.assertEqual(box.ui_actions[1]['kind'], 'task')
        self.assertEqual(box.ui_actions[1]['text'], 'Drei Vorschaubilder je Produkt rendern.')
        self.assertIn('error', box.call('propose_task', {'text': ''}))
        self.assertTrue(set(PLANUNG_TOOLS) <= set(SCHEMAS))
        self.assertEqual(ChatTools(None, PLANUNG_TOOLS).names, PLANUNG_TOOLS, 'der Planungstisch bekommt nur die Werkzeuge des Planens')


class PlanningMode(unittest.TestCase):
    def test_the_role_is_in_the_system_sentence_and_only_planning_tools_are_offered(self):
        from guppi_runtime.uix_server import UIXHub
        with tempfile.TemporaryDirectory() as tmp:
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                turns = []
                hub.runtime.llama_server = FakeServer()
                hub.runtime.control.execute = fake_model(turns, ('propose_intent', {'title': '3D-Assets über Etsy', 'text': 'Shop aufbauen', 'stufen': ['Nische', 'Modellieren', 'Veröffentlichen']}))
                out = hub.planung_reply({'text': 'Wir wollen 3D-Assets über Etsy verkaufen, plane das mit mir', 'rolle': 'researcher'})
                self.assertEqual(out['status'], 'completed')
                self.assertEqual(out['ui_actions'][0]['stufen'], ['Nische', 'Modellieren', 'Veröffentlichen'])
                system = turns[0]['messages'][0]['content']
                self.assertIn('der Rechercheur', system)
                self.assertIn('Planungstisch', system)
                self.assertEqual(sorted(t['function']['name'] for t in turns[0]['tools']), sorted(PLANUNG_TOOLS))
                lines = [json.loads(l) for l in hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
                last = [e for e in lines if e.get('event_type') == 'UIX_CHAT_TOOLS'][-1]['payload']
                self.assertEqual((last['modus'], last['offered']), ('planung', ['intent']))
                self.assertEqual(hub.objects_view({'type': 'intent'})['items'], [], 'ein Vorschlag legt nichts an')
            finally:
                hub.close()


class InTheBrowser(unittest.TestCase):
    def test_a_proposal_with_stages_becomes_a_goal_and_a_sentence_becomes_an_order(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise unittest.SkipTest('playwright fehlt')
        import uix_check
        from uix_check import start_server, wait_until_started
        url, stop = start_server(lambda *a: None, shell='paperclip')
        try:
            hub = uix_check.LAST_HUB
            turns = []
            hub.runtime.llama_server = FakeServer()
            hub.runtime.control.execute = fake_model(turns, ('propose_intent', {'title': '3D-Assets über einen Etsy-Shop', 'text': 'Vom Modell bis zum Verkauf.',
                                                                              'stufen': ['Nische festlegen', 'Assets modellieren', 'Listing schreiben', 'Veröffentlichen']}))
            with sync_playwright() as pw:
                b = pw.chromium.launch(); page = b.new_page(viewport={'width': 1400, 'height': 900})
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url); wait_until_started(page); page.wait_for_timeout(1200)
                page.click('.pc-nav-row:has-text("Planungstisch")')
                page.wait_for_selector('.t-planung-eingabe textarea', timeout=15000)
                page.select_option('.t-planung-rolle', 'planner')
                page.fill('.t-planung-eingabe textarea', 'Wir wollen 3D-Assets über einen Etsy-Shop verkaufen')
                page.keyboard.press('Enter')
                page.wait_for_selector('.t-planung-karte.intent', timeout=20000)
                self.assertEqual(page.locator('.t-planung-stufen li').count(), 4, 'die Karte zeigt die vier Stufen')
                page.click('.t-planung-karte.intent button:has-text("Übernehmen")')
                page.wait_for_selector('.t-planung-fest', timeout=15000)
                goals = hub.objects_view({'type': 'intent'})['items']
                self.assertEqual(len(goals), 1)
                self.assertEqual([s['name'] for s in goals[0]['stufen']], ['Nische festlegen', 'Assets modellieren', 'Listing schreiben', 'Veröffentlichen'])
                self.assertEqual(page.locator('.t-planung-karte').count(), 0, 'übernommen heißt vom Tisch')
                # ohne Assistent: der Satz wird direkt ein Auftrag – eine Aufgabe, geplant, nicht ausgeführt
                page.fill('.t-planung-eingabe textarea', 'Drei Vorschaubilder je Produkt rendern')
                page.click('.t-planung-knoepfe button:has-text("Als Auftrag")')
                page.click('.t-planung-karte.task button:has-text("Übernehmen")')
                page.wait_for_function("()=>document.querySelectorAll('.t-planung-fest').length === 2", timeout=15000)
                tasks = [t for t in hub.objects_view({'type': 'task'})['items'] if 'Vorschaubilder' in t['title']]
                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0]['state'], 'bereit', 'geplant, nicht ausgeführt')
                self.assertEqual(errors, [])
                b.close()
        finally:
            stop()


if __name__ == '__main__':
    unittest.main()
