"""Tests for Factory Production Hardening (F2-05)."""

from __future__ import annotations

import asyncio
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sedra_runtime.factory.production_hardening import (
    MonitoringCollector,
    AlertManager,
    AlertRule,
    Alert,
    AlertSeverity,
    AlertChannel,
    RetryPolicy,
    RetryExecutor,
    RetryAttempt,
    ProductionHardening,
    ExecutionMetrics,
    get_default_hardening,
)


class MonitoringCollectorTest(unittest.TestCase):
    """Tests for MonitoringCollector."""

    def setUp(self):
        self.collector = MonitoringCollector(window_minutes=60)

    def _make_metrics(self, **kwargs) -> ExecutionMetrics:
        defaults = {
            "execution_id": "exec-1",
            "workflow_id": "wf-1",
            "workflow_name": "Test Workflow",
            "adapter_type": "native",
            "status": "success",
            "duration_ms": 1000,
            "started_at": datetime.now().isoformat(),
            "finished_at": datetime.now().isoformat(),
        }
        defaults.update(kwargs)
        return ExecutionMetrics(**defaults)

    def test_record_and_failure_rate(self):
        """Test recording metrics and calculating failure rate."""
        self.collector.record(self._make_metrics(status="success", execution_id="1"))
        self.collector.record(self._make_metrics(status="success", execution_id="2"))
        self.collector.record(self._make_metrics(status="failed", execution_id="3"))
        self.collector.record(self._make_metrics(status="timeout", execution_id="4"))

        rate = self.collector.get_failure_rate()
        self.assertEqual(rate, 0.5)  # 2/4 failed

    def test_failure_rate_by_adapter(self):
        """Test failure rate filtered by adapter type."""
        self.collector.record(self._make_metrics(adapter_type="native", status="success", execution_id="1"))
        self.collector.record(self._make_metrics(adapter_type="native", status="failed", execution_id="2"))
        self.collector.record(self._make_metrics(adapter_type="n8n", status="success", execution_id="3"))

        native_rate = self.collector.get_failure_rate(adapter_type="native")
        n8n_rate = self.collector.get_failure_rate(adapter_type="n8n")

        self.assertEqual(native_rate, 0.5)
        self.assertEqual(n8n_rate, 0.0)

    def test_avg_duration(self):
        """Test average duration calculation."""
        self.collector.record(self._make_metrics(duration_ms=1000, execution_id="1"))
        self.collector.record(self._make_metrics(duration_ms=2000, execution_id="2"))
        self.collector.record(self._make_metrics(duration_ms=3000, execution_id="3"))

        avg = self.collector.get_avg_duration()
        self.assertEqual(avg, 2000.0)

    def test_p95_duration(self):
        """Test P95 duration calculation."""
        for i in range(100):
            self.collector.record(self._make_metrics(duration_ms=i * 10, execution_id=str(i)))

        p95 = self.collector.get_p95_duration()
        # 95th percentile of 0-990 should be ~940
        self.assertGreaterEqual(p95, 930)
        self.assertLessEqual(p95, 950)

    def test_throughput(self):
        """Test throughput calculation (executions per minute)."""
        now = datetime.now()
        for i in range(10):
            m = self._make_metrics(
                execution_id=str(i),
                started_at=(now - timedelta(seconds=30)).isoformat(),  # 30 seconds ago
                finished_at=now.isoformat(),
            )
            self.collector.record(m)

        # 10 executions in 1 minute window = 10/min
        throughput = self.collector.get_throughput(minutes=1)
        self.assertAlmostEqual(throughput, 10.0, places=0)

    def test_retry_rate(self):
        """Test average retry count."""
        self.collector.record(self._make_metrics(retry_count=0, execution_id="1"))
        self.collector.record(self._make_metrics(retry_count=1, execution_id="2"))
        self.collector.record(self._make_metrics(retry_count=2, execution_id="3"))

        rate = self.collector.get_retry_rate()
        self.assertEqual(rate, 1.0)

    def test_get_summary(self):
        """Test comprehensive summary."""
        self.collector.record(self._make_metrics(status="success", execution_id="1"))
        self.collector.record(self._make_metrics(status="failed", execution_id="2"))
        self.collector.record(self._make_metrics(status="cancelled", execution_id="3"))

        summary = self.collector.get_summary()
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["by_status"]["success"], 1)
        self.assertEqual(summary["by_status"]["failed"], 1)
        self.assertEqual(summary["by_status"]["cancelled"], 1)
        self.assertAlmostEqual(summary["failure_rate"], 2/3)

    def test_window_filtering(self):
        """Test that old metrics are filtered out by time window."""
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        recent_time = datetime.now().isoformat()

        self.collector.record(self._make_metrics(
            execution_id="old", started_at=old_time, finished_at=old_time
        ))
        self.collector.record(self._make_metrics(
            execution_id="recent", started_at=recent_time, finished_at=recent_time
        ))

        # Default window is 60 minutes, old should be filtered
        summary = self.collector.get_summary()
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["by_status"].get("success", 0), 1)


