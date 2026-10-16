import posixpath
import shlex

def check_shell(command, cwd, protected):
    if not isinstance(command, str):
        return None
    
    try:
        argv = shlex.split(command)
    except ValueError:
        return "unparsable"
    
    if not argv:
        return None
    
    parts = []
    current_part = []
    
    for word in argv:
        if word in ("&&", "||", ";", "|"):
            if current_part:
                parts.append(current_part)
            parts.append([word])
            current_part = []
        else:
            current_part.append(word)
    
    if current_part:
        parts.append(current_part)
    
    effective_cwd = cwd
    for part in parts:
        if len(part) == 1 and part[0] in ("&&", "||", ";", "|"):
            continue
        elif len(part) == 2 and part[0] == "cd":
            effective_cwd = posixpath.normpath(posixpath.join(effective_cwd, part[1]))
        else:
            result = check(part, effective_cwd, protected)
            if result is not None:
                return result
    
    return None

def check(argv, cwd, protected):
    if not isinstance(argv, list) or len(argv) == 0:
        return None
    if not all(isinstance(arg, str) for arg in argv):
        return None
    
    basename = argv[0].replace("\\", "/").split("/")[-1]
    if basename.lower() not in ("git", "git.exe"):
        return None
    
    protected = [posixpath.normpath(p) for p in protected]
    
    i = 1
    effective_cwd = cwd
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("-"):
            if arg.startswith("--git-dir") or arg.startswith("--work-tree"):
                effective_cwd = posixpath.normpath(effective_cwd)
                for protected_root in protected:
                    if effective_cwd == protected_root or effective_cwd.startswith(protected_root + "/"):
                        return "git_dir_override"
                return None
            elif arg == "-C":
                if i + 1 < len(argv):
                    effective_cwd = posixpath.normpath(posixpath.join(effective_cwd, argv[i + 1]))
                    i += 2
                else:
                    i += 1
            elif arg == "-c":
                if i + 1 < len(argv):
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        else:
            break
    
    if i >= len(argv):
        return None
    
    subcommand = argv[i]
    
    effective_cwd = posixpath.normpath(effective_cwd)
    is_protected = any(
        effective_cwd == root or effective_cwd.startswith(root + "/")
        for root in protected
    )
    
    if not is_protected:
        return None
    
    if subcommand == "clean":
        return "clean"
    elif subcommand == "checkout":
        return "checkout"
    elif subcommand == "restore":
        return "restore"
    elif subcommand == "switch":
        return "switch"
    elif subcommand == "rebase":
        return "rebase"
    elif subcommand in ("filter-branch", "filter-repo", "update-ref"):
        return "history_rewrite"
    elif subcommand == "reset":
        for j in range(i + 1, len(argv)):
            if argv[j] in ("--hard", "--merge", "--keep"):
                return "reset_hard"
    elif subcommand == "push":
        for j in range(i + 1, len(argv)):
            if argv[j] == "-f" or argv[j].startswith("--force"):
                return "push_force"
    elif subcommand == "commit":
        for j in range(i + 1, len(argv)):
            if argv[j] == "--amend":
                return "commit_amend"
    elif subcommand == "branch":
        for j in range(i + 1, len(argv)):
            if argv[j] == "-D":
                return "branch_delete"
    elif subcommand == "stash":
        for j in range(i + 1, len(argv)):
            if argv[j] in ("drop", "clear"):
                return "stash_drop"
    
    return None