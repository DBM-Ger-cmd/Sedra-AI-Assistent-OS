"""Native Workflow Adapter — In-Process Workflow Execution.

Parser für Native YAML/JSON, In-Process Executor mit Async/Retry/Timeout,
Validator, DryRun Simulator, Export (YAML, Mermaid).
"""

from __future__ import annotations

import asyncio
import yaml
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..adapter_base import (
    AdapterType,
    WorkflowStatus,
    ValidationSeverity,
    ValidationIssue,
    ValidationResult,
    DryRunResult,
    ExecutionResult,
    ExecutionContext,
    WorkflowStep,
    WorkflowSpec,
    WorkflowAdapter,
)

# Evidence Store Integration (optional)
try:
    from ..evidence_store import get_default_store, RunStatus
    EVIDENCE_STORE_AVAILABLE = True
except ImportError:
    EVIDENCE_STORE_AVAILABLE = False


class NativeWorkflowAdapter(WorkflowAdapter):
    """Native Workflow Adapter für In-Process Ausführung."""
    
    def __init__(self):
        super().__init__(AdapterType.NATIVE)
        self._step_executors: dict[str, callable] = {}
        self._register_builtin_executors()
    
    @property
    def supported_formats(self) -> list[str]:
        return ["yaml", "yml", "json", "native"]
    
    def _register_builtin_executors(self):
        """Registriert eingebaute Step-Executors."""
        self._step_executors = {
            "script": self._execute_script,
            "http": self._execute_http,
            "condition": self._execute_condition,
            "delay": self._execute_delay,
            "parallel": self._execute_parallel,
            "loop": self._execute_loop,
            "native_function": self._execute_native_function,
        }
    
    # =========================================================================
    # Parsing
    # =========================================================================
    
    def parse(self, source: str | dict | bytes) -> WorkflowSpec:
        """Parst Native Workflow (YAML/JSON/Dict) zu WorkflowSpec."""
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        
        if isinstance(source, str):
            # Versuche YAML zuerst, dann JSON
            try:
                data = yaml.safe_load(source)
            except yaml.YAMLError:
                try:
                    data = json.loads(source)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Ungültiges YAML/JSON: {e}")
        elif isinstance(source, dict):
            data = source
        else:
            raise ValueError(f"Nicht unterstützter Source-Typ: {type(source)}")
        
        return self._dict_to_spec(data)
    
    def _dict_to_spec(self, data: dict) -> WorkflowSpec:
        """Konvertiert Dict zu WorkflowSpec."""
        # Basis-Felder
        spec = WorkflowSpec(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            adapter_type=AdapterType.NATIVE,
            parameters=data.get("parameters", {}),
            metadata=data.get("metadata", {}),
        )
        
        # Steps parsen
        steps_data = data.get("steps", [])
        for step_data in steps_data:
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
            spec.steps.append(step)
        
        return spec
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    def validate(self, spec: WorkflowSpec) -> ValidationResult:
        """Validiert Native Workflow Spec."""
        result = ValidationResult(valid=True)
        
        # Basis-Checks
        if not spec.name:
            result.add_error("missing_name", "Workflow muss einen Namen haben")
        
        if not spec.steps:
            result.add_warning("no_steps", "Workflow hat keine Steps")
        
        # Step-Validierung
        step_ids = set()
        for i, step in enumerate(spec.steps):
            if not step.id:
                result.add_error("missing_step_id", f"Step {i} hat keine ID", path=f"steps[{i}]")
            elif step.id in step_ids:
                result.add_error("duplicate_step_id", f"Doppelte Step-ID: {step.id}", path=f"steps[{i}]")
            else:
                step_ids.add(step.id)
            
            if not step.name:
                result.add_warning("missing_step_name", f"Step {step.id} hat keinen Namen", path=f"steps[{i}]")
            
            if step.type not in self._step_executors:
                result.add_error("unknown_step_type", f"Unbekannter Step-Type: {step.type}", path=f"steps[{i}].type")
            
            # Dependencies prüfen
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    result.add_error("missing_dependency", f"Step {step.id} hängt von unbekanntem Step ab: {dep_id}", path=f"steps[{i}].depends_on")
        
        # Zirkuläre Dependencies prüfen
        if self._has_circular_dependencies(spec):
            result.add_error("circular_dependency", "Workflow enthält zirkuläre Dependencies")
        
        return result
    
    def _has_circular_dependencies(self, spec: WorkflowSpec) -> bool:
        """Prüft auf zirkuläre Dependencies (DFS)."""
        visited = set()
        rec_stack = set()
        
        def dfs(step_id: str) -> bool:
            if step_id in rec_stack:
                return True
            if step_id in visited:
                return False
            
            visited.add(step_id)
            rec_stack.add(step_id)
            
            step = spec.get_step(step_id)
            if step:
                for dep_id in step.depends_on:
                    if dfs(dep_id):
                        return True
            
            rec_stack.remove(step_id)
            return False
        
        for step in spec.steps:
            if step.id not in visited:
                if dfs(step.id):
                    return True
        return False
    
    # =========================================================================
    # Dry Run
    # =========================================================================
    
    def dry_run(self, spec: WorkflowSpec, context: ExecutionContext) -> DryRunResult:
        """Simuliert Workflow-Ausführung ohne Seiteneffekte."""
        simulated_steps = []
        total_estimated_ms = 0
        
        # Topologische Sortierung für Ausführungsreihenfolge
        execution_order = self._topological_sort(spec)
        
        for step in execution_order:
            step_sim = {
                "step_id": step.id,
                "name": step.name,
                "type": step.type,
                "estimated_duration_ms": step.timeout_ms,
                "config_preview": self._config_preview(step.config),
            }
            simulated_steps.append(step_sim)
            total_estimated_ms += step.timeout_ms
        
        return DryRunResult(
            success=True,
            simulated_steps=simulated_steps,
            estimated_duration_ms=total_estimated_ms,
            estimated_resources={
                "memory_mb": 50,
                "cpu_percent": 10,
            },
            warnings=["Dry-Run simuliert nur, keine echte Ausführung"],
        )
    
    def _topological_sort(self, spec: WorkflowSpec) -> list[WorkflowStep]:
        """Topologische Sortierung der Steps."""
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
            # Fallback: Original-Reihenfolge
            return spec.steps
        return result
    
    def _config_preview(self, config: dict) -> dict:
        """Erstellt Preview der Step-Config (ohne Secrets)."""
        preview = {}
        for k, v in config.items():
            if "secret" in k.lower() or "password" in k.lower() or "token" in k.lower():
                preview[k] = "***"
            elif isinstance(v, str) and len(v) > 100:
                preview[k] = v[:100] + "..."
            else:
                preview[k] = v
        return preview
    
    # =========================================================================
    # Execution
    # =========================================================================
    
    async def execute(self, spec: WorkflowSpec, context: ExecutionContext) -> ExecutionResult:
        """Führt Native Workflow asynchron aus."""
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
            # Pre-Execution Hook
            self.on_before_execute(spec, context)
            
            # Validierung
            validation = self.validate(spec)
            if not validation.valid:
                result.status = WorkflowStatus.FAILED
                result.error = f"Validierung fehlgeschlagen: {validation.errors}"
                # Evidence Store: Failed validation
                if store:
                    store.record_run_end(run_id, success=False, error_message=result.error)
                return result
            
            # Topologische Sortierung
            execution_order = self._topological_sort(spec)
            result.steps_total = len(execution_order)
            
            # Step-Ausführung mit Timeout
            step_results = {}
            
            async def run_steps():
                for step in execution_order:
                    # Gate-Check für Steps mit Policies
                    if step.policies and context.gate_callback:
                        result.status = WorkflowStatus.WAITING_GATE
                        for policy_id in step.policies:
                            gate_result = await context.gate_callback(policy_id, {
                                "step_id": step.id,
                                "step_name": step.name,
                                "workflow_id": spec.id,
                            })
                            if gate_result != "approved":
                                result.status = WorkflowStatus.CANCELLED
                                result.error = f"Gate rejected for step {step.id}: {gate_result}"
                                return
                    
                    # Step ausführen
                    step_start = time.time()
                    try:
                        executor = self._step_executors.get(step.type)
                        if not executor:
                            raise ValueError(f"Kein Executor für Step-Type: {step.type}")
                        
                        step_result = await executor(step, context, step_results)
                        step_results[step.id] = step_result
                        result.steps_executed += 1
                        
                        self.on_step_complete(step, step_result, context)
                        
                    except Exception as e:
                        result.status = WorkflowStatus.FAILED
                        result.error = f"Step {step.id} fehlgeschlagen: {e}"
                        return
                
                # Success
                result.status = WorkflowStatus.SUCCESS
                result.success = True
                result.output = step_results
            
            # Apply timeout if specified
            if context.timeout_ms and context.timeout_ms > 0:
                await asyncio.wait_for(run_steps(), timeout=context.timeout_ms / 1000.0)
            else:
                await run_steps()
            
        except asyncio.TimeoutError:
            result.status = WorkflowStatus.FAILED
            result.error = f"Timeout nach {context.timeout_ms}ms"
        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.error = str(e)
        
        finally:
            from datetime import datetime
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
    
    # =========================================================================
    # Built-in Step Executors
    # =========================================================================
    
    async def _execute_script(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt Python-Script aus (sandboxed)."""
        script = step.config.get("script", "")
        if not script:
            return {"output": "No script provided"}
        
        # TODO: Echte Sandbox (RestrictedPython, subprocess, etc.)
        # Für jetzt: Mock
        await asyncio.sleep(0.01)  # Simuliere Arbeit
        return {"output": f"Script executed: {step.name}", "lines": len(script.split('\n'))}
    
    async def _execute_http(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt HTTP-Request aus."""
        url = step.config.get("url", "")
        method = step.config.get("method", "GET")
        headers = step.config.get("headers", {})
        body = step.config.get("body")
        
        # TODO: Echte HTTP-Requests mit aiohttp
        await asyncio.sleep(0.05)
        return {"status": 200, "url": url, "method": method, "mock": True}
    
    async def _execute_condition(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Evaluiert Bedingung."""
        expression = step.config.get("expression", "true")
        # TODO: Echte Expression-Evaluation (sicher)
        result = expression.lower() in ("true", "1", "yes")
        return {"condition": expression, "result": result}
    
    async def _execute_delay(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Wartet angegebene Zeit."""
        delay_ms = step.config.get("delay_ms", 1000)
        await asyncio.sleep(delay_ms / 1000)
        return {"delayed_ms": delay_ms}
    
    async def _execute_parallel(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt Sub-Steps parallel aus."""
        sub_steps = step.config.get("steps", [])
        tasks = []
        for sub_step_config in sub_steps:
            sub_step = WorkflowStep(
                id=sub_step_config.get("id", ""),
                name=sub_step_config.get("name", ""),
                type=sub_step_config.get("type", "script"),
                config=sub_step_config.get("config", {}),
            )
            tasks.append(self._execute_script(sub_step, context, previous_results))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {"parallel_results": results}
    
    async def _execute_loop(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Führt Loop aus."""
        iterations = step.config.get("iterations", 1)
        sub_steps = step.config.get("steps", [])
        
        all_results = []
        for i in range(iterations):
            iteration_results = {}
            for sub_step_config in sub_steps:
                sub_step = WorkflowStep(
                    id=f"{sub_step_config.get('id', '')}_{i}",
                    name=sub_step_config.get("name", ""),
                    type=sub_step_config.get("type", "script"),
                    config=sub_step_config.get("config", {}),
                )
                result = await self._execute_script(sub_step, context, previous_results)
                iteration_results[sub_step.id] = result
            all_results.append(iteration_results)
        
        return {"loop_results": all_results}
    
    async def _execute_native_function(self, step: WorkflowStep, context: ExecutionContext, previous_results: dict) -> Any:
        """Ruft registrierte Native Function auf."""
        func_name = step.config.get("function", "")
        args = step.config.get("args", [])
        kwargs = step.config.get("kwargs", {})
        
        # TODO: Registry für Native Functions
        return {"function": func_name, "called": True, "mock": True}
    
    # =========================================================================
    # Export
    # =========================================================================
    
    def export(self, spec: WorkflowSpec, format: str) -> str:
        """Exportiert Spec in verschiedenen Formaten."""
        format = format.lower()
        
        if format in ("yaml", "yml"):
            return self._export_yaml(spec)
        elif format == "json":
            return self._export_json(spec)
        elif format == "mermaid":
            return self._export_mermaid(spec)
        else:
            raise ValueError(f"Nicht unterstütztes Export-Format: {format}")
    
    def _export_yaml(self, spec: WorkflowSpec) -> str:
        data = {
            "id": spec.id,
            "name": spec.name,
            "version": spec.version,
            "description": spec.description,
            "parameters": spec.parameters,
            "metadata": spec.metadata,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "config": s.config,
                    "depends_on": s.depends_on,
                    "timeout_ms": s.timeout_ms,
                    "retry_policy": s.retry_policy,
                    "policies": s.policies,
                }
                for s in spec.steps
            ],
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    def _export_json(self, spec: WorkflowSpec) -> str:
        data = {
            "id": spec.id,
            "name": spec.name,
            "version": spec.version,
            "description": spec.description,
            "parameters": spec.parameters,
            "metadata": spec.metadata,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "config": s.config,
                    "depends_on": s.depends_on,
                    "timeout_ms": s.timeout_ms,
                    "retry_policy": s.retry_policy,
                    "policies": s.policies,
                }
                for s in spec.steps
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def _export_mermaid(self, spec: WorkflowSpec) -> str:
        lines = ["```mermaid", "flowchart TD"]
        
        for step in spec.steps:
            node_id = step.id.replace("-", "_")
            label = f"{step.name}\\n({step.type})"
            lines.append(f'    {node_id}["{label}"]')
        
        for step in spec.steps:
            node_id = step.id.replace("-", "_")
            for dep_id in step.depends_on:
                dep_node = dep_id.replace("-", "_")
                lines.append(f"    {dep_node} --> {node_id}")
        
        lines.append("```")
        return "\n".join(lines)