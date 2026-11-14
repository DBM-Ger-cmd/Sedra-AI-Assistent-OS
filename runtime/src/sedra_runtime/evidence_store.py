"""SEDRA Evidence Store — SQLite-basierte Speicherung für Runs, Benchmarks, Gate-Evidence, Meta-Insights."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────

@dataclass
class RunRecord:
    run_id: str
    typ_id: str
    name: str
    build_type: str  # 'project' | 'module' | 'service'
    started_at: str  # ISO8601
    finished_at: str | None
    duration_ms: int | None
    success: bool
    artifacts_count: int
    error_message: str | None
    metrics: dict

    @staticmethod
    def from_row(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            typ_id=row["typ_id"],
            name=row["name"],
            build_type=row["build_type"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration_ms=row["duration_ms"],
            success=bool(row["success"]),
            artifacts_count=row["artifacts_count"],
            error_message=row["error_message"],
            metrics=json.loads(row["metrics_json"]) if row["metrics_json"] else {},
        )


@dataclass
class BenchmarkRecord:
    benchmark_id: str
    typ_id: str
    variant: str
    params: dict
    score: float
    runs_count: int
    aggregated_metrics: dict
    created_at: str

    @staticmethod
    def from_row(row: sqlite3.Row) -> BenchmarkRecord:
        return BenchmarkRecord(
            benchmark_id=row["benchmark_id"],
            typ_id=row["typ_id"],
            variant=row["variant"],
            params=json.loads(row["params_json"]) if row["params_json"] else {},
            score=row["score"],
            runs_count=row["runs_count"],
            aggregated_metrics=json.loads(row["aggregated_metrics_json"]) if row["aggregated_metrics_json"] else {},
            created_at=row["created_at"],
        )


@dataclass
class GateEvidenceRecord:
    evidence_id: str
    gate_id: str
    run_id: str
    evidence_type: str  # 'test_result' | 'coverage' | 'security' | 'performance'
    payload: dict
    verdict: str | None  # 'pass' | 'fail' | 'warning' | 'pending'
    reviewer: str | None
    reviewed_at: str | None
    created_at: str

    @staticmethod
    def from_row(row: sqlite3.Row) -> GateEvidenceRecord:
        return GateEvidenceRecord(
            evidence_id=row["evidence_id"],
            gate_id=row["gate_id"],
            run_id=row["run_id"],
            evidence_type=row["evidence_type"],
            payload=json.loads(row["payload_json"]) if row["payload_json"] else {},
            verdict=row["verdict"],
            reviewer=row["reviewer"],
            reviewed_at=row["reviewed_at"],
            created_at=row["created_at"],
        )


@dataclass
class MetaInsightRecord:
    insight_id: str
    pattern: str
    confidence: float
    supporting_run_ids: list[str]
    recommendation: str
    created_at: str

    @staticmethod
    def from_row(row: sqlite3.Row) -> MetaInsightRecord:
        return MetaInsightRecord(
            insight_id=row["insight_id"],
            pattern=row["pattern"],
            confidence=row["confidence"],
            supporting_run_ids=json.loads(row["supporting_run_ids"]) if row["supporting_run_ids"] else [],
            recommendation=row["recommendation"],
            created_at=row["created_at"],
        )


# ──────────────────────────────────────────────
# Evidence Store
# ──────────────────────────────────────────────

SCHEMA_SQL = """
-- Runs: Jeder Build-Vorgang
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    typ_id TEXT NOT NULL,
    name TEXT NOT NULL,
    build_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    success INTEGER NOT NULL,
    artifacts_count INTEGER DEFAULT 0,
    error_message TEXT,
    metrics_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Benchmarks: Aggregierte Vergleiche
