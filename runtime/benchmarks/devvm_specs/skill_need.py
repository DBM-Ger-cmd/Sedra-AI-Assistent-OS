"""SKILL NEED TEST (Captain 2026-10-13: "dann gucken wir nach einem geeigneten Test"). The A/B measurement on bench_std showed no use of the skill tools because bench_std tasks are closed: everything the model needs stands in the task.
Here the task names only the KIND of document, and the exact format is a convention that a model cannot guess but that stands in two skills of the core library: the ADR format of `documentation-and-adrs` (location, title
"ADR-001: ...", fixed sections) and the review labels of `code-review-and-quality` (Critical:, Nit:, Optional:, ...). Five stages (adr, review, spec, plan, commit; the last three from spec-driven-development, planning-and-task-breakdown and git-workflow-and-versioning), hidden tests check only the written files. Run it twice: without and with `--skills runtime_data/skill_library_core`
(same prompt in both arms); the question is whether the coder finds and uses the skill and whether the files then follow the convention. Seed: benchmarks/skill_need_seed (store.py). Reference: benchmarks/devvm_refs/skill_need (the two files)."""

SEED = "benchmarks/skill_need_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given
NOTES = '''# Notes
Pure Python 3 standard library. Do NOT write tests. Create only the file(s) the task asks for. Where the task says "the team's usual format", the team keeps it in its written guidance; follow that guidance, do not invent a format.
'''

ADR = '''
import re
from pathlib import Path
files = sorted(Path("docs/decisions").glob("*.md")) if Path("docs/decisions").is_dir() else []
assert len(files) == 1
lines = files[0].read_text(encoding="utf-8").splitlines()
assert re.match(r"^# ADR-001: \\S", lines[0])
heads = [l.strip() for l in lines if l.startswith("## ")]
assert heads == ["## Status", "## Date", "## Context", "## Decision", "## Alternatives Considered", "## Consequences"]
def after(title):
    i = lines.index(title)
    return next(l.strip() for l in lines[i + 1:] if l.strip())
assert after("## Status") in ("Proposed", "Accepted")
assert re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", after("## Date"))
subs = [l[4:].strip().lower() for l in lines if l.startswith("### ")]
assert len(subs) >= 2 and any("postgres" in s for s in subs) and any("json" in s for s in subs)
assert "sqlite" in " ".join(lines).lower()
'''

REVIEW = '''
import re
from pathlib import Path
rows = [l for l in Path("review.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
assert len(rows) >= 2
LABEL = re.compile(r"^- \\**(Critical|Required|Nit|Optional|Consider|FYI):?\\**:? ")
assert all(LABEL.match(r) for r in rows)
sql = [r for r in rows if re.search(r"inject|sql|parameter", r, re.I)]
assert sql and all(re.match(r"^- \\**Critical", r) for r in sql)
assert sum(1 for r in rows if re.match(r"^- \\**Critical", r)) <= 2
'''

SPEC = '''
import re
from pathlib import Path
found = sorted(Path(".").glob("SPEC*.md"))
assert len(found) == 1
lines = found[0].read_text(encoding="utf-8").splitlines()
assert re.match(r"^# Spec: \\S", lines[0])
heads = [l.strip() for l in lines if l.startswith("## ")]
assert heads == ["## Objective", "## Tech Stack", "## Commands", "## Project Structure", "## Code Style", "## Testing Strategy", "## Boundaries", "## Success Criteria", "## Open Questions"]
i = lines.index("## Boundaries")
block = []
for l in lines[i + 1:]:
    if l.startswith("## "): break
    block.append(l.strip())
for tag in ("- Always:", "- Ask first:", "- Never:"):
    assert any(b.startswith(tag) and len(b) > len(tag) + 2 for b in block)
assert "markdown" in " ".join(lines).lower()
'''

PLAN = '''
import re
from pathlib import Path
text = Path("tasks/todo.md").read_text(encoding="utf-8")
parts = re.split(r"(?m)^## Task (\\d+): (\\S.*)$", text)
tasks = [parts[i + 2] for i in range(1, len(parts) - 2, 3)]
assert len(tasks) >= 3
for body in tasks:
    assert re.search(r"\\*\\*Acceptance criteria:\\*\\*\\s*\\n- \\[ \\] \\S", body)
    assert "**Verification:**" in body and "**Dependencies:**" in body
    assert re.search(r"\\*\\*Estimated scope:\\*\\*\\s*(Small|Medium|Large)", body)
assert re.search(r"\\*\\*Dependencies:\\*\\*\\s*None", tasks[0])
assert "markdown" in text.lower()
'''

COMMIT = '''
import re
from pathlib import Path
lines = Path("commit_msg.txt").read_text(encoding="utf-8").splitlines()
assert re.match(r"^fix: \\S", lines[0]) and len(lines[0]) <= 72
assert len(lines) >= 3 and lines[1] == "" and any(l.strip() for l in lines[2:])
body = " ".join(lines[2:]).lower()
assert "inject" in body or "parameter" in body or "concatenat" in body
'''

STAGES = [
    {"name": "adr", "no_own_check": True,
     "task": '''The tool keeps a local cache of its lookups. Record the decision to use SQLite for this cache as an architecture decision record, the first one of the project. Alternatives that were considered: PostgreSQL and JSON files. Today is 2026-10-13.
Use the team's usual location, numbering and format for such records (the team keeps them in its written guidance). Write only that one file.''',
     "hidden": {"hidden_need_adr.py": ADR}},
    {"name": "review", "no_own_check": True,
     "task": '''Review `store.py` (already in the workspace) and write your review comments to `review.md`: one comment per line, every line starting with "- ". Report every real problem you find, at least two comments. Use the team's usual format for review comments (the team keeps it in its written guidance). Do not change `store.py`.''',
     "hidden": {"hidden_need_review.py": REVIEW}},
    {"name": "spec", "no_own_check": True,
     "task": '''Before the next feature is built, write its specification: the tool shall be able to export all notes as one Markdown file (one heading per note, in creation order). The tool is a small Python program (`store.py` and a command line `main.py`) that uses only the standard library and unittest.
Use the team's usual format for specifications (one spec file, named SPEC.md or SPEC-<name>.md in the project root) (the team keeps them in its written guidance). Write only that one file.''',
     "hidden": {"hidden_need_spec.py": SPEC}},
    {"name": "plan", "no_own_check": True,
     "task": '''Break the work of the Markdown export feature into tasks (collect the notes, render them as Markdown, add a command line option that writes the file; at least three tasks, each small). Record them in the team's usual task list, with the team's usual structure for a task (the team keeps both in its written guidance). Write only that one file.''',
     "hidden": {"hidden_need_plan.py": PLAN}},
    {"name": "commit", "no_own_check": True,
     "task": '''The function `find_user` in `store.py` was fixed: it built its SQL text by joining the name into it, now it uses a parameterized query. Write the commit message for this fix to `commit_msg.txt` in the team's usual commit message format (the team keeps it in its written guidance). Write only that one file.''',
     "hidden": {"hidden_need_commit.py": COMMIT}},
]
