"""Domain Events — Factory Studio Ereignis-Typen für Event-Driven Architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class DomainEvent:
    """Basisklasse für alle Domain Events."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=datetime.now)
    event_type: str = ""
    aggregate_id: str = ""
    version: int = 1


@dataclass
class ProjectCreated(DomainEvent):
    """Ein neues Factory-Projekt wurde erstellt."""
    event_type: str = "ProjectCreated"
    project_id: str = ""
    name: str = ""
    factory_type_id: str = ""
    
    def __post_init__(self):
        self.aggregate_id = self.project_id


@dataclass
class ProjectStatusChanged(DomainEvent):
    """Projekt-Status hat sich geändert."""
    event_type: str = "ProjectStatusChanged"
    project_id: str = ""
    old_status: str = ""
    new_status: str = ""
    
    def __post_init__(self):
        self.aggregate_id = self.project_id


@dataclass
class ModuleAdded(DomainEvent):
    """Ein Modul wurde zum Projekt hinzugefügt."""
    event_type: str = "ModuleAdded"
    project_id: str = ""
    module_id: str = ""
    module_name: str = ""
    module_type_id: str = ""
    layer: str = ""
    
    def __post_init__(self):
        self.aggregate_id = self.project_id


@dataclass
class ModuleStatusChanged(DomainEvent):
    """Modul-Status hat sich geändert."""
    event_type: str = "ModuleStatusChanged"
    module_id: str = ""
    project_id: str = ""
    old_status: str = ""
    new_status: str = ""
    
    def __post_init__(self):
        self.aggregate_id = self.module_id


@dataclass
class BuildStarted(DomainEvent):
    """Ein Build wurde gestartet."""
    event_type: str = "BuildStarted"
    build_id: str = ""
    project_id: str = ""
    module_id: str | None = None
    build_type: str = ""
    factory_type_id: str = ""
    
    def __post_init__(self):
        self.aggregate_id = self.build_id


@dataclass
class BuildCompleted(DomainEvent):
    """Ein Build wurde abgeschlossen."""
    event_type: str = "BuildCompleted"
    build_id: str = ""
    project_id: str = ""
    success: bool = False
    duration_ms: int = 0
    artifacts: list[str] = field(default_factory=list)
    error_message: str | None = None
    
    def __post_init__(self):
        self.aggregate_id = self.build_id


@dataclass
class BenchmarkCompleted(DomainEvent):
    """Ein Benchmark wurde abgeschlossen."""
    event_type: str = "BenchmarkCompleted"
    benchmark_id: str = ""
    factory_type_id: str = ""
    variant: str = ""
    score: float | None = None
    runs_count: int = 0
    
    def __post_init__(self):
        self.aggregate_id = self.benchmark_id


@dataclass
class GateRequested(DomainEvent):
    """Ein Captain-Gate wurde angefordert."""
    event_type: str = "GateRequested"
    gate_id: str = ""
    gate_type: str = ""
    target_id: str = ""
    requested_by: str = ""
    
    def __post_init__(self):
        self.aggregate_id = self.gate_id


@dataclass
class GateDecided(DomainEvent):
    """Ein Captain-Gate wurde entschieden."""
    event_type: str = "GateDecided"
    gate_id: str = ""
    decision: str = ""  # approved, rejected
    decided_by: str = ""
    reason: str | None = None
    
    def __post_init__(self):
        self.aggregate_id = self.gate_id