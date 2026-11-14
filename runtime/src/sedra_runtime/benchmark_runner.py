"""SEDRA Benchmark Runner — Führt Factory-Builds wiederholt aus, sammelt Metriken, berechnet Scores."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sedra_runtime.evidence_store import EvidenceStore, RunRecord
from sedra_runtime.factory_builder import FactoryBuilder, BuildResult
from sedra_runtime.factory_registry import FactoryRegistry


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class BenchmarkConfig:
    """Konfiguration für einen Benchmark-Lauf."""
    typ_id: str
    variant: str = "default"
    params: dict[str, Any] = field(default_factory=dict)
    iterations: int = 3
    build_type: str = "project"  # project | module | service
    project_name: str | None = None  # für module/service builds
    warmup: int = 0  # Warmup-Runs (werden nicht gewertet)
    cleanup_between: bool = True  # Artefakte zwischen Runs löschen


@dataclass
class BenchmarkResult:
    """Ergebnis eines Benchmark-Laufs (aggregiert)."""
    benchmark_id: str
    typ_id: str
    variant: str
    params: dict[str, Any]
    score: float
    runs: list[RunRecord]
    aggregated_metrics: dict[str, Any]
    created_at: datetime
    config: BenchmarkConfig


# =============================================================================
# Benchmark Runner
# =============================================================================

class BenchmarkRunner:
    """Führt Factory-Builds wiederholt aus und speichert Results im Evidence Store."""

    def __init__(
        self,
        store: EvidenceStore,
        builder: FactoryBuilder,
        registry: FactoryRegistry,
        project_root: Path | None = None,
    ):
        self.store = store
        self.builder = builder
        self.registry = registry
        self.project_root = project_root or Path.cwd()

    def run_benchmark(self, config: BenchmarkConfig) -> BenchmarkResult:
        """Führt einen kompletten Benchmark aus (warmup + iterations)."""
        all_runs: list[RunRecord] = []
        
        # Warmup-Runs (nicht gewertet)
        for i in range(config.warmup):
            self._run_single(config, f"warmup_{i}", count=False)
        
        # Echte Iterations
        for i in range(config.iterations):
            run = self._run_single(config, f"iter_{i}", count=True)
            if run:
                all_runs.append(run)
        
        if not all_runs:
            raise RuntimeError("Keine erfolgreichen Runs für Benchmark")
        
        # Score berechnen
        score = self._calculate_score(all_runs, config)
        
        # Im Evidence Store speichern
        benchmark_record = self.store.record_benchmark(
            typ_id=config.typ_id,
            variant=config.variant,
            params=config.params,
            score=score,
            runs=all_runs,
        )
        
        # Aggregierte Metriken für Return-Objekt
        aggregated = self._aggregate_metrics(all_runs)
        
        return BenchmarkResult(
            benchmark_id=benchmark_record.benchmark_id,
            typ_id=config.typ_id,
            variant=config.variant,
            params=config.params,
            score=score,
            runs=all_runs,
            aggregated_metrics=aggregated,
            created_at=benchmark_record.created_at,
            config=config,
        )

    def _run_single(
        self,
        config: BenchmarkConfig,
        suffix: str,
        count: bool
    ) -> RunRecord | None:
        """Führt einen einzelnen Build aus."""
        name = f"{config.typ_id}_{config.variant}_{suffix}"
        
        # Run im Evidence Store starten
        run = self.store.record_run_start(config.typ_id, name, config.build_type)
        
        try:
            # Build ausführen
            if config.build_type == "project":
                result: BuildResult = self.builder.build_project(
                    config.typ_id, name, gate_freigabe=True
                )
            elif config.build_type == "module":
                if not config.project_name:
                    raise ValueError("project_name erforderlich für module build")
                project_path = self.project_root / config.project_name
                result = self.builder.build_module(
                    config.typ_id, name, project_path, gate_freigabe=True
                )
            elif config.build_type == "service":
                if not config.project_name:
                    raise ValueError("project_name erforderlich für service build")
                project_path = self.project_root / config.project_name
                result = self.builder.build_service(
                    config.typ_id, name, project_path, gate_freigabe=True
                )
            else:
                raise ValueError(f"Unbekannter build_type: {config.build_type}")
            
            # Run beenden
            artifacts = [Path(a) for a in (result.artifacts or [])]
            finished = self.store.record_run_end(
                run.run_id,
                success=result.success,
                artifacts=artifacts,
                error=result.message if not result.success else None,
                metrics={
                    "template_render_ms": getattr(result, 'template_render_ms', 0),
                    "files_created": len(artifacts),
                    "build_type": config.build_type,
                }
            )
            
            # Cleanup falls konfiguriert
            if config.cleanup_between and result.success and result.path:
                import shutil
                shutil.rmtree(result.path, ignore_errors=True)
            
            return finished
            
        except Exception as e:
            self.store.record_run_end(
                run.run_id,
                success=False,
                error=str(e),
                metrics={"build_type": config.build_type, "exception": type(e).__name__}
            )
            return None

    def _calculate_score(self, runs: list[RunRecord], config: BenchmarkConfig) -> float:
        """Berechnet Composite Score (0.0 - 1.0)."""
        if not runs:
            return 0.0
        
        # Success Rate (Gewicht 0.5)
        success_rate = sum(1 for r in runs if r.success) / len(runs)
        
        # Duration Score (Gewicht 0.3) — schneller = besser
        durations = [r.duration_ms for r in runs if r.duration_ms and r.success]
        if durations:
            median_duration = statistics.median(durations)
            # Normalisieren: 1000ms = 1.0, 10000ms = 0.1, >60000ms = 0.0
            duration_score = max(0.0, min(1.0, 1000 / median_duration))
        else:
            duration_score = 0.0
        
        # Artifact Score (Gewicht 0.2) — mehr Artefakte = vollständiger
        artifact_counts = [r.artifacts_count for r in runs if r.success]
        if artifact_counts:
            avg_artifacts = statistics.mean(artifact_counts)
            # Erwartet: project ~3, module ~20+, service ~6
            expected = {"project": 3, "module": 20, "service": 6}.get(config.build_type, 10)
            artifact_score = min(1.0, avg_artifacts / expected)
        else:
            artifact_score = 0.0
        
        # Weighted Composite
        score = (
            0.5 * success_rate +
            0.3 * duration_score +
            0.2 * artifact_score
        )
        
        return round(score, 3)

    def _aggregate_metrics(self, runs: list[RunRecord]) -> dict[str, Any]:
        """Aggregiert Metriken über alle Runs."""
        if not runs:
            return {}
        
        successful = [r for r in runs if r.success]
        durations = [r.duration_ms for r in successful if r.duration_ms is not None]
        artifact_counts = [r.artifacts_count for r in successful]
        
        agg = {
            "runs_total": len(runs),
            "runs_successful": len(successful),
            "success_rate": len(successful) / len(runs),
        }
        
        if durations:
            agg["duration_ms"] = {
                "min": min(durations),
                "max": max(durations),
                "mean": statistics.mean(durations),
                "median": statistics.median(durations),
                "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
            }
        
        if artifact_counts:
            agg["artifacts"] = {
                "min": min(artifact_counts),
                "max": max(artifact_counts),
                "mean": statistics.mean(artifact_counts),
                "median": statistics.median(artifact_counts),
            }
        
        # Metriken aus Run-Metrics aggregieren
        metric_keys = set()
        for r in successful:
            metric_keys.update(r.metrics.keys())
        
        for key in metric_keys:
            vals = [r.metrics.get(key) for r in successful if isinstance(r.metrics.get(key), (int, float))]
            if vals:
                agg[f"metric_{key}"] = {
                    "min": min(vals),
                    "max": max(vals),
                    "mean": statistics.mean(vals),
                    "median": statistics.median(vals),
                }
        
        return agg

    def compare_variants(
        self,
        typ_id: str,
        variants: list[BenchmarkConfig],
        project_name: str | None = None
    ) -> list[BenchmarkResult]:
        """Vergleicht mehrere Varianten für denselben Typ."""
        results = []
        for variant_config in variants:
            variant_config.typ_id = typ_id
            if project_name and variant_config.build_type in ("module", "service"):
                variant_config.project_name = project_name
            result = self.run_benchmark(variant_config)
            results.append(result)
        return results


# =============================================================================
# Convenience: Quick Benchmark
# =============================================================================

def quick_benchmark(
    store: EvidenceStore,
    builder: FactoryBuilder,
    registry: FactoryRegistry,
    typ_id: str,
    variant: str = "default",
    iterations: int = 3,
    build_type: str = "project",
    project_root: Path | None = None,
) -> BenchmarkResult:
    """Schneller Benchmark mit Defaults."""
    config = BenchmarkConfig(
        typ_id=typ_id,
        variant=variant,
        iterations=iterations,
        build_type=build_type,
    )
    runner = BenchmarkRunner(store, builder, registry, project_root)
    return runner.run_benchmark(config)