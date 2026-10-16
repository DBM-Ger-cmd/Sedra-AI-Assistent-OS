"""Ticket B6-G-03, AP1: die Wissensbasis des KI GateWay (gateway/wissen.py) – Regelbuch, Leitfaden, Live-Zustand, Antworten ohne Modell."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.gateway import klassen
from guppi_runtime.gateway.vorgang import GateWay
from guppi_runtime.gateway.wissen import GatewayWissen, LEITFADEN, SCHRITT_VON_ZUSTAND, ZUSTAENDE
from host_isolation import setUpModule, tearDownModule  # noqa: F401

ANFRAGE = 'Lena Beispiel fragt per lena@example.com nach dem Stand von NORD-42. Kundennummer: K-1042.'


class DieWissensbasis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='gw-wissen-'); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gw = GateWay(self.root)
        self.w = GatewayWissen(self.root, self.gw)

    def frage(self, text, vid=None):
        return self.w.antwort(text, vid)

    # ---- Leitfaden und Zustände
    def test_the_guide_has_seven_steps_and_every_state_knows_its_step(self):
        self.assertEqual([s['nr'] for s in LEITFADEN], list(range(1, 8)))
        for s in LEITFADEN:
            for k in ('station', 'titel', 'mensch', 'warten', 'pruefen', 'ablegen', 'sedra'):
                self.assertTrue(s[k], f'Schritt {s["nr"]} ohne {k}')
        for z in ZUSTAENDE:
            self.assertIn(z, SCHRITT_VON_ZUSTAND)
        out = self.frage('Wie lege ich einen Vorgang an und wie geht es dann weiter?')
        self.assertEqual(out['art'], 'leitfaden'); self.assertIn('sieben Schritte', out['reply']); self.assertIn('7. Ablegen', out['reply'])

    def test_step_seven_answers_where_things_are_filed(self):
        for q in ('Wo liegt der Entwurf nach dem Ablegen?', 'Wie lege ich das Ergebnis ab?', 'Schritt 7'):
            out = self.frage(q)
            self.assertEqual(out['art'], 'leitfaden', q); self.assertIn('entwuerfe/', out['reply']); self.assertIn('Kein Versand', out['reply'])
        self.assertIn('Schritt 3', self.frage('Was passiert in Schritt 3?')['reply'])

    # ---- nächster Schritt je Zustand
    def test_next_step_without_a_case_points_to_station_01(self):
        out = self.frage('Was muss ich als Nächstes machen?')
        self.assertEqual(out['art'], 'schritt'); self.assertIn('Neuer Vorgang', out['reply'])
        self.assertEqual(out['ui_actions'][0]['object'], {'type': 'gateway', 'id': 'alle', 'title': 'KI GateWay', 'collection': True})

    def test_next_step_follows_the_state(self):
        v = self.gw.neu('Reklamation')
        self.assertIn('Leitfaden Schritt 3', self.frage('was nun?')['reply'])
        self.gw.pruefen(v.id, ANFRAGE)
        out = self.frage('was muss ich jetzt tun')
        self.assertIn('Leitfaden Schritt 4', out['reply']); self.assertIn('SK1', out['reply']); self.assertIn('nur lokal', out['reply'])
        self.assertEqual(out['ui_actions'][0]['object']['id'], v.id)
        _, b = self.gw.bindung(v.id, 'LOCAL_ONLY'); self.gw.vorgemerkt(v.id, 'LOCAL_ONLY', 'M', b)
        self.assertIn('Leitfaden Schritt 5', self.frage('wie geht es weiter')['reply'])
        self.gw.ausfuehren(v.id, 'LOCAL_ONLY', b, lambda m: 'Sehr geehrte <PERSON_001>, der Stand folgt.')
        self.assertIn('Leitfaden Schritt 6', self.frage('nächster schritt')['reply'])
        self.gw.pruefung(v.id, 'geprueft')
        self.assertIn('keinen offenen Vorgang', self.frage('was nun')['reply'], 'abgeschlossen = kein offener Vorgang mehr')

    def test_a_blocked_case_explains_its_rule_and_an_error_its_code(self):
        v = self.gw.neu('Key'); self.gw.pruefen(v.id, 'hier mein Token ghp_' + 'a' * 36)
        out = self.frage('Warum ist der Vorgang gesperrt?')
        self.assertEqual(out['art'], 'vorgang'); self.assertIn('R-07', out['reply']); self.assertIn('kein „trotzdem“', out['reply'])
        self.assertNotIn('ghp_', out['reply'])
        v2 = self.gw.neu('F'); v2.zustand, v2.fehler = 'FEHLER', 'mapping_fehlt'; self.gw._save(v2)
        out = self.frage('wo ist der fehler', v2.id)
        self.assertIn('mapping_fehlt', out['reply']); self.assertIn('Neustart', out['reply'])

    def test_a_case_named_in_the_question_wins_over_the_latest(self):
        a = self.gw.neu('A'); self.gw.pruefen(a.id, 'Hallo, kurze Übersicht.')
        b = self.gw.neu('B')
        out = self.frage(f'Was ist mit {a.id} als nächstes?')
        self.assertIn('„A“', out['reply']); self.assertIn('Schritt 4', out['reply'])
        self.assertIn('„B“', self.frage('was nun')['reply'], 'ohne Nennung: der jüngste offene Vorgang')

    # ---- Text prüfen
    def test_checking_a_text_names_rules_positions_and_no_duplicates(self):
        out = self.frage('Wo ist der Fehler in diesem Text: Kunde nennt seine Steuer-ID 12 345 678 901 und das Passwort: Sommer2026!')
        self.assertEqual(out['art'], 'text')
        self.assertIn('R-04', out['reply']); self.assertIn('R-07', out['reply']); self.assertIn('gesperrt', out['reply'])
        self.assertEqual(out['reply'].count('R-07'), 1, 'ein Fund je Stelle, keine Dopplung')
        r = self.w.fehler_im_text('Bitte Rückzahlung auf DE89 3704 0044 0532 0130 00.')
        self.assertEqual([f['regel'] for f in r['funde']], ['R-06']); self.assertEqual(r['einstufung']['wege'], ['LOCAL_ONLY'])
        self.assertIn('nichts', self.w.fehler_im_text('Bitte die Öffnungszeiten zusammenfassen.')['satz'])
        self.assertIn('„Lena', self.frage('Prüfe bitte:\nLena Beispiel schreibt an lena@example.com')['reply'])

    # ---- Regelbuch, Begriffe, Fehler
    def test_rule_questions_hit_the_rule_book(self):
        out = self.frage('Was sagt Regel R-02?')
        self.assertEqual(out['art'], 'wissen'); self.assertTrue(out['reply'].startswith('R-02 –')); self.assertIn('Art. 9', out['reply'])
        out = self.frage('Was ist P04?')['reply']
        self.assertTrue(out.startswith('R-04 –') and '(P04)' in out, out[:80])
        self.assertIn('nie', self.frage('darf eine IBAN in die cloud')['reply'].lower())

    def test_terms_come_before_error_codes(self):
        out = self.frage('Was bedeutet Pseudonymisierung?')
        self.assertTrue(out['reply'].startswith('Pseudonymisierung:'), out['reply'][:80]); self.assertIn('keine Anonymisierung', out['reply'])
        self.assertIn('B6_PSEUDO_RECHECK_FAILED', self.frage('was heißt B6_PSEUDO_RECHECK_FAILED')['reply'])

    def test_status_lists_the_cases(self):
        self.assertIn('Keine Vorgänge', self.frage('Wie ist der Stand?')['reply'])
        v = self.gw.neu('Reklamation'); self.gw.pruefen(v.id, ANFRAGE)
        out = self.frage('welche vorgänge sind offen')
        self.assertEqual(out['art'], 'stand'); self.assertIn(v.id, out['reply']); self.assertIn('SK1', out['reply'])

    # ---- Zuständigkeit, Ablage, Hygiene
    def test_responsibility_depends_on_words_ids_and_the_active_shell(self):
        z = GatewayWissen.zustaendig
        self.assertTrue(z('Was sagt das Gateway zu SK3?', 'cockpit'))
        self.assertTrue(z('was ist mit GW-20261015-ABCDEF', 'cockpit'))
        self.assertTrue(z('was muss ich jetzt tun', 'gateway-studio'))
        self.assertFalse(z('was muss ich jetzt tun', 'cockpit'))
        self.assertFalse(z('welches modell läuft', 'gateway-studio'))

    def test_own_entries_survive_a_new_instance_and_are_found(self):
        self.w.eintragen('Wie heißt unser Testkunde?', 'Nordwerk Muster GmbH (synthetisch).')
        w2 = GatewayWissen(self.root, self.gw)
        out = w2.antwort('Wie heißt unser Testkunde?')
        self.assertIn('Nordwerk', out['reply']); self.assertEqual(out['art'], 'wissen')
        self.assertEqual(len(w2.suche('Testkunde')), 1)

    def test_the_sqlite_holds_no_case_text_and_every_answer_names_its_source(self):
        v = self.gw.neu('Reklamation'); self.gw.pruefen(v.id, ANFRAGE)
        for q in ('was nun', 'warum', 'stand', 'R-01', 'wie lege ich an'):
            out = self.frage(q)
            self.assertEqual(out['quelle'], 'gateway-wissen ' + klassen.POLICY_VERSION)
            for a in out['ui_actions']:
                self.assertEqual((a['kind'], a['object']['type']), ('open', 'gateway'))
        raw = (self.root / 'local_config' / 'gateway' / 'wissen.sqlite').read_bytes()
        for word in (b'Lena', b'lena@example.com', b'K-1042', b'NORD-42'):
            self.assertNotIn(word, raw)
        self.assertNotIn('Lena', str([r for r in self.w.suche('Lena')]), 'die Suche kennt keinen Vorgangstext')

    def test_an_unknown_question_says_so_and_still_helps(self):
        out = self.frage('Wie wird das Wetter im GateWay?')
        self.assertIn('Regelbuch', out['reply']); self.assertTrue(out['ui_actions'])


if __name__ == '__main__':
    unittest.main()
