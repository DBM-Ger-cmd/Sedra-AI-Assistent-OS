"""Domain Entities — Factory Studio Kern-Entitäten."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class ProjectStatus(str, Enum):
    """Status eines Factory-Projekts."""
    CREATED = "created"
    BUILDING = "building"
    READY = "ready"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModuleStatus(str, Enum):
    """Status eines Factory-Moduls."""
    PLANNED = "planned"
    GENERATING = "generating"
    GENERATED = "generated"
    BUILDING = "building"
    BUILT = "built"
    FAILED = "failed"


class BuildStatus(str, Enum):
    """Status eines Build-Vorgangs."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FactoryProject:
    """Ein Factory-Projekt (ProjectBrowser Root-Node)."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    display_name: str = ""
    description: str = ""
    factory_type_id: str = ""  # z.B. "project_type", "module_type"
    status: ProjectStatus = ProjectStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Computed properties (nicht persistiert)
    modules: list[FactoryModule] = field(default_factory=list, repr=False)
    last_build: FactoryBuild | None = field(default=None, repr=False)
    
    @property
    def is_active(self) -> bool:
        return self.status in (ProjectStatus.CREATED, ProjectStatus.READY, ProjectStatus.BUILDING)


@dataclass
class FactoryModule:
    """Ein Factory-Modul (5-Layer Modul innerhalb eines Projekts)."""
    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    name: str = ""
    display_name: str = ""
    module_type_id: str = ""  # z.B. "module_type", "service_type"
    status: ModuleStatus = ModuleStatus.PLANNED
    layer: str = ""  # domain, application, infrastructure, ai, app
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # Module IDs
    
    @property
    def is_ready_for_build(self) -> bool:
        return self.status == ModuleStatus.GENERATED


@dataclass
class FactoryBuild:
    """Ein Build-Vorgang (Project, Module oder Service)."""
    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    module_id: str | None = None
    build_type: str = "project"  # project, module, service
    factory_type_id: str = ""
    status: BuildStatus = BuildStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    success: bool = False
    artifacts: list[str] = field(default_factory=list)
    error_message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        return self.finished_at is not None


@dataclass
class FactoryBenchmark:
    """Ein Benchmark-Ergebnis für einen Factory-Typ."""
    id: str = field(default_factory=lambda: str(uuid4()))
    factory_type_id: str = ""
    variant: str = "default"
    params: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    runs_count: int = 0
    aggregated_metrics: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    run_ids: list[str] = field(default_factory=list)


@dataclass
class FactoryGate:
    """Ein Captain-Gate für Factory-Operationen."""
    id: str = field(default_factory=lambda: str(uuid4()))
    gate_type: str = ""  # register, transition, build, benchmark
    target_id: str = ""  # Project/Module/Build ID
    status: str = "pending"  # pending, approved, rejected
    requested_by: str = ""
    requested_at: datetime = field(default_factory=datetime.now)
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)