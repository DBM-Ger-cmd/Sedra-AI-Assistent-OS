"""GatePanel ViewModel — Captain-Gate Approve/Reject Panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from communitytoolkit_mvvm import ObservableObject, ObservableCollection, RelayCommand

from ....di import ServiceContainer
from ...use_cases.gate_graph_use_cases import ListGatesResponse, ApproveGateRequest, RejectGateRequest


@dataclass
class GateItemViewModel(ObservableObject):
    """Gate Item für Panel."""
    gate_id: str
    gate_type: str
    target_id: str
    status: str  # pending, approved, rejected
    requested_by: str
    requested_at: str
    decided_by: str | None = None
    decided_at: str | None = None
    decision_reason: str | None = None


class GatePanelViewModel(ObservableObject):
    """ViewModel für GatePanel — Captain-Gate Approve/Reject."""
    
    def __init__(self, main_vm: Any):
        self.main_vm = main_vm
        self.container: ServiceContainer = main_vm.container
        
        # Collection
        self.gates: ObservableCollection[GateItemViewModel] = ObservableCollection()
        
        # Computed
        self.pending_count: int = 0
        
        # State
        self.is_loading: bool = False
        
        # Commands
        self.approve_gate_command = RelayCommand[str](self._approve_gate)
        self.reject_gate_command = RelayCommand[str](self._reject_gate)
        self.refresh_command = RelayCommand(self.refresh)
        
        # Initial load
        # asyncio.create_task(self.refresh())  # Nicht im Constructor
    
    async def refresh(self):
        """Aktualisiert Gates."""
        self.is_loading = True
        self.notify_property_changed("is_loading")
        
        try:
            response: ListGatesResponse = await self.container.list_gates.execute()
            
            self.gates.clear()
            for g in response.gates:
                self.gates.append(GateItemViewModel(
                    gate_id=g.get("gate_id", g.get("id", "")),
                    gate_type=g.get("gate_type", ""),
                    target_id=g.get("target_id", ""),
                    status=g.get("status", "pending"),
                    requested_by=g.get("requested_by", ""),
                    requested_at=g.get("requested_at", ""),
                    decided_by=g.get("decided_by"),
                    decided_at=g.get("decided_at"),
                    decision_reason=g.get("decision_reason"),
                ))
            
            self.pending_count = sum(1 for g in self.gates if g.status == "pending")
            self.notify_property_changed("gates")
            self.notify_property_changed("pending_count")
        except Exception as ex:
            print(f"GatePanel refresh error: {ex}")
        finally:
            self.notify_property_changed("gates")
            self.notify_property_changed("pending_count")
    
    async def _approve_gate(self, gate_id: str):
        """Genehmigt Gate."""
        try:
            request = ApproveGateRequest(gate_id=gate_id)
            result = await self.container.approve_gate.execute(request)
            
            if result.success:
                await self.refresh()
        except Exception as ex:
            print(f"Approve gate error: {ex}")
    
    async def _reject_gate(self, gate_id: str):
        """Lehnt Gate ab."""
        # TODO: Reason Dialog anzeigen
        try:
            request = RejectGateRequest(gate_id=gate_id, reason="Abgelehnt via GatePanel")
            result = await self.container.reject_gate.execute(request)
            
            if result.success:
                await self.refresh()
        except Exception as ex:
            print(f"Reject gate error: {ex}")