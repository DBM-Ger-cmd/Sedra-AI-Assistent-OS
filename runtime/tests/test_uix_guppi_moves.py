"""Build 19 – GUPPI bewegt sich in der Oberfläche, und die Minimal-Shell gehört dem Captain.

Aus dem PC-Test vom 15.10.2026:
  * „kannst du mir ein Fenster für Maschinenraum öffnen“ → GUPPI: „Ich kann keine neuen Fenster öffnen.“
  * „ja“ auf die angekündigte Entscheidung ging ans Modell („Verstehe. Wie kann ich dir helfen?“).
  * Minimal: kein Weg zurück zur Übersicht; die Ablage hatte keine Bildzeichen und ließ sich nicht erweitern.

Die Zusagen, je ein Test: GUPPI **schlägt vor, tut nichts** (jede Bewegung ist ein Knopf in `ui_actions`; ausgeführt wird erst
über `POST /api/actions` mit denselben Gates); ein Satz mit „öffnen“ ist Navigation ohne Modell; „ja“ liest die Entscheidungen
frisch; die Ablage steht in uix.yaml (der Port wechselt bei jedem Start), wird geprüft und überlebt einen Shell-Wechsel; „Zur
Übersicht“ gilt nur für diesen Lauf."""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

RUNTIME = Path(__file__).resolve().parents[1]
UIX = RUNTIME / 'src' / 'guppi_runtime' / 'uix'
MINIMAL = UIX / 'shells' / 'minimal'
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


def run_js(files, code):
    box = ';'.join(f"require({json.dumps(str(f))})" for f in files)
    out = subprocess.run(['node', '-e', f'const box = globalThis; {box}; {code}'], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr.strip()[:400])
    return json.loads(out.stdout.strip().splitlines()[-1])


class FakeHub:
    """Just what ChatTools reads – and a trap: anything that would *do* something raises."""

    def __init__(self, state='bereit'):
        self.state = state

    def object_view(self, kind, oid):
        if kind == 'model' and oid == 'coder.qwen':
            return {'type': 'model', 'id': oid, 'title': oid, 'state': self.state}
        return {'type': kind, 'id': oid, 'title': oid, 'state': 'nicht gefunden'}

    def decisions_view(self):
        return {'items': [{'id': 'request:M-1', 'title': 'Kontext 65536', 'ways': ['freigeben_und_anwenden', 'ablehnen']}]}

    def __getattr__(self, name):          # load_model, run_mission, intent_create, … – must never be reached from the chat
        raise AssertionError(f'ChatTools rief {name} – ein Vorschlag darf nichts tun')


class ChatToolsMove(unittest.TestCase):
    def tools(self, state='bereit'):
        from guppi_runtime.chat_tools import ChatTools
        return ChatTools(FakeHub(state))

    def test_the_places_are_the_same_as_in_the_contract(self):
        from guppi_runtime.chat_tools import PLACES
        ids = run_js([UIX / 'ui' / 'places.js'], "console.log(JSON.stringify(box.sedraPlaces.PLACES.map(p=>p.id)));")
        self.assertEqual(sorted(PLACES), sorted(ids), 'chat_tools.PLACES und ui/places.js nennen dieselben Orte')

    def test_open_place_is_a_button_not_a_deed(self):
        box = self.tools()
        out = json.loads(box.call('open_place', {'place': 'machine'}))
        self.assertEqual(out['status'], 'offered')
        self.assertEqual(box.ui_actions, [{'kind': 'open', 'place': 'machine', 'title': 'Maschinenraum'}])
        self.assertTrue(box.call('open_place', {'place': 'keller'}).startswith('error: unknown_place'))

    def test_an_action_is_offered_only_when_the_object_offers_it_now(self):
        box = self.tools('bereit')
        listed = json.loads(box.call('list_actions', {'type': 'model', 'id': 'coder.qwen'}))
        self.assertEqual([a['verb'] for a in listed['actions']], ['laden'])
        self.assertEqual(json.loads(box.call('propose_action', {'type': 'model', 'id': 'coder.qwen', 'verb': 'laden'}))['status'], 'offered')
        self.assertTrue(box.call('propose_action', {'type': 'model', 'id': 'coder.qwen', 'verb': 'entladen'}).startswith('error: verb_not_offered_now'))
        self.assertTrue(box.call('propose_action', {'type': 'model', 'id': 'gibtsnicht', 'verb': 'laden'}).startswith('error: object_not_found'))
        self.assertEqual(box.ui_actions[0]['kind'], 'verb')
        self.assertFalse(box.ui_actions[0]['needs_gate'])

    def test_an_intent_is_proposed_not_created_and_the_buttons_are_limited(self):
        box = self.tools()
        box.call('propose_intent', {'title': 'Export aufräumen', 'text': 'Den CSV-Export aufräumen'})
        self.assertEqual(box.ui_actions[0], {'kind': 'intent', 'title': 'Export aufräumen', 'text': 'Den CSV-Export aufräumen'})
        for place in ('models', 'logbook', 'decisions'):
            box.call('open_place', {'place': place})
        self.assertTrue(box.call('open_place', {'place': 'crew'}).startswith('error: too_many'))
        self.assertEqual(len(box.ui_actions), 4)

    def test_waiting_decisions_are_readable(self):
        out = json.loads(self.tools().call('list_decisions', {}))
        self.assertEqual(out[0]['id'], 'request:M-1')


