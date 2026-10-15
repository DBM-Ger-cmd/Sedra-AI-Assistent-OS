"""Skill digest (Captain 2026-10-13: "ja das soll er machen"). The 5-stage need test showed that the coder finds the right skill but does not copy its template exactly: a skill is 200-600 lines, the template stands somewhere in the
middle, the model reads 120-line pages and writes its own scaffold (stage spec: 0/3 even with skills). `skill_digest.py` builds a short view of a skill text: a one-line summary, then the markdown templates (fenced blocks of the
languages markdown or md) with their title and line numbers, then an outline of the headings with line numbers so the model can read on exactly where it needs to. Pure text functions; the tool parameter `brief` of skill_read and
SkillLibrary.brief are wired by Claude after acceptance. GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/skill_digest)."""

NOTES = '''# Notes for skill_digest
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code. `import` lines at the top.
'''

BT = "chr(96) * 3"

HEAD = '''
BT = chr(96) * 3
DOC = chr(10).join(["# Title", "Intro line about the skill.", "More text.", "", "## Overview", "Some words.", "", "## ADR Template", "Store them here.",
    BT + "markdown", "# ADR-001: Title", "", "## Status", "Accepted", BT, "", "### Lifecycle", BT, "PROPOSED -> ACCEPTED", BT, "## Rules",
    BT + "python", "# not a heading", "x = 1", BT, "- a", BT + "md", "# Short", BT, "#### Deep", "## Last"])
'''

S1 = HEAD + '''
from skill_digest import outline
assert outline(DOC) == [(1, 1, "Title"), (5, 2, "Overview"), (8, 2, "ADR Template"), (17, 3, "Lifecycle"), (21, 2, "Rules"), (30, 4, "Deep"), (31, 2, "Last")]
assert outline("") == [] and outline(None) == []
assert outline("no headings here\\n#nospace\\n##### five") == []
assert outline("## Title with trailing   \\n") == [(1, 2, "Title with trailing")]
assert outline(BT + "\\n# inside\\n" + BT + "\\n# outside") == [(4, 1, "outside")]
assert outline("# Open\\n" + BT + "\\n# never closed\\n## also inside") == [(1, 1, "Open")]
'''

S2 = S1 + '''
from skill_digest import templates
t = templates(DOC)
assert len(t) == 2
assert t[0] == {"title": "ADR Template", "start": 10, "end": 15, "lang": "markdown", "body": ["# ADR-001: Title", "", "## Status", "Accepted"]}
assert t[1] == {"title": "Rules", "start": 27, "end": 29, "lang": "md", "body": ["# Short"]}
assert templates("") == [] and templates(None) == []
assert templates(BT + "python\\nx = 1\\n" + BT) == []
assert templates(BT + "\\nplain\\n" + BT) == []
assert templates("# A\\n" + BT + "markdown\\nunclosed\\n") == []
only = templates(BT + "Markdown\\n# X\\n" + BT)
assert len(only) == 1 and only[0]["title"] == "" and only[0]["lang"] == "markdown" and only[0]["start"] == 1 and only[0]["end"] == 3
assert [x["title"] for x in templates("# One\\n" + BT + "md\\na\\n" + BT + "\\n## Two\\n" + BT + "md\\nb\\n" + BT)] == ["One", "Two"]
'''

S3 = S2 + '''
from skill_digest import digest
want = chr(10).join(["Summary: Intro line about the skill.", "Template (ADR Template, lines 10-15):", "# ADR-001: Title", "", "## Status", "Accepted",
    "Template (Rules, lines 27-29):", "# Short", "Outline:", "5 Overview", "8 ADR Template", "17   Lifecycle", "21 Rules", "31 Last"])
assert digest(DOC) == want
assert digest("") == "Outline:"
assert digest("no heading only text") == "Summary: no heading only text" + chr(10) + "Outline:"
assert digest("# Only\\n" + BT + "markdown\\nunclosed\\n") == "Outline:"
long_line = "x" * 300
assert digest(long_line).splitlines()[0] == "Summary: " + "x" * 160
assert digest(BT + "\\ncode first\\n" + BT + "\\ntext after").splitlines()[0] == "Summary: text after"
assert digest("# H\\n\\n## Sub\\ntext") == chr(10).join(["Summary: text", "Outline:", "3 Sub"])
before = DOC
digest(DOC)
assert DOC == before
'''

