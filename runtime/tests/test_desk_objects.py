"""Das Objektmodell und die Verben des Desks (SHELL_WERKZEUG_VERTRAG_v1 §10.1/§10.2).

Geprüft wird, was die Oberfläche glauben darf: dass jedes Objekt dieselbe Form hat, dass ein Verb nur im passenden Zustand
angeboten wird, dass ein Verb, das nicht angeboten wird, auch nicht läuft – und dass die Gates darunter dieselben bleiben."""
import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import actions as desk_actions
from guppi_runtime.desk import objects as desk_objects

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'

SHAPE = ('type', 'id', 'title', 'state', 'summary', 'actions', 'links')


def compact(**kw):
    base = {'mission_id': 'M-1', 'intent': 'CSV-Parser bauen', 'phase': 'EXECUTE', 'status': 'active',
            'steps': ['a', 'b', 'c'], 'steps_done': 1, 'pending_gates': 0}
    base.update(kw)
    return base


class Shape(unittest.TestCase):
    def test_every_object_has_the_same_form(self):
        candidates = [
            desk_objects.task_object(compact()),
            desk_objects.candidate_object({'identity': {'mission_id': 'M-1'}, 'plan': {}, 'execution': {}}),
            desk_objects.model_object({'id': 'coder.local', 'model': 'x.gguf', 'roles': ['coder'], 'provider': 'llama-cpp-server', 'enabled': True, 'loaded': False}),
            desk_objects.decision_object({'id': 'gate:HG-1', 'kind': 'gate', 'title': 'Netz', 'describe': 'pypi', 'mission_id': 'M-1', 'gate_id': 'HG-1', 'ways': ['einmal', 'ablehnen']}),
            desk_objects.skill_object({'id': 'debug', 'name': 'Debuggen', 'description': 'Fehler finden'}),
            desk_objects.project_object({'project_id': 'P-1', 'name': 'Export'}),
            desk_objects.not_found('task', 'M-weg'),
        ]
        for obj in candidates:
            with self.subTest(obj['type']):
                for field in SHAPE:
                    self.assertIn(field, obj)
                self.assertIsInstance(obj['summary'], str)
                self.assertTrue(obj['summary'].strip())
                self.assertIsInstance(obj['actions'], list)
                self.assertIsInstance(obj['links'], list)

    def test_a_task_tells_its_state_in_one_sentence(self):
        self.assertIn('wartet auf deine Freigabe', desk_objects.task_object(compact(pending_gates=1))['summary'])
        self.assertIn('Schritt 2 von 3', desk_objects.task_object(compact())['summary'])
        self.assertEqual(desk_objects.task_object(compact(phase='COMPLETE'))['state'], 'fertig')
        self.assertIn('Logbuch', desk_objects.task_object(compact(phase='FAILED'))['summary'])

    def test_a_task_with_only_a_plan_is_not_called_done(self):
        # 28.10.2026: „Erstelle mir ein Master-Chat-Fenster“ – kein Werkzeug, nur result.txt als Plan, und die Shell sagte „fertig“
        plan_only = desk_objects.task_object(compact(phase='COMPLETE', qualification='ARTIFACT_ONLY'))
        self.assertEqual(plan_only['state'], 'nur Plan')
        self.assertIn('nicht ausgeführt', plan_only['summary'])
        self.assertNotIn('fertig', plan_only['summary'])
        self.assertEqual(desk_objects.task_object(compact(phase='COMPLETE', qualification='VERIFIED_INVENTORY'))['state'], 'fertig')
        from guppi_runtime.desk import intents
        missions = {'M-1': compact(phase='COMPLETE', status='closed', qualification='ARTIFACT_ONLY')}
        self.assertEqual(intents.state_of({'tasks': ['M-1']}, missions)[0], 'nur Plan')

    def test_every_phase_the_runtime_knows_has_a_german_word(self):
        """Sonst steht Maschinensprache im Satz des Captains ('candidate_review'), und der Satz ist der Kern von Regel 6."""
        from guppi_runtime.core.mission import ALLOWED
        phases = set(ALLOWED) | {p for targets in ALLOWED.values() for p in targets}
        self.assertEqual(sorted(phases - set(desk_objects.PHASE_WORD)), [])
        self.assertIn('Kandidat liegt vor', desk_objects.task_object(compact(phase='CANDIDATE_REVIEW'))['summary'])

    def test_a_waiting_task_points_at_the_decision(self):
        links = desk_objects.task_object(compact(pending_gates=1))['links']
        self.assertEqual(links[0]['type'], 'decision')

    def test_a_candidate_knows_where_it_stands(self):
        plan = {'steps': [{'binding': {'inputs': {'changes': [{'path': 'app.py', 'content': 'x = 1\n'}]}}}]}
        proposed = desk_objects.candidate_object({'identity': {'mission_id': 'M-1'}, 'plan': plan, 'execution': {}})
        self.assertEqual(proposed['state'], 'vorgeschlagen')
        self.assertEqual(proposed['files'], [{'path': 'app.py', 'bytes': 6}])
        applied = desk_objects.candidate_object({'identity': {'mission_id': 'M-1'}, 'plan': plan,
                                                 'execution': {'candidate_acceptance': {'status': 'APPLIED', 'completed': ['app.py']}}})
        self.assertEqual(applied['state'], 'übernommen')
        stuck = desk_objects.candidate_object({'identity': {'mission_id': 'M-1'}, 'plan': plan,
                                               'execution': {'candidate_acceptance': {'status': 'REVIEW_REQUIRED'}}})
        self.assertEqual(stuck['state'], 'braucht Durchsicht')
        self.assertIn('nichts weiter tun', stuck['summary'])
        none = desk_objects.candidate_object({'identity': {'mission_id': 'M-1'}, 'plan': {}, 'execution': {}})
        self.assertEqual(none['state'], 'keiner')


