"""Tests für Benchmark Runner."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from sedra_runtime.benchmark_runner import (
    BenchmarkRunner,
    BenchmarkConfig,
    BenchmarkResult,
    quick_benchmark,
)
from sedra_runtime.evidence_store import EvidenceStore, RunRecord
from sedra_runtime.factory_builder import FactoryBuilder, BuildResult
from sedra_runtime.factory_registry import FactoryRegistry, FactoryType, REGISTERED


class BenchmarkRunnerTest(unittest.TestCase):
    """Tests für BenchmarkRunner."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "bench.db"
        self.project_root = Path(self.tmpdir.name) / "projects"
        self.project_root.mkdir()
        
        self.store = EvidenceStore(self.db_path)
        self.registry = FactoryRegistry()
        self.registry.registriere_typ("test_proj", "Test Project", ["build"], "manifest.json", gate_freigabe=True)
        self.registry.registriere_typ("test_mod", "Test Module", ["build"], "manifest.json", gate_freigabe=True)
        
        self.builder = FactoryBuilder(self.registry, self.project_root)
        self.runner = BenchmarkRunner(self.store, self.builder, self.registry, self.project_root)

    def tearDown(self):
        self.store.close()
        self.tmpdir.cleanup()

    def _mock_successful_build(self, artifacts_count: int = 3):
        """Mock für erfolgreichen Build."""
        mock_result = MagicMock(spec=BuildResult)
        mock_result.success = True
        mock_result.artifacts = [f"/tmp/file_{i}.txt" for i in range(artifacts_count)]
        mock_result.message = "ok"
        mock_result.path = "/tmp/test_project"
        mock_result.template_render_ms = 50
        return mock_result

    def _mock_failed_build(self, error: str = "Build failed"):
        """Mock für fehlgeschlagenen Build."""
        mock_result = MagicMock(spec=BuildResult)
        mock_result.success = False
        mock_result.artifacts = []
        mock_result.message = error
        mock_result.path = None
        return mock_result

    # ---- run_benchmark ----

    @patch.object(FactoryBuilder, 'build_project')
    def test_run_benchmark_erstellt_ergebnis(self, mock_build):
        mock_build.return_value = self._mock_successful_build(3)
        
        config = BenchmarkConfig(typ_id="test_proj", variant="default", iterations=2)
        result = self.runner.run_benchmark(config)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.typ_id, "test_proj")
        self.assertEqual(result.variant, "default")
        self.assertEqual(len(result.runs), 2)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 1.0)
        self.assertIn("duration_ms", result.aggregated_metrics)
        self.assertIn("artifacts", result.aggregated_metrics)

    @patch.object(FactoryBuilder, 'build_project')
    def test_run_benchmark_mit_fehler(self, mock_build):
        mock_build.return_value = self._mock_failed_build("Template error")
        
        config = BenchmarkConfig(typ_id="test_proj", variant="default", iterations=2)
        result = self.runner.run_benchmark(config)
        
        # Alle Runs failed -> score sollte niedrig sein
        self.assertEqual(len(result.runs), 2)
        self.assertEqual(result.score, 0.0)  # success_rate = 0
        self.assertEqual(result.aggregated_metrics["success_rate"], 0.0)

    @patch.object(FactoryBuilder, 'build_project')
    def test_run_benchmark_mixed_success(self, mock_build):
        mock_build.side_effect = [
            self._mock_successful_build(3),
            self._mock_failed_build("Error"),
            self._mock_successful_build(4),
        ]
        
        config = BenchmarkConfig(typ_id="test_proj", variant="default", iterations=3)
        result = self.runner.run_benchmark(config)
        
        self.assertEqual(len(result.runs), 3)
        self.assertAlmostEqual(result.aggregated_metrics["success_rate"], 2/3)

    @patch.object(FactoryBuilder, 'build_project')
    def test_run_benchmark_warmup(self, mock_build):
        mock_build.return_value = self._mock_successful_build(3)
        
        config = BenchmarkConfig(typ_id="test_proj", variant="default", iterations=2, warmup=2)
        result = self.runner.run_benchmark(config)
        
        # warmup runs + iterations = 4 calls
        self.assertEqual(mock_build.call_count, 4)
        # Aber nur 2 gewertete Runs
        self.assertEqual(len(result.runs), 2)

    # ---- Score Calculation ----

    def test_calculate_score_perfect(self):
        runs = [
            RunRecord("r1", "t", "n", "project", datetime.now(), datetime.now(), 100, True, 3, None, {}),
            RunRecord("r2", "t", "n", "project", datetime.now(), datetime.now(), 100, True, 3, None, {}),
        ]
        config = BenchmarkConfig(typ_id="t", build_type="project")
        score = self.runner._calculate_score(runs, config)
        self.assertEqual(score, 1.0)

    def test_calculate_score_all_failed(self):
        runs = [
            RunRecord("r1", "t", "n", "project", datetime.now(), datetime.now(), 100, False, 0, "err", {}),
            RunRecord("r2", "t", "n", "project", datetime.now(), datetime.now(), 100, False, 0, "err", {}),
        ]
        config = BenchmarkConfig(typ_id="t", build_type="project")
        score = self.runner._calculate_score(runs, config)
        self.assertEqual(score, 0.0)

    def test_calculate_score_slow_builds(self):
        # Sehr langsame Builds -> niedriger duration_score
        runs = [
            RunRecord("r1", "t", "n", "project", datetime.now(), datetime.now(), 50000, True, 3, None, {}),
            RunRecord("r2", "t", "n", "project", datetime.now(), datetime.now(), 60000, True, 3, None, {}),
        ]
        config = BenchmarkConfig(typ_id="t", build_type="project")
        score = self.runner._calculate_score(runs, config)
        # success=1.0, duration_score~0.02, artifact=1.0 -> ~0.5*1 + 0.3*0.02 + 0.2*1 = 0.706
        self.assertLess(score, 0.8)
        self.assertGreater(score, 0.5)

    # ---- compare_variants ----

    @patch.object(FactoryBuilder, 'build_project')
    def test_compare_variants(self, mock_build):
        mock_build.return_value = self._mock_successful_build(3)
        
        variants = [
            BenchmarkConfig(typ_id="test_proj", variant="v1", iterations=1),
            BenchmarkConfig(typ_id="test_proj", variant="v2", iterations=1),
        ]
        results = self.runner.compare_variants("test_proj", variants)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].variant, "v1")
        self.assertEqual(results[1].variant, "v2")

    # ---- Module/Service Builds ----

    @patch.object(FactoryBuilder, 'build_module')
    def test_run_benchmark_module(self, mock_build):
        mock_build.return_value = self._mock_successful_build(20)
        
        # Erst Projekt bauen
        project_result = self.builder.build_project("test_proj", "parent_proj", gate_freigabe=True)
        
        config = BenchmarkConfig(
            typ_id="test_mod",
            variant="default",
            iterations=1,
            build_type="module",
            project_name="parent_proj"
        )
        result = self.runner.run_benchmark(config)
        
        self.assertEqual(len(result.runs), 1)
        self.assertEqual(result.runs[0].build_type, "module")

    @patch.object(FactoryBuilder, 'build_service')
    def test_run_benchmark_service(self, mock_build):
        mock_build.return_value = self._mock_successful_build(6)
        
        project_result = self.builder.build_project("test_proj", "parent_proj", gate_freigabe=True)
        
        config = BenchmarkConfig(
            typ_id="test_mod",
            variant="default",
            iterations=1,
            build_type="service",
            project_name="parent_proj"
        )
        result = self.runner.run_benchmark(config)
        
        self.assertEqual(len(result.runs), 1)
        self.assertEqual(result.runs[0].build_type, "service")

    # ---- Evidence Store Integration ----

    @patch.object(FactoryBuilder, 'build_project')
    def test_runs_in_store_gespeichert(self, mock_build):
        mock_build.return_value = self._mock_successful_build(3)
        
        config = BenchmarkConfig(typ_id="test_proj", variant="default", iterations=2)
        self.runner.run_benchmark(config)
        
        # Im Store nachschauen
        runs = self.store.list_runs(typ_id="test_proj", limit=10)
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(r.success for r in runs))
        
        benchmarks = self.store.get_benchmarks("test_proj")
        self.assertEqual(len(benchmarks), 1)
        self.assertEqual(benchmarks[0].variant, "default")

    # ---- quick_benchmark ----

    @patch.object(FactoryBuilder, 'build_project')
    def test_quick_benchmark(self, mock_build):
        mock_build.return_value = self._mock_successful_build(3)
        
        result = quick_benchmark(
            self.store, self.builder, self.registry,
            "test_proj", variant="quick", iterations=2
        )
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.variant, "quick")
        self.assertEqual(len(result.runs), 2)


if __name__ == "__main__":
    unittest.main()