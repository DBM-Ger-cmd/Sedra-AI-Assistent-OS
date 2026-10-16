"""Skill library (Captain 2026-10-13): third-party SKILL.md files as a read-only library that the coder looks up on demand.

    report = build_library(source_dir, library_dir, source="claude-skills", license="MIT")      # import, dedupe, scan, write index.json + skills/<id>/SKILL.md
    lib = SkillLibrary(library_dir)
    lib.search("write a code review checklist", limit=5)      # [{"id", "name", "description", "score"}]
    lib.read("code-reviewer", start=1, end=120)               # (page, total_lines, first, last): one page, at most MAX_PAGE_LINES lines

Rules: downloaded skills are DATA, never instructions for GUPPI. Only the SKILL.md and Markdown files under references/ are copied; scripts and every other file are not
(nothing from the library is ever executed). Mirror folders of other agents (.codex, .gemini, ...) are skipped, equal copies are imported once. A skill whose text contains
an instruction pattern against the user or the harness is imported as `flagged` and never found by search or read. The caller (coder_ext or a tool box) decides if the tools exist at all.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from .digest import digest
from .rank import rank
from .unify import merge_index, resolve

MIRRORS = frozenset({".codex", ".gemini", ".vibe", ".hermes", ".cursor", ".claude", ".opencode", ".github", ".agents", "node_modules", ".git"})
MAX_SKILL_BYTES = 200_000
SYNONYMS = (
    ("debug", "bug", "error", "fault", "failure", "crash", "broken", "diagnose"),
    ("test", "tdd", "testing"),
    ("review", "audit", "critique", "inspect"),
    ("plan", "planning", "breakdown", "decompose", "split", "steps"),
    ("refactor", "simplify", "simplification", "cleanup", "restructure"),
    ("doc", "docs", "documentation", "readme", "adr"),
    ("secure", "security", "vulnerability", "hardening"),
    ("performance", "slow", "optimize", "optimization", "speed"),
    ("api", "interface", "endpoint", "contract"),
    ("git", "commit", "branch", "merge"),
    ("context", "compression", "memory"),
    ("spec", "requirement", "requirements", "specification"),
)
BRIEF_NOTE = "DIGEST, not the full text: rules for labels, names, formats or severity can stand in sections that are not shown here. Before you write, read the sections of the outline that match your task with skill_read start/end."
MAX_PAGE_LINES = 120
MAX_PAGE_CHARS = 6_000
ID_RE = re.compile(r"[^a-z0-9]+")
FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
KEY_RE = re.compile(r"^([A-Za-z_-]+):\s*(.*)$")

# Text that talks to the agent instead of describing work: asks to ignore rules, hide things from the user, send data away or run downloaded code.
FLAGS = (
    ("override", re.compile(r"ignore (all |any )?(previous|prior|above|earlier) (instructions|rules|messages)|disregard (the )?(system|previous) (prompt|instructions)", re.I)),
    ("secrecy", re.compile(r"do not (tell|inform|show|reveal to) the user|without (telling|informing|asking) the user|hide this from the user", re.I)),
    ("exfiltrate", re.compile(r"(send|post|upload|exfiltrate)\b[^.\n]{0,60}\b(credentials|api[_ -]?keys?|tokens?|passwords?|secrets?|ssh keys?)\b", re.I)),
    ("remote_exec", re.compile(r"(curl|wget|iwr|Invoke-WebRequest)\b[^\n|]{0,200}\|\s*(sudo\s+)?(ba|z)?sh\b|powershell[^\n]{0,40}-enc(odedcommand)?\b|base64\s+(-d|--decode)[^\n]{0,60}\|\s*(ba)?sh", re.I)),
    ("guard_bypass", re.compile(r"(disable|bypass|turn off|skip) (the )?(guard|sandbox|safety (checks?|rules?)|permission (checks?|prompts?)|approval)", re.I)),
)


def parse_frontmatter(text):
    """(fields, body). Handles `key: value`, quoted values and `>`/`|` blocks of the simple kind used by SKILL.md files; anything else is ignored, never guessed."""
    m = FRONT_RE.match(text)
    if not m: return {}, text
    fields, key, block = {}, None, []
    for line in m.group(1).splitlines():
        k = KEY_RE.match(line) if not line.startswith((" ", "\t")) else None
        if k:
            if key is not None and block: fields[key] = " ".join(s.strip() for s in block if s.strip())
            key, value = k.group(1), k.group(2).strip()
            block = []
            if value in (">", "|", ">-", "|-", ">+", "|+", ""): continue
            fields[key] = value.strip("\"'"); key = None
        elif key is not None: block.append(line)
    if key is not None and block: fields[key] = " ".join(s.strip() for s in block if s.strip())
    return fields, text[m.end():]


def scan(text):
    """Names of the flag patterns that match; empty = clean. A match is a reason to keep the skill out of reach, not proof of bad intent."""
    return [name for name, rx in FLAGS if rx.search(text)]


def make_id(name, taken):
    base = ID_RE.sub("-", str(name).lower()).strip("-")[:60] or "skill"
    sid, n = base, 2
    while sid in taken:
        sid, n = f"{base}-{n}", n + 1
    return sid


def _skill_files(source):
    """SKILL.md paths below `source`, mirror folders left out, sorted so that the import is reproducible."""
    out = []
    for p in Path(source).rglob("SKILL.md"):
        rel = p.relative_to(source).parts
        if any(part in MIRRORS for part in rel[:-1]): continue
        out.append(p)
    return sorted(out, key=lambda p: (len(p.relative_to(source).parts), p.relative_to(source).as_posix()))


def _unix(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _old_ids(library):
    try: data = json.loads((Path(library) / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError): return set()
    return {e["id"] for e in data.get("skills", []) if isinstance(e, dict) and isinstance(e.get("id"), str) and re.fullmatch(r"[a-z0-9-]+", e["id"])}


def build_library(source, library, *, source_name, license_name, release=(), priority=None):
    """Import every SKILL.md below `source` (a folder, or a dict {source name: folder}; the order of the dict is the order of the import) into `library` (index.json and skills/<id>/...). Returns counts. Existing library content is replaced skill by skill, never deleted.
    `priority`: a list of source names, best first (the `source` of every skill is the name of its top folder below `source`): equal skills (same name or nearly the same description) are merged into one entry with `merged_from`, `also_in` and `aliases` in index.json, and the folders of the merged ones are removed.
    `release`: skill names the Captain checked by hand whose scan hits are false alarms (e.g. a skill that WARNS against injected instructions); their flags are cleared and kept as `released`."""
    roots = {label: Path(path) for label, path in source.items()} if isinstance(source, dict) else {None: Path(source)}
    library = Path(library)
    (library / "skills").mkdir(parents=True, exist_ok=True)
    old = _old_ids(library)
    taken, seen, entries = set(), {}, []
    counts = {"found": 0, "imported": 0, "duplicates": 0, "flagged": 0, "unreadable": 0, "too_big": 0, "no_description": 0}
    for label, root, path in ((label, root, path) for label, root in roots.items() for path in _skill_files(root)):
        counts["found"] += 1
        try: raw = path.read_bytes()
        except OSError: counts["unreadable"] += 1; continue
        if len(raw) > MAX_SKILL_BYTES: counts["too_big"] += 1; continue
        text = _unix(raw.decode("utf-8", errors="replace"))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in seen: counts["duplicates"] += 1; continue
        fields, body = parse_frontmatter(text)
        name = fields.get("name") or path.parent.name
        desc = fields.get("description", "").strip()
        if not desc: counts["no_description"] += 1
        sid = make_id(name, taken); taken.add(sid); seen[digest] = sid
        refs = {}
        for ref in sorted((path.parent / "references").glob("*.md")) if (path.parent / "references").is_dir() else []:
            if ref.stat().st_size <= MAX_SKILL_BYTES: refs[ref.name] = _unix(ref.read_text(encoding="utf-8", errors="replace"))
        flags = scan(text + "\n".join(refs.values()))
        released = flags if flags and str(name) in release else []
        if released: flags = []
        if flags: counts["flagged"] += 1
        folder = library / "skills" / sid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(body.strip() + "\n", encoding="utf-8", newline="\n")
        for fname, content in refs.items():
            (folder / "references").mkdir(exist_ok=True)
            (folder / "references" / fname).write_text(content, encoding="utf-8", newline="\n")
        entries.append({"id": sid, "name": str(name)[:80], "description": desc[:600], "lines": body.count("\n") + 1, "references": sorted(refs), "flags": flags, **({"released": released} if released else {}),
                        "source": label or (path.relative_to(root).parts[0] if priority is not None else source_name), "origin": path.relative_to(root).parent.as_posix(), "sha256": digest})
        counts["imported"] += 1
    aliases = {}
    if priority is not None:
        merged = merge_index(entries, list(priority))
        entries, aliases = merged["entries"], merged["aliases"]
        for dup in aliases: shutil.rmtree(library / "skills" / dup, ignore_errors=True)
        counts["merged"] = len(aliases); counts["imported"] -= len(aliases)
    for gone in old - {e["id"] for e in entries}: shutil.rmtree(library / "skills" / gone, ignore_errors=True)      # folders of the previous index that this import no longer holds
    index = {"schema": 1, "source": source_name, "license": license_name, "skills": entries, "aliases": aliases}
    (library / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return counts


class SkillLibrary:
    """Read-only access to an imported library. Flagged skills are invisible: not found by search, refused by read."""

    def __init__(self, library):
        self.root = Path(library)
        data = json.loads((self.root / "index.json").read_text(encoding="utf-8"))
        self.entries = {e["id"]: e for e in data.get("skills", []) if not e.get("flags")}
        self.license = data.get("license", "")
        self.aliases = data.get("aliases", {})

    def __len__(self):
        return len(self.entries)

    def search(self, query, limit=5):
        hits = rank(list(self.entries.values()), query, SYNONYMS, limit)
        return [{"id": h["id"], "name": self.entries[h["id"]]["name"], "description": self.entries[h["id"]]["description"][:200], "score": h["score"]} for h in hits]

    def brief(self, skill_id, max_lines=120):
        """Templates and outline of a skill (digest.digest), or of one reference file when `skill_id` is "id/file.md". Raises KeyError for an unknown id."""
        entry = self.entries.get(resolve(self.aliases, skill_id))
        if entry is None: raise KeyError(skill_id)
        return BRIEF_NOTE + chr(10) + digest((self.root / "skills" / entry["id"] / "SKILL.md").read_text(encoding="utf-8"), max_lines)

    def read(self, skill_id, start=None, end=None, reference=None):
        """One page of a skill (or one of its reference files). Returns (page, total_lines, first, last). Raises KeyError for an unknown id, ValueError for a bad reference name, TypeError for a start or end that is not a number, IndexError(total_lines) for a start behind the last line."""
        skill_id = resolve(self.aliases, skill_id)
        entry = self.entries.get(skill_id)
        if entry is None: raise KeyError(skill_id)
        if reference:
            if reference not in entry["references"]: raise ValueError("unknown_reference")
            path = self.root / "skills" / skill_id / "references" / reference
        else: path = self.root / "skills" / skill_id / "SKILL.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        try: a, last = max(1, int(start or 1)), int(end) if end else None
        except ValueError: raise TypeError("not_a_number")
        if a > max(len(lines), 1): raise IndexError(len(lines))
        b = min(len(lines), max(a, last) if last else a + MAX_PAGE_LINES - 1, a + MAX_PAGE_LINES - 1)
        page = "\n".join(lines[a - 1:b])
        if len(page) > MAX_PAGE_CHARS:
            page = page[:MAX_PAGE_CHARS]
            if "\n" in page: page = page.rsplit("\n", 1)[0]
            b = a + page.count("\n")
        return page, len(lines), a, b
