import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from guppi_runtime.devenv.devvm import DevWorkspace
from guppi_runtime.sandbox.broker import SandboxBroker
from guppi_runtime.tools.base import ToolPermissionError, ToolValidationError

RUNTIME = Path(__file__).resolve().parents[1]
POLICY = {'max_files': 6, 'max_file_bytes': 1000, 'max_input_bytes': 3000}


class Audit:
    def __init__(self): self.events = []
    def append(self, event, **kw): self.events.append((event, kw.get('component'), kw.get('mission_id'), kw.get('payload')))


class DevCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.audit = Audit()
        self.ws = DevWorkspace(self.root, 'M-TEST0001', policy=dict(POLICY), audit=self.audit); self.ws.create()


class FilesTests(DevCase):
    def test_nested_folders_are_created_when_needed_and_everything_is_listed(self):
        self.ws.write('pkg/sub/mod.py', 'x = 1\n'); self.ws.write('README.md', '# hi\n'); self.ws.mkdir('docs/empty')
        self.assertEqual(self.ws.read('pkg/sub/mod.py'), 'x = 1\n')
        self.assertEqual(self.ws.tree(), ['README.md', 'pkg/sub/mod.py'])
        self.assertEqual([(e['name'], e['type']) for e in self.ws.list()], [('docs', 'dir'), ('pkg', 'dir'), ('README.md', 'file')])
        self.assertEqual(self.ws.search('X = 1'), [{'path': 'pkg/sub/mod.py', 'line': 1, 'text': 'x = 1'}])
        self.assertEqual(self.ws.source, 'devvm/M-TEST0001/repo/work')

    def test_the_brokers_path_rules_hold_for_every_operation(self):
        for bad in ('.hidden.py', '../x.py', '/abs.py', 'a\\b.py', 'sub/.git/config', 'prog.exe', 'con.py', 'token.py', 'a/b/c/d/e/f/g/h/i.py', '', 'x' * 300 + '.py'):
            with self.assertRaises(ToolValidationError, msg=bad): self.ws.write(bad, 'x')
        self.ws.write('a.py', 'x')
        for bad in ('../out.py', '.git/x.py'):
            with self.assertRaises((ToolValidationError, ToolPermissionError), msg=bad): self.ws.move('a.py', bad)
        self.assertEqual(self.ws.tree(), ['a.py'])

    def test_limits_follow_the_vm_input_limits(self):
        with self.assertRaises(ToolValidationError): self.ws.write('big.py', 'x' * 1001)
        for i in range(6): self.ws.write(f'f{i}.py', 'x')
        with self.assertRaises(ToolValidationError): self.ws.write('f6.py', 'x')                     # 7th file
        self.ws.write('f0.py', 'y' * 900)                                                            # rewriting an existing one is fine
        for i in range(1, 3): self.ws.write(f'f{i}.py', 'z' * 900)                                    # 2700 bytes plus three small files
        with self.assertRaises(ToolValidationError): self.ws.write('f3.py', 'z' * 900)               # total of 3000 bytes exceeded
        self.assertEqual(self.ws.usage()['files'], 6)

    def test_move_delete_and_the_workspace_itself_is_protected(self):
        self.ws.write('a.py', 'x'); self.ws.write('d/b.py', 'y')
        self.ws.move('a.py', 'n/a2.py'); self.assertEqual(self.ws.tree(), ['d/b.py', 'n/a2.py'])
        with self.assertRaises(ToolValidationError): self.ws.move('n/a2.py', 'd/b.py')              # destination exists
        with self.assertRaises(ToolValidationError): self.ws.delete('d')                             # not empty
        self.ws.delete('d/b.py'); self.ws.delete('d')
        for bad in ('', '..', '.'):
            with self.assertRaises((ToolValidationError, ToolPermissionError), msg=repr(bad)): self.ws.delete(bad)
        self.assertTrue(self.ws.work.is_dir())

    def test_symlinks_are_refused(self):
        self.ws.write('a.py', 'x')
        try: (self.ws.work / 'link.py').symlink_to(self.root)
        except OSError: self.skipTest('no symlink right on this host')
        with self.assertRaises(ToolPermissionError): self.ws.read('link.py')

    def test_every_change_is_audited_with_the_mission(self):
        self.ws.write('a.py', 'x'); self.ws.mkdir('d'); self.ws.move('a.py', 'd/a.py'); self.ws.delete('d/a.py')
        self.assertEqual([e[0] for e in self.audit.events], ['DEVVM_CREATED', 'DEVVM_WRITE', 'DEVVM_MKDIR', 'DEVVM_MOVE', 'DEVVM_DELETE'])
        self.assertTrue(all(e[1] == 'devvm' and e[2] == 'M-TEST0001' for e in self.audit.events))

    def test_bad_mission_ids_and_double_create_are_refused(self):
        for bad in ('', '../x', 'a b', 'x' * 70, None):
            with self.assertRaises(ToolValidationError, msg=str(bad)): DevWorkspace(self.root, bad, policy=POLICY)
        with self.assertRaises(ToolValidationError): self.ws.create()


