"""Verb `quelle_pruefen` (SPEC_WERKZEUG_WISSEN_v2 §3.4, Abnahme Z7): die Vorprüfung im geführten Antrag – nur lesen, kein Gate, kein
Audit. Sie sagt, wie viele Dateien und ungefähr wie viele Abschnitte eine Quelle bringt, ob sie sich mit einer aktiven Quelle
überschneidet (Lehre aus Prüfung F4: das Logbuch stand doppelt im Index) und ob es genau diese Quelle schon gibt."""
import unittest

from test_wissen_desk import Basis


class QuellePruefen(Basis):
    def pruefe(self, **args):
        args.setdefault('adapter', 'markdown'); args.setdefault('wurzel', 'projekt'); args.setdefault('stufe', 1)
        return self.act('wissen', None, 'quelle_pruefen', **args)

    def test_zaehlt_und_schaetzt_ohne_spuren(self):
        (self.project / 'notizen' / 'zwei.md').write_text('# Zwei\n\n' + 'Text. ' * 400, encoding='utf-8')
        vorher = len(self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines())
        out = self.pruefe(pfad='notizen')
        self.assertEqual(out['status'], 'erledigt')
        self.assertEqual(out['dateien'], 2)
        self.assertGreaterEqual(out['abschnitte_etwa'], 2)
        self.assertIn('2 Dateien, etwa', out['satz'])
        self.assertFalse(out['schon_da']); self.assertEqual(out['ueberschneidung'], [])
        self.assertEqual(self.sp.quellen(), [], 'die Vorprüfung legt keine Quelle an')
        import json
        neu = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines()[vorher:]]
        # nur die Zeile, die jede Handlung am Desk bekommt (UIX_ACTION, ohne Pfad) – kein Eintrag des Speichers, kein Antrag
        self.assertEqual([e['event_type'] for e in neu], ['UIX_ACTION'])
        self.assertNotIn('notizen', json.dumps(neu))

    def test_fehler_als_satz(self):
        for pfad, code in (('/etc', 'wis_pfad_absolut'), ('../draussen', 'wis_pfad_ausserhalb'), ('gibtsnicht', 'wis_speicher_nicht_lesbar')):
            with self.subTest(pfad):
                out = self.pruefe(pfad=pfad)
                self.assertEqual((out['status'], out['code']), ('fehler', code))
                self.assertTrue(out['satz'])

    def test_ueberschneidung_und_schon_da(self):
        self.decide(self.beantrage(pfad='notizen'))                              # Ordner freigegeben
        teil = self.pruefe(pfad='notizen/werkbank.md')
        self.assertEqual([u['dateien'] for u in teil['ueberschneidung']], [1])
        self.assertIn('Überschneidet sich mit „projekt/notizen“ (1 Datei)', teil['satz'])
        gleich = self.pruefe(pfad='notizen')
        self.assertTrue(gleich['schon_da']); self.assertEqual(gleich['ueberschneidung'], [])
        self.assertIn('schon freigegeben', gleich['satz'])

    def test_speicher_ohne_dateien(self):
        out = self.act('wissen', None, 'quelle_pruefen', adapter='knowledge', wurzel='repo', pfad='knowledge', stufe=1)
        if out['status'] == 'fehler':
            self.skipTest('kein Wissensordner in diesem Paket: ' + out['code'])
        self.assertIsNone(out['dateien']); self.assertIn('erste Abgleich', out['satz'])


if __name__ == '__main__':
    unittest.main()
