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
        self.kern = kn.Kern(self.store, oeffnen=oeffnen, oeffnen_pc=oeffnen)       # Standard ist der PC-Ton: dieselbe Attrappe für beide Eingänge

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
        self.kern.oeffnen = self.kern.oeffnen_pc = lambda cb, rate: Kaputt(cb)
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
        self.assertEqual(self.kern.start('Mic', 'de', '2026-10-28T10:00:00', 'mikrofon')['quelle'], 'mikrofon')
        self.kern.verwerfen()
        with self.assertRaisesRegex(ValueError, 'quelle_unbekannt'):
            self.kern.start('x', 'de', '2026-10-28T10:00:00', 'radio')

    def test_the_default_source_is_the_pc_sound_and_the_order_in_the_list_says_so(self):
        """Captain 04.11.2026: der Ton des Rechners ist der Standard, das Mikrofon kommt dazu, und es gibt beides gemischt."""
        self.assertEqual(kn.STANDARD_QUELLE, 'pc_ton')
        self.assertEqual(kn.QUELLEN, ('pc_ton', 'mikrofon', 'beides'))
        gerufen = []
        self.kern.oeffnen_pc = lambda cb, rate: gerufen.append('pc') or FakeStrom(cb)
        self.kern.oeffnen = lambda cb, rate: gerufen.append('mic') or FakeStrom(cb)
        self.assertEqual(self.kern.start('Standard', 'de', '2026-11-04T10:00:00')['quelle'], 'pc_ton')
        self.assertEqual(gerufen, ['pc'])
        self.kern.verwerfen()
        self.assertEqual(self.kern.start('Leer', 'de', '2026-11-04T10:00:00', '')['quelle'], 'pc_ton')           # leere Angabe: Standard
        self.kern.verwerfen()

    def test_both_sources_are_mixed_into_one_track_with_the_microphone_as_clock(self):
        pc, mic = {}, {}
        self.kern.oeffnen_pc = lambda cb, rate: pc.update(cb=cb) or FakeStrom(cb)
        self.kern.oeffnen = lambda cb, rate: mic.update(cb=cb) or FakeStrom(cb)
        self.assertEqual(self.kern.start('Beides', 'de', '2026-11-04T10:00:00', 'beides')['quelle'], 'beides')
        stueck = lambda wert, n: np.full(n, wert, dtype=np.int16).tobytes()
        pc['cb'](stueck(1000, 800), 800, None, None)                    # der PC-Ton liegt bereit, geschrieben wird erst mit dem Mikrofon
        self.assertEqual(self.kern.stand()['groesse'], 0)
        mic['cb'](stueck(200, 1600), 1600, None, None)                   # 800 Proben mit PC-Ton (1200), 800 ohne (nur Mikrofon: 200)
        mic['cb'](stueck(32000, 4), 4, None, None)                       # ohne PC-Ton: nur das Mikrofon
        pc['cb'](stueck(30000, 2), 2, None, None)
        mic['cb'](stueck(5000, 2), 2, None, None)                        # 35000 wird auf 32767 begrenzt
        a = self.kern.stopp('2026-11-04T10:00:05')
        with wave.open(str(self.store.datei(self.store.get(a['id']))), 'rb') as w:
            werte = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        self.assertEqual(len(werte), 1606)
        self.assertEqual((set(werte[:800]), set(werte[800:1600])), ({1200}, {200}))
        self.assertEqual(list(werte[1600:1604]), [32000] * 4)
        self.assertEqual(list(werte[1604:]), [32767, 32767])

    def test_the_pc_buffer_in_the_mix_is_limited_to_one_second(self):
        pc = {}
        self.kern.oeffnen_pc = lambda cb, rate: pc.update(cb=cb) or FakeStrom(cb)
        self.kern.start('Puffer', 'de', '2026-11-04T10:00:00', 'beides')
        strom = self.kern.lauf['strom']
        for _ in range(5):
            pc['cb'](np.full(16000, 7, dtype=np.int16).tobytes(), 16000, None, None)
        self.assertEqual(len(strom.pc), kn._BeidesStrom.PUFFER_MAX)
        self.kern.verwerfen()

    def test_if_the_microphone_is_missing_in_both_the_loopback_is_closed_again(self):
        zu = []
        class PcStrom(FakeStrom):
            def close(self): zu.append('pc')
        self.kern.oeffnen_pc = lambda cb, rate: PcStrom(cb)
        def kein_mikro(cb, rate): raise OSError('kein Eingabegerät')
        self.kern.oeffnen = kein_mikro
        with self.assertRaises(ValueError) as ctx:
            self.kern.start('Halb', 'de', '2026-11-04T10:00:00', 'beides')
        self.assertIn('kein_mikrofon: Für PC-Ton und Mikrofon', str(ctx.exception))
        self.assertEqual((zu, self.kern.stand()['status']), (['pc'], 'aus'))

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
