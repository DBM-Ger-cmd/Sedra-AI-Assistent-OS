"""Application Ports — Factory Studio Schnittstellen zu externen Systemen.

Definiert die Verträge für externe Services (Factory Registry, Evidence Store, Gate-Client).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class FactoryRegistryPort(ABC):
    """Port für Factory Registry Zugriff (HTTP/JSON)."""
    
    @abstractmethod
    async def list_types(self) -> list[dict[str, Any]]:
        """Alle Factory-Typen listen."""
        ...
    
    @abstractmethod
    async def get_type(self, typ_id: str) -> dict[str, Any] | None:
        """Factory-Typ Details laden."""
        ...
    
    @abstractmethod
    async def build_project(self, typ_id: str, name: str, gate: bool = True) -> dict[str, Any]:
        """Projekt via Factory Builder erstellen."""
        ...
    
    @abstractmethod
    async def build_module(self, typ_id: str, name: str, project: str, gate: bool = True) -> dict[str, Any]:
        """Modul zu Projekt hinzufügen."""
        ...
    
    @abstractmethod
    async def build_service(self, typ_id: str, name: str, project: str, gate: bool = True) -> dict[str, Any]:
        """Service-Definition erstellen."""
        ...
    
    @abstractmethod
    async def register_type(self, typ_id: str, name: str, functions: list[str], manifest_ref: str, gate: bool = True) -> dict[str, Any]:
        """Neuen Factory-Typ registrieren."""
        ...
    
    @abstractmethod
    async def transition_type(self, typ_id: str, state: str, gate: bool = True) -> dict[str, Any]:
        """Factory-Typ Status wechseln."""
        ...


class EvidenceStorePort(ABC):
    """Port für Evidence Store Zugriff (HTTP/JSON)."""
    
    @abstractmethod
    async def list_runs(self, typ_id: str | None = None, limit: int = 50, success: bool | None = None) -> list[dict[str, Any]]:
        """Runs listen."""
        ...
    
    @abstractmethod
    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Run-Details laden."""
        ...
    
    @abstractmethod
    async def get_benchmarks(self, typ_id: str | None = None) -> list[dict[str, Any]]:
        """Benchmarks listen."""
        ...
    
    @abstractmethod
    async def run_benchmark(self, config: dict[str, Any]) -> dict[str, Any]:
        """Benchmark ausführen."""
        ...
    
    @abstractmethod
    async def compare_variants(self, typ_id: str, variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Varianten vergleichen."""
        ...
    
    @abstractmethod
    async def analyze(self, min_runs: int = 10, typ_id: str | None = None) -> list[dict[str, Any]]:
        """Meta-Analyse ausführen."""
        ...
    
    @abstractmethod
    async def detect_regressions(self, typ_id: str, window: int = 30, threshold: float = 20.0) -> list[dict[str, Any]]:
        """Regressionen erkennen."""
        ...
    
    @abstractmethod
    async def get_insights(self, min_confidence: float = 0.5) -> list[dict[str, Any]]:
        """Insights laden."""
        ...
    
    @abstractmethod
    async def get_report(self, min_runs: int = 10) -> dict[str, Any]:
        """Vollständigen Report laden."""
        ...


class GateClientPort(ABC):
    """Port für Captain-Gate Client (One Sedra Integration)."""
    
    @abstractmethod
    async def get_pending_gates(self) -> list[dict[str, Any]]:
        """Alle offenen Gates laden."""
        ...
    
    @abstractmethod
    async def approve_gate(self, gate_id: str) -> dict[str, Any]:
        """Gate genehmigen."""
        ...
    
    @abstractmethod
    async def reject_gate(self, gate_id: str, reason: str | None = None) -> dict[str, Any]:
        """Gate ablehnen."""
        ...
    
    @abstractmethod
    async def get_gate_status(self, gate_id: str) -> dict[str, Any] | None:
        """Gate-Status laden."""
        ...


class NotificationPort(ABC):
    """Port für Benachrichtigungen (Toast, In-App, etc.)."""
    
    @abstractmethod
    async def notify_build_complete(self, project_name: str, success: bool) -> None:
        ...
    
    @abstractmethod
    async def notify_benchmark_complete(self, typ_id: str, score: float) -> None:
        ...
    
    @abstractmethod
    async def notify_gate_pending(self, gate_id: str, gate_type: str) -> None:
        ...
    
    @abstractmethod
    async def notify_gate_decided(self, gate_id: str, decision: str) -> None:
        ...