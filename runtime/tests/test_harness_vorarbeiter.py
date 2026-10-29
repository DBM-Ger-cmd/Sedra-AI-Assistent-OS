"""N4 der Harness-Shell Stufe 3 (rein, ohne Server): Ernennung und Bremse des Vorarbeiters, Karten vorlegen und Frist, Vorlagen-Felder."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from guppi_runtime.harness import freigabe, vorarbeiter, vorlagen

JETZT = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class VorarbeiterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='vorarbeiter-')
        self.pfad = Path(self.tmp.name) / 'harness' / 'vorarbeiter.json'
        self.v = vorarbeiter.Vorarbeiter(self.pfad)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ernennen_entziehen_und_neustart(self):
        self.assertIsNone(self.v.zustaendig('p'))
        self.v.ernennen('p', 'S-11111111', jetzt_z=JETZT)
        self.assertEqual((self.v.zustaendig('p'), self.v.projekt_von('S-11111111'), self.v.projekt_von('S-22222222')), ('S-11111111', 'p', None))
        neu = vorarbeiter.Vorarbeiter(self.pfad)
        self.assertEqual(neu.zustaendig('p'), 'S-11111111', 'die Ernennung übersteht den Neustart')
        self.v.ernennen('p', 'S-22222222')                          # genau einer je Projekt
        self.assertEqual((self.v.zustaendig('p'), self.v.projekt_von('S-11111111')), ('S-22222222', None))
        self.assertIsNotNone(self.v.entziehen('p'))
        self.assertIsNone(self.v.zustaendig('p'))
        self.assertIsNone(self.v.entziehen('p'))

    def test_bremse_je_stunde(self):
        for i in range(3):
            self.v.merken('p', JETZT + timedelta(minutes=i))
        self.assertTrue(self.v.bremse_frei('p', 4, JETZT + timedelta(minutes=5)))
        self.assertFalse(self.v.bremse_frei('p', 3, JETZT + timedelta(minutes=5)))
        self.assertTrue(self.v.bremse_frei('p', 3, JETZT + timedelta(minutes=70)), 'nach einer Stunde zählt es nicht mehr')
        self.assertTrue(self.v.bremse_frei('anderes', 1, JETZT), 'je Projekt')

    def test_defaults_der_spec(self):
        self.assertEqual((vorarbeiter.BEGRUENDUNG_MIN, vorarbeiter.BREMSE_PRO_STUNDE, vorarbeiter.FRIST_MIN), (15, 30, 15))


class KartenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='karten-')
        self.karten = freigabe.Karten(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def neu(self, an='vorarbeiter', angelegt=None):
        k = self.karten.anlegen({'sitzung_id': 'S-11111111', 'werkzeug': 'datei_aendern', 'ziel': 'docs/x.md', 'an': an, 'art': 'werkzeug'})
        if angelegt:
            k['angelegt'] = angelegt.isoformat()
            self.karten.speichern(k)
        return k

    def test_vorlegen_laesst_die_karte_offen_beim_captain(self):
        k = self.neu()
        v = self.karten.vorlegen(k['karte_id'], 'vorarbeiter:S-22222222', 'Das sollte der Captain sehen.')
        self.assertEqual((v['status'], v['an'], v['vorgelegt']['von']), ('offen', 'captain', 'vorarbeiter:S-22222222'))
        self.karten.uebernehmen(k['karte_id'])
        with self.assertRaisesRegex(ValueError, 'karte_schon_beantwortet'):
            self.karten.vorlegen(k['karte_id'], 'x', 'y')

    def test_frist_laesst_alte_karten_an_den_captain_fallen(self):
        alt = self.neu(angelegt=JETZT - timedelta(minutes=16))
        jung = self.neu(angelegt=JETZT - timedelta(minutes=5))
        beim_captain = self.neu(an='captain', angelegt=JETZT - timedelta(minutes=60))
        geaendert = self.karten.frist_pruefen(15, JETZT)
        self.assertEqual([k['karte_id'] for k in geaendert], [alt['karte_id']])
        self.assertEqual(self.karten.laden(alt['karte_id'])['an'], 'captain')
        self.assertTrue(self.karten.laden(alt['karte_id'])['frist_abgelaufen'])
        self.assertEqual(self.karten.laden(jung['karte_id'])['an'], 'vorarbeiter')
        self.assertNotIn('frist_abgelaufen', self.karten.laden(beim_captain['karte_id']))
        self.assertEqual(self.karten.frist_pruefen(15, JETZT), [], 'ein zweites Mal ändert sich nichts')
        self.assertEqual([k['karte_id'] for k in self.karten.frist_pruefen(5, JETZT)], [jung['karte_id']], 'die Frist ist einstellbar')

    def test_oeffentlich_zeigt_die_neuen_felder(self):
        k = self.neu()
        o = freigabe.oeffentlich(k)
        for feld in ('an', 'art', 'vorschau_hash', 'vorgelegt', 'frist_abgelaufen', 'zurueckgenommen', 'aufgabe_id'):
            self.assertIn(feld, o)
        self.assertEqual((o['an'], o['art']), ('vorarbeiter', 'werkzeug'))


class VorlagenFelderTests(unittest.TestCase):
    def doc(self, **kw):
        v = {'id': 'x', 'name': 'X', 'werkzeuge': ['datei_lesen']}
        v.update(kw)
        return {'harness_vorlage': v}

    def test_frist_und_bremse_in_der_vorlage(self):
        ok = vorlagen.pruefen(self.doc(frist_min=30, bremse_pro_stunde=10), 'T')
        self.assertEqual((ok['frist_min'], ok['bremse_pro_stunde']), (30, 10))
        self.assertEqual(vorlagen.pruefen(self.doc(), 'T')['frist_min'], 15)
        for kw in ({'frist_min': 4}, {'frist_min': 61}, {'frist_min': 'x'}, {'bremse_pro_stunde': 0}, {'bremse_pro_stunde': 101}):
            with self.assertRaises(vorlagen.VorlageFehler, msg=str(kw)):
                vorlagen.pruefen(self.doc(**kw), 'T')


if __name__ == '__main__':
    unittest.main()
