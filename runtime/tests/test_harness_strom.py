"""T3 der Harness-Shell: der Strom einer Antwort (G2 §3.2, §5)."""
import io
import threading
import time
import unittest

from guppi_runtime.harness.strom import Stroeme, ZuVieleAntworten, schreiben


class Uhr:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


class StromTests(unittest.TestCase):
    def test_id_und_reihenfolge(self):
        a = Stroeme().anlegen('S-1')
        self.assertRegex(a.id, r'^A-[0-9A-F]{8}$')
        for i in range(5):
            a.senden('text.ungeprueft', {'stueck': str(i)})
        e = a.lesen(0, timeout=0)
        self.assertEqual([x['id'] for x in e], [1, 2, 3, 4, 5])
        self.assertEqual(''.join(x['data']['stueck'] for x in e), '01234')

    def test_wiederaufnahme_ab_nummer(self):
        a = Stroeme().anlegen('S-1')
        for i in range(4): a.senden('denken', {'stueck': str(i)})
        self.assertEqual([x['id'] for x in a.lesen(2, timeout=0)], [3, 4])

    def test_leser_blockiert_bis_neues_ereignis(self):
        a = Stroeme().anlegen('S-1')
        threading.Timer(0.2, lambda: a.senden('zug.start', {'zug': 1})).start()
        start = time.monotonic()
        e = a.lesen(0, timeout=5)
        self.assertEqual(e[0]['event'], 'zug.start')
        self.assertLess(time.monotonic() - start, 3)

    def test_leser_kommt_beim_ende_frei(self):
        a = Stroeme().anlegen('S-1')
        threading.Timer(0.2, a.beenden).start()
        start = time.monotonic()
        self.assertEqual(a.lesen(0, timeout=5), [])
        self.assertLess(time.monotonic() - start, 3)

    def test_nach_ende_kommt_nichts_dazu(self):
        a = Stroeme().anlegen('S-1')
        a.senden('ende', {'ende': 'antwort'})
        self.assertIsNone(a.senden('text.ungeprueft', {'stueck': 'x'}))
        self.assertTrue(a.fertig)

    def test_ende_raeumt_nach_zehn_minuten_auf(self):
        uhr = Uhr()
        s = Stroeme(clock=uhr)
        a = s.anlegen('S-1')
        a.senden('ende', {'ende': 'antwort'})
        uhr.t += 599
        self.assertIs(s.hole(a.id), a, 'bis ende + 10 min vollständig lesbar')
        self.assertEqual(len(a.lesen(0, timeout=0)), 1)
        uhr.t += 2
        self.assertIsNone(s.hole(a.id))

    def test_grenze_acht_laufende(self):
        s = Stroeme()
        laufend = [s.anlegen(f'S-{i}') for i in range(8)]
        with self.assertRaises(ZuVieleAntworten) as ctx:
            s.anlegen('S-9')
        self.assertEqual(str(ctx.exception), 'zu_viele_antworten')
        laufend[0].senden('ende', {})
        self.assertIsNotNone(s.anlegen('S-9'), 'eine fertige zählt nicht mehr')

    def test_abbruch_signal(self):
        s = Stroeme()
        a = s.anlegen('S-1')
        self.assertFalse(a.abbruch.is_set())
        a.stoppen()
        self.assertTrue(a.abbruch.is_set())
        self.assertIs(s.laufend_in('S-1'), a)

    def test_schreiben_als_sse_bis_ende(self):
        a = Stroeme().anlegen('S-1')
        a.senden('text.ungeprueft', {'stueck': 'Hallo'})
        a.senden('ende', {'ende': 'antwort'})
        out = io.BytesIO()
        letzte = schreiben(out, a, ab=0)
        text = out.getvalue().decode('utf-8')
        self.assertEqual(letzte, 2)
        self.assertIn('id: 1\nevent: text.ungeprueft\n', text)
        self.assertIn('"stueck": "Hallo"', text)
        self.assertTrue(text.rstrip().endswith('}'))
        out2 = io.BytesIO()
        schreiben(out2, a, ab=1)
        self.assertNotIn('id: 1\n', out2.getvalue().decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
