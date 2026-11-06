"""F0-04: no fabricated operational readiness; failed construction cleans up."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sedra_runtime.runtime import SedraRuntime, SedraRuntime, _readiness_from_boot
from sedra_runtime.wissen.speicher import WissenSpeicher
import os
from host_isolation import setUpModule as _host_hoch, tearDownModule as _host_runter
_WISSEN = {}


def setUpModule():
    _host_hoch()
    _WISSEN['alt'] = os.environ.get('SEDRA_WISSEN_STANDARD')
    os.environ['SEDRA_WISSEN_STANDARD'] = 'an'      # diese Tests prüfen das Schließen des Wissensspeichers; der Testlauf setzt sonst `aus`


def tearDownModule():
    if _WISSEN.get('alt') is None:
        os.environ.pop('SEDRA_WISSEN_STANDARD', None)
    else:
        os.environ['SEDRA_WISSEN_STANDARD'] = _WISSEN['alt']
    _host_runter()

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('SEDRA_Architecture_v*'))[-1]


class ServiceReadinessTest(unittest.TestCase):
    def test_core_ready_does_not_imply_factory_ready(self):
        view = {
            'state': 'READY',
            'job_supervisor': {'enabled': True, 'counts': {'BUILDING': 2}},
            'model_scheduler': {'enabled': False, 'error': 'config_missing'},
            'wissen': {'enabled': False, 'error': None},
            'sandbox': {'execution_ready': False, 'blockers': ['missing_vm']},
            'permissions': {'available': True},
            'llama_server': {'available': True, 'running': False},
        }
        status = _readiness_from_boot(view)
        self.assertEqual(status['core']['state'], 'READY')
        self.assertEqual(status['services']['job_supervisor']['state'], 'CONFIGURED')
        self.assertEqual(status['services']['model_scheduler']['state'], 'ERROR')
        self.assertEqual(status['services']['sandbox']['state'], 'BLOCKED')
        self.assertEqual(status['services']['llama_server']['state'], 'AVAILABLE_NOT_RUNNING')
        self.assertEqual(status['factory']['state'], 'NOT_EVALUATED')

    def test_configured_is_not_an_end_to_end_guarantee(self):
        result = _readiness_from_boot({'state': 'SAFE_MODE', 'orchestra': {'enabled': True},
                                       'sandbox': {'execution_ready': True, 'blockers': []}})
        self.assertEqual(result['core']['state'], 'SAFE_MODE')
        self.assertEqual(result['services']['orchestra'],
                         {'state': 'CONFIGURED', 'reason': 'execution_not_verified'})
        self.assertEqual(result['services']['sandbox']['state'], 'PREFLIGHT_PASS')
        self.assertEqual(result['factory']['state'], 'NOT_EVALUATED')

    def test_unknown_status_does_not_turn_into_disabled(self):
        result = _readiness_from_boot({'state': 'UNKNOWN'})
        self.assertEqual(result['services']['wissen']['state'], 'UNKNOWN')
        self.assertEqual(result['services']['sandbox']['state'], 'UNKNOWN')

    def test_corrupt_supervisor_records_are_blocked(self):
        result = _readiness_from_boot({'state': 'READY', 'job_supervisor': {'enabled': True, 'corrupt_records': 2}})
        self.assertEqual(result['services']['job_supervisor']['state'], 'BLOCKED')

    def test_llama_status_is_not_confused_with_enabled(self):
        running = _readiness_from_boot({'llama_server': {'running': True, 'available': True}})
        self.assertEqual(running['services']['llama_server']['state'], 'RUNNING_UNVERIFIED')
        missing = _readiness_from_boot({'llama_server': {'running': False, 'available': False}})
        self.assertEqual(missing['services']['llama_server']['state'], 'UNAVAILABLE')
        off = _readiness_from_boot({'llama_server': {'enabled': False}})
        self.assertEqual(off['services']['llama_server']['state'], 'DISABLED')

    def test_summary_has_no_side_effects_on_input(self):
        view = {'state': 'READY', 'sandbox': {'execution_ready': False, 'blockers': ['x']}}
        before = {'state': view['state'], 'sandbox': dict(view['sandbox'])}
        self.assertEqual(_readiness_from_boot(view)['services']['sandbox']['state'], 'BLOCKED')
        self.assertEqual(view, before)


class RuntimeBootstrapTest(unittest.TestCase):
    def test_public_alias_and_boot_compatibility(self):
        self.assertIs(SedraRuntime, SedraRuntime)
        with tempfile.TemporaryDirectory() as tmp:
            rt = SedraRuntime(Path(tmp), ARCH)
            try:
                boot = rt.boot()
                self.assertEqual(boot['state'], 'READY')
                self.assertIn('service_readiness', boot)
                self.assertEqual(boot['service_readiness']['core']['state'], boot['state'])
                self.assertEqual(boot['service_readiness']['factory']['state'], 'NOT_EVALUATED')
            finally:
                rt.close()

    def test_failed_construction_closes_actual_sqlite_wissen(self):
        closed_objects = []
        original_close = WissenSpeicher.schliessen

        def record_close(wissen):
            closed_objects.append(wissen)
            return original_close(wissen)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(WissenSpeicher, 'schliessen', record_close), \
                 patch.object(SedraRuntime, '_configure_context_manager', side_effect=ValueError('simulated_boot_failure')):
                with self.assertRaisesRegex(ValueError, 'simulated_boot_failure'):
                    SedraRuntime(Path(tmp), ARCH)
        self.assertEqual(len(closed_objects), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            closed_objects[0].db.execute('SELECT 1')

    def test_cleanup_error_does_not_mask_original_error(self):
        class FailingWissen:
            def schliessen(self):
                raise RuntimeError('close_failed')

        def raise_after_resource(rt, *args):
            rt.wissen = FailingWissen()
            raise ValueError('primary_boot_error')

        with patch.object(SedraRuntime, '_initialize', raise_after_resource):
            with self.assertRaisesRegex(ValueError, 'primary_boot_error') as caught:
                SedraRuntime(Path('/unused'))
        self.assertTrue(any('RuntimeError' in n for n in caught.exception.__notes__))

    def test_error_before_service_creation_has_no_cleanup_dependency(self):
        def raise_first(_rt, *args):
            raise FileNotFoundError('missing_architecture')

        with patch.object(SedraRuntime, '_initialize', raise_first):
            with self.assertRaisesRegex(FileNotFoundError, 'missing_architecture'):
                SedraRuntime(Path('/unused'))


if __name__ == '__main__':
    unittest.main()
