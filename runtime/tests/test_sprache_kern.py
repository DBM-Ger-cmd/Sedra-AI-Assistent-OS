"""Die Aufnahme im Kern: Start, Pause, Stopp als WAV-Record; Verwerfen löscht; ohne Mikrofon sagt der Kern das."""
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_skip  # noqa: E402

env_skip.need_numpy()          # ganzes Modul: ohne numpy nicht lauffähig (nur der Test braucht es)
import numpy as np  # noqa: E402

from guppi_runtime.sprache import aufnahmen as au  # noqa: E402
from guppi_runtime.sprache import kern as kn  # noqa: E402


class FakeStrom:
    """Ohne Thread: die Tests geben die Stücke selbst (cb), damit die Zahlen stimmen."""
    def __init__(self, cb):
        self.cb = cb
    def start(self): pass
    def stop(self): pass
    def close(self): pass


class KernAufnahme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kern-')
        self.addCleanup(self.tmp.cleanup)
        self.store = au.Store(Path(self.tmp.name))
        self.strom = None

        def oeffnen(cb, rate):
            self.strom = FakeStrom(cb)
            return self.strom
        self.kern = kn.Kern(self.store, oeffnen=oeffnen)

    def test_start_pause_stopp_saves_a_wav_record_and_leaves_no_raw_file(self):
        self.assertEqual(self.kern.stand()['status'], 'aus')
        self.assertEqual(self.kern.start('Teamrunde', 'de', '2026-10-20T10:00:00')['status'], 'laeuft')
        self.strom.cb(np.full(1600, 800, dtype=np.int16).tobytes(), 1600, None, None)
        self.assertEqual(self.kern.pause()['status'], 'pause')
        self.strom.cb(np.full(1600, 800, dtype=np.int16).tobytes(), 1600, None, None)   # in der Pause kommt nichts an
        self.assertEqual(self.kern.weiter()['status'], 'laeuft')
        self.strom.cb(np.full(1600, 800, dtype=np.int16).tobytes(), 1600, None, None)
        a = self.kern.stopp('2026-10-20T10:00:05')
        self.assertEqual((a['status'], a['titel']), ('fertig', 'Teamrunde'))
        with wave.open(str(self.store.datei(self.store.get(a['id']))), 'rb') as w:
            self.assertEqual((w.getnchannels(), w.getframerate(), w.getnframes()), (1, 16000, 3200))
        self.assertEqual(list(self.store.dir.glob('*.pcm')), [])
        self.assertEqual(self.kern.stand()['status'], 'aus')

    def test_verwerfen_removes_the_record(self):
        self.kern.start('Weg', 'de', '2026-10-20T10:00:00')
        self.kern.verwerfen()
        self.assertEqual(self.kern.stand()['status'], 'aus')
        self.assertEqual([x for x in self.store.liste() if x['titel'] == 'Weg'], [])

    def test_an_empty_recording_leaves_no_record_behind(self):
        self.kern.start('Leer', 'de', '2026-10-20T10:00:00')
        with self.assertRaises(ValueError) as ctx:
            self.kern.stopp('2026-10-20T10:00:01')
        self.assertEqual(str(ctx.exception), 'aufnahme_leer')
        self.assertEqual([x for x in self.store.liste() if x['titel'] == 'Leer'], [])
        self.assertEqual(self.kern.stand()['status'], 'aus')

    def test_the_size_limit_stops_growth_and_is_reported(self):
        import guppi_runtime.sprache.kern as km
        old = km.au.MAX_GROESSE
        km.au.MAX_GROESSE = 3200 * 2          # zwei Stücke à 1600 Frames
        self.addCleanup(lambda: setattr(km.au, 'MAX_GROESSE', old))
        self.kern.start('Voll', 'de', '2026-10-20T10:00:00')
        for _ in range(4):
            self.strom.cb(np.full(1600, 800, dtype=np.int16).tobytes(), 1600, None, None)
        self.assertTrue(self.kern.stand()['voll'])
        a = self.kern.stopp('2026-10-20T10:00:05')
        self.assertEqual(a['groesse'], 44 + 3200 * 2)

    def test_without_a_microphone_the_kern_says_so_and_keeps_nothing(self):
        class Kaputt:
            def __init__(self, cb): pass
            def start(self): raise OSError('kein Eingabegerät')
        self.kern.oeffnen = lambda cb, rate: Kaputt(cb)
        with self.assertRaises(ValueError) as ctx:
            self.kern.start('Ohne Gerät', 'de', '2026-10-20T10:00:00')
        self.assertIn('kein_mikrofon', str(ctx.exception))
        self.assertEqual(self.kern.stand()['status'], 'aus')
        self.assertEqual([x for x in self.store.liste() if x['titel'] == 'Ohne Gerät'], [])


class KernQuelle(KernAufnahme):
    """Mikrofon oder PC-Ton: dieselbe Aufnahme, anderer Eingang."""
    def test_pc_ton_opens_the_loopback_and_unknown_source_is_refused(self):
        offen = []
        self.kern.oeffnen_pc = lambda cb, rate: offen.append(rate) or FakeStrom(cb)
        self.assertEqual(self.kern.start('Ton', 'de', '2026-10-28T10:00:00', 'pc_ton')['quelle'], 'pc_ton')
        self.assertEqual(offen, [kn.RATE])
        self.kern.verwerfen()
        self.assertEqual(self.kern.start('Mic', 'de', '2026-10-28T10:00:00')['quelle'], 'mikrofon')
        self.kern.verwerfen()
        with self.assertRaisesRegex(ValueError, 'quelle_unbekannt'):
            self.kern.start('x', 'de', '2026-10-28T10:00:00', 'radio')

    def test_the_pc_sound_block_becomes_16khz_mono(self):
        got = []
        strom = kn._PcTonStrom.__new__(kn._PcTonStrom)
        strom.kanaele, strom.quelle_rate, strom.rate, strom.pos, strom._weiter = 2, 48000, 16000, 0.0, 0
        strom.callback = lambda daten, n, z, s: got.append((len(daten), n))
        links_rechts = np.tile(np.array([1000, 3000], dtype=np.int16), 4800)      # 4800 Frames = 0,1 s bei 48 kHz
        strom._block(links_rechts.tobytes(), 4800, None, None)
        self.assertEqual(got, [(1600 * 2, 1600)])


if __name__ == '__main__':
    unittest.main()
