"""Factory Production Hardening — Monitoring, Alerting, Retry Logic (F2-05)."""

from __future__ import annotations

import asyncio
import time
import uuid
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from ..evidence_store import get_default_store
    EVIDENCE_STORE_AVAILABLE = True
except ImportError:
    EVIDENCE_STORE_AVAILABLE = False


logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    WEBHOOK = "webhook"
    LOG = "log"
    EMAIL = "email"  # placeholder


@dataclass
class AlertRule:
    """Alert rule configuration."""
    id: str
    name: str
    description: str
    metric: str  # e.g., "execution_failure_rate", "execution_duration_p95", "queue_depth"
    threshold: float
    operator: str  # "gt", "gte", "lt", "lte", "eq"
    severity: AlertSeverity = AlertSeverity.WARNING
    channels: list[AlertChannel] = field(default_factory=lambda: [AlertChannel.LOG])
    webhook_url: Optional[str] = None
    cooldown_seconds: int = 300  # 5 min default cooldown
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_triggered: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["channels"] = [c.value for c in self.channels]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AlertRule":
        data = data.copy()
        data["severity"] = AlertSeverity(data["severity"])
        data["channels"] = [AlertChannel(c) for c in data["channels"]]
        return cls(**data)


@dataclass
class Alert:
    """Fired alert instance."""
    id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_value: float
    threshold: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None


