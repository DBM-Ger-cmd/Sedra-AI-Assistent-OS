"""Gespräch mit dem Unterarbeiter (Spec 1, D1.3.1 `anweisen`, D1.3.6 Typ `gespraech`, ORC-14, G2-S1-04, G2-S1-12; S1.H7).

`anweisen` nur am aktiven Agenten mit Delegationsrecht: Nachricht, Issue beim Unterarbeiter, Weckruf `captain:<nachricht>`; derselbe
Schlüssel noch einmal legt nichts Neues an. `gespraech` ist nur lesend: Seiten mit `mehr`, ohne `agent` → `agent_required`.
`ORC_MESSAGE` im Audit trägt nie den Text."""
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.orchestra import messages
from test_orchestra_desk import NOW, Desk


class Anweisen(Desk):
    def setUp(self):
        super().setUp()
        self.db.execute("UPDATE agents SET can_delegate = 1 WHERE id = 'A-UA'")

    def test_only_at_the_foreman(self):
        verbs = lambda aid: [a['verb'] for a in self.hub.objects_view({'type': 'agent', 'id': aid})['actions']]     # noqa: E731
        self.assertIn('anweisen', verbs('A-UA'))
        self.assertNotIn('anweisen', verbs('A-3'), 'andere Agenten über kommentieren (G2-S1-04)')

    def test_message_issue_and_wakeup_and_the_same_key_once(self):
        out = self.act('agent', 'A-UA', 'anweisen', text='Bau den CSV-Export.\nMit Kopfzeile.', key='k-1')['result']
        self.assertTrue(out['neu'])
        msg = self.row('agent_messages', 'id', out['nachricht'])
        self.assertEqual((msg['rolle'], msg['status'], msg['idempotency_key'], msg['issue_id']), ('captain', 'angenommen', 'captain:k-1', out['issue']))
        task = self.row('tasks', 'id', out['issue'])
        self.assertEqual((task['title'], task['assignee'], task['origin'], task['description']),
                         ('Bau den CSV-Export.', 'A-UA', 'captain', 'Bau den CSV-Export.\nMit Kopfzeile.'))
        self.assertEqual(self.wakeups('A-UA'), [{'reason': 'captain', 'idempotency_key': f"captain:{out['nachricht']}", 'task_id': out['issue'],
                                                 'outcome': None}])
        again = self.act('agent', 'A-UA', 'anweisen', text='Bau den CSV-Export.\nMit Kopfzeile.', key='k-1')['result']
        self.assertEqual((again['nachricht'], again['neu']), (out['nachricht'], False))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 3, 'kein zweites Issue')
        self.assertEqual(len(self.wakeups('A-UA')), 1)
        self.assertEqual(self.audit('ORC_MESSAGE'), [{'agent_id': 'A-UA', 'message_id': out['nachricht'], 'laenge': 34, 'issue_id': out['issue']}])
        self.assertNotIn('CSV', self.hub.runtime.audit.path.read_text(encoding='utf-8').split('ORC_MESSAGE')[1][:300])

    def test_empty_or_too_long_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'args_invalid'):
            self.act('agent', 'A-UA', 'anweisen', text='  ')
        with self.assertRaisesRegex(ValueError, 'text_too_long'):
            self.act('agent', 'A-UA', 'anweisen', text='x' * 8001)


class Gespraech(Desk):
    def setUp(self):
        super().setUp()
        for n in range(5):
            messages.add(self.db, 'A-UA', 'captain' if n % 2 == 0 else 'agent', f'Nachricht {n}', NOW)

    def test_pages_newest_last_with_mehr(self):
        out = self.hub.objects_view({'type': 'gespraech', 'agent': 'A-UA', 'limit': 2})
        self.assertEqual(([i['text'] for i in out['items']], out['mehr'], out['quelle']['zustand']), (['Nachricht 3', 'Nachricht 4'], True, 'bereit'))
        older = self.hub.objects_view({'type': 'gespraech', 'agent': 'A-UA', 'limit': 2, 'vor': out['items'][0]['id']})
        self.assertEqual([i['text'] for i in older['items']], ['Nachricht 1', 'Nachricht 2'])
        item = out['items'][-1]
        self.assertEqual((item['type'], item['rolle'], item['state'], item['route'], item['agent_id']), ('gespraech', 'captain', 'angenommen', 'lokal', 'A-UA'))
        self.assertEqual(item['actions'], [], 'nur lesend')

    def test_one_message_and_the_errors(self):
        first = self.hub.objects_view({'type': 'gespraech', 'agent': 'A-UA'})['items'][0]
        self.assertEqual(self.hub.objects_view({'type': 'gespraech', 'id': str(first['id'])})['text'], 'Nachricht 0')
        self.assertEqual(self.hub.objects_view({'type': 'gespraech', 'id': '999'})['state'], 'nicht gefunden')
        with self.assertRaisesRegex(ValueError, 'agent_required'):
            self.hub.objects_view({'type': 'gespraech'})
        self.assertEqual(self.hub.objects_view({'type': 'gespraech', 'agent': 'A-3'})['items'], [])

    def test_letzte_nachricht_at_the_agent(self):
        last = self.hub.objects_view({'type': 'gespraech', 'agent': 'A-UA'})['items'][-1]['id']
        self.assertEqual(self.hub.objects_view({'type': 'agent', 'id': 'A-UA'})['letzte_nachricht'], last)


if __name__ == '__main__':
    unittest.main()
