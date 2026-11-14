"""Policy Registry — Zentrale Policy-Verwaltung (Z5)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PolicySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyEvaluatorType(str, Enum):
    CAPTAIN_GATE = "captain_gate"
    AUTO = "auto"
    SCRIPT = "script"


@dataclass
class PolicyDefinition:
    """Policy Definition für Captain Gates und automatische Policies."""
    id: str
    name: str
    description: str
    severity: PolicySeverity
    requires: list[str] = field(default_factory=list)  # roles, approval types
    evaluator: PolicyEvaluatorType = PolicyEvaluatorType.CAPTAIN_GATE
    config: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["evaluator"] = self.evaluator.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PolicyDefinition":
        data = data.copy()
        data["severity"] = PolicySeverity(data["severity"])
        data["evaluator"] = PolicyEvaluatorType(data["evaluator"])
        return cls(**data)


class PolicyRegistry:
    """Zentrale Policy Registry mit Persistenz (Z5)."""

    def __init__(self, store_path: Optional[Path] = None):
        self._policies: dict[str, PolicyDefinition] = {}
        self._store_path = store_path or Path("local_config/policies.json")
        self._load()

    def _load(self) -> None:
        """Lädt Policies aus JSON Datei."""
        if self._store_path.exists():
            try:
                with self._store_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                for p_data in data.get("policies", []):
                    policy = PolicyDefinition.from_dict(p_data)
                    self._policies[policy.id] = policy
            except Exception:
                pass  # Silent fail, start with empty registry

    def _save(self) -> None:
        """Speichert Policies in JSON Datei (atomar)."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._store_path.with_suffix(".tmp")
        data = {
            "version": "1.0",
            "policies": [p.to_dict() for p in self._policies.values()],
            "updated_at": datetime.now().isoformat(),
        }
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self._store_path)

    # --- CRUD Operations ---

    def register(self, policy: PolicyDefinition) -> PolicyDefinition:
        """Registriert eine neue Policy."""
        if policy.id in self._policies:
            raise ValueError(f"Policy bereits registriert: {policy.id}")
        policy.created_at = datetime.now().isoformat()
        policy.updated_at = datetime.now().isoformat()
        self._policies[policy.id] = policy
        self._save()
        return policy

    def get(self, policy_id: str) -> Optional[PolicyDefinition]:
        """Holt Policy by ID."""
        return self._policies.get(policy_id)

    def update(self, policy: PolicyDefinition) -> PolicyDefinition:
        """Aktualisiert bestehende Policy."""
        if policy.id not in self._policies:
            raise ValueError(f"Policy nicht gefunden: {policy.id}")
        policy.updated_at = datetime.now().isoformat()
        self._policies[policy.id] = policy
        self._save()
        return policy

    def delete(self, policy_id: str) -> bool:
        """Löscht Policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            self._save()
            return True
        return False

    def list(self) -> list[PolicyDefinition]:
        """Listet alle Policies."""
        return list(self._policies.values())

    def list_by_severity(self, severity: PolicySeverity) -> list[PolicyDefinition]:
        """Filtert Policies nach Severity."""
        return [p for p in self._policies.values() if p.severity == severity]

    def list_by_evaluator(self, evaluator: PolicyEvaluatorType) -> list[PolicyDefinition]:
        """Filtert Policies nach Evaluator Type."""
        return [p for p in self._policies.values() if p.evaluator == evaluator]


# --- Default Policies ---

DEFAULT_POLICIES = [
    PolicyDefinition(
        id="production-deploy",
        name="Production Deployment",
        description="Erfordert Captain Approval für Production Deployments",
        severity=PolicySeverity.CRITICAL,
        requires=["captain", "approval:manual"],
        evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
    ),
    PolicyDefinition(
        id="data-migration",
        name="Data Migration",
        description="Erfordert Captain Approval für Data Migration Operations",
        severity=PolicySeverity.HIGH,
        requires=["captain", "approval:manual"],
        evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
    ),
    PolicyDefinition(
        id="schema-change",
        name="Schema Change",
        description="Erfordert Captain Approval für Database Schema Changes",
        severity=PolicySeverity.HIGH,
        requires=["captain", "approval:manual"],
        evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
    ),
    PolicyDefinition(
        id="external-api-call",
        name="External API Call",
        description="Auto-Approval für External API Calls in Development",
        severity=PolicySeverity.MEDIUM,
        requires=[],
        evaluator=PolicyEvaluatorType.AUTO,
        config={"environments": ["development", "staging"]},
    ),
    PolicyDefinition(
        id="resource-intensive",
        name="Resource Intensive Operation",
        description="Captain Approval für CPU/Memory intensive Operations",
        severity=PolicySeverity.HIGH,
        requires=["captain"],
        evaluator=PolicyEvaluatorType.CAPTAIN_GATE,
        config={"cpu_threshold_percent": 80, "memory_threshold_mb": 1024},
    ),
]


def create_default_registry(store_path: Optional[Path] = None) -> PolicyRegistry:
    """Erstellt Registry mit Default Policies."""
    registry = PolicyRegistry(store_path)
    for policy in DEFAULT_POLICIES:
        if policy.id not in registry._policies:
            registry.register(policy)
    return registry