"""F0-03: CLI/One-Sedra lifecycle regression tests; no hardware or browser."""
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sedra_runtime import cli, uix_server
from sedra_runtime.desk.events import Poller


class CliRuntimeLifecycle(unittest.TestCase):
    def test_runtime_command_closes_on_success(self):
        rt = Mock()
        rt.boot.return_value = {'state': 'READY'}
        with patch.object(cli, 'runtime_from_args', return_value=rt), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['doctor']), 0)
        rt.boot.assert_called_once_with()
        rt.close.assert_called_once_with()

    def test_runtime_command_closes_when_operation_raises(self):
        rt = Mock()
        rt.brain.run.side_effect = ValueError('simulated operation failure')
        with patch.object(cli, 'runtime_from_args', return_value=rt):
            with self.assertRaisesRegex(ValueError, 'simulated operation failure'):
                cli.main(['run', 'mission-test'])
        rt.close.assert_called_once_with()

    def test_desk_commands_do_not_create_a_second_runtime(self):
        with patch.object(cli, 'runtime_from_args', side_effect=AssertionError('must not open runtime')):
            with patch.object(cli, 'desk_command', return_value=0) as desk:
                self.assertEqual(cli.main(['objects', 'task']), 0)
                desk.assert_called_once()


class OneSedraServerLifecycle(unittest.TestCase):
    def run_fake(self, *, choose=None, make=None, start=None, serve=None, close=None):
        hub = Mock()
        server = Mock()
        if start is not None:
            hub.poller.start.side_effect = start
        if serve is not None:
            server.serve_forever.side_effect = serve
        if close is not None:
            hub.close.side_effect = close
        choose_shell = Mock(side_effect=choose) if isinstance(choose, BaseException) else Mock(return_value='harness')
        make_server = Mock(side_effect=make) if isinstance(make, BaseException) else Mock(return_value=(server, 'http://127.0.0.1:0'))
        with patch.object(uix_server, 'UIXHub', return_value=hub), \
             patch.object(uix_server, 'choose_start_shell', choose_shell), \
             patch.object(uix_server, 'make_server', make_server), \
             contextlib.redirect_stdout(io.StringIO()):
            if any(isinstance(x, BaseException) for x in (make, start, serve, close)):
                try:
                    result = uix_server.serve(Path('/fake'), Path('/fake-arch'))
                except Exception as exc:
                    result = exc
            else:
                result = uix_server.serve(Path('/fake'), Path('/fake-arch'))
        return hub, server, make_server, result

    def test_normal_exit_closes_hub_and_socket(self):
        hub, server, _, result = self.run_fake()
        self.assertEqual(result, 0)
        hub.poller.start.assert_called_once_with()
        server.serve_forever.assert_called_once_with(poll_interval=0.25)
        hub.close.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_unknown_shell_closes_hub_before_server_exists(self):
        hub, server, make_server, result = self.run_fake(choose=ValueError('unknown shell'))
        self.assertEqual(result, 4)
        hub.close.assert_called_once_with()
        make_server.assert_not_called()
        server.server_close.assert_not_called()

    def test_server_creation_failure_still_closes_hub(self):
        hub, server, _, result = self.run_fake(make=OSError('bind failure'))
        self.assertIsInstance(result, OSError)
        hub.close.assert_called_once_with()
        server.server_close.assert_not_called()

    def test_poller_start_failure_closes_hub_and_socket(self):
        hub, server, _, result = self.run_fake(start=RuntimeError('poller failure'))
        self.assertIsInstance(result, RuntimeError)
        hub.close.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_serve_forever_failure_closes_hub_and_socket(self):
        hub, server, _, result = self.run_fake(serve=RuntimeError('server failure'))
        self.assertIsInstance(result, RuntimeError)
        hub.close.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_server_socket_closes_even_if_hub_close_fails(self):
        hub, server, _, result = self.run_fake(close=RuntimeError('cleanup failure'))
        self.assertIsInstance(result, RuntimeError)
        server.server_close.assert_called_once_with()

    def test_keyboard_interrupt_still_closes(self):
        hub, server, _, result = self.run_fake(serve=KeyboardInterrupt())
        self.assertEqual(result, 0)
        hub.close.assert_called_once_with()
        server.server_close.assert_called_once_with()


class DesktopEarlyInitAndPoller(unittest.TestCase):
    def test_failed_hub_boot_closes_runtime(self):
        rt = Mock()
        rt.boot.side_effect = RuntimeError('boot failed')
        with patch.object(uix_server, 'SedraRuntime', return_value=rt):
            with self.assertRaisesRegex(RuntimeError, 'boot failed'):
                uix_server.UIXHub(Path('/fake'), Path('/fake-arch'))
        rt.close.assert_called_once_with()

    def test_poller_stop_does_not_join_unstarted_thread(self):
        # The first tick can fail at its publish stage before Thread.start().
        stream = Mock()
        stream.publish.side_effect = RuntimeError('failed first publish')
        def bad_snapshot():
            raise RuntimeError('snapshot unavailable')
        poller = Poller(None, stream, snapshot=bad_snapshot)
        with self.assertRaisesRegex(RuntimeError, 'failed first publish'):
            poller.start()
        poller.stop()
        self.assertIsNone(poller._thread)


if __name__ == '__main__':
    unittest.main()