CREATE TABLE IF NOT EXISTS benchmarks (
    benchmark_id TEXT PRIMARY KEY,
    typ_id TEXT NOT NULL,
    variant TEXT,
    params_json TEXT,
    score REAL,
    runs_count INTEGER,
    aggregated_metrics_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Gate Evidence: Für Captain-Entscheidungen
CREATE TABLE IF NOT EXISTS gate_evidence (
    evidence_id TEXT PRIMARY KEY,
    gate_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    verdict TEXT,
    reviewer TEXT,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Meta Insights: Gelernte Muster
CREATE TABLE IF NOT EXISTS meta_insights (
    insight_id TEXT PRIMARY KEY,
    pattern TEXT NOT NULL,
    confidence REAL NOT NULL,
    supporting_run_ids TEXT,
    recommendation TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indizes
CREATE INDEX IF NOT EXISTS idx_runs_typ_id ON runs(typ_id);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_benchmarks_typ_id ON benchmarks(typ_id);
CREATE INDEX IF NOT EXISTS idx_gate_evidence_gate_id ON gate_evidence(gate_id);
CREATE INDEX IF NOT EXISTS idx_gate_evidence_run_id ON gate_evidence(run_id);
"""

PRAGMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=30000;
"""


class EvidenceStore:
    """SQLite-basierter Evidence Store für Factory-Runs, Benchmarks, Gates, Insights."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(PRAGMA_SQL)
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        try:
            yield self._conn
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ──────────────────────────────────────────────
    # Runs
    # ──────────────────────────────────────────────

    def record_run_start(
        self,
        typ_id: str,
        name: str,
        build_type: str,
        run_id: str | None = None,
    ) -> RunRecord:
        """Startet einen neuen Run-Record."""
        run_id = run_id or str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, typ_id, name, build_type, started_at, success, artifacts_count)
                VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (run_id, typ_id, name, build_type, started_at),
            )
        return RunRecord(
            run_id=run_id,
            typ_id=typ_id,
            name=name,
            build_type=build_type,
            started_at=started_at,
            finished_at=None,
            duration_ms=None,
            success=False,
            artifacts_count=0,
            error_message=None,
            metrics={},
        )

    def record_run_end(
        self,
        run_id: str,
        success: bool,
        artifacts: list[Path] | None = None,
        error: str | None = None,
        metrics: dict | None = None,
    ) -> RunRecord:
        """Beendet einen Run-Record mit Ergebnis."""
        finished_at = datetime.now(timezone.utc).isoformat()
        artifacts_count = len(artifacts) if artifacts else 0
        
        # Duration berechnen
        with self._connect() as conn:
            row = conn.execute("SELECT started_at FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row:
                started = datetime.fromisoformat(row["started_at"])
                finished = datetime.fromisoformat(finished_at)
                duration_ms = int((finished - started).total_seconds() * 1000)
            else:
                duration_ms = 0
            
            conn.execute(
                """
                UPDATE runs
                SET finished_at = ?, duration_ms = ?, success = ?, artifacts_count = ?,
                    error_message = ?, metrics_json = ?
                WHERE run_id = ?
                """,
                (finished_at, duration_ms, int(success), artifacts_count, error, json.dumps(metrics or {}), run_id),
            )
        
        return self.get_run(run_id)  # type: ignore[return-value]

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return RunRecord.from_row(row) if row else None

    def list_runs(self, typ_id: str | None = None, limit: int = 100) -> list[RunRecord]:
        with self._connect() as conn:
            if typ_id:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE typ_id = ? ORDER BY started_at DESC LIMIT ?",
                    (typ_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [RunRecord.from_row(r) for r in rows]

    def get_recent_runs(self, typ_id: str, limit: int = 50) -> list[RunRecord]:
        """Alias für list_runs mit Default-Limit."""
        return self.list_runs(typ_id, limit)

    # ──────────────────────────────────────────────
    # Benchmarks
    # ──────────────────────────────────────────────

    def record_benchmark(
        self,
        typ_id: str,
        variant: str,
        params: dict,
        score: float,
        runs: list[RunRecord],
    ) -> BenchmarkRecord:
        benchmark_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Aggregierte Metriken berechnen
        aggregated = self._aggregate_metrics(runs)
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO benchmarks (benchmark_id, typ_id, variant, params_json, score, runs_count, aggregated_metrics_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (benchmark_id, typ_id, variant, json.dumps(params), score, len(runs), json.dumps(aggregated), created_at),
            )
        
        return BenchmarkRecord(
            benchmark_id=benchmark_id,
            typ_id=typ_id,
            variant=variant,
            params=params,
            score=score,
            runs_count=len(runs),
            aggregated_metrics=aggregated,
            created_at=created_at,
        )

    def _aggregate_metrics(self, runs: list[RunRecord]) -> dict:
        if not runs:
            return {}
        
        durations = [r.duration_ms for r in runs if r.duration_ms is not None]
        success_count = sum(1 for r in runs if r.success)
        artifact_counts = [r.artifacts_count for r in runs]
        
        agg = {
            "runs_total": len(runs),
            "success_rate": success_count / len(runs),
            "duration_ms": {
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "avg": sum(durations) / len(durations) if durations else 0,
                "median": sorted(durations)[len(durations) // 2] if durations else 0,
            },
            "artifacts": {
                "min": min(artifact_counts) if artifact_counts else 0,
                "max": max(artifact_counts) if artifact_counts else 0,
                "avg": sum(artifact_counts) / len(artifact_counts) if artifact_counts else 0,
            },
        }
        return agg

    def get_benchmarks(self, typ_id: str | None = None) -> list[BenchmarkRecord]:
        with self._connect() as conn:
            if typ_id:
                rows = conn.execute(
                    "SELECT * FROM benchmarks WHERE typ_id = ? ORDER BY created_at DESC",
                    (typ_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM benchmarks ORDER BY created_at DESC"
                ).fetchall()
            return [BenchmarkRecord.from_row(r) for r in rows]

    def get_latest_benchmark(self, typ_id: str, variant: str | None = None) -> BenchmarkRecord | None:
        with self._connect() as conn:
            if variant:
                row = conn.execute(
                    "SELECT * FROM benchmarks WHERE typ_id = ? AND variant = ? ORDER BY created_at DESC LIMIT 1",
                    (typ_id, variant),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM benchmarks WHERE typ_id = ? ORDER BY created_at DESC LIMIT 1",
                    (typ_id,),
                ).fetchone()
            return BenchmarkRecord.from_row(row) if row else None

    # ──────────────────────────────────────────────
    # Gate Evidence
    # ──────────────────────────────────────────────

    def add_gate_evidence(
        self,
        gate_id: str,
        run_id: str,
        evidence_type: str,
        payload: dict,
    ) -> GateEvidenceRecord:
        evidence_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gate_evidence (evidence_id, gate_id, run_id, evidence_type, payload_json, verdict, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (evidence_id, gate_id, run_id, evidence_type, json.dumps(payload), created_at),
            )
        
        return GateEvidenceRecord(
            evidence_id=evidence_id,
            gate_id=gate_id,
            run_id=run_id,
            evidence_type=evidence_type,
            payload=payload,
            verdict="pending",
            reviewer=None,
            reviewed_at=None,
            created_at=created_at,
        )

    def update_gate_verdict(
        self,
        evidence_id: str,
        verdict: str,
        reviewer: str,
    ) -> GateEvidenceRecord:
        reviewed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE gate_evidence SET verdict = ?, reviewer = ?, reviewed_at = ? WHERE evidence_id = ?",
                (verdict, reviewer, reviewed_at, evidence_id),
            )
        return self.get_gate_evidence_by_id(evidence_id)  # type: ignore[return-value]

    def get_gate_evidence_by_id(self, evidence_id: str) -> GateEvidenceRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM gate_evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
            return GateEvidenceRecord.from_row(row) if row else None

    def get_gate_evidence(self, gate_id: str) -> list[GateEvidenceRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM gate_evidence WHERE gate_id = ? ORDER BY created_at DESC",
                (gate_id,),
            ).fetchall()
            return [GateEvidenceRecord.from_row(r) for r in rows]

    # ──────────────────────────────────────────────
    # Meta Insights
    # ──────────────────────────────────────────────

    def add_insight(
        self,
        pattern: str,
        confidence: float,
        supporting_run_ids: list[str],
        recommendation: str,
    ) -> MetaInsightRecord:
        insight_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO meta_insights (insight_id, pattern, confidence, supporting_run_ids, recommendation, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (insight_id, pattern, confidence, json.dumps(supporting_run_ids), recommendation, created_at),
            )
        
        return MetaInsightRecord(
            insight_id=insight_id,
            pattern=pattern,
            confidence=confidence,
            supporting_run_ids=supporting_run_ids,
            recommendation=recommendation,
            created_at=created_at,
        )

    def get_insights(self, min_confidence: float = 0.5) -> list[MetaInsightRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM meta_insights WHERE confidence >= ? ORDER BY confidence DESC",
                (min_confidence,),
            ).fetchall()
            return [MetaInsightRecord.from_row(r) for r in rows]

    def delete_insight(self, insight_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM meta_insights WHERE insight_id = ?", (insight_id,))
            return cur.rowcount > 0

    # ──────────────────────────────────────────────
    # Health / Stats
    # ──────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        with self._connect() as conn:
            runs_count = conn.execute("SELECT COUNT(*) as c FROM runs").fetchone()["c"]
            benchmarks_count = conn.execute("SELECT COUNT(*) as c FROM benchmarks").fetchone()["c"]
            evidence_count = conn.execute("SELECT COUNT(*) as c FROM gate_evidence").fetchone()["c"]
            insights_count = conn.execute("SELECT COUNT(*) as c FROM meta_insights").fetchone()["c"]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        return {
            "db_path": str(self.db_path),
            "db_size_bytes": db_size,
            "runs": runs_count,
            "benchmarks": benchmarks_count,
            "gate_evidence": evidence_count,
            "meta_insights": insights_count,
            "ok": True,
        }


def get_default_store() -> EvidenceStore:
    """Liefert Default Evidence Store im Projekt-Root (local_config/evidence/evidence.db)."""
    project_root = Path.cwd()
    store_dir = project_root / 'local_config' / 'evidence'
    store_dir.mkdir(parents=True, exist_ok=True)
    return EvidenceStore(store_dir / 'evidence.db')