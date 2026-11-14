"""Policy Evaluator — Policy Decision Engine mit Captain Gate Integration (Z4)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from .registry import PolicyRegistry, PolicyDefinition, PolicyEvaluatorType, PolicySeverity


class PolicyDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    ERROR = "error"


@dataclass
class PolicyContext:
    """Context für Policy Evaluation."""
    workflow_id: str
    step_id: str
    step_name: str
    adapter_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    user_roles: list[str] = field(default_factory=list)
    environment: str = "development"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyResult:
    """Ergebnis einer Policy Evaluation."""
    policy_id: str
    decision: PolicyDecision
    reason: str = ""
    evaluator: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence_data: dict[str, Any] = field(default_factory=dict)


# Type aliases für Gate Callbacks
GateCallback = Callable[[str, dict[str, Any]], str]  # policy_id, context -> decision (sync)
AsyncGateCallback = Callable[[str, dict[str, Any]], Awaitable[str]]  # policy_id, context -> decision (async)


class PolicyEvaluator:
    """Policy Evaluator mit Captain Gate Integration (Z4)."""

    def __init__(
        self,
        registry: PolicyRegistry,
        gate_callback: Optional[GateCallback] = None,
        default_timeout_seconds: float = 300.0,  # 5 Minuten Default
    ):
        self.registry = registry
        self.gate_callback = gate_callback
        self.default_timeout_seconds = default_timeout_seconds
        self._pending_gates: dict[str, tuple[PolicyContext, PolicyResult]] = {}

    def evaluate(
        self,
        policy_id: str,
        context: PolicyContext,
    ) -> PolicyResult:
        """Evaluiert eine Policy synchron."""
        policy = self.registry.get(policy_id)
        if not policy:
            return PolicyResult(
                policy_id=policy_id,
                decision=PolicyDecision.ERROR,
                reason=f"Policy nicht gefunden: {policy_id}",
                evaluator="registry",
            )

        # Auto-Evaluator: Sofortige Entscheidung basierend auf Config
        if policy.evaluator == PolicyEvaluatorType.AUTO:
            return self._evaluate_auto(policy, context)

        # Script-Evaluator: Placeholder für zukünftige Script-basierte Policies
        if policy.evaluator == PolicyEvaluatorType.SCRIPT:
            return self._evaluate_script(policy, context)

        # Captain Gate: Async Callback (hier synchron blockierend für Simplicity)
        if policy.evaluator == PolicyEvaluatorType.CAPTAIN_GATE:
            return self._evaluate_captain_gate(policy, context)

        return PolicyResult(
            policy_id=policy_id,
            decision=PolicyDecision.ERROR,
            reason=f"Unbekannter Evaluator: {policy.evaluator}",
            evaluator=policy.evaluator.value,
        )

    def _evaluate_auto(self, policy: PolicyDefinition, context: PolicyContext) -> PolicyResult:
        """Auto-Evaluation basierend auf Policy Config."""
        # Environment Check
        allowed_envs = policy.config.get("environments", [])
        if allowed_envs and context.environment not in allowed_envs:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.REJECTED,
                reason=f"Environment '{context.environment}' nicht erlaubt für Auto-Policy",
                evaluator="auto",
            )

        # Role Check
        required_roles = policy.config.get("required_roles", [])
        if required_roles:
            has_role = any(role in context.user_roles for role in required_roles)
            if not has_role:
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.REJECTED,
                    reason=f"Benötigte Rollen fehlen: {required_roles}",
                    evaluator="auto",
                )

        # Resource Thresholds
        cpu_threshold = policy.config.get("cpu_threshold_percent")
        memory_threshold = policy.config.get("memory_threshold_mb")
        if cpu_threshold or memory_threshold:
            # TODO: Actual resource monitoring integration
            pass

        return PolicyResult(
            policy_id=policy.id,
            decision=PolicyDecision.APPROVED,
            reason="Auto-Policy Conditions erfüllt",
            evaluator="auto",
        )

    def _evaluate_script(self, policy: PolicyDefinition, context: PolicyContext) -> PolicyResult:
        """Script-basierte Evaluation (Placeholder)."""
        script = policy.config.get("script", "")
        if not script:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.ERROR,
                reason="Kein Script für Script-Evaluator konfiguriert",
                evaluator="script",
            )
        # TODO: Safe Script Execution (RestrictedPython, etc.)
        return PolicyResult(
            policy_id=policy.id,
            decision=PolicyDecision.PENDING,
            reason="Script Evaluation nicht implementiert",
            evaluator="script",
        )

    def _evaluate_captain_gate(self, policy: PolicyDefinition, context: PolicyContext) -> PolicyResult:
        """Captain Gate Evaluation via Callback."""
        if not self.gate_callback:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.ERROR,
                reason="Kein Gate Callback registriert",
                evaluator="captain_gate",
            )

        # Gate Context für Captain
        gate_context = {
            "policy_id": policy.id,
            "policy_name": policy.name,
            "policy_description": policy.description,
            "policy_severity": policy.severity.value,
            "workflow_id": context.workflow_id,
            "step_id": context.step_id,
            "step_name": context.step_name,
            "adapter_type": context.adapter_type,
            "environment": context.environment,
            "user_roles": context.user_roles,
            "parameters": context.parameters,
            "metadata": context.metadata,
        }

        try:
            # Sync call to gate callback (in real impl: async with timeout)
            decision = self.gate_callback(policy.id, gate_context)

            if decision == "approved":
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.APPROVED,
                    reason="Captain approved",
                    evaluator="captain_gate",
                    evidence_data=gate_context,
                )
            elif decision == "rejected":
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.REJECTED,
                    reason="Captain rejected",
                    evaluator="captain_gate",
                    evidence_data=gate_context,
                )
            else:
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.PENDING,
                    reason=f"Unbekannte Gate Decision: {decision}",
                    evaluator="captain_gate",
                )
        except Exception as e:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.ERROR,
                reason=f"Gate Callback Fehler: {e}",
                evaluator="captain_gate",
            )

    def evaluate_multiple(
        self,
        policy_ids: list[str],
        context: PolicyContext,
    ) -> list[PolicyResult]:
        """Evaluiert multiple Policies (alle müssen APPROVED sein)."""
        results = []
        for pid in policy_ids:
            result = self.evaluate(pid, context)
            results.append(result)
            if result.decision != PolicyDecision.APPROVED:
                # Early exit bei Reject/Error
                break
        return results


class AsyncPolicyEvaluator:
    """Async Policy Evaluator für echte Captain Gates mit Timeout und Webhook Support."""

    def __init__(
        self,
        registry: PolicyRegistry,
        gate_callback: Optional[AsyncGateCallback] = None,
        gate_callback_sync: Optional[GateCallback] = None,
        default_timeout_seconds: float = 300.0,
        webhook_url: Optional[str] = None,
    ):
        self.registry = registry
        self.gate_callback = gate_callback
        self.gate_callback_sync = gate_callback_sync
        self.default_timeout = default_timeout_seconds
        self.webhook_url = webhook_url
        self._pending_gates: dict[str, asyncio.Task] = {}

    async def evaluate(
        self,
        policy_id: str,
        context: PolicyContext,
    ) -> PolicyResult:
        """Async Evaluation mit Timeout Support."""
        policy = self.registry.get(policy_id)
        if not policy:
            return PolicyResult(
                policy_id=policy_id,
                decision=PolicyDecision.ERROR,
                reason=f"Policy nicht gefunden: {policy_id}",
                evaluator="registry",
            )

        if policy.evaluator == PolicyEvaluatorType.AUTO:
            return self._evaluate_auto(policy, context)

        if policy.evaluator == PolicyEvaluatorType.SCRIPT:
            return self._evaluate_script(policy, context)

        if policy.evaluator == PolicyEvaluatorType.CAPTAIN_GATE:
            return await self._evaluate_captain_gate_async(policy, context)

        return PolicyResult(
            policy_id=policy_id,
            decision=PolicyDecision.ERROR,
            reason=f"Unbekannter Evaluator: {policy.evaluator}",
            evaluator=policy.evaluator.value,
        )

    def _evaluate_auto(self, policy: PolicyDefinition, context: PolicyContext) -> PolicyResult:
        """Auto-Evaluation (delegiert an sync evaluator logic)."""
        allowed_envs = policy.config.get("environments", [])
        if allowed_envs and context.environment not in allowed_envs:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.REJECTED,
                reason=f"Environment '{context.environment}' nicht erlaubt für Auto-Policy",
                evaluator="auto",
            )

        required_roles = policy.config.get("required_roles", [])
        if required_roles:
            has_role = any(role in context.user_roles for role in required_roles)
            if not has_role:
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.REJECTED,
                    reason=f"Benötigte Rollen fehlen: {required_roles}",
                    evaluator="auto",
                )

        return PolicyResult(
            policy_id=policy.id,
            decision=PolicyDecision.APPROVED,
            reason="Auto-Policy Conditions erfüllt",
            evaluator="auto",
        )

    def _evaluate_script(self, policy: PolicyDefinition, context: PolicyContext) -> PolicyResult:
        script = policy.config.get("script", "")
        if not script:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.ERROR,
                reason="Kein Script für Script-Evaluator konfiguriert",
                evaluator="script",
            )
        return PolicyResult(
            policy_id=policy.id,
            decision=PolicyDecision.PENDING,
            reason="Script Evaluation nicht implementiert",
            evaluator="script",
        )

    async def _evaluate_captain_gate_async(
        self,
        policy: PolicyDefinition,
        context: PolicyContext,
    ) -> PolicyResult:
        """Async Captain Gate mit Timeout und Webhook Support."""
        
        gate_context = {
            "policy_id": policy.id,
            "policy_name": policy.name,
            "policy_description": policy.description,
            "policy_severity": policy.severity.value,
            "workflow_id": context.workflow_id,
            "step_id": context.step_id,
            "step_name": context.step_name,
            "adapter_type": context.adapter_type,
            "environment": context.environment,
            "user_roles": context.user_roles,
            "parameters": context.parameters,
            "metadata": context.metadata,
        }

        # Webhook Notification (fire-and-forget)
        if self.webhook_url:
            asyncio.create_task(self._send_webhook(policy.id, gate_context))

        # Determine which callback to use
        callback = self.gate_callback or self.gate_callback_sync
        if not callback:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.ERROR,
                reason="Kein Gate Callback registriert",
                evaluator="captain_gate",
            )

        try:
            # Execute callback with timeout
            if asyncio.iscoroutinefunction(callback):
                decision = await asyncio.wait_for(
                    callback(policy.id, gate_context),
                    timeout=self.default_timeout,
                )
            else:
                # Sync callback in thread pool
                loop = asyncio.get_event_loop()
                decision = await asyncio.wait_for(
                    loop.run_in_executor(None, callback, policy.id, gate_context),
                    timeout=self.default_timeout,
                )

            if decision == "approved":
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.APPROVED,
                    reason="Captain approved",
                    evaluator="captain_gate",
                    evidence_data=gate_context,
                )
            elif decision == "rejected":
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.REJECTED,
                    reason="Captain rejected",
                    evaluator="captain_gate",
                    evidence_data=gate_context,
                )
            else:
                return PolicyResult(
                    policy_id=policy.id,
                    decision=PolicyDecision.PENDING,
                    reason=f"Unbekannte Gate Decision: {decision}",
                    evaluator="captain_gate",
                )
        except asyncio.TimeoutError:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.REJECTED,
                reason=f"Captain Gate Timeout nach {self.default_timeout}s",
                evaluator="captain_gate",
            )
        except Exception as e:
            return PolicyResult(
                policy_id=policy.id,
                decision=PolicyDecision.ERROR,
                reason=f"Gate Callback Fehler: {e}",
                evaluator="captain_gate",
            )

    async def _send_webhook(self, policy_id: str, context: dict[str, Any]) -> None:
        """Sendet Webhook Notification (fire-and-forget)."""
        try:
            import aiohttp
            payload = {
                "policy_id": policy_id,
                "timestamp": datetime.now().isoformat(),
                "context": context,
            }
            async with aiohttp.ClientSession() as session:
                await session.post(self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=5))
        except Exception:
            pass  # Silent fail for webhook


def create_evaluator(
    registry: PolicyRegistry,
    gate_callback: Optional[GateCallback] = None,
) -> PolicyEvaluator:
    """Factory für Policy Evaluator."""
    return PolicyEvaluator(registry, gate_callback)


def create_async_evaluator(
    registry: PolicyRegistry,
    gate_callback: Optional[AsyncGateCallback] = None,
    gate_callback_sync: Optional[GateCallback] = None,
    default_timeout_seconds: float = 300.0,
    webhook_url: Optional[str] = None,
) -> AsyncPolicyEvaluator:
    """Factory für Async Policy Evaluator."""
    return AsyncPolicyEvaluator(
        registry,
        gate_callback=gate_callback,
        gate_callback_sync=gate_callback_sync,
        default_timeout_seconds=default_timeout_seconds,
        webhook_url=webhook_url,
    )