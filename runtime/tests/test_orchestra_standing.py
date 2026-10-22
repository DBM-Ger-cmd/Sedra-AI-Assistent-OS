"""Dauerfreigabe am Desk (Spec 1, ORC-15, D1.4, G2-S1-13; G4-Entscheidung HALT 1 A mit Auflage, Captain 22.10.2026; S1.H7).

Das Verb `dauerfreigabe` beantragt mit der Art `standing` und genau der Bindung, die `guard.grant_standing` nachbaut. Nach der
Freigabe prüft `gated.decide` den Token für diese eine Art nicht selbst; der Applier gibt ihn genau einmal an den Guard. Ist der
Agent seit dem Antrag anders (Fingerabdruck), endet der Antrag mit `binding_stale` und der Token bleibt unverbraucht; lehnt der Guard
ab, endet er mit dessen Grund. Der Spiegel `standing_approvals` folgt dem Guard; `widerrufen` braucht kein Gate."""
import json
import unittest
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.core.request_binding import digest
from guppi_runtime.desk import gated
from guppi_runtime.orchestra import org, service
from test_orchestra_desk import Desk


def later(now, days):
    from datetime import datetime, timedelta
    return (datetime.strptime(now, '%Y-%m-%dT%H:%M:%SZ') + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


class Standing(Desk):
    def setUp(self):
        super().setUp()
        self.now = service.utc_now()                     # der Guard prüft den Ablauf gegen die echte Uhr
        self.orch._clock = lambda: self.now

    def tokens(self):
        return json.loads(self.hub.runtime.guard.token_store_path.read_text(encoding='utf-8'))

    def request(self, **args):
        out = self.act('agent', 'A-3', 'dauerfreigabe', **args)
        mid = out['result']['decision_id'].split(':', 1)[1]
        return out, self.hub.runtime.missions.load(mid)['human_gates']['pending']

    def verbs(self, aid='A-3'):
        return [a['verb'] for a in self.hub.objects_view({'type': 'agent', 'id': aid})['actions']]

    def test_the_request_binds_exactly_what_the_guard_rebuilds(self):
        self.assertIn('dauerfreigabe', self.verbs())
        self.assertNotIn('dauerfreigabe', self.verbs('A-UA'), 'Stufe 4: keine Dauerfreigabe')
        out, [gate] = self.request(tage=3, laeufe=10)
        agent = self.row('agents', 'id', 'A-3')
        binding = {'art': 'standing', 'agent_id': 'A-3', 'fingerprint': org.fingerprint(agent), 'max_uses': 10, 'expires_at': later(self.now, 3)}
        self.assertEqual((gate['request']['exact_action'], gate['request']['targets']), ('wake_agent', ['agent:A-3']))
        self.assertEqual(gate['request']['request_digest'], digest(binding))
        decision = next(d for d in self.hub.decisions_view()['items'] if d['id'] == out['result']['decision_id'])
        self.assertEqual((decision['kind'], decision['agent_id'], decision['title']), ('request:standing', 'A-3', 'Dauerfreigabe für Prüfer: 10 Läufe, 3 Tage'))
        with self.assertRaisesRegex(ValueError, 'args_invalid'):
            self.act('agent', 'A-3', 'dauerfreigabe', tage=31)

    def test_approval_grants_once_through_the_guard_and_mirrors(self):
        out, [gate] = self.request()
        guard = self.hub.runtime.guard
        with mock.patch.object(guard, 'authorize', wraps=guard.authorize) as authorize:
            result = self.decide(out)
        self.assertEqual(authorize.call_count, 0, 'decide prüft den Token für standing nicht selbst')
        self.assertEqual(result['status'], 'applied')
        once = [t for t in self.tokens().values() if t.get('gate_id') == gate['gate_id'] and t.get('kind') == 'once']
        self.assertEqual([t['status'] for t in once], ['used'], 'genau einmal verbraucht – vom Guard')
        token = guard.standing_status('A-3')
        self.assertEqual((token['status'], token['limits']['max_uses']), ('active', 50))
        mirror = self.row('standing_approvals', 'agent_id', 'A-3')
        self.assertEqual((mirror['token_id'], mirror['status'], mirror['uses'], mirror['max_uses']), (token['token_id'], 'aktiv', 0, 50))
        agent = self.hub.objects_view({'type': 'agent', 'id': 'A-3'})
        self.assertEqual(agent['dauerfreigabe'], {'aktiv': True, 'laeufe': 0, 'max_laeufe': 50, 'bis': token['validity']['expires_at']})
        self.assertEqual(self.verbs()[-1:], ['widerrufen'])
        self.assertNotIn('dauerfreigabe', self.verbs())

    def test_a_changed_agent_is_stale_and_the_token_stays_unspent(self):
        out, [gate] = self.request()
        self.db.execute("UPDATE agents SET permission_level = 1, revision = revision + 1 WHERE id = 'A-3'")
        self.assertEqual(self.decide(out), {'status': 'binding_stale', 'result': None})
        once = [t for t in self.tokens().values() if t.get('gate_id') == gate['gate_id']]
        self.assertEqual([t['status'] for t in once], ['active'])
        self.assertIsNone(self.hub.runtime.guard.standing_status('A-3'))

    def test_a_refusal_of_the_guard_ends_with_its_reason(self):
        agent = self.row('agents', 'id', 'A-3')
        binding = {'art': 'standing', 'agent_id': 'A-3', 'fingerprint': org.fingerprint(agent), 'max_uses': 51, 'expires_at': later(self.now, 3)}
        req = gated.request(self.hub, 'standing', 'wake_agent', 'agent:A-3', binding, exact=True, describe='zu viele Läufe')
        result = self.hub.decide({'id': 'request:' + req['mission_id'], 'way': 'freigeben_und_anwenden'})['result']
        self.assertEqual(result, {'status': 'guard_refused', 'reason': 'standing_uses_out_of_range', 'result': None})
        m = self.hub.runtime.missions.load(req['mission_id'])
        self.assertEqual((m['lifecycle']['status'], m['result']['error']), ('closed', 'guard_refused:standing_uses_out_of_range'))
        self.assertEqual(self.audit('DESK_GATED_REFUSED')[0]['reason'], 'standing_uses_out_of_range')

    def test_widerrufen_without_a_gate(self):
        self.decide(self.request()[0])
        out = self.act('agent', 'A-3', 'widerrufen')
        self.assertEqual((out['needs_gate'], out['result']['widerrufen']), (False, 1))
        self.assertEqual(self.row('standing_approvals', 'agent_id', 'A-3')['status'], 'widerrufen')
        self.assertIsNone(self.hub.objects_view({'type': 'agent', 'id': 'A-3'})['dauerfreigabe'])


    def test_any_other_kind_still_has_its_token_checked_by_decide(self):
        """Auflage HALT 1: eine andere Art bekommt den Token nicht; decide verbraucht ihn vor dem Applier."""
        seen = []

        def do(hub, binding):
            seen.append([t['status'] for t in self.tokens().values() if t.get('mission_id') == mid])
            return 'ok'
        gated.register_applier('auflage_test', do)
        self.addCleanup(gated._APPLIERS.pop, 'auflage_test', None)
        mid = gated.request(self.hub, 'auflage_test', 'wake_agent', 'agent:A-3', {'op': 'x'})['mission_id']
        self.assertEqual(self.hub.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})['result']['status'], 'applied')
        self.assertEqual(seen, [['used']])


class OnlyStanding(unittest.TestCase):
    """Auflage zu HALT 1: `spends_token` gilt fest im Code nur für `standing`; kein Applier kann es für eine andere Art bekommen."""

    def test_fixed_in_code(self):
        import inspect
        self.assertEqual(gated.SPENDS_TOKEN, frozenset({'standing'}))
        self.assertNotIn('spends_token', inspect.signature(gated.register_applier).parameters)
        self.assertNotIn('spends_token', inspect.signature(gated.request).parameters)


if __name__ == '__main__':
    unittest.main()