class ChatReplyCarriesTheButtons(unittest.TestCase):
    def test_the_reply_carries_ui_actions_and_the_audit_counts_them(self):
        from guppi_runtime.uix_server import UIXHub
        with tempfile.TemporaryDirectory() as tmp:
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                class FakeServer:
                    def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]
                turns = []

                def fake_execute(mission, request):
                    turns.append(request)
                    if len(turns) == 1:
                        msg = {'content': '', 'tool_calls': [{'id': 'c1', 'type': 'function',
                                                              'function': {'name': 'open_place', 'arguments': '{"place": "machine"}'}}]}
                        return {'status': 'completed', 'model_result': {'message': msg, 'finish_reason': 'tool_calls'}}
                    return {'status': 'completed', 'model_result': {'content': 'Ich öffne dir den Maschinenraum.', 'finish_reason': 'stop'}}
                hub.runtime.llama_server = FakeServer(); hub.runtime.control.execute = fake_execute
                out = hub.chat_reply({'text': 'kannst du mir den Maschinenraum zeigen'})
                self.assertEqual(out['status'], 'completed')
                self.assertEqual(out['ui_actions'], [{'kind': 'open', 'place': 'machine', 'title': 'Maschinenraum'}])
                self.assertEqual(turns[0]['tool_choice'], 'required', '„zeig“ ist eine Bewegung: erst ein Werkzeug, dann die Antwort')
                self.assertIn('open_place', turns[0]['messages'][0]['content'], 'der Systemsatz nennt die Werkzeuge')
                self.assertNotIn('nichts ausführen', turns[0]['messages'][0]['content'])
                lines = [json.loads(l) for l in hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
                events = [e for e in lines if e.get('event_type') == 'UIX_CHAT_TOOLS']
                self.assertEqual(events[-1]['payload']['offered'], ['open'])
            finally:
                hub.close()


class TheConversationRoutesAndAnswers(unittest.TestCase):
    def test_a_sentence_that_asks_to_open_is_navigation(self):
        out = run_js([UIX / 'ui' / 'places.js'], """
          const r = t=>{ const x = box.sedraPlaces.routeText(t); return x.kind === 'place' ? x.id : 'talk'; };
          console.log(JSON.stringify([r('kannst du mir ein fenster für maschinenraum öffnen'), r('öffne die werkstatt'),
                                      r('geh zum logbuch'), r('zeig mir die Modelle von gestern'), r('öffne mir das bitte'),
                                      r('Baue einen Parser und öffne ihn')]));
        """)
        self.assertEqual(out, ['machine', 'models', 'logbook', 'talk', 'talk', 'talk'])

    def test_yes_reads_the_list_fresh_and_ok_is_no_approval(self):
        out = run_js([UIX / 'tools' / 'talk' / 'tool.js'], """
          const t = box.sedraTalkPure;
          const req = {id:'request:1', ways:['freigeben_und_anwenden','ablehnen']}, gate = {id:'gate:2', ways:['einmal','ablehnen']};
          console.log(JSON.stringify({
            ja: t.yesNo('ja'), ok: t.yesNo('ok'), nein: t.yesNo('Nein!'),
            one: (t.pickDecision([req], null) || {}).id, announced: (t.pickDecision([req, gate], 'gate:2') || {}).id,
            gone: t.pickDecision([req, gate], 'gate:9'), none: t.pickDecision([], 'x'),
            wayReq: t.wayFor(req, 'einmal'), wayGate: t.wayFor(gate, 'einmal'), wayNo: t.wayFor(req, 'ablehnen'),
            label: t.actionLabel({kind:'verb', label:'Laden', title:'coder.qwen', needs_gate:false})
          }));
        """)
        self.assertEqual((out['ja'], out['ok'], out['nein']), ('einmal', '', 'ablehnen'))
        self.assertEqual((out['one'], out['announced'], out['gone'], out['none']), ('request:1', 'gate:2', None, None))
        self.assertEqual((out['wayReq'], out['wayGate'], out['wayNo']), ('freigeben_und_anwenden', 'einmal', 'ablehnen'))
        self.assertEqual(out['label'], 'Laden: coder.qwen')

    def test_the_talk_manifest_allows_exactly_the_new_routes(self):
        doc = yaml.safe_load((UIX / 'tools' / 'talk' / 'tool.yaml').read_text(encoding='utf-8'))['tool']
        for route in ('POST /api/actions', 'POST /api/intent/create'):
            self.assertIn(route, doc['api'])
        self.assertNotIn('POST /api/decisions/answer', doc['api'], 'Entscheidungen beantwortet die Shell, nicht das Gespräch')


class TheShelf(unittest.TestCase):
    def registry(self, tmp, text='uix:\n  shell: minimal\n'):
        from guppi_runtime.desk.registry import Registry
        cfg = Path(tmp) / 'local_config'
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / 'uix.yaml').write_text(text, encoding='utf-8')
        return Registry(Path(tmp))

    def test_saved_checked_and_kept_through_a_shell_change(self):
        from guppi_runtime.desk.registry import UixConfigError
        with tempfile.TemporaryDirectory() as tmp:
            reg = self.registry(tmp)
            items = [{'kind': 'place', 'place': 'machine', 'label': 'Maschine', 'icon': 'maschine'},
                     {'kind': 'auftrag', 'text': 'Lade das Coder-Modell', 'label': 'Coder laden', 'icon': 'blitz'},
                     {'kind': 'object', 'object': {'type': 'task', 'id': 'M-20261015-ab', 'title': 'Parser'}, 'label': 'Parser', 'icon': 'aufgaben'}]
            reg.save_shelf('minimal', items)
            self.assertEqual(reg.shelf()['minimal'][1]['text'], 'Lade das Coder-Modell')
            reg.save_config(shell='cockpit')
            self.assertEqual(len(reg.shelf()['minimal']), 3, 'ein Shell-Wechsel löscht die Ablage nicht')
            reg.save_config(disabled=['meter'])
            self.assertEqual(len(reg.shelf()['minimal']), 3)
            for bad in ([{'kind': 'shell', 'label': 'x'}], [{'kind': 'auftrag', 'label': 'x', 'text': ''}],
                        [{'kind': 'place', 'place': '../x', 'label': 'x'}], [{'kind': 'place', 'place': 'machine', 'label': 'x' * 25}],
                        [{'kind': 'object', 'object': {'type': 'file', 'id': 'a'}, 'label': 'x'}],
                        [{'kind': 'place', 'place': 'machine', 'label': 'x', 'icon': '<svg>'}], [{'kind': 'place', 'place': 'machine', 'label': 'x'}] * 25):
                with self.subTest(bad=str(bad)[:60]), self.assertRaises(UixConfigError):
                    reg.save_shelf('minimal', bad)
            reg.save_shelf('minimal', None)
            self.assertNotIn('minimal', reg.shelf())

    def test_a_tool_switch_under_a_start_override_keeps_the_chosen_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = self.registry(tmp)
            reg.shell_override = 'start'
            reg.save_config(disabled=['meter'])
            reg.save_shelf('minimal', [{'kind': 'place', 'place': 'machine', 'label': 'M'}])
            reg.shell_override = None
            self.assertEqual(reg.config()['shell'], 'minimal', 'der Override dieses Starts wird nicht zur Wahl')

    def test_overview_is_a_visit_and_the_shelf_route_is_audited(self):
        from guppi_runtime.uix_server import UIXHub
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'project' / 'local_config'
            cfg.mkdir(parents=True)
            (cfg / 'uix.yaml').write_text('uix:\n  shell: minimal\n', encoding='utf-8')
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                out = hub.shell_set({'shell': 'start', 'nur_jetzt': True})
                self.assertEqual(out['status'], 'visit')
                self.assertEqual(hub.gateway.manifest()['shell']['id'], 'start')
                self.assertEqual(yaml.safe_load((cfg / 'uix.yaml').read_text(encoding='utf-8'))['uix']['shell'], 'minimal')
                self.assertEqual(hub.shelf_view()['chosen'], 'minimal')
                hub.shell_set({'shell': 'minimal'})
                self.assertIsNone(hub.gateway.registry.shell_override, 'eine Wahl hebt den Besuch auf')
                saved = hub.shelf_save({'shell': 'minimal', 'items': [{'kind': 'auftrag', 'text': 'öffne den Maschinenraum', 'label': 'Maschine'}]})
                self.assertEqual(saved['items'][0]['icon'], 'star')
                with self.assertRaises(ValueError):
                    hub.shelf_save({'shell': 'gibtsnicht', 'items': []})
                with self.assertRaises(ValueError):
                    hub.shelf_save({'shell': 'minimal', 'items': [{'kind': 'auftrag', 'label': 'x'}]})
                kinds = [e['event_type'] for e in hub.audit_view()['events']]
                self.assertIn('UIX_SHELL_VISIT', kinds); self.assertIn('UIX_SHELF_SAVED', kinds)
            finally:
                hub.close()

    def test_minimal_declares_the_routes_it_now_uses(self):
        doc = yaml.safe_load((MINIMAL / 'shell.yaml').read_text(encoding='utf-8'))['shell']
        for route in ('GET /api/uix/modules', 'GET /api/uix/shelf', 'POST /api/uix/shelf'):      # Wechsel über sedraWechsel (Härtung 30.10., HU-S4) – kein eigener POST /api/uix/shell mehr
            self.assertIn(route, doc['api'])
        self.assertEqual(doc['entry']['js'][0], 'icons.js', 'die Zeichen zuerst: Menüleiste und Ablage brauchen sie')

    def test_pure_parts_of_shelf_editor_and_icons(self):
        out = run_js([UIX / 'ui' / 'places.js', MINIMAL / 'icons.js', MINIMAL / 'shelfedit.js', MINIMAL / 'shelf.js'], """
          const P = box.sedraPlaces.PLACES, I = require(%s), E = require(%s), S = require(%s);
          const types = P.map(p=>p.object.type).concat(S.SHELF.map(e=>e.object ? e.object.type : 'machine'));
          console.log(JSON.stringify({
            missing: types.filter(t=>I.typeIcon(t) === 'stern'),
            unknownIcons: S.SHELF.filter(e=>!I.ICONS[e.icon]).map(e=>e.label),
            place: E.entryFrom({kind:'place', place:'machine', label:'', icon:''}, P, I.typeIcon),
            noPlace: E.entryFrom({kind:'place', place:''}, P, I.typeIcon).error,
            talkWin: E.entryFrom({kind:'object', object:{type:'talk', id:'guppi'}}, P, I.typeIcon).error,
            order: E.entryFrom({kind:'auftrag', text:'Lade das Coder-Modell bitte jetzt sofort', label:''}, P, I.typeIcon).entry,
            moved: S.move([1,2,3], 0, 1), edge: S.move([1,2,3], 2, 1),
            resolved: S.resolve({kind:'place', place:'logbook'}, P).type,
            marks: S.openMarks([{kind:'place', place:'machine'}, {kind:'auftrag', text:'x'}], [{type:'machine', id:'machine'}], P)
          }));
        """ % (json.dumps(str(MINIMAL / 'icons.js')), json.dumps(str(MINIMAL / 'shelfedit.js')), json.dumps(str(MINIMAL / 'shelf.js'))))
        self.assertEqual(out['missing'], [], 'jeder Ort und jedes Vorgabefeld hat ein eigenes Zeichen')
        self.assertEqual(out['unknownIcons'], [])
        self.assertEqual(out['place']['entry'], {'kind': 'place', 'place': 'machine', 'label': 'Maschinenraum', 'icon': 'maschine'})
        self.assertTrue(out['noPlace']); self.assertTrue(out['talkWin'])
        self.assertEqual(out['order'], {'kind': 'auftrag', 'text': 'Lade das Coder-Modell bitte jetzt sofort', 'label': 'Lade das Coder-Modell bi', 'icon': 'auftrag'})
        self.assertEqual((out['moved'], out['edge'], out['resolved'], out['marks']), ([2, 1, 3], [1, 2, 3], 'logbook', [True, False]))

    def test_the_icons_are_paths_only(self):
        text = (MINIMAL / 'icons.js').read_text(encoding='utf-8')
        self.assertNotIn('innerHTML', text)
        for path in re.findall(r"'(M[0-9][^']*)'", text):
            self.assertRegex(path, r'^[MmLlHhVvAaCcZz0-9 .,\-]+$', path)


if __name__ == '__main__':
    unittest.main()
