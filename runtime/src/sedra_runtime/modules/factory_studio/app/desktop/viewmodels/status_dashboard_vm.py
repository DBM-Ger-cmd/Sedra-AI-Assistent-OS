"""StatusDashboard ViewModel — Factory Health, Gates, Activity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sedra_runtime.modules.factory_studio._mvvm import ObservableObject, ObservableCollection, RelayCommand

from ..di import ServiceContainer
from ....application.use_cases.gate_graph_use_cases import ListGatesResponse


@dataclass
class HealthCardViewModel(ObservableObject):
    """Health Card für Dashboard."""
    title: str
    value: str
    subtitle: str = ""
    status: str = "info"  # success, warning, error, info
    progress: float = 0
    show_progress: bool = False


@dataclass
class GateItemViewModel(ObservableObject):
    """Gate Item für Liste."""
    gate_id: str
    gate_type: str
    target_id: str
    status: str  # pending, approved, rejected
    requested_by: str
    requested_at: str
    decided_by: str | None = None
    decided_at: str | None = None
    decision_reason: str | None = None


@dataclass
class ActivityItemViewModel(ObservableObject):
    """Activity Feed Item."""
    type: str  # build, benchmark, gate, project, module, error, info
    message: str
    timestamp: str


class StatusDashboardViewModel(ObservableObject):
    """ViewModel für StatusDashboard — Factory Health, Gates, Activity."""
    
    def __init__(self, main_vm: Any):
        self.main_vm = main_vm
        self.container: ServiceContainer = main_vm.container
        
        # Collections
        self.health_cards: ObservableCollection[HealthCardViewModel] = ObservableCollection()
        self.gates: ObservableCollection[GateItemViewModel] = ObservableCollection()
        self.recent_activity: ObservableCollection[ActivityItemViewModel] = ObservableCollection()
        
        # Computed
        self.pending_gates_count: int = 0
        self.last_refresh: str = ""
        self.status_message: str = "Bereit"
        
        # State
        self.is_loading: bool = False
        
        # Commands
        self.refresh_command = RelayCommand(self.refresh)
        self.settings_command = RelayCommand(self._open_settings)
        
        # Selected Project from MainVM
        self._project_id: str | None = None
    
    @property
    def project_id(self) -> str | None:
        return self._project_id
    
    @project_id.setter
    def project_id(self, value: str | None):
        self._project_id = value
        if value:
            self.refresh()
    
    async def refresh(self):
        """Aktualisiert alle Dashboard-Daten."""
        self.is_loading = True
        self.status_message = "Aktualisiere..."
        self.notify_property_changed("is_loading")
        self.notify_property_changed("status_message")
        
        try:
            await self._load_health_cards()
            await self._load_gates()
            await self._load_activity()
            
            self.last_refresh = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            self.status_message = f"Aktualisiert um {self.last_refresh}"
        except Exception as ex:
            self.status_message = f"Fehler: {ex}"
        finally:
            self.is_loading = False
            self.notify_property_changed("is_loading")
            self.notify_property_changed("status_message")
            self.notify_property_changed("last_refresh")
    
    async def _load_health_cards(self):
        """Lädt Health Cards."""
        self.health_cards.clear()
        
        # Factory Registry Health
        try:
            reg_health = await self.container.factory_registry.list_types()
            self.health_cards.append(HealthCardViewModel(
                title="Factory Registry",
                value=str(len(reg_health)),
                subtitle="Typen registriert",
                status="success",
            ))
        except Exception:
            self.health_cards.append(HealthCardViewModel(
                title="Factory Registry",
                value="—",
                subtitle="Nicht erreichbar",
                status="error",
            ))
        
        # Evidence Store Health
        try:
            store_health = self.container.evidence_store.health()
            self.health_cards.append(HealthCardViewModel(
                title="Evidence Store",
                value=str(store_health.get("runs", 0)),
                subtitle=f"Runs, {store_health.get('benchmarks', 0)} Benchmarks",
                status="success" if store_health.get("ok") else "error",
                progress=min(100, store_health.get("runs", 0) * 2),
                show_progress=True,
            ))
        except Exception:
            self.health_cards.append(HealthCardViewModel(
                title="Evidence Store",
                value="—",
                subtitle="Nicht erreichbar",
                status="error",
            ))
        
        # Factory Builder Health (via Registry)
        self.health_cards.append(HealthCardViewModel(
            title="Factory Builder",
            value="Bereit",
            subtitle="Templates geladen",
            status="success",
        ))
        
        # Captain Gates
        pending = sum(1 for g in self.gates if g.status == "pending")
        self.health_cards.append(HealthCardViewModel(
            title="Captain Gates",
            value=str(pending),
            subtitle="Offen" if pending > 0 else "Alle erledigt",
            status="warning" if pending > 0 else "success",
        ))
        
        self.notify_property_changed("health_cards")
    
    async def _load_gates(self):
        """Lädt Captain Gates."""
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
            
            self.pending_gates_count = sum(1 for g in self.gates if g.status == "pending")
            self.notify_property_changed("gates")
            self.notify_property_changed("pending_gates_count")
        except Exception as ex:
            print(f"Load gates error: {ex}")
    
    async def _load_activity(self):
        """Lädt letzte Aktivitäten (Mock für Demo)."""
        self.recent_activity.clear()
        
        # In echt: aus Event Store / Audit Log
        # Für Demo: Mock-Daten
        mock_activities = [
            ActivityItemViewModel(type="build", message="Project 'demo_project' build completed successfully", timestamp=datetime.now().isoformat()),
            ActivityItemViewModel(type="benchmark", message="Benchmark 'project_type' variant 'default' completed (Score: 0.85)", timestamp=datetime.now().isoformat()),
            ActivityItemViewModel(type="gate", message="Gate 'register' approved by Captain", timestamp=datetime.now().isoformat()),
            ActivityItemViewModel(type="project", message="Project 'demo_project' created", timestamp=datetime.now().isoformat()),
        ]
        
        for a in mock_activities:
            self.recent_activity.append(a)
        
        self.notify_property_changed("recent_activity")
    
    def _open_settings(self):
        # TODO: Settings Dialog
        pass


# Import datetime at top level
from datetime import datetime