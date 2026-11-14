"""Main ViewModel — Factory Studio Root ViewModel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ....di import ServiceContainer, get_container


@dataclass
class MainViewModel:
    """Root ViewModel für Factory Studio Tab.
    
    Koordiniert alle Sub-ViewModels und hält globale State.
    """
    
    container: ServiceContainer
    
    # Sub-ViewModels (lazy loaded)
    _project_browser: Any = field(default=None, init=False, repr=False)
    _graph_view: Any = field(default=None, init=False, repr=False)
    _execution_view: Any = field(default=None, init=False, repr=False)
    _status_dashboard: Any = field(default=None, init=False, repr=False)
    _gate_panel: Any = field(default=None, init=False, repr=False)
    
    # Global State
    is_loading: bool = field(default=False, init=False)
    status_message: str = field(default="Bereit", init=False)
    selected_project_id: str | None = field(default=None, init=False)
    selected_module_id: str | None = field(default=None, init=False)
    
    def __post_init__(self):
        if self.container is None:
            self.container = get_container()
    
    @property
    def project_browser(self):
        """ProjectBrowser ViewModel (lazy)."""
        if self._project_browser is None:
            from .project_browser_vm import ProjectBrowserViewModel
            self._project_browser = ProjectBrowserViewModel(self)
        return self._project_browser
    
    @property
    def graph_view(self):
        """GraphView ViewModel (lazy)."""
        if self._graph_view is None:
            from .graph_view_vm import GraphViewViewModel
            self._graph_view = GraphViewViewModel(self)
        return self._graph_view
    
    @property
    def execution_view(self):
        """ExecutionView ViewModel (lazy)."""
        if self._execution_view is None:
            from .execution_view_vm import ExecutionViewViewModel
            self._execution_view = ExecutionViewViewModel(self)
        return self._execution_view
    
    @property
    def status_dashboard(self):
        """StatusDashboard ViewModel (lazy)."""
        if self._status_dashboard is None:
            from .status_dashboard_vm import StatusDashboardViewModel
            self._status_dashboard = StatusDashboardViewModel(self)
        return self._status_dashboard
    
    @property
    def gate_panel(self):
        """GatePanel ViewModel (lazy)."""
        if self._gate_panel is None:
            from .gate_panel_vm import GatePanelViewModel
            self._gate_panel = GatePanelViewModel(self)
        return self._gate_panel
    
    async def initialize(self):
        """Initialisiert alle Sub-ViewModels."""
        self.is_loading = True
        self.status_message = "Initialisiere Factory Studio..."
        
        try:
            # Projekte laden
            await self.project_browser.load_projects()
            self.status_message = "Bereit"
        except Exception as e:
            self.status_message = f"Fehler: {e}"
        finally:
            self.is_loading = False
    
    async def refresh_all(self):
        """Aktualisiert alle Views."""
        await self.project_browser.load_projects()
        if self.selected_project_id:
            await self.graph_view.load_graph(self.selected_project_id)
            await self.execution_view.load_builds(self.selected_project_id)
        await self.status_dashboard.refresh()
        await self.gate_panel.refresh()
    
    def select_project(self, project_id: str):
        """Projekt selektiert -> abhängige Views aktualisieren."""
        self.selected_project_id = project_id
        self.selected_module_id = None
        # Sub-ViewModels benachrichtigen
    
    def select_module(self, module_id: str):
        """Modul selektiert."""
        self.selected_module_id = module_id