@dataclass
class RetryPolicy:
    """Retry policy for failed executions."""
    id: str
    name: str
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on: list[str] = field(default_factory=lambda: ["timeout", "transient_error", "resource_exhausted"])
    excluded_errors: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class RetryAttempt:
    """Single retry attempt record."""
    attempt_number: int
    delay_seconds: float
    error: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExecutionMetrics:
    """Metrics for a single execution."""
    execution_id: str
    workflow_id: str
    workflow_name: str
    adapter_type: str
    status: str  # success, failed, cancelled, timeout
    duration_ms: int
    started_at: str
    finished_at: str
    retry_count: int = 0
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MonitoringCollector:
    """Collects and aggregates execution metrics."""

    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self._metrics: list[ExecutionMetrics] = []
        self._max_metrics = 10000  # Keep last 10k executions

    def record(self, metrics: ExecutionMetrics) -> None:
        """Record execution metrics."""
        self._metrics.append(metrics)
        # Trim old metrics
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        self._metrics = [
            m for m in self._metrics
            if datetime.fromisoformat(m.started_at) > cutoff
        ]
        # Hard limit
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics:]

    def get_failure_rate(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> float:
        """Get failure rate in the time window."""
        metrics = self._get_filtered(adapter_type, minutes)
        if not metrics:
            return 0.0
        failed = sum(1 for m in metrics if m.status in ("failed", "timeout", "cancelled"))
        return failed / len(metrics)

    def get_avg_duration(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> float:
        """Get average execution duration in ms."""
        metrics = self._get_filtered(adapter_type, minutes)
        if not metrics:
            return 0.0
        return sum(m.duration_ms for m in metrics) / len(metrics)

    def get_p95_duration(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> float:
        """Get 95th percentile duration in ms."""
        metrics = self._get_filtered(adapter_type, minutes)
        if not metrics:
            return 0.0
        durations = sorted(m.duration_ms for m in metrics)
        idx = int(len(durations) * 0.95)
        return durations[min(idx, len(durations) - 1)]

    def get_throughput(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> float:
        """Get executions per minute."""
        metrics = self._get_filtered(adapter_type, minutes)
        if not metrics:
            return 0.0
        window = minutes or self.window_minutes
        return len(metrics) / window

    def get_retry_rate(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> float:
        """Get average retry count per execution."""
        metrics = self._get_filtered(adapter_type, minutes)
        if not metrics:
            return 0.0
        return sum(m.retry_count for m in metrics) / len(metrics)

    def _get_filtered(self, adapter_type: Optional[str], minutes: Optional[int]) -> list[ExecutionMetrics]:
        """Filter metrics by adapter type and time window."""
        cutoff = datetime.now() - timedelta(minutes=minutes or self.window_minutes)
        result = [
            m for m in self._metrics
            if datetime.fromisoformat(m.started_at) > cutoff
        ]
        if adapter_type:
            result = [m for m in result if m.adapter_type == adapter_type]
        return result

    def get_summary(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> dict[str, Any]:
        """Get comprehensive metrics summary."""
        metrics = self._get_filtered(adapter_type, minutes)
        if not metrics:
            return {"count": 0}

        by_status = {}
        for m in metrics:
            by_status[m.status] = by_status.get(m.status, 0) + 1

        return {
            "count": len(metrics),
            "by_status": by_status,
            "failure_rate": self.get_failure_rate(adapter_type, minutes),
            "avg_duration_ms": self.get_avg_duration(adapter_type, minutes),
            "p95_duration_ms": self.get_p95_duration(adapter_type, minutes),
            "throughput_per_min": self.get_throughput(adapter_type, minutes),
            "avg_retry_count": self.get_retry_rate(adapter_type, minutes),
            "window_minutes": minutes or self.window_minutes,
            "adapter_filter": adapter_type,
        }


class AlertManager:
    """Manages alert rules and fires alerts based on metrics."""

    def __init__(self, monitoring: MonitoringCollector):
        self.monitoring = monitoring
        self._rules: dict[str, AlertRule] = {}
        self._alerts: list[Alert] = []
        self._max_alerts = 1000
        self._notification_handlers: dict[AlertChannel, Callable] = {
            AlertChannel.LOG: self._notify_log,
            AlertChannel.WEBHOOK: self._notify_webhook,
        }

    def add_rule(self, rule: AlertRule) -> AlertRule:
        """Add or update an alert rule."""
        self._rules[rule.id] = rule
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = False) -> list[AlertRule]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def check_rules(self, adapter_type: Optional[str] = None) -> list[Alert]:
        """Check all enabled rules against current metrics."""
        fired = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if self._in_cooldown(rule):
                continue

            metric_value = self._get_metric_value(rule.metric, adapter_type)
            if metric_value is None:
                continue

            if self._evaluate_condition(metric_value, rule.threshold, rule.operator):
                alert = self._fire_alert(rule, metric_value)
                fired.append(alert)

        return fired

    def _get_metric_value(self, metric: str, adapter_type: Optional[str]) -> Optional[float]:
        """Get metric value by name."""
        if metric == "execution_failure_rate":
            return self.monitoring.get_failure_rate(adapter_type)
        elif metric == "execution_duration_p95":
            return self.monitoring.get_p95_duration(adapter_type)
        elif metric == "execution_avg_duration":
            return self.monitoring.get_avg_duration(adapter_type)
        elif metric == "execution_throughput":
            return self.monitoring.get_throughput(adapter_type)
        elif metric == "execution_retry_rate":
            return self.monitoring.get_retry_rate(adapter_type)
        return None

    def _evaluate_condition(self, value: float, threshold: float, operator: str) -> bool:
        if operator == "gt":
            return value > threshold
        elif operator == "gte":
            return value >= threshold
        elif operator == "lt":
            return value < threshold
        elif operator == "lte":
            return value <= threshold
        elif operator == "eq":
            return value == threshold
        return False

    def _in_cooldown(self, rule: AlertRule) -> bool:
        if not rule.last_triggered:
            return False
        last = datetime.fromisoformat(rule.last_triggered)
        return (datetime.now() - last).total_seconds() < rule.cooldown_seconds

    def _fire_alert(self, rule: AlertRule, metric_value: float) -> Alert:
        alert = Alert(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            message=f"Alert '{rule.name}': {rule.metric}={metric_value:.2f} {rule.operator} {rule.threshold}",
            metric_value=metric_value,
            threshold=rule.threshold,
        )
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        # Update rule cooldown
        rule.last_triggered = datetime.now().isoformat()

        # Send notifications
        for channel in rule.channels:
            handler = self._notification_handlers.get(channel)
            if handler:
                try:
                    handler(alert, rule)
                except Exception as e:
                    logger.error(f"Notification handler {channel} failed: {e}")

        return alert

    def _notify_log(self, alert: Alert, rule: AlertRule) -> None:
        level = logging.WARNING if alert.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL) else logging.INFO
        logger.log(level, f"ALERT [{alert.severity.value.upper()}] {alert.message}")

    async def _notify_webhook(self, alert: Alert, rule: AlertRule) -> None:
        if not rule.webhook_url:
            return
        try:
            import aiohttp
            payload = {
                "alert_id": alert.id,
                "rule_id": rule.id,
                "rule_name": rule.name,
                "severity": alert.severity.value,
                "message": alert.message,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp,
            }
            async with aiohttp.ClientSession() as session:
                await session.post(rule.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=5))
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")

    def get_alerts(self, unacknowledged_only: bool = False, limit: int = 100) -> list[Alert]:
        alerts = self._alerts
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return alerts[-limit:]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now().isoformat()
                alert.acknowledged_by = acknowledged_by
                return True
        return False


class RetryExecutor:
    """Executes operations with retry logic."""

    def __init__(self, policy: RetryPolicy):
        self.policy = policy

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        delay = self.policy.base_delay_seconds * (self.policy.exponential_base ** attempt)
        delay = min(delay, self.policy.max_delay_seconds)
        if self.policy.jitter:
            import random
            delay *= (0.5 + random.random())  # 0.5-1.5x jitter
        return delay

    def should_retry(self, error: str, attempt: int) -> bool:
        """Determine if operation should be retried."""
        if attempt >= self.policy.max_retries:
            return False
        if not self.policy.enabled:
            return False
        if any(exc in error for exc in self.policy.excluded_errors):
            return False
        return any(retry_err in error for retry_err in self.policy.retry_on)

    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> tuple[Any, list[RetryAttempt]]:
        """Execute operation with retry logic."""
        attempts = []
        last_error = None

        for attempt in range(self.policy.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(*args, **kwargs)
                else:
                    result = operation(*args, **kwargs)
                return result, attempts
            except Exception as e:
                last_error = e
                error_str = str(e)
                delay = self.calculate_delay(attempt)
                attempts.append(RetryAttempt(
                    attempt_number=attempt + 1,
                    delay_seconds=delay,
                    error=error_str,
                ))
                if not self.should_retry(error_str, attempt):
                    break
                if attempt < self.policy.max_retries:
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise last_error


class ProductionHardening:
    """Main entry point for production hardening features."""

    def __init__(
        self,
        monitoring_window_minutes: int = 60,
        metrics_store_path: Optional[Path] = None,
    ):
        self.monitoring = MonitoringCollector(monitoring_window_minutes)
        self.alerts = AlertManager(self.monitoring)
        self._default_retry_policy = RetryPolicy(
            id="default",
            name="Default Retry Policy",
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
        )
        self._retry_policies: dict[str, RetryPolicy] = {
            "default": self._default_retry_policy,
        }

        # Setup default alert rules
        self._setup_default_alerts()

    def _setup_default_alerts(self) -> None:
        """Setup default alert rules."""
        # High failure rate alert
        self.alerts.add_rule(AlertRule(
            id="high_failure_rate",
            name="High Execution Failure Rate",
            description="Triggered when failure rate exceeds 10%",
            metric="execution_failure_rate",
            threshold=0.10,
            operator="gt",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
            cooldown_seconds=300,
        ))

        # Critical failure rate
        self.alerts.add_rule(AlertRule(
            id="critical_failure_rate",
            name="Critical Execution Failure Rate",
            description="Triggered when failure rate exceeds 25%",
            metric="execution_failure_rate",
            threshold=0.25,
            operator="gt",
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.LOG, AlertChannel.WEBHOOK],
            cooldown_seconds=600,
        ))

        # Slow executions (p95 > 5 min)
        self.alerts.add_rule(AlertRule(
            id="slow_executions",
            name="Slow Executions (P95)",
            description="Triggered when P95 duration exceeds 5 minutes",
            metric="execution_duration_p95",
            threshold=300000,  # 5 min in ms
            operator="gt",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.LOG],
            cooldown_seconds=600,
        ))

    def record_execution(
        self,
        execution_id: str,
        workflow_id: str,
        workflow_name: str,
        adapter_type: str,
        status: str,
        duration_ms: int,
        started_at: datetime,
        finished_at: datetime,
        retry_count: int = 0,
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ExecutionMetrics:
        """Record execution metrics."""
        metrics = ExecutionMetrics(
            execution_id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            adapter_type=adapter_type,
            status=status,
            duration_ms=duration_ms,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            retry_count=retry_count,
            error=error,
            metadata=metadata or {},
        )
        self.monitoring.record(metrics)

        # Store to evidence store if available
        if EVIDENCE_STORE_AVAILABLE:
            try:
                store = get_default_store()
                store.record_run_end(
                    run_id=execution_id,
                    success=(status == "success"),
                    error_message=error,
                    metrics={
                        "workflow_id": workflow_id,
                        "workflow_name": workflow_name,
                        "adapter_type": adapter_type,
                        "duration_ms": duration_ms,
                        "retry_count": retry_count,
                        "status": status,
                    }
                )
            except Exception:
                pass  # Silent fail

        return metrics

    def get_metrics_summary(self, adapter_type: Optional[str] = None, minutes: Optional[int] = None) -> dict:
        return self.monitoring.get_summary(adapter_type, minutes)

    def check_alerts(self, adapter_type: Optional[str] = None) -> list[Alert]:
        return self.alerts.check_rules(adapter_type)

    def add_alert_rule(self, rule: AlertRule) -> AlertRule:
        return self.alerts.add_rule(rule)

    def get_retry_policy(self, policy_id: str = "default") -> RetryPolicy:
        return self._retry_policies.get(policy_id, self._default_retry_policy)

    def set_retry_policy(self, policy: RetryPolicy) -> None:
        self._retry_policies[policy.id] = policy

    def create_retry_executor(self, policy_id: str = "default") -> RetryExecutor:
        return RetryExecutor(self.get_retry_policy(policy_id))

    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        policy_id: str = "default",
        **kwargs
    ) -> tuple[Any, list[RetryAttempt]]:
        """Execute operation with retry policy."""
        executor = self.create_retry_executor(policy_id)
        return await executor.execute_with_retry(operation, *args, **kwargs)


# Global instance for easy access
_default_hardening: Optional[ProductionHardening] = None


def get_default_hardening() -> ProductionHardening:
    """Get or create default production hardening instance."""
    global _default_hardening
    if _default_hardening is None:
        _default_hardening = ProductionHardening()
    return _default_hardening


def set_default_hardening(hardening: ProductionHardening) -> None:
    """Set custom default production hardening instance."""
    global _default_hardening
    _default_hardening = hardening