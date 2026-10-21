"""Dauerfreigabe im Guard (Spec 1, D1.4, ORC-15, Kern-Gate G2-S1-KERN-01): Testliste 1 bis 16.

Eine Dauerfreigabe entsteht nur aus einer verbrauchten Einmal-Freigabe für genau diese Bindung, deckt nur `wake_agent` eines
Agenten, endet mit Ablauf, geändertem Fingerabdruck, Budget-Stopp, letzter Nutzung oder Widerruf und ist über `authorize`/
`check_token` nie nutzbar. Fake-Uhr: `datetime` und `utcnow` im Modul `guard` ersetzt; Token-Speicher in einem Temp-Ordner."""
import json
import multiprocessing
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.core import guard as guard_module
from guppi_runtime.core.audit import AuditLog
from guppi_runtime.core.guard import TOKEN_KEEP_S, Guard

RUNTIME = Path(__file__).resolve().parents[1]
RULES = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT' / 'core' / 'guard' / 'guard_rules.yaml'
START = datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)


def fingerprint(agent_id='A1', **changes):
    fp = {'agent_id': agent_id, 'status': 'aktiv', 'permission_level': 2, 'recipe_id': 'coder.local', 'reports_to': 'A0',
          'budget_tokens': 100000, 'budget_eur_cent': None, 'budget_period': 'gesamt'}
    fp.update(changes)
    return fp


