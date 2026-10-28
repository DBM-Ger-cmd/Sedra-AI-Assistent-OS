"""Die Live-Zeilen (desk/live.py, Cockpit-Regel 5).

Der Grundsatz dieses Moduls ist, dass es nichts erfindet: jede Zeile hat ihre Entsprechung im Missionsdatensatz oder im Audit.
Diese Tests halten das fest – und dass die Nummerierung stabil bleibt, denn darauf verlässt sich der Ereignisstrom (`since`)."""
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import live


def mission(**kw):
    base = {
        'identity': {'mission_id': 'M-1', 'created_at': '2026-10-14T18:00:00+00:00'},
        'captain_intent': {'original': 'CSV-Parser bauen'},
        'lifecycle': {'phase': 'EXECUTE'},
        'plan': {'steps': [{'id': 'STEP-1', 'description': 'Kandidat vorbereiten'}, {'id': 'STEP-2', 'description': 'Tests ausführen'}]},
        'execution': {'step_journal': {'steps': [
            {'id': 'STEP-1', 'status': 'COMPLETED', 'attempts': 1,
             'started_at': '2026-10-14T18:00:01+00:00', 'finished_at': '2026-10-14T18:00:02+00:00',
             'result': {'status': 'completed', 'artifacts': [{'path': 'workspace/M-1/candidate-report.json'}]}},
            {'id': 'STEP-2', 'status': 'RUNNING', 'attempts': 1, 'started_at': '2026-10-14T18:00:03+00:00'},
        ]}},
        'human_gates': {'pending': []},
    }
    base.update(kw)
    return base


