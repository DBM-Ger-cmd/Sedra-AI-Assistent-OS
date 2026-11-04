"""Rückfall der Gesprächs-Zusammenfassung ohne Modell (F3 des Plans vom 04.11.2026): bei leerer Antwort steht ein Auszug, ehrlich als Auszug benannt."""
import unittest

from guppi_runtime.harness import auszug as az
from guppi_runtime.harness.api import HarnessApi

NACHRICHTEN = [
    {'typ': 'captain', 'text': 'Bitte die Taskleiste umbauen. Alles andere später.'},
    {'typ': 'modell', 'text': 'Erledigt.\nDie Zellen sind zusammengelegt und getestet.'},
    {'typ': 'captain', 'text': '   '},
    {'typ': 'captain', 'text': 'x' * 500},
]


class Auszug(unittest.TestCase):
    def test_je_nachricht_der_erste_satz_und_der_kopf_sagt_auszug(self):
        t = az.auszug(None, NACHRICHTEN[:2])
        zeilen = t.splitlines()
        self.assertEqual(zeilen[0], az.KOPF)
        self.assertIn('ohne Modell', az.KOPF)
        self.assertEqual(zeilen[1:], ['- Captain: Bitte die Taskleiste umbauen.', '- SEDRA: Erledigt.'])

    def test_leere_nachrichten_fallen_weg_und_lange_werden_gekuerzt(self):
        t = az.auszug(None, NACHRICHTEN[2:])
        zeilen = t.splitlines()
        self.assertEqual(len(zeilen), 2)
        self.assertTrue(zeilen[1].endswith('…'))
        self.assertLessEqual(len(zeilen[1]), len('- Captain: ') + 220)

    def test_die_bisherige_zusammenfassung_bleibt_und_der_alte_kopf_wird_nicht_doppelt(self):
        erster = az.auszug(None, NACHRICHTEN[:1])
        zweiter = az.auszug(erster, NACHRICHTEN[1:2])
        self.assertEqual(zweiter.count(az.KOPF), 1)
        self.assertEqual(zweiter.splitlines()[1:], ['- Captain: Bitte die Taskleiste umbauen.', '- SEDRA: Erledigt.'])

    def test_zu_lang_dann_fallen_die_aeltesten_zeilen_weg_und_das_limit_gilt(self):
        viele = [{'typ': 'captain', 'text': f'Nachricht {i} mit etwas Text, damit es Platz braucht.'} for i in range(200)]
        t = az.auszug(None, viele, maximal=600)
        self.assertLessEqual(len(t), 600)
        self.assertIn('Nachricht 199', t)
        self.assertNotIn('Nachricht 0 ', t)

    def test_nichts_ergibt_nur_den_kopf(self):
        self.assertEqual(az.auszug(None, []), az.KOPF)


class Stub:
    """Gerade genug von HarnessApi für `_verlauf_zusammenfassen`: ein Modell, das nichts sagt."""
    def __init__(self, inhalt):
        self.inhalt = inhalt
        self.angehaengt, self.audit, self.ereignisse = [], [], []
        self.sitzungen = self

    def _zusammenfassen_modus(self): return 'auto'
    def _option(self, name): return {'verlauf_laenge': 2, 'zusammen_ab': 2}[name]
    def laden(self, sid): return {'eintraege': [dict(e) for e in VERLAUF]}
    def anhaengen(self, sid, e): self.angehaengt.append(e)
    def execute(self, mission, req): return {'status': 'completed', 'model_result': {'content': self.inhalt, 'finish_reason': 'length'}}
    def _audit(self, name, payload): self.audit.append((name, payload))


class Strom:
    def __init__(self): self.gesendet = []
    def senden(self, name, daten): self.gesendet.append((name, daten))


VERLAUF = [{'typ': 'captain', 'text': 'Erste Frage. Mehr Text.'}, {'typ': 'modell', 'text': 'Erste Antwort. Mehr.'},
           {'typ': 'captain', 'text': 'Zweite Frage.'}, {'typ': 'modell', 'text': 'Zweite Antwort.'},
           {'typ': 'captain', 'text': 'Dritte Frage.'}, {'typ': 'modell', 'text': 'Dritte Antwort.'}, {'typ': 'captain', 'text': 'Neu jetzt.'}]


class Rueckfall(unittest.TestCase):
    def lauf(self, inhalt):
        s, a = Stub(inhalt), Strom()
        messages = [{'role': 'system', 'content': 'Basis'}]
        HarnessApi._verlauf_zusammenfassen(s, 'S-1', object(), 'modell', a, messages)
        return s, a, messages

    def test_leere_modellantwort_gibt_einen_auszug_statt_eines_fehlers(self):
        s, a, messages = self.lauf('')
        self.assertEqual(len(s.angehaengt), 1)
        z = s.angehaengt[0]
        self.assertEqual((z['typ'], z['art']), ('zusammenfassung', 'auszug'))
        self.assertTrue(z['text'].startswith(az.KOPF))
        self.assertIn('Captain: Erste Frage.', z['text'])
        self.assertIn(az.KOPF, messages[0]['content'])
        phasen = [d.get('phase') for n, d in a.gesendet]
        self.assertEqual(phasen, ['start', 'ende'])
        self.assertEqual(a.gesendet[-1][1]['art'], 'auszug')
        self.assertIn('HARNESS_VERLAUF_ZUSAMMENFASSUNG_LEER', [n for n, _ in s.audit])

    def test_eine_echte_zusammenfassung_bleibt_eine_zusammenfassung(self):
        s, a, messages = self.lauf('- Der Captain wollte etwas.')
        z = s.angehaengt[0]
        self.assertEqual((z['art'], z['text']), ('modell', '- Der Captain wollte etwas.'))
        self.assertNotIn('HARNESS_VERLAUF_ZUSAMMENFASSUNG_LEER', [n for n, _ in s.audit])


if __name__ == '__main__':
    unittest.main()
