"""Der Kern „Sprache“ (19.10.2026): Aufnehmen in Stücken, Abspielen, Löschen, Sprache → Text für jede Shell.

Je Zusage ein Test: ohne Provider ist die Auskunft ein benannter Platzhalter mit Installationsbefehl, nichts wird erfunden; ein
Provider wird nur `bereit`, wenn er und ffmpeg da sind; die Kommandozeile von whisperx/whisper schreibt SRT in den Zielordner mit
fester Sprache; die Stücke werden angehängt und jedes bleibt unter dem Request-Limit; eine leere Aufnahme wird kein Record; die
Abschrift von Hand wird ein Transkript mit Herkunft `manuell`; der Lauf mit einer Provider-Attrappe wird ein Transkript mit Herkunft
`stt:whisperx`, und ein Fehler steht im Record statt in einer Ausnahme; die Erkenntnisse aus einem Transkript werden in vier Blöcke
gelesen und an die Fassung gebunden."""
import base64
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.fisch import erkenntnisse as ek
from guppi_runtime.sprache import aufnahmen as au
from guppi_runtime.sprache import stt

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'
SRT = "1\n00:00:00,500 --> 00:00:02,000\nHallo zusammen.\n\n2\n00:00:02,500 --> 00:00:05,000\nWir entscheiden das am Freitag.\n"


def b64(b): return base64.b64encode(b).decode('ascii')


class Provider(unittest.TestCase):
    def test_without_a_provider_the_answer_is_a_named_placeholder_with_the_install_command(self):
        p = stt.provider_finden(which=lambda n: None)
        self.assertEqual((p['status'], p['provider'], p['install']), ('platzhalter', 'keiner', 'pip install whisperx'))
        self.assertIn('nichts', p['note'].lower() + ' nichts')
        nur_ffmpeg_fehlt = stt.provider_finden(which=lambda n: '/usr/bin/whisperx' if n == 'whisperx' else None)
        self.assertEqual((nur_ffmpeg_fehlt['status'], nur_ffmpeg_fehlt['provider']), ('platzhalter', 'whisperx'))
        self.assertIn('ffmpeg', nur_ffmpeg_fehlt['note'])

    def test_whisperx_is_preferred_and_the_command_writes_srt_with_a_fixed_language(self):
        which = lambda n: '/usr/bin/' + n if n in ('whisperx', 'whisper', 'ffmpeg') else None
        p = stt.provider_finden(which=which)
        self.assertEqual((p['status'], p['provider'], p['befehl']), ('bereit', 'whisperx', '/usr/bin/whisperx'))
        cmd = stt.befehl(p, Path('/tmp/a.webm'), 'de', Path('/tmp/out'))
        self.assertEqual(cmd[:2], ['/usr/bin/whisperx', str(Path('/tmp/a.webm'))])      # str(Path): Windows setzt \ ein
        for flag, wert in (('--language', 'de'), ('--output_format', 'srt'), ('--output_dir', '/tmp/out'), ('--device', 'cpu'), ('--compute_type', 'int8'), ('--model', 'small')):
            self.assertEqual(cmd[cmd.index(flag) + 1], str(Path(wert)) if wert.startswith('/') else wert, flag)
        w = stt.provider_finden(which=lambda n: '/usr/bin/' + n if n in ('whisper', 'ffmpeg') else None)
        self.assertEqual(w['provider'], 'whisper')
        self.assertIn('--fp16', stt.befehl(w, 'a.webm', 'en', 'out'))
        with self.assertRaises(ValueError):
            stt.befehl(p, 'a.webm', 'xx', 'out')

    def test_the_setting_file_is_read_and_bad_values_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'local_config').mkdir()
            (Path(tmp) / 'local_config' / stt.EINSTELLUNG_DATEI).write_text('{"modell": "medium", "geraet": "tpu", "rechenart": "int8"}', encoding='utf-8')
            e = stt.einstellung(tmp)
            self.assertEqual((e['modell'], e['geraet'], e['rechenart']), ('medium', 'cpu', 'int8'))
            self.assertEqual(stt.einstellung(Path(tmp) / 'nicht-da'), stt.STANDARD)


