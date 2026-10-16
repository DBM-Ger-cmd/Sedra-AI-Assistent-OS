import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.sandbox_edit import Sandbox, SandboxError, MAX_WRITE_BYTES, parse_action, run_action


class SandboxBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sandbox-test-')
        self.root = Path(self.tmp.name) / 'redesign'
        (self.root / 'shells' / 'cockpit').mkdir(parents=True)
        (self.root / 'shells' / 'cockpit' / 'shell.css').write_text('a{}', encoding='utf-8')
        self.outside = Path(self.tmp.name) / 'live.css'
        self.outside.write_text('live', encoding='utf-8')
        self.sb = Sandbox(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_paths_outside_the_root_are_refused(self):
        for bad in ('../live.css', 'shells/../../live.css', str(self.outside), '/etc/passwd', 'C:/Windows/x.css', '', None):
            with self.subTest(path=bad):
                with self.assertRaises(SandboxError):
                    self.sb.read_file(bad) if bad else self.sb.write_file(bad, 'x')
        self.assertEqual(self.outside.read_text(encoding='utf-8'), 'live', 'the live file is untouched')

    def test_writes_stay_inside_and_are_recorded(self):
        msg = self.sb.write_file('shells/cockpit/new.css', 'b{}')
        self.assertIn('shells/cockpit/new.css', msg)
        self.assertEqual(self.sb.writes, [{'path': 'shells/cockpit/new.css', 'bytes': 3}])

    def test_only_text_types_are_writable_and_size_is_capped(self):
        with self.assertRaises(SandboxError): self.sb.write_file('shells/x.exe', 'MZ')
        with self.assertRaises(SandboxError): self.sb.write_file('shells/x.py', 'print(1)')
        with self.assertRaises(SandboxError): self.sb.write_file('shells/big.css', 'x' * (MAX_WRITE_BYTES + 1))

    def test_a_run_writes_only_its_own_files(self):
        scoped = Sandbox(self.root, allow=['shells/cockpit/shell.css'])
        scoped.write_file('shells/cockpit/shell.css', 'c{}')
        with self.assertRaises(SandboxError): scoped.write_file('shells/cockpit/other.css', 'x{}')
        with self.assertRaises(SandboxError): scoped.write_file('shells/cockpit', 'x{}')
        self.assertEqual(scoped.read_file('shells/cockpit/shell.css'), 'c{}', 'reading the scope is allowed')

    def test_links_out_of_the_root_are_not_followed_for_reading(self):
        # a file name that points at the live tree must not be readable through the sandbox
        target = self.root / 'shells' / 'cockpit' / 'shell.css'
        self.assertEqual(self.sb.read_file('shells/cockpit/shell.css'), 'a{}')
        self.assertTrue(target.resolve().is_relative_to(self.root.resolve()))


class ActionProtocol(unittest.TestCase):
    def test_the_first_json_with_a_tool_is_taken(self):
        text = 'Ich schreibe jetzt. {"tool": "read_file", "args": {"path": "a.css"}} danach mehr'
        self.assertEqual(parse_action(text), ('read_file', {'path': 'a.css'}))

    def test_text_without_a_tool_gives_none(self):
        self.assertIsNone(parse_action('Hallo, hier ist keine Aktion.'))
        self.assertIsNone(parse_action('{"x": 1}'))

    def test_finish_ends_the_loop_and_unknown_tools_are_told(self):
        with tempfile.TemporaryDirectory() as d:
            sb = Sandbox(d)
            self.assertEqual(run_action(sb, 'finish', {'summary': 'fertig'})[1], True)
            self.assertIn('unbekanntes Werkzeug', run_action(sb, 'delete_all', {})[0])
            self.assertTrue(run_action(sb, 'write_file', {'path': '../x.css', 'content': 'a'})[0].startswith('Fehler'))


if __name__ == '__main__':
    unittest.main()
