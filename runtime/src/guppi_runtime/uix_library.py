"""Bibliothek window (Captain 2026-10-14): see and edit the skills.

Three shelves, one window:
- SEDRA's own capabilities (`skills/<id>/skill.yaml` of the architecture, the "20 Skills" of the tray): read-only here, they are the runtime's contract.
- The imported libraries of `config/skill_library.yaml` (core, full): third-party SKILL.md files, DATA for the coder, read-only; a skill can be
  copied as the template of an own skill.
- The Captain's own skills: `local_config/skill_library/skills/<id>/SKILL.md` (this PC, not in git). Written only behind a Captain gate; every write makes a
  backup, re-scans the text with the library's flag patterns (a flagged text is refused, like an import would be) and rebuilds the folder's
  index.json, so `SkillLibrary(local_config/skill_library)` and `devvm_build.py --skills <that folder>` can use it like any library.
Pure helpers (`custom_index`, `check_skill_text`) take text and paths; the hub-bound part is `LibraryDesk`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
from pathlib import Path

from .skill_library import MAX_SKILL_BYTES, SkillLibrary, parse_frontmatter, scan
from .skill_library.config import library_path, load as load_libraries

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,59}$")
ACTION = "change_skill"
TEMPLATE = """---
name: {id}
description: Wann dieser Skill gilt (ein Satz: Aufgabe, Auslöser). Der Coder findet ihn über diese Beschreibung.
---

# {title}

## Wann
- …

## Vorgehen
1. …

