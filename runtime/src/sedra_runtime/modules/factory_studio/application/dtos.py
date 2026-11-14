"""Data Transfer Objects — Factory Studio API-Datentransfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class ProjectDTO:
    """Projekt für API-Transport."""
    id: str
    name: str
    display_name: str
    description: str
    factory_type_id: str
    status: str
    created_at: str  # ISO8601
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    modules_count: int = 0
    last_build_status: str | None = None
    last_build_at: str | None = None


@dataclass
class ModuleDTO:
    """Modul für API-Transport."""
    id: str
    project_id: str
    name: str
    display_name: str
    module_type_id: str
    status: str
    layer: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class BuildDTO:
    """Build für API-Transport."""
    id: str
    project_id: str
    module_id: str | None
    build_type: str
    factory_type_id: str
    status: str
    started_at: str | None
    finished_at: str | None
    duration_ms: int | None
    success: bool
    artifacts: list[str] = field(default_factory=list)
    error_message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkDTO:
    """Benchmark für API-Transport."""
    id: str
    factory_type_id: str
    variant: str
    params: dict[str, Any]
    score: float | None
    runs_count: int
    aggregated_metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str


@dataclass
class GateDTO:
    """Captain-Gate für API-Transport."""
    id: str
    gate_type: str
    target_id: str
    status: str
    requested_by: str
    requested_at: str
    decided_by: str | None = None
    decided_at: str | None = None
    decision_reason: str | None = None


@dataclass
class GraphDTO:
    """Dependency-Graph für API-Transport."""
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProjectListResponse:
    """Response für Projekt-Liste."""
    projects: list[ProjectDTO]
    total: int


@dataclass
class ModuleListResponse:
    """Response für Modul-Liste."""
    modules: list[ModuleDTO]
    total: int


@dataclass
class BuildListResponse:
    """Response für Build-Liste."""
    builds: list[BuildDTO]
    total: int


@dataclass
class BenchmarkListResponse:
    """Response für Benchmark-Liste."""
    benchmarks: list[BenchmarkDTO]
    total: int


@dataclass
class GateListResponse:
    """Response für Gate-Liste."""
    gates: list[GateDTO]
    total: int