S4 = S3 + '''
MORE = "[more: read the full text with skill_read start/end]"
cut = digest(DOC, 8).splitlines()
assert len(cut) == 8 and cut[:-1] == want.splitlines()[:7] and cut[-1] == MORE
assert digest(DOC, 14) == want
assert len(digest(DOC, 13).splitlines()) == 13 and digest(DOC, 13).splitlines()[-1] == MORE
assert digest(DOC, 0).splitlines() == ["Summary: Intro line about the skill.", MORE]
assert digest(DOC, 1).splitlines() == ["Summary: Intro line about the skill.", MORE]
assert digest(DOC, "3").splitlines() == ["Summary: Intro line about the skill.", "Template (ADR Template, lines 10-15):", MORE]
many = chr(10).join(f"## H{i}" for i in range(200))
r = digest(many).splitlines()
assert len(r) == 60 and r[0] == "Outline:" and r[-1] == MORE and r[1] == "1 H0"
assert len(digest(DOC, 1000).splitlines()) == 14
'''

STAGES = [
    {"name": "outline", "no_own_check": True,
     "task": '''Create `skill_digest.py` with `outline(text) -> list`. The text is split into lines (`str(text or "")`, `splitlines()`, line numbers start at 1). A line is a heading when it matches `#` to `####` (1 to 4 hash signs), then white space, then a title; the title is the rest of the line without white space at both ends. Lines that start (after white space) with three backticks open or close a fenced block: lines inside a fenced block are never headings, and a fence that is never closed makes the rest of the text "inside". The result is a list of tuples (line number, level = number of hash signs, title). No comments and no docstrings.''',
     "hidden": {"hidden_digest_1.py": S1}},
    {"name": "templates", "no_own_check": True,
     "task": '''In `skill_digest.py` (keep `outline`) add `templates(text) -> list`: the fenced blocks whose language is `markdown` or `md` (the word after the three backticks of the opening fence, compared in lower case). Every block is a dict {"title", "start", "end", "lang", "body"}: title = the title of the closest heading ABOVE the opening fence ("" when there is none; use `outline`), start and end = the line numbers of the opening and the closing fence, lang = the language in lower case, body = the list of lines between the fences. A block that is never closed is ignored. Blocks of other languages (python, none) are not returned. No comments and no docstrings.''',
     "hidden": {"hidden_digest_2.py": S2}},
    {"name": "digest", "no_own_check": True,
     "task": '''In `skill_digest.py` add `digest(text, max_lines=60) -> str`: the lines, joined with "\\n": (1) when there is a summary: "Summary: " + the summary. The summary is the first line (white space cut at both ends, at most 160 characters) that is not empty, does not start with "#" and is not inside a fenced block; no such line: no summary line. (2) For every template (from `templates`): "Template (<title>, lines <start>-<end>):" and then its body lines. (3) "Outline:" and then, for every heading of level 2 or 3, one line "<line number> <two spaces per level above 2><title>" (so "17   Lifecycle" for a level 3 heading at line 17: the separating space plus two spaces). Nothing is modified. (The length limit comes in the next step; ignore max_lines for now.) No comments and no docstrings.''',
     "hidden": {"hidden_digest_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Now apply the length limit in `digest`: `max_lines` is made an int and is at least 2. When the lines of the digest are more than `max_lines`, the result is the first `max_lines - 1` lines followed by the exact line "[more: read the full text with skill_read start/end]" (so the result has exactly `max_lines` lines); otherwise nothing changes. The marker text is a module level constant `MORE`.
Then read the file once more: no rule may be copied into several places (the fence check must exist once), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_digest_full.py": S4}},
]