class Clock:
    def __init__(self, now):
        self.now = now
        clock = self

        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock.now if tz is None else clock.now.astimezone(tz)
        self.datetime = FakeDatetime

    def utcnow(self):
        return self.now.isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='guard-standing-')
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = self.dir / 'tokens.json'
        self.audit_path = self.dir / 'audit.jsonl'
        self.clock = Clock(START)
        for name, value in (('datetime', self.clock.datetime), ('utcnow', self.clock.utcnow)):
            patcher = mock.patch.object(guard_module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.guard = self.new_guard()

    def new_guard(self):
        return Guard(RULES, AuditLog(self.audit_path), self.store)

    def events(self, kind):
        if not self.audit_path.exists():
            return []
        rows = [json.loads(line) for line in self.audit_path.read_text(encoding='utf-8').splitlines() if line.strip()]
        return [r['payload'] for r in rows if r['event_type'] == kind]

    def binding(self, agent_id='A1', fp=None, max_uses=50, days=7):
        expires = (self.clock.now + timedelta(days=days)).isoformat()
        return {'art': 'standing', 'agent_id': agent_id, 'fingerprint': fp or fingerprint(agent_id), 'max_uses': max_uses,
                'expires_at': expires}

    def once(self, binding, mission_id='M-REQ', action='wake_agent'):
        gate = self.guard.create_gate(mission_id, action, 'agent:' + binding['agent_id'], request_binding=binding)
        return self.guard.approve(gate)

    def grant(self, binding, token=None, mission_id='M-REQ'):
        token = token if token is not None else self.once(binding, mission_id)
        return self.guard.grant_standing(token, mission_id=mission_id, agent_id=binding['agent_id'], fingerprint=binding['fingerprint'],
                                         max_uses=binding['max_uses'], expires_at=binding['expires_at'])

    def use(self, agent_id='A1', fp=None, stage='ok', run_ref='W-1'):
        return self.guard.authorize_standing(agent_id, fingerprint=fp or fingerprint(agent_id), budget_stage=stage, run_ref=run_ref)


class Grant(Base):
    def test_01_a_valid_single_approval_becomes_a_standing_token(self):
        b = self.binding()
        once = self.once(b)
        out = self.grant(b, once)
        self.assertTrue(out['authorized'])
        token = out['token']
        self.assertEqual((token['kind'], token['status'], token['uses'], token['grants']['action_type'], token['grants']['targets']),
                         ('standing', 'active', 0, 'wake_agent', ['agent:A1']))
        self.assertEqual(token['limits'], {'single_use': False, 'max_uses': 50, 'max_level': 3})
        self.assertTrue(token['token_id'].startswith('STD-'))
        self.assertEqual(json.loads(self.store.read_text(encoding='utf-8'))[once['token_id']]['status'], 'used')
        self.assertEqual(self.events('CAPTAIN_STANDING_GRANTED'),
                         [{'token_id': token['token_id'], 'agent_id': 'A1', 'max_uses': 50, 'expires_at': b['expires_at'], 'level': 2}])

    def test_02_without_a_foreign_or_a_spent_single_approval_there_is_no_standing_token(self):
        b = self.binding()
        self.assertEqual(self.grant(b, token={})['reason'], 'missing_or_inactive_token')
        foreign = self.once(b, mission_id='M-ANDERE')
        self.assertEqual(self.grant(b, token=foreign)['reason'], 'mission_mismatch')
        other_agent = self.once(self.binding('A2'))
        self.assertEqual(self.grant(b, token=other_agent)['reason'], 'target_out_of_scope')
        spent = self.once(b)
        self.assertTrue(self.guard.authorize(spent, mission_id='M-REQ', action='wake_agent', target='agent:A1', request_binding=b)['authorized'])
        self.assertFalse(self.grant(b, token=spent)['authorized'])
        self.assertIsNone(self.guard.standing_status('A1'))
        self.assertEqual(self.events('CAPTAIN_STANDING_GRANTED'), [])
        self.assertEqual(len(self.events('CAPTAIN_STANDING_REFUSED')), 4)

    def test_03_a_binding_other_than_the_one_approved_is_refused(self):
        b = self.binding(max_uses=5)
        once = self.once(b)
        out = self.guard.grant_standing(once, mission_id='M-REQ', agent_id='A1', fingerprint=b['fingerprint'], max_uses=6,
                                        expires_at=b['expires_at'])
        self.assertEqual(out, {'authorized': False, 'reason': 'request_digest_mismatch'})
        self.assertIsNone(self.guard.standing_status('A1'))

    def test_04_level_uses_expiry_and_status_each_have_their_own_reason(self):
        cases = {'standing_level_too_high': self.binding(fp=fingerprint(permission_level=4)),
                 'standing_uses_out_of_range': self.binding(max_uses=51),
                 'standing_expiry_out_of_range': self.binding(days=31),
                 'standing_agent_not_active': self.binding(fp=fingerprint(status='pausiert'))}
        for reason, b in cases.items():
            with self.subTest(reason):
                self.assertEqual(self.grant(b), {'authorized': False, 'reason': reason})
        self.assertIsNone(self.guard.standing_status('A1'))
        self.assertEqual([e['reason'] for e in self.events('CAPTAIN_STANDING_REFUSED')], list(cases))

    def test_12_a_second_grant_replaces_the_first(self):
        first = self.grant(self.binding())['token']
        self.clock.now += timedelta(seconds=1)
        second = self.grant(self.binding(max_uses=10))['token']
        tokens = json.loads(self.store.read_text(encoding='utf-8'))
        self.assertEqual((tokens[first['token_id']]['status'], tokens[first['token_id']]['end_reason']), ('ended', 'ersetzt'))
        active = [t for t in tokens.values() if t.get('kind') == 'standing' and t['status'] == 'active']
        self.assertEqual([t['token_id'] for t in active], [second['token_id']])
        self.assertEqual(self.guard.standing_status('A1')['token_id'], second['token_id'])


class Use(Base):
    def setUp(self):
        super().setUp()
        self.token = self.grant(self.binding())['token']

    def status(self):
        return self.guard.standing_status('A1')

    def test_05_a_valid_use_counts_and_is_audited_with_the_run(self):
        out = self.use(run_ref='W-7')
        self.assertEqual(out, {'authorized': True, 'token_id': self.token['token_id'], 'uses': 1, 'left': 49})
        self.assertEqual(self.status()['uses'], 1)
        self.assertEqual(self.events('CAPTAIN_STANDING_USED'),
                         [{'token_id': self.token['token_id'], 'agent_id': 'A1', 'uses': 1, 'max_uses': 50, 'run_ref': 'W-7'}])

    def test_06_after_expiry_the_token_ends(self):
        self.clock.now += timedelta(days=7)
        self.assertEqual(self.use(), {'authorized': False, 'reason': 'standing_expired'})
        self.assertEqual((self.status()['status'], self.status()['end_reason']), ('expired', 'abgelaufen'))
        self.assertEqual(self.events('CAPTAIN_STANDING_ENDED'), [{'token_id': self.token['token_id'], 'agent_id': 'A1', 'reason': 'abgelaufen'}])
        self.assertEqual(self.use()['reason'], 'no_standing_approval')

    def test_07_a_changed_fingerprint_ends_the_token(self):
        changes = {'stufe': {'permission_level': 3}, 'rezept': {'recipe_id': 'coder.andere'}, 'vorgesetzter': {'reports_to': 'A9'},
                   'budget': {'budget_tokens': 200000}, 'pausiert': {'status': 'pausiert'}}
        for name, change in changes.items():
            with self.subTest(name):
                self.grant(self.binding())
                self.assertEqual(self.use(fp=fingerprint(**change)), {'authorized': False, 'reason': 'standing_fingerprint_changed'})
                self.assertEqual((self.status()['status'], self.status()['end_reason']), ('ended', 'erloschen:fingerabdruck'))

    def test_08_a_stopped_budget_ends_the_token(self):
        self.assertEqual(self.use(stage='gestoppt'), {'authorized': False, 'reason': 'standing_budget_exhausted'})
        self.assertEqual((self.status()['status'], self.status()['end_reason']), ('ended', 'erloschen:budget'))

    def test_09_the_50th_use_is_allowed_the_51st_is_not(self):
        for n in range(1, 51):
            self.assertEqual(self.use(run_ref=f'W-{n}')['uses'], n)
        self.assertEqual((self.status()['status'], self.status()['end_reason'], self.status()['uses']), ('spent', 'verbraucht', 50))
        # Nach der 50. Nutzung ist das Token beendet; die 51. findet keine aktive Dauerfreigabe mehr (Entwurf D1.4, offener Punkt).
        self.assertEqual(self.use(), {'authorized': False, 'reason': 'no_standing_approval'})

    def test_09b_an_active_token_with_all_uses_spent_is_used_up(self):
        tokens = json.loads(self.store.read_text(encoding='utf-8'))
        tokens[self.token['token_id']]['uses'] = 50
        self.store.write_text(json.dumps(tokens), encoding='utf-8')
        self.assertEqual(self.use(), {'authorized': False, 'reason': 'standing_used_up'})
        self.assertEqual((self.status()['status'], self.status()['end_reason']), ('spent', 'verbraucht'))

    def test_10_revoke(self):
        self.assertEqual(self.guard.revoke_standing('A1', reason='captain'), 1)
        self.assertEqual(self.events('CAPTAIN_STANDING_REVOKED'), [{'agent_id': 'A1', 'reason': 'captain', 'count': 1}])
        self.assertEqual((self.status()['status'], self.status()['end_reason']), ('ended', 'widerrufen:captain'))
        self.assertEqual(self.use(), {'authorized': False, 'reason': 'no_standing_approval'})
        self.assertEqual(self.guard.revoke_standing('A1', reason='captain'), 0)

    def test_11_a_standing_token_never_passes_authorize_or_check_token(self):
        for action in ('wake_agent', 'agent.assign', 'paid_action'):
            with self.subTest(action):
                for call in (self.guard.authorize, self.guard.check_token):
                    out = call(self.token, mission_id='M-REQ', action=action, target='agent:A1', request_binding=None)
                    self.assertEqual(out, {'authorized': False, 'reason': 'token_kind_mismatch'})
        self.assertEqual(self.status()['uses'], 0)

    def test_14_a_restart_keeps_count_and_status(self):
        self.use(); self.use()
        self.guard = self.new_guard()
        self.assertEqual((self.status()['uses'], self.status()['status']), (2, 'active'))
        self.assertEqual(self.use()['uses'], 3)
        self.guard.revoke_standing('A1', reason='captain')
        self.guard = self.new_guard()
        self.assertEqual(self.status()['status'], 'ended')


def _use_last(store, start, results):
    guard = Guard(RULES, None, Path(store))
    start.wait(10)
    out = guard.authorize_standing('A1', fingerprint=fingerprint(), budget_stage='ok', run_ref='race')
    results.put(out['authorized'])


class Race(unittest.TestCase):
    def test_13_two_processes_race_for_the_last_use(self):
        with tempfile.TemporaryDirectory(prefix='guard-race-') as tmp:
            store = Path(tmp) / 'tokens.json'
            guard = Guard(RULES, None, store)
            fp = fingerprint()
            b = {'art': 'standing', 'agent_id': 'A1', 'fingerprint': fp, 'max_uses': 1,
                 'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
            gate = guard.create_gate('M-REQ', 'wake_agent', 'agent:A1', request_binding=b)
            out = guard.grant_standing(guard.approve(gate), mission_id='M-REQ', agent_id='A1', fingerprint=fp, max_uses=1,
                                       expires_at=b['expires_at'])
            self.assertTrue(out['authorized'])
            ctx = multiprocessing.get_context('spawn')
            start, results = ctx.Event(), ctx.Queue()
            procs = [ctx.Process(target=_use_last, args=(str(store), start, results)) for _ in range(2)]
            for p in procs:
                p.start()
            start.set()
            got = sorted(results.get(timeout=60) for _ in procs)
            for p in procs:
                p.join(30)
            self.assertEqual(got, [False, True])
            self.assertEqual(Guard(RULES, None, store).standing_status('A1')['status'], 'spent')


class Store(Base):
    def test_15_prune_drops_ended_standing_tokens_after_30_days_and_keeps_active_ones(self):
        ended = self.grant(self.binding('A1'))['token']
        active = self.grant(self.binding('A2'))['token']
        self.guard.revoke_standing('A1', reason='captain')
        self.clock.now += timedelta(seconds=TOKEN_KEEP_S - 60)
        self.once(self.binding('A3'))
        self.assertIn(ended['token_id'], json.loads(self.store.read_text(encoding='utf-8')))
        self.clock.now += timedelta(seconds=120)
        self.once(self.binding('A3'))
        tokens = json.loads(self.store.read_text(encoding='utf-8'))
        self.assertNotIn(ended['token_id'], tokens)
        self.assertEqual(tokens[active['token_id']]['status'], 'active')

    def test_16_old_tokens_without_kind_still_pass_authorize(self):
        b = {'pfad': 'x'}
        gate = self.guard.create_gate('M-1', 'install_module', 'modul:x', request_binding=b)
        token = self.guard.approve(gate)
        self.assertEqual(token['kind'], 'once')
        tokens = json.loads(self.store.read_text(encoding='utf-8'))
        del tokens[token['token_id']]['kind']
        self.store.write_text(json.dumps(tokens), encoding='utf-8')
        del token['kind']
        self.assertEqual(self.guard.check_token(token, mission_id='M-1', action='install_module', target='modul:x', request_binding=b),
                         {'authorized': True, 'reason': 'approved'})
        self.assertTrue(self.guard.authorize(token, mission_id='M-1', action='install_module', target='modul:x', request_binding=b)['authorized'])


if __name__ == '__main__':
    unittest.main()
