"""Einstellen eines Agenten (Spec 1, ORC-01, D1.3.1; Entscheidung HALT 3 B, Captain 22.10.2026; S1.H7).

Die AM-Instanz gibt es vorher (eigener AM-Ablauf, hier als Eintrag in der AM-Registry). `einstellen {name, instance_id, reports_to,
budget_tokens}` ist ein Antrag mit Gate `set_org`; ohne Freigabe keine Zeile in `agents`. Nach „Freigeben und anwenden“ liefert
`POST /api/objects {type: agent, id}` Vorgesetzten, Rolle, Stufe und Budget. Rolle und Stufe kommen aus der Vorlage, das
Delegationsrecht nur für `guppi.orchestra.foreman`. Ist die Instanz seit dem Antrag nicht mehr aktiv oder geändert:
`binding_stale`; eine schon vergebene Instanz: `instance_taken`. Abgelehnt bleibt die Instanz stehen (kein Aufräumen)."""
import json
import sqlite3
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.agent_manager.agent_registry import Registry
from test_orchestra_desk import Desk

TEMPLATES = {'guppi.orchestra.foreman': {'role': 'unterarbeiter', 'recipe': 'foreman.local', 'capabilities': [{'side_effect': 'proposal_only'}]},
             'guppi.orchestra.coder': {'role': 'coder', 'capabilities': [{'side_effect': 'read_only'}, {'side_effect': 'reversible_write'}]},
             'leer': {'role': 'x', 'capabilities': []}}


class Hire(Desk):
    def setUp(self):
        super().setUp()
        self.am_path = self.hub.project_root / 'runtime_data' / 'agent_manager' / 'registry.sqlite'
        self.am_path.parent.mkdir(parents=True, exist_ok=True)
        reg = Registry(str(self.am_path))
        try:
            for ref, template in TEMPLATES.items():
                reg.command('cmd-t-' + ref, 'create', 'template', ref, {'template': dict(template, id=ref), 'preview': {'ok': True}, 'digest': 'd-' + ref})
            for iid, ref in (('ins-ua', 'guppi.orchestra.foreman'), ('ins-co', 'guppi.orchestra.coder'), ('ins-leer', 'leer'), ('ins-q', 'guppi.orchestra.coder')):
                reg.command('cmd-' + iid, 'create', 'agent', iid, {'template_ref': ref, 'template_digest': 'd-' + ref, 'lifecycle': 'ACTIVE',
                                                                   'qualification': 'UNVERIFIED', 'admission': {'valid': False, 'revoked': False}})
        finally:
            reg.close()
        self.set_instance('ins-q', lifecycle='QUARANTINED')

    def set_instance(self, iid, **changes):
        db = sqlite3.connect(self.am_path)
        try:
            data = json.loads(db.execute("SELECT data FROM entries WHERE kind = 'agent' AND key = ?", (iid,)).fetchone()[0])
            data.update(changes)
            db.execute("UPDATE entries SET data = ? WHERE kind = 'agent' AND key = ?", (json.dumps(data), iid))
            db.commit()
        finally:
            db.close()

    def hire(self, iid, name='Neu', reports_to='A-UA', budget_tokens=20000):
        return self.act('agent', None, 'einstellen', name=name, instance_id=iid, reports_to=reports_to, budget_tokens=budget_tokens)

    def count(self):
        return self.db.execute('SELECT COUNT(*) FROM agents').fetchone()[0]

    def test_a_request_with_set_org_and_after_approval_the_agent_is_there(self):
        before = self.count()
        out = self.hire('ins-ua', name='Unterarbeiter 2')
        self.assertEqual((out['needs_gate'], out['result']['text']), (True, 'Antrag liegt im Posteingang'))
        self.assertEqual(self.count(), before, 'ohne Freigabe keine Zeile')
        mid = out['result']['decision_id'].split(':', 1)[1]
        gates = self.hub.runtime.missions.load(mid)['human_gates']['pending']
        self.assertEqual([(g['request']['exact_action'], g['request']['targets'][0][:8]) for g in gates], [('set_org', 'agent:A-')])
        decision = next(d for d in self.hub.decisions_view()['items'] if d['id'] == out['result']['decision_id'])
        self.assertEqual(decision['agent_id'], gates[0]['request']['targets'][0][len('agent:'):])
        result = self.decide(out)
        agent = self.hub.objects_view({'type': 'agent', 'id': result['result']['id']})
        self.assertEqual((agent['title'], agent['reports_to'], agent['rolle'], agent['stufe'], agent['can_delegate'], agent['budget']['grenze_token']),
                         ('Unterarbeiter 2', 'A-UA', 'unterarbeiter', 1, 1, 20000))
        row = self.row('agents', 'id', agent['id'])
        self.assertEqual((row['instance_id'], row['template_id'], row['recipe_id'], row['status']), ('ins-ua', 'guppi.orchestra.foreman', 'foreman.local', 'aktiv'))
        self.assertEqual(self.audit('ORC_AGENT_HIRED')[0]['instance_id'], 'ins-ua')

    def test_level_from_the_strongest_effect_and_no_delegation_for_other_templates(self):
        result = self.decide(self.hire('ins-co'))
        row = self.row('agents', 'id', result['result']['id'])
        self.assertEqual((row['role'], row['permission_level'], row['can_delegate']), ('coder', 2, 0))

    def test_instances_that_cannot_be_hired(self):
        cases = {'instance_not_found': 'ins-weg', 'instance_not_active': 'ins-q', 'template_without_effect': 'ins-leer'}
        for code, iid in cases.items():
            with self.subTest(code):
                with self.assertRaisesRegex(ValueError, code):
                    self.hire(iid)
        self.decide(self.hire('ins-co'))
        with self.assertRaisesRegex(ValueError, 'instance_taken'):
            self.hire('ins-co', name='Zweiter')

    def test_a_changed_instance_makes_the_approval_stale(self):
        out = self.hire('ins-co')
        self.set_instance('ins-co', lifecycle='QUARANTINED')
        before = self.count()
        self.assertEqual(self.decide(out), {'status': 'binding_stale', 'result': None})
        self.assertEqual(self.count(), before)
        out = self.hire('ins-ua')
        self.set_instance('ins-ua', template_digest='anders')
        self.assertEqual(self.decide(out)['status'], 'binding_stale')

    def test_two_requests_for_one_instance_only_the_first_hires(self):
        first, second = self.hire('ins-co'), self.hire('ins-co', name='Zwilling')
        self.decide(first)
        with self.assertRaisesRegex(ValueError, 'instance_taken'):
            self.decide(second)

    def test_rejected_leaves_the_instance_alone(self):
        before = self.count()
        self.assertEqual(self.decide(self.hire('ins-co'), 'ablehnen')['status'], 'rejected')
        self.assertEqual(self.count(), before)
        db = sqlite3.connect(self.am_path)
        try:
            self.assertEqual(json.loads(db.execute("SELECT data FROM entries WHERE key = 'ins-co'").fetchone()[0])['lifecycle'], 'ACTIVE')
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
