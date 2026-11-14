"""Value Objects — Factory Studio unveränderliche Werte-Objekte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectId:
    """Eindeutige Projekt-Identifikation."""
    value: str
    
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("ProjectId darf nicht leer sein")


@dataclass(frozen=True)
class ModuleId:
    """Eindeutige Modul-Identifikation."""
    value: str
    
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("ModuleId darf nicht leer sein")


@dataclass(frozen=True)
class FactoryTypeId:
    """Factory-Typ Identifikation (Registry-Key)."""
    value: str
    
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("FactoryTypeId darf nicht leer sein")


@dataclass(frozen=True)
class BuildId:
    """Build-Identifikation."""
    value: str
    
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("BuildId darf nicht leer sein")


@dataclass(frozen=True)
class BenchmarkConfig:
    """Konfiguration für einen Benchmark-Lauf."""
    factory_type_id: FactoryTypeId
    variant: str = "default"
    params: dict[str, Any] = None
    iterations: int = 3
    build_type: str = "project"  # project, module, service
    project_name: str | None = None
    warmup: int = 0
    cleanup_between: bool = True
    
    def __post_init__(self):
        if self.params is None:
            object.__setattr__(self, 'params', {})


@dataclass(frozen=True)
class GraphNode:
    """Knoten im Dependency-Graph (für GraphView)."""
    id: str
    label: str
    node_type: str  # project, module, service
    status: str
    metadata: dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})


@dataclass(frozen=True)
class GraphEdge:
    """Kante im Dependency-Graph."""
    source: str
    target: str
    edge_type: str = "depends_on"  # depends_on, builds, contains
    metadata: dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})


@dataclass(frozen=True)
class MetricPoint:
    """Einzelner Metrik-Punkt für Charts."""
    timestamp: str  # ISO8601
    value: float
    label: str | None = None


@dataclass(frozen=True)
class ChartSeries:
    """Zeitreihe für Metrik-Charts."""
    name: str
    points: list[MetricPoint]
    unit: str = ""
    color: str | None = None