"""U4–U6 der Harness-Shell Stufe 2: Werkzeuge Lesen, Schreiben und befehl, mit dem echten Guard und einem Wegwerf-Projekt."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import befehl as befehl_mod
from guppi_runtime.harness import katalog
from guppi_runtime.harness.werkzeuge import WerkzeugFehler, Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
MISSION = 'M-HARNESS'


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        (root / 'runtime').mkdir()
        (root / 'docs' / 'a.md').write_text('\n'.join(f'Zeile {i}' for i in range(1, 1001)) + '\n', encoding='utf-8')
        (root / 'docs' / 'b.txt').write_text('eins\nzwei\nzwei\n', encoding='utf-8')
        (root / '.env').write_text('GEHEIM=zwei\n', encoding='utf-8')
        (root / 'notizen.md').write_text('zwei außerhalb\n', encoding='utf-8')
        self.root = root
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**', 'runtime/**']}
        self.w = Werkzeuge(self.projekt, guard=self.guard, mission_id=MISSION, regeln=katalog.laden(Path('fehlt'))['regeln'])

    def token(self, plan):
        g = self.guard.create_gate(MISSION, plan['gate']['aktion'], plan['gate']['ziel'], request_binding=plan['gate']['bindung'])
        return self.guard.approve(g)


class LesenTests(Basis):
    def test_datei_lesen_mit_nummern_und_grenze(self):
        out = self.w.ausfuehren('datei_lesen', {'pfad': 'docs/a.md', 'ab_zeile': 10, 'zeilen': 1000})
        self.assertEqual(out['status'], 'ok')
        zeilen = out['ergebnis'].splitlines()
        self.assertIn('Zeilen 10–409 von 1000', zeilen[0])
        self.assertIn('ab_zeile=410', zeilen[0])
        self.assertEqual(len(zeilen), 401, 'höchstens 400 Zeilen (D-E5)')
        self.assertTrue(zeilen[1].endswith('| Zeile 10'))

    def test_zeichengrenze_je_aufruf_und_weiterlesen(self):
        """Abnahme Nemotron C2: 200 Zeilen = 126 KB sprengten das Fenster. Jetzt höchstens LESEN_ZEICHEN_MAX je Aufruf, und
        „weiter mit ab_zeile=N“ führt lückenlos weiter."""
        from guppi_runtime.harness.werkzeuge import LESEN_ZEICHEN_MAX
        (self.root / 'docs' / 'lang.md').write_text('\n'.join('x' * 500 + f' {i}' for i in range(1, 301)) + '\n', encoding='utf-8')
        erster = self.w.ausfuehren('datei_lesen', {'pfad': 'docs/lang.md', 'zeilen': 400})
        self.assertLessEqual(len(erster['ergebnis']), LESEN_ZEICHEN_MAX + 200)
        self.assertIn('weiter mit ab_zeile=', erster['ergebnis'])
        import re
        ab = int(re.search(r'weiter mit ab_zeile=(\d+)', erster['ergebnis']).group(1))
        zweiter = self.w.ausfuehren('datei_lesen', {'pfad': 'docs/lang.md', 'ab_zeile': ab, 'zeilen': 400})
        self.assertTrue(zweiter['ergebnis'].splitlines()[1].lstrip().startswith(f'{ab}|'), 'lückenlos ab der nächsten Zeile')
        einzeln = self.w.ausfuehren('datei_lesen', {'pfad': 'docs/a.md', 'zeilen': 5})
        self.assertIn('Zeilen 1–5 von 1000', einzeln['ergebnis'])

    def test_pfad_ausserhalb_wird_abgelehnt(self):
        for pfad in ('../x', 'C:/Windows/win.ini', 'docs/../../x'):
            with self.assertRaises(WerkzeugFehler):
                self.w.vorbereiten('datei_lesen', {'pfad': pfad})

    def test_auflisten_mit_muster(self):
        out = self.w.ausfuehren('dateien_auflisten', {'pfad': 'docs', 'muster': '*.md'})
        self.assertIn('f a.md', out['ergebnis'])
        self.assertNotIn('b.txt', out['ergebnis'])

    def test_suchen_laesst_verbotenes_aus(self):
        out = self.w.ausfuehren('suchen', {'text': 'ZWEI'})
        self.assertEqual(out['status'], 'ok')
        self.assertIn('docs/b.txt:2:', out['ergebnis'])
        self.assertIn('notizen.md:1:', out['ergebnis'])
        self.assertNotIn('.env', out['ergebnis'], 'was der Katalog nicht lesen lässt, wird nicht durchsucht')
        self.assertEqual(self.w.ausfuehren('suchen', {})['status'], 'fehler')

    def test_suchen_hoechstens_200_treffer(self):
        out = self.w.ausfuehren('suchen', {'regex': r'Zeile \d+', 'pfad': 'docs'})
        self.assertIn('bei 200 abgeschnitten', out['ergebnis'])
        self.assertEqual(len(out['ergebnis'].splitlines()), 201)


class SchreibenTests(Basis):
    def test_ausserhalb_des_schreibbereichs_ohne_gate(self):
        for pfad in ('notizen.md', 'local_config/x.yaml', '../x.md'):
            with self.assertRaises(WerkzeugFehler):
                self.w.vorbereiten('datei_schreiben', {'pfad': pfad, 'inhalt': 'x'})

    def test_ueberschreiben_braucht_das_token_fuer_genau_diesen_inhalt(self):
        args = {'pfad': 'docs/b.txt', 'alt': 'eins', 'neu': 'EINS'}
        plan = self.w.vorbereiten('datei_aendern', args)
        self.assertIn('-eins', plan['vorschau']); self.assertIn('+EINS', plan['vorschau'])
        self.assertEqual(self.w.ausfuehren('datei_aendern', args)['status'], 'fehler', 'ohne Token nichts')
        fremd = self.token(self.w.vorbereiten('datei_schreiben', {'pfad': 'docs/b.txt', 'inhalt': 'anders'}))
        self.assertEqual(self.w.ausfuehren('datei_aendern', args, token=fremd)['status'], 'fehler', 'Token für anderen Inhalt passt nicht')
        out = self.w.ausfuehren('datei_aendern', args, token=self.token(plan))
        self.assertEqual(out['status'], 'ok', out)
        self.assertTrue(out['wirkung'])
        self.assertEqual((self.root / 'docs' / 'b.txt').read_text(encoding='utf-8'), 'EINS\nzwei\nzwei\n')

    def test_token_verfaellt_wenn_die_datei_sich_aendert(self):
        args = {'pfad': 'docs/b.txt', 'inhalt': 'neu'}
        t = self.token(self.w.vorbereiten('datei_schreiben', args))
        (self.root / 'docs' / 'b.txt').write_text('inzwischen geändert', encoding='utf-8')
        self.assertEqual(self.w.ausfuehren('datei_schreiben', args, token=t)['status'], 'fehler')

    def test_neue_datei(self):
        out = self.w.ausfuehren('datei_schreiben', {'pfad': 'docs/neu/c.md', 'inhalt': 'hallo'})
        self.assertEqual(out['status'], 'ok', out)
        self.assertEqual((self.root / 'docs' / 'neu' / 'c.md').read_text(encoding='utf-8'), 'hallo')

    def test_aendern_genau_einmal(self):
        with self.assertRaises(WerkzeugFehler) as ctx:
            self.w.vorbereiten('datei_aendern', {'pfad': 'docs/b.txt', 'alt': 'zwei', 'neu': 'x'})
        self.assertIn('nicht_eindeutig', str(ctx.exception))
        with self.assertRaises(WerkzeugFehler) as ctx:
            self.w.vorbereiten('datei_aendern', {'pfad': 'docs/b.txt', 'alt': 'drei', 'neu': 'x'})
        self.assertIn('nicht_gefunden', str(ctx.exception))


class BefehlTests(Basis):
    def lauf(self, zeile, **kw):
        args = dict({'befehl': zeile}, **kw)
        plan = self.w.vorbereiten('befehl', args)
        return self.w.ausfuehren('befehl', args, token=self.token(plan), plan=plan)

    def test_interpreterzeichen_und_ordner_ausserhalb(self):
        for zeile in ('git status | more', 'echo x > y', 'a && b', 'a; b', 'type x < y', 'echo `x`', 'echo $(x)'):
            with self.assertRaises(befehl_mod.BefehlFehler, msg=zeile):
                self.w.vorbereiten('befehl', {'befehl': zeile})
        with self.assertRaises(befehl_mod.BefehlFehler):
            self.w.vorbereiten('befehl', {'befehl': 'git status', 'ordner': '..'})

    def test_ohne_passendes_token_laeuft_nichts(self):
        out = self.w.ausfuehren('befehl', {'befehl': 'python -c "print(1)"'})
        self.assertEqual(out['status'], 'fehler')
        self.assertIn('Kein passendes Token', out['ergebnis'])
        anderer = self.token(self.w.vorbereiten('befehl', {'befehl': 'python -c "print(2)"'}))
        self.assertIn('Kein passendes Token', self.w.ausfuehren('befehl', {'befehl': 'python -c "print(1)"'}, token=anderer)['ergebnis'])

    def test_laeuft_im_ordner_mit_utf8(self):
        out = self.lauf('python -c "import os; print(os.getcwd()); print(chr(228))"', ordner='docs')
        self.assertEqual(out['status'], 'ok', out)
        self.assertIn('docs', out['ergebnis'])
        self.assertIn('ä', out['ergebnis'])

    def test_zeitlimit_beendet(self):
        t0 = time.monotonic()
        out = self.lauf('python -c "import time; time.sleep(30)"', zeitlimit_s=1)
        self.assertIn('ZEITLIMIT', out['ergebnis'])
        self.assertLess(time.monotonic() - t0, 15)

    def test_stopp_beendet(self):
        abbruch = threading.Event()
        threading.Timer(0.5, abbruch.set).start()
        args = {'befehl': 'python -c "import time; time.sleep(30)"'}
        plan = self.w.vorbereiten('befehl', args)
        t0 = time.monotonic()
        out = self.w.ausfuehren('befehl', args, token=self.token(plan), plan=plan, abbruch=abbruch)
        self.assertEqual(out['status'], 'abgebrochen')
        self.assertLess(time.monotonic() - t0, 15)

    def test_ruecknahme_der_aufgabe_beendet_den_befehl(self):
        # Stufe 3 G2 §4.4, Befund 7 des Bauberichts: ein `befehl` unter einer Aufgaben-Freigabe endet mit ihrer Rücknahme
        from guppi_runtime.harness import befehl as befehl_mod
        self.w.kontext = {'sitzung_id': 'S-00000001', 'antwort_id': None, 'aufgabe_id': 'T-TESTRUECK'}
        befehl_mod.RUECKNAHME.vergessen('T-TESTRUECK')
        threading.Timer(0.5, lambda: befehl_mod.RUECKNAHME.ausloesen('T-TESTRUECK')).start()
        args = {'befehl': 'python -c "import time; time.sleep(30)"'}
        plan = self.w.vorbereiten('befehl', args)
        t0 = time.monotonic()
        out = self.w.ausfuehren('befehl', args, token=self.token(plan), plan=plan)
        self.assertEqual(out['status'], 'abgebrochen')
        self.assertIn('AUFGABE ZURÜCKGENOMMEN', out['ergebnis'])
        self.assertLess(time.monotonic() - t0, 15)
        befehl_mod.RUECKNAHME.vergessen('T-TESTRUECK')
        self.w.kontext = {}

    def test_ohne_aufgabe_kein_ruecknahme_ereignis(self):
        from guppi_runtime.harness import befehl as befehl_mod
        self.assertIsNone(befehl_mod.RUECKNAHME.ereignis(None))
        self.assertIsNone(befehl_mod.RUECKNAHME.ausloesen(''))

    def test_ausgabe_gekuerzt(self):
        out = self.lauf('python -c "print(\'x\' * 50000)"')
        self.assertIn('gekürzt', out['ergebnis'])
        self.assertLess(len(out['ergebnis']), 20_200)


if __name__ == '__main__':
    unittest.main()
