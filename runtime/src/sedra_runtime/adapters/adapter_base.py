"""Adapter Base Classes — Universal Factory Workflow Adapter Framework.

Basis-Klassen und Interfaces für alle Workflow-Adapter (Native, n8n, Hybrid).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


# =============================================================================
# Enums & Constants
# =============================================================================

class AdapterType(str, Enum):
    """Workflow-Adapter Typen."""
    NATIVE = "native"
    N8N = "n8n"
    HYBRID = "hybrid"


class WorkflowStatus(str, Enum):
    """Workflow-Ausführungsstatus."""
    PENDING = "pending"
    VALIDATING = "validating"
    DRY_RUNNING = "dry_running"
    WAITING_GATE = "waiting_gate"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationSeverity(str, Enum):
    """Validierungs-Schweregrad."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class GateDecision(str, Enum):
    """Captain-Gate Entscheidung."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ValidationIssue:
    """Einzelnes Validierungs-Problem."""
    severity: ValidationSeverity
    code: str
    message: str
    path: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Ergebnis einer Validierung."""
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    
    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]
    
    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]
    
    def add_error(self, code: str, message: str, path: str = "", **details):
        self.issues.append(ValidationIssue(ValidationSeverity.ERROR, code, message, path, details))
        self.valid = False
    
    def add_warning(self, code: str, message: str, path: str = "", **details):
        self.issues.append(ValidationIssue(ValidationSeverity.WARNING, code, message, path, details))
    
    def add_info(self, code: str, message: str, path: str = "", **details):
        self.issues.append(ValidationIssue(ValidationSeverity.INFO, code, message, path, details))


@dataclass
class DryRunResult:
    """Ergebnis eines Dry-Runs."""
    success: bool
    simulated_steps: list[dict[str, Any]] = field(default_factory=list)
    estimated_duration_ms: int = 0
    estimated_resources: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Ergebnis einer Workflow-Ausführung."""
    execution_id: str = field(default_factory=lambda: str(uuid4())[:8])
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    steps_executed: int = 0
    steps_total: int = 0
    gate_decisions: dict[str, GateDecision] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        return self.finished_at is not None


@dataclass
class ExecutionContext:
    """Kontext für Workflow-Ausführung."""
    workflow_id: str
    adapter_type: AdapterType
    parameters: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)  # Nur Referenzen, keine Werte!
    gate_callback: Optional[callable] = None  # Für Captain-Gate Integration
    audit_logger: Optional[callable] = None   # Für Audit Logging
    dry_run: bool = False
    timeout_ms: int = 300000  # 5 Minuten Default
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Workflow Specification
# =============================================================================

@dataclass
class WorkflowStep:
    """Einzelner Workflow-Schritt."""
    id: str
    name: str
    type: str  # "native", "n8n", "script", "http", "condition", "loop"
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)  # Step IDs
    timeout_ms: int = 30000
    retry_policy: dict[str, Any] = field(default_factory=dict)
    policies: list[str] = field(default_factory=list)  # Policy IDs für Captain-Gates


@dataclass
class WorkflowSpec:
    """Workflow-Spezifikation (adapter-unabhängig)."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    adapter_type: AdapterType = AdapterType.NATIVE
    steps: list[WorkflowStep] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)  # Input Parameter Schema
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_dependencies(self, step_id: str) -> list[WorkflowStep]:
        step = self.get_step(step_id)
        if not step:
            return []
        return [self.get_step(dep_id) for dep_id in step.depends_on if self.get_step(dep_id)]


# =============================================================================
# Adapter Interface
# =============================================================================

