"""Safe removal of local model files (2026-10-03, Captain: "bauen wir dann gleich einen sicher-entfernen-Modus dazu ein").

    guppi model-remove-preview <recipe-id-or-gguf-path> [...]   what would go, who uses it, a plan with a digest
    guppi model-remove --plan <file>                             Captain gate (model_remove), then: recipes off, files to quarantine
    guppi model-restore <removal-id>                             files back, recipes on again

Nothing is ever deleted here. Files move into `<models root>/_guppi_entfernt/<removal-id>/` on the same drive (a rename, instant
even for 20 GB) with a manifest; the Captain deletes that folder when sure. Recipes that point at a removed file are switched off in
local_config/role_routing.yaml with a marker comment, so restore can switch exactly those on again. A model that is loaded right now,
or a file outside the models root, is refused. The plan digest binds the Captain's approval to exactly these files and recipes.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .. import local_paths

QUARANTINE = "_guppi_entfernt"
MARKER = "# guppi-model-remove "


class RemovalError(ValueError):
    pass


def _overlay(project):
    return Path(project) / "local_config" / "role_routing.yaml"


def _recipes(project):
    raw = yaml.safe_load(_overlay(project).read_text(encoding="utf-8")) or {}
    return (raw.get("role_routing") or {}).get("capabilities") or []


def _gguf_of(recipe):
    server = ((recipe.get("profile") or {}).get("server") or {})
    return [Path(p) for p in (server.get("gguf"), server.get("mmproj")) if p]


def _same(a, b):
    return str(Path(a).resolve()).casefold() == str(Path(b).resolve()).casefold()


def preview(project, targets, *, models_root, loaded_paths=(), profiles=None):
    """targets: recipe ids or file paths. Returns the plan (nothing is changed)."""
    root = Path(models_root).resolve()
    recipes = _recipes(project)
    by_id = {r.get("id"): r for r in recipes}
    files = []
    for t in targets:
        if t in by_id:
            files += _gguf_of(by_id[t])
        elif str(t).lower().endswith(".gguf"):
            files.append(Path(t))
        else:
            raise RemovalError(f"unknown_recipe:{t}")      # neither a recipe id nor a .gguf path
    out_files, seen = [], set()
    for f in files:
        f = f.resolve()
        key = str(f).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            rel = f.relative_to(root)
        except ValueError:
            raise RemovalError(f"outside_models_root:{f}")
        if QUARANTINE in rel.parts:
            raise RemovalError(f"already_in_quarantine:{f}")
        if not f.is_file():
            raise RemovalError(f"file_missing:{f}")
        if any(_same(f, p) for p in loaded_paths):
            raise RemovalError(f"model_is_loaded:{f}")
        st = f.stat()
        out_files.append({"path": str(f), "relative": rel.as_posix(), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns})
    if not out_files:
        raise RemovalError("nothing_to_remove")
    users = sorted({r.get("id") for r in recipes for g in _gguf_of(r) if any(_same(g, f["path"]) for f in out_files)})
    profile_refs = []
    if profiles is not None:
        for name, prof in (profiles.profiles or {}).items():
            for purpose, entry in prof.items():
                if isinstance(entry, dict) and set(entry.get("prefer") or []) & set(users):
                    profile_refs.append(f"{name}.{purpose}")
    plan = {"schema": 1, "action": "model_remove", "models_root": str(root), "files": out_files, "recipes_to_disable": users,
            "profiles_affected": profile_refs, "total_bytes": sum(f["bytes"] for f in out_files)}
    plan["plan_digest"] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan


def _check_plan(plan):
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != plan.get("plan_digest"):
        raise RemovalError("plan_digest_mismatch")


def _set_enabled(project, recipe_ids, removal_id, *, enable):
    path = _overlay(project)
    text = path.read_text(encoding="utf-8")
    shutil.copy2(path, path.with_name(path.name + f".bak-{removal_id}-{'restore' if enable else 'remove'}"))
    for rid in recipe_ids:
        head = f"    - id: {rid}\n"
        if head not in text:
            continue
        line = f"      enabled: false   {MARKER}{removal_id}\n"
        if enable:
            text = text.replace(head + line, head)
        elif head + line not in text:
            text = text.replace(head, head + line, 1)
    path.write_text(text, encoding="utf-8")


def remove(project, plan, *, now=None):
    """Execute an approved plan. Files that changed since the preview (size/mtime) refuse the whole plan."""
    _check_plan(plan)
    for f in plan["files"]:
        p = Path(f["path"])
        if not p.is_file():
            raise RemovalError(f"file_missing:{p}")
        st = p.stat()
        if st.st_size != f["bytes"] or st.st_mtime_ns != f["mtime_ns"]:
            raise RemovalError(f"file_changed_since_preview:{p}")
    removal_id = "RM-" + (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S")
    qdir = Path(plan["models_root"]) / QUARANTINE / removal_id
    _set_enabled(project, plan["recipes_to_disable"], removal_id, enable=False)
    moved = []
    try:
        for f in plan["files"]:
            target = qdir / f["relative"]
            target.parent.mkdir(parents=True, exist_ok=True)
            Path(f["path"]).rename(target)                     # same drive: a rename, nothing is copied or deleted
            moved.append({"from": f["path"], "to": str(target), "bytes": f["bytes"]})
    except Exception:
        for m in reversed(moved):
            Path(m["to"]).rename(m["from"])
        _set_enabled(project, plan["recipes_to_disable"], removal_id, enable=True)
        raise
    manifest = {"removal_id": removal_id, "plan_digest": plan["plan_digest"], "moved": moved, "recipes_disabled": plan["recipes_to_disable"],
                "total_bytes": plan["total_bytes"], "at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
                "note": "Delete this folder to free the space for good; `guppi model-restore " + removal_id + "` puts everything back."}
    (qdir / "removal.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def restore(project, models_root, removal_id):
    if not re.fullmatch(r"RM-\d{8}T\d{6}", removal_id or ""):
        raise RemovalError("removal_id_invalid")
    qdir = Path(models_root).resolve() / QUARANTINE / removal_id
    try:
        manifest = json.loads((qdir / "removal.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RemovalError("removal_not_found")
    for m in manifest["moved"]:
        if Path(m["from"]).exists():
            raise RemovalError(f"original_path_taken:{m['from']}")
    for m in manifest["moved"]:
        Path(m["from"]).parent.mkdir(parents=True, exist_ok=True)
        Path(m["to"]).rename(m["from"])
    _set_enabled(project, manifest["recipes_disabled"], removal_id, enable=True)
    (qdir / "removal.json").rename(qdir / "removal.restored.json")
    return {"status": "restored", "removal_id": removal_id, "files": len(manifest["moved"]), "recipes_enabled": manifest["recipes_disabled"]}


def models_root(rt):
    raw = (yaml.safe_load((rt.config_root / "llama_server.yaml").read_text(encoding="utf-8")) or {}).get("llama_server") or {}
    root = local_paths.expand(raw.get("models_root"))
    if not root or local_paths.unresolved(root):
        raise RemovalError("models_root_not_configured")
    return Path(root)


def _loaded_paths(rt):
    srv = getattr(rt, "llama_server", None)
    status = srv.status() if srv is not None else {}
    if not status.get("running"):
        return []
    return [g for r in _recipes(rt.project_root) if str(r.get("model")) == str(status.get("model")) for g in _gguf_of(r)]


def command(rt, mid, operation, *, targets=None, plan=None, removal_id=None):
    """CLI entry: preview | remove | restore. `remove` runs only with the Captain's token for exactly this plan (Guard GR-028)."""
    root = models_root(rt)
    if operation == "preview":
        return {"status": "completed", "plan": preview(rt.project_root, targets or [], models_root=root, loaded_paths=_loaded_paths(rt),
                                                       profiles=getattr(rt, "routing_profiles", None))}
    if operation == "restore":
        out = restore(rt.project_root, root, removal_id)
        rt.audit.append("MODEL_RESTORED", component="model-removal", payload=out)
        return out
    if operation != "remove":
        raise RemovalError("unsupported_model_removal_operation")
    _check_plan(plan)
    fresh = preview(rt.project_root, [f["path"] for f in plan["files"]], models_root=root, loaded_paths=_loaded_paths(rt),
                    profiles=getattr(rt, "routing_profiles", None))
    if fresh["plan_digest"] != plan["plan_digest"]:
        raise RemovalError("plan_changed_since_preview")
    with rt.missions.execution_lock(mid):
        mission = rt.missions.load(mid)
        token = mission["execution"].get("approval_token")
        target = "model_remove:" + plan["plan_digest"]
        verdict = rt.guard.evaluate("model_remove", mission_id=mid, target=target)
        if verdict["decision"] == "BLOCK":
            return {"status": "blocked", "guard": verdict}
        if verdict["decision"] != "ALLOW" and not rt.guard.authorize(token, mission_id=mid, action="model_remove", target=target, request_binding=plan)["authorized"]:
            gb = round(plan["total_bytes"] / 1e9, 1)
            gate = rt.guard.create_gate(mid, "model_remove", target, request_binding=plan, rollback_available=True,
                                        risks=[f"Moves {len(plan['files'])} model file(s), {gb} GB, into {QUARANTINE}/ (nothing is deleted)",
                                               "Switches off recipes: " + (", ".join(plan["recipes_to_disable"]) or "none")])
            if not any(g["request"] == gate["request"] for g in mission["human_gates"]["pending"]):
                mission["human_gates"]["pending"].append(gate)
            rt.missions.save(mission)
            return {"status": "captain_required", "gate": gate}
        manifest = remove(rt.project_root, plan)
        if token and token.get("status") == "used":
            mission["execution"].pop("approval_token", None)
        rt.missions.save(mission)
    rt.audit.append("MODEL_REMOVED", component="model-removal", mission_id=mid,
                    payload={k: manifest[k] for k in ("removal_id", "plan_digest", "recipes_disabled", "total_bytes")})
    return {"status": "completed", **manifest}
