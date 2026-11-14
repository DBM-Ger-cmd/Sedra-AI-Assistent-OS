"""Tests für Evidence Store."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sedra_runtime.evidence_store import (
    EvidenceStore,
    RunRecord,
    BenchmarkRecord,
    GateEvidenceRecord,
    MetaInsightRecord,
)


class EvidenceStoreTest(unittest.TestCase):
    """Tests für EvidenceStore CRUD-Operationen."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "evidence.db"
        self.store = EvidenceStore(self.db_path)

    def tearDown(self):
        self.store.close()
        self.tmpdir.cleanup()

    # ──────────────────────────────────────────────
    # Runs
    # ──────────────────────────────────────────────

    def test_record_run_start_erzeugt_record(self):
        run = self.store.record_run_start("test_type", "my_project", "project")
        self.assertIsInstance(run, RunRecord)
        self.assertEqual(run.typ_id, "test_type")
        self.assertEqual(run.name, "my_project")
        self.assertEqual(run.build_type, "project")
        self.assertFalse(run.success)
        self.assertEqual(run.artifacts_count, 0)
        self.assertIsNotNone(run.started_at)
        self.assertIsNone(run.finished_at)

    def test_record_run_start_mit_custom_id(self):
        run = self.store.record_run_start("t1", "n1", "project", run_id="custom-id-123")
        self.assertEqual(run.run_id, "custom-id-123")

    def test_record_run_end_aktualisiert_erfolgreich(self):
        run = self.store.record_run_start("t1", "n1", "project")
        from pathlib import Path
        artifacts = [Path("/tmp/a.txt"), Path("/tmp/b.txt")]
        
        finished = self.store.record_run_end(run.run_id, success=True, artifacts=artifacts, metrics={"files": 2})
        
        self.assertTrue(finished.success)
        self.assertEqual(finished.artifacts_count, 2)
        self.assertIsNotNone(finished.finished_at)
        self.assertIsNotNone(finished.duration_ms)
        # duration_ms kann 0 sein wenn sehr schnell (sub-ms), also >= 0
        self.assertGreaterEqual(finished.duration_ms, 0)
        self.assertEqual(finished.metrics, {"files": 2})

    def test_record_run_end_mit_fehler(self):
        run = self.store.record_run_start("t1", "n1", "project")
        finished = self.store.record_run_end(run.run_id, success=False, error="Template nicht gefunden")
        
        self.assertFalse(finished.success)
        self.assertEqual(finished.error_message, "Template nicht gefunden")
        self.assertEqual(finished.artifacts_count, 0)

    def test_get_run_existiert(self):
        run = self.store.record_run_start("t1", "n1", "project")
        fetched = self.store.get_run(run.run_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.run_id, run.run_id)

    def test_get_run_nicht_existiert_gibt_none(self):
        fetched = self.store.get_run("nicht-existierend")
        self.assertIsNone(fetched)

    def test_list_runs_filter_nach_typ(self):
        self.store.record_run_start("type_a", "proj1", "project")
        self.store.record_run_start("type_b", "proj2", "project")
        self.store.record_run_start("type_a", "proj3", "module")
        
        runs_a = self.store.list_runs(typ_id="type_a")
        runs_b = self.store.list_runs(typ_id="type_b")
        all_runs = self.store.list_runs()
        
        self.assertEqual(len(runs_a), 2)
        self.assertEqual(len(runs_b), 1)
        self.assertEqual(len(all_runs), 3)
        # Neueste zuerst
        self.assertEqual(runs_a[0].name, "proj3")

    def test_list_runs_limit(self):
        for i in range(5):
            self.store.record_run_start("t1", f"p{i}", "project")
        runs = self.store.list_runs(limit=3)
        self.assertEqual(len(runs), 3)

    # ──────────────────────────────────────────────
    # Benchmarks
    # ──────────────────────────────────────────────

    def test_record_benchmark_speichert_aggregierte_metriken(self):
        run1 = self.store.record_run_start("bench_type", "r1", "project")
        self.store.record_run_end(run1.run_id, True, artifacts=[Path("a")], metrics={"render_ms": 100})
        run2 = self.store.record_run_start("bench_type", "r2", "project")
        self.store.record_run_end(run2.run_id, True, artifacts=[Path("b"), Path("c")], metrics={"render_ms": 200})
        run3 = self.store.record_run_start("bench_type", "r3", "project")
        self.store.record_run_end(run3.run_id, False, error="fail")
        
        # WICHTIG: Updated Runs aus DB holen für Benchmark
        run1_updated = self.store.get_run(run1.run_id)
        run2_updated = self.store.get_run(run2.run_id)
        run3_updated = self.store.get_run(run3.run_id)
        
        bench = self.store.record_benchmark("bench_type", "default", {"param": "value"}, 0.85, [run1_updated, run2_updated, run3_updated])
        
        self.assertEqual(bench.typ_id, "bench_type")
        self.assertEqual(bench.variant, "default")
        self.assertEqual(bench.params, {"param": "value"})
        self.assertEqual(bench.score, 0.85)
        self.assertEqual(bench.runs_count, 3)
        self.assertIn("success_rate", bench.aggregated_metrics)
        self.assertAlmostEqual(bench.aggregated_metrics["success_rate"], 2/3)
        self.assertIn("duration_ms", bench.aggregated_metrics)
        self.assertIn("artifacts", bench.aggregated_metrics)

    def test_get_benchmarks_filter_nach_typ(self):
        self.store.record_benchmark("t1", "v1", {}, 0.5, [])
        self.store.record_benchmark("t2", "v1", {}, 0.7, [])
        
        benches_t1 = self.store.get_benchmarks("t1")
        benches_t2 = self.store.get_benchmarks("t2")
        all_benches = self.store.get_benchmarks()
        
        self.assertEqual(len(benches_t1), 1)
        self.assertEqual(len(benches_t2), 1)
        self.assertEqual(len(all_benches), 2)

    def test_get_latest_benchmark(self):
        self.store.record_benchmark("t1", "v1", {}, 0.5, [])
        self.store.record_benchmark("t1", "v2", {}, 0.7, [])
        self.store.record_benchmark("t1", "v1", {}, 0.6, [])
        
        latest = self.store.get_latest_benchmark("t1")
        self.assertEqual(latest.variant, "v1")
        self.assertEqual(latest.score, 0.6)
        
        latest_v2 = self.store.get_latest_benchmark("t1", variant="v2")
        self.assertEqual(latest_v2.variant, "v2")
        self.assertEqual(latest_v2.score, 0.7)

    # ──────────────────────────────────────────────
    # Gate Evidence
    # ──────────────────────────────────────────────

    def test_add_gate_evidence_erzeugt_pending(self):
        run = self.store.record_run_start("t1", "n1", "project")
        evidence = self.store.add_gate_evidence("gate-123", run.run_id, "test_result", {"passed": 10, "failed": 0})
        
        self.assertEqual(evidence.gate_id, "gate-123")
        self.assertEqual(evidence.run_id, run.run_id)
        self.assertEqual(evidence.evidence_type, "test_result")
        self.assertEqual(evidence.payload, {"passed": 10, "failed": 0})
        self.assertEqual(evidence.verdict, "pending")
        self.assertIsNone(evidence.reviewer)

    def test_update_gate_verdict(self):
        run = self.store.record_run_start("t1", "n1", "project")
        evidence = self.store.add_gate_evidence("gate-123", run.run_id, "coverage", {"coverage": 85})
        
        updated = self.store.update_gate_verdict(evidence.evidence_id, "pass", "captain")
        
        self.assertEqual(updated.verdict, "pass")
        self.assertEqual(updated.reviewer, "captain")
        self.assertIsNotNone(updated.reviewed_at)

    def test_get_gate_evidence_filter_nach_gate(self):
        run = self.store.record_run_start("t1", "n1", "project")
        self.store.add_gate_evidence("gate-a", run.run_id, "test", {})
        self.store.add_gate_evidence("gate-b", run.run_id, "security", {})
        
        evidence_a = self.store.get_gate_evidence("gate-a")
        evidence_b = self.store.get_gate_evidence("gate-b")
        
        self.assertEqual(len(evidence_a), 1)
        self.assertEqual(evidence_a[0].evidence_type, "test")
        self.assertEqual(len(evidence_b), 1)
        self.assertEqual(evidence_b[0].evidence_type, "security")

    # ──────────────────────────────────────────────
    # Meta Insights
    # ──────────────────────────────────────────────

    def test_add_insight(self):
        insight = self.store.add_insight(
            pattern="Module > 20 Dateien sind langsam",
            confidence=0.8,
            supporting_run_ids=["run-1", "run-2"],
            recommendation="Module splitten",
        )
        
        self.assertEqual(insight.pattern, "Module > 20 Dateien sind langsam")
        self.assertEqual(insight.confidence, 0.8)
        self.assertEqual(insight.supporting_run_ids, ["run-1", "run-2"])
        self.assertEqual(insight.recommendation, "Module splitten")

    def test_get_insights_min_confidence(self):
        self.store.add_insight("High confidence", 0.9, [], "rec1")
        self.store.add_insight("Medium confidence", 0.6, [], "rec2")
        self.store.add_insight("Low confidence", 0.3, [], "rec3")
        
        insights = self.store.get_insights(min_confidence=0.5)
        self.assertEqual(len(insights), 2)
        self.assertEqual(insights[0].confidence, 0.9)  # Höchste zuerst
        self.assertEqual(insights[1].confidence, 0.6)

    def test_delete_insight(self):
        insight = self.store.add_insight("To delete", 0.5, [], "rec")
        deleted = self.store.delete_insight(insight.insight_id)
        self.assertTrue(deleted)
        
        insights = self.store.get_insights(min_confidence=0.0)
        self.assertEqual(len(insights), 0)
        
        # Zweites Löschen gibt False
        deleted_again = self.store.delete_insight(insight.insight_id)
        self.assertFalse(deleted_again)

    # ──────────────────────────────────────────────
    # Health / Persistenz
    # ──────────────────────────────────────────────

    def test_health_zaehlt_korrekt(self):
        self.store.record_run_start("t1", "n1", "project")
        self.store.record_benchmark("t1", "v1", {}, 0.5, [])
        run = self.store.record_run_start("t1", "n2", "project")
        self.store.add_gate_evidence("g1", run.run_id, "test", {})
        self.store.add_insight("pattern", 0.7, [], "rec")
        
        health = self.store.health()
        
        self.assertEqual(health["runs"], 2)
        self.assertEqual(health["benchmarks"], 1)
        self.assertEqual(health["gate_evidence"], 1)
        self.assertEqual(health["meta_insights"], 1)
        self.assertTrue(health["ok"])
        self.assertGreater(health["db_size_bytes"], 0)

    def test_persistenz_ueberlebt_neustart(self):
        run = self.store.record_run_start("persist_type", "persist_name", "project")
        self.store.record_run_end(run.run_id, True, metrics={"key": "value"})
        self.store.add_insight("persist_pattern", 0.9, [run.run_id], "persist_rec")
        
        self.store.close()
        
        # Neu öffnen
        new_store = EvidenceStore(self.db_path)
        fetched = new_store.get_run(run.run_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.metrics, {"key": "value"})
        
        insights = new_store.get_insights(0.0)
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0].pattern, "persist_pattern")
        
        new_store.close()

    def test_wal_mode_aktiv(self):
        # WAL-Mode sollte aktiv sein (keine Exception bei concurrent access)
        with self.store._connect() as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            self.assertEqual(row[0].lower(), "wal")


if __name__ == "__main__":
    unittest.main()