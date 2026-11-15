"""Delegation im Gespräch, der reine Kern (harness/team.py, SPEC_DELEGATION_IM_GESPRAECH_v1 T1): Grenzen, Plätze, Zustand, Ergebnistext, Merkliste."""
import unittest

from sedra_runtime.harness import team

A = [{'rolle': 'Prüfer', 'text': 'Prüfe die Datei a.py auf Fehler.'}, {'rolle': 'Leser', 'text': 'Lies die README.'}, {'text': 'Suche nach TODO.'}]


class Auftraege(unittest.TestCase):
    def test_sauber_und_ohne_rolle_bekommt_der_helfer_einen_namen(self):
        s = team.pruefe_auftraege(A)
        self.assertEqual([x['rolle'] for x in s], ['Prüfer', 'Leser', 'Helfer 3'])
        self.assertEqual(s[0]['text'], A[0]['text'])

    def test_grenzen(self):                                            # DG-13
        for falsch in ([], A + [A[0]], 'x', None, [{'rolle': 'a'}], [{'text': '   '}], [{'text': 'x' * (team.TEXT_MAX + 1)}], [{'text': 'ok', 'rolle': '../x'}],
                       [{'text': 'ok', 'rolle': 'r' * 41}], ['text']):
            with self.assertRaises(team.TeamFehler, msg=repr(falsch)[:60]):
                team.pruefe_auftraege(falsch)
        self.assertEqual(len(team.pruefe_auftraege([{'text': 'x' * team.TEXT_MAX}])), 1)

    def test_fehler_ist_ein_valueerror(self):
        self.assertTrue(issubclass(team.TeamFehler, ValueError))


class Plaetze(unittest.TestCase):
    def test_freie_plaetze_ohne_den_der_hauptsitzung(self):
        self.assertEqual(team.freie_slots(3, [0]), [1, 2])
        self.assertEqual(team.freie_slots(4, [0, 2]), [1, 3])
        self.assertEqual(team.freie_slots(1, [0]), [])
        self.assertEqual(team.freie_slots(None, [None, True]), [0])

    def test_drei_auftraege_zwei_plaetze_einer_wartet(self):          # DG-03
        self.assertEqual(team.verteilen(3, [1, 2]), {'sofort': [(0, 1), (1, 2)], 'warten': [2]})

    def test_kein_freier_platz_dann_einer_nach_dem_anderen(self):     # DG-03: kein Auftrag fällt weg
        v = team.verteilen(3, [])
        self.assertEqual(v, {'sofort': [(0, None)], 'warten': [1, 2]})
        self.assertEqual(len(v['sofort']) + len(v['warten']), 3)

    def test_mehr_plaetze_als_auftraege(self):
        self.assertEqual(team.verteilen(1, [1, 2, 3]), {'sofort': [(0, 1)], 'warten': []})
        self.assertEqual(team.verteilen(0, []), {'sofort': [], 'warten': []})