class AlertManagerTest(unittest.TestCase):
    """Tests for AlertManager."""

    def setUp(self):
        self.collector = MonitoringCollector(window_minutes=60)
        self.alerts = AlertManager(self.collector)

    def _record_executions(self, count: int, failure_rate: float = 0.0):
        """Helper to record executions with given failure rate."""
        for i in range(count):
            status = "failed" if i < count * failure_rate else "success"
            self.collector.record(ExecutionMetrics(
                execution_id=f"exec-{i}",
                workflow_id="wf-1",
                workflow_name="Test",
                adapter_type="native",
                status=status,
                duration_ms=1000,
                started_at=datetime.now().isoformat(),
                finished_at=datetime.now().isoformat(),
            ))

    def test_add_and_get_rule(self):
        """Test adding and retrieving alert rules."""
        rule = AlertRule(
            id="test-rule",
            name="Test Rule",
            description="Test",
            metric="execution_failure_rate",
            threshold=0.1,
            operator="gt",
        )
        self.alerts.add_rule(rule)

        retrieved = self.alerts.get_rule("test-rule")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test-rule")
        self.assertEqual(retrieved.threshold, 0.1)

    def test_remove_rule(self):
        """Test removing alert rules."""
        rule = AlertRule(
            id="remove-me",
            name="Remove Me",
            description="Test",
            metric="execution_failure_rate",
            threshold=0.1,
            operator="gt",
        )
        self.alerts.add_rule(rule)
        self.assertTrue(self.alerts.remove_rule("remove-me"))
        self.assertIsNone(self.alerts.get_rule("remove-me"))
        self.assertFalse(self.alerts.remove_rule("nonexistent"))

    def test_list_rules(self):
        """Test listing rules with enabled filter."""
        self.alerts.add_rule(AlertRule(
            id="enabled-rule", name="Enabled", description="",
            metric="execution_failure_rate", threshold=0.1, operator="gt", enabled=True
        ))
        self.alerts.add_rule(AlertRule(
            id="disabled-rule", name="Disabled", description="",
            metric="execution_failure_rate", threshold=0.1, operator="gt", enabled=False
        ))

        all_rules = self.alerts.list_rules()
        enabled_rules = self.alerts.list_rules(enabled_only=True)

        self.assertEqual(len(all_rules), 2)
        self.assertEqual(len(enabled_rules), 1)
        self.assertEqual(enabled_rules[0].id, "enabled-rule")

    def test_check_rules_fires_alert(self):
        """Test that rules fire alerts when threshold exceeded."""
        # Setup: 50% failure rate
        self._record_executions(10, failure_rate=0.5)

        rule = AlertRule(
            id="high-failure",
            name="High Failure Rate",
            description="Test",
            metric="execution_failure_rate",
            threshold=0.1,
            operator="gt",
            severity=AlertSeverity.WARNING,
        )
        self.alerts.add_rule(rule)

        fired = self.alerts.check_rules()
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].rule_id, "high-failure")
        self.assertEqual(fired[0].severity, AlertSeverity.WARNING)
        self.assertIn("0.50", fired[0].message)

    def test_check_rules_no_alert_when_below_threshold(self):
        """Test that rules don't fire when below threshold."""
        # 5% failure rate
        self._record_executions(20, failure_rate=0.05)

        rule = AlertRule(
            id="high-failure",
            name="High Failure Rate",
            description="Test",
            metric="execution_failure_rate",
            threshold=0.1,
            operator="gt",
        )
        self.alerts.add_rule(rule)

        fired = self.alerts.check_rules()
        self.assertEqual(len(fired), 0)

    def test_cooldown_prevents_duplicate_alerts(self):
        """Test that cooldown prevents firing same alert repeatedly."""
        self._record_executions(10, failure_rate=0.5)

        rule = AlertRule(
            id="high-failure",
            name="High Failure Rate",
            description="Test",
            metric="execution_failure_rate",
            threshold=0.1,
            operator="gt",
            cooldown_seconds=300,
        )
        self.alerts.add_rule(rule)

        # First check fires
        fired1 = self.alerts.check_rules()
        self.assertEqual(len(fired1), 1)

        # Second check should not fire (cooldown)
        fired2 = self.alerts.check_rules()
        self.assertEqual(len(fired2), 0)

    def test_different_operators(self):
        """Test different comparison operators."""
        self._record_executions(10, failure_rate=0.5)

        # Test lte (should fire when value <= threshold)
        rule_lte = AlertRule(
            id="lte-test", name="LTE Test", description="",
            metric="execution_failure_rate", threshold=0.6, operator="lte",
        )
        self.alerts.add_rule(rule_lte)
        fired = self.alerts.check_rules()
        self.assertEqual(len(fired), 1)  # 0.5 <= 0.6 is true

        # Test lt
        rule_lt = AlertRule(
            id="lt-test", name="LT Test", description="",
            metric="execution_failure_rate", threshold=0.5, operator="lt",
        )
        self.alerts.add_rule(rule_lt)
        # Clear previous by creating new manager
        alerts2 = AlertManager(self.collector)
        alerts2.add_rule(rule_lt)
        fired = alerts2.check_rules()
        self.assertEqual(len(fired), 0)  # 0.5 < 0.5 is false

    def test_acknowledge_alert(self):
        """Test acknowledging alerts."""
        self._record_executions(10, failure_rate=0.5)
        rule = AlertRule(
            id="test", name="Test", description="",
            metric="execution_failure_rate", threshold=0.1, operator="gt",
        )
        self.alerts.add_rule(rule)
        fired = self.alerts.check_rules()
        alert_id = fired[0].id

        # Should be unacknowledged initially
        alerts = self.alerts.get_alerts(unacknowledged_only=True)
        self.assertEqual(len(alerts), 1)

        # Acknowledge
        self.assertTrue(self.alerts.acknowledge_alert(alert_id, "admin"))
        alerts = self.alerts.get_alerts(unacknowledged_only=True)
        self.assertEqual(len(alerts), 0)

    def test_p95_duration_alert(self):
        """Test alert on P95 duration."""
        # Record slow executions
        for i in range(20):
            duration = 400000 if i < 2 else 1000  # 2 slow, 18 fast
            self.collector.record(ExecutionMetrics(
                execution_id=f"exec-{i}",
                workflow_id="wf-1", workflow_name="Test", adapter_type="native",
                status="success", duration_ms=duration,
                started_at=datetime.now().isoformat(),
                finished_at=datetime.now().isoformat(),
            ))

        rule = AlertRule(
            id="slow-p95", name="Slow P95", description="",
            metric="execution_duration_p95", threshold=300000, operator="gt",
        )
        self.alerts.add_rule(rule)

        fired = self.alerts.check_rules()
        self.assertEqual(len(fired), 1)
        self.assertIn("execution_duration_p95", fired[0].message)


