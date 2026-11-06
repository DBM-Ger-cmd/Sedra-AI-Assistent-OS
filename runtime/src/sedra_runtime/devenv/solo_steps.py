"""Helpers of the step plan of the solo mode (Captain 2026-10-10): the planner cuts a long task into steps, the developer builds ONE step per fresh, short conversation.

What goes into a step (so that the planner cannot lose a requirement by rewording it):
  - the task is cut into numbered units; the planner says which units belong to which step, and the developer gets exactly these units WORD FOR WORD (units no step claimed go to EVERY step: general rules such as the style);
  - the interface of every step (names, arguments, results), so that the parts fit together;
  - one line from each earlier step (its hand-in summary);
  - a map of the workspace (every class and function with its line), so that he does not have to open files to find his way.
Option checks: `syntax_problems` (a Python file that does not parse after a step) for the option --step-syntax-check.
"""
import ast
import re

from ..devenv.devvm_tools import outline

UNIT_CHARS = 450
MAP_CHARS = 3000

SENTENCE = re.compile(r'(?<=[.;])\s+(?=[A-Z`"(\[{<])')


def number_task(task):
    """The task as a list of units (a line, or a run of sentences of a long line, at most about UNIT_CHARS characters). The text is never changed, only cut at line ends and after a period or semicolon."""
    units = []
    for line in str(task).splitlines():
        line = line.strip()
        if not line: continue
        if len(line) <= UNIT_CHARS: units.append(line); continue
        current = ""
        for part in SENTENCE.split(line):
            if current and len(current) + len(part) + 1 > UNIT_CHARS: units.append(current); current = part
            else: current = (current + " " + part).strip()
        if current: units.append(current)
    return units


def numbered(units):
    return "\n".join(f"[{i}] {u}" for i, u in enumerate(units, 1))


def extract_for(step, steps, units):
    """The units of one step, in the order of the task: its own units plus every unit that no step claimed. A step without valid unit numbers gets the whole task (nothing is lost)."""
    count = len(units)
    claimed = set()
    for s in steps: claimed |= {k for k in (s.get("lines") or []) if isinstance(k, int) and 1 <= k <= count}
    own = {k for k in (step.get("lines") or []) if isinstance(k, int) and 1 <= k <= count}
    chosen = sorted(own | (set(range(1, count + 1)) - claimed)) if own else list(range(1, count + 1))
    return "\n".join(units[k - 1] for k in chosen)


def workspace_map(ws, limit=MAP_CHARS):
    """Every Python file of the workspace root (not the check scripts) with its classes and functions and their lines; empty for an empty workspace."""
    parts = []
    for row in ws.list(""):
        name = row["name"]
        if row["type"] != "file" or not name.endswith(".py") or name.startswith("check_"): continue
        try: rows = outline(ws.read(name)).splitlines()
        except Exception: continue
        parts.append(f"{name} ({rows[0]})\n" + "\n".join(rows[1:]))
    text = "\n".join(parts)
    return text if len(text) <= limit else text[:limit] + "\n[...map cut...]"


def syntax_problems(ws):
    """[(file, line, message)] of the Python files of the workspace root that do not parse."""
    found = []
    for row in ws.list(""):
        name = row["name"]
        if row["type"] != "file" or not name.endswith(".py"): continue
        try: ast.parse(ws.read(name))
        except SyntaxError as exc: found.append((name, exc.lineno, exc.msg))
        except Exception: continue
    return found


STEP_PROMPT = ("You build ONE step of a larger task. The earlier steps are done and their code is in the workspace: do not rewrite it, build on it.\n"
               "Plan:\n{plan}\n{notes}{map}\n"
               "YOUR step {i} of {n}: {title}\n{instruction}\n\n"
               "The parts of the task that belong to your step, word for word:\n{extract}\n\n"
               "Done when: {acceptance}{lessons}\n\n"
               "Work on your own. {check} Do NOT commit.")
