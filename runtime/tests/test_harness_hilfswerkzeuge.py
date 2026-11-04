"""Hilfswerkzeuge auf der CPU (P1 des Plans vom 04.11.2026): Sedra erkennt nur, was da ist – Programm im PATH, Paket installiert –, und nennt sonst den Installationsbefehl."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from guppi_runtime.harness import hilfswerkzeuge as hw
from guppi_runtime.harness.api import WEG

KOPF = 'schema: 1\nwerkzeuge:\n'
EINS = '  - {id: a, name: A, art: programm, name_im_system: aprog, zweck: z, install: "pip install a", plan: W1}\n'
ZWEI = '  - {id: b, name: B, art: paket, name_im_system: bpaket, zweck: z, install: "pip install b", plan: F1}\n'


def datei(text):
    d = tempfile.mkdtemp()
    p = Path(d) / 'h.yaml'
    p.write_text(text, encoding='utf-8')
    return p


class Erkennung(unittest.TestCase):
    def test_programm_und_paket_da_oder_fehlt(self):
        p = datei(KOPF + EINS + ZWEI)
        s = hw.stand(p, which=lambda n: '/bin/aprog' if n == 'aprog' else None, find_spec=lambda n: None)
        self.assertEqual([(w['id'], w['status']) for w in s['werkzeuge']], [('a', 'da'), ('b', 'fehlt')])
        self.assertEqual((s['da'], s['gesamt']), (1, 2))
        self.assertEqual(s['werkzeuge'][0]['fundort'], '/bin/aprog')
        self.assertEqual(s['werkzeuge'][1]['install'], 'pip install b')
        s = hw.stand(p, which=lambda n: None, find_spec=lambda n: SimpleNamespace(origin=None) if n == 'bpaket' else None)
        self.assertEqual(s['werkzeuge'][1]['status'], 'da')
        self.assertEqual(s['werkzeuge'][1]['fundort'], 'installiert')

    def test_ein_paket_das_beim_suchen_fehlschlaegt_ist_nur_fehlt(self):
        def kaputt(n): raise ImportError('x')
        s = hw.stand(datei(KOPF + ZWEI), which=lambda n: None, find_spec=kaputt)
        self.assertEqual(s['werkzeuge'][0]['status'], 'fehlt')

    def test_nichts_wird_importiert_oder_gestartet(self):
        gerufen = []
        hw.stand(datei(KOPF + EINS + ZWEI), which=lambda n: gerufen.append(('which', n)) or None, find_spec=lambda n: gerufen.append(('spec', n)) or None)
        self.assertEqual(gerufen, [('which', 'aprog'), ('spec', 'bpaket')])


class Konfiguration(unittest.TestCase):
    def test_kaputte_dateien_sind_ein_satz(self):
        for text, grund in [('nichts: 1\n', 'hilfswerkzeuge_ohne_liste'),
                            (KOPF + '  - {id: a, name: A, art: dienst, name_im_system: x, zweck: z, install: i}\n', 'hilfswerkzeuge_art_unbekannt'),
                            (KOPF + EINS + EINS, 'hilfswerkzeuge_id_doppelt'),
                            (KOPF + '  - {id: a, name: A, art: paket, zweck: z, install: i}\n', 'hilfswerkzeuge_feld_fehlt'),
                            (KOPF + '  - nur text\n', 'hilfswerkzeuge_eintrag_kein_objekt'),
                            ('{{{', 'hilfswerkzeuge_nicht_lesbar')]:
            with self.assertRaises(ValueError, msg=text) as e:
                hw.lesen(datei(text))
            self.assertIn(grund, str(e.exception))
        with self.assertRaises(ValueError):
            hw.lesen(Path(tempfile.mkdtemp()) / 'gibt-es-nicht.yaml')

    def test_die_mitgelieferte_liste_ist_gueltig_und_nennt_die_angefragten_werkzeuge(self):
        ids = [e['id'] for e in hw.lesen()]
        self.assertEqual(len(ids), len(set(ids)))
        for erwartet in ('whisperx', 'faster-whisper', 'whisper', 'ffmpeg', 'presidio', 'markitdown', 'rapidocr', 'piper', 'silero-vad', 'argos'):
            self.assertIn(erwartet, ids)
        for e in hw.lesen():
            self.assertTrue(e['install'].strip(), e['id'])
            self.assertTrue(e['plan'].strip(), e['id'] + ' braucht eine Plan-Nummer')

    def test_der_provider_faster_whisper_steht_hier_wie_im_kern(self):
        from guppi_runtime.sprache import stt
        exe = {e['id']: e['name_im_system'] for e in hw.lesen()}
        for name, programm, _install, _hinweis in stt.PROVIDER:
            self.assertEqual(exe.get(name), programm, name)


class Weg(unittest.TestCase):
    def test_der_weg_ist_bekannt(self):
        m = WEG.fullmatch('/api/harness/hilfswerkzeuge')
        self.assertIsNotNone(m)
        self.assertIn('hilfswerkzeuge', m.groups())


if __name__ == '__main__':
    unittest.main()
