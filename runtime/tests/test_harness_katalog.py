"""U1 der Harness-Shell Stufe 2: den Freigabe-Katalog laden und prüfen (HS-25). Die Einstufung selbst (U2) prüfen versteckte Tests (D-F1)."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness import katalog


class KatalogLadenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'projekt'
        self.root.mkdir()

    def schreibe(self, text):
        (self.root / 'local_config').mkdir(exist_ok=True)
        (self.root / 'local_config' / katalog.DATEI).write_text(text, encoding='utf-8')

    def test_ohne_eigene_datei_gilt_die_vorlage(self):
        k = katalog.laden(self.root)
        self.assertEqual(k['quelle'], 'vorlage')
        ids = [r['id'] for r in k['regeln']]
        for rid in ('lesen-alles', 'lesen-geheim', 'schreiben-runtime', 'schreiben-docs', 'befehl-git-lesen', 'befehl-tests', 'befehl-python'):
            self.assertIn(rid, ids)
        self.assertFalse((self.root / 'local_config').exists(), 'es wird nichts in local_config angelegt (D-F2)')

    def test_die_datei_des_captains_geht_vor(self):
        self.schreibe("freigabe_katalog:\n  regeln:\n    - {id: alles, werkzeug: '*', muster: '**', stufe: verboten, begruendung: Test}\n")
        k = katalog.laden(self.root)
        self.assertEqual((k['quelle'], [r['id'] for r in k['regeln']]), ('local_config', ['alles']))
        self.assertEqual(k['regeln'][0]['werkzeug'], ['*'])
        self.assertEqual(k['regeln'][0]['muster'], ['**'])

    def test_kaputte_datei_ist_ein_fehler_mit_grund_kein_rueckfall(self):
        faelle = {
            'freigabe_katalog: [\n': 'datei_unlesbar',
            'freigabe_katalog: {regeln: []}\n': 'regeln_fehlen',
            "freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: loeschen, muster: x, stufe: frei, begruendung: b}\n": 'werkzeug_unbekannt',
            "freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: befehl, muster: x, stufe: locker, begruendung: b}\n": 'stufe_unbekannt',
            "freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: befehl, muster: x, stufe: frei}\n": 'begruendung_fehlt',
            "freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: datei_lesen, muster: '../**', stufe: frei, begruendung: b}\n": 'muster_ausserhalb',
            "freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: datei_lesen, muster: 'C:/x/**', stufe: frei, begruendung: b}\n": 'muster_ausserhalb',
            "freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: befehl, muster: x, stufe: frei, begruendung: b}\n    - {id: a, werkzeug: befehl, muster: y, stufe: frei, begruendung: b}\n": 'doppelt',
        }
        for text, grund in faelle.items():
            self.schreibe(text)
            with self.assertRaises(katalog.KatalogFehler, msg=text) as ctx:
                katalog.laden(self.root)
            self.assertIn(grund, str(ctx.exception), text)

    def test_befehlsmuster_duerfen_wie_befehle_aussehen(self):
        self.schreibe("freigabe_katalog:\n  regeln:\n    - {id: a, werkzeug: befehl, muster: 'python ../x.py *', stufe: captain, begruendung: b}\n")
        self.assertEqual(katalog.laden(self.root)['regeln'][0]['muster'], ['python ../x.py *'])


if __name__ == '__main__':
    unittest.main()
