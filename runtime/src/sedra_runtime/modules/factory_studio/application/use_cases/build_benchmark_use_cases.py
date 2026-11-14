"""Factory Studio Use Cases — Build & Benchmark Management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.entities import FactoryBuild, BuildStatus, FactoryBenchmark
from ...domain.repositories import FactoryStudioRepositories
from ...domain.value_objects import ProjectId, ModuleId, BuildId, FactoryTypeId, BenchmarkConfig
from ..dtos import BuildDTO, BuildListResponse, BenchmarkDTO, BenchmarkListResponse
from ..ports import FactoryRegistryPort, EvidenceStorePort, NotificationPort


@dataclass
class StartBuildRequest:
    project_id: str
    module_id: str | None
    build_type: str  # project, module, service
    factory_type_id: str
    gate: bool = True


@dataclass
class StartBuildResponse:
    build: BuildDTO | None
    success: bool = True
    message: str = ""


class StartBuildUseCase:
    """Startet einen Factory-Build (Project/Module/Service)."""
    
    def __init__(
        self,
        repositories: FactoryStudioRepositories,
        factory_registry: FactoryRegistryPort,
        notifications: NotificationPort,
    ):
        self.repos = repositories
        self.factory_registry = factory_registry
        self.notifications = notifications
    
    async def execute(self, request: StartBuildRequest) -> StartBuildResponse:
        # Projekt prüfen
        project = await self.repos.projects.get(ProjectId(request.project_id))
        if not project:
            return StartBuildResponse(build=None, success=False, message="Projekt nicht gefunden")
        
        # Module prüfen falls angegeben
        if request.module_id:
            module = await self.repos.modules.get(ModuleId(request.module_id))
            if not module or module.project_id != request.project_id:
                return StartBuildResponse(build=None, success=False, message="Modul nicht gefunden oder gehört nicht zu diesem Projekt")
        
        # Factory-Typ prüfen
        type_info = await self.factory_registry.get_type(request.factory_type_id)
        if not type_info:
            return StartBuildResponse(build=None, success=False, message=f"Factory-Typ '{request.factory_type_id}' nicht gefunden")
        
        # Build-Record erstellen
        build = FactoryBuild(
            project_id=request.project_id,
            module_id=request.module_id,
            build_type=request.build_type,
            factory_type_id=request.factory_type_id,
            status=BuildStatus.PENDING,
        )
        
        await self.repos.builds.add(build)
        
        # Build asynchron via Factory Registry starten
        # (In echt: Background Task / Message Queue)
        if request.build_type == "project":
            result = await self.factory_registry.build_project(request.factory_type_id, project.name, gate=request.gate)
        elif request.build_type == "module":
            module = await self.repos.modules.get(ModuleId(request.module_id)) if request.module_id else None
            result = await self.factory_registry.build_module(request.factory_type_id, module.name, request.project_id, gate=request.gate)
        elif request.build_type == "service":
            result = await self.factory_registry.build_service(request.factory_type_id, f"{project.name}_svc", request.project_id, gate=request.gate)
        else:
            return StartBuildResponse(build=None, success=False, message=f"Unbekannter Build-Type: {request.build_type}")
        
        # Build-Status aktualisieren
        build.status = BuildStatus.RUNNING
        build.started_at = build.started_at.__class__.now()
        await self.repos.builds.update(build)
        
        # Ergebnis verarbeiten (vereinfacht - in echt async)
        if result.get("success"):
            build.status = BuildStatus.SUCCESS
            build.success = True
            build.artifacts = result.get("artifacts", [])
        else:
            build.status = BuildStatus.FAILED
            build.success = False
            build.error_message = result.get("message", "Build fehlgeschlagen")
        
        build.finished_at = build.finished_at.__class__.now()
        if build.started_at and build.finished_at:
            build.duration_ms = int((build.finished_at - build.started_at).total_seconds() * 1000)
        
        await self.repos.builds.update(build)
        
        # Notification
        await self.notifications.notify_build_complete(project.name, build.success)
        
        return StartBuildResponse(build=self._to_dto(build), message="Build abgeschlossen")
    
    def _to_dto(self, build: FactoryBuild) -> BuildDTO:
        return BuildDTO(
            id=build.id,
            project_id=build.project_id,
            module_id=build.module_id,
            build_type=build.build_type,
            factory_type_id=build.factory_type_id,
            status=build.status.value,
            started_at=build.started_at.isoformat() if build.started_at else None,
            finished_at=build.finished_at.isoformat() if build.finished_at else None,
            duration_ms=build.duration_ms,
            success=build.success,
            artifacts=build.artifacts,
            error_message=build.error_message,
            metrics=build.metrics,
        )


@dataclass
class ListBuildsResponse:
    builds: list[BuildDTO]
    total: int


class ListBuildsUseCase:
    """Listet Builds eines Projekts."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, project_id: str) -> ListBuildsResponse:
        builds = await self.repos.builds.get_by_project(ProjectId(project_id))
        dtos = [self._to_dto(b) for b in builds]
        return ListBuildsResponse(builds=dtos, total=len(dtos))
    
    def _to_dto(self, build: FactoryBuild) -> BuildDTO:
        return BuildDTO(
            id=build.id,
            project_id=build.project_id,
            module_id=build.module_id,
            build_type=build.build_type,
            factory_type_id=build.factory_type_id,
            status=build.status.value,
            started_at=build.started_at.isoformat() if build.started_at else None,
            finished_at=build.finished_at.isoformat() if build.finished_at else None,
            duration_ms=build.duration_ms,
            success=build.success,
            artifacts=build.artifacts,
            error_message=build.error_message,
            metrics=build.metrics,
        )


