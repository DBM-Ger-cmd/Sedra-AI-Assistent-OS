import posixpath
import shlex

ALWAYS = {"clean": "clean", "checkout": "checkout", "restore": "restore", "switch": "switch", "rebase": "rebase",
          "filter-branch": "history_rewrite", "filter-repo": "history_rewrite", "update-ref": "history_rewrite"}
SEPARATORS = {"&&", "||", ";", "|"}


def _norm(path):
    return posixpath.normpath(path)


def _inside(path, roots):
    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in (_norm(x) for x in roots))


def _is_git(word):
    name = posixpath.basename(word.replace("\\", "/")).lower()
    return name in ("git", "git.exe")


def _sub_reason(sub, args):
    if sub in ALWAYS:
        return ALWAYS[sub]
    if sub == "reset" and any(a in ("--hard", "--merge", "--keep") for a in args):
        return "reset_hard"
    if sub == "push" and any(a == "-f" or a.startswith("--force") for a in args):
        return "push_force"
    if sub == "commit" and "--amend" in args:
        return "commit_amend"
    if sub == "branch" and "-D" in args:
        return "branch_delete"
    if sub == "stash" and args[:1] and args[0] in ("drop", "clear"):
        return "stash_drop"
    return None


def check(argv, cwd, protected):
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv) or not _is_git(argv[0]):
        return None
    where = _norm(cwd)
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        opt = argv[i]
        if opt == "-C" and i + 1 < len(argv):
            where = _norm(posixpath.join(where, argv[i + 1]))
            i += 2
            continue
        if opt == "-c":
            i += 2
            continue
        if opt.startswith("--git-dir") or opt.startswith("--work-tree"):
            return "git_dir_override" if _inside(where, protected) else None
        i += 1
    if i >= len(argv) or not _inside(where, protected):
        return None
    return _sub_reason(argv[i], argv[i + 1:])


def check_shell(command, cwd, protected):
    try:
        words = shlex.split(command)
    except ValueError:
        return "unparsable"
    part, where = [], _norm(cwd)
    for word in words + [";"]:
        if word in SEPARATORS:
            if len(part) == 2 and part[0] == "cd":
                where = _norm(posixpath.join(where, part[1]))
            reason = check(part, where, protected) if part else None
            if reason:
                return reason
            part = []
        else:
            part.append(word)
    return None