class WriteRobustnessTests(DevCase):
    def test_a_rename_that_windows_refuses_for_a_moment_is_retried(self):
        import os
        real, fails = os.replace, [2]
        def flaky(src, dst):
            if fails[0]: fails[0] -= 1; raise PermissionError('[WinError 5] Zugriff verweigert')
            return real(src, dst)
        with patch('guppi_runtime.devenv.devvm.os.replace', side_effect=flaky): self.ws.write('a.py', 'x = 1\n')
        self.assertEqual(self.ws.read('a.py'), 'x = 1\n'); self.assertEqual(fails[0], 0)
        self.assertEqual(list(self.ws.work.glob('*.tmp-write')), [])

    def test_when_it_never_works_nothing_is_left_behind_and_the_error_is_raised(self):
        with patch('guppi_runtime.devenv.devvm.os.replace', side_effect=PermissionError('gesperrt')), patch('guppi_runtime.devenv.devvm.time.sleep'):
            with self.assertRaises(PermissionError): self.ws.write('a.py', 'x')
        self.assertEqual(list(self.ws.work.rglob('*')), [])                                           # no half-written helper file: the VM would refuse the folder
        self.assertEqual(self.ws.tree(), [])

    def test_a_stale_helper_file_is_not_part_of_the_workspace(self):
        self.ws.write('a.py', 'x'); (self.ws.work / 'b.py.tmp-write').write_text('half')
        self.assertEqual(self.ws.tree(), ['a.py']); self.assertEqual(self.ws.usage()['files'], 1)


