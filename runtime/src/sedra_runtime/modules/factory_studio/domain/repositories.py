"""Repository Interfaces — Factory Studio Persistenz-Abstraktionen.

Definiert die Verträge für Datenzugriff (Ports für Infrastructure Layer).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .entities import FactoryProject, FactoryModule, FactoryBuild, FactoryBenchmark, FactoryGate
from .value_objects import ProjectId, ModuleId, FactoryTypeId, BuildId, BenchmarkConfig, GraphNode, GraphEdge


class ProjectRepository(ABC):
    """Repository für Factory-Projekte."""
    
    @abstractmethod
    async def add(self, project: FactoryProject) -> None:
        """Neues Projekt speichern."""
        ...
    
    @abstractmethod
    async def get(self, project_id: ProjectId) -> FactoryProject | None:
        """Projekt nach ID laden."""
        ...
    
    @abstractmethod
    async def get_by_name(self, name: str) -> FactoryProject | None:
        """Projekt nach Name laden."""
        ...
    
    @abstractmethod
    async def list_all(self, status: str | None = None) -> list[FactoryProject]:
        """Alle Projekte listen (optional gefiltert nach Status)."""
        ...
    
    @abstractmethod
    async def update(self, project: FactoryProject) -> None:
        """Projekt aktualisieren."""
        ...
    
    @abstractmethod
    async def delete(self, project_id: ProjectId) -> bool:
        """Projekt löschen. Returns True wenn gelöscht."""
        ...


class ModuleRepository(ABC):
    """Repository für Factory-Module."""
    
    @abstractmethod
    async def add(self, module: FactoryModule) -> None:
        ...
    
    @abstractmethod
    async def get(self, module_id: ModuleId) -> FactoryModule | None:
        ...
    
    @abstractmethod
    async def get_by_project(self, project_id: ProjectId) -> list[FactoryModule]:
        """Alle Module eines Projekts laden."""
        ...
    
    @abstractmethod
    async def get_by_name_and_project(self, project_id: ProjectId, name: str) -> FactoryModule | None:
        ...
    
    @abstractmethod
    async def update(self, module: FactoryModule) -> None:
        ...
    
    @abstractmethod
    async def delete(self, module_id: ModuleId) -> bool:
        ...


class BuildRepository(ABC):
    """Repository für Build-Vorgänge."""
    
    @abstractmethod
    async def add(self, build: FactoryBuild) -> None:
        ...
    
    @abstractmethod
    async def get(self, build_id: BuildId) -> FactoryBuild | None:
        ...
    
    @abstractmethod
    async def get_by_project(self, project_id: ProjectId) -> list[FactoryBuild]:
        ...
    
    @abstractmethod
    async def get_by_module(self, module_id: ModuleId) -> list[FactoryBuild]:
        ...
    
    @abstractmethod
    async def get_latest_for_project(self, project_id: ProjectId) -> FactoryBuild | None:
        ...
    
    @abstractmethod
    async def update(self, build: FactoryBuild) -> None:
        ...


class BenchmarkRepository(ABC):
    """Repository für Benchmark-Ergebnisse."""
    
    @abstractmethod
    async def add(self, benchmark: FactoryBenchmark) -> None:
        ...
    
    @abstractmethod
    async def get_by_type(self, factory_type_id: FactoryTypeId) -> list[FactoryBenchmark]:
        ...
    
    @abstractmethod
    async def get_latest(self, factory_type_id: FactoryTypeId, variant: str | None = None) -> FactoryBenchmark | None:
        ...
    
    @abstractmethod
    async def list_all(self) -> list[FactoryBenchmark]:
        ...


class GateRepository(ABC):
    """Repository für Captain-Gates."""
    
    @abstractmethod
    async def add(self, gate: FactoryGate) -> None:
        ...
    
    @abstractmethod
    async def get(self, gate_id: str) -> FactoryGate | None:
        ...
    
    @abstractmethod
    async def get_pending(self) -> list[FactoryGate]:
        """Alle offenen Gates laden."""
        ...
    
    @abstractmethod
    async def get_by_target(self, target_id: str) -> list[FactoryGate]:
        ...
    
    @abstractmethod
    async def update(self, gate: FactoryGate) -> None:
        ...


class GraphRepository(ABC):
    """Repository für Dependency-Graph (GraphView)."""
    
    @abstractmethod
    async def get_project_graph(self, project_id: ProjectId) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Vollständigen Graph für ein Projekt laden."""
        ...
    
    @abstractmethod
    async def get_module_subgraph(self, module_id: ModuleId, depth: int = 2) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Teilgraph um ein Modul (Dependencies + Dependents)."""
        ...


# Aggregiertes Repository-Interface für DI
class FactoryStudioRepositories(ABC):
    """Fassade für alle Repositories (einfacher DI-Zugriff)."""
    
    @property
    @abstractmethod
    def projects(self) -> ProjectRepository:
        ...
    
    @property
    @abstractmethod
    def modules(self) -> ModuleRepository:
        ...
    
    @property
    @abstractmethod
    def builds(self) -> BuildRepository:
        ...
    
    @property
    @abstractmethod
    def benchmarks(self) -> BenchmarkRepository:
        ...
    
    @property
    @abstractmethod
    def gates(self) -> GateRepository:
        ...
    
    @property
    @abstractmethod
    def graph(self) -> GraphRepository:
        ...