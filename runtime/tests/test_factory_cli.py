"""F2-02: Tests für Factory CLI-Kommandos."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.factory_registry import FactoryRegistry
from sedra_runtime.factory_builder import FactoryBuilder
from sedra_runtime.cli import main as cli_main


class FactoryCLITest(unittest.TestCase):
    """Integrationstests für factory CLI-Kommandos."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run_cli(self, *args):
        """Führt CLI-Kommando aus und gibt (exit_code, parsed_json) zurück."""
        import sys
        from io import StringIO

        # Architecture root required by runtime
        arch_root = Path("E:/Sedra Umgebung/A1 Sedra Main Branch Entwicklungs umgebung/architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT")
        full_args = ['--root', str(self.root), '--architecture', str(arch_root), *args]

        old_argv = sys.argv
        old_stdout = sys.stdout
        try:
            sys.argv = ['sedra', *full_args]
            sys.stdout = StringIO()
            exit_code = cli_main()
            output = sys.stdout.getvalue()
        except SystemExit as e:
            exit_code = e.code
            output = sys.stdout.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout

        try:
            parsed = json.loads(output) if output.strip() else None
        except json.JSONDecodeError:
            parsed = output
        return exit_code, parsed

    # ---- register ----

    def test_factory_register_erstellt_typ(self):
        code, out = self._run_cli('--root', str(self.root), 'factory', 'register', 'test_proj', 'Test Project', '--functions', 'build,deploy', '--manifest-ref', 'test.json', '--gate')
        self.assertEqual(code, 0)
        self.assertEqual(out['typ_id'], 'test_proj')
        self.assertEqual(out['name'], 'Test Project')
        self.assertEqual(out['zustand'], 'registered')
        self.assertEqual(out['funktionen'], ['build', 'deploy'])

    def test_factory_register_ohne_gate_funktioniert_ohne_gate_permission(self):
        # Register ohne --gate funktioniert, aber Typ hat keine Gate-Permission
        code, out = self._run_cli('--root', str(self.root), 'factory', 'register', 'test_proj2', 'Test Project 2', '--functions', 'build')
        self.assertEqual(code, 0)
        self.assertEqual(out['zustand'], 'registered')
        # Gate-Permission sollte nicht gesetzt sein
        self.assertFalse(out.get('gate_freigabe', False))

    def test_factory_build_project_ohne_gate_schlaegt_fehl(self):
        # Build braucht Gate-Permission
        self._run_cli('--root', str(self.root), 'factory', 'register', 'bp_nogate', 'NoGate', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-project', 'bp_nogate', 'my_project')
        self.assertEqual(code, 2)
        self.assertFalse(out['success'])
        self.assertIn('gate_required', out['message'])

    def test_factory_register_doppelter_typ_schlaegt_fehl(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'test_dup', 'Test Dup', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'register', 'test_dup', 'Test Dup', '--gate')
        self.assertEqual(code, 2)
        self.assertIn('typ_bereits_registriert', str(out))

    # ---- list ----

    def test_factory_list_zeigt_registrierte_typen(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'list_a', 'List A', '--gate')
        self._run_cli('--root', str(self.root), 'factory', 'register', 'list_b', 'List B', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'list')
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 2)
        typ_ids = {t['typ_id'] for t in out}
        self.assertEqual(typ_ids, {'list_a', 'list_b'})

    def test_factory_list_leer_am_anfang(self):
        code, out = self._run_cli('--root', str(self.root), 'factory', 'list')
        self.assertEqual(code, 0)
        self.assertEqual(out, [])

    # ---- build-project ----

    def test_factory_build_project_erzeugt_projekt(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'bp_type', 'BuildProject Type', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-project', 'bp_type', 'my_project', '--gate')
        self.assertEqual(code, 0)
        self.assertTrue(out['success'])
        self.assertIsNotNone(out['path'])
        self.assertEqual(out['message'], 'projekt_erzeugt')
        # Prüfe Dateien
        project_path = Path(out['path'])
        self.assertTrue((project_path / '.gitignore').exists())
        self.assertTrue((project_path / 'pyproject.toml').exists())
        self.assertTrue((project_path / 'README.md').exists())

    def test_factory_build_project_ohne_gate_schlaegt_fehl(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'bp_nogate', 'NoGate', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-project', 'bp_nogate', 'my_project')
        self.assertEqual(code, 2)
        self.assertFalse(out['success'])
        self.assertIn('gate_required', out['message'])

    def test_factory_build_project_unbekannter_typ(self):
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-project', 'unknown', 'proj', '--gate')
        self.assertEqual(code, 2)
        self.assertFalse(out['success'])
        self.assertIn('typ_unbekannt', out['message'])

    def test_factory_build_project_bestehendes_projekt_schlaegt_fehl(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'bp_exist', 'Exist', '--gate')
        self._run_cli('--root', str(self.root), 'factory', 'build-project', 'bp_exist', 'existing', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-project', 'bp_exist', 'existing', '--gate')
        self.assertEqual(code, 2)
        self.assertFalse(out['success'])
        self.assertIn('projekt_existiert', out['message'])

    # ---- build-module ----

    def test_factory_build_module_erzeugt_modul(self):
        # Project type registrieren und Projekt bauen
        self._run_cli('--root', str(self.root), 'factory', 'register', 'project_type', 'Project Type', '--gate')
        self._run_cli('--root', str(self.root), 'factory', 'build-project', 'project_type', 'parent_project', '--gate')
        # Module type registrieren
        self._run_cli('--root', str(self.root), 'factory', 'register', 'mod_type', 'Module Type', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-module', 'mod_type', 'my_module', '--project', str(self.root / 'parent_project'), '--gate')
        self.assertEqual(code, 0)
        self.assertTrue(out['success'])
        module_path = Path(out['path'])
        # Prüfe 5 Layer
        for layer in ['domain', 'application', 'infrastructure', 'ai', 'app']:
            self.assertTrue((module_path / layer / '__init__.py').exists(), f"Layer {layer} fehlt")
        # Prüfe Sub-Packages
        self.assertTrue((module_path / 'domain' / 'entities' / '__init__.py').exists())
        self.assertTrue((module_path / 'application' / 'dtos' / '__init__.py').exists())

    def test_factory_build_module_ohne_projekt_schlaegt_fehl(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'mod_noproj', 'NoProj', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-module', 'mod_noproj', 'mod', '--project', str(self.root / 'nonexistent'), '--gate')
        self.assertEqual(code, 2)
        self.assertFalse(out['success'])
        self.assertIn('projekt_nicht_gefunden', out['message'])

    # ---- build-service ----

    def test_factory_build_service_erzeugt_service(self):
        # Project type registrieren und Projekt bauen
        self._run_cli('--root', str(self.root), 'factory', 'register', 'project_type', 'Project Type', '--gate')
        self._run_cli('--root', str(self.root), 'factory', 'build-project', 'project_type', 'svc_parent', '--gate')
        # Service type registrieren
        self._run_cli('--root', str(self.root), 'factory', 'register', 'svc_type', 'Service Type', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'build-service', 'svc_type', 'my_service', '--project', str(self.root / 'svc_parent'), '--gate')
        self.assertEqual(code, 0)
        self.assertTrue(out['success'])
        svc_path = Path(out['path'])
        self.assertTrue((svc_path / 'README.md').exists())
        self.assertTrue((svc_path / 'docker' / 'Dockerfile').exists())
        self.assertTrue((svc_path / 'docker' / 'docker-compose.yml').exists())
        self.assertTrue((svc_path / 'n8n' / 'workflow.json').exists())
        self.assertTrue((svc_path / 'systemd' / 'my_service.service').exists())

    # ---- status ----

    def test_factory_status_zeigt_typ_info(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'status_type', 'Status Type', '--functions', 'fn1', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'status', 'status_type')
        self.assertEqual(code, 0)
        self.assertEqual(out['typ_id'], 'status_type')
        self.assertEqual(out['name'], 'Status Type')
        self.assertEqual(out['funktionen'], ['fn1'])
        self.assertTrue(out['gate_freigabe'])

    def test_factory_status_unbekannt_schlaegt_fehl(self):
        code, out = self._run_cli('--root', str(self.root), 'factory', 'status', 'unknown')
        self.assertEqual(code, 2)
        self.assertEqual(out['status'], 'not_found')

    # ---- transition ----

    def test_factory_transition_registered_ready(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'trans_type', 'Transition Type', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'transition', 'trans_type', 'ready', '--gate')
        self.assertEqual(code, 0)
        self.assertEqual(out['zustand'], 'ready')

    def test_factory_transition_ohne_gate_schlaegt_fehl(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'trans_nogate', 'NoGate', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'transition', 'trans_nogate', 'ready')
        self.assertEqual(code, 2)
        self.assertIn('gate_freigabe_erforderlich', str(out))

    def test_factory_transition_ungueltig_schlaegt_fehl(self):
        self._run_cli('--root', str(self.root), 'factory', 'register', 'trans_inv', 'Invalid', '--gate')
        code, out = self._run_cli('--root', str(self.root), 'factory', 'transition', 'trans_inv', 'active', '--gate')  # registered -> active nicht erlaubt
        self.assertEqual(code, 2)
        self.assertIn('ungueltiger_uebergang', str(out))

    # ---- Persistenz ----

    def test_factory_persistenz_ueberlebt_neustart(self):
        # Registrierung
        self._run_cli('--root', str(self.root), 'factory', 'register', 'persist_type', 'Persist', '--functions', 'f1', '--gate')
        # Neuer CLI-Aufruf (simuliert Neustart)
        code, out = self._run_cli('--root', str(self.root), 'factory', 'list')
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['typ_id'], 'persist_type')
        self.assertEqual(out[0]['funktionen'], ['f1'])


class FactoryRegistryPersistTest(unittest.TestCase):
    """Direkte Tests für FactoryRegistry Save/Load."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / 'registry.json'

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_load_roundtrip(self):
        reg = FactoryRegistry()
        reg.registriere_typ('rt1', 'Roundtrip', ['fn1', 'fn2'], 'manifest.json', gate_freigabe=True)
        reg.wechsel_zustand('rt1', 'ready', gate_freigabe=True)
        reg.save(self.path)

        loaded = FactoryRegistry.load(self.path)
        self.assertEqual(len(loaded._typen), 1)
        ft = loaded.get('rt1')
        self.assertEqual(ft.typ_id, 'rt1')
        self.assertEqual(ft.name, 'Roundtrip')
        self.assertEqual(ft.functionen, {'fn1', 'fn2'})
        self.assertEqual(ft.zustand, 'ready')
        self.assertEqual(ft.manifest_ref, 'manifest.json')
        self.assertTrue('rt1' in loaded._gate_erlaubt)

    def test_load_nicht_existente_datei(self):
        loaded = FactoryRegistry.load(self.path)
        self.assertEqual(len(loaded._typen), 0)
        self.assertEqual(len(loaded._gate_erlaubt), 0)


if __name__ == '__main__':
    unittest.main()