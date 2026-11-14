"""Dependency Injection Container — Factory Studio Desktop App."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...infrastructure.config import FactoryStudioConfig, get_config
from ...infrastructure.external import (
    HttpFactoryRegistryClient,
    HttpEvidenceStoreClient,
    HttpGateClient,
    ConsoleNotificationClient,
    NoOpNotificationClient,
)
from ...infrastructure.persistence import InMemoryFactoryStudioRepositories
from ...application.use_cases.project_use_cases import (
    CreateProjectUseCase, ListProjectsUseCase, GetProjectUseCase,
    UpdateProjectUseCase, DeleteProjectUseCase,
)
from ...application.use_cases.module_use_cases import (
    AddModuleUseCase, ListModulesUseCase, GetModuleUseCase,
    UpdateModuleUseCase, DeleteModuleUseCase,
)
from ...application.use_cases.build_benchmark_use_cases import (
    StartBuildUseCase, ListBuildsUseCase, GetBuildUseCase,
    RunBenchmarkUseCase, CompareVariantsUseCase, ListBenchmarksUseCase,
)
from ...application.use_cases.gate_graph_use_cases import (
    ListGatesUseCase, ApproveGateUseCase, RejectGateUseCase,
    GetGateStatusUseCase, GetProjectGraphUseCase, GetModuleSubgraphUseCase,
)
from ...application.ports import (
    FactoryRegistryPort, EvidenceStorePort, GateClientPort, NotificationPort,
)


@dataclass
class ServiceContainer:
    """DI-Container für Factory Studio Desktop App.
    
    Verwaltet alle Services und ihre Abhängigkeiten.
    """
    
    config: FactoryStudioConfig
    
    # Repositories
    repositories: InMemoryFactoryStudioRepositories
    
    # External Clients
    factory_registry: FactoryRegistryPort
    evidence_store: EvidenceStorePort
    gate_client: GateClientPort
    notifications: NotificationPort
    
    # Use Cases - Project
    create_project: CreateProjectUseCase
    list_projects: ListProjectsUseCase
    get_project: GetProjectUseCase
    update_project: UpdateProjectUseCase
    delete_project: DeleteProjectUseCase
    
    # Use Cases - Module
    add_module: AddModuleUseCase
    list_modules: ListModulesUseCase
    get_module: GetModuleUseCase
    update_module: UpdateModuleUseCase
    delete_module: DeleteModuleUseCase
    
    # Use Cases - Build & Benchmark
    start_build: StartBuildUseCase
    list_builds: ListBuildsUseCase
    get_build: GetBuildUseCase
    run_benchmark: RunBenchmarkUseCase
    compare_variants: CompareVariantsUseCase
    list_benchmarks: ListBenchmarksUseCase
    
    # Use Cases - Gates & Graph
    list_gates: ListGatesUseCase
    approve_gate: ApproveGateUseCase
    reject_gate: RejectGateUseCase
    get_gate_status: GetGateStatusUseCase
    get_project_graph: GetProjectGraphUseCase
    get_module_subgraph: GetModuleSubgraphUseCase
    
    @classmethod
    def create(cls, config: FactoryStudioConfig | None = None) -> "ServiceContainer":
        """Erstellt und verdrahtet den kompletten Container."""
        config = config or get_config()
        
        # Repositories
        repositories = InMemoryFactoryStudioRepositories()
        
        # External Clients (mit Mock-Fallback für Development)
        if config.mock_external_services:
            factory_registry: FactoryRegistryPort = HttpFactoryRegistryClient(config.factory_registry_url)
            evidence_store: EvidenceStorePort = HttpEvidenceStoreClient(config.evidence_store_url)
            gate_client: GateClientPort = HttpGateClient(config.gate_server_url)
        else:
            factory_registry = HttpFactoryRegistryClient(config.factory_registry_url)
            evidence_store = HttpEvidenceStoreClient(config.evidence_store_url)
            gate_client = HttpGateClient(config.gate_server_url)
        
        if config.notification_type == "console":
            notifications: NotificationPort = ConsoleNotificationClient()
        elif config.notification_type == "none":
            notifications = NoOpNotificationClient()
        else:
            notifications = ConsoleNotificationClient()
        
        # Use Cases verdrahten
        return cls(
            config=config,
            repositories=repositories,
            factory_registry=factory_registry,
            evidence_store=evidence_store,
            gate_client=gate_client,
            notifications=notifications,
            
            # Project Use Cases
            create_project=CreateProjectUseCase(repositories, factory_registry, notifications),
            list_projects=ListProjectsUseCase(repositories),
            get_project=GetProjectUseCase(repositories),
            update_project=UpdateProjectUseCase(repositories),
            delete_project=DeleteProjectUseCase(repositories),
            
            # Module Use Cases
            add_module=AddModuleUseCase(repositories, factory_registry),
            list_modules=ListModulesUseCase(repositories),
            get_module=GetModuleUseCase(repositories),
            update_module=UpdateModuleUseCase(repositories),
            delete_module=DeleteModuleUseCase(repositories),
            
            # Build & Benchmark Use Cases
            start_build=StartBuildUseCase(repositories, factory_registry, notifications),
            list_builds=ListBuildsUseCase(repositories),
            get_build=GetBuildUseCase(repositories),
            run_benchmark=RunBenchmarkUseCase(evidence_store, notifications),
            compare_variants=CompareVariantsUseCase(evidence_store),
            list_benchmarks=ListBenchmarksUseCase(evidence_store),
            
            # Gate & Graph Use Cases
            list_gates=ListGatesUseCase(gate_client),
            approve_gate=ApproveGateUseCase(gate_client, repositories, notifications),
            reject_gate=RejectGateUseCase(gate_client, repositories, notifications),
            get_gate_status=GetGateStatusUseCase(gate_client),
            get_project_graph=GetProjectGraphUseCase(repositories.graph),
            get_module_subgraph=GetModuleSubgraphUseCase(repositories.graph),
        )
    
    async def close(self):
        """Schließt alle HTTP-Clients."""
        for client in [self.factory_registry, self.evidence_store, self.gate_client]:
            if hasattr(client, 'close'):
                await client.close()
    
    def get_use_case(self, name: str):
        """Holt Use Case by Name (für ViewModel-Lookup)."""
        return getattr(self, name, None)


# Global Container Instance (Singleton für App-Lifetime)
_container: ServiceContainer | None = None


def get_container(config: FactoryStudioConfig | None = None) -> ServiceContainer:
    """Liefert den globalen Container (erstellt bei erstem Aufruf)."""
    global _container
    if _container is None:
        _container = ServiceContainer.create(config)
    return _container


async def close_container():
    """Schließt den globalen Container."""
    global _container
    if _container:
        await _container.close()
        _container = None