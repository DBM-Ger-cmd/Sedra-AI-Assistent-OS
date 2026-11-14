"""GraphView ViewModel — Dependency Graph Visualisierung mit GraphX."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from communitytoolkit_mvvm import ObservableObject, ObservableCollection, RelayCommand

from ....di import ServiceContainer
from ...use_cases.gate_graph_use_cases import GetProjectGraphResponse, GetModuleSubgraphResponse


@dataclass
class GraphNodeViewModel(ObservableObject):
    """ViewModel für Graph-Knoten (Vertex)."""
    id: str
    label: str
    node_type: str  # project, module, service
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Computed
    @property
    def color(self) -> str:
        colors = {
            "project": "#0078D7",    # Blue
            "module": "#107C10",     # Green
            "service": "#FF8C00",    # Orange
            "build": "#8764B8",      # Purple
        }
        return colors.get(self.node_type, "#666666")
    
    @property
    def icon(self) -> str:
        icons = {
            "project": "\uE70D",      # Folder
            "module": "\uE95D",       # Cube
            "service": "\uE70E",      # Globe
            "build": "\uE76C",        # Hammer
        }
        return icons.get(self.node_type, "\uE711")


@dataclass
class GraphEdgeViewModel(ObservableObject):
    """ViewModel für Graph-Kanten (Edges)."""
    source: str
    target: str
    edge_type: str = "depends_on"  # depends_on, builds, contains
    
    @property
    def is_dependency(self) -> bool:
        return self.edge_type == "depends_on"


class GraphViewViewModel(ObservableObject):
    """ViewModel für GraphView — Dependency Graph Visualisierung."""
    
    def __init__(self, main_vm: Any):
        self.main_vm = main_vm
        self.container: ServiceContainer = main_vm.container
        
        # GraphX Objects
        self.graph: Any = None  # GraphX.Graph<GraphNodeViewModel, GraphEdgeViewModel>
        self.zoom_control: Any = None  # GraphX.ZoomControl
        
        # Layout
        self.layout_algorithms: list[str] = ["Sugiyama (Hierarchisch)", "Force Directed", "Circular", "Tree"]
        self.selected_layout: str = "Sugiyama (Hierarchisch)"
        
        # State
        self.is_layouting: bool = False
        self.node_count: int = 0
        self.edge_count: int = 0
        
        # Commands
        self.zoom_in_command = RelayCommand(self._zoom_in)
        self.zoom_out_command = RelayCommand(self._zoom_out)
        self.relayout_command = RelayCommand(self._relayout)
        self.show_filter_command = RelayCommand(self._show_filter)
        
        # Project/Module Selection
        self._current_project_id: str | None = None
        self._current_module_id: str | None = None
    
    @property
    def current_project_id(self) -> str | None:
        return self._current_project_id
    
    @current_project_id.setter
    def current_project_id(self, value: str | None):
        self._current_project_id = value
        if value:
            self.load_graph(value)
    
    @property
    def current_module_id(self) -> str | None:
        return self._current_module_id
    
    @current_module_id.setter
    def current_module_id(self, value: str | None):
        self._current_module_id = value
        if value:
            self.load_module_subgraph(value)
    
    async def load_graph(self, project_id: str):
        """Lädt vollständigen Projekt-Graph."""
        self.is_layouting = True
        self.notify_property_changed("is_layouting")
        
        try:
            response: GetProjectGraphResponse = await self.container.get_project_graph.execute(project_id)
            
            if not response.success:
                return
            
            # GraphX Graph erstellen
            from graphx import Graph, Vertex, Edge
            
            self.graph = Graph()
            
            # Vertices hinzufügen
            vertex_map = {}
            for n in response.graph.nodes:
                vm = GraphNodeViewModel(
                    id=n["id"],
                    label=n["label"],
                    node_type=n["node_type"],
                    status=n["status"],
                    metadata=n.get("metadata", {}),
                )
                vertex = Vertex(vm)
                self.graph.AddVertex(vertex)
                vertex_map[n["id"]] = vertex
            
            # Edges hinzufügen
            for e in response.graph.edges:
                source_v = vertex_map.get(e["source"])
                target_v = vertex_map.get(e["target"])
                if source_v and target_v:
                    edge_vm = GraphEdgeViewModel(
                        source=e["source"],
                        target=e["target"],
                        edge_type=e.get("edge_type", "depends_on"),
                    )
                    edge = Edge(source_v, target_v, edge_vm)
                    self.graph.AddEdge(edge)
            
            # Counters aktualisieren
            self.node_count = len(response.graph.nodes)
            self.edge_count = len(response.graph.edges)
            self.notify_property_changed("node_count")
            self.notify_property_changed("edge_count")
            
            # Layout berechnen
            await self._relayout_async()
            
        except Exception as ex:
            print(f"Graph load error: {ex}")
        finally:
            self.is_layouting = False
            self.notify_property_changed("is_layouting")
    
    async def load_module_subgraph(self, module_id: str, depth: int = 2):
        """Lädt Teilgraph um ein Modul."""
        self.is_layouting = True
        self.notify_property_changed("is_layouting")
        
        try:
            response: GetModuleSubgraphResponse = await self.container.get_module_subgraph.execute(module_id, depth)
            
            if not response.success:
                return
            
            # Ähnlich wie load_graph aber für Subgraph
            # ... (Implementation ähnlich)
            
        except Exception as ex:
            print(f"Subgraph load error: {ex}")
        finally:
            self.is_layouting = False
            self.notify_property_changed("is_layouting")
    
    async def _relayout_async(self):
        """Berechnet Layout asynchron."""
        if not self.graph:
            return
        
        self.is_layouting = True
        self.notify_property_changed("is_layouting")
        
        try:
            # GraphX Layout Algorithm ausführen
            if self.zoom_control:
                await self.zoom_control.Graph.LayoutAlgorithmFactory.CreateLayoutAsync(
                    "Sugiyama", 
                    self.zoom_control.Graph,
                    None
                )
                await self.zoom_control.ZoomToFit()
        except Exception as ex:
            print(f"Relayout error: {ex}")
        finally:
            self.is_layouting = False
            self.notify_property_changed("is_layouting")
    
    def _zoom_in(self):
        if self.zoom_control:
            self.zoom_control.ZoomIn()
    
    def _zoom_out(self):
        if self.zoom_control:
            self.zoom_control.ZoomOut()
    
    def _relayout(self):
        # Async wrapper
        import asyncio
        asyncio.create_task(self._relayout_async())
    
    def _show_filter(self):
        # TODO: Filter-Dialog anzeigen
        pass