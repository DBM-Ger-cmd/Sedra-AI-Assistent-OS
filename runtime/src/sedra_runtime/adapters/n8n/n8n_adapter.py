"""n8n Workflow Adapter — n8n Workflow Import/Export/Execution.

Parser für n8n Workflow JSON, Executor via n8n CLI/API,
Validator mit n8n Schema, DryRun via n8n --dry-run.
"""

from __future__ import annotations

import json
import subprocess
import asyncio
import tempfile
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import aiohttp

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

# Policy Integration (MOD-02)
from ...policy import PolicyRegistry, PolicyEvaluator, PolicyContext, create_evaluator, PolicyDecision

# Evidence Store Integration (optional)
try:
    from ..evidence_store import get_default_store, RunStatus
    EVIDENCE_STORE_AVAILABLE = True
except ImportError:
    EVIDENCE_STORE_AVAILABLE = False


class N8nWorkflowAdapter(WorkflowAdapter):
    """n8n Workflow Adapter für n8n Workflow JSON."""

    def __init__(
        self,
        n8n_cli_path: str = "n8n",
        n8n_api_url: str = "http://localhost:5678",
        n8n_api_key: Optional[str] = None,
        policy_registry: Optional["PolicyRegistry"] = None,
        gate_callback: Optional[callable] = None,
    ):
        super().__init__(AdapterType.N8N)
        self.n8n_cli_path = n8n_cli_path
        self.n8n_api_url = n8n_api_url.rstrip("/")
        self.n8n_api_key = n8n_api_key
        self._n8n_available = self._check_n8n_availability()

        # Policy Integration (MOD-02)
        from ...policy import PolicyRegistry, create_evaluator
        self.policy_registry = policy_registry or PolicyRegistry()
        self.policy_evaluator = create_evaluator(self.policy_registry, gate_callback)

        # API Client
        self._api_client: Optional["N8nApiClient"] = None

    @property
    def api_client(self) -> "N8nApiClient":
        """Lazy-initialized API Client."""
        if self._api_client is None:
            self._api_client = N8nApiClient(self.n8n_api_url, self.n8n_api_key)
        return self._api_client

    @property
    def supported_formats(self) -> list[str]:
        return ["n8n.json", "json"]

    def _check_n8n_availability(self) -> bool:
        """Prüft ob n8n CLI/API verfügbar ist."""
        try:
            result = subprocess.run(
                [self.n8n_cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    # =========================================================================
    # Parsing
    # =========================================================================

    def parse(self, source: str | dict | bytes) -> WorkflowSpec:
        """Parst n8n Workflow JSON zu WorkflowSpec."""
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        if isinstance(source, str):
            try:
                data = json.loads(source)
            except json.JSONDecodeError as e:
                raise ValueError(f"Ungültiges JSON: {e}")
        elif isinstance(source, dict):
            data = source
        else:
            raise ValueError(f"Nicht unterstützter Source-Typ: {type(source)}")

        return self._n8n_to_spec(data)

    def _n8n_to_spec(self, data: dict) -> WorkflowSpec:
        """Konvertiert n8n Workflow JSON zu WorkflowSpec."""
        # n8n Workflow Structure:
        # {
        #   "name": "Workflow Name",
        #   "nodes": [...],
        #   "connections": {...},
        #   "active": false,
        #   "settings": {},
        #   "id": "1"
        # }

        spec = WorkflowSpec(
            id=data.get("id", ""),
            name=data.get("name", "n8n Workflow"),
            version="1.0.0",
            description=data.get("description", ""),
            adapter_type=AdapterType.N8N,
            metadata={
                "n8n_original": data,
                "active": data.get("active", False),
                "settings": data.get("settings", {}),
            },
        )

        # Nodes zu Steps konvertieren
        nodes = data.get("nodes", [])
        connections = data.get("connections", {})

        node_map = {}
        for node in nodes:
            step = WorkflowStep(
                id=node.get("id", ""),
                name=node.get("name", node.get("type", "Unknown")),
                type="n8n_node",
                config={
                    "n8n_type": node.get("type", ""),
                    "position": node.get("position", [0, 0]),
                    "parameters": node.get("parameters", {}),
                    "credentials": node.get("credentials", {}),
                    "disabled": node.get("disabled", False),
                },
            )
            spec.steps.append(step)
            node_map[node.get("id")] = step.id

        # Connections zu Dependencies auflösen
        for source_node, connections in connections.items():
            if source_node not in node_map:
                continue
            source_step_id = node_map[source_node]

            for conn_type, targets in connections.items():
                for target_group in targets:
                    for target in target_group:
                        target_node = target.get("node")
                        if target_node in node_map:
                            target_step_id = node_map[target_node]
                            # Dependency: target hängt von source ab
                            target_step = spec.get_step(target_step_id)
                            if target_step and source_step_id not in target_step.depends_on:
                                target_step.depends_on.append(source_step_id)

        return spec

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self, spec: WorkflowSpec) -> ValidationResult:
        """Validiert n8n Workflow Spec."""
        result = ValidationResult(valid=True)

        if not spec.name:
            result.add_error("missing_name", "n8n Workflow muss einen Namen haben")

        if not spec.steps:
            result.add_warning("no_steps", "Workflow hat keine Nodes")

        # n8n-spezifische Checks
        n8n_steps = [s for s in spec.steps if s.type == "n8n_node"]
        for step in n8n_steps:
            n8n_type = step.config.get("n8n_type", "")
            if not n8n_type:
                result.add_warning("missing_n8n_type", f"Node {step.id} hat keinen n8n Type", path=f"steps[{step.id}]")

            # Credentials prüfen (nur Referenzen, keine Werte!)
            creds = step.config.get("credentials", {})
            for cred_name, cred_ref in creds.items():
                if isinstance(cred_ref, dict) and "id" not in cred_ref:
                    result.add_warning("incomplete_credential", f"Credential {cred_name} unvollständig", path=f"steps[{step.id}].credentials")

        return result

    # =========================================================================
    # Dry Run
    # =========================================================================

    def dry_run(self, spec: WorkflowSpec, context: ExecutionContext) -> DryRunResult:
        """Simuliert n8n Workflow-Ausführung (via n8n --dry-run oder Simulation)."""
        simulated_steps = []
        total_estimated_ms = 0

        for step in spec.steps:
            if step.type != "n8n_node":
                continue

            n8n_type = step.config.get("n8n_type", "unknown")
            estimated_ms = self._estimate_n8n_node_duration(step.config)

            simulated_steps.append({
                "step_id": step.id,
                "name": step.name,
                "n8n_type": n8n_type,
                "estimated_duration_ms": estimated_ms,
            })
            total_estimated_ms += estimated_ms

        return DryRunResult(
            success=True,
            simulated_steps=simulated_steps,
            estimated_duration_ms=total_estimated_ms,
            estimated_resources={
                "memory_mb": 100,
                "n8n_processes": 1,
            },
            warnings=[
                "Dry-Run nutzt n8n --dry-run falls verfügbar",
                "Keine echten Credentials verwendet",
            ],
        )

    def _estimate_n8n_node_duration(self, config: dict) -> int:
        """Schätzt Dauer eines n8n Nodes basierend auf Type."""
        n8n_type = config.get("n8n_type", "").lower()

        # Grobe Schätzungen
        if "http" in n8n_type or "webhook" in n8n_type:
            return 2000
        elif "database" in n8n_type or "sql" in n8n_type:
            return 1500
        elif "transform" in n8n_type or "function" in n8n_type:
            return 500
        elif "if" in n8n_type or "switch" in n8n_type:
            return 100
        return 500

    def _resolve_credentials(self, step: WorkflowSpec, context: ExecutionContext) -> dict:
        """Löst Credential Referenzen zu echten Werten auf (MOD-02).

        In n8n sind Credentials nur Referenzen (id/name).
        Hier würde die Integration mit n8n Credentials Store erfolgen.
        """
        creds = step.config.get("credentials", {})
        resolved = {}
        for cred_name, cred_ref in creds.items():
            if isinstance(cred_ref, dict) and "id" in cred_ref:
                # TODO: Echte Resolution via n8n API oder Credentials Store
                # Für jetzt: Mock Resolution
                resolved[cred_name] = {
                    "resolved": True,
                    "cred_id": cred_ref["id"],
                    "cred_name": cred_ref.get("name", cred_name),
                    "mock_values": {"api_key": "mock-key", "username": "mock-user"},
                }
            else:
                resolved[cred_name] = {"resolved": False, "original": cred_ref}
        return resolved

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute(self, spec: WorkflowSpec, context: ExecutionContext) -> ExecutionResult:
        """Führt n8n Workflow aus (via n8n CLI oder REST API)."""
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
                if store:
                    store.record_run_end(run_id, success=False, error_message=result.error)
                return result

            if not self._n8n_available and not (self.n8n_api_key and self.n8n_api_url):
                result.status = WorkflowStatus.FAILED
                result.error = "n8n CLI nicht verfügbar und keine API konfiguriert."
                if store:
                    store.record_run_end(run_id, success=False, error_message=result.error)
                return result

            # ===== POLICY EVALUATION (MOD-02) =====
            policy_decisions = []
            for step in spec.steps:
                if step.policies:
                    resolved_creds = self._resolve_credentials(step, context)

                    policy_context = PolicyContext(
                        workflow_id=spec.id,
                        step_id=step.id,
                        step_name=step.name,
                        adapter_type=self.adapter_type.value,
                        parameters=context.parameters,
                        user_roles=context.parameters.get("user_roles", []),
                        environment=context.parameters.get("environment", "development"),
                        metadata={
                            "step_type": step.type,
                            "n8n_type": step.config.get("n8n_type", ""),
                            "resolved_credentials": resolved_creds,
                            "timeout_ms": step.timeout_ms,
                        },
                    )

                    for policy_id in step.policies:
                        policy_result = self.policy_evaluator.evaluate(policy_id, policy_context)
                        policy_decisions.append({
                            "step_id": step.id,
                            "step_name": step.name,
                            "policy_id": policy_id,
                            "decision": policy_result.decision.value,
                            "reason": policy_result.reason,
                            "evaluator": policy_result.evaluator,
                            "timestamp": policy_result.timestamp,
                        })

                        if store:
                            try:
                                store.record_run_end(
                                    run_id=f"{run_id}-policy-{policy_id}",
                                    success=(policy_result.decision == PolicyDecision.APPROVED),
                                    error_message=policy_result.reason if policy_result.decision != PolicyDecision.APPROVED else None,
                                    artifacts=[{"policy_decision": policy_result.evidence_data}],
                                    metrics={
                                        "policy_id": policy_id,
                                        "step_id": step.id,
                                        "decision": policy_result.decision.value,
                                        "evaluator": policy_result.evaluator,
                                    }
                                )
                            except Exception:
                                pass

                        if policy_result.decision != PolicyDecision.APPROVED:
                            result.status = WorkflowStatus.CANCELLED
                            result.success = False
                            result.error = f"Policy '{policy_id}' für Step '{step.id}' nicht genehmigt: {policy_result.reason}"
                            if store:
                                store.record_run_end(
                                    run_id=run_id,
                                    success=False,
                                    error_message=result.error,
                                    metrics={
                                        "policy_decisions": policy_decisions,
                                        "cancelled_at_step": step.id,
                                        "cancelled_reason": "policy_rejected",
                                    }
                                )
                            return result

            result.status = WorkflowStatus.RUNNING
            result.steps_total = len(spec.steps)

            # Determine execution mode: API or CLI
            use_api = (
                context.parameters.get("use_api", False)
                and self.n8n_api_key
                and self.n8n_api_url
            )

            if use_api:
                return await self._execute_via_api(spec, context, store, run_id, result)
            else:
                return await self._execute_via_cli(spec, context, store, run_id, result)

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

            if store:
                try:
                    store.record_run_end(
                        run_id=run_id,
                        success=result.success,
                        error_message=result.error,
                        artifacts=[{"output": result.output}] if result.output else [],
                        metrics={
                            "steps_total": result.steps_total,
                            "steps_executed": result.steps_executed,
                            "duration_ms": result.duration_ms,
                            "adapter_type": self.adapter_type.value,
                            "n8n_available": self._n8n_available,
                        }
                    )
                except Exception:
                    pass

        return result

    async def _execute_via_cli(
        self,
        spec: WorkflowSpec,
        context: ExecutionContext,
        store,
        run_id: str,
        result: ExecutionResult
    ) -> ExecutionResult:
        """Führt Workflow via n8n CLI aus."""

        workflow_json = self._spec_to_n8n_json(spec)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(workflow_json, f, indent=2)
            workflow_file = f.name

        try:
            cmd = [self.n8n_cli_path, "execute", "--workflow", workflow_file]
            if context.dry_run:
                cmd.append("--dry-run")

            result.status = WorkflowStatus.RUNNING

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=context.timeout_ms / 1000
            )

            if process.returncode == 0:
                result.status = WorkflowStatus.SUCCESS
                result.success = True
                result.output = {"stdout": stdout.decode(), "stderr": stderr.decode()}
            else:
                result.status = WorkflowStatus.FAILED
                result.error = f"n8n execution failed: {stderr.decode()}"

        finally:
            try:
                os.unlink(workflow_file)
            except Exception:
                pass

        return result

    async def _execute_via_api(
        self,
        spec: WorkflowSpec,
        context: ExecutionContext,
        store,
        run_id: str,
        result: ExecutionResult
    ) -> ExecutionResult:
        """Führt Workflow via n8n REST API aus."""

        try:
            # 1. Workflow erstellen/updaten via API
            workflow_json = self._spec_to_n8n_json(spec)

            # Check if workflow already exists (by name)
            workflows = await self.api_client.get_workflows()
            existing = next((w for w in workflows if w.get("name") == spec.name), None)

            if existing:
                workflow_id = existing["id"]
                await self.api_client.update_workflow(workflow_id, workflow_json)
            else:
                created = await self.api_client.create_workflow(workflow_json)
                workflow_id = created["id"]

            # Execute via API
            result.status = WorkflowStatus.RUNNING

            input_data = context.parameters.get("input_data", {})

            execution = await self.api_client.execute_workflow(
                workflow_id=workflow_id,
                data=input_data,
                wait=True,
                timeout_seconds=context.timeout_ms // 1000
            )

            status = execution.get("status", "unknown")
            if status == "success":
                result.status = WorkflowStatus.SUCCESS
                result.success = True
                result.output = execution.get("data", {})
            elif status == "error":
                result.status = WorkflowStatus.FAILED
                result.error = execution.get("error", "n8n API execution failed")
            elif status == "canceled":
                result.status = WorkflowStatus.CANCELLED
                result.error = "Workflow canceled"
            else:
                result.status = WorkflowStatus.FAILED
                result.error = f"Unknown execution status: {status}"

        except asyncio.TimeoutError:
            result.status = WorkflowStatus.FAILED
            result.error = f"API Timeout nach {context.timeout_ms}ms"
        except aiohttp.ClientError as e:
            result.status = WorkflowStatus.FAILED
            result.error = f"n8n API Fehler: {e}"
        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.error = str(e)

        return result

    def _spec_to_n8n_json(self, spec: WorkflowSpec) -> dict:
        """Konvertiert WorkflowSpec zurück zu n8n JSON."""
        # Rekonstruiere n8n Structure aus Spec
        nodes = []
        connections = {}

        for step in spec.steps:
            if step.type != "n8n_node":
                continue

            node = {
                "id": step.id,
                "name": step.name,
                "type": step.config.get("n8n_type", "n8n-nodes-base.noOp"),
                "position": step.config.get("position", [0, 0]),
                "parameters": step.config.get("parameters", {}),
                "credentials": step.config.get("credentials", {}),
                "disabled": step.config.get("disabled", False),
            }
            nodes.append(node)

            # Connections
            if step.depends_on:
                connections[step.id] = {
                    "main": [[{"node": dep_id, "type": "main", "index": 0}] for dep_id in step.depends_on]
                }

        return {
            "name": spec.name,
            "nodes": nodes,
            "connections": connections,
            "active": False,
            "settings": spec.metadata.get("n8n_settings", {}),
        }

    # =========================================================================
    # Export
    # =========================================================================

    def export(self, spec: WorkflowSpec, format: str) -> str:
        """Exportiert Spec als n8n Workflow JSON."""
        format = format.lower()

        if format in ("n8n.json", "json"):
            workflow_json = self._spec_to_n8n_json(spec)
            return json.dumps(workflow_json, indent=2, ensure_ascii=False)
        elif format in ("yaml", "yml"):
            import yaml
            workflow_json = self._spec_to_n8n_json(spec)
            return yaml.dump(workflow_json, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Nicht unterstütztes Export-Format: {format}")


class N8nApiClient:
    """n8n REST API Client für Workflow Execution ohne CLI."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-N8N-API-KEY"] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_workflows(self) -> list[dict]:
        """Listet alle Workflows."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/api/v1/workflows") as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("data", [])

    async def get_workflow(self, workflow_id: str) -> dict:
        """Holt einen Workflow by ID."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/api/v1/workflows/{workflow_id}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def create_workflow(self, workflow: dict) -> dict:
        """Erstellt einen neuen Workflow."""
        session = await self._get_session()
        async with session.post(f"{self.base_url}/api/v1/workflows", json=workflow) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def update_workflow(self, workflow_id: str, workflow: dict) -> dict:
        """Aktualisiert einen Workflow."""
        session = await self._get_session()
        async with session.put(f"{self.base_url}/api/v1/workflows/{workflow_id}", json=workflow) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Löscht einen Workflow."""
        session = await self._get_session()
        async with session.delete(f"{self.base_url}/api/v1/workflows/{workflow_id}") as resp:
            resp.raise_for_status()
            return True

    async def execute_workflow(
        self,
        workflow_id: str,
        data: Optional[dict] = None,
        wait: bool = True,
        timeout_seconds: int = 300
    ) -> dict:
        """Führt einen Workflow via API aus.

        Args:
            workflow_id: ID des Workflows
            data: Input Data für den Workflow
            wait: Ob auf Abschluss warten
            timeout_seconds: Timeout in Sekunden

        Returns:
            Execution Result mit Status, Data, etc.
        """
        session = await self._get_session()

        # Workflow ausführen
        exec_data = {"data": data or {}}
        async with session.post(
            f"{self.base_url}/api/v1/workflows/{workflow_id}/execute",
            json=exec_data
        ) as resp:
            resp.raise_for_status()
            execution = await resp.json()

        execution_id = execution.get("id")
        if not execution_id:
            raise ValueError("Keine Execution ID in Response")

        if not wait:
            return {"execution_id": execution_id, "status": "started"}

        # Polling bis Abschluss
        start_time = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                raise asyncio.TimeoutError(f"Workflow Execution Timeout nach {timeout_seconds}s")

            async with session.get(
                f"{self.base_url}/api/v1/executions/{execution_id}"
            ) as resp:
                resp.raise_for_status()
                execution = await resp.json()

            status = execution.get("status", "unknown")
            if status in ("success", "error", "canceled"):
                return execution

            await asyncio.sleep(1)  # Polling Interval

    async def get_execution(self, execution_id: str) -> dict:
        """Holt Execution Status."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/api/v1/executions/{execution_id}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_credentials(self) -> list[dict]:
        """Listet alle Credentials."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/api/v1/credentials") as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("data", [])

    async def get_credential(self, credential_id: str) -> dict:
        """Holt Credential Details (mit decrypted values falls berechtigt)."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/api/v1/credentials/{credential_id}") as resp:
            resp.raise_for_status()
            return await resp.json()