class GitTests(DevCase):
    def test_commit_status_diff_log_and_restore(self):
        self.assertEqual(self.ws.log(), []); self.ws.write('a.py', 'one\n'); self.ws.write('d/b.py', 'two\n')
        self.assertEqual(self.ws.status(), {'added': ['a.py', 'd/b.py'], 'modified': [], 'deleted': []})
        first = self.ws.commit('first version'); self.assertRegex(first, r'^[0-9a-f]{40}$')
        with self.assertRaises(ToolValidationError): self.ws.commit('again')                          # nothing to commit
        self.ws.write('a.py', 'one\nmore\n'); self.ws.delete('d/b.py'); self.ws.write('c.py', 'new\n')
        self.assertEqual(self.ws.status(), {'added': ['c.py'], 'modified': ['a.py'], 'deleted': ['d/b.py']})
        diff = self.ws.diff()
        self.assertIn('+more', diff); self.assertIn('--- a/d/b.py', diff); self.assertIn('+++ b/c.py', diff)
        self.assertIn('+more', self.ws.diff('a.py')); self.assertNotIn('c.py', self.ws.diff('a.py'))
        second = self.ws.commit('second version')
        self.assertEqual([e['message'] for e in self.ws.log()], ['second version', 'first version'])
        self.assertEqual(self.ws.log(1)[0]['commit'], second)
        self.assertEqual(self.ws.status(), {'added': [], 'modified': [], 'deleted': []})
        restored = self.ws.restore(first)
        self.assertEqual(restored, ['a.py', 'd/b.py']); self.assertEqual(self.ws.tree(), ['a.py', 'd/b.py']); self.assertEqual(self.ws.read('a.py'), 'one\n')
        self.assertEqual(self.ws.status(), {'added': ['d/b.py'], 'modified': ['a.py'], 'deleted': ['c.py']})   # like `git checkout <commit> -- .`: HEAD stays, the restore is a change
        third = self.ws.commit('back to the first version')
        self.assertEqual([e['message'] for e in self.ws.log()], ['back to the first version', 'second version', 'first version'])
        self.assertEqual(self.ws.status(), {'added': [], 'modified': [], 'deleted': []}); self.assertNotEqual(third, first)
        for bad in ('abc', '0' * 40, None):
            with self.assertRaises(ToolValidationError, msg=str(bad)): self.ws.restore(bad)

    def test_a_commit_with_a_path_outside_work_leaves_the_workspace_untouched(self):
        self.ws.write('a.py', 'one\n'); self.ws.commit('first')
        (self.ws.repo_path / 'evil.txt').write_text('x', encoding='utf-8')
        repo = self.ws._repo()
        try:
            tree = repo.get_worktree(); tree.stage(['evil.txt']); bad = tree.commit(message=b'bad', committer=b'T <t@t>', author=b'T <t@t>', no_verify=True).decode('ascii')
        finally: repo.close()
        self.ws.write('b.py', 'two\n')
        with self.assertRaises(ToolValidationError): self.ws.restore(bad)
        self.assertEqual(self.ws.tree(), ['a.py', 'b.py'])          # nothing was removed before the bad path was found

    def test_git_hooks_never_run_on_the_host(self):
        self.ws.write('a.py', 'x\n')
        hooks = self.ws.repo_path / '.git' / 'hooks'; hooks.mkdir(parents=True, exist_ok=True)
        for name in ('pre-commit', 'commit-msg', 'post-commit'): (hooks / name).write_text('#!/bin/sh\ntouch ran-' + name + '\n')
        with patch('dulwich.hooks.ShellHook.execute', side_effect=AssertionError('a shell hook was executed')):
            self.ws.commit('with hooks lying around')
        self.assertEqual(self.ws.log()[0]['message'], 'with hooks lying around')
        repo = self.ws._repo(); self.assertEqual(repo.hooks, {}); repo.close()

    def test_git_data_stays_out_of_the_vm_source_and_the_broker_accepts_the_workspace(self):
        self.ws.write('code.py', 'x = 1\n'); self.ws.write('test_code.py', 'import code\n'); self.ws.commit('v1')
        broker = SandboxBroker(self.root, self.root / 'sandbox-data', RUNTIME / 'config' / 'sandbox.yaml', None, None)
        plan = self.ws.vm_preview(broker, [['python3', '-m', 'unittest', 'discover']], exports=['code.py'])
        self.assertEqual(plan['request']['source'], 'devvm/M-TEST0001/repo/work')
        self.assertEqual([f['path'] for f in plan['files']], ['code.py', 'test_code.py'])           # no .git, nothing hidden
        self.assertNotIn('export_dirs', plan['request'])
        with self.assertRaises(ToolValidationError) as ctx: self.ws.vm_preview(broker, [['python3', 'x']], export_dirs=['out'])
        self.assertIn('export_dirs_disabled_by_policy', str(ctx.exception))                          # the Captain's switch is off

    def test_destroy_removes_only_this_missions_folder(self):
        other = DevWorkspace(self.root, 'M-OTHER001', policy=POLICY); other.create(); self.ws.write('a.py', 'x'); self.ws.commit('x')
        self.ws.destroy()
        self.assertFalse(self.ws.repo_path.parent.exists()); self.assertTrue(other.work.is_dir())


if __name__ == '__main__':
    unittest.main()
