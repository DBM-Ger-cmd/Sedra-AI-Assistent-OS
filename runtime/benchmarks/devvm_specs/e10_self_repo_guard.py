"""E-10 (coder extension "self repo guard", 2026-10-11): in a self-development run the coder must never rewrite SEDRA's own checkout with git (reset --hard, clean, checkout,
rebase, push --force ...). `self_repo_guard.py` decides from the argument list (and from a shell line) whether a git command is blocked inside a protected folder. Idea from Hermes
tools/self_repo_guard.py (MIT). Pure functions, nothing is executed. SEDRA builds it (model comparison 2026-10-11), Claude only wrote this file, the hidden tests and the
reference (benchmarks/devvm_refs/e10_self_repo_guard). Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for self_repo_guard
Pure Python 3 standard library (posixpath, shlex), no file, process or network access, nothing is executed, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
Paths are POSIX paths ("/" separators); normalise them with posixpath.normpath. A path is inside a root when it equals the root or starts with the root followed by "/".
'''

COMMON = r'''
from self_repo_guard import IMPORTS
P = ["/sedra/runtime", "/sedra/workspace/"]
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
assert check(["git", "reset", "--hard"], "/sedra/runtime", P) == "reset_hard"
assert check(["git", "reset", "--hard", "HEAD~1"], "/sedra/runtime/src/x", P) == "reset_hard"
assert check(["git", "reset", "--merge"], "/sedra/runtime", P) == "reset_hard"
assert check(["git", "reset", "--keep"], "/sedra/runtime", P) == "reset_hard"
assert check(["git", "reset", "HEAD", "a.py"], "/sedra/runtime", P) is None
assert check(["git", "reset", "--hard"], "/tmp/work", P) is None
assert check(["git", "reset", "--hard"], "/sedra/runtimes", P) is None
assert check(["git", "clean", "-fd"], "/sedra/workspace", P) == "clean"
assert check(["git", "clean"], "/sedra/workspace/a", P) == "clean"
assert check(["git", "checkout", "main"], "/sedra/runtime", P) == "checkout"
assert check(["git", "restore", "x.py"], "/sedra/runtime", P) == "restore"
assert check(["git", "switch", "dev"], "/sedra/runtime", P) == "switch"
assert check(["git", "rebase", "-i", "HEAD~3"], "/sedra/runtime", P) == "rebase"
assert check(["git", "filter-branch"], "/sedra/runtime", P) == "history_rewrite"
assert check(["git", "filter-repo"], "/sedra/runtime", P) == "history_rewrite"
assert check(["git", "update-ref", "refs/heads/main", "abc"], "/sedra/runtime", P) == "history_rewrite"
assert check(["git", "push", "-f"], "/sedra/runtime", P) == "push_force"
assert check(["git", "push", "origin", "main", "--force"], "/sedra/runtime", P) == "push_force"
assert check(["git", "push", "--force-with-lease"], "/sedra/runtime", P) == "push_force"
assert check(["git", "push", "origin", "main"], "/sedra/runtime", P) is None
assert check(["git", "commit", "--amend", "-m", "x"], "/sedra/runtime", P) == "commit_amend"
assert check(["git", "commit", "-m", "x"], "/sedra/runtime", P) is None
assert check(["git", "branch", "-D", "old"], "/sedra/runtime", P) == "branch_delete"
assert check(["git", "branch", "-d", "old"], "/sedra/runtime", P) is None
assert check(["git", "stash", "drop"], "/sedra/runtime", P) == "stash_drop"
assert check(["git", "stash", "clear"], "/sedra/runtime", P) == "stash_drop"
assert check(["git", "stash"], "/sedra/runtime", P) is None
assert check(["git", "stash", "pop"], "/sedra/runtime", P) is None
assert check(["git", "status"], "/sedra/runtime", P) is None
assert check(["git", "log", "--oneline"], "/sedra/runtime", P) is None
assert check(["git"], "/sedra/runtime", P) is None
assert check(["git", "--version"], "/sedra/runtime", P) is None
"""

