"""U3 der Harness-Shell Stufe 2: feste Captain-Vorbehalte (HS-28)."""
import unittest

from guppi_runtime.harness import vorbehalte


class VorbehalteTests(unittest.TestCase):
    def test_geschuetzte_pfade(self):
        for pfad in ('local_config/switches.yaml', 'workspace/GUPPI_OS/local_config/x.yaml', 'runtime/config/freigabe_katalog.beispiel.yaml',
                     'runtime/src/guppi_runtime/core/guard.py', 'runtime/src/guppi_runtime/harness/freigabe.py',
                     'runtime/src/guppi_runtime/harness/vorbehalte.py', 'runtime/src/guppi_runtime/harness/befehl.py',
                     'runtime/src/guppi_runtime/devenv/model_tools.py', 'runtime/benchmarks/devvm_build.py',
                     'architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT/core/guard/guard_rules.yaml', '.git/config',
                     'RUNTIME\\SRC\\guppi_runtime\\Core\\x.py', '../anderes/datei.txt'):
            for w in ('datei_schreiben', 'datei_aendern'):
                self.assertIsNotNone(vorbehalte.pruefen(w, pfad, {'inhalt': 'x'}), (w, pfad))

    def test_freie_pfade_haben_keinen_vorbehalt(self):
        for pfad in ('docs/LOGBUCH_AGENT_MANAGER.md', 'runtime/src/guppi_runtime/harness/schleife.py', 'runtime/tests/test_x.py'):
            self.assertIsNone(vorbehalte.pruefen('datei_aendern', pfad, {'alt': 'a', 'neu': 'b'}), pfad)

    def test_lesen_hat_keinen_vorbehalt(self):
        # Lesen regelt der Katalog (lesen-geheim); Vorbehalte gelten für Wirkung und Befehle
        self.assertIsNone(vorbehalte.pruefen('datei_lesen', 'local_config/switches.yaml'))

    def test_befehle(self):
        for zeile in ('git push origin main', 'GIT  PUSH', 'git branch -f main HEAD', 'git reset --hard HEAD~1', 'del x', 'rm -rf docs', 'rmdir x',
                      'Remove-Item -Recurse x', 'format c:', 'curl http://x', 'wget x', 'Invoke-WebRequest x', 'pip install requests', 'winget install x'):
            self.assertIsNotNone(vorbehalte.pruefen('befehl', zeile), zeile)
        for zeile in ('git status', 'git log -3', 'python benchmarks/run_tests.py harness', 'rmx', 'deliver.bat', 'formatter.py'):
            self.assertIsNone(vorbehalte.pruefen('befehl', zeile), zeile)

    def test_leer_ueberschreiben(self):
        self.assertIsNotNone(vorbehalte.pruefen('datei_schreiben', 'docs/x.md', {'inhalt': '  '}, vorhanden=True))
        self.assertIsNone(vorbehalte.pruefen('datei_schreiben', 'docs/x.md', {'inhalt': ''}, vorhanden=False))


if __name__ == '__main__':
    unittest.main()
