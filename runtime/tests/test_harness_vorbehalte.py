"""U3 der Harness-Shell Stufe 2: feste Captain-Vorbehalte (HS-28)."""
import unittest

from sedra_runtime.harness import vorbehalte


class VorbehalteTests(unittest.TestCase):
    def test_geschuetzte_pfade(self):
        for pfad in ('local_config/switches.yaml', 'workspace/SEDRA_OS/local_config/x.yaml', 'runtime/config/freigabe_katalog.beispiel.yaml',
                     'runtime/src/sedra_runtime/core/guard.py', 'runtime/src/sedra_runtime/harness/freigabe.py',
                     'runtime/src/sedra_runtime/harness/vorbehalte.py', 'runtime/src/sedra_runtime/harness/befehl.py',
                     'runtime/src/sedra_runtime/devenv/model_tools.py', 'runtime/benchmarks/devvm_build.py',
                     'architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT/core/guard/guard_rules.yaml', '.git/config',
                     'RUNTIME\\SRC\\sedra_runtime\\Core\\x.py', '../anderes/datei.txt',
                     'runtime/src/sedra_runtime/harness/erlaubnis.py', 'runtime/src/sedra_runtime/harness/katalog.py',          # Captain 05.11.2026 (U5, U7)
                     'runtime/src/sedra_runtime/harness/bausteine.py', 'runtime/config/freigabe_bausteine.yaml', 'docs/AAR/LESSONS.md'):
            for w in ('datei_schreiben', 'datei_aendern'):
                self.assertIsNotNone(vorbehalte.pruefen(w, pfad, {'inhalt': 'x'}), (w, pfad))

    def test_code_der_oberflaeche_ist_hart_geschuetzt(self):
        """Apps v1 O3 (G3 S8): was Vertrauen, Rechte, Routen und Freigaben der Module prüft oder festlegt, ändert das Modell nie ohne Karte des Captains."""
        S = 'runtime/src/sedra_runtime/'
        pfade = (S + 'uix/ui/loader.js', S + 'uix/ui/bruecke.js', S + 'uix/ui/schema/tool.schema.json', S + 'uix/tools/gauge-ram/tool.yaml', S + 'uix/shells/harness/shell.yaml',
                 S + 'uix/shells/gateway-studio/shell.vorgabe.yaml', S + 'uix/shells/harness/arbeitsplatz.yaml', S + 'uix/desk.html', S + 'uix/retro_desktop.html', S + 'uix/js/main.js',
                 S + 'desk/gateway.py', S + 'desk/install.py', S + 'desk/registry.py', S + 'desk/herkunft.py', S + 'desk/routen_pruefung.py', S + 'desk/shell_regeln.py',
                 S + 'desk/manifest_felder.py', S + 'desk/gate_texte.py', S + 'desk/berechtigung.py', S + 'desk/rechte_diff.py', S + 'uix_server.py', S + 'uix_clients.py',
                 S + 'cloud_settings.py', S + 'models/cloud_api.py', 'runtime/config/cloud_providers.yaml', 'runtime/tests/test_freigabe_vollstaendig.py',
                 S + 'harness/oberflaeche.py', 'RUNTIME\\SRC\\sedra_runtime\\Uix\\UI\\Loader.js')
        for pfad in pfade:
            for w in ('datei_schreiben', 'datei_aendern'):
                grund = vorbehalte.pruefen(w, pfad, {'inhalt': 'x', 'alt': 'a', 'neu': 'b'})
                self.assertIsNotNone(grund, (w, pfad))
                self.assertTrue(grund.startswith('Captain-Vorbehalt: '), (w, pfad, grund))

    def test_shells_und_texte_der_oberflaeche_bleiben_frei(self):
        """Der weiche Teil (JS und CSS der Shells) kommt später mit freigabe.py; bis dahin gilt für diese Dateien, was vorher galt."""
        S = 'runtime/src/sedra_runtime/'
        for pfad in (S + 'uix/shells/harness/taskleiste.js', S + 'uix/shells/harness/shell.css', S + 'uix/shells/harness/README.md', S + 'uix/tools/gauge-ram/tool.js',
                     S + 'uix/tools/gauge-ram/README.md', S + 'desk/objects.py', S + 'desk/actions.py', 'runtime/tests/test_desk_gateway.py'):
            self.assertIsNone(vorbehalte.pruefen('datei_aendern', pfad, {'alt': 'a', 'neu': 'b'}), pfad)

    def test_lesen_der_geschuetzten_dateien_bleibt_sache_des_katalogs(self):
        self.assertIsNone(vorbehalte.pruefen('datei_lesen', 'runtime/src/sedra_runtime/uix_server.py'))

    def test_freie_pfade_haben_keinen_vorbehalt(self):
        for pfad in ('docs/LOGBUCH_AGENT_MANAGER.md', 'runtime/src/sedra_runtime/harness/schleife.py', 'runtime/tests/test_x.py'):
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
