"""S4.5 (Spec Freigaben S4, FS-40 bis FS-42, E2 = Wert 2): Eine Erlaubnis deckt denselben Aufruf (Werkzeug, Ziel, Hash der Argumente) höchstens
zweimal, solange dazwischen nichts geschrieben wurde; danach geht er als Karte an den Captain, das Audit vermerkt `gedeckelt`, die Erlaubnis bleibt.
Der Deckel steht fest im Code, eine Einstellung darf ihn nur enger stellen."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import deckung, katalog
from sedra_runtime.harness import freigabe as fg
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


class WiederholungTests(unittest.TestCase):
    def test_deckel_fest_und_nur_enger(self):
        self.assertEqual(deckung.deckel_wert(), 2)
        self.assertEqual(deckung.deckel_wert(1), 1)
        self.assertEqual(deckung.deckel_wert(2), 2)
        for schlecht in (3, 99):
            with self.assertRaises(ValueError):                    # FS-42: weiter stellen wird abgelehnt
                deckung.deckel_wert(schlecht)
        for kaputt in (0, -1, 'zwei', True, 1.5):
            with self.assertRaises(ValueError):
                deckung.deckel_wert(kaputt)

    def test_zaehlen_deckel_und_neue_runde(self):
        w = deckung.Wiederholung()
        k = w.schluessel('befehl', 'python -m unittest', {'a': 1})
        self.assertFalse(w.erreicht(k))
        w.zaehlen(k)
        self.assertFalse(w.erreicht(k))
        w.zaehlen(k)
        self.assertTrue(w.erreicht(k))                               # FS-40/41: nach zwei gedeckten Aufrufen ist Schluss
        w.schreibe()                                                 # FS-40: Schreiben dazwischen zählt neu
        self.assertFalse(w.erreicht(k))

    def test_anderer_aufruf_hat_eigenen_zaehler(self):
        w = deckung.Wiederholung()
        a, b = w.schluessel('befehl', 'x', {}), w.schluessel('befehl', 'y', {})
        w.zaehlen(a)
        w.zaehlen(a)
        self.assertTrue(w.erreicht(a))
        self.assertFalse(w.erreicht(b))
        self.assertNotEqual(w.schluessel('befehl', 'x', {'a': 1}), w.schluessel('befehl', 'x', {'a': 2}))      # Hash der Argumente gehört dazu

    def test_gegenprobe_enger_deckel_von_eins(self):
        w = deckung.Wiederholung(1)
        k = w.schluessel('befehl', 'x', {})
        w.zaehlen(k)
        self.assertTrue(w.erreicht(k))


class KisteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.w = Werkzeuge(projekt, guard=self.guard, mission_id='M-HARNESS', regeln=self.regeln)
        self.audit = []
        protokoll = mock.Mock()
        protokoll.append = lambda ereignis, component=None, mission_id=None, payload=None, **_: self.audit.append((ereignis, payload))
        self.karten = Karten(Path(self.tmp.name) / 'karten')
        erlaubnisse = [{'karte_id': 'K-1', 'werkzeug': 'befehl', 'muster': 'git commit*', 'aktiv': True},
                       {'karte_id': 'K-2', 'werkzeug': 'datei_schreiben', 'muster': 'docs/**', 'aktiv': True}]
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=protokoll, karten=self.karten,
                           sitzung_id='S-00000001', erlaubnisse=erlaubnisse)
        self.ok = {'status': 'ok', 'ergebnis': 'ran', 'wirkung': True}

    def _befehl(self, zeile='git commit -m x'):
        return self.kiste.aufruf('befehl', {'befehl': zeile})

    def test_dritter_gleicher_aufruf_wird_zur_karte_und_das_audit_vermerkt_es(self):
        with mock.patch.object(fg, 'ausfuehren', return_value=self.ok):
            r1, r2 = self._befehl(), self._befehl()
        self.assertEqual((r1['status'], r1['stufe']), ('ok', 'sitzung'))
        self.assertEqual((r2['status'], r2['stufe']), ('ok', 'sitzung'))
        with mock.patch.object(fg, 'ausfuehren', return_value=self.ok) as m:
            r3 = self._befehl()
            self.assertEqual(r3['status'], 'wartet')                  # FS-41: jetzt entscheidet der Captain
            m.assert_not_called()
        self.assertIn('2-mal ohne Änderung wiederholt', r3['karte']['begruendung'])
        gedeckelt = [p for e, p in self.audit if e == 'HARNESS_ERLAUBNIS' and p['aktion'] == 'gedeckelt']
        self.assertEqual([(p['id'], p['dauer']) for p in gedeckelt], [('K-1', 'sitzung')])
        self.assertEqual(self.kiste.erlaubnisse[0]['karte_id'], 'K-1')      # die Erlaubnis selbst bleibt bestehen

    def test_anderer_befehl_ist_nicht_gedeckelt(self):
        with mock.patch.object(fg, 'ausfuehren', return_value=self.ok):
            self._befehl(), self._befehl()
            r = self._befehl('git commit -m y')
        self.assertEqual(r['status'], 'ok')

    def test_schreiben_dazwischen_zaehlt_neu(self):
        with mock.patch.object(fg, 'ausfuehren', return_value=self.ok):
            self._befehl(), self._befehl()
            w = self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'neu\n'})      # ein Schreiben (FS-40)
            self.assertEqual(w['status'], 'ok')
            r = self._befehl()
        self.assertEqual(r['status'], 'ok')

    def test_gegenprobe_ohne_erlaubnis_kein_zaehler_noetig(self):
        kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000002')
        with mock.patch.object(fg, 'ausfuehren', return_value=self.ok):
            self.assertEqual(kiste.aufruf('befehl', {'befehl': 'git commit -m x'})['status'], 'wartet')


if __name__ == '__main__':
    unittest.main()