class Verbs(unittest.TestCase):
    def test_a_verb_is_offered_only_in_the_state_it_fits(self):
        ready = desk_objects.task_object(compact(phase='READY'))
        running = desk_objects.task_object(compact(phase='EXECUTE'))
        self.assertEqual([v['verb'] for v in desk_actions.offered(ready)], ['ausfuehren'])
        self.assertEqual(desk_actions.offered(running), [])

    def test_taking_over_is_not_offered_before_the_tests_ran(self):
        plan = {'steps': [{'binding': {'inputs': {'changes': [{'path': 'app.py', 'content': 'x\n'}]}}}]}
        mission = {'identity': {'mission_id': 'M-1'}, 'plan': plan, 'execution': {}}
        untested = desk_objects.candidate_object(mission, report={'ready_for_merge': False})
        self.assertEqual(sorted(v['verb'] for v in desk_actions.offered(untested)), ['nachpruefen', 'testen'])
        self.assertIn('Übernehmen geht erst', untested['summary'])

    def test_the_dangerous_verbs_say_that_they_need_the_captain(self):
        plan = {'steps': [{'binding': {'inputs': {'changes': [{'path': 'app.py', 'content': 'x\n'}]}}}]}
        obj = desk_objects.candidate_object({'identity': {'mission_id': 'M-1'}, 'plan': plan, 'execution': {}},
                                            report={'ready_for_merge': True})
        offered = {v['verb']: v for v in desk_actions.offered(obj)}
        self.assertEqual(sorted(offered), ['nachpruefen', 'testen', 'uebernehmen'])
        self.assertTrue(offered['uebernehmen']['needs_gate'])
        self.assertIn('gesichert', offered['uebernehmen']['confirm'])
        self.assertFalse(offered['testen']['needs_gate'])

    def test_a_verb_that_is_not_offered_does_not_run(self):
        calls = []

        class Hub:
            def run_mission(self, payload):
                calls.append(payload)
                return {'status': 'ran'}
        running = desk_objects.task_object(compact(phase='EXECUTE'))
        with self.assertRaises(ValueError):
            desk_actions.run(Hub(), 'task', 'M-1', 'ausfuehren', {}, lookup=lambda k, i: running)
        self.assertEqual(calls, [], 'the hub must not be called at all')

    def test_unknown_types_and_verbs_are_refused(self):
        ready = desk_objects.task_object(compact(phase='READY'))
        for kind, verb in (('raumschiff', 'ausfuehren'), ('task', 'fliegen')):
            with self.subTest(kind + '/' + verb):
                with self.assertRaises(ValueError):
                    desk_actions.run(None, kind, 'M-1', verb, {}, lookup=lambda k, i: ready)

    def test_an_object_that_is_gone_is_not_acted_on(self):
        with self.assertRaises(ValueError):
            desk_actions.run(None, 'task', 'M-weg', 'ausfuehren', {}, lookup=lambda k, i: desk_objects.not_found('task', i))


