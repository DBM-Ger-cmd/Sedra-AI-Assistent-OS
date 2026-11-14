"""Factory Studio Use Cases — Project Management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.entities import FactoryProject, ProjectStatus
from ...domain.repositories import ProjectRepository, FactoryStudioRepositories
from ...domain.value_objects import ProjectId
from ..dtos import ProjectDTO, ProjectListResponse
from ..ports import FactoryRegistryPort, NotificationPort


@dataclass
class CreateProjectRequest:
    name: str
    display_name: str
    description: str = ""
    factory_type_id: str = "project_type"
    metadata: dict[str, Any] = None


@dataclass
class CreateProjectResponse:
    project: ProjectDTO
    success: bool = True
    message: str = ""


class CreateProjectUseCase:
    """Erstellt ein neues Factory-Projekt."""
    
    def __init__(
        self,
        repositories: FactoryStudioRepositories,
        factory_registry: FactoryRegistryPort,
        notifications: NotificationPort,
    ):
        self.repos = repositories
        self.factory_registry = factory_registry
        self.notifications = notifications
    
    async def execute(self, request: CreateProjectRequest) -> CreateProjectResponse:
        # Prüfen ob Factory-Typ existiert und bereit ist
        type_info = await self.factory_registry.get_type(request.factory_type_id)
        if not type_info:
            return CreateProjectResponse(
                project=None,
                success=False,
                message=f"Factory-Typ '{request.factory_type_id}' nicht gefunden"
            )
        if type_info.get("zustand") not in ("ready", "active"):
            return CreateProjectResponse(
                project=None,
                success=False,
                message=f"Factory-Typ '{request.factory_type_id}' nicht bereit (Status: {type_info.get('zustand')})"
            )
        
        # Projekt erstellen
        project = FactoryProject(
            name=request.name,
            display_name=request.display_name or request.name,
            description=request.description,
            factory_type_id=request.factory_type_id,
            metadata=request.metadata or {},
        )
        
        # In Repository speichern
        await self.repos.projects.add(project)
        
        # DTO zurückgeben
        dto = ProjectDTO(
            id=project.id,
            name=project.name,
            display_name=project.display_name,
            description=project.description,
            factory_type_id=project.factory_type_id,
            status=project.status.value,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            metadata=project.metadata,
        )
        
        return CreateProjectResponse(project=dto, message="Projekt erstellt")


@dataclass
class ListProjectsResponse:
    projects: list[ProjectDTO]
    total: int


class ListProjectsUseCase:
    """Listet alle Factory-Projekte."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, status: str | None = None) -> ListProjectsResponse:
        projects = await self.repos.projects.list_all(status)
        dtos = [self._to_dto(p) for p in projects]
        return ListProjectsResponse(projects=dtos, total=len(dtos))
    
    def _to_dto(self, project: FactoryProject) -> ProjectDTO:
        return ProjectDTO(
            id=project.id,
            name=project.name,
            display_name=project.display_name,
            description=project.description,
            factory_type_id=project.factory_type_id,
            status=project.status.value,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            metadata=project.metadata,
            modules_count=len(project.modules),
            last_build_status=project.last_build.status.value if project.last_build else None,
            last_build_at=project.last_build.finished_at.isoformat() if project.last_build and project.last_build.finished_at else None,
        )


@dataclass
class GetProjectResponse:
    project: ProjectDTO | None
    success: bool = True
    message: str = ""


class GetProjectUseCase:
    """Lädt ein einzelnes Projekt mit Details."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, project_id: str) -> GetProjectResponse:
        project = await self.repos.projects.get(ProjectId(project_id))
        if not project:
            return GetProjectResponse(project=None, success=False, message="Projekt nicht gefunden")
        
        return GetProjectResponse(project=self._to_dto(project))
    
    def _to_dto(self, project: FactoryProject) -> ProjectDTO:
        return ProjectDTO(
            id=project.id,
            name=project.name,
            display_name=project.display_name,
            description=project.description,
            factory_type_id=project.factory_type_id,
            status=project.status.value,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            metadata=project.metadata,
            modules_count=len(project.modules),
            last_build_status=project.last_build.status.value if project.last_build else None,
            last_build_at=project.last_build.finished_at.isoformat() if project.last_build and project.last_build.finished_at else None,
        )


@dataclass
class UpdateProjectRequest:
    project_id: str
    display_name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class UpdateProjectResponse:
    project: ProjectDTO | None
    success: bool = True
    message: str = ""


class UpdateProjectUseCase:
    """Aktualisiert Projekt-Metadaten."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, request: UpdateProjectRequest) -> UpdateProjectResponse:
        project = await self.repos.projects.get(ProjectId(request.project_id))
        if not project:
            return UpdateProjectResponse(project=None, success=False, message="Projekt nicht gefunden")
        
        if request.display_name is not None:
            project.display_name = request.display_name
        if request.description is not None:
            project.description = request.description
        if request.metadata is not None:
            project.metadata.update(request.metadata)
        
        project.updated_at = project.updated_at.__class__.now()
        await self.repos.projects.update(project)
        
        return UpdateProjectResponse(project=self._to_dto(project), message="Projekt aktualisiert")
    
    def _to_dto(self, project: FactoryProject) -> ProjectDTO:
        return ProjectDTO(
            id=project.id,
            name=project.name,
            display_name=project.display_name,
            description=project.description,
            factory_type_id=project.factory_type_id,
            status=project.status.value,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            metadata=project.metadata,
            modules_count=len(project.modules),
        )


@dataclass
class DeleteProjectResponse:
    success: bool = True
    message: str = ""


class DeleteProjectUseCase:
    """Löscht ein Projekt (nur wenn keine aktiven Builds)."""
    
    def __init__(self, repositories: FactoryStudioRepositories):
        self.repos = repositories
    
    async def execute(self, project_id: str) -> DeleteProjectResponse:
        project = await self.repos.projects.get(ProjectId(project_id))
        if not project:
            return DeleteProjectResponse(success=False, message="Projekt nicht gefunden")
        
        # Prüfen: keine aktiven Builds
        builds = await self.repos.builds.get_by_project(ProjectId(project_id))
        active_builds = [b for b in builds if b.status.value in ("pending", "running")]
        if active_builds:
            return DeleteProjectResponse(success=False, message="Aktive Builds vorhanden, Projekt kann nicht gelöscht werden")
        
        # Module prüfen
        modules = await self.repos.modules.get_by_project(ProjectId(project_id))
        if modules:
            return DeleteProjectResponse(success=False, message="Projekt enthält noch Module, diese zuerst entfernen")
        
        deleted = await self.repos.projects.delete(ProjectId(project_id))
        if not deleted:
            return DeleteProjectResponse(success=False, message="Löschen fehlgeschlagen")
        
        return DeleteProjectResponse(message="Projekt gelöscht")