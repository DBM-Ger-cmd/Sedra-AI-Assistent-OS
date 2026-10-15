"""Data of the Guppy meter window: how much code GUPPI and Claude have written. Glue around the pure modules code_collector (records) and code_meter (cards, weekly grid).

Claude's lines come from `git log --numstat` of the project folder (docs, archive, workspace and engines are left out, and so are the files that GUPPI built and Claude only copied over) plus the work of today that is not committed yet (changed tracked files and new files); GUPPI's lines come from the newest
build candidate of every spec under runtime_data/devvm_candidates (code files without tests). Both are approximations, and the view says so. Read-only: nothing is written, nothing is started apart from `git log`."""
import datetime
import os
import subprocess

from .code_collector import candidate_records, records_from_numstat
from .code_meter import cards, daily_totals, heatmap
from .token_records import token_records
from .usage_meter import token_view

IGNORED_PREFIXES = ("archiv/", "docs/", "workspace/", "engines/", ".venv/")
GUPPI_BUILT = tuple("runtime/src/guppi_runtime/agent_manager/" + name for name in ("agent_contracts.py", "agent_registry.py", "agent_import.py", "agent_matcher.py", "code_meter.py"))
GENERIC_NAMES = ("util.py", "utils.py", "main.py", "app.py")
RANGES = (("all", None), ("30", 30), ("7", 7), ("today", 1))


def git_log(repo_root, run=subprocess.run):
    try:
        done = run(["git", "-C", str(repo_root), "log", "--numstat", "--no-merges", "--pretty=format:@%ad", "--date=short"], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def working_tree_log(repo_root, today, run=subprocess.run):
    """Today's work that is not committed yet, in the format of `git log --numstat` with today's date as the header: changed tracked files (`git diff HEAD --numstat`) and new files (counted by their non-empty lines)."""
    def git(*args):
        try:
            done = run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            return ""
        return done.stdout if done.returncode == 0 else ""
    lines = [f"@{today}"] + [line for line in git("diff", "HEAD", "--numstat").splitlines() if line.strip()]
    for path in git("ls-files", "--others", "--exclude-standard").splitlines():
        try:
            with open(os.path.join(str(repo_root), path), encoding="utf-8") as handle:
                count = sum(1 for line in handle if line.strip())
        except (OSError, UnicodeDecodeError):
            continue
        lines.append(f"{count}\t0\t{path}")
    return "\n".join(lines) + "\n"


def _is_code(relative):
    name = os.path.basename(relative)
    return name.endswith(".py") and not name.startswith(("test_", "acceptance_")) and not relative.replace("\\", "/").startswith("tests/")


def candidate_entries(project_root):
    """[{"spec", "attempt", "lines"}] for every candidate folder: the number of lines of its code files (no tests, no acceptance scripts)."""
    root = os.path.join(str(project_root), "runtime_data", "devvm_candidates")
    entries = []
    try:
        specs = sorted(os.listdir(root))
    except OSError:
        return entries
    for spec in specs:
        try:
            attempts = sorted(os.listdir(os.path.join(root, spec)))
        except OSError:
            continue
        for attempt in attempts:
            folder, lines = os.path.join(root, spec, attempt), 0
            for base, _, files in os.walk(folder):
                for name in files:
                    relative = os.path.relpath(os.path.join(base, name), folder)
                    if _is_code(relative):
                        try:
                            with open(os.path.join(base, name), encoding="utf-8", errors="replace") as handle:
                                lines += sum(1 for line in handle if line.strip())
                        except OSError:
                            pass
            entries.append({"spec": spec, "attempt": attempt, "lines": lines})
    return entries


def built_paths(repo_root, project_root):
    """Repo paths under runtime/src that carry the name of a code file GUPPI built (any folder of runtime_data/devvm_candidates): they count for GUPPI, not for Claude, also after Claude's fixes. No list to maintain."""
    names = set()
    root = os.path.join(str(project_root), "runtime_data", "devvm_candidates")
    for base, _, files in os.walk(root):
        for name in files:
            if _is_code(name) and not name.startswith("__") and name not in GENERIC_NAMES:
                names.add(name)
    found = []
    src = os.path.join(str(repo_root), "runtime", "src")
    for base, _, files in os.walk(src):
        for name in files:
            if name in names:
                found.append(os.path.relpath(os.path.join(base, name), str(repo_root)).replace("\\", "/"))
    return tuple(found)


def _since(daily, today, days):
    if days is None:
        return daily
    first = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days - 1)).isoformat()
    return {day: value for day, value in daily.items() if first <= day <= today}


def meter_view(repo_root, project_root, today=None, weeks=26, run=subprocess.run):
    today = today or datetime.date.today().isoformat()
    text = git_log(repo_root, run)
    pending = working_tree_log(repo_root, today, run) if text is not None else ""
    entries = candidate_entries(project_root)
    ignore = IGNORED_PREFIXES + GUPPI_BUILT + built_paths(repo_root, project_root)
    records = records_from_numstat(text, ignore_prefixes=ignore) + records_from_numstat(pending, ignore_prefixes=ignore) + candidate_records(entries)
    daily = daily_totals(records)
    return {"today": today, "weeks": weeks, "grid": heatmap(daily, today, weeks), "ranges": {name: cards(_since(daily, today, days), today) for name, days in RANGES},
            "tokens": token_view(token_records(project_root), today),
            "sources": {"git": text is not None, "candidates": len(entries)},
            "note": "Näherung: Claudes Zeilen aus git (ohne Doku und Archiv), GUPPIs Zeilen aus dem jeweils neuesten Bauversuch je Spec (nur Code, ohne Tests)."}