@dataclass
class GetBuildResponse:
    build: BuildDTO | None
    success: bool = True
    message: str = ""


class GetBuildUseCase:
    """Lädt Build-Details."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, build_id: str) -> GetBuildResponse:
        build = await self.repos.builds.get(BuildId(build_id))
        if not build:
            return GetBuildResponse(build=None, success=False, message="Build nicht gefunden")
        return GetBuildResponse(build=self._to_dto(build))
    
    def _to_dto(self, build: FactoryBuild) -> BuildDTO:
        return BuildDTO(
            id=build.id,
            project_id=build.project_id,
            module_id=build.module_id,
            build_type=build.build_type,
            factory_type_id=build.factory_type_id,
            status=build.status.value,
            started_at=build.started_at.isoformat() if build.started_at else None,
            finished_at=build.finished_at.isoformat() if build.finished_at else None,
            duration_ms=build.duration_ms,
            success=build.success,
            artifacts=build.artifacts,
            error_message=build.error_message,
            metrics=build.metrics,
        )


# --- Benchmark Use Cases ---

@dataclass
class RunBenchmarkRequest:
    factory_type_id: str
    variant: str = "default"
    params: dict[str, Any] = None
    iterations: int = 3
    build_type: str = "project"
    project_name: str | None = None
    warmup: int = 0
    cleanup_between: bool = True
    gate: bool = True


@dataclass
class RunBenchmarkResponse:
    benchmark: BenchmarkDTO | None
    success: bool = True
    message: str = ""


class RunBenchmarkUseCase:
    """Führt einen Benchmark für einen Factory-Typ aus."""
    
    def __init__(
        self,
        evidence_store: EvidenceStorePort,
        notifications: NotificationPort,
    ):
        self.evidence_store = evidence_store
        self.notifications = notifications
    
    async def execute(self, request: RunBenchmarkRequest) -> RunBenchmarkResponse:
        config = {
            "typ_id": request.factory_type_id,
            "variant": request.variant,
            "params": request.params or {},
            "iterations": request.iterations,
            "build_type": request.build_type,
            "project_name": request.project_name,
            "warmup": request.warmup,
            "cleanup_between": request.cleanup_between,
        }
        
        result = await self.evidence_store.run_benchmark(config)
        
        if not result.get("success", True):
            return RunBenchmarkResponse(benchmark=None, success=False, message=result.get("error", "Benchmark fehlgeschlagen"))
        
        dto = BenchmarkDTO(
            id=result.get("benchmark_id", ""),
            factory_type_id=request.factory_type_id,
            variant=request.variant,
            params=request.params or {},
            score=result.get("score"),
            runs_count=result.get("runs", 0),
            aggregated_metrics=result.get("aggregated_metrics", {}),
            created_at=result.get("created_at", ""),
        )
        
        await self.notifications.notify_benchmark_complete(request.factory_type_id, dto.score or 0.0)
        
        return RunBenchmarkResponse(benchmark=dto, message="Benchmark abgeschlossen")


@dataclass
class CompareVariantsRequest:
    factory_type_id: str
    variants: list[str]
    iterations: int = 3
    build_type: str = "project"
    project_name: str | None = None
    gate: bool = True


@dataclass
class CompareVariantsResponse:
    benchmarks: list[BenchmarkDTO]
    success: bool = True
    message: str = ""


class CompareVariantsUseCase:
    """Vergleicht mehrere Varianten eines Factory-Typs."""
    
    def __init__(self, evidence_store: EvidenceStorePort):
        self.evidence_store = evidence_store
    
    async def execute(self, request: CompareVariantsRequest) -> CompareVariantsResponse:
        variant_configs = []
        for v in request.variants:
            variant_configs.append({
                "typ_id": request.factory_type_id,
                "variant": v,
                "iterations": request.iterations,
                "build_type": request.build_type,
                "project_name": request.project_name,
            })
        
        results = await self.evidence_store.compare_variants(request.factory_type_id, variant_configs)
        
        dtos = []
        for r in results:
            dtos.append(BenchmarkDTO(
                id=r.get("benchmark_id", ""),
                factory_type_id=request.factory_type_id,
                variant=r.get("variant", ""),
                params={},
                score=r.get("score"),
                runs_count=r.get("runs", 0),
                aggregated_metrics=r.get("aggregated_metrics", {}),
                created_at=r.get("created_at", ""),
            ))
        
        return CompareVariantsResponse(benchmarks=dtos, message=f"{len(dtos)} Varianten verglichen")


@dataclass
class ListBenchmarksResponse:
    benchmarks: list[BenchmarkDTO]
    total: int


class ListBenchmarksUseCase:
    """Listet Benchmarks für einen Typ."""
    
    def __init__(self, evidence_store: EvidenceStorePort):
        self.evidence_store = evidence_store
    
    async def execute(self, factory_type_id: str | None = None) -> ListBenchmarksResponse:
        benches = await self.evidence_store.get_benchmarks(factory_type_id)
        dtos = [BenchmarkDTO(
            id=b.get("benchmark_id", ""),
            factory_type_id=b.get("typ_id", ""),
            variant=b.get("variant", ""),
            params=b.get("params", {}),
            score=b.get("score"),
            runs_count=b.get("runs_count", 0),
            aggregated_metrics=b.get("aggregated_metrics", {}),
            created_at=b.get("created_at", ""),
        ) for b in benches]
        return ListBenchmarksResponse(benchmarks=dtos, total=len(dtos))