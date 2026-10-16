import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime import uix_start


class StandardShellTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='uix-standard-')
        self.root = Path(self.tmp.name)
        (self.root / 'local_config').mkdir()
        (self.root / 'local_config' / 'uix.yaml').write_text('uix:\n  shell: minimal\n  tools:\n    disabled: []\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_the_default_and_keeps_other_keys(self):
        shell = uix_start.list_shells()[0][0]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(uix_start.set_standard_shell(self.root, shell), 0)
        data = yaml.safe_load((self.root / 'local_config' / 'uix.yaml').read_text(encoding='utf-8'))
        self.assertEqual(data['uix']['shell'], shell)
        self.assertEqual(data['uix']['tools'], {'disabled': []})

    def test_unknown_shell_is_refused_and_file_stays(self):
        before = (self.root / 'local_config' / 'uix.yaml').read_text(encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(uix_start.set_standard_shell(self.root, 'gibt-es-nicht'), 2)
        self.assertEqual((self.root / 'local_config' / 'uix.yaml').read_text(encoding='utf-8'), before)


if __name__ == '__main__':
    unittest.main()
