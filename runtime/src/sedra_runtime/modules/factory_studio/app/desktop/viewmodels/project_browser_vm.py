"""ProjectBrowser ViewModel — Baumansicht für Factory-Projekte."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sedra_runtime.modules.factory_studio._mvvm import ObservableObject, ObservableCollection, RelayCommand

from ..di import ServiceContainer
from ....application.use_cases.project_use_cases import CreateProjectRequest, ListProjectsResponse


@dataclass
class ProjectNode:
    """Projekt-Knoten für TreeView."""
    id: str
    name: str
    display_name: str
    status: str
    modules_count: int
    last_build_status: str | None
    children: list["ProjectNode"] = field(default_factory=list)
    is_expanded: bool = True
    is_selected: bool = False


class ProjectBrowserViewModel(ObservableObject):
    """ViewModel für ProjectBrowser TreeView."""
    
    def __init__(self, main_vm: Any):
        self.main_vm = main_vm
        self.container: ServiceContainer = main_vm.container
        
        # Observable Collections für UI-Binding
        self.projects = ObservableCollection[ProjectNode]()
        self.selected_project: ProjectNode | None = None
        
        # Commands
        self.create_project_command = RelayCommand(self._on_create_project)
        self.refresh_command = RelayCommand(self.load_projects)
        self.delete_project_command = RelayCommand(self._on_delete_project)
        self.select_project_command = RelayCommand[ProjectNode](self._on_select_project)
        
        # State
        self.is_loading = False
        self.error_message: str | None = None
    
    async def load_projects(self):
        """Lädt alle Projekte und baut Baum auf."""
        self.is_loading = True
        self.error_message = None
        self.notify_property_changed("is_loading")
        
        try:
            response: ListProjectsResponse = await self.container.list_projects.execute()
            
            self.projects.clear()
            for p_dto in response.projects:
                node = ProjectNode(
                    id=p_dto.id,
                    name=p_dto.name,
                    display_name=p_dto.display_name,
                    status=p_dto.status,
                    modules_count=p_dto.modules_count,
                    last_build_status=p_dto.last_build_status,
                )
                self.projects.append(node)
            
            self.error_message = None
        except Exception as e:
            self.error_message = f"Fehler beim Laden: {e}"
        finally:
            self.is_loading = False
            self.notify_property_changed("is_loading")
            self.notify_property_changed("error_message")
    
    def _on_select_project(self, node: ProjectNode):
        """Projekt in TreeView selektiert."""
        # Vorherige Selektion entfernen
        if self.selected_project:
            self.selected_project.is_selected = False
            self.selected_project.notify_property_changed("is_selected")
        
        node.is_selected = True
        self.selected_project = node
        node.notify_property_changed("is_selected")
        
        # Main VM benachrichtigen
        self.main_vm.select_project(node.id)
    
    async def _on_create_project(self):
        """Neues Projekt erstellen (Dialog -> Use Case)."""
        # TODO: Dialog für Name, DisplayName, FactoryType anzeigen
        # Für Demo: Hardcoded
        from ....application.use_cases.project_use_cases import CreateProjectRequest
        
        result = await self.container.create_project.execute(CreateProjectRequest(
            name="new_project",
            display_name="Neues Projekt",
            factory_type_id="project_type",
        ))
        
        if result.success:
            await self.load_projects()  # Baum aktualisieren
        else:
            # Fehler anzeigen
            pass
    
    async def _on_delete_project(self):
        """Ausgewähltes Projekt löschen."""
        if not self.selected_project:
            return
        
        # TODO: Bestätigungsdialog
        # await self.container.delete_project.execute(self.selected_project.id)
        # await self.load_projects()
        pass