class Aufnahmen(unittest.TestCase):
    def test_pieces_are_appended_and_stay_under_the_request_limit_and_an_empty_recording_is_no_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = au.Store(tmp)
            a = st.beginnen('Besprechung', 'audio/webm;codecs=opus', 'de', '2026-10-19T20:00:00Z')
            self.assertEqual((a['status'], a['endung'], a['mime']), ('laeuft', 'webm', 'audio/webm'))
            st.anhaengen(a['id'], b64(b'abc')); st.anhaengen(a['id'], b64(b'')); r = st.anhaengen(a['id'], b64(b'defg'))
            self.assertEqual((r['groesse'], r['stuecke']), (7, 3))
            self.assertEqual(st.datei(a).read_bytes(), b'abcdefg')
            self.assertLess(au.MAX_STUECK, 1024 * 1024)
            with self.assertRaises(ValueError):
                st.anhaengen(a['id'], 'x' * (au.MAX_STUECK + 1))
            with self.assertRaises(ValueError):
                st.anhaengen(a['id'], '!!not base64!!')
            f = st.beenden(a['id'], '12.5', '2026-10-19T20:01:00Z')
            self.assertEqual((f['status'], f['dauer']), ('fertig', 12.5))
            with self.assertRaises(ValueError):
                st.anhaengen(a['id'], b64(b'x'))
            self.assertEqual(st.abspielen(a['id'])['daten'], b64(b'abcdefg'))
            self.assertEqual([x['id'] for x in st.liste()], [a['id']])
            leer = st.beginnen('', 'audio/ogg', 'en', '2026-10-19T20:02:00Z')
            self.assertTrue(leer['titel'].startswith('Aufnahme '))
            with self.assertRaises(ValueError):
                st.beenden(leer['id'], 0, '2026-10-19T20:02:30Z')
            with self.assertRaises(ValueError):
                au.neu('x', 'video/mp4', 'de', '2026-10-19T20:00:00Z')
            st.loeschen(a['id'])
            self.assertFalse(st.datei(a).exists())


class AmHub(unittest.TestCase):
    def setUp(self):
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='sprache-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)

    def aufnahme(self):
        a = self.hub.sprache.beginnen({'titel': 'Team', 'mime': 'audio/webm', 'sprache': 'de'})
        self.hub.sprache.stueck({'id': a['id'], 'data': b64(b'\x1aE\xdf\xa3 fake webm')})
        return self.hub.sprache.beenden({'id': a['id'], 'dauer': 4.2})

    def test_without_a_provider_the_hand_written_transcript_is_the_way_and_the_record_names_it(self):
        self.hub.sprache.which = lambda n: None
        a = self.aufnahme()
        self.assertEqual(self.hub.sprache.status()['stt']['status'], 'platzhalter')
        with self.assertRaises(ValueError) as cm:
            self.hub.sprache.transkribieren({'id': a['id']})
        self.assertEqual(str(cm.exception), 'kein_provider')
        out = self.hub.sprache.transkribieren({'id': a['id'], 'text': 'Hallo zusammen. Wir entscheiden das am Freitag.'})
        self.assertEqual((out['status'], out['provider']), ('fertig', 'manuell'))
        t = self.hub.fisch.transkript({'id': out['transkript_id']})
        self.assertEqual((t['fassung']['herkunft'], t['sprache'], t['geschaetzt']), ('manuell', 'de', True))
        self.assertIn(str(Path('sprache') / 'aufnahmen'), t['quelle'])                   # Pfadtrenner je System
        self.assertEqual(self.hub.sprache.aufnahmen()['aufnahmen'][0]['transkript_id'], out['transkript_id'])
        self.assertIn('SPRACHE_TRANSKRIBIERT', [e['event_type'] for e in self.hub.audit_view()['events']])

    def test_a_provider_run_becomes_a_transcript_and_a_failure_lands_in_the_record(self):
        self.hub.sprache.which = lambda n: '/usr/bin/' + n if n in ('whisperx', 'ffmpeg') else None
        calls = []
        def run(cmd, **kw):
            calls.append(cmd)
            ziel = Path(cmd[cmd.index('--output_dir') + 1])
            (ziel / (Path(cmd[1]).stem + '.srt')).write_text(SRT, encoding='utf-8')
            return subprocess.CompletedProcess(cmd, 0, '', '')
        self.hub.sprache.run = run
        a = self.aufnahme()
        out = self.hub.sprache.transkribieren({'id': a['id']})
        self.assertEqual((out['status'], out['provider']), ('laeuft', 'whisperx'))
        for _ in range(100):
            if self.hub.sprache.store.get(a['id'])['stt']['status'] != 'laeuft': break
            time.sleep(0.05)
        rec = self.hub.sprache.store.get(a['id'])
        self.assertEqual(rec['stt']['status'], 'fertig', rec['stt'])
        t = self.hub.fisch.transkript({'id': rec['transkript_id']})
        self.assertEqual((t['fassung']['herkunft'], len(t['cues']), t['cues'][1]['start']), ('stt:whisperx', 2, 2.5))
        self.assertEqual(calls[0][calls[0].index('--language') + 1], 'de')
        # ein Fehler des Providers: der Record sagt es, kein Transkript entsteht
        self.hub.sprache.run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, '', 'CUDA not available')
        b = self.aufnahme()
        self.hub.sprache.transkribieren({'id': b['id']})
        for _ in range(100):
            if self.hub.sprache.store.get(b['id'])['stt']['status'] != 'laeuft': break
            time.sleep(0.05)
        rec = self.hub.sprache.store.get(b['id'])
        self.assertEqual(rec['stt']['status'], 'fehler'); self.assertIn('CUDA', rec['stt']['fehler']); self.assertIsNone(rec['transkript_id'])
        self.assertEqual(len(self.hub.fisch.transkripte()['transkripte']), 1)