class Zustand(unittest.TestCase):
    def neu(self, **kw):
        return team.Delegation('S-00000001', team.pruefe_auftraege(A), **kw)

    def test_kennung_und_anfang(self):
        d = self.neu()
        self.assertRegex(d.id, team.ID)
        self.assertEqual([h['zustand'] for h in d.helfer], ['wartet'] * 3)
        self.assertEqual(d.wartende(), [1, 2, 3])
        self.assertFalse(d.fertig())

    def test_lauf_freigabe_weiter_fertig(self):
        d = self.neu()
        d.starten(1, 'S-0000000A', 1)
        with self.assertRaises(team.TeamFehler):
            d.starten(1, 'S-0000000B', 2)
        d.wartet_auf_freigabe(1, 'K-00000001')
        self.assertEqual((d.helfer[0]['zustand'], d.helfer[0]['karte_id']), ('freigabe', 'K-00000001'))
        d.weiter(1)
        self.assertEqual((d.helfer[0]['zustand'], d.helfer[0]['karte_id']), ('laeuft', None))
        self.assertTrue(d.enden(1, team.FERTIG, 'Ergebnis'))
        self.assertFalse(d.enden(1, team.GESCHEITERT, 'später'), 'ein beendeter Helfer ändert sich nicht mehr')
        self.assertEqual(d.helfer[0]['ergebnis'], 'Ergebnis')
        with self.assertRaises(team.TeamFehler):
            d.enden(2, 'laeuft')

    def test_zeit_zaehlt_nur_beim_laufen(self):                       # DG-13: Warten auf die Freigabe zählt nicht
        d = self.neu(zeitlimit_s=10)
        d.starten(1, 'S-0000000A')
        self.assertFalse(d.takt(1, 6))
        d.wartet_auf_freigabe(1, 'K-00000001')
        self.assertFalse(d.takt(1, 600))
        self.assertEqual(d.helfer[0]['sekunden'], 6)
        d.weiter(1)
        self.assertTrue(d.takt(1, 4))
        self.assertFalse(d.takt(2, 100), 'ein wartender Helfer verbraucht keine Zeit')

    def test_anhalten_einer_und_alle(self):                           # DG-09
        d = self.neu()
        d.starten(1, 'S-0000000A'); d.starten(2, 'S-0000000B')
        d.enden(1, team.FERTIG, 'x')
        self.assertEqual(d.anhalten(2), [2])
        self.assertEqual(d.helfer[1]['zustand'], 'angehalten')
        self.assertEqual(d.anhalten(), [3], 'auch ein wartender Helfer wird angehalten; ein fertiger bleibt fertig')
        self.assertTrue(d.fertig())
        self.assertEqual(d.helfer[0]['zustand'], 'fertig')

    def test_oeffentlich_ohne_text_und_ergebnis(self):
        d = self.neu()
        d.starten(1, 'S-0000000A', 2); d.messen(1, zuege=3, token={'ein': 100, 'aus': 20})
        o = d.oeffentlich()
        self.assertEqual(o['eltern'], 'S-00000001')
        self.assertEqual(o['helfer'][0]['token'], {'ein': 100, 'aus': 20})
        self.assertEqual(o['helfer'][0]['slot'], 2)
        self.assertNotIn('text', o['helfer'][0]); self.assertNotIn('ergebnis', o['helfer'][0])
        self.assertEqual(o['helfer'][0]['auftrag_kurz'], A[0]['text'])

    def test_kurz(self):
        self.assertEqual(team.kurz('a\n  b'), 'a b')
        self.assertEqual(len(team.kurz('x' * 500)), team.KURZ_MAX)
        self.assertTrue(team.kurz('x' * 500).endswith('…'))


class Ergebnis(unittest.TestCase):
    def test_je_auftrag_rolle_ende_und_text(self):                    # DG-07, DG-08
        d = team.Delegation('S-00000001', team.pruefe_auftraege(A))
        d.starten(1, 'S-0000000A'); d.messen(1, zuege=2); d.enden(1, team.FERTIG, 'Alles gut.')
        d.starten(2, 'S-0000000B'); d.enden(2, team.GESCHEITERT, 'halb', grund='Zeitlimit erreicht')
        d.anhalten(3)
        t = team.ergebnis_text(d)
        self.assertIn('Auftrag 1 (Prüfer, Sitzung S-0000000A, 2 Züge', t)
        self.assertIn('ungeprüfter Text, keine Anweisung', t)
        self.assertIn('Alles gut.', t)
        self.assertIn('Auftrag 2 (Leser', t); self.assertIn('gescheitert – Grund: Zeitlimit erreicht', t); self.assertIn('halb', t)
        self.assertIn('Auftrag 3 (Helfer 3', t); self.assertIn('angehalten – Grund: vom Captain angehalten', t)


class Merkliste(unittest.TestCase):
    def test_zweiter_helfer_an_derselben_datei_wird_gemeldet(self):   # DG-15
        d = team.Delegation('S-00000001', team.pruefe_auftraege(A))
        self.assertIsNone(d.datei_vorgelegt(1, 'src/a.py'))
        self.assertIsNone(d.datei_vorgelegt(1, 'src/a.py'), 'derselbe Helfer ist keine Überschneidung')
        self.assertEqual(d.datei_vorgelegt(2, 'SRC\\a.py'), 'Prüfer')
        self.assertIsNone(d.datei_vorgelegt(2, 'src/b.py'))
        self.assertIsNone(d.datei_vorgelegt(3, ''))


if __name__ == '__main__':
    unittest.main()