class WorkflowAdapter(ABC):
    """Abstract Base Class für alle Workflow-Adapter."""
    
    def __init__(self, adapter_type: AdapterType):
        self.adapter_type = adapter_type
    
    @property
    def name(self) -> str:
        """Anzeigename des Adapters."""
        return self.adapter_type.value.capitalize()
    
    @property
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Unterstützte Import/Export Formate (z.B. ['yaml', 'json', 'n8n.json'])."""
        ...
    
    @abstractmethod
    def parse(self, source: str | dict | bytes) -> WorkflowSpec:
        """Source (JSON/YAML/File/Bytes) → Internal WorkflowSpec."""
        ...
    
    @abstractmethod
    def validate(self, spec: WorkflowSpec) -> ValidationResult:
        """Validiert Spec gegen Schema + Policies."""
        ...
    
    @abstractmethod
    def dry_run(self, spec: WorkflowSpec, context: ExecutionContext) -> DryRunResult:
        """Simuliert Ausführung ohne Seiteneffekte."""
        ...
    
    @abstractmethod
    async def execute(self, spec: WorkflowSpec, context: ExecutionContext) -> ExecutionResult:
        """Führt Workflow kontrolliert aus (mit Captain-Gates)."""
        ...
    
    @abstractmethod
    def export(self, spec: WorkflowSpec, format: str) -> str:
        """Spec → Target Format (yaml, json, n8n.json, mermaid, etc.)."""
        ...
    
    # Optional: Lifecycle Hooks
    def on_before_execute(self, spec: WorkflowSpec, context: ExecutionContext) -> None:
        """Hook vor Ausführung."""
        pass
    
    def on_after_execute(self, result: ExecutionResult, context: ExecutionContext) -> None:
        """Hook nach Ausführung."""
        pass
    
    def on_step_complete(self, step: WorkflowStep, result: Any, context: ExecutionContext) -> None:
        """Hook nach jedem Schritt."""
        pass


# =============================================================================
# Adapter Registry
# =============================================================================

class AdapterRegistry:
    """Registry für verfügbare Workflow-Adapter."""
    
    def __init__(self):
        self._adapters: dict[AdapterType, WorkflowAdapter] = {}
        self._aliases: dict[str, AdapterType] = {}
    
    def register(self, adapter: WorkflowAdapter) -> None:
        """Registriert einen Adapter."""
        self._adapters[adapter.adapter_type] = adapter
        # Aliases für Formate
        for fmt in adapter.supported_formats:
            self._aliases[fmt.lower()] = adapter.adapter_type
    
    def get(self, adapter_type: AdapterType) -> Optional[WorkflowAdapter]:
        return self._adapters.get(adapter_type)
    
    def get_by_format(self, format: str) -> Optional[WorkflowAdapter]:
        adapter_type = self._aliases.get(format.lower())
        if adapter_type:
            return self._adapters.get(adapter_type)
        return None
    
    def list_adapters(self) -> list[AdapterType]:
        return list(self._adapters.keys())
    
    def parse_auto(self, source: str | dict | bytes, format_hint: str = "") -> WorkflowSpec:
        """Automatische Format-Erkennung und Parsing."""
        if format_hint:
            adapter = self.get_by_format(format_hint)
            if adapter:
                return adapter.parse(source)
        
        # Heuristik: n8n JSON hat "nodes" und "connections"
        if isinstance(source, dict) and "nodes" in source and "connections" in source:
            adapter = self.get(AdapterType.N8N)
            if adapter:
                return adapter.parse(source)
        
        # Default: Native
        adapter = self.get(AdapterType.NATIVE)
        if adapter:
            return adapter.parse(source)
        
        raise ValueError("Kein passender Adapter gefunden")


# =============================================================================
# Factory Functions
# =============================================================================

def create_adapter_registry() -> AdapterRegistry:
    """Erstellt Standard-Adapter-Registry (Lazy-Loading der konkreten Adapter)."""
    registry = AdapterRegistry()
    # Konkrete Adapter werden bei Bedarf geladen (Lazy Import)
    return registry


def get_adapter_registry() -> AdapterRegistry:
    """Singleton für Adapter-Registry."""
    if not hasattr(get_adapter_registry, "_instance"):
        get_adapter_registry._instance = create_adapter_registry()
    return get_adapter_registry._instance