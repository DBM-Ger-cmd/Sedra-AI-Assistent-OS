"""F2-02: Tests für Factory Builder."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sedra_runtime.factory_registry import FactoryRegistry, FactoryRegistryError
from sedra_runtime.factory_builder import FactoryBuilder, BuildResult


class FactoryBuilderTest(unittest.TestCase):
    """Tests für FactoryBuilder."""

    def setUp(self):
        self.registry = FactoryRegistry()
        self.registry.registriere_typ("test_project", "Test Project", ["build"], gate_freigabe=True)
        self.registry.registriere_typ("test_module", "Test Module", ["build"], gate_freigabe=True)
        self.registry.registriere_typ("test_service", "Test Service", ["deploy"], gate_freigabe=True)

    def _make_builder(self, tmp: Path) -> FactoryBuilder:
        return FactoryBuilder(self.registry, tmp)

    # ---- build_project ----

    def test_build_project_erzeugt_projekt(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = self._make_builder(Path(tmp))
            result = builder.build_project("test_project", "my_project", gate_freigabe=True)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.path)
            self.assertTrue(result.path.exists())
            self.assertEqual(result.message, "projekt_erzeugt")

            # Prüfe erwartete Dateien
            expected = [".gitignore", "pyproject.toml", "README.md"]
            for exp in expected:
                self.assertTrue((result.path / exp).exists(), f"Fehlt: {exp}")

    def test_build_project_ohne_gate_schlaegt_fehl(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = self._make_builder(Path(tmp))
            result = builder.build_project("test_project", "my_project", gate_freigabe=False)

            self.assertFalse(result.success)
            self.assertIn("gate_required", result.message)

    def test_build_project_unbekannter_typ_schlaegt_fehl(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = self._make_builder(Path(tmp))
            result = builder.build_project("unbekannt", "my_project", gate_freigabe=True)

            self.assertFalse(result.success)
            self.assertIn("typ_unbekannt", result.message)

    def test_build_project_bestehendes_projekt_schlaegt_fehl(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = self._make_builder(Path(tmp))
            builder.build_project("test_project", "my_project", gate_freigabe=True)
            result = builder.build_project("test_project", "my_project", gate_freigabe=True)

            self.assertFalse(result.success)
            self.assertIn("projekt_existiert", result.message)

    # ---- build_module ----

    def test_build_module_erzeugt_modul_mit_5_layern(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "my_project"
            project_root.mkdir()
            (project_root / "src").mkdir()
            (project_root / "pyproject.toml").write_text("[project]\nname = \"my_project\"\n")

            builder = self._make_builder(Path(tmp))
            result = builder.build_module("test_module", "my_module", project_root, gate_freigabe=True)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.path)
            self.assertTrue(result.path.exists())

            # Prüfe 5 Layer Struktur
            layers = ["domain", "application", "infrastructure", "ai", "app"]
            for layer in layers:
                self.assertTrue((result.path / layer).exists(), f"Layer fehlt: {layer}")
                self.assertTrue((result.path / layer / "__init__.py").exists(), f"__init__.py fehlt in {layer}")

            # Prüfe Sub-Packages
            sub_packages = {
                "domain": ["entities", "value_objects", "events", "repositories"],
                "application": ["use_cases", "dtos", "ports"],
                "infrastructure": ["persistence", "external", "config"],
                "ai": ["models", "prompts", "agents"],
                "app": ["cli", "web", "desktop"],
            }
            for layer, subs in sub_packages.items():
                for sub in subs:
                    self.assertTrue(
                        (result.path / layer / sub / "__init__.py").exists(),
                        f"Sub-package fehlt: {layer}/{sub}"
                    )

    def test_build_module_ohne_gate_schlaegt_fehl(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "my_project"
            project_root.mkdir()
            (project_root / "src").mkdir()

            builder = self._make_builder(Path(tmp))
            result = builder.build_module("test_module", "my_module", project_root, gate_freigabe=False)

            self.assertFalse(result.success)
            self.assertIn("gate_required", result.message)

    def test_build_module_ohne_projekt_schlaegt_fehl(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = self._make_builder(Path(tmp))
            result = builder.build_module("test_module", "my_module", Path(tmp) / "nonexistent", gate_freigabe=True)

            self.assertFalse(result.success)
            self.assertIn("projekt_nicht_gefunden", result.message)

    # ---- build_service ----

    def test_build_service_erzeugt_service_definitionen(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "my_project"
            project_root.mkdir()
            (project_root / "services").mkdir()

            builder = self._make_builder(Path(tmp))
            result = builder.build_service("test_service", "my_service", project_root, gate_freigabe=True)

            self.assertTrue(result.success)
            self.assertIsNotNone(result.path)
            self.assertTrue(result.path.exists())

            # Prüfe Service-Artefakte
            expected = [
                "README.md",
                "docker/Dockerfile",
                "docker/docker-compose.yml",
                "n8n/workflow.json",
                "systemd/my_service.service",  # Dateiname getemplated
            ]
            for exp in expected:
                self.assertTrue((result.path / exp).exists(), f"Service-Artefakt fehlt: {exp}")

    def test_build_service_ohne_gate_schlaegt_fehl(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "my_project"
            project_root.mkdir()
            (project_root / "services").mkdir()

            builder = self._make_builder(Path(tmp))
            result = builder.build_service("test_service", "my_service", project_root, gate_freigabe=False)

            self.assertFalse(result.success)
            self.assertIn("gate_required", result.message)

    # ---- Template-Rendering ----

    def test_template_platzhalter_werden_ersetzt(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = self._make_builder(Path(tmp))
            result = builder.build_project("test_project", "mein_projekt", gate_freigabe=True)

            readme = (result.path / "README.md").read_text(encoding="utf-8")
            self.assertIn("mein_projekt", readme)
            self.assertIn("test_project", readme)
            self.assertIn("Test Project", readme)

    def test_module_template_platzhalter(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "my_project"
            project_root.mkdir()
            (project_root / "src").mkdir()

            builder = self._make_builder(Path(tmp))
            result = builder.build_module("test_module", "mein_modul", project_root, gate_freigabe=True)

            readme = (result.path / "README.md").read_text(encoding="utf-8")
            self.assertIn("mein_modul", readme)
            self.assertIn("test_module", readme)
            self.assertIn("Test Module", readme)
            self.assertIn("my_project", readme)

            # Prüfe Python-Dateien auf MODULE_NAME Platzhalter
            init_py = (result.path / "__init__.py").read_text(encoding="utf-8")
            self.assertIn("mein_modul", init_py)
            self.assertIn("test_module", init_py)


class BuildResultTest(unittest.TestCase):
    """Tests für BuildResult Dataclass."""

    def test_build_result_defaults(self):
        result = BuildResult(success=True, path=Path("/tmp/test"))
        self.assertTrue(result.success)
        self.assertEqual(result.path, Path("/tmp/test"))
        self.assertEqual(result.message, "")
        self.assertEqual(result.artifacts, [])

    def test_build_result_mit_artifacts(self):
        artifacts = [Path("/tmp/a"), Path("/tmp/b")]
        result = BuildResult(success=True, artifacts=artifacts)
        self.assertEqual(result.artifacts, artifacts)


if __name__ == "__main__":
    unittest.main()