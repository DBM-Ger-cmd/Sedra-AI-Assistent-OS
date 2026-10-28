"""Abnahme KERN-01 (Spec 0, D5, K0.22): mit eingeschaltetem Schalter und einer Fixture-Datenbank aus `orchestra.store.open_db`
liefern `POST /api/objects` für `agent`, `issue`, `routine` und `budget` die Schlüssel der einen Form; `task` bleibt die
Mission wie aufgezeichnet (Golden). Mit Schalter aus sind die Typen Platzhalter mit `quelle` (aus).

Spec 1 (S1.H7, D1.3, Vertrag mit Shell D): dazu die Felder für Shell D, `quelle` (bereit) in allen fünf Listen, die Verben je
Zustand, direkte Verben und Anträge mit „Freigeben und anwenden“ über den Applier, `binding_stale`."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk.kinds import SHAPE
from guppi_runtime.orchestra.store import open_db
from guppi_runtime.uix_server import make_server

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
from test_desk_kinds import FakeHost, call, cases, data, key, post, GOLDEN

ROWS = Path(__file__).resolve().parent / 'fixtures' / 'orchestra_desk' / 'rows.json'
# Spec 1 (D1.3.4, Vertrag mit Shell D): die Felder neben der einen Form; Einzelansicht und Liste.
AGENT_FIELDS = ['rolle', 'reports_to', 'status', 'stufe', 'can_delegate', 'pause_reason', 'revision', 'arbeitet', 'budget',
                'offene_entscheidungen', 'dauerfreigabe', 'letzte_nachricht', 'laeufe']
ISSUE_FIELDS = ['zustand', 'bearbeiter', 'prioritaet', 'eltern_id', 'mission_id', 'vorhaben_id', 'projekt_id', 'geaendert', 'max_level',
                'origin', 'pruefung', 'ausgecheckt', 'revision', 'blocker', 'kommentare']
ROUTINE_FIELDS = ['agent_id', 'cron', 'zeitzone', 'nachholen', 'catch_up', 'enabled', 'next_run', 'last_run', 'beschreibung', 'vorlage',
                  'laeufe', 'letzter_lauf']
BUDGET_FIELDS = ['agent_id', 'pause_reason', 'status']
LIST_FIELDS = {'agent': AGENT_FIELDS, 'issue': ISSUE_FIELDS, 'routine': ROUTINE_FIELDS, 'budget': BUDGET_FIELDS}
FIELDS = dict(LIST_FIELDS, issue=ISSUE_FIELDS + ['kette'])


def fixture_db(project):
    """Die Datenbank, wie die Runtime sie öffnen wird (runtime_data/orchestra/orchestra.db), mit den Zeilen aus rows.json."""
    rows = json.loads(ROWS.read_text(encoding='utf-8'))
    conn = open_db(Path(project) / 'runtime_data' / 'orchestra' / 'orchestra.db')
    try:
        for table in ('agents', 'tasks', 'routines', 'spend'):
            for row in rows[table]:
                cols = sorted(row)
                conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])
    finally:
        conn.close()


def switch_on(project):
    (Path(project) / 'local_config').mkdir(parents=True, exist_ok=True)
    (Path(project) / 'local_config' / 'switches.yaml').write_text('switches:\n  orchestra: {enabled: true}\n', encoding='utf-8')


class SwitchOn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='orchestra-desk-')
        project = Path(cls.tmp.name) / 'project'
        switch_on(project)
        fixture_db(project)
        cls.hub = FakeHost(cls.tmp.name, data())
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hub.close()
        cls.hub.runtime.orchestra.close()
        cls.tmp.cleanup()

    def objects(self, body):
        status, out = post(self.url, '/api/objects', body)
        self.assertEqual(status, 200, out)
        return out

    def test_the_runtime_is_on_and_the_four_types_are_registered(self):
        entry = self.hub.runtime.boot()['orchestra']
        self.assertEqual((entry['enabled'], entry['error'], entry['schema_version']), (True, None, 2))
        self.assertEqual(set(entry['takt']), {'laeuft', 'letzter', 'owner'}, 'der Takt startet mit dem Server (S1.H6)')
        self.assertEqual(self.hub.kinds.problems, [])
        for name in ('agent', 'issue', 'routine', 'budget'):
            self.assertEqual(self.hub.kinds.get(name).source, 'orchestra', name)

    def test_the_four_types_have_the_shape_and_the_shell_d_fields(self):
        singles = [{'type': 'agent', 'id': 'A-CODER'}, {'type': 'issue', 'id': 'I-100'}, {'type': 'routine', 'id': 'R-1'},
                   {'type': 'budget', 'id': 'A-CODER'}]
        for body in singles:
            with self.subTest(body):
                obj = self.objects(body)
                self.assertEqual(sorted(obj), sorted(SHAPE + tuple(FIELDS[body['type']])))
                self.assertEqual((obj['type'], obj['id']), (body['type'], body['id']))
        for t in ('agent', 'issue', 'routine', 'budget'):
            with self.subTest(t):
                listing = self.objects({'type': t})
                self.assertTrue(listing['items'])
                for item in listing['items']:
                    self.assertEqual(sorted(item), sorted(SHAPE + tuple(LIST_FIELDS[t])))
                self.assertEqual(listing['quelle']['zustand'], 'bereit')

    def test_what_the_objects_say(self):
        agent = self.objects({'type': 'agent', 'id': 'A-CODER'})
        self.assertEqual((agent['title'], agent['state'], agent['links']), ('Coder', 'pausiert', [{'type': 'agent', 'id': 'A-UA'}]))
        self.assertEqual([i['id'] for i in self.objects({'type': 'issue'})['items']], ['I-100', 'I-101'], 'Priorität zuerst')
        self.assertEqual([i['id'] for i in self.objects({'type': 'issue', 'state': 'offen'})['items']], ['I-101'])
        budget = self.objects({'type': 'budget', 'id': 'A-CODER'})
        self.assertEqual((budget['state'], budget['summary']), ('Warnung', 'Token 850/1000 · Cent 120/500'))
        self.assertEqual(self.objects({'type': 'budget', 'id': 'A-UA'})['state'], 'im Rahmen')
        self.assertEqual(self.objects({'type': 'agent', 'id': 'A-WEG'})['state'], 'nicht gefunden')
        self.assertEqual(self.objects({'type': 'routine', 'id': 'R-1'})['state'], 'an')

    def test_the_verbs_follow_the_state(self):
        """Spec 1 (D1.3.1): ersetzt OP-12 aus Spec 0 – die Verben erscheinen je Zustand; `anweisen` nur mit Delegationsrecht."""
        def verbs(body):
            return [a['verb'] for a in self.objects(body)['actions']]
        self.assertEqual(verbs({'type': 'agent', 'id': 'A-CODER'}), ['einordnen', 'fortsetzen', 'beenden'])
        self.assertEqual(verbs({'type': 'agent', 'id': 'A-UA'}), ['einordnen', 'pausieren', 'beenden', 'wecken'])
        self.assertEqual(verbs({'type': 'issue', 'id': 'I-100'}), ['zuweisen', 'blocker_setzen', 'kommentieren', 'abbrechen'])
        self.assertEqual(verbs({'type': 'routine', 'id': 'R-1'}), ['aendern', 'ausschalten'])
        self.assertEqual(verbs({'type': 'budget', 'id': 'A-CODER'}), ['festlegen'])
        self.assertEqual([a['verb'] for a in self.objects({'type': 'issue'})['actions']], ['anlegen'])
        self.assertEqual([a['verb'] for a in self.objects({'type': 'routine'})['actions']], ['anlegen'])
        self.assertEqual([a['verb'] for a in self.objects({'type': 'agent'})['actions']], ['einstellen'])

    def test_the_shell_d_fields(self):
        agent = self.objects({'type': 'agent', 'id': 'A-CODER'})
        self.assertEqual((agent['rolle'], agent['reports_to'], agent['status'], agent['stufe'], agent['can_delegate'], agent['arbeitet']),
                         ('Entwicklung', 'A-UA', 'pausiert', 3, 0, False))
        self.assertEqual((agent['budget']['verbraucht_token'], agent['budget']['grenze_token'], agent['budget']['stufe']), (850, 1000, 'warnung'))
        self.assertEqual((agent['offene_entscheidungen'], agent['dauerfreigabe'], agent['laeufe']), (0, None, []))
        issue = self.objects({'type': 'issue', 'id': 'I-101'})
        self.assertEqual((issue['zustand'], issue['bearbeiter'], issue['eltern_id'], issue['blocker'], issue['kommentare']),
                         ('offen', None, 'I-100', [], []))
        self.assertEqual(issue['kette'], [{'type': 'issue', 'id': 'I-100', 'title': 'CSV-Export bauen', 'fehlt': False},
                                          {'type': 'issue', 'id': 'I-101', 'title': 'Tests schreiben', 'fehlt': False}])
        kette = self.objects({'type': 'issue', 'id': 'I-100'})['kette']
        self.assertEqual([(g['type'], g['id'], g['fehlt']) for g in kette], [('intent', 'V-1', False), ('project', 'P-1', False), ('issue', 'I-100', False)],
                         'Vorhaben und Projekt über den Auflöser des Hubs')
        routine = self.objects({'type': 'routine', 'id': 'R-1'})
        self.assertEqual((routine['zeitzone'], routine['nachholen'], routine['vorlage'], routine['laeufe'], routine['letzter_lauf']),
                         ('Europe/Berlin', 'auslassen', {'titel': 'Bericht', 'beschreibung': None}, [], None))
        gespraech = self.objects({'type': 'gespraech', 'agent': 'A-UA'})
        self.assertEqual((gespraech['items'], gespraech['mehr'], gespraech['quelle']['zustand']), ([], False, 'bereit'))
        status, out = post(self.url, '/api/objects', {'type': 'gespraech'})
        self.assertEqual((status, out['message']), (400, 'agent_required'))

    def test_task_stays_the_mission_as_recorded(self):
        golden = json.loads((GOLDEN / 'golden.json').read_text(encoding='utf-8'))
        for c in cases():
            if c[1] and (c[1][0] if c[0] == 'object' else c[1].get('type')) == 'task':
                with self.subTest(key(c)):
                    self.assertEqual(call(self.hub, c), golden[key(c)])


NOW = '2026-10-22T08:00:00Z'


class Desk(unittest.TestCase):
    """Ein echter Hub je Test (Missionen, Guard, Entscheidungen echt), Orchestrierung an, Fixture-Datenbank, feste Uhr."""

    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        tmp = tempfile.TemporaryDirectory(prefix='orchestra-verbs-')
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / 'project'
        switch_on(project)
        fixture_db(project)
        self.hub = UIXHub(project, ARCH)
        self.addCleanup(self.hub.close)
        self.orch = self.hub.runtime.orchestra
        self.addCleanup(self.orch.close)
        self.orch._clock = lambda: NOW
        self.db = self.orch.conn
        self.db.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at)"
                        " VALUES ('A-3', 'I-3', 'reviewer', 'Prüfer', 'Prüfung', 'A-UA', 'aktiv', 2, ?, ?)", (NOW, NOW))

    def act(self, kind, oid, verb, **args):
        body = {'type': kind, 'verb': verb, 'args': args}
        if oid:
            body['id'] = oid
        return self.hub.act(body)

    def decide(self, out, way='freigeben_und_anwenden'):
        return self.hub.decide({'id': out['result']['decision_id'], 'way': way})['result']

    def row(self, table, key, value):
        r = self.db.execute(f'SELECT * FROM {table} WHERE {key} = ?', (value,)).fetchone()
        return dict(r) if r else None

    def wakeups(self, agent_id):
        return [dict(r) for r in self.db.execute('SELECT reason, idempotency_key, task_id, outcome FROM wakeups WHERE agent_id = ? ORDER BY id',
                                                  (agent_id,))]

    def audit(self, event):
        lines = self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines()
        return [e['payload'] for e in map(json.loads, filter(str.strip, lines)) if e['event_type'] == event]


class DirectVerbs(Desk):
    def test_zuweisen_wakes_the_new_assignee(self):
        out = self.act('issue', 'I-101', 'zuweisen', bearbeiter='A-UA')
        self.assertEqual((out['status'], out['needs_gate'], out['result']['bearbeiter']), ('done', False, 'A-UA'))
        task = self.row('tasks', 'id', 'I-101')
        self.assertEqual((task['assignee'], task['state']), ('A-UA', 'zugewiesen'))
        self.assertEqual(self.wakeups('A-UA'), [{'reason': 'zugewiesen', 'idempotency_key': f"assign:I-101:{task['revision']}",
                                                 'task_id': 'I-101', 'outcome': None}])
        self.assertEqual(self.audit('ORC_TASK_ASSIGNED'), [{'task_id': 'I-101', 'alt': None, 'neu': 'A-UA', 'by': 'captain'}])
        with self.assertRaisesRegex(ValueError, 'agent_inactive'):
            self.act('issue', 'I-101', 'zuweisen', bearbeiter='A-CODER')

    def test_anlegen_with_and_without_assignee(self):
        out = self.act('issue', None, 'anlegen', titel='Doku ergänzen', beschreibung='kurz', vorhaben_id='V-1', bearbeiter='A-3')
        task = self.row('tasks', 'id', out['result']['issue'])
        self.assertEqual((task['title'], task['description'], task['goal_ref'], task['assignee'], task['origin']),
                         ('Doku ergänzen', 'kurz', 'V-1', 'A-3', 'captain'))
        self.assertEqual([w['reason'] for w in self.wakeups('A-3')], ['zugewiesen'])
        out = self.act('issue', None, 'anlegen', titel='Ohne Bearbeiter')
        self.assertEqual(self.row('tasks', 'id', out['result']['issue'])['state'], 'offen')
        with self.assertRaisesRegex(ValueError, 'args_invalid'):
            self.act('issue', None, 'anlegen', titel=' ')

    def test_blocker_set_and_released_wakes_the_assignee(self):
        self.act('issue', 'I-101', 'zuweisen', bearbeiter='A-3')
        self.act('issue', 'I-101', 'blocker_setzen', blocker='I-100')
        self.assertEqual(self.hub.objects_view({'type': 'issue', 'id': 'I-101'})['blocker'], ['I-100'])
        with self.assertRaisesRegex(ValueError, 'blocker_cycle'):
            self.act('issue', 'I-100', 'blocker_setzen', blocker='I-101')
        out = self.act('issue', 'I-101', 'blocker_loesen', blocker='I-100')
        self.assertEqual(out['result']['offen'], 0)
        self.assertEqual(self.wakeups('A-3')[-1], {'reason': 'antwort', 'idempotency_key': 'unblocked:I-101:I-100', 'task_id': 'I-101',
                                                   'outcome': None})

    def test_kommentieren_shows_in_the_issue_and_wakes_its_assignee(self):
        self.act('issue', 'I-101', 'zuweisen', bearbeiter='A-3')
        for n in range(4):
            out = self.act('issue', 'I-101', 'kommentieren', text=f'Hinweis {n}')
        self.assertEqual(self.wakeups('A-3')[-1]['idempotency_key'], f"comment:{out['result']['kommentar']}")
        single = self.hub.objects_view({'type': 'issue', 'id': 'I-101'})['kommentare']
        self.assertEqual([k['text'] for k in single], ['Hinweis 0', 'Hinweis 1', 'Hinweis 2', 'Hinweis 3'])
        self.assertEqual((single[0]['autor'], single[0]['autor_art']), ('Captain', 'captain'))
        listed = next(i for i in self.hub.objects_view({'type': 'issue'})['items'] if i['id'] == 'I-101')['kommentare']
        self.assertEqual([k['text'] for k in listed], ['Hinweis 1', 'Hinweis 2', 'Hinweis 3'], 'in der Liste die letzten drei (OP-S1-18)')

    def test_abbrechen_closes_the_task(self):
        self.act('issue', 'I-101', 'abbrechen')
        self.assertEqual(self.row('tasks', 'id', 'I-101')['state'], 'abgebrochen')
        self.assertEqual(self.hub.objects_view({'type': 'issue', 'id': 'I-101'})['actions'], [{'verb': 'kommentieren', 'label': 'Kommentieren',
                                                                                           'needs_gate': False, 'confirm': None}])

    def test_pausieren_frees_the_task_closes_wakeups_and_revokes(self):
        from guppi_runtime.orchestra import board, heartbeat
        self.act('issue', 'I-101', 'zuweisen', bearbeiter='A-UA')
        board.checkout(self.db, 'I-101', 'A-UA', 'run-1', NOW)
        heartbeat.enqueue(self.db, 'A-UA', 'captain', None, NOW, 0)
        self.act('agent', 'A-UA', 'pausieren')
        agent = self.row('agents', 'id', 'A-UA')
        self.assertEqual((agent['status'], agent['pause_reason']), ('pausiert', 'captain'))
        task = self.row('tasks', 'id', 'I-101')
        self.assertEqual((task['state'], task['assignee'], task['checkout_run']), ('offen', None, None))
        self.assertEqual({w['outcome'] for w in self.wakeups('A-UA')}, {'pausiert'})
        self.assertEqual(self.audit('CAPTAIN_STANDING_REVOKED'), [{'agent_id': 'A-UA', 'reason': 'captain', 'count': 0}])
        self.assertEqual(self.db.execute("SELECT text FROM comments WHERE task_id = 'I-101'").fetchone()[0], 'pausiert_vom_captain')

    def test_wecken_is_a_captain_wakeup_for_the_tick(self):
        out = self.act('agent', 'A-UA', 'wecken')
        self.assertTrue(out['needs_gate'], 'ein Lauf braucht eine Freigabe – die stellt der Takt')
        self.assertEqual(self.wakeups('A-UA'), [{'reason': 'captain', 'idempotency_key': None, 'task_id': None, 'outcome': None}])

    def test_a_verb_not_offered_in_this_state_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'verb_not_offered_in_this_state'):
            self.act('agent', 'A-CODER', 'pausieren')
        with self.assertRaisesRegex(ValueError, 'verb_not_offered_in_this_state'):
            self.act('agent', 'A-UA', 'anweisen', text='Los')


class Requests(Desk):
    def test_einordnen_waits_for_the_captain_then_applies(self):
        out = self.act('agent', 'A-3', 'einordnen', reports_to='A-CODER')
        self.assertEqual((out['needs_gate'], out['result']['status'], out['result']['text']), (True, 'beantragt', 'Antrag liegt im Posteingang'))
        self.assertEqual(self.row('agents', 'id', 'A-3')['reports_to'], 'A-UA', 'ohne Freigabe nichts')
        decision = next(d for d in self.hub.decisions_view()['items'] if d['id'] == out['result']['decision_id'])
        self.assertEqual((decision['kind'], decision['agent_id'], decision['binding']['op']), ('request:orchestra', 'A-3', 'einordnen'))
        self.assertEqual(self.hub.objects_view({'type': 'agent', 'id': 'A-3'})['offene_entscheidungen'], 1)
        result = self.decide(out)
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(self.row('agents', 'id', 'A-3')['reports_to'], 'A-CODER')
        self.assertEqual(self.audit('ORC_APPLIED'), [{'op': 'einordnen', 'agent_id': 'A-3', 'routine_id': None}])

    def test_a_changed_agent_makes_the_approval_stale(self):
        out = self.act('agent', 'A-3', 'einordnen', reports_to='A-CODER')
        self.act('agent', 'A-3', 'pausieren')
        self.assertEqual(self.decide(out), {'status': 'binding_stale', 'result': None})
        self.assertEqual(self.row('agents', 'id', 'A-3')['reports_to'], 'A-UA')

    def test_a_stale_wake_request_closes_its_wakeup(self):
        from guppi_runtime.desk import orchestra_kinds
        from guppi_runtime.orchestra import heartbeat
        heartbeat.enqueue(self.db, 'A-UA', 'captain', None, NOW, 0)
        wakeup_id = self.db.execute("SELECT id FROM wakeups WHERE agent_id = 'A-UA'").fetchone()[0]
        self.db.execute("UPDATE wakeups SET outcome = 'antrag' WHERE id = ?", (wakeup_id,))
        binding = {'op': 'wecken', 'agent_id': 'A-UA', 'agent_revision': -1, 'task_id': 'I-101', 'task_revision': 0, 'wakeup_id': wakeup_id}
        with self.assertRaisesRegex(ValueError, 'binding_stale'):
            orchestra_kinds.apply(self.hub, binding)
        self.assertEqual(self.db.execute("SELECT outcome FROM wakeups WHERE id = ?", (wakeup_id,)).fetchone()[0], 'abgelehnt')

    def test_reject_changes_nothing(self):
        out = self.act('agent', 'A-3', 'einordnen', reports_to='A-CODER')
        self.assertEqual(self.decide(out, 'ablehnen')['status'], 'rejected')
        self.assertEqual(self.row('agents', 'id', 'A-3')['reports_to'], 'A-UA')

    def test_fortsetzen_and_beenden(self):
        self.decide(self.act('agent', 'A-CODER', 'fortsetzen'))
        self.assertEqual(self.row('agents', 'id', 'A-CODER')['status'], 'aktiv')
        self.act('issue', 'I-101', 'zuweisen', bearbeiter='A-3')
        out = self.act('agent', 'A-3', 'beenden')
        self.assertEqual(out['needs_gate'], True)
        self.decide(out)
        self.assertEqual(self.row('agents', 'id', 'A-3')['status'], 'beendet')
        task = self.row('tasks', 'id', 'I-101')
        self.assertEqual((task['state'], task['assignee']), ('offen', None))
        with self.assertRaisesRegex(ValueError, 'verb_not_offered_in_this_state'):
            self.act('agent', 'A-3', 'pausieren')

    def test_budget_after_a_stop_is_two_gates_and_resumes(self):
        self.db.execute("UPDATE agents SET pause_reason = 'budget', revision = revision + 1 WHERE id = 'A-CODER'")
        self.db.execute("INSERT INTO budget_incidents (agent_id, kind, percent, used_tokens, created_at) VALUES ('A-CODER', 'stopp', 100, 1000, ?)", (NOW,))
        self.assertNotIn('fortsetzen', [a['verb'] for a in self.hub.objects_view({'type': 'agent', 'id': 'A-CODER'})['actions']])
        out = self.act('budget', 'A-CODER', 'festlegen', budget_tokens=5000)
        mid = out['result']['decision_id'].split(':', 1)[1]
        gates = self.hub.runtime.missions.load(mid)['human_gates']['pending']
        self.assertEqual([g['request']['exact_action'] for g in gates], ['set_budget', 'resume_agent'])
        self.decide(out)
        agent = self.row('agents', 'id', 'A-CODER')
        self.assertEqual((agent['budget_tokens'], agent['status'], agent['pause_reason']), (5000, 'aktiv', None))
        self.assertEqual(self.row('budget_incidents', 'agent_id', 'A-CODER')['resolution'], 'erhoeht')

    def test_budget_without_stop_is_one_gate(self):
        out = self.act('budget', 'A-UA', 'festlegen', budget_tokens=7, budget_period='monat')
        mid = out['result']['decision_id'].split(':', 1)[1]
        self.assertEqual(len(self.hub.runtime.missions.load(mid)['human_gates']['pending']), 1)
        self.decide(out)
        self.assertEqual((self.row('agents', 'id', 'A-UA')['budget_tokens'], self.row('agents', 'id', 'A-UA')['budget_period']), (7, 'monat'))
        with self.assertRaisesRegex(ValueError, 'budget_invalid'):
            self.act('budget', 'A-UA', 'festlegen', budget_tokens=-1)

    def test_routines_are_requests_and_a_bad_cron_is_refused_at_once(self):
        with self.assertRaisesRegex(ValueError, 'cron_invalid:minute'):
            self.act('routine', None, 'anlegen', titel='X', agent_id='A-UA', cron='99 * * * *', zeitzone='UTC')
        with self.assertRaisesRegex(ValueError, 'cron_timezone_unknown'):
            self.act('routine', None, 'anlegen', titel='X', agent_id='A-UA', cron='0 9 * * *', zeitzone='Mars/Olymp')
        self.assertEqual([d for d in self.hub.decisions_view()['items'] if d['kind'] == 'request:orchestra'], [], 'kein Antrag mit ungültigem Ausdruck')
        out = self.act('routine', None, 'anlegen', titel='Täglich', agent_id='A-UA', cron='0 9 * * *', zeitzone='UTC', nachholen='nachholen',
                       vorlage_titel='Bericht', vorlage_beschreibung='kurz')
        rid = self.decide(out)['result']['id']
        routine = self.hub.objects_view({'type': 'routine', 'id': rid})
        self.assertEqual((routine['title'], routine['zeitzone'], routine['nachholen'], routine['vorlage']),
                         ('Täglich', 'UTC', 'nachholen', {'titel': 'Bericht', 'beschreibung': 'kurz'}))
        aus = self.act('routine', rid, 'ausschalten')
        aendern = self.act('routine', rid, 'aendern', cron='30 9 * * *')
        self.decide(aus)
        self.assertEqual(self.row('routines', 'id', rid)['enabled'], 0)
        self.assertEqual(self.decide(aendern)['status'], 'binding_stale', 'die Routine hat sich seit dem Antrag geändert')
        self.decide(self.act('routine', rid, 'einschalten'))
        self.assertEqual(self.row('routines', 'id', rid)['enabled'], 1)


class SwitchOff(unittest.TestCase):
    def test_issue_is_unknown_and_agent_the_placeholder(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-desk-off-') as tmp:
            fixture_db(Path(tmp) / 'project')                # die Datenbank liegt da – ohne Schalter wird sie nicht gelesen
            hub = FakeHost(tmp, data())
            try:
                self.assertIsNone(hub.runtime.orchestra)
                aus = {'zustand': 'aus', 'grund': 'orchestra_off', 'takt': None}      # Spec 4 (G2-S1-10): Platzhalter mit quelle
                for kind in ('issue', 'routine', 'budget', 'gespraech'):
                    self.assertEqual(hub.objects_view({'type': kind}), {'type': kind, 'items': [], 'quelle': aus})
                with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
                    hub.objects_view({'type': 'issue', 'id': 'UA-1'})
                self.assertEqual(hub.objects_view({'type': 'agent'}), {'type': 'agent', 'items': []})
                with self.assertRaisesRegex(ValueError, 'unknown_object_type'):
                    hub.objects_view({'type': 'agent', 'id': 'A-CODER'})
            finally:
                hub.close()


if __name__ == '__main__':
    unittest.main()
