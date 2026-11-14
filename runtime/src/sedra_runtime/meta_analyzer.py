"""SEDRA Meta Analyzer — Analysiert Evidence Store History → Muster, Anomalien, Empfehlungen."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sedra_runtime.evidence_store import EvidenceStore, RunRecord, MetaInsightRecord


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class RegressionSignal:
    """Ein erkanntes Regressions-Signal."""
    typ_id: str
    metric: str
    current_value: float
    baseline_value: float
    change_pct: float
    severity: str  # 'critical' | 'warning' | 'info'
    runs_analyzed: int
    window: int


@dataclass
class PatternInsight:
    """Ein erkanntes Muster (für Meta Insights)."""
    pattern: str
    confidence: float
    supporting_run_ids: list[str]
    recommendation: str
    category: str  # 'failure' | 'performance' | 'quality' | 'variant'


# =============================================================================
# Meta Analyzer
# =============================================================================

class MetaAnalyzer:
    """Analysiert Run-History und generiert Insights/Regressionen."""

    def __init__(self, store: EvidenceStore):
        self.store = store

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def analyze(
        self,
        min_runs: int = 10,
        typ_id: str | None = None,
    ) -> list[PatternInsight]:
        """Analysiert Run-History → Muster, Anomalien, Empfehlungen."""
        insights: list[PatternInsight] = []

        # Runs holen
        runs = self.store.list_runs(typ_id=typ_id, limit=1000)
        if len(runs) < min_runs:
            return insights

        # 1. Failure Pattern Analysis
        insights.extend(self._analyze_failure_patterns(runs, typ_id))

        # 2. Performance Bottleneck Analysis
        insights.extend(self._analyze_performance_bottlenecks(runs, typ_id))

        # 3. Variant Comparison (falls Benchmarks existieren)
        insights.extend(self._analyze_variant_comparison(typ_id))

        # 4. Artifact Completeness
        insights.extend(self._analyze_artifact_completeness(runs, typ_id))

        # 5. Duration Trend (Verschlechterung über Zeit)
        insights.extend(self._analyze_duration_trend(runs, typ_id))

        return insights

    def detect_regressions(
        self,
        typ_id: str,
        window: int = 50,
        baseline_window: int = 50,
        threshold_pct: float = 0.20,  # 20% Veränderung
    ) -> list[RegressionSignal]:
        """Vergleicht letzte N Runs mit Baseline → Performance/Quality Regressions."""
        signals: list[RegressionSignal] = []

        # Aktuelle Runs (letztes Window)
        recent_runs = self.store.list_runs(typ_id=typ_id, limit=window)
        if len(recent_runs) < 5:
            return signals

        # Baseline Runs (Window davor)
        all_runs = self.store.list_runs(typ_id=typ_id, limit=window + baseline_window)
        baseline_runs = all_runs[window:window + baseline_window]
        if len(baseline_runs) < 5:
            return signals

        # Nur erfolgreiche Runs vergleichen
        recent_success = [r for r in recent_runs if r.success]
        baseline_success = [r for r in baseline_runs if r.success]

        if not recent_success or not baseline_success:
            return signals

        # Metriken vergleichen
        metrics_to_check = [
            ("duration_ms", "duration", "ms"),
            ("artifacts_count", "artifacts", "count"),
        ]

        for metric_key, metric_name, _ in metrics_to_check:
            recent_vals = [r.metrics.get(metric_key) for r in recent_success if r.metrics.get(metric_key) is not None]
            baseline_vals = [r.metrics.get(metric_key) for r in baseline_success if r.metrics.get(metric_key) is not None]

            if not recent_vals or not baseline_vals:
                continue

            recent_median = statistics.median(recent_vals)
            baseline_median = statistics.median(baseline_vals)

            if baseline_median == 0:
                continue

            change_pct = (recent_median - baseline_median) / baseline_median

            if abs(change_pct) >= threshold_pct:
                # Direction: duration increase = bad, artifact decrease = bad
                is_regression = (
                    (metric_key == "duration_ms" and change_pct > 0) or
                    (metric_key == "artifacts_count" and change_pct < 0)
                )

                if is_regression:
                    severity = "critical" if abs(change_pct) > 0.5 else "warning"
                    signals.append(RegressionSignal(
                        typ_id=typ_id,
                        metric=metric_name,
                        current_value=recent_median,
                        baseline_value=baseline_median,
                        change_pct=round(change_pct * 100, 1),
                        severity=severity,
                        runs_analyzed=len(recent_success),
                        window=window,
                    ))

        return signals

    def get_insights(self, min_confidence: float = 0.5) -> list[MetaInsightRecord]:
        """Holt gespeicherte Insights aus Store."""
        return self.store.get_insights(min_confidence)

    def save_insights(self, insights: list[PatternInsight]) -> list[MetaInsightRecord]:
        """Speichert Insights in Store."""
        saved = []
        for insight in insights:
            record = self.store.add_insight(
                pattern=insight.pattern,
                confidence=insight.confidence,
                supporting_run_ids=insight.supporting_run_ids,
                recommendation=insight.recommendation,
            )
            saved.append(record)
        return saved

    # -------------------------------------------------------------------------
    # Private Analysis Methods
    # -------------------------------------------------------------------------

    def _analyze_failure_patterns(
        self,
        runs: list[RunRecord],
        typ_id: str | None
    ) -> list[PatternInsight]:
        """Erkennt Failure-Patterns (häufige Fehler, bestimmte Typen)."""
        insights: list[PatternInsight] = []

        failed = [r for r in runs if not r.success]
        if not failed:
            return insights

        total = len(runs)
        fail_rate = len(failed) / total

        if fail_rate >= 0.3:  # 30%+ Failure Rate
            # Häufigste Fehlermeldungen
            error_counts: dict[str, int] = {}
            for r in failed:
                if r.error_message:
                    error_counts[r.error_message] = error_counts.get(r.error_message, 0) + 1

            if error_counts:
                top_error = max(error_counts, key=error_counts.get)
                count = error_counts[top_error]
                confidence = min(0.9, 0.5 + (count / len(failed)) * 0.4)

                insights.append(PatternInsight(
                    pattern=f"Hohe Failure-Rate ({fail_rate:.0%}) für Typ '{typ_id or 'alle'}' — Top-Fehler: '{top_error}' ({count}x)",
                    confidence=confidence,
                    supporting_run_ids=[r.run_id for r in failed[:10]],
                    recommendation=f"Template/Config für '{top_error}' prüfen; Gate-Checks verstärken",
                    category="failure",
                ))

        # Failure nach Build-Type
        by_type: dict[str, list[RunRecord]] = {}
        for r in failed:
            by_type.setdefault(r.build_type, []).append(r)

        for btype, type_failed in by_type.items():
            type_total = len([r for r in runs if r.build_type == btype])
            if type_total > 0:
                type_fail_rate = len(type_failed) / type_total
                if type_fail_rate >= 0.4:
                    insights.append(PatternInsight(
                        pattern=f"Build-Type '{btype}' hat hohe Failure-Rate ({type_fail_rate:.0%})",
                        confidence=0.75,
                        supporting_run_ids=[r.run_id for r in type_failed[:5]],
                        recommendation=f"'{btype}' Templates und Validierung prüfen",
                        category="failure",
                    ))

        return insights

    def _analyze_performance_bottlenecks(
        self,
        runs: list[RunRecord],
        typ_id: str | None
    ) -> list[PatternInsight]:
        """Erkennt Performance-Bottlenecks (Template-Rendering, Duration)."""
        insights: list[PatternInsight] = []

        successful = [r for r in runs if r.success and r.duration_ms is not None]
        if len(successful) < 5:
            return insights

        durations = [r.duration_ms for r in successful]
        median_duration = statistics.median(durations)

        # Template Render Metriken
        render_times = [r.metrics.get("template_render_ms") for r in successful if r.metrics.get("template_render_ms")]
        if render_times:
            median_render = statistics.median(render_times)
            render_ratio = median_render / median_duration if median_duration > 0 else 0

            if render_ratio > 0.5:  # >50% der Zeit im Template Rendering
                insights.append(PatternInsight(
                    pattern=f"Template-Rendering ist Bottleneck ({render_ratio:.0%} der Build-Zeit, Median {median_render:.0f}ms)",
                    confidence=0.8,
                    supporting_run_ids=[r.run_id for r in successful[:10]],
                    recommendation="Template-Engine optimieren (Caching, weniger Platzhalter, Jinja2 Upgrade)",
                    category="performance",
                ))

        # Langsame Builds identifizieren (Top 25% langsamste)
        if len(durations) >= 4:
            slow_threshold = sorted(durations)[int(len(durations) * 0.75)]
            slow_runs = [r for r in successful if r.duration_ms >= slow_threshold]
            if len(slow_runs) >= 3:
                insights.append(PatternInsight(
                    pattern=f"Top 25% der Builds sind langsam (>= {slow_threshold:.0f}ms, Median {median_duration:.0f}ms)",
                    confidence=0.7,
                    supporting_run_ids=[r.run_id for r in slow_runs[:5]],
                    recommendation="Outlier analysieren: große Module, komplexe Templates, I/O",
                    category="performance",
                ))

        return insights

    def _analyze_variant_comparison(self, typ_id: str | None) -> list[PatternInsight]:
        """Vergleicht Benchmark-Varianten für denselben Typ."""
        insights: list[PatternInsight] = []

        if not typ_id:
            return insights

        benchmarks = self.store.get_benchmarks(typ_id)
        if len(benchmarks) < 2:
            return insights

        # Gruppieren nach Variant
        by_variant: dict[str, list] = {}
        for b in benchmarks:
            key = b.variant or "default"
            by_variant.setdefault(key, []).append(b)

        if len(by_variant) < 2:
            return insights

        # Beste Variant finden (höchster Score)
        variant_scores = {}
        for variant, benches in by_variant.items():
            scores = [b.score for b in benches if b.score is not None]
            if scores:
                variant_scores[variant] = statistics.mean(scores)

        if len(variant_scores) >= 2:
            best_variant = max(variant_scores, key=variant_scores.get)
            worst_variant = min(variant_scores, key=variant_scores.get)
            best_score = variant_scores[best_variant]
            worst_score = variant_scores[worst_variant]

            if best_score - worst_score >= 0.15:  # 15% Unterschied
                insights.append(PatternInsight(
                    pattern=f"Variant '{best_variant}' (Score {best_score:.2f}) schlägt '{worst_variant}' ({worst_score:.2f}) um {(best_score-worst_score)*100:.0f}%",
                    confidence=0.75,
                    supporting_run_ids=[],
                    recommendation=f"Variant '{best_variant}' als Default setzen; '{worst_variant}' deprecaten",
                    category="variant",
                ))

        return insights

    def _analyze_artifact_completeness(
        self,
        runs: list[RunRecord],
        typ_id: str | None
    ) -> list[PatternInsight]:
        """Prüft ob Builds erwartete Artefakte erzeugen."""
        insights: list[PatternInsight] = []

        successful = [r for r in runs if r.success]
        if not successful:
            return insights

        by_type: dict[str, list[RunRecord]] = {}
        for r in successful:
            by_type.setdefault(r.build_type, []).append(r)

        expected_artifacts = {"project": 3, "module": 20, "service": 6}

        for btype, type_runs in by_type.items():
            expected = expected_artifacts.get(btype, 10)
            artifact_counts = [r.artifacts_count for r in type_runs]
            median_artifacts = statistics.median(artifact_counts)

            if median_artifacts < expected * 0.5:  # Weniger als 50% der erwarteten Artefakte
                insights.append(PatternInsight(
                    pattern=f"Build-Type '{btype}' erzeugt zu wenige Artefakte (Median {median_artifacts} vs. erwartet ~{expected})",
                    confidence=0.7,
                    supporting_run_ids=[r.run_id for r in type_runs[:5]],
                    recommendation=f"Template für '{btype}' prüfen: fehlende Dateien, Conditional Rendering",
                    category="quality",
                ))

        return insights

    def _analyze_duration_trend(
        self,
        runs: list[RunRecord],
        typ_id: str | None
    ) -> list[PatternInsight]:
        """Erkennt Trends in Build-Duration über Zeit (Verschlechterung)."""
        insights: list[PatternInsight] = []

        successful = [r for r in runs if r.success and r.duration_ms is not None]
        if len(successful) < 10:
            return insights

        # Nach Zeit sortieren (älteste zuerst)
        successful.sort(key=lambda r: r.started_at)

        # Ersten 25% vs letzten 25% vergleichen
        split = len(successful) // 4
        early = successful[:split]
        late = successful[-split:]

        early_median = statistics.median(r.duration_ms for r in early)
        late_median = statistics.median(r.duration_ms for r in late)

        if early_median > 0:
            change_pct = (late_median - early_median) / early_median

            if change_pct > 0.3:  # 30% langsamer
                insights.append(PatternInsight(
                    pattern=f"Build-Duration Trend: +{change_pct:.0%} langsamer über Zeit (Early: {early_median:.0f}ms → Late: {late_median:.0f}ms)",
                    confidence=0.75,
                    supporting_run_ids=[r.run_id for r in late[:5]],
                    recommendation="Regression bislegen: Template-Änderungen, Dependency-Bloat, Cache-Invalidation",
                    category="performance",
                ))

        return insights


# =============================================================================
# Convenience Functions
# =============================================================================

def run_full_analysis(store: EvidenceStore, min_runs: int = 10) -> dict[str, Any]:
    """Führt komplette Analyse aus und gibt Report zurück."""
    analyzer = MetaAnalyzer(store)

    # Alle Typen holen
    all_runs = store.list_runs(limit=1000)
    typ_ids = list(set(r.typ_id for r in all_runs))

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_runs": len(all_runs),
        "typ_ids": typ_ids,
        "insights": [],
        "regressions": {},
    }

    # Global analyse
    global_insights = analyzer.analyze(min_runs=min_runs)
    report["insights"].extend([{
        "pattern": i.pattern,
        "confidence": i.confidence,
        "recommendation": i.recommendation,
        "category": i.category,
        "supporting_runs": len(i.supporting_run_ids),
    } for i in global_insights])

    # Pro Typ Regressions
    for tid in typ_ids:
        regs = analyzer.detect_regressions(tid)
        if regs:
            report["regressions"][tid] = [{
                "metric": r.metric,
                "change_pct": r.change_pct,
                "severity": r.severity,
                "current": r.current_value,
                "baseline": r.baseline_value,
            } for r in regs]

    return report