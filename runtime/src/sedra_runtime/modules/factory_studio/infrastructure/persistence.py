"""In-Memory Persistenz — Factory Studio Repository-Implementierungen.

Einfache In-Memory Implementation für Entwicklung/Testing.
Produktion: Austausch gegen PostgreSQL/SQLite Implementation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...domain.entities import FactoryProject, FactoryModule, FactoryBuild, FactoryBenchmark, FactoryGate, ProjectStatus, ModuleStatus, BuildStatus
from ...domain.repositories import (
    ProjectRepository, ModuleRepository, BuildRepository, 
    BenchmarkRepository, GateRepository, GraphRepository,
    FactoryStudioRepositories,
)
from ...domain.value_objects import ProjectId, ModuleId, BuildId, FactoryTypeId, GraphNode, GraphEdge


class InMemoryProjectRepository(ProjectRepository):
    """In-Memory Projekt-Repository."""
    
    def __init__(self):
        self._projects: dict[str, FactoryProject] = {}
        self._by_name: dict[str, str] = {}  # name -> id
    
    async def add(self, project: FactoryProject) -> None:
        self._projects[project.id] = project
        self._by_name[project.name] = project.id
    
    async def get(self, project_id: ProjectId) -> FactoryProject | None:
        return self._projects.get(project_id.value)
    
    async def get_by_name(self, name: str) -> FactoryProject | None:
        pid = self._by_name.get(name)
        if pid:
            return self._projects.get(pid)
        return None
    
    async def list_all(self, status: str | None = None) -> list[FactoryProject]:
        projects = list(self._projects.values())
        if status:
            projects = [p for p in projects if p.status.value == status]
        # Neueste zuerst
        projects.sort(key=lambda p: p.created_at, reverse=True)
        return projects
    
    async def update(self, project: FactoryProject) -> None:
        if project.id in self._projects:
            self._projects[project.id] = project
            self._by_name[project.name] = project.id
    
    async def delete(self, project_id: ProjectId) -> bool:
        project = self._projects.pop(project_id.value, None)
        if project:
            self._by_name.pop(project.name, None)
            return True
        return False


class InMemoryModuleRepository(ModuleRepository):
    """In-Memory Modul-Repository."""
    
    def __init__(self):
        self._modules: dict[str, FactoryModule] = {}
        self._by_project: dict[str, list[str]] = defaultdict(list)  # project_id -> [module_ids]
        self._by_name_project: dict[tuple[str, str], str] = {}  # (name, project_id) -> module_id
    
    async def add(self, module: FactoryModule) -> None:
        self._modules[module.id] = module
        self._by_project[module.project_id].append(module.id)
        self._by_name_project[(module.name, module.project_id)] = module.id
    
    async def get(self, module_id: ModuleId) -> FactoryModule | None:
        return self._modules.get(module_id.value)
    
    async def get_by_project(self, project_id: ProjectId) -> list[FactoryModule]:
        return [self._modules[mid] for mid in self._by_project.get(project_id.value, [])]
    
    async def get_by_name_and_project(self, project_id: ProjectId, name: str) -> FactoryModule | None:
        mid = self._by_name_project.get((name, project_id.value))
        if mid:
            return self._modules.get(mid)
        return None
    
    async def update(self, module: FactoryModule) -> None:
        if module.id in self._modules:
            self._modules[module.id] = module
    
    async def delete(self, module_id: ModuleId) -> bool:
        module = self._modules.pop(module_id.value, None)
        if module:
            self._by_project[module.project_id].remove(module.id)
            self._by_name_project.pop((module.name, module.project_id), None)
            return True
        return False


class InMemoryBuildRepository(BuildRepository):
    """In-Memory Build-Repository."""
    
    def __init__(self):
        self._builds: dict[str, FactoryBuild] = {}
        self._by_project: dict[str, list[str]] = defaultdict(list)
        self._by_module: dict[str, list[str]] = defaultdict(list)
    
    async def add(self, build: FactoryBuild) -> None:
        self._builds[build.id] = build
        self._by_project[build.project_id].append(build.id)
        if build.module_id:
            self._by_module[build.module_id].append(build.id)
    
    async def get(self, build_id: BuildId) -> FactoryBuild | None:
        return self._builds.get(build_id.value)
    
    async def get_by_project(self, project_id: ProjectId) -> list[FactoryBuild]:
        return [self._builds[bid] for bid in self._by_project.get(project_id.value, [])]
    
    async def get_by_module(self, module_id: ModuleId) -> list[FactoryBuild]:
        return [self._builds[bid] for bid in self._by_module.get(module_id.value, [])]
    
    async def get_latest_for_project(self, project_id: ProjectId) -> FactoryBuild | None:
        builds = self._by_project.get(project_id.value, [])
        if not builds:
            return None
        # Neueste nach started_at
        latest_id = max(builds, key=lambda bid: self._builds[bid].started_at or "")
        return self._builds.get(latest_id)
    
    async def update(self, build: FactoryBuild) -> None:
        if build.id in self._builds:
            self._builds[build.id] = build


class InMemoryBenchmarkRepository(BenchmarkRepository):
    """In-Memory Benchmark-Repository."""
    
    def __init__(self):
        self._benchmarks: dict[str, FactoryBenchmark] = {}
        self._by_type: dict[str, list[str]] = defaultdict(list)
    
    async def add(self, benchmark: FactoryBenchmark) -> None:
        self._benchmarks[benchmark.id] = benchmark
        self._by_type[benchmark.factory_type_id].append(benchmark.id)
    
    async def get_by_type(self, factory_type_id: FactoryTypeId) -> list[FactoryBenchmark]:
        return [self._benchmarks[bid] for bid in self._by_type.get(factory_type_id.value, [])]
    
    async def get_latest(self, factory_type_id: FactoryTypeId, variant: str | None = None) -> FactoryBenchmark | None:
        benchmarks = self._by_type.get(factory_type_id.value, [])
        if not benchmarks:
            return None
        if variant:
            benchmarks = [bid for bid in benchmarks if self._benchmarks[bid].variant == variant]
        if not benchmarks:
            return None
        latest_id = max(benchmarks, key=lambda bid: self._benchmarks[bid].created_at)
        return self._benchmarks.get(latest_id)
    
    async def list_all(self) -> list[FactoryBenchmark]:
        return list(self._benchmarks.values())


class InMemoryGateRepository(GateRepository):
    """In-Memory Gate-Repository."""
    
    def __init__(self):
        self._gates: dict[str, FactoryGate] = {}
        self._by_target: dict[str, list[str]] = defaultdict(list)
    
    async def add(self, gate: FactoryGate) -> None:
        self._gates[gate.id] = gate
        self._by_target[gate.target_id].append(gate.id)
    
    async def get(self, gate_id: str) -> FactoryGate | None:
        return self._gates.get(gate_id)
    
    async def get_pending(self) -> list[FactoryGate]:
        return [g for g in self._gates.values() if g.status == "pending"]
    
    async def get_by_target(self, target_id: str) -> list[FactoryGate]:
        return [self._gates[gid] for gid in self._by_target.get(target_id, [])]
    
    async def update(self, gate: FactoryGate) -> None:
        if gate.id in self._gates:
            self._gates[gate.id] = gate


class InMemoryGraphRepository(GraphRepository):
    """In-Memory Graph-Repository (berechnet Graph on-the-fly)."""
    
    def __init__(self, project_repo: InMemoryProjectRepository, module_repo: InMemoryModuleRepository):
        self.project_repo = project_repo
        self.module_repo = module_repo
    
    async def get_project_graph(self, project_id: ProjectId) -> tuple[list[GraphNode], list[GraphEdge]]:
        project = await self.project_repo.get(project_id)
        if not project:
            return [], []
        
        modules = await self.module_repo.get_by_project(project_id)
        
        nodes = []
        edges = []
        
        # Projekt-Node
        nodes.append(GraphNode(
            id=project.id,
            label=project.display_name or project.name,
            node_type="project",
            status=project.status.value,
            metadata={"factory_type": project.factory_type_id},
        ))
        
        # Modul-Nodes
        for module in modules:
            nodes.append(GraphNode(
                id=module.id,
                label=module.display_name or module.name,
                node_type="module",
                status=module.status.value,
                metadata={"layer": module.layer, "type": module.module_type_id},
            ))
            # Edge: Project -> Module
            edges.append(GraphEdge(
                source=project.id,
                target=module.id,
                edge_type="contains",
            ))
            # Dependency Edges
            for dep_id in module.depends_on:
                edges.append(GraphEdge(
                    source=module.id,
                    target=dep_id,
                    edge_type="depends_on",
                ))
        
        return nodes, edges
    
    async def get_module_subgraph(self, module_id: ModuleId, depth: int = 2) -> tuple[list[GraphNode], list[GraphEdge]]:
        module = await self.module_repo.get(module_id)
        if not module:
            return [], []
        
        # BFS für Dependencies und Dependents
        visited = set()
        nodes = []
        edges = []
        
        def add_module(m_id: str, current_depth: int, is_dependency: bool):
            if current_depth > depth or m_id in visited:
                return
            visited.add(m_id)
            m = self._modules.get(m_id)
            if not m:
                return
            
            nodes.append(GraphNode(
                id=m.id,
                label=m.display_name or m.name,
                node_type="module",
                status=m.status.value,
                metadata={"layer": m.layer, "type": m.module_type_id},
            ))
            
            # Dependencies (outgoing)
            for dep_id in m.depends_on:
                edges.append(GraphEdge(
                    source=m.id,
                    target=dep_id,
                    edge_type="depends_on",
                ))
                add_module(dep_id, current_depth + 1, True)
            
            # Dependents (incoming) - finden über alle Module
            if not is_dependency:  # nur für Start-Modul Dependents suchen
                for other in self._modules.values():
                    if module_id.value in other.depends_on:
                        edges.append(GraphEdge(
                            source=other.id,
                            target=m.id,
                            edge_type="depends_on",
                        ))
                        add_module(other.id, current_depth + 1, False)
        
        # Wir brauchen Zugriff auf alle Module
        self._modules = {m.id: m for m in await self.module_repo.get_by_project(ProjectId(module.project_id))}
        
        add_module(module_id.value, 0, False)
        
        return nodes, edges


class InMemoryFactoryStudioRepositories(FactoryStudioRepositories):
    """Aggregierte In-Memory Repositories für DI."""
    
    def __init__(self):
        self._projects = InMemoryProjectRepository()
        self._modules = InMemoryModuleRepository()
        self._builds = InMemoryBuildRepository()
        self._benchmarks = InMemoryBenchmarkRepository()
        self._gates = InMemoryGateRepository()
        self._graph = InMemoryGraphRepository(self._projects, self._modules)
    
    @property
    def projects(self) -> ProjectRepository:
        return self._projects
    
    @property
    def modules(self) -> ModuleRepository:
        return self._modules
    
    @property
    def builds(self) -> BuildRepository:
        return self._builds
    
    @property
    def benchmarks(self) -> BenchmarkRepository:
        return self._benchmarks
    
    @property
    def gates(self) -> GateRepository:
        return self._gates
    
    @property
    def graph(self) -> GraphRepository:
        return self._graph