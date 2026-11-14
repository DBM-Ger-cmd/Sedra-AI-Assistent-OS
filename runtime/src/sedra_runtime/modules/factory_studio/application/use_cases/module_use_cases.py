"""Factory Studio Use Cases — Module Management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.entities import FactoryModule, ModuleStatus
from ..domain.repositories import FactoryStudioRepositories
from ..domain.value_objects import ModuleId, ProjectId
from .dtos import ModuleDTO, ModuleListResponse
from .ports import FactoryRegistryPort


@dataclass
class AddModuleRequest:
    project_id: str
    name: str
    display_name: str
    module_type_id: str
    layer: str = "domain"
    metadata: dict[str, Any] = None


@dataclass
class AddModuleResponse:
    module: ModuleDTO | None
    success: bool = True
    message: str = ""


class AddModuleUseCase:
    """Fügt ein Modul zu einem Projekt hinzu."""
    
    def __init__(
        self,
        repositories: FactoryStudioRepositories,
        factory_registry: FactoryRegistryPort,
    ):
        self.repos = repositories
        self.factory_registry = factory_registry
    
    async def execute(self, request: AddModuleRequest) -> AddModuleResponse:
        # Projekt prüfen
        project = await self.repos.projects.get(ProjectId(request.project_id))
        if not project:
            return AddModuleResponse(module=None, success=False, message="Projekt nicht gefunden")
        
        # Factory-Typ prüfen
        type_info = await self.factory_registry.get_type(request.module_type_id)
        if not type_info:
            return AddModuleResponse(module=None, success=False, message=f"Factory-Typ '{request.module_type_id}' nicht gefunden")
        if type_info.get("zustand") not in ("ready", "active"):
            return AddModuleResponse(module=None, success=False, message=f"Factory-Typ nicht bereit")
        
        # Namenskollision prüfen
        existing = await self.repos.modules.get_by_name_and_project(ProjectId(request.project_id), request.name)
        if existing:
            return AddModuleResponse(module=None, success=False, message=f"Modul '{request.name}' existiert bereits in diesem Projekt")
        
        # Modul erstellen
        module = FactoryModule(
            project_id=request.project_id,
            name=request.name,
            display_name=request.display_name or request.name,
            module_type_id=request.module_type_id,
            layer=request.layer,
            metadata=request.metadata or {},
        )
        
        await self.repos.modules.add(module)
        
        dto = ModuleDTO(
            id=module.id,
            project_id=module.project_id,
            name=module.name,
            display_name=module.display_name,
            module_type_id=module.module_type_id,
            status=module.status.value,
            layer=module.layer,
            created_at=module.created_at.isoformat(),
            updated_at=module.updated_at.isoformat(),
            metadata=module.metadata,
            depends_on=module.depends_on,
        )
        
        return AddModuleResponse(module=dto, message="Modul hinzugefügt")


@dataclass
class ListModulesResponse:
    modules: list[ModuleDTO]
    total: int


class ListModulesUseCase:
    """Listet Module eines Projekts."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, project_id: str) -> ListModulesResponse:
        modules = await self.repos.modules.get_by_project(ProjectId(project_id))
        dtos = [self._to_dto(m) for m in modules]
        return ListModulesResponse(modules=dtos, total=len(dtos))
    
    def _to_dto(self, module: FactoryModule) -> ModuleDTO:
        return ModuleDTO(
            id=module.id,
            project_id=module.project_id,
            name=module.name,
            display_name=module.display_name,
            module_type_id=module.module_type_id,
            status=module.status.value,
            layer=module.layer,
            created_at=module.created_at.isoformat(),
            updated_at=module.updated_at.isoformat(),
            metadata=module.metadata,
            depends_on=module.depends_on,
        )


@dataclass
class GetModuleResponse:
    module: ModuleDTO | None
    success: bool = True
    message: str = ""


class GetModuleUseCase:
    """Lädt ein einzelnes Modul."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, module_id: str) -> GetModuleResponse:
        module = await self.repos.modules.get(ModuleId(module_id))
        if not module:
            return GetModuleResponse(module=None, success=False, message="Modul nicht gefunden")
        return GetModuleResponse(module=self._to_dto(module))
    
    def _to_dto(self, module: FactoryModule) -> ModuleDTO:
        return ModuleDTO(
            id=module.id,
            project_id=module.project_id,
            name=module.name,
            display_name=module.display_name,
            module_type_id=module.module_type_id,
            status=module.status.value,
            layer=module.layer,
            created_at=module.created_at.isoformat(),
            updated_at=module.updated_at.isoformat(),
            metadata=module.metadata,
            depends_on=module.depends_on,
        )


@dataclass
class UpdateModuleRequest:
    module_id: str
    display_name: str | None = None
    status: str | None = None
    layer: str | None = None
    depends_on: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class UpdateModuleResponse:
    module: ModuleDTO | None
    success: bool = True
    message: str = ""


class UpdateModuleUseCase:
    """Aktualisiert ein Modul."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, request: UpdateModuleRequest) -> UpdateModuleResponse:
        module = await self.repos.modules.get(ModuleId(request.module_id))
        if not module:
            return UpdateModuleResponse(module=None, success=False, message="Modul nicht gefunden")
        
        if request.display_name is not None:
            module.display_name = request.display_name
        if request.status is not None:
            try:
                module.status = ModuleStatus(request.status)
            except ValueError:
                return UpdateModuleResponse(module=None, success=False, message=f"Ungültiger Status: {request.status}")
        if request.layer is not None:
            module.layer = request.layer
        if request.depends_on is not None:
            module.depends_on = request.depends_on
        if request.metadata is not None:
            module.metadata.update(request.metadata)
        
        module.updated_at = module.updated_at.__class__.now()
        await self.repos.modules.update(module)
        
        return UpdateModuleResponse(module=self._to_dto(module), message="Modul aktualisiert")
    
    def _to_dto(self, module: FactoryModule) -> ModuleDTO:
        return ModuleDTO(
            id=module.id,
            project_id=module.project_id,
            name=module.name,
            display_name=module.display_name,
            module_type_id=module.module_type_id,
            status=module.status.value,
            layer=module.layer,
            created_at=module.created_at.isoformat(),
            updated_at=module.updated_at.isoformat(),
            metadata=module.metadata,
            depends_on=module.depends_on,
        )


@dataclass
class DeleteModuleResponse:
    success: bool = True
    message: str = ""


class DeleteModuleUseCase:
    """Entfernt ein Modul aus dem Projekt."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, module_id: str) -> DeleteModuleResponse:
        module = await self.repos.modules.get(ModuleId(module_id))
        if not module:
            return DeleteModuleResponse(success=False, message="Modul nicht gefunden")
        
        # Builds prüfen
        builds = await self.repos.builds.get_by_module(ModuleId(module_id))
        active = [b for b in builds if b.status.value in ("pending", "running")]
        if active:
            return DeleteModuleResponse(success=False, message="Aktive Builds für dieses Modul vorhanden")
        
        deleted = await self.repos.modules.delete(ModuleId(module_id))
        if not deleted:
            return DeleteModuleResponse(success=False, message="Löschen fehlgeschlagen")
        
        return DeleteModuleResponse(message="Modul entfernt")