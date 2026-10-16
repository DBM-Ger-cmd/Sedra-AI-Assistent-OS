import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from guppi_runtime.readiness import build_report, initialization_failure
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class ReadinessCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.runtime = SimpleNamespace(
            boot=Mock(return_value={'state': 'READY'}),
            sandbox=SimpleNamespace(doctor=Mock(return_value={'blockers': [], 'execution_ready': True}),
                                    data_root=root / 'sandboxes'),
            hardware_manager=SimpleNamespace(
                root=root / 'hardware',
                get_state=Mock(return_value={'thermal_state': 'NORMAL', 'profile_error': None}),
                capabilities=Mock(return_value={'fan_control': {'write_supported': False}}),
                preflight=Mock(return_value={'thermal_state': 'NORMAL'}),
                apply_profile=Mock(side_effect=AssertionError('must not write')),
                restore=Mock(side_effect=AssertionError('must not write'))))

    def test_pass_is_only_prerequisites(self):
        report = build_report(self.runtime)
        self.assertEqual(report['status'], 'PRECHECK_PASS_PC_TEST_PENDING')
        self.assertFalse(report['release_ready'])
        self.assertTrue(report['pending_acceptance'])
        self.assertFalse(report['hardware_manager']['fan_write_ready'])
        self.runtime.hardware_manager.apply_profile.assert_not_called()
        self.runtime.hardware_manager.restore.assert_not_called()

    def test_core_safe_mode_blocks_even_with_available_sandbox(self):
        self.runtime.boot.return_value = {'state': 'SAFE_MODE'}
        report = build_report(self.runtime)
        self.assertIn('core:core_not_ready', report['blockers'])
        self.assertEqual(report['status'], 'PRECHECK_BLOCKED')

    def test_boot_exception_does_not_hide_other_probes(self):
        self.runtime.boot.side_effect = ValueError('damaged_registry')
        report = build_report(self.runtime)
        self.assertEqual(report['core_state'], 'UNKNOWN')
        self.assertEqual(report['checks']['core']['status'], 'ERROR')
        self.runtime.sandbox.doctor.assert_called_once()
        self.runtime.hardware_manager.preflight.assert_called_once()

    def test_sandbox_blockers_are_kept(self):
        self.runtime.sandbox.doctor.return_value = {'blockers': ['missing_image', 'missing_sdk']}
        self.assertEqual(build_report(self.runtime)['blockers'],
                         ['sandbox:missing_image', 'sandbox:missing_sdk'])

    def test_broken_doctor_blocks(self):
        self.runtime.sandbox.doctor.side_effect = ValueError('invalid_policy')
        self.assertIn('sandbox:probe_failed', build_report(self.runtime)['blockers'])

    def test_hardware_collection_error_keeps_sandbox_result(self):
        self.runtime.hardware_manager.get_state.side_effect = RuntimeError('sensor_io_failed')
        report = build_report(self.runtime)
        self.assertIn('hardware_state:probe_failed', report['blockers'])
        self.assertIsNotNone(report['sandbox'])

    def test_profile_error_blocks(self):
        self.runtime.hardware_manager.get_state.return_value = {
            'thermal_state': 'SENSOR_FAULT', 'profile_error': 'hardware_changed'}
        self.assertIn('hardware_state:profile_error', build_report(self.runtime)['blockers'])

    def test_admission_errors_block(self):
        for reason in ['HOT', 'CRITICAL', 'SENSOR_FAULT', 'RECOVERY', 'RAM_reserve_not_available']:
            with self.subTest(reason=reason):
                self.runtime.hardware_manager.preflight.side_effect = RuntimeError(reason)
                report = build_report(self.runtime)
                self.assertIn('hardware_admission:probe_failed', report['blockers'])
                self.assertEqual(report['checks']['hardware_admission']['error'], reason)

    def test_capability_error_blocks(self):
        self.runtime.hardware_manager.capabilities.side_effect = ValueError('invalid_inventory')
        self.assertIn('hardware_capabilities:probe_failed', build_report(self.runtime)['blockers'])

    def test_retained_locks_block_and_are_never_removed(self):
        for component, parent, filename in [
            ('hardware_operation', self.runtime.hardware_manager.root, 'mutation.lock'),
            ('sandbox_operation', self.runtime.sandbox.data_root, 'active.lock')]:
            parent.mkdir()
            path = parent / filename
            path.write_text('interrupted')
            report = build_report(self.runtime)
            self.assertIn(component + ':active_or_interrupted_operation', report['blockers'])
            self.assertEqual(path.read_text(), 'interrupted')

    def test_unqualified_thermal_limits_are_explicit(self):
        self.runtime.hardware_manager.get_state.return_value = {'thermal_state': 'UNQUALIFIED'}
        report = build_report(self.runtime)
        self.assertTrue(report['warnings'])
        self.assertFalse(report['release_ready'])

    def test_initialization_failure_is_reported_by_cli(self):
        spec = importlib.util.spec_from_file_location('ready_cli', Path(__file__).parents[1] / 'ready_test.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, 'GuppiRuntime', side_effect=ValueError('invalid_configuration')), \
             patch('sys.argv', ['ready_test.py', '--root', self.tmp.name]), patch('builtins.print'):
            self.assertEqual(module.main(), 2)
        report = json.loads((Path(self.tmp.name) / 'runtime_data/reports/PC_READY_TEST_v1.15.json').read_text())
        self.assertIn('initialization:probe_failed', report['blockers'])
        self.assertFalse(report['release_ready'])
        self.assertEqual(initialization_failure(ValueError('x'))['status'], 'PRECHECK_BLOCKED')
