"""Hybrid Workflow Adapter — Kombiniert Native + n8n Nodes.

Orchestrator für gemischte Workflows mit Native und n8n Nodes.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Optional

from ..adapter_base import (
    AdapterType,
    WorkflowStatus,
    ValidationSeverity,
    ValidationResult,
    DryRunResult,
    ExecutionResult,
    ExecutionContext,
    WorkflowStep,
    WorkflowSpec,
    WorkflowAdapter,
)

from ..native.native_adapter import NativeWorkflowAdapter
from ..n8n.n8n_adapter import N8nWorkflowAdapter

# Evidence Store Integration (optional)
try:
    from ..evidence_store import get_default_store, RunStatus
    EVIDENCE_STORE_AVAILABLE = True
except ImportError:
    EVIDENCE_STORE_AVAILABLE = False


class HybridWorkflowAdapter(WorkflowAdapter):
    """Hybrid Workflow Adapter — kombiniert Native + n8n Nodes."""
    
    def __init__(self, n8n_cli_path: str = "n8n", n8n_api_url: str = "http://localhost:5678"):
        super().__init__(AdapterType.HYBRID)
        self.native_adapter = NativeWorkflowAdapter()
        self.n8n_adapter = N8nWorkflowAdapter()
    
    @property
    def supported_formats(self) -> list[str]:
        return ["hybrid.json", "yaml", "yml", "json"]
    
    # =========================================================================
    # Parsing
    # =========================================================================
    
    def parse(self, source: str | dict | bytes) -> WorkflowSpec:
        """Parst Hybrid Workflow (kann Native + n8n Nodes enthalten)."""
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        
        if isinstance(source, str):
            # Versuche JSON first (Hybrid Format), dann Native
            try:
                data = json.loads(source)
                # Check if hybrid format (has adapter_type field per step)
                if isinstance(data, dict) and "steps" in data:
                    for step in data.get("steps", []):
                        if "adapter_type" in step:
                            return self._dict_to_spec(data)
                # Fallback: Native
                return self.native_adapter.parse(source)
            except json.JSONDecodeError:
                return self.native_adapter.parse(source)
        elif isinstance(source, dict):
            return self._dict_to_spec(source)
        else:
            return self.native_adapter.parse(source)
    
    def _dict_to_spec(self, data: dict) -> WorkflowSpec:
        """Konvertiert Hybrid Dict zu WorkflowSpec."""
        spec = WorkflowSpec(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            adapter_type=AdapterType.HYBRID,
            parameters=data.get("parameters", {}),
            metadata=data.get("metadata", {}),
        )
        
        for step_data in data.get("steps", []):
            step = WorkflowStep(
                id=step_data.get("id", ""),
                name=step_data.get("name", ""),
                type=step_data.get("type", "script"),
                config=step_data.get("config", {}),
                depends_on=step_data.get("depends_on", []),
                timeout_ms=step_data.get("timeout_ms", 30000),
                retry_policy=step_data.get("retry_policy", {}),
                policies=step_data.get("policies", []),
            )
            # Adapter-Type pro Step speichern
            step.config["adapter_type"] = step_data.get("adapter_type", "native")
            spec.steps.append(step)
        
        return spec
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    def validate(self, spec: WorkflowSpec) -> ValidationResult:
        """Validiert Hybrid Workflow (delegiert an jeweilige Adapter)."""
        result = ValidationResult(valid=True)
        
        # Basis-Validierung
        if not spec.name:
            result.add_error("missing_name", "Workflow muss einen Namen haben")
        
        if not spec.steps:
            result.add_warning("no_steps", "Workflow hat keine Steps")
        
        # Pro Step validieren
        for step in spec.steps:
            adapter_type = step.config.get("adapter_type", "native")
            
            if adapter_type == "native":
                native_result = self.native_adapter.validate(WorkflowSpec(steps=[step]))
                for issue in native_result.issues:
                    result.issues.append(issue)
            elif adapter_type == "n8n":
                n8n_result = self.n8n_adapter.validate(WorkflowSpec(steps=[step]))
                for issue in n8n_result.issues:
                    result.issues.append(issue)
            elif adapter_type == "hybrid":
                # Hybrid Step = Orchestrator
                pass
            else:
                result.add_error("unknown_adapter_type", f"Unbekannter Adapter-Type: {adapter_type}", path=f"steps[{step.id}]")
        
        # Zirkuläre Dependencies prüfen (über alle Steps)
        if self._has_circular_dependencies(spec):
            result.add_error("circular_dependency", "Workflow enthält zirkuläre Dependencies")
        
        return result
    
    def _has_circular_dependencies(self, spec: WorkflowSpec) -> bool:
        """Prüft auf zirkuläre Dependencies (DFS) - delegiert an native_adapter."""
        return self.native_adapter._has_circular_dependencies(spec)
    
    # =========================================================================
    # Dry Run
    # =========================================================================
    
    def dry_run(self, spec: WorkflowSpec, context: ExecutionContext) -> DryRunResult:
        """Kombiniert Dry-Runs beider Adapter."""
        native_steps = [s for s in spec.steps if s.config.get("adapter_type", "native") == "native"]
        n8n_steps = [s for s in spec.steps if s.config.get("adapter_type") == "n8n"]
        
        native_spec = WorkflowSpec(steps=native_steps)
        n8n_spec = WorkflowSpec(steps=n8n_steps)
        
        native_dry = self.native_adapter.dry_run(native_spec, context)
        n8n_dry = self.n8n_adapter.dry_run(n8n_spec, context)
        
        return DryRunResult(
            success=native_dry.success and n8n_dry.success,
            simulated_steps=native_dry.simulated_steps + n8n_dry.simulated_steps,
            estimated_duration_ms=native_dry.estimated_duration_ms + n8n_dry.estimated_duration_ms,
            estimated_resources={
                "memory_mb": native_dry.estimated_resources.get("memory_mb", 0) + n8n_dry.estimated_resources.get("memory_mb", 0),
            },
            warnings=native_dry.warnings + n8n_dry.warnings,
            errors=native_dry.errors + n8n_dry.errors,
        )
    
    # =========================================================================
    # Execution
    # =========================================================================
    
    async def execute(self, spec: WorkflowSpec, context: ExecutionContext) -> ExecutionResult:
        """Führt Hybrid Workflow aus (Orchestrator)."""
        from datetime import datetime
        
        # Evidence Store: Run starten
        run_id = str(uuid.uuid4())
        store = None
        if EVIDENCE_STORE_AVAILABLE and not context.dry_run:
            try:
                store = get_default_store()
                store.record_run_start(
                    run_id=run_id,
                    typ_id=f"adapter-{self.adapter_type.value}",
                    name=spec.name or spec.id,
                    build_type="adapter_execution",
                    params=context.parameters,
                )
            except Exception:
                store = None  # Silent fail for evidence store
        
        result = ExecutionResult(
            workflow_id=spec.id,
            status=WorkflowStatus.RUNNING,
        )
        
        try:
            self.on_before_execute(spec, context)
            
            validation = self.validate(spec)
            if not validation.valid:
                result.status = WorkflowStatus.FAILED
                result.error = f"Validierung fehlgeschlagen: {validation.errors}"
                # Evidence Store: Failed validation
                if store:
                    store.record_run_end(run_id, success=False, error_message=result.error)
                return result
            
            result.status = WorkflowStatus.RUNNING
            result.steps_total = len(spec.steps)
            
            # Topologische Sortierung
            execution_order = self._topological_sort(spec)
            result.steps_total = len(execution_order)
            
            step_results = {}
            
            for step in execution_order:
                adapter_type = step.config.get("adapter_type", "native")
                
                # Gate-Check
                if step.policies and context.gate_callback:
                    result.status = WorkflowStatus.WAITING_GATE
                    for policy_id in step.policies:
                        gate_result = await context.gate_callback(policy_id, {
                            "step_id": step.id,
                            "step_name": step.name,
                            "workflow_id": spec.id,
                            "adapter_type": adapter_type,
                        })
                        if gate_result != "approved":
                            result.status = WorkflowStatus.CANCELLED
                            result.error = f"Gate rejected for step {step.id}: {gate_result}"
                            return result
                
                # Step mit passendem Adapter ausführen
                step_result = await self._execute_step_by_adapter(step, context, step_results)
                step_results[step.id] = step_result
                result.steps_executed += 1
                
                self.on_step_complete(step, step_result, context)
            
            result.status = WorkflowStatus.SUCCESS
            result.success = True
            result.output = step_results
            
        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.error = str(e)
        
        finally:
            result.finished_at = datetime.now()
            if result.started_at:
                result.duration_ms = int((result.finished_at - result.started_at).total_seconds() * 1000)
            self.on_after_execute(result, context)
            
            # Evidence Store: Run beenden
            if store:
                try:
                    store.record_run_end(
                        run_id=run_id,
                        success=result.success,
                        error_message=result.error,
                        artifacts=[{"step_id": k, "result": str(v)} for k, v in result.output.items()] if result.output else [],
                        metrics={
                            "steps_total": result.steps_total,
                            "steps_executed": result.steps_executed,
                            "duration_ms": result.duration_ms,
                            "adapter_type": self.adapter_type.value,
                        }
                    )
                except Exception:
                    pass  # Silent fail for evidence store
        
        return result
    
    def _topological_sort(self, spec: WorkflowSpec) -> list[WorkflowStep]:
        """Topologische Sortierung (wie Native)."""
        in_degree = {step.id: 0 for step in spec.steps}
        adj = {step.id: [] for step in spec.steps}
        
        for step in spec.steps:
            for dep_id in step.depends_on:
                adj[dep_id].append(step.id)
                in_degree[step.id] += 1
        
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        result = []
        
        while queue:
            current_id = queue.pop(0)
            step = spec.get_step(current_id)
            if step:
                result.append(step)
            for neighbor in adj[current_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(spec.steps):
            return spec.steps
        return result
    
    async def _execute_step_by_adapter(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt Step mit passendem Adapter aus."""
        adapter_type = step.config.get("adapter_type", "native")
        
        if adapter_type == "native":
            return await self.native_adapter._execute_script(step, context, previous_results)
        elif adapter_type == "n8n":
            # Für einzelne n8n Nodes: Sub-Workflow erstellen und ausführen
            return await self._execute_n8n_step(step, context, previous_results)
        else:
            # Hybrid/Orchestrator Step
            return await self._execute_hybrid_step(step, context, previous_results)
    
    async def _execute_n8n_step(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt einzelnen n8n Node aus (via Sub-Workflow)."""
        # Erstelle temporären n8n Workflow für einzelnen Node
        sub_spec = WorkflowSpec(
            name=f"{step.name}_sub",
            adapter_type=AdapterType.N8N,
            steps=[step],
        )
        
        sub_context = ExecutionContext(
            workflow_id=f"{context.workflow_id}_{step.id}",
            adapter_type=AdapterType.N8N,
            parameters=context.parameters,
            environment=context.environment,
            gate_callback=context.gate_callback,
            audit_logger=context.audit_logger,
            dry_run=context.dry_run,
        )
        
        result = await self.n8n_adapter.execute(sub_spec, sub_context)
        return result.output
    
    async def _execute_hybrid_step(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt Hybrid Orchestrator Step aus."""
        # Orchestrator-Logik: z.B. Datentransformation zwischen Native/n8n
        await asyncio.sleep(0.01)
        return {"orchestrator": step.name, "status": "completed"}
    
    # =========================================================================
    # Export
    # =========================================================================
    
    def export(self, spec: WorkflowSpec, format: str) -> str:
        """Exportiert Hybrid Spec."""
        format = format.lower()
        
        if format in ("hybrid.json", "json"):
            return self._export_json(spec)
        elif format in ("yaml", "yml"):
            import yaml
            return yaml.dump(self._spec_to_dict(spec), default_flow_style=False, allow_unicode=True)
        else:
            # Delegate to appropriate adapter
            return self.native_adapter.export(spec, format)
    
    def _spec_to_dict(self, spec: WorkflowSpec) -> dict:
        return {
            "id": spec.id,
            "name": spec.name,
            "version": spec.version,
            "description": spec.description,
            "adapter_type": "hybrid",
            "parameters": spec.parameters,
            "metadata": spec.metadata,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "adapter_type": s.config.get("adapter_type", "native"),
                    "config": s.config,
                    "depends_on": s.depends_on,
                    "timeout_ms": s.timeout_ms,
                    "retry_policy": s.retry_policy,
                    "policies": s.policies,
                }
                for s in spec.steps
            ],
        }
    
    def _export_json(self, spec: WorkflowSpec) -> str:
        import json
        return json.dumps(self._spec_to_dict(spec), indent=2, ensure_ascii=False)