class ThroughTheHub(unittest.TestCase):
    """Derselbe Weg wie in der Oberfläche: Objekt lesen, Verb ausführen, Zustand hat sich geändert."""

    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-obj-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        project = self.hub.new_project({'name': 'Prüfprojekt'})
        self.mission = self.hub.create_chat_mission({'intent': 'Create a GUPPI demo artifact', 'project_id': project['project_id']})['mission']['mission_id']

    def test_a_task_runs_through_the_one_action_route(self):
        obj = self.hub.object_view('task', self.mission)
        self.assertEqual(obj['state'], 'bereit')
        self.assertIn('ausfuehren', [a['verb'] for a in obj['actions']])
        out = self.hub.act({'type': 'task', 'id': self.mission, 'verb': 'ausfuehren'})
        self.assertEqual(out['status'], 'done')
        # ohne passendes Werkzeug schreibt die Runtime nur ein Plan-Artefakt (ARTIFACT_ONLY) – das heißt „nur Plan“, nicht „fertig“
        self.assertEqual(self.hub.object_view('task', self.mission)['state'], 'nur Plan')
        self.assertIn('UIX_ACTION', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_the_same_verb_is_refused_once_the_state_moved_on(self):
        self.hub.act({'type': 'task', 'id': self.mission, 'verb': 'ausfuehren'})
        with self.assertRaises(ValueError):
            self.hub.act({'type': 'task', 'id': self.mission, 'verb': 'ausfuehren'})

    def test_the_list_of_a_type_carries_the_same_shape(self):
        view = self.hub.objects_view({'type': 'task'})
        self.assertEqual(view['type'], 'task')
        self.assertTrue(view['items'])
        for field in SHAPE:
            self.assertIn(field, view['items'][0])

    def test_an_unknown_type_is_refused(self):
        with self.assertRaises(ValueError):
            self.hub.objects_view({'type': 'raumschiff'})


class CandidateThroughTheHub(unittest.TestCase):
    """Ein echter Kandidat: Diff, Bericht und die Verben, die er in seinem Zustand hergibt."""

    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-cand-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        rt = self.hub.runtime
        policy = rt.sandbox.policy()
        policy['target_qualified'] = False
        rt.sandbox.config_path = Path(self.tmp.name) / 'unqualified-sandbox.yaml'
        rt.sandbox.config_path.write_text(yaml.safe_dump({'sandbox': policy}), encoding='utf-8')
        folder = rt.filesystem_tool.root / 'demo'
        folder.mkdir(parents=True, exist_ok=True)
        self.old = 'def greet(name):\n    return name\n'
        self.new = 'def greet(name):\n    return "Hallo " + name\n'
        (folder / 'app.py').write_bytes(self.old.encode('utf-8'))      # Bytes: write_text würde unter Windows \r\n schreiben und den Hash brechen
        request = {'project_path': 'demo', 'files': ['app.py'],
                   'changes': [{'path': 'app.py', 'expected_sha256': hashlib.sha256(self.old.encode()).hexdigest(), 'content': self.new}]}
        mission = rt.brain.create_mission('Ändere Code als Kandidat', inputs=request)
        self.mission = rt.brain.run(mission['identity']['mission_id'])['identity']['mission_id']

    def test_the_candidate_shows_the_old_and_the_new_text(self):
        diff = self.hub.candidate_diff({'mission_id': self.mission})
        self.assertEqual(len(diff['files']), 1)
        self.assertEqual(diff['files'][0]['before'], self.old)
        self.assertEqual(diff['files'][0]['after'], self.new)
        self.assertIsNone(diff['files'][0]['note'])
        self.assertTrue(diff['unified'] and '+++ candidate/app.py' in diff['unified'][0])

    def test_the_report_never_calls_an_untested_candidate_green(self):
        report = self.hub.candidate_report({'mission_id': self.mission})
        self.assertTrue(report['exists'])
        self.assertFalse(report['tests_executed'])
        self.assertFalse(report['ready_for_merge'])
        self.assertIn('nicht getestet', report['qualification_text'])
        self.assertEqual(report['static_checks'][0]['check'], 'PYTHON_SYNTAX_PASS')

    def test_the_task_points_at_its_candidate(self):
        links = self.hub.object_view('task', self.mission)['links']
        self.assertEqual(links[0]['type'], 'candidate')
        self.assertEqual(links[0]['id'], self.mission)

    def test_an_untested_candidate_cannot_be_taken_over_at_all(self):
        obj = self.hub.object_view('candidate', self.mission)
        self.assertEqual(obj['state'], 'vorgeschlagen')
        self.assertFalse(obj['qualified'])
        self.assertNotIn('uebernehmen', [a['verb'] for a in obj['actions']],
                         'die Runtime würde es ablehnen (bound_test_commands_required) – dann bietet es die Oberfläche auch nicht an')
        with self.assertRaises(ValueError):
            self.hub.act({'type': 'candidate', 'id': self.mission, 'verb': 'uebernehmen'})
        self.assertEqual((Path(self.hub.runtime.filesystem_tool.root) / 'demo' / 'app.py').read_text(encoding='utf-8'), self.old,
                         'ohne Freigabe wird keine Datei angefasst')

    def test_a_report_for_a_mission_without_one_says_so(self):
        other = self.hub.create_chat_mission({'intent': 'Nur reden'})['mission']['mission_id']
        self.assertFalse(self.hub.candidate_report({'mission_id': other})['exists'])


if __name__ == '__main__':
    unittest.main()
