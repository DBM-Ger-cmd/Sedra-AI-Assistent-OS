"""SEDRA Workflow Adapters Package."""

from __future__ import annotations

from .adapter_base import (
    AdapterType,
    WorkflowStatus,
    ValidationSeverity,
    GateDecision,
    ValidationIssue,
    ValidationResult,
    DryRunResult,
    ExecutionResult,
    ExecutionContext,
    WorkflowStep,
    WorkflowSpec,
    WorkflowAdapter,
    AdapterRegistry,
    create_adapter_registry,
    get_adapter_registry,
)

__all__ = [
    "AdapterType",
    "WorkflowStatus",
    "ValidationSeverity",
    "GateDecision",
    "ValidationIssue",
    "ValidationResult",
    "DryRunResult",
    "ExecutionResult",
    "ExecutionContext",
    "WorkflowStep",
    "WorkflowSpec",
    "WorkflowAdapter",
    "AdapterRegistry",
    "create_adapter_registry",
    "get_adapter_registry",
]

# Lazy-Loading für konkrete Adapter
def get_native_adapter():
    from .native.native_adapter import NativeWorkflowAdapter
    return NativeWorkflowAdapter()

def get_n8n_adapter():
    from .n8n.n8n_adapter import N8nWorkflowAdapter
    return N8nWorkflowAdapter()

def get_hybrid_adapter():
    from .hybrid.hybrid_adapter import HybridWorkflowAdapter
    return HybridWorkflowAdapter()