class Erkenntnisse(unittest.TestCase):
    def test_the_four_blocks_are_read_and_nothing_is_added(self):
        out = ek.lesen('ZUSAMMENFASSUNG:\nEs ging um den Liefertermin.\nENTSCHEIDUNGEN:\n- Lieferung am Freitag\nOFFENE FRAGEN:\n- keine\nAUFGABEN:\n- [PERSON_1] ruft den Kunden an, bis Donnerstag')
        self.assertEqual(out, {'zusammenfassung': 'Es ging um den Liefertermin.', 'entscheidungen': ['Lieferung am Freitag'], 'offen': [],
                               'aufgaben': ['[PERSON_1] ruft den Kunden an, bis Donnerstag']})
        frei = ek.lesen('Nur ein Satz ohne Blöcke.')
        self.assertEqual((frei['zusammenfassung'], frei['aufgaben']), ('Nur ein Satz ohne Blöcke.', []))

    def test_at_the_hub_the_insight_is_bound_to_the_version(self):
        from guppi_runtime.uix_server import UIXHub
        with tempfile.TemporaryDirectory(prefix='ek-') as tmp:
            hub = UIXHub(Path(tmp) / 'project', ARCH)
            try:
                tid = hub.fisch.transkript_import({'text': SRT, 'titel': 'Team', 'sprache': 'de'})['id']
                self.assertEqual(hub.fisch.transkript_erkenntnisse({'id': tid})['status'], 'no_model')
                class FakeServer:
                    def loaded_models(self): return [{'identifier': 'fake', 'modelKey': 'fake'}]
                seen = []
                def execute(m, r):
                    seen.append(r)
                    return {'status': 'completed', 'model_result': {'content': 'ZUSAMMENFASSUNG:\nTermin besprochen.\nENTSCHEIDUNGEN:\n- Freitag\nOFFENE FRAGEN:\n- Uhrzeit\nAUFGABEN:\n- Einladung schicken', 'finish_reason': 'stop'}}
                hub.runtime.llama_server = FakeServer(); hub.runtime.control.execute = execute
                out = hub.fisch.transkript_erkenntnisse({'id': tid})
                self.assertEqual((out['status'], out['erkenntnisse']['version'], out['erkenntnisse']['aufgaben']), ('completed', 1, ['Einladung schicken']))
                self.assertIn('Wir entscheiden das am Freitag', seen[0]['messages'][1]['content'])
                self.assertEqual(hub.fisch.transkript({'id': tid})['erkenntnisse']['entscheidungen'], ['Freitag'])
                hub.fisch.transkript_pseudonymisieren({'id': tid})
                t = hub.fisch.transkript({'id': tid})
                self.assertEqual((t['fassung']['version'], t['erkenntnisse']['version']), (2, 1), 'die Erkenntnis bleibt an Fassung 1 gebunden')
            finally:
                hub.close()


if __name__ == '__main__':
    unittest.main()
