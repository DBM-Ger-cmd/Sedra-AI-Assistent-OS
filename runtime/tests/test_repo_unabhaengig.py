"""repo_unabhaengig.py (U2-13): ein verknüpfter Worktree bekommt ein eigenes Repository. Nur mit synthetischen Repositories im Temp-Ordner; A1 und der Hub werden nicht berührt."""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import repo_unabhaengig as ru  # noqa: E402


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert done.returncode == 0, (args, done.stderr)
    return done.stdout.strip()


def rmtree(path):
    def fix(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=fix)


class Unabhaengig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="repo-unabh-")
        self.addCleanup(lambda: rmtree(self.tmp.name))
        root = Path(self.tmp.name)
        self.hub, self.a1, self.bundle = root / "hub", root / "a1", root / "archiv" / "a1.bundle"
        self.hub.mkdir()
        git(self.hub, "init", "-q", "-b", "main")
        for k, v in (("user.name", "T"), ("user.email", "t@example.invalid"), ("core.autocrlf", "true"), ("remote.origin.url", "https://example.invalid/x.git"),
                     ("remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"), ("branch.main.remote", "origin"), ("branch.main.merge", "refs/heads/main")):
            git(self.hub, "config", k, v)
        (self.hub / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.hub, "add", "."); git(self.hub, "commit", "-qm", "eins")
        git(self.hub, "tag", "v1")
        git(self.hub, "branch", "nur-lokal"); git(self.hub, "checkout", "-q", "nur-lokal")
        (self.hub / "b.txt").write_text("b\n", encoding="utf-8"); git(self.hub, "add", "."); git(self.hub, "commit", "-qm", "zwei"); git(self.hub, "checkout", "-q", "main")
        git(self.hub, "update-ref", "refs/remotes/origin/main", git(self.hub, "rev-parse", "main"))
        git(self.hub, "worktree", "add", "-q", str(self.a1), "-b", "arbeit")
        (self.a1 / "c.txt").write_text("c\n", encoding="utf-8"); git(self.a1, "add", "."); git(self.a1, "commit", "-qm", "drei")

    def go(self, *extra):
        return ru.main(["--repo", str(self.a1), "--bundle", str(self.bundle), "--no-process-check", *extra])

    def test_dry_run_changes_nothing(self):
        self.assertEqual(self.go(), 0)
        self.assertTrue((self.a1 / ".git").is_file())
        self.assertFalse((self.a1 / ".git.neu").exists())
        self.assertFalse(self.bundle.exists())

    def test_go_makes_an_independent_repository_with_all_refs(self):
        before_refs = ru.refs(self.a1)
        head = git(self.a1, "rev-parse", "HEAD")
        self.assertEqual(self.go("--go"), 0)
        self.assertTrue((self.a1 / ".git").is_dir())
        self.assertTrue((self.a1 / ".git" / "hub-link").is_file())
        self.assertFalse((self.a1 / ".git.hub-link").exists(), "keine Zusatzdatei im Arbeitsordner")
        self.assertEqual(git(self.a1, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.a1, "symbolic-ref", "--short", "HEAD"), "arbeit")
        self.assertEqual(git(self.a1, "status", "--short"), "")
        after = ru.refs(self.a1)
        for name, sha in before_refs.items():
            self.assertEqual(after.get(name), sha, name)
        self.assertIn("refs/tags/v1", after)
        self.assertIn("refs/heads/nur-lokal", after)
        self.assertEqual(len(git(self.a1, "worktree", "list").splitlines()), 1)
        self.assertEqual(git(self.a1, "config", "remote.origin.url"), "https://example.invalid/x.git")
        self.assertEqual(git(self.a1, "config", "branch.main.merge"), "refs/heads/main")
        self.assertEqual(git(self.a1, "config", "core.autocrlf"), "true")
        self.assertTrue(self.bundle.is_file())

    def test_the_hub_can_be_deleted_afterwards(self):
        self.assertEqual(self.go("--go"), 0)
        rmtree(self.hub)
        self.assertIn("drei", git(self.a1, "log", "--oneline"))
        self.assertEqual(git(self.a1, "status", "--short"), "")
        git(self.a1, "checkout", "-q", "nur-lokal")
        self.assertTrue((self.a1 / "b.txt").exists())

    def test_a_dirty_tree_is_refused_and_nothing_changes(self):
        (self.a1 / "c.txt").write_text("geändert\n", encoding="utf-8")
        self.assertEqual(self.go("--go"), 2)
        self.assertTrue((self.a1 / ".git").is_file())
        self.assertFalse((self.a1 / ".git.neu").exists())

    def test_rollback_restores_the_link(self):
        self.assertEqual(self.go("--go"), 0)
        self.assertEqual(ru.main(["--repo", str(self.a1), "--rollback"]), 0)
        self.assertTrue((self.a1 / ".git").is_file())
        self.assertEqual(git(self.a1, "status", "--short"), "")
        self.assertEqual(git(self.a1, "symbolic-ref", "--short", "HEAD"), "arbeit")

    def test_running_twice_is_refused(self):
        self.assertEqual(self.go("--go"), 0)
        self.assertEqual(self.go("--go"), 2)


if __name__ == "__main__":
    unittest.main()