## Prüfen
- …
"""


def check_skill_text(text, skill_id):
    """ValueError with a reason when the text cannot become an own skill: size, front matter (name, description), flag patterns."""
    if not isinstance(text, str): raise ValueError("text_required")
    if len(text.encode("utf-8")) > MAX_SKILL_BYTES: raise ValueError("skill_too_large")
    fields, body = parse_frontmatter(text)
    if not fields.get("name") or not fields.get("description"): raise ValueError("frontmatter_name_and_description_required")
    if not body.strip(): raise ValueError("skill_body_empty")
    flags = scan(text)
    if flags: raise ValueError("skill_text_flagged:" + ",".join(flags))
    return fields, body


def custom_index(root):
    """index.json of the Captain's folder, from the SKILL.md files that are there. Returns the entries."""
    root = Path(root)
    entries = []
    (root / "skills").mkdir(parents=True, exist_ok=True)
    for folder in sorted(p for p in (root / "skills").glob("*") if p.is_dir() and ".bak-" not in p.name and (p / "SKILL.md").is_file()):
        text = (folder / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        fields, body = parse_frontmatter(text)
        refs = sorted(p.name for p in (folder / "references").glob("*.md")) if (folder / "references").is_dir() else []
        entries.append({"id": folder.name, "name": str(fields.get("name") or folder.name)[:80], "description": str(fields.get("description") or "")[:600],
                        "lines": body.count("\n") + 1, "references": refs, "flags": scan(text), "source": "captain", "origin": f"local_config/skill_library/skills/{folder.name}",
                        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    (root / "index.json").write_text(json.dumps({"schema": 1, "source": "captain", "license": "eigene", "skills": entries, "aliases": {}}, ensure_ascii=False, indent=1), encoding="utf-8")
    return entries


class LibraryDesk:
    CUSTOM = "eigene"

    def __init__(self, hub):
        self.hub = hub

    # ---- where things are
    def custom_root(self):
        return self.hub.runtime.project_root / "local_config" / "skill_library"

    def _libraries(self):
        try: return load_libraries()
        except Exception: return {}

    def _library(self, name):
        if name == self.CUSTOM:
            root = self.custom_root()
            if not (root / "index.json").is_file():
                root.mkdir(parents=True, exist_ok=True); custom_index(root)
            return SkillLibrary(root)
        libraries = self._libraries()
        if name not in libraries: raise ValueError("unknown_library")
        try: return SkillLibrary(library_path(name, libraries))
        except (KeyError, FileNotFoundError, json.JSONDecodeError): raise ValueError("library_not_built")

    # ---- views
    def view(self):
        rt = self.hub.runtime
        own = []
        for sid, meta in sorted(getattr(rt.registry, "skills", {}).items()):
            d = meta.get("data", meta) if isinstance(meta, dict) else {}
            own.append({"id": sid, "name": d.get("name", sid), "version": d.get("version"), "description": d.get("description", ""), "capabilities": d.get("capabilities", []),
                        "triggers": d.get("triggers", []), "tool_hints": d.get("tool_hints", []), "guard": (d.get("guard") or {}).get("level")})
        shelves = []
        for name, entry in self._libraries().items():
            try:
                lib = SkillLibrary(library_path(name, self._libraries())); count, ok, note = len(lib), True, ""
            except Exception as exc:
                count, ok, note = 0, False, "nicht gebaut: python -m guppi_runtime.skill_library build " + name
            shelves.append({"name": name, "note": str(entry.get("note", "")), "license": str(entry.get("license", "")), "count": count, "available": ok, "hint": note, "editable": False})
        root = self.custom_root(); root.mkdir(parents=True, exist_ok=True)
        custom = custom_index(root)
        shelves.insert(0, {"name": self.CUSTOM, "note": "Eigene Skills dieses PCs (local_config/skill_library); Schreiben nur mit Freigabe", "license": "eigene", "count": len([e for e in custom if not e["flags"]]),
                           "available": True, "hint": "", "editable": True})
        return {"own": own, "libraries": shelves, "custom": custom, "custom_root": str(root), "template": TEMPLATE}

    def search(self, payload):
        query = str(payload.get("query") or "").strip()
        name = str(payload.get("library") or "core")
        lib = self._library(name)
        if not query:
            items = sorted(lib.entries.values(), key=lambda e: e["name"].lower())
            return {"library": name, "hits": [{"id": e["id"], "name": e["name"], "description": e["description"][:200], "lines": e.get("lines"), "score": None} for e in items[:400]], "total": len(lib)}
        return {"library": name, "hits": lib.search(query[:200], limit=min(50, int(payload.get("limit") or 20))), "total": len(lib)}

    def read(self, payload):
        name = str(payload.get("library") or "core")
        lib = self._library(name)
        sid = str(payload.get("id") or "")
        ref = payload.get("reference") or None
        try:
            page, total, first, last = lib.read(sid, payload.get("start"), payload.get("end"), ref)
        except KeyError: raise ValueError("unknown_skill")
        except IndexError: raise ValueError("start_behind_end")
        entry = lib.entries.get(sid) or {}
        return {"library": name, "id": sid, "name": entry.get("name", sid), "description": entry.get("description", ""), "references": entry.get("references", []),
                "source": entry.get("source", ""), "license": lib.license, "page": page, "total": total, "first": first, "last": last, "editable": name == self.CUSTOM}

    def full_text(self, payload):
        """The whole SKILL.md (for the editor and for copying a library skill as a template). Only skills the library knows, never flagged ones."""
        name = str(payload.get("library") or "core")
        lib = self._library(name)
        sid = str(payload.get("id") or "")
        if sid not in lib.entries: raise ValueError("unknown_skill")
        return {"library": name, "id": sid, "text": (lib.root / "skills" / sid / "SKILL.md").read_text(encoding="utf-8", errors="replace")}

    # ---- own skills: request (gate) and apply
    def _path(self, sid):
        return self.custom_root() / "skills" / sid / "SKILL.md"

    def custom_request(self, payload):
        sid = str(payload.get("id") or "").strip().lower()
        if not ID_RE.match(sid): raise ValueError("skill_id_invalid")
        text = payload.get("text")
        delete = text is None or (isinstance(text, str) and not text.strip())
        path = self._path(sid)
        old = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        if delete:
            if not old: raise ValueError("unknown_skill")
            describe = f"Eigenen Skill {sid} löschen"
        else:
            if text.count("\n") < 2: raise ValueError("skill_body_empty")
            check_skill_text(text, sid)
            if text == old: raise ValueError("nothing_changed")
            describe = f"Eigenen Skill {sid} {'ändern' if old else 'anlegen'} ({text.count(chr(10)) + 1} Zeilen)"
        binding = {"skill_id": sid, "text": "" if delete else text, "delete": delete, "text_sha256": hashlib.sha256(("" if delete else text).encode("utf-8")).hexdigest(),
                   "file_sha256": hashlib.sha256(old.encode("utf-8")).hexdigest() if old else "", "describe": describe, "old_lines": old.count("\n") + 1 if old else 0}
        risks = ["schreibt local_config/skill_library/skills/" + sid + "/SKILL.md", "der Coder kann den Text als Nachschlagewerk lesen (er wird nie ausgeführt)"]
        return self.hub._remember("skill", self.hub._gate_request(describe, ACTION, f"skill:{sid}", binding, risks, "skill_request"))      # the Deck shows it under "Wartet auf dich"

    def custom_apply(self, payload):
        mission_id = str(payload.get("mission_id") or "").strip()
        if not mission_id: raise ValueError("mission_id_required")
        rt = self.hub.runtime
        with rt.missions.execution_lock(mission_id):
            try: m = rt.missions.load(mission_id)
            except KeyError: raise ValueError("unknown_mission")
            binding = (m.get("context") or {}).get("skill_request") or {}
            path = self._path(binding.get("skill_id", "")) if binding else None
            current = hashlib.sha256(path.read_text(encoding="utf-8", errors="replace").encode("utf-8")).hexdigest() if path is not None and path.is_file() else ""
            binding = self.hub._spend_approval(m, mission_id, "skill_request", ACTION, lambda b: f"skill:{b['skill_id']}", current)
            if hashlib.sha256(binding["text"].encode("utf-8")).hexdigest() != binding["text_sha256"]: raise ValueError("request_text_changed")
            backup = None
            stamp = ".bak-" + datetime.date.today().isoformat() + "-uix"
            if binding["delete"]:                                                  # the whole folder moves aside; nothing is lost
                backup = path.parent.with_name(path.parent.name + stamp)
                if backup.exists(): shutil.rmtree(backup)
                shutil.move(str(path.parent), str(backup))
            else:
                if path.is_file():
                    backup = path.with_name("SKILL.md" + stamp); shutil.copy2(path, backup)
                check_skill_text(binding["text"], binding["skill_id"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(binding["text"], encoding="utf-8")
            custom_index(self.custom_root())
            m["execution"].pop("approval_token", None)
            m["result"] = {"kind": "skill_deleted" if binding["delete"] else "skill_written", "skill_id": binding["skill_id"], "backup": backup.name if backup else None}
            m["lifecycle"]["status"] = "closed"
            rt.missions.save(m)
            rt.audit.append("SKILL_CUSTOM_DELETED" if binding["delete"] else "SKILL_CUSTOM_WRITTEN", component="uix", mission_id=mission_id,
                            payload={"skill_id": binding["skill_id"], "text_sha256": binding["text_sha256"]})
        return {"status": "applied", "skill_id": binding["skill_id"], "deleted": binding["delete"]}
