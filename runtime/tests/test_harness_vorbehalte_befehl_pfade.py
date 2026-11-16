"""O-1 (Hardening 16.11.2026, docs/HARDENING_2026-11-16_MASTER.md): der feste Vorbehalt prüft bei `befehl` auch die Pfad-Argumente schreibender Programme.

Vorher schrieb `xcopy docs\\neu.txt local_config\\harness_projekte.yaml /Y` in einen geschützten Pfad, sobald ein Katalog-Muster `xcopy*` frei war (oder eine Aufgabe oder eine
Sitzungs-Erlaubnis es deckte): `vorbehalte.pruefen` sah nur die Zeile als Text. Alle Namen, Pfade und Werte sind erfunden (Wegwerf-Projekt im Temp-Ordner)."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sedra_runtime.harness import aufgabe_deckung, vorbehalte  # noqa: E402

from test_hardening_master_2026_11_16 import Projekt, SID  # noqa: E402

WIN = os.name == 'nt'


def grund(zeile, ordner='.'):
    return vorbehalte.pruefen('befehl', zeile, {'befehl': zeile, 'ordner': ordner})


class Zeilen(unittest.TestCase):
    def test_schreibende_programme_in_geschuetzte_pfade(self):
        for zeile in ('xcopy docs\\neu.txt local_config\\harness_projekte.yaml /Y', 'copy a.txt local_config\\x.yaml', 'copy a.txt local_config', 'move a.txt local_config\\',
                      'robocopy docs local_config /E', 'ren a.txt freigabe_katalog.yaml', 'xcopy a LOCAL_CONFIG\\harness', 'xcopy a ".\\local_config\\h.yaml"',
                      'xcopy docs\\* local_config\\*', 'copy a.txt runtime\\src\\sedra_runtime\\harness\\freigabe.py', 'cp a runtime/src/sedra_runtime/core/guard.py',
                      'xcopy a .git\\hooks\\pre-commit', 'xcopy a --dest=local_config', 'copy a.txt runtime\\..\\local_config\\x'):
            with self.subTest(zeile=zeile):
                self.assertIsNotNone(grund(zeile), zeile)

    def test_arbeitsordner_zaehlt_mit(self):
        self.assertIsNotNone(grund('xcopy a ..\\local_config\\x /Y', ordner='docs'), 'docs\\..\\local_config ist local_config')
        self.assertIsNotNone(grund('copy a harness\\freigabe.py', ordner='runtime/src/sedra_runtime'))
        self.assertIsNone(grund('copy a freigabe.py', ordner='docs'), 'docs\\freigabe.py liegt nicht im geschützten Ordner')

    def test_git_schreibende_unterbefehle(self):
        for zeile in ('git checkout -- local_config/x.yaml', 'git restore local_config/x.yaml', 'git apply local_config/x.patch', 'git rm local_config/x', 'git mv a local_config/a',
                      'git checkout abc123 -- runtime/src/sedra_runtime/core/guard.py', 'git -C . restore runtime/src/sedra_runtime/core/guard.py',
                      'git -c core.x=y restore local_config/x', 'git --no-pager checkout -- local_config/x', 'git -C docs restore ../local_config/x'):
            with self.subTest(zeile=zeile):
                self.assertIsNotNone(grund(zeile), zeile)

    def test_lesen_und_normales_arbeiten_bleibt_frei(self):
        for zeile in ('xcopy docs\\a.txt docs\\b.txt /Y', 'copy a.txt b.txt', 'git checkout feature', 'git checkout -b neu', 'git checkout abc123', 'git status', 'git diff local_config/x.yaml',
                      'git add -A', 'git commit -m x', 'git log local_config', 'python benchmarks/run_tests.py harness', 'python -m py_compile local_config/x.py',
                      'type local_config\\x.yaml', 'findstr x local_config\\*', 'pytest tests/test_x.py', 'node --check x.js', 'xcopy a docs\\sub\\ /E', 'copy a.txt ..\\ausserhalb.txt'):
            with self.subTest(zeile=zeile):
                self.assertIsNone(grund(zeile), zeile)

    def test_unlesbare_und_leere_zeilen_machen_nichts_kaputt(self):
        for zeile in ('', '   ', 'xcopy "a', 'xcopy a | more', 'xcopy a > local_config\\x'):
            with self.subTest(zeile=zeile):
                self.assertIsNone(grund(zeile), 'die Zeile weist befehl.py selbst ab; hier keine Ausnahme')

    def test_absolute_und_umgebungspfade_sind_nicht_sache_dieser_pruefung(self):
        for zeile in ('xcopy a C:\\Fremd\\local_config\\x', 'xcopy a %TEMP%\\x', 'xcopy a ~\\x', 'xcopy a \\\\server\\share\\local_config'):
            with self.subTest(zeile=zeile):
                self.assertIsNone(grund(zeile))

    def test_vorhandene_befehlsliste_gilt_weiter(self):
        self.assertIn('git push', grund('git push origin main'))
        self.assertIn('rm', grund('rm -rf x'))

    def test_gegenprobe_die_muster_sind_wirksam(self):
        """Ohne die Prüfung wäre die Zeile frei – hier der Beweis, dass es die neue Funktion ist, die sie hält."""
        self.assertIsNotNone(vorbehalte.pruefen_befehl_pfade('xcopy a local_config\\x', {'ordner': '.'}))
        self.assertIsNone(vorbehalte.pruefen_befehl_pfade('python x.py local_config\\x', {'ordner': '.'}), 'Skripte deckt die Regel G4, nicht diese Prüfung')


@unittest.skipUnless(WIN, 'xcopy gibt es nur unter Windows')
class GanzerWeg(Projekt):
    """Katalog und Aufgabe geben `xcopy*` frei; der feste Vorbehalt hält trotzdem (Kiste.aufruf)."""

    def test_katalog_frei_schreibt_trotzdem_nicht_in_local_config(self):
        self.regeln = self.regeln + [{'id': 'test-xcopy-frei', 'werkzeug': ['befehl'], 'muster': ['xcopy*'], 'stufe': 'frei', 'begruendung': 'Test'}]
        (self.root / 'docs' / 'neu.txt').write_text('EVIL', encoding='utf-8')
        r = self.kiste(master=None).aufruf('befehl', {'befehl': 'xcopy docs\\neu.txt local_config\\harness_projekte.yaml /Y', 'ordner': '.'})
        self.assertEqual(r['status'], 'wartet', r)
        self.unveraendert()

    def test_derselbe_befehl_in_docs_laeuft_ohne_karte(self):
        self.regeln = self.regeln + [{'id': 'test-xcopy-frei', 'werkzeug': ['befehl'], 'muster': ['xcopy*'], 'stufe': 'frei', 'begruendung': 'Test'}]
        (self.root / 'docs' / 'neu.txt').write_text('OK', encoding='utf-8')
        (self.root / 'docs' / 'sub').mkdir()
        r = self.kiste(master=None).aufruf('befehl', {'befehl': 'xcopy docs\\neu.txt docs\\sub\\ /Y', 'ordner': '.'})
        self.assertNotEqual(r['status'], 'wartet', r)
        self.assertEqual((self.root / 'docs' / 'sub' / 'neu.txt').read_text(encoding='utf-8'), 'OK')

    def test_eine_aufgabe_mit_dem_muster_wird_schon_beim_anlegen_abgewiesen(self):
        grund_ = vorbehalte.pruefen('befehl', 'xcopy docs\\* local_config\\*', {'ordner': '.'})
        self.assertIsNotNone(grund_)


if __name__ == '__main__':
    unittest.main()
