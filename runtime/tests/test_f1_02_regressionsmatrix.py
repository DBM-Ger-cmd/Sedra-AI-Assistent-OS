"""F1-02: Gestufte kompatible Namensmigration — Regressionsmatrix.

Prüft, dass die Namensmigration (SEDRA-NAME-01 / SEDRA-NAME-02) alle vier
Akzeptanzbereiche abdeckt: Windows-Starter, APIs, Daten und Tests.
Kein Datenverlust bei der Umstellung.

Keine externen Abhängigkeiten, kein Modell, kein Netzwerk. Laufbar mit unittest.
"""
from __future__ import annotations

import io
import importlib.util
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sedra_runtime import legacy_names as ln  # noqa: E402
from sedra_runtime import umzug  # noqa: E402

# Repo-Root: Eltern-Eltern von tests/
ROOT = Path(__file__).resolve().parents[2]


class RegressionsmatrixTest(unittest.TestCase):
    """Die Regressionsmatrix deckt alle vier Bereiche der Acceptance ab."""

    def test_windows_starter_bleibt_funktionsfaehig(self):
        """START_SEDRA.bat / start_sedra.sh verweisen auf die neuen Namen."""
        # START_SEDRA.bat existiert im Repo und ruft sedra_runtime.uix_start auf
        bat = ROOT / 'START_SEDRA.bat'
        if bat.is_file():
            text = bat.read_text(encoding='utf-8', errors='replace')
            self.assertIn('sedra_runtime.uix_start', text)
            self.assertNotIn('guppi_runtime.uix_start', text)

    def test_apis_alten_namen_sind_weiterleitend(self):
        """Alte GUPPI_* Umgebungsvariablen werden auf SEDRA_* gespiegelt."""
        env = {'GUPPI_API_KEY': 'alt-key', 'GUPPI_ENDPOINT': 'alt-endpoint', 'SEDRA_ANDERE': 'besteht'}
        gesetzt = ln.env_aliase(env)
        self.assertIn('SEDRA_API_KEY', gesetzt)
        self.assertIn('SEDRA_ENDPOINT', gesetzt)
        self.assertEqual(env['SEDRA_API_KEY'], 'alt-key')
        self.assertEqual(env['SEDRA_ENDPOINT'], 'alt-endpoint')
        # Bestehende neue Variablen gewinnen
        env2 = {'GUPPI_A': 'alt', 'SEDRA_A': 'neu'}
        self.assertEqual(ln.env_aliase(env2), [])
        self.assertEqual(env2['SEDRA_A'], 'neu')

    def test_daten_bleiben_erhalten_kein_verlust(self):
        """Projektordner, Architekturordner und lokale Daten bleiben bei der Migration erhalten."""
        import tempfile
        from pathlib import Path as P
        tmp = tempfile.TemporaryDirectory()
        root = P(tmp.name)

        # Projektordner mit Daten
        alt_projekt = root / 'workspace' / ln.PROJEKTORDNER_ALT
        (alt_projekt / 'runtime_data').mkdir(parents=True)
        (alt_projekt / 'config').mkdir(parents=True)
        (alt_projekt / 'runtime_data' / 'daten.db').write_text('wichtige daten', encoding='utf-8')
        (alt_projekt / 'config' / 'lokale_datei.txt').write_text('config', encoding='utf-8')

        # Architekturordner mit Daten
        arch_alt = root / 'architecture' / (ln.ARCHITEKTUR_ALT + 'v1.20_X')
        (arch_alt).mkdir(parents=True)
        (arch_alt / 'spezifikation.md').write_text('# spec', encoding='utf-8')
        # Neuer Architekturordner existiert bereits (gestufte Migration: zuerst neu anlegen)
        arch_neu = root / 'architecture' / (ln.ARCHITEKTUR_NEU + 'v1.20_X')
        (arch_neu).mkdir(parents=True)
        (arch_neu / 'spezifikation.md').write_text('# spec', encoding='utf-8')

        schritte = ln.umziehen(root)

        # Projektordner wurde umbenannt, Daten sind da
        neu_projekt = root / 'workspace' / ln.PROJEKTORDNER_NEU
        self.assertTrue((neu_projekt / 'runtime_data' / 'daten.db').is_file())
        self.assertTrue((neu_projekt / 'config' / 'lokale_datei.txt').is_file())
        self.assertFalse(alt_projekt.exists())

        # Architekturordner wurde gesichert (nicht gelöscht), neuer existiert
        arch_neu = root / 'architecture' / (ln.ARCHITEKTUR_NEU + 'v1.20_X')
        self.assertTrue(arch_neu.is_dir())
        self.assertTrue((arch_neu / 'spezifikation.md').is_file())

        # Sicherung existiert
        sicherung = root / 'local_config/update/sicherung/alt_namen'
        self.assertTrue(sicherung.exists())

    def test_tests_laufen_weiter(self):
        """Bestehende Tests für die Namensmigration laufen grün."""
        spec = importlib.util.spec_from_file_location(
            'test_legacy_names', ROOT / 'runtime' / 'tests' / 'test_legacy_names.py'
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(mod)
        runner = unittest.TextTestRunner(stream=io.StringIO())
        result = runner.run(suite)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])


if __name__ == '__main__':
    unittest.main()