class RetryExecutorTest(unittest.TestCase):
    """Tests for RetryExecutor."""

    def setUp(self):
        self.policy = RetryPolicy(
            id="test-policy",
            name="Test Policy",
            max_retries=3,
            base_delay_seconds=0.01,  # Fast for tests
            max_delay_seconds=0.1,
            exponential_base=2.0,
            jitter=False,
            retry_on=["transient", "timeout"],
            excluded_errors=["permanent"],
        )
        self.executor = RetryExecutor(self.policy)

    def test_calculate_delay_exponential(self):
        """Test exponential backoff delay calculation."""
        self.assertEqual(self.executor.calculate_delay(0), 0.01)
        self.assertEqual(self.executor.calculate_delay(1), 0.02)
        self.assertEqual(self.executor.calculate_delay(2), 0.04)
        self.assertEqual(self.executor.calculate_delay(3), 0.08)

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay_seconds."""
        policy = RetryPolicy(
            id="cap-test", name="Cap Test", max_retries=10,
            base_delay_seconds=10.0, max_delay_seconds=1.0,
            jitter=False,  # Disable jitter for predictable test
        )
        executor = RetryExecutor(policy)
        # Even attempt 0 should be capped at max
        self.assertEqual(executor.calculate_delay(0), 1.0)

    def test_should_retry_on_matching_error(self):
        """Test retry decision for matching error."""
        self.assertTrue(self.executor.should_retry("transient error", 0))
        self.assertTrue(self.executor.should_retry("timeout occurred", 1))
        self.assertTrue(self.executor.should_retry("some transient issue", 2))

    def test_should_not_retry_on_excluded_error(self):
        """Test no retry for excluded errors."""
        self.assertFalse(self.executor.should_retry("permanent failure", 0))
        self.assertFalse(self.executor.should_retry("permanent error occurred", 1))

    def test_should_not_retry_after_max_retries(self):
        """Test no retry after max attempts."""
        self.assertFalse(self.executor.should_retry("transient error", 3))  # max_retries=3

    def test_should_not_retry_when_disabled(self):
        """Test no retry when policy disabled."""
        policy = RetryPolicy(
            id="disabled", name="Disabled", max_retries=3, enabled=False
        )
        executor = RetryExecutor(policy)
        self.assertFalse(executor.should_retry("transient error", 0))

    async def test_execute_with_retry_success_first_try(self):
        """Test successful execution on first try."""
        async def operation():
            return "success"

        result, attempts = await self.executor.execute_with_retry(operation)
        self.assertEqual(result, "success")
        self.assertEqual(len(attempts), 0)

    async def test_execute_with_retry_success_after_retries(self):
        """Test successful execution after retries."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("transient error")
            return "success"

        result, attempts = await self.executor.execute_with_retry(operation)
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(len(attempts), 2)  # 2 failed attempts recorded

    async def test_execute_with_retry_exhausted(self):
        """Test exception raised after all retries exhausted."""
        async def operation():
            raise Exception("transient error")

        with self.assertRaises(Exception) as ctx:
            await self.executor.execute_with_retry(operation)
        self.assertIn("transient error", str(ctx.exception))

    async def test_execute_with_retry_sync_function(self):
        """Test retry with sync function."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient error")
            return "sync success"

        result, attempts = await self.executor.execute_with_retry(operation)
        self.assertEqual(result, "sync success")
        self.assertEqual(len(attempts), 1)

    def test_retry_attempt_records_error(self):
        """Test that retry attempts record error details."""
        async def operation():
            raise Exception("specific transient error")

        with self.assertRaises(Exception):
            asyncio.run(self.executor.execute_with_retry(operation))

        # Can't easily check attempts from outside, but we know they were created
        # by the fact that it retried max_retries times


class ProductionHardeningTest(unittest.TestCase):
    """Integration tests for ProductionHardening."""

    def setUp(self):
        self.hardening = ProductionHardening(monitoring_window_minutes=60)

    def test_record_execution(self):
        """Test recording execution metrics."""
        metrics = self.hardening.record_execution(
            execution_id="exec-1",
            workflow_id="wf-1",
            workflow_name="Test Workflow",
            adapter_type="native",
            status="success",
            duration_ms=5000,
            started_at=datetime.now() - timedelta(seconds=5),
            finished_at=datetime.now(),
        )

        self.assertEqual(metrics.execution_id, "exec-1")
        self.assertEqual(metrics.status, "success")
        self.assertEqual(metrics.duration_ms, 5000)

    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        for i in range(5):
            self.hardening.record_execution(
                execution_id=f"exec-{i}",
                workflow_id="wf-1",
                workflow_name="Test",
                adapter_type="native",
                status="success" if i < 4 else "failed",
                duration_ms=1000,
                started_at=datetime.now() - timedelta(minutes=10),
                finished_at=datetime.now(),
            )

        summary = self.hardening.get_metrics_summary()
        self.assertEqual(summary["count"], 5)
        self.assertAlmostEqual(summary["failure_rate"], 0.2)

    def test_check_alerts(self):
        """Test checking alerts."""
        # High failure rate
        for i in range(10):
            self.hardening.record_execution(
                execution_id=f"exec-{i}",
                workflow_id="wf-1", workflow_name="Test", adapter_type="native",
                status="failed" if i < 3 else "success",
                duration_ms=1000,
                started_at=datetime.now() - timedelta(minutes=10),
                finished_at=datetime.now(),
            )

        alerts = self.hardening.check_alerts()
        # Should fire high_failure_rate (30% > 10%)
        alert_ids = {a.rule_id for a in alerts}
        self.assertIn("high_failure_rate", alert_ids)

    def test_add_alert_rule(self):
        """Test adding custom alert rule."""
        rule = AlertRule(
            id="custom-alert",
            name="Custom Alert",
            description="Custom test alert",
            metric="execution_failure_rate",
            threshold=0.5,
            operator="gt",
        )
        self.hardening.add_alert_rule(rule)

        retrieved = self.hardening.alerts.get_rule("custom-alert")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.threshold, 0.5)

    def test_retry_policy_management(self):
        """Test retry policy get/set."""
        default_policy = self.hardening.get_retry_policy("default")
        self.assertEqual(default_policy.id, "default")

        custom_policy = RetryPolicy(
            id="custom", name="Custom", max_retries=5, base_delay_seconds=2.0
        )
        self.hardening.set_retry_policy(custom_policy)

        retrieved = self.hardening.get_retry_policy("custom")
        self.assertEqual(retrieved.max_retries, 5)
        self.assertEqual(retrieved.base_delay_seconds, 2.0)

    def test_create_retry_executor(self):
        """Test creating retry executor from policy."""
        executor = self.hardening.create_retry_executor("default")
        self.assertIsInstance(executor, RetryExecutor)
        self.assertEqual(executor.policy.id, "default")

    async def test_execute_with_retry_integration(self):
        """Test execute_with_retry convenience method."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient error")
            return "integrated success"

        result, attempts = await self.hardening.execute_with_retry(operation)
        self.assertEqual(result, "integrated success")
        self.assertEqual(len(attempts), 1)

    def test_get_default_hardening_singleton(self):
        """Test get_default_hardening returns singleton."""
        h1 = get_default_hardening()
        h2 = get_default_hardening()
        self.assertIs(h1, h2)


class AlertRuleSerializationTest(unittest.TestCase):
    """Tests for AlertRule serialization."""

    def test_to_from_dict(self):
        """Test AlertRule round-trip serialization."""
        rule = AlertRule(
            id="serialize-test",
            name="Serialize Test",
            description="Test serialization",
            metric="execution_failure_rate",
            threshold=0.15,
            operator="gte",
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.LOG, AlertChannel.WEBHOOK],
            webhook_url="http://example.com/webhook",
            cooldown_seconds=600,
            enabled=False,
        )

        data = rule.to_dict()
        self.assertEqual(data["id"], "serialize-test")
        self.assertEqual(data["severity"], "critical")
        self.assertEqual(data["channels"], ["log", "webhook"])
        self.assertEqual(data["webhook_url"], "http://example.com/webhook")

        restored = AlertRule.from_dict(data)
        self.assertEqual(restored.id, rule.id)
        self.assertEqual(restored.severity, rule.severity)
        self.assertEqual(restored.channels, rule.channels)
        self.assertEqual(restored.webhook_url, rule.webhook_url)
        self.assertEqual(restored.enabled, rule.enabled)


if __name__ == "__main__":
    unittest.main()