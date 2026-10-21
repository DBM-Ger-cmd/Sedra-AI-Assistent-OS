"""`desk/gated.py` mit mehreren Gates, Applier-Register, `decide`, `reject`, `pending` und `binding_stale` (Spec 1, D1.3.2, D1.3.3,
S1.H5, G2-S1-08) und der zweiten, generischen Änderung an `uix_server.decide`/`_open_requests` (G2-S1-09).

Ein Antrag mit zwei Gates ist eine Entscheidung; „Freigeben und anwenden“ gibt beide frei, prüft beide Token und ruft dann genau
einmal den Applier mit der gebundenen Bindung. Nach einem Neustart steht der Antrag wieder im Posteingang und ist anwendbar."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import gated
from guppi_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
KIND = 'gated_test'
GATES = [('set_budget', 'agent:A1'), ('resume_agent', 'agent:A1')]


def audit_payloads(hub, event):
    lines = hub.runtime.audit.path.read_text(encoding='utf-8').splitlines()
    return [e.get('payload') for e in map(json.loads, filter(str.strip, lines)) if e.get('event_type') == event]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='desk-gated-s1-')
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        self.hub = self.open_hub()
        self.applied, self.rejected = [], []
        self.stale = False
        gated.register_applier(KIND, self.do, on_reject=self.on_reject)
        self.addCleanup(gated._APPLIERS.pop, KIND, None)

    def open_hub(self):
        hub = UIXHub(self.project, ARCH)
        self.addCleanup(hub.close)
        return hub

    def do(self, hub, binding):
        if self.stale:
            raise ValueError('binding_stale')
        self.applied.append(binding)
        return {'ok': binding['op']}

    def on_reject(self, hub, binding):
        self.rejected.append(binding)
        return 'abgelehnt'

    def request(self, binding=None, gates=GATES):
        return gated.request(self.hub, KIND, gates[0][0], gates[0][1], binding or {'op': 'budget', 'grenze': 5000, 'describe': 'Budget A1'},
                             gates=gates)

    def decision(self, mid, hub=None):
        return next((d for d in (hub or self.hub).decisions_view()['items'] if d['id'] == 'request:' + mid), None)


class SeveralGates(Base):
    def test_two_gates_are_one_decision_with_the_agent(self):
        req = self.request()
        mid = req['mission_id']
        m = self.hub.runtime.missions.load(mid)
        self.assertEqual([(g['request']['exact_action'], g['request']['targets']) for g in m['human_gates']['pending']],
                         [('set_budget', ['agent:A1']), ('resume_agent', ['agent:A1'])])
        self.assertEqual(len({g['request']['request_digest'] for g in m['human_gates']['pending']}), 1, 'eine Bindung für alle Gates')
        self.assertEqual(m['context'][gated.CONTEXT]['gates'], [list(g) for g in GATES])
        items = [d for d in self.hub.decisions_view()['items'] if d['mission_id'] == mid]
        self.assertEqual([d['id'] for d in items], ['request:' + mid], 'ein Antrag, eine Entscheidung')
        d = items[0]
        self.assertEqual((d['kind'], d['agent_id'], d['ways'], d['apply']), ('request:' + KIND, 'A1', ['freigeben_und_anwenden', 'ablehnen'], None))
        self.assertEqual(d['binding']['op'], 'budget')
        self.assertEqual(self.applied, [])

    def test_approve_and_apply_runs_the_binding_once(self):
        mid = self.request()['mission_id']
        out = self.hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
        self.assertEqual(out['result'], {'status': 'applied', 'result': {'ok': 'budget'}})
        self.assertEqual([b['grenze'] for b in self.applied], [5000])
        self.assertEqual(self.applied[0]['agent_id'], 'A1')
        m = self.hub.runtime.missions.load(mid)
        self.assertEqual((m['human_gates']['pending'], len(m['human_gates']['resolved']), m['lifecycle']['status']), ([], 2, 'closed'))
        self.assertNotIn('approval_tokens', m['execution'])
        self.assertEqual(audit_payloads(self.hub, 'DESK_GATED_APPLIED'),
                         [{'kind': KIND, 'gates': [list(g) for g in GATES], 'target': 'agent:A1', 'agent_id': 'A1'}])
        self.assertEqual(len(audit_payloads(self.hub, 'CAPTAIN_GATE_APPROVED')), 2)
        self.assertIsNone(self.decision(mid))
        with self.assertRaisesRegex(ValueError, 'unknown_decision'):
            self.hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
        self.assertEqual(len(self.applied), 1)

    def test_reject_denies_every_gate_and_runs_nothing(self):
        mid = self.request()['mission_id']
        out = self.hub.decide({'id': 'request:' + mid, 'way': 'ablehnen'})
        self.assertEqual(out['result'], {'status': 'rejected', 'result': 'abgelehnt'})
        self.assertEqual((self.applied, [b['op'] for b in self.rejected]), ([], ['budget']))
        m = self.hub.runtime.missions.load(mid)
        self.assertEqual([g['resolution']['decision'] for g in m['human_gates']['resolved']], ['DENY', 'DENY'])
        self.assertEqual(m['lifecycle']['status'], 'closed')
        self.assertEqual(len(audit_payloads(self.hub, 'DESK_GATED_REJECTED')), 1)
        self.assertEqual(audit_payloads(self.hub, 'CAPTAIN_GATE_APPROVED'), [])
        self.assertIsNone(self.decision(mid))

    def test_a_stale_binding_ends_the_request_without_effect(self):
        mid = self.request()['mission_id']
        self.stale = True
        out = self.hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
        self.assertEqual(out['result'], {'status': 'binding_stale', 'result': None})
        self.assertEqual(self.applied, [])
        m = self.hub.runtime.missions.load(mid)
        self.assertEqual((m['lifecycle']['status'], m['result']['error']), ('closed', 'binding_stale'))
        self.assertEqual(audit_payloads(self.hub, 'DESK_GATED_STALE'),
                         [{'kind': KIND, 'gates': [list(g) for g in GATES], 'target': 'agent:A1', 'agent_id': 'A1'}])
        self.assertEqual(audit_payloads(self.hub, 'DESK_GATED_APPLIED'), [])
        self.assertIsNone(self.decision(mid))

    def test_a_changed_binding_is_refused_and_nothing_runs(self):
        mid = self.request()['mission_id']
        m = self.hub.runtime.missions.load(mid)
        m['context'][gated.CONTEXT]['binding']['grenze'] = 10 ** 9
        self.hub.runtime.missions.save(m)
        with self.assertRaisesRegex(ValueError, 'captain_approval_invalid'):
            self.hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
        self.assertEqual(self.applied, [])
        self.assertEqual(audit_payloads(self.hub, 'DESK_GATED_APPLIED'), [])

    def test_spec0_apply_refuses_a_request_with_several_gates(self):
        mid = self.request()['mission_id']
        with self.assertRaisesRegex(ValueError, 'several_gates_need_decide'):
            gated.apply(self.hub, mid, self.applied.append)


class OneGate(Base):
    def test_a_single_gate_request_goes_the_same_way(self):
        req = self.request({'op': 'wecken', 'describe': 'A2 wecken'}, gates=[('wake_agent', 'agent:A2')])
        self.assertEqual(req['binding']['agent_id'], 'A2')
        out = self.hub.decide({'id': 'request:' + req['mission_id'], 'way': 'freigeben_und_anwenden'})
        self.assertEqual(out['result']['result'], {'ok': 'wecken'})

    def test_agent_id_only_for_the_agent_actions(self):
        req = gated.request(self.hub, KIND, 'echo_test_action', 'agent:A3', {'op': 'x'})
        self.assertNotIn('agent_id', req['binding'])
        req = gated.request(self.hub, KIND, 'set_org', 'agent:A3', {'op': 'x', 'agent_id': 'A9'})
        self.assertEqual(req['binding']['agent_id'], 'A9', 'eine gesetzte agent_id bleibt')

    def test_bad_gates_are_refused(self):
        for gates in ([], [('set_budget',)], [('set_budget', '')]):
            with self.subTest(gates):
                with self.assertRaisesRegex(ValueError, 'gates_invalid'):
                    gated.request(self.hub, KIND, 'set_budget', 'agent:A1', {'op': 'x'}, gates=gates)


class AfterRestart(Base):
    def test_the_request_is_back_in_the_inbox_and_can_be_applied(self):
        mid = self.request()['mission_id']
        self.hub.close()
        hub = self.open_hub()
        d = self.decision(mid, hub)
        self.assertIsNotNone(d, 'nach dem Neustart wieder im Posteingang')
        self.assertEqual((d['kind'], d['agent_id']), ('request:' + KIND, 'A1'))
        self.assertEqual([x['id'] for x in hub.decisions_view()['items']].count('request:' + mid), 1)
        out = hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
        self.assertEqual(out['result']['status'], 'applied')
        self.assertEqual(len(self.applied), 1)
        self.assertIsNone(self.decision(mid, hub))

    def test_pending_skips_known_and_decided_missions(self):
        mid = self.request()['mission_id']
        self.assertEqual([r['mission_id'] for r in gated.pending(self.hub, set())], [mid])
        self.assertEqual(gated.pending(self.hub, {mid}), [])
        self.hub.decide({'id': 'request:' + mid, 'way': 'ablehnen'})
        self.assertEqual(gated.pending(self.hub, set()), [])


class Register(unittest.TestCase):
    def tearDown(self):
        gated._APPLIERS.pop('reg_test', None)

    def test_register_and_look_up(self):
        def do(hub, binding):
            return None
        self.assertIsNone(gated.applier('reg_test'))
        gated.register_applier('reg_test', do)
        gated.register_applier('reg_test', do)            # derselbe Applier aus einem zweiten Hub: kein Fehler
        self.assertIs(gated.applier('reg_test'), do)
        with self.assertRaisesRegex(ValueError, 'applier_already_registered'):
            gated.register_applier('reg_test', lambda h, b: None)

    def test_only_before_the_registry_is_frozen(self):
        from guppi_runtime.desk import builtin_kinds
        reg = builtin_kinds.new_registry()
        reg.freeze()
        with self.assertRaisesRegex(ValueError, 'kinds_frozen'):
            gated.register_applier('reg_test', lambda h, b: None, registry=reg)
        self.assertIsNone(gated.applier('reg_test'))


class WithoutApplier(unittest.TestCase):
    """Eine Art ohne Applier (Spec 0) bleibt beim alten Weg: „Freigeben und anwenden“ sagt `decision_cannot_be_applied`."""

    def test_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='desk-gated-s0-') as tmp:
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                mid = gated.request(hub, 'echo_test', 'echo_test_action', 'echo:eins', {'text': 'hallo'})['mission_id']
                with self.assertRaisesRegex(ValueError, 'decision_cannot_be_applied'):
                    hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
                with self.assertRaisesRegex(ValueError, 'decision_cannot_be_applied'):
                    gated.decide(hub, mid)
            finally:
                hub.close()


if __name__ == '__main__':
    unittest.main()