C2 = r"""
assert check(["GIT.EXE", "clean"], "/sedra/runtime", P) == "clean"
assert check(["/usr/bin/git", "clean"], "/sedra/runtime", P) == "clean"
assert check(["C:\\Program Files\\Git\\bin\\git.exe", "clean"], "/sedra/runtime", P) == "clean"
assert check(["gitk", "clean"], "/sedra/runtime", P) is None
assert check(["C:/Tools\\git.exe", "clean"], "/sedra/runtime", P) == "clean"
assert check(["python", "clean"], "/sedra/runtime", P) is None
assert check(["git", "-C", "/sedra/runtime", "reset", "--hard"], "/tmp", P) == "reset_hard"
assert check(["git", "-C", "../sedra/runtime", "clean"], "/x", P) == "clean"
assert check(["git", "-C", "/tmp", "clean"], "/sedra/runtime", P) is None
assert check(["git", "-C", "/sedra", "-C", "runtime", "clean"], "/tmp", P) == "clean"
assert check(["git", "-c", "user.name=x", "clean"], "/sedra/runtime", P) == "clean"
assert check(["git", "--no-pager", "clean"], "/sedra/runtime", P) == "clean"
assert check(["git", "--git-dir=/other/.git", "status"], "/sedra/runtime", P) == "git_dir_override"
assert check(["git", "--work-tree=/x", "status"], "/sedra/runtime", P) == "git_dir_override"
assert check(["git", "--git-dir=/other/.git", "status"], "/tmp", P) is None
assert check(["git", "clean"], "/sedra/runtime/../runtime/./src", P) == "clean"
assert check(["git", "clean"], "/sedra/workspace", P) == "clean"
assert check(["git", "clean"], "/sedra", P) is None
assert check([], "/sedra/runtime", P) is None
assert check("git clean", "/sedra/runtime", P) is None
assert check(["git", 5], "/sedra/runtime", P) is None
args = ["git", "-C", "/sedra/runtime", "clean"]; copy = list(args)
check(args, "/tmp", P); assert args == copy
"""

C3 = r"""
assert check_shell("git status && git reset --hard", "/sedra/runtime", P) == "reset_hard"
assert check_shell("git status ; git clean -fd", "/sedra/runtime", P) == "clean"
assert check_shell("git log || git push --force", "/sedra/runtime", P) == "push_force"
assert check_shell("git status | git rebase main", "/sedra/runtime", P) == "rebase"
assert check_shell("git clean -fd && git reset --hard", "/sedra/runtime", P) == "clean"
assert check_shell("git status && git log", "/sedra/runtime", P) is None
assert check_shell("cd /sedra/runtime && git clean -fd", "/tmp", P) == "clean"
assert check_shell("cd runtime && git checkout x", "/sedra", P) == "checkout"
assert check_shell("cd /tmp && git clean -fd", "/sedra/runtime", P) is None
assert check_shell("git commit -m 'reset --hard'", "/sedra/runtime", P) is None
assert check_shell("git commit -m 'oops", "/sedra/runtime", P) == "unparsable"
assert check_shell("", "/sedra/runtime", P) is None
assert check_shell("echo hi", "/sedra/runtime", P) is None
"""

STAGES = [
    {"name": "check",
     "task": """Create `self_repo_guard.py` (Python 3 standard library only) with `check(argv, cwd, protected) -> str or None`. It says whether a git command must be blocked because it would rewrite a protected folder (SEDRA's own checkout). Nothing is executed.
- argv: the argument list. Return None when argv is not a list, is empty, contains a non-str, or argv[0] is not git: the last path part of argv[0] (after replacing "\\" by "/"), lower-cased, must be "git" or "git.exe".
- cwd: the folder the command runs in (POSIX path). protected: a list of root folders (POSIX paths, maybe with a trailing "/"). Normalise every path with posixpath.normpath. A folder is inside a root when it equals the root or starts with the root followed by "/" ("/sedra/runtimes" is NOT inside "/sedra/runtime").
- Global options come before the subcommand and all start with "-": "-C <path>" changes the folder (posixpath.join with the current folder, then normpath; may repeat); "-c <name=value>" is skipped with its value; an option starting with "--git-dir" or "--work-tree" returns "git_dir_override" when the folder is inside a protected root, else None; any other option is skipped.
- The first argument that does not start with "-" is the subcommand. No subcommand, or a folder outside every protected root: None.
- Blocked subcommands (return value in quotes): clean -> "clean", checkout -> "checkout", restore -> "restore", switch -> "switch", rebase -> "rebase", filter-branch / filter-repo / update-ref -> "history_rewrite"; reset with any of --hard, --merge, --keep among its arguments -> "reset_hard"; push with "-f" or an argument starting with "--force" -> "push_force"; commit with "--amend" -> "commit_amend"; branch with "-D" -> "branch_delete"; stash whose first argument is drop or clear -> "stash_drop". Everything else: None.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. Add `tests/test_self_repo_guard.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e10_1.py": hidden("check", C1 + C2)}},
    {"name": "shell",
     "task": """Add `check_shell(command, cwd, protected) -> str or None` to `self_repo_guard.py`: the same decision for a whole shell line.
- Split the line with shlex.split; when that raises ValueError return "unparsable".
- The words "&&", "||", ";" and "|" (as separate words) separate the line into parts. Check the parts in order with check(part, folder, protected) and return the first reason that is not None; None when no part is blocked (also for an empty line).
- A part that is exactly ["cd", <path>] changes the folder for the parts after it (posixpath.join with the current folder, then normpath). The folder starts as cwd.
Add tests to `tests/test_self_repo_guard.py`.""",
     "hidden": {"hidden_e10_2.py": hidden("check, check_shell", C3)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_self_repo_guard.py` and read `self_repo_guard.py` once more. Make sure no rule is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e10_full.py": hidden("check, check_shell", C1 + C2 + C3)}},
]
