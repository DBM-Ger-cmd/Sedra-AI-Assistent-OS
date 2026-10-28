"""T2 der Harness-Shell: Sitzungsdateien (G2 §3.7)."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from guppi_runtime.harness.sitzung import ID, SitzungFehler, Sitzungen, titel_aus


class SitzungTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ordner = Path(self.tmp.name) / 'runtime_data' / 'harness' / 'sitzungen'
        self.s = Sitzungen(self.ordner)

    def test_anlegen_schreibt_den_kopf_mit_id(self):
        kopf = self.s.anlegen('sedra-entwicklung', 'Erste Frage', modell='m', mission_id='M-1')
        self.assertRegex(kopf['id'], r'^S-[0-9A-F]{8}$')
        zeilen = (self.ordner / (kopf['id'] + '.jsonl')).read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(zeilen), 1)
        doc = json.loads(zeilen[0])
        self.assertEqual((doc['typ'], doc['version'], doc['projekt'], doc['vorlage'], doc['mission_id']), ('kopf', 1, 'sedra-entwicklung', None, 'M-1'))

    def test_anhaengen_und_laden(self):
        sid = self.s.anlegen('p')['id']
        self.s.anhaengen(sid, {'typ': 'captain', 'text': 'Hallo'})
        self.s.anhaengen(sid, {'typ': 'modell', 'antwort_id': 'A-1', 'text': 'Hi', 'ende': 'antwort'})
        geladen = self.s.laden(sid)
        self.assertEqual([e['typ'] for e in geladen['eintraege']], ['captain', 'modell'])
        self.assertIn('zeit', geladen['eintraege'][0])
        self.assertEqual(geladen['kaputt'], 0)

    def test_eine_zeile_je_eintrag_nur_anhaengen(self):
        sid = self.s.anlegen('p')['id']
        pfad = self.ordner / (sid + '.jsonl')
        vorher = pfad.read_bytes()
        self.s.anhaengen(sid, {'typ': 'captain', 'text': 'zwei\nZeilen'})
        nachher = pfad.read_bytes()
        self.assertTrue(nachher.startswith(vorher))
        self.assertEqual(nachher.count(b'\n'), 2)

    def test_kaputte_zeile_wird_uebersprungen_und_gezaehlt(self):
        sid = self.s.anlegen('p')['id']
        self.s.anhaengen(sid, {'typ': 'captain', 'text': 'a'})
        with open(self.ordner / (sid + '.jsonl'), 'a', encoding='utf-8') as f:
            f.write('{"typ": "modell", "text": "abgeschn\n')
        self.s.anhaengen(sid, {'typ': 'captain', 'text': 'b'})
        geladen = self.s.laden(sid)
        self.assertEqual(geladen['kaputt'], 1)
        self.assertEqual([e['text'] for e in geladen['eintraege']], ['a', 'b'])

    def test_liste_je_projekt_neueste_zuerst(self):
        a = self.s.anlegen('eins', 'A')['id']
        b = self.s.anlegen('zwei', 'B')['id']
        c = self.s.anlegen('eins', 'C')['id']
        import os, time
        os.utime(self.ordner / (a + '.jsonl'), (time.time() + 5, time.time() + 5))
        eins = self.s.liste('eins')
        self.assertEqual([x['id'] for x in eins], [a, c])
        self.assertEqual({x['id'] for x in self.s.liste()}, {a, b, c})
        self.assertIn('zuletzt', eins[0])

    def test_titel_aendern_haengt_eine_zeile_an(self):
        sid = self.s.anlegen('p', 'alt')['id']
        self.s.titel_aendern(sid, 'neu')
        geladen = self.s.laden(sid)
        self.assertEqual(geladen['titel'], 'neu')
        self.assertEqual(geladen['kopf']['titel'], 'alt', 'der Kopf wird nie umgeschrieben')
        self.assertEqual(self.s.liste()[0]['titel'], 'neu')

    def test_titel_hoechstens_60_zeichen(self):
        self.assertEqual(len(titel_aus('x' * 200)), 60)
        self.assertEqual(titel_aus('  zwei\n  Zeilen '), 'zwei Zeilen')

    def test_loeschen_verschiebt_nach_geloescht(self):
        sid = self.s.anlegen('p')['id']
        ziel = self.s.loeschen(sid)
        self.assertTrue(ziel.is_file())
        self.assertEqual(ziel.parent.name, 'geloescht')
        self.assertFalse((self.ordner / (sid + '.jsonl')).exists())
        self.assertEqual(self.s.liste(), [])
        with self.assertRaises(SitzungFehler):
            self.s.laden(sid)

    def test_unbekannte_oder_boese_id_wird_abgelehnt(self):
        for sid in ('S-00000000', '../x', 'S-1A2B3C4D/../../x', 'beliebig'):
            with self.assertRaises(SitzungFehler):
                self.s.laden(sid)
        with self.assertRaises(SitzungFehler):
            self.s.anhaengen('S-ABCDEF12', {'typ': 'captain', 'text': 'x'})

    def test_falscher_eintrag_wird_abgelehnt(self):
        sid = self.s.anlegen('p')['id']
        for e in ({'typ': 'kopf'}, {'text': 'ohne typ'}, 'kein dict'):
            with self.assertRaises(SitzungFehler):
                self.s.anhaengen(sid, e)

    def test_gleichzeitiges_anhaengen_aus_zwei_threads(self):
        sid = self.s.anlegen('p')['id']
        lang = 'ä' * 5000

        def schreiber(name):
            for i in range(100):
                self.s.anhaengen(sid, {'typ': 'captain', 'text': f'{name}{i}', 'fuell': lang})
        threads = [threading.Thread(target=schreiber, args=(n,)) for n in 'ab']
        for t in threads: t.start()
        for t in threads: t.join()
        geladen = self.s.laden(sid)
        self.assertEqual(geladen['kaputt'], 0)
        self.assertEqual(len(geladen['eintraege']), 200)
        self.assertEqual({e['text'] for e in geladen['eintraege']}, {f'{n}{i}' for n in 'ab' for i in range(100)})

    def test_nach_neustart_ist_alles_da(self):
        sid = self.s.anlegen('p', 'bleibt')['id']
        self.s.anhaengen(sid, {'typ': 'captain', 'text': 'x'})
        neu = Sitzungen(self.ordner)
        self.assertEqual(neu.laden(sid)['titel'], 'bleibt')
        self.assertEqual(len(neu.laden(sid)['eintraege']), 1)

    def test_modell_wahl(self):
        sid = self.s.anlegen('p', modell='a')['id']
        self.s.modell_waehlen(sid, 'b')
        self.assertEqual(self.s.laden(sid)['modell'], 'b')
        self.assertTrue(ID.fullmatch(sid))


if __name__ == '__main__':
    unittest.main()
