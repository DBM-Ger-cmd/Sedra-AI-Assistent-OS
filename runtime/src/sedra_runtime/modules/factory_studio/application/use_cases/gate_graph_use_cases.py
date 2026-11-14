"""Factory Studio Use Cases — Gate & Graph Management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.entities import FactoryGate
from ..domain.repositories import FactoryStudioRepositories, GraphRepository
from ..domain.value_objects import ProjectId, ModuleId
from .dtos import GateDTO, GateListResponse, GraphDTO
from .ports import GateClientPort, NotificationPort


@dataclass
class ListGatesResponse:
    gates: list[GateDTO]
    total: int


class ListGatesUseCase:
    """Listet alle offenen Captain-Gates."""
    
    def __init__(self, gate_client: GateClientPort):
        self.gate_client = gate_client
    
    async def execute(self) -> ListGatesResponse:
        gates = await self.gate_client.get_pending_gates()
        dtos = [GateDTO(
            id=g.get("gate_id", g.get("id", "")),
            gate_type=g.get("gate_type", ""),
            target_id=g.get("target_id", ""),
            status=g.get("status", "pending"),
            requested_by=g.get("requested_by", ""),
            requested_at=g.get("requested_at", ""),
            decided_by=g.get("decided_by"),
            decided_at=g.get("decided_at"),
            decision_reason=g.get("decision_reason"),
        ) for g in gates]
        return ListGatesResponse(gates=dtos, total=len(dtos))


@dataclass
class ApproveGateRequest:
    gate_id: str


@dataclass
class ApproveGateResponse:
    success: bool = True
    message: str = ""


class ApproveGateUseCase:
    """Genehmigt ein Captain-Gate."""
    
    def __init__(
        self,
        gate_client: GateClientPort,
        repositories: FactoryStudioRepositories,
        notifications: NotificationPort,
    ):
        self.gate_client = gate_client
        self.repos = repositories
        self.notifications = notifications
    
    async def execute(self, request: ApproveGateRequest) -> ApproveGateResponse:
        result = await self.gate_client.approve_gate(request.gate_id)
        
        if not result.get("success", True):
            return ApproveGateResponse(success=False, message=result.get("error", "Genehmigung fehlgeschlagen"))
        
        await self.notifications.notify_gate_decided(request.gate_id, "approved")
        
        return ApproveGateResponse(message="Gate genehmigt")


@dataclass
class RejectGateRequest:
    gate_id: str
    reason: str | None = None


@dataclass
class RejectGateResponse:
    success: bool = True
    message: str = ""


class RejectGateUseCase:
    """Lehnt ein Captain-Gate ab."""
    
    def __init__(
        self,
        gate_client: GateClientPort,
        repositories: FactoryStudioRepositories,
        notifications: NotificationPort,
    ):
        self.gate_client = gate_client
        self.repos = repositories
        self.notifications = notifications
    
    async def execute(self, request: RejectGateRequest) -> RejectGateResponse:
        result = await self.gate_client.reject_gate(request.gate_id, request.reason)
        
        if not result.get("success", True):
            return RejectGateResponse(success=False, message=result.get("error", "Ablehnung fehlgeschlagen"))
        
        await self.notifications.notify_gate_decided(request.gate_id, "rejected")
        
        return RejectGateResponse(message="Gate abgelehnt")


@dataclass
class GetGateStatusResponse:
    gate: GateDTO | None
    success: bool = True
    message: str = ""


class GetGateStatusUseCase:
    """Lädt Gate-Status."""
    
    def __init__(self, gate_client: GateClientPort):
        self.gate_client = gate_client
    
    async def execute(self, gate_id: str) -> GetGateStatusResponse:
        gate = await self.gate_client.get_gate_status(gate_id)
        if not gate:
            return GetGateStatusResponse(gate=None, success=False, message="Gate nicht gefunden")
        
        return GetGateStatusResponse(gate=GateDTO(
            id=gate.get("gate_id", gate.get("id", "")),
            gate_type=gate.get("gate_type", ""),
            target_id=gate.get("target_id", ""),
            status=gate.get("status", "pending"),
            requested_by=gate.get("requested_by", ""),
            requested_at=gate.get("requested_at", ""),
            decided_by=gate.get("decided_by"),
            decided_at=gate.get("decided_at"),
            decision_reason=gate.get("decision_reason"),
        ))


# --- Graph Use Cases ---

@dataclass
class GetProjectGraphResponse:
    graph: GraphDTO
    success: bool = True
    message: str = ""


class GetProjectGraphUseCase:
    """Lädt den vollständigen Dependency-Graph für ein Projekt."""
    
    def __init__(self, graph_repo: GraphRepository):
        self.graph_repo = graph_repo
    
    async def execute(self, project_id: str) -> GetProjectGraphResponse:
        nodes, edges = await self.graph_repo.get_project_graph(ProjectId(project_id))
        
        return GetProjectGraphResponse(graph=GraphDTO(
            nodes=[{
                "id": n.id,
                "label": n.label,
                "node_type": n.node_type,
                "status": n.status,
                "metadata": n.metadata,
            } for n in nodes],
            edges=[{
                "source": e.source,
                "target": e.target,
                "edge_type": e.edge_type,
                "metadata": e.metadata,
            } for e in edges],
        ))


@dataclass
class GetModuleSubgraphResponse:
    graph: GraphDTO
    success: bool = True
    message: str = ""


class GetModuleSubgraphUseCase:
    """Lädt Teilgraph um ein Modul (Dependencies + Dependents)."""
    
    def __init__(self, graph_repo: GraphRepository):
        self.graph_repo = graph_repo
    
    async def execute(self, module_id: str, depth: int = 2) -> GetModuleSubgraphResponse:
        nodes, edges = await self.graph_repo.get_module_subgraph(ModuleId(module_id), depth)
        
        return GetModuleSubgraphResponse(graph=GraphDTO(
            nodes=[{
                "id": n.id,
                "label": n.label,
                "node_type": n.node_type,
                "status": n.status,
                "metadata": n.metadata,
            } for n in nodes],
            edges=[{
                "source": e.source,
                "target": e.target,
                "edge_type": e.edge_type,
                "metadata": e.metadata,
            } for e in edges],
        ))