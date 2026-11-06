"""Sprache → Text: die Provider-Suche und ihre Kommandozeilen (rein, ohne Provider auf dem Rechner). Neu 04.11.2026: `faster-whisper`
(die Kommandozeile `whisper-ctranslate2`) als CPU-Provider neben WhisperX und openai-whisper."""
import unittest

from sedra_runtime.sprache import stt


def gefunden(*namen):
    return lambda n: ('/bin/' + n) if (n == 'ffmpeg' or n in namen) else None


class Provider(unittest.TestCase):
    def test_reihenfolge_whisperx_vor_faster_whisper_vor_whisper(self):
        self.assertEqual([p[0] for p in stt.PROVIDER], ['whisperx', 'faster-whisper', 'whisper'])
        self.assertEqual(stt.provider_finden(gefunden('whisperx', 'whisper-ctranslate2', 'whisper'))['provider'], 'whisperx')
        self.assertEqual(stt.provider_finden(gefunden('whisper-ctranslate2', 'whisper'))['provider'], 'faster-whisper')
        self.assertEqual(stt.provider_finden(gefunden('whisper'))['provider'], 'whisper')

    def test_faster_whisper_allein_ist_bereit(self):
        p = stt.provider_finden(gefunden('whisper-ctranslate2'))
        self.assertEqual((p['status'], p['provider']), ('bereit', 'faster-whisper'))
        self.assertIn('pip install whisper-ctranslate2', p['install'])

    def test_ohne_ffmpeg_nur_platzhalter(self):
        p = stt.provider_finden(lambda n: '/bin/' + n if n == 'whisper-ctranslate2' else None)
        self.assertEqual((p['status'], p['provider']), ('platzhalter', 'faster-whisper'))

    def test_ohne_provider_nennt_den_neuen(self):
        p = stt.provider_finden(gefunden())
        self.assertEqual(p['provider'], 'keiner')
        self.assertIn('whisper-ctranslate2', p['note'])

    def test_kommandozeile_cpu_int8(self):
        p = stt.provider_finden(gefunden('whisper-ctranslate2'))
        cmd = stt.befehl(p, 'a.wav', 'de', 'ziel')
        self.assertEqual(cmd[0], p['befehl'])
        self.assertTrue(cmd[0].endswith('whisper-ctranslate2'))
        self.assertEqual(cmd[cmd.index('--device') + 1], 'cpu')
        self.assertEqual(cmd[cmd.index('--compute_type') + 1], 'int8')
        self.assertEqual(cmd[cmd.index('--language') + 1], 'de')
        self.assertNotIn('--fp16', cmd)

    def test_eigener_befehl_zaehlt_nur_mit_passendem_namen(self):
        e = {'befehl': '/opt/x/whisper-ctranslate2'}
        p = stt.provider_finden(gefunden('whisper-ctranslate2', '/opt/x/whisper-ctranslate2'), e)
        self.assertEqual(p['befehl'], '/opt/x/whisper-ctranslate2')
        self.assertEqual(stt.befehl(p, 'a.wav', 'en', 'z')[0], '/opt/x/whisper-ctranslate2')

    def test_unbekannte_sprache_wird_abgelehnt(self):
        p = stt.provider_finden(gefunden('whisper-ctranslate2'))
        with self.assertRaises(ValueError):
            stt.befehl(p, 'a.wav', 'xx', 'z')


if __name__ == '__main__':
    unittest.main()
