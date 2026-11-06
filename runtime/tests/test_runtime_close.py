"""F0: explicit, safe runtime teardown and resource ownership."""
from __future__ import annotations
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from sedra_runtime.runtime import SedraRuntime, SedraRuntime
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


class RuntimeTeardown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = SedraRuntime(Path(self.tmp.name), ARCH)

    def tearDown(self):
        try:
            self.rt.close()
        finally:
            self.tmp.cleanup()

    def test_sedra_alias_exposes_same_shutdown_contract(self):
        self.assertIs(SedraRuntime, SedraRuntime)
        self.assertTrue(callable(self.rt.close))

    def test_closes_wissen_database_twice_without_error(self):
        wissen = self.rt.wissen
        self.assertIsNotNone(wissen)
        wissen.db.execute('SELECT 1')
        self.rt.close()
        self.rt.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            wissen.db.execute('SELECT 1')

    def test_orchestra_is_closed_when_present(self):
        dummy = Mock()
        self.rt.orchestra = dummy
        self.rt.close()
        self.rt.close()
        dummy.close.assert_called_once_with()

    def test_other_services_close_even_if_one_fails_then_retry_only_failed(self):
        dummy = Mock()
        dummy.close.side_effect = RuntimeError('simulated failure')
        self.rt.orchestra = dummy
        wissen = self.rt.wissen
        with self.assertRaisesRegex(RuntimeError, 'runtime_close_failed:orchestra'):
            self.rt.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            wissen.db.execute('SELECT 1')
        dummy.close.side_effect = None
        self.rt.close()
        self.rt.close()
        self.assertEqual(dummy.close.call_count, 2)


class UixTeardown(unittest.TestCase):
    def _hub(self):
        # The shutdown path itself is tested without opening a browser or port.
        from sedra_runtime.uix_server import UIXHub
        hub = UIXHub.__new__(UIXHub)
        hub.poller = Mock()
        hub.runtime = Mock()
        hub._scheduler = Mock(return_value=None)
        hub.gpu_token = None
        return hub

    def test_uix_delegates_to_one_runtime_close(self):
        hub = self._hub()
        hub.close()
        hub.poller.stop.assert_called_once_with()
        hub.runtime.close.assert_called_once_with()

    def test_uix_logs_runtime_close_failure_without_leaking_exception(self):
        hub = self._hub()
        hub.runtime.close.side_effect = RuntimeError('runtime_close_failed:wissen')
        hub.close()
        hub.runtime.audit.append.assert_called_once()
        event, = hub.runtime.audit.append.call_args.args
        self.assertEqual(event, 'RUNTIME_SHUTDOWN_ERROR')


if __name__ == '__main__':
    unittest.main()