class Lines(unittest.TestCase):
    def test_a_run_reads_like_a_protocol(self):
        rows = live.lines(mission())
        text = [r['kind'] + '|' + r['line'] for r in rows]
        self.assertEqual(text[0], 'note|Aufgabe angelegt: CSV-Parser bauen')
        self.assertIn('step|Schritt 1: Kandidat vorbereiten', text)
        self.assertTrue(any(t.startswith('ok|fertig in 1.0 s') for t in text), text)
        self.assertIn('out|candidate-report.json', text)
        self.assertIn('step|Schritt 2: Tests ausführen – läuft', text)

    def test_the_numbers_are_dense_and_ordered(self):
        rows = live.lines(mission())
        self.assertEqual([r['n'] for r in rows], list(range(1, len(rows) + 1)))
        stamps = [r['at'] for r in rows if r['at']]
        self.assertEqual(stamps, sorted(stamps), 'die Zeilen stehen in der Reihenfolge, in der sie entstanden sind')

    def test_only_the_audit_events_that_matter_become_lines(self):
        events = [
            {'event_type': 'MESSAGE_SENT', 'mission_id': 'M-1', 'timestamp': '2026-10-14T18:00:01+00:00'},
            {'event_type': 'MISSION_STATE_CHANGED', 'mission_id': 'M-1', 'timestamp': '2026-10-14T18:00:01+00:00'},
            {'event_type': 'CAPTAIN_GATE_APPROVED', 'mission_id': 'M-1', 'timestamp': '2026-10-14T18:00:04+00:00'},
            {'event_type': 'GUARD_BLOCKED', 'mission_id': 'M-2', 'timestamp': '2026-10-14T18:00:05+00:00'},
        ]
        lines = [r['line'] for r in live.lines(mission(), events)]
        self.assertIn('freigegeben', lines)
        self.assertNotIn('message sent', lines)
        self.assertNotIn('Guard hat das abgelehnt', lines, 'ein Ereignis einer anderen Aufgabe gehört nicht hierher')

    def test_a_waiting_gate_is_a_line_of_its_own(self):
        waiting = mission(human_gates={'pending': [{'gate_id': 'HG-1', 'created_at': '2026-10-14T18:00:04+00:00',
                                                    'request': {'exact_action': 'candidate_accept', 'targets': ['app.py']}}]})
        rows = [r for r in live.lines(waiting) if r['kind'] == 'gate']
        self.assertEqual(len(rows), 1)
        self.assertIn('wartet auf dich', rows[0]['line'])
        self.assertIn('app.py', rows[0]['line'])

    def test_a_failed_step_says_why_and_is_marked_bad(self):
        broken = mission(execution={'step_journal': {'steps': [
            {'id': 'STEP-1', 'status': 'FAILED', 'attempts': 3, 'started_at': '2026-10-14T18:00:01+00:00',
             'finished_at': '2026-10-14T18:00:02+00:00', 'result': {'reason_code': 'MODEL_UNAVAILABLE'}}]}},
            lifecycle={'phase': 'FAILED'})
        rows = live.lines(broken)
        bad = [r['line'] for r in rows if r['kind'] == 'bad']
        self.assertTrue(any('MODEL_UNAVAILABLE' in line for line in bad), bad)
        self.assertEqual(rows[-1]['line'], 'Aufgabe fehlgeschlagen.')
        self.assertIn('3 Versuche für diesen Schritt', [r['line'] for r in rows])

    def test_a_plan_artifact_alone_is_not_reported_as_done(self):
        only_plan = mission(lifecycle={'phase': 'COMPLETE'}, result={'kind': 'planning_artifact', 'qualification': 'ARTIFACT_ONLY', 'accepted': False})
        rows = live.lines(only_plan)
        self.assertEqual(rows[-1]['kind'], 'bad')
        self.assertIn('nicht ausgeführt', rows[-1]['line'])
        self.assertNotIn('Aufgabe fertig.', [r['line'] for r in rows])
        done = mission(lifecycle={'phase': 'COMPLETE'}, result={'qualification': 'VERIFIED_INVENTORY'})
        self.assertEqual(live.lines(done)[-1]['line'], 'Aufgabe fertig.')

    def test_the_take_over_and_its_rollback_are_told(self):
        applied = mission(execution={'candidate_acceptance': {'status': 'APPLIED', 'completed': ['app.py'],
                                                              'finished_at': '2026-10-14T18:00:09+00:00',
                                                              'plan': {'files': [{'path': 'app.py'}]}}})
        self.assertIn('Übernommen: 1 Datei(en) geschrieben.', [r['line'] for r in live.lines(applied)])
        rolled = mission(execution={'candidate_acceptance': {'status': 'APPLIED', 'completed': ['app.py'],
                                                             'rollback': {'status': 'ROLLED_BACK', 'finished_at': '2026-10-14T18:00:11+00:00'}}})
        self.assertIn('Zurückgenommen – die alten Dateien stehen wieder.', [r['line'] for r in live.lines(rolled)])

    def test_a_stuck_take_over_is_not_glossed_over(self):
        stuck = mission(execution={'candidate_acceptance': {'status': 'REVIEW_REQUIRED', 'error': 'written_file_verification_failed',
                                                            'finished_at': '2026-10-14T18:00:09+00:00', 'completed': []}})
        bad = [r['line'] for r in live.lines(stuck) if r['kind'] == 'bad']
        self.assertTrue(any('steckengeblieben' in line for line in bad), bad)

    def test_the_tail_is_what_the_stream_sends_on(self):
        rows = live.lines(mission())
        self.assertEqual(live.tail(rows, 0)[0]['n'], 1)
        rest = live.tail(rows, 3)
        self.assertEqual([r['n'] for r in rest], [r['n'] for r in rows if r['n'] > 3])
        self.assertEqual(live.tail(rows, len(rows)), [])
        self.assertEqual(live.signature(rows), len(rows))

    def test_an_empty_mission_still_says_something(self):
        rows = live.lines({'identity': {'mission_id': 'M-9'}, 'plan': {}, 'execution': {}})
        self.assertTrue(rows)
        self.assertIn('Aufgabe angelegt', rows[0]['line'])

    def test_the_stream_only_announces_what_grew(self):
        from guppi_runtime.desk.events import diff
        before = {'missions': [], 'decisions': [], 'model': {}, 'state': 'READY', 'live': {'M-1': 4}}
        same = dict(before)
        self.assertEqual(diff(before, same), [])
        more = dict(before, live={'M-1': 7})
        events = diff(before, more)
        self.assertEqual([n for n, _ in events], ['live.line'])
        self.assertEqual(events[0][1], {'task_id': 'M-1', 'line': '', 'since': 4, 'total': 7})


if __name__ == '__main__':
    unittest.main()
