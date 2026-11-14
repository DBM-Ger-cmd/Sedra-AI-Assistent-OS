"""S4.2 Teil b (FS-31, Spec Freigaben S4): das eine Audit-Ereignis HARNESS_ERLAUBNIS {aktion, id, dauer, herkunft, kanal} kommt zusätzlich zu den
alten Ereignissen (die ein Jahr bleiben). Gegenproben: unbekannte Aktion oder Dauer ist ein Fehler; die alten Ereignisse bleiben."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.harness import aufgabe, deckung
from test_harness_aufgabe import JETZT, eingabe


class EreignisTests(unittest.TestCase):
    def test_felder(self):
        self.assertEqual(deckung.ereignis('erteilt', 'K-1', 'sitzung', 'karte', 'karte'),
                         {'aktion': 'erteilt', 'id': 'K-1', 'dauer': 'sitzung', 'herkunft': 'karte', 'kanal': 'karte'})

    def test_gegenprobe_unbekannte_aktion_oder_dauer(self):
        with self.assertRaises(ValueError):
            deckung.ereignis('geloescht', 'K-1', 'sitzung', 'karte', 'karte')
        with self.assertRaises(ValueError):
            deckung.ereignis('erteilt', 'K-1', 'immerzu', 'karte', 'karte')

    def test_alle_fuenf_aktionen_und_vier_dauern(self):
        for a in ('erteilt', 'zurueckgenommen', 'abgelaufen', 'erschoepft', 'gedeckelt'):
            for d in ('einmal', 'sitzung', 'befristet', 'immer'):
                self.assertEqual(deckung.ereignis(a, 'x', d, 'h', 'k')['aktion'], a)


class AufgabeAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aufgaben-ereignis-')
        self.audit = []
        self.store = aufgabe.Aufgaben(Path(self.tmp.name) / 'aufgaben', audit=lambda e, p, **_: self.audit.append((e, p)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_anlegen_und_zuruecknehmen_schreiben_das_eine_und_die_alten_ereignisse(self):
        a, _ = self.store.anlegen(eingabe(), jetzt_z=JETZT)
        self.store.zuruecknehmen(a['id'], 'test', jetzt_z=JETZT)
        namen = [e for e, _ in self.audit]
        self.assertIn('HARNESS_AUFGABE_ANGELEGT', namen)
        self.assertIn('HARNESS_AUFGABE_ZURUECKGENOMMEN', namen)
        neu = [p for e, p in self.audit if e == 'HARNESS_ERLAUBNIS']
        self.assertEqual([p['aktion'] for p in neu], ['erteilt', 'zurueckgenommen'])
        for p in neu:
            self.assertEqual((p['id'], p['dauer'], p['herkunft'], p['kanal']), (a['id'], 'befristet', 'aufgabe', 'aufgabe'))

    def test_jeder_aufgabe_ereignisname_steht_im_code(self):
        quelle = (Path(aufgabe.__file__)).read_text(encoding='utf-8')
        for name in deckung.AUFGABE_EREIGNISSE:
            self.assertIn(name, quelle, name)


if __name__ == '__main__':
    unittest.main()
