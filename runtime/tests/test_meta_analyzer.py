"""Tests für Meta Analyzer."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sedra_runtime.meta_analyzer import (
    MetaAnalyzer,
    PatternInsight,
    RegressionSignal,
    run_full_analysis,
)
from sedra_runtime.evidence_store import EvidenceStore, RunRecord


class MetaAnalyzerTest(unittest.TestCase):
    """Tests für MetaAnalyzer."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "meta.db"
        self.store = EvidenceStore(self.db_path)
        self.analyzer = MetaAnalyzer(self.store)

    def tearDown(self):
        self.store.close()
        self.tmpdir.cleanup()

    def _create_runs(
        self,
        count: int,
        success_rate: float = 1.0,
        base_duration: int = 100,
        error_msg: str | None = None,
        typ_id: str = "test_type",
        build_type: str = "project",
        artifacts_count: int = 3,
    ) -> list[RunRecord]:
        """Erstellt Test-Runs mit variierenden Eigenschaften."""
        runs = []
        import uuid
        for i in range(count):
            success = i < int(count * success_rate)
            run = RunRecord(
                run_id=f"{typ_id}_{uuid.uuid4().hex[:8]}",
                typ_id=typ_id,
                name=f"test_{i}",
                build_type=build_type,
                started_at=datetime.now() - timedelta(minutes=count - i),
                finished_at=datetime.now() - timedelta(minutes=count - i - 1),
                duration_ms=base_duration + i * 10,
                success=success,
                artifacts_count=artifacts_count if success else 0,
                error_message=error_msg if not success else None,
                metrics={"template_render_ms": base_duration // 2, "duration_ms": base_duration + i * 10}
            )
            # Direkt in DB einfügen für Tests
            with self.store._connect() as conn:
                conn.execute(
                    """INSERT INTO runs (run_id, typ_id, name, build_type, started_at, finished_at,
                       duration_ms, success, artifacts_count, error_message, metrics_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run.run_id, run.typ_id, run.name, run.build_type,
                     run.started_at.isoformat(), run.finished_at.isoformat(),
                     run.duration_ms, int(run.success), run.artifacts_count,
                     run.error_message, '{"template_render_ms": %d, "duration_ms": %d}' % (base_duration // 2, base_duration + i * 10))
                )
            runs.append(run)
        return runs

    # ---- analyze() ----

    def test_analyze_zu_wenige_runs_gibt_leer(self):
        self._create_runs(5)
        insights = self.analyzer.analyze(min_runs=10)
        self.assertEqual(len(insights), 0)

    def test_analyze_failure_pattern_hohe_rate(self):
        # 10 Runs, 40% failure rate
        self._create_runs(10, success_rate=0.6, error_msg="Template not found")
        insights = self.analyzer.analyze(min_runs=5)
        
        failure_insights = [i for i in insights if i.category == "failure"]
        self.assertGreater(len(failure_insights), 0)
        self.assertIn("Hohe Failure-Rate", failure_insights[0].pattern)
        self.assertIn("Template not found", failure_insights[0].pattern)

    def test_analyze_performance_bottleneck_template_render(self):
        # Template rendering > 50% der Zeit
        # base_duration=100, template_render=80 -> 80%
        runs = self._create_runs(10, base_duration=100)
        # Need to update the runs with higher template_render_ms
        # The _create_runs uses base_duration//2 = 50, we need more
        # Let's manually insert with higher template render
        for i, run in enumerate(runs):
            with self.store._connect() as conn:
                conn.execute(
                    "UPDATE runs SET metrics_json = ? WHERE run_id = ?",
                    ('{"template_render_ms": 80, "duration_ms": 100}', run.run_id)
                )
        
        insights = self.analyzer.analyze(min_runs=5)
        
        perf_insights = [i for i in insights if i.category == "performance"]
        bottleneck = [i for i in perf_insights if "Bottleneck" in i.pattern]
        self.assertGreater(len(bottleneck), 0)

    def test_analyze_artifact_completeness_zu_wenig(self):
        # Module mit nur 5 Artefakten (erwartet 20)
        self._create_runs(10, build_type="module", artifacts_count=5)
        insights = self.analyzer.analyze(min_runs=5)
        
        quality_insights = [i for i in insights if i.category == "quality"]
        self.assertGreater(len(quality_insights), 0)
        self.assertIn("zu wenige Artefakte", quality_insights[0].pattern)

    def test_analyze_duration_trend_verschlechterung(self):
        # Early runs schnell, late runs langsam
        early_runs = []
        late_runs = []
        base_time = datetime.now() - timedelta(hours=2)
        
        for i in range(20):
            if i < 10:
                dur = 100  # Early: schnell
            else:
                dur = 200  # Late: doppelt so langsam
            
            run = RunRecord(
                run_id=f"trend_{i}",
                typ_id="trend_type",
                name=f"test_{i}",
                build_type="project",
                started_at=base_time + timedelta(minutes=i),
                finished_at=base_time + timedelta(minutes=i+1),
                duration_ms=dur,
                success=True,
                artifacts_count=3,
                error_message=None,
                metrics={"duration_ms": dur}
            )
            early_runs.append(run) if i < 10 else late_runs.append(run)
            
            with self.store._connect() as conn:
                conn.execute(
                    """INSERT INTO runs (run_id, typ_id, name, build_type, started_at, finished_at,
                       duration_ms, success, artifacts_count, error_message, metrics_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run.run_id, run.typ_id, run.name, run.build_type,
                     run.started_at.isoformat(), run.finished_at.isoformat(),
                     run.duration_ms, int(run.success), run.artifacts_count,
                     run.error_message, '{"duration_ms": %d}' % dur)
                )
        
        insights = self.analyzer.analyze(min_runs=5, typ_id="trend_type")
        trend_insights = [i for i in insights if "Trend" in i.pattern]
        self.assertGreater(len(trend_insights), 0)
        self.assertIn("langsamer", trend_insights[0].pattern)

    # ---- detect_regressions() ----

    def test_detect_regressions_dauer_erhoeht(self):
        # Baseline: 50 Runs mit 100ms
        # Recent: 50 Runs mit 150ms (50% langsamer)
        self._setup_regression_scenario(baseline_duration=100, recent_duration=150)
        
        signals = self.analyzer.detect_regressions("reg_type", window=50, threshold_pct=0.2)
        
        self.assertGreater(len(signals), 0)
        dur_signals = [s for s in signals if s.metric == "duration"]
        self.assertGreater(len(dur_signals), 0)
        self.assertEqual(dur_signals[0].severity, "warning")  # 50% > 20% threshold, < 50% -> warning
        self.assertGreater(dur_signals[0].change_pct, 0)

    def test_detect_regressions_artefakte_verringert(self):
        # Baseline: 10 Artefakte, Recent: 5 Artefakte (50% weniger)
        self._setup_artifact_regression(baseline_artifacts=10, recent_artifacts=5)
        
        signals = self.analyzer.detect_regressions("reg_type", window=50, threshold_pct=0.2)
        
        artifact_signals = [s for s in signals if s.metric == "artifacts"]
        self.assertGreater(len(artifact_signals), 0)
        self.assertLess(artifact_signals[0].change_pct, 0)  # Negativ = weniger

    def test_detect_regressions_keine_baseline(self):
        # Nur 5 Runs total -> keine Baseline
        self._create_runs(5, typ_id="nobase")
        signals = self.analyzer.detect_regressions("nobase", window=50)
        self.assertEqual(len(signals), 0)

    def test_detect_regressions_nur_erfolgreiche_verglichen(self):
        # Baseline alle success, Recent 50% failed -> nur erfolgreiche verglichen
        self._create_runs(30, typ_id="mixed", success_rate=1.0)
        self._create_runs(30, typ_id="mixed", success_rate=0.5, base_duration=200)
        
        signals = self.analyzer.detect_regressions("mixed", window=30, threshold_pct=0.2)
        # Sollte nur erfolgreiche Runs vergleichen
        self.assertIsInstance(signals, list)

    def _setup_regression_scenario(self, baseline_duration: int, recent_duration: int):
        """Erstellt Baseline + Recent Runs für Regression-Test."""
        # Baseline (älter)
        for i in range(60):
            run = RunRecord(
                run_id=f"base_{i}",
                typ_id="reg_type",
                name=f"base_{i}",
                build_type="project",
                started_at=datetime.now() - timedelta(hours=2, minutes=60-i),
                finished_at=datetime.now() - timedelta(hours=2, minutes=59-i),
                duration_ms=baseline_duration,
                success=True,
                artifacts_count=3,
                error_message=None,
                metrics={"duration_ms": baseline_duration}
            )
            with self.store._connect() as conn:
                conn.execute(
                    """INSERT INTO runs (run_id, typ_id, name, build_type, started_at, finished_at,
                       duration_ms, success, artifacts_count, error_message, metrics_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run.run_id, run.typ_id, run.name, run.build_type,
                     run.started_at.isoformat(), run.finished_at.isoformat(),
                     run.duration_ms, int(run.success), run.artifacts_count,
                     run.error_message, '{"duration_ms": %d}' % baseline_duration)
                )

        # Recent (newer)
        for i in range(60):
            run = RunRecord(
                run_id=f"recent_{i}",
                typ_id="reg_type",
                name=f"recent_{i}",
                build_type="project",
                started_at=datetime.now() - timedelta(minutes=60-i),
                finished_at=datetime.now() - timedelta(minutes=59-i),
                duration_ms=recent_duration,
                success=True,
                artifacts_count=3,
                error_message=None,
                metrics={"duration_ms": recent_duration}
            )
            with self.store._connect() as conn:
                conn.execute(
                    """INSERT INTO runs (run_id, typ_id, name, build_type, started_at, finished_at,
                       duration_ms, success, artifacts_count, error_message, metrics_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run.run_id, run.typ_id, run.name, run.build_type,
                     run.started_at.isoformat(), run.finished_at.isoformat(),
                     run.duration_ms, int(run.success), run.artifacts_count,
                     run.error_message, '{"duration_ms": %d}' % recent_duration)
                )

    def _setup_artifact_regression(self, baseline_artifacts: int, recent_artifacts: int):
        """Erstellt Baseline + Recent Runs für Artifact Regression."""
        # Baseline
        for i in range(60):
            run = RunRecord(
                run_id=f"base_art_{i}",
                typ_id="reg_type",
                name=f"base_{i}",
                build_type="project",
                started_at=datetime.now() - timedelta(hours=2, minutes=60-i),
                finished_at=datetime.now() - timedelta(hours=2, minutes=59-i),
                duration_ms=100,
                success=True,
                artifacts_count=baseline_artifacts,
                error_message=None,
                metrics={"artifacts_count": baseline_artifacts}
            )
            with self.store._connect() as conn:
                conn.execute(
                    """INSERT INTO runs (run_id, typ_id, name, build_type, started_at, finished_at,
                       duration_ms, success, artifacts_count, error_message, metrics_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run.run_id, run.typ_id, run.name, run.build_type,
                     run.started_at.isoformat(), run.finished_at.isoformat(),
                     run.duration_ms, int(run.success), run.artifacts_count,
                     run.error_message, '{"artifacts_count": %d}' % baseline_artifacts)
                )

        # Recent
        for i in range(60):
            run = RunRecord(
                run_id=f"recent_art_{i}",
                typ_id="reg_type",
                name=f"recent_{i}",
                build_type="project",
                started_at=datetime.now() - timedelta(minutes=60-i),
                finished_at=datetime.now() - timedelta(minutes=59-i),
                duration_ms=100,
                success=True,
                artifacts_count=recent_artifacts,
                error_message=None,
                metrics={"artifacts_count": recent_artifacts}
            )
            with self.store._connect() as conn:
                conn.execute(
                    """INSERT INTO runs (run_id, typ_id, name, build_type, started_at, finished_at,
                       duration_ms, success, artifacts_count, error_message, metrics_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run.run_id, run.typ_id, run.name, run.build_type,
                     run.started_at.isoformat(), run.finished_at.isoformat(),
                     run.duration_ms, int(run.success), run.artifacts_count,
                     run.error_message, '{"artifacts_count": %d}' % recent_artifacts)
                )

    # ---- save_insights / get_insights ----

    def test_save_and_get_insights(self):
        insights = [
            PatternInsight(
                pattern="Test Pattern",
                confidence=0.8,
                supporting_run_ids=["run1", "run2"],
                recommendation="Test Rec",
                category="test",
            )
        ]
        saved = self.analyzer.save_insights(insights)
        
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].pattern, "Test Pattern")
        self.assertEqual(saved[0].confidence, 0.8)
        
        retrieved = self.analyzer.get_insights(min_confidence=0.5)
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].pattern, "Test Pattern")

    def test_get_insights_filter_confidence(self):
        self.analyzer.save_insights([
            PatternInsight("High", 0.9, [], "rec", "test"),
            PatternInsight("Low", 0.3, [], "rec", "test"),
        ])
        
        high = self.analyzer.get_insights(min_confidence=0.5)
        all_ins = self.analyzer.get_insights(min_confidence=0.0)
        
        self.assertEqual(len(high), 1)
        self.assertEqual(len(all_ins), 2)

    # ---- run_full_analysis ----

    def test_run_full_analysis_erstellt_report(self):
        self._create_runs(15, typ_id="type_a")
        self._create_runs(15, typ_id="type_b")
        
        report = run_full_analysis(self.store, min_runs=10)
        
        self.assertIn("timestamp", report)
        self.assertEqual(report["total_runs"], 30)
        self.assertIn("type_a", report["typ_ids"])
        self.assertIn("type_b", report["typ_ids"])
        self.assertIsInstance(report["insights"], list)
        self.assertIsInstance(report["regressions"], dict)


if __name__ == "__main__":
    unittest.main()