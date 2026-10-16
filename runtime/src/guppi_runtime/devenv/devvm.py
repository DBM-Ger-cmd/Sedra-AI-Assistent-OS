"""DevVM Phase 1 (docs/DEVVM_AUFTRAG_2026-10-05.md): the developer workspace of one mission, held on the HOST, with git.

    ws = DevWorkspace(tool_root, "M-12345678", policy=broker.policy(), audit=rt.audit)
    ws.create()                                   # devvm/<mission>/repo/work  +  devvm/<mission>/repo/.git
    ws.write("pkg/mod.py", "x = 1\\n")             # new folders are created when needed (bounded)
    ws.commit("first version")                    # git in pure Python (dulwich), no hooks, no git program
    plan = ws.vm_preview(broker, [["python3", "-m", "unittest", "discover"]])      # a VM run is only PREVIEWED here

Why on the host: the VM is ephemeral (job limit 120 s, tmpfs wiped afterwards, measured in DevVM phase 0), the agent run may last 10 minutes, and the broker's input
rules forbid hidden entries such as `.git`. So the workspace lives here, `work/` is what a VM job gets copied in, and `.git` sits next to it (never copied).
Rules (the same as the broker's, so everything in the workspace can be run in the VM): relative paths below `work`, no dot names, no symlinks, only the file types the
broker allows (.py .md .txt .json .yaml .yml .toml .csv .js .css .html), at most `max_files` files, `max_file_bytes` per file and `max_input_bytes` in total, depth at most 8.
Nothing here starts a VM or executes model code: running is the broker's job and goes through the Guard and the Captain's gate as before.
Git hooks never run (dulwich's shell hooks are removed after opening the repository), and the model has no way to write into `.git`.
"""
from __future__ import annotations

import difflib
import os
import re
import shutil
import time
from pathlib import Path

from dulwich.object_store import iter_tree_contents
from dulwich.objects import Blob
from dulwich.repo import Repo

from ..sandbox.broker import SandboxBroker
from ..tools.base import ToolPermissionError, ToolValidationError

MAX_DEPTH = 8
TMP_SUFFIX = ".tmp-write"
IDENTITY = b"GUPPI DevVM <devvm@guppi.local>"


class DevWorkspace:
    def __init__(self, tool_root, mission_id, *, policy, audit=None, author=IDENTITY):
        if not isinstance(mission_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", mission_id): raise ToolValidationError("invalid_mission_id")
        self.tool_root = Path(tool_root).resolve()
        self.mission_id = mission_id
        self.policy = policy
        self.audit = audit
        self.author = author if isinstance(author, bytes) else str(author).encode("utf-8")
        self.repo_path = self.tool_root / "devvm" / mission_id / "repo"
        self.work = self.repo_path / "work"

    # ---- helpers -------------------------------------------------------------------------------------------------------------------
    def _audit(self, event, payload):
        if self.audit: self.audit.append(event, component="devvm", mission_id=self.mission_id, payload=payload)

    def _rel(self, value, directory=False):
        rel = SandboxBroker.relative(value, directory=directory)
        if len(rel.split("/")) > MAX_DEPTH: raise ToolValidationError("path_too_deep")
        return rel

    def _abs(self, rel):
        path = self.work.joinpath(*rel.split("/")) if rel else self.work
        current = self.work
        for part in rel.split("/") if rel else []:
            current = current / part
            if current.is_symlink(): raise ToolPermissionError("symlink_path_not_allowed")
        resolved = path.resolve()
        try: resolved.relative_to(self.work.resolve())
        except ValueError: raise ToolPermissionError("path_outside_workspace")
        return path

    def _files(self):
        return sorted(p for p in self.work.rglob("*") if p.is_file() and not p.is_symlink() and not p.name.endswith(TMP_SUFFIX)) if self.work.is_dir() else []

    def _check_growth(self, rel, new_size):
        files = {p.relative_to(self.work).as_posix(): p.stat().st_size for p in self._files()}
        files[rel] = new_size
        if new_size > self.policy["max_file_bytes"]: raise ToolValidationError("file_too_large")
        if len(files) > self.policy["max_files"]: raise ToolValidationError("too_many_files")
        if sum(files.values()) > self.policy["max_input_bytes"]: raise ToolValidationError("workspace_too_large")

    def _repo(self):
        repo = Repo(str(self.repo_path))
        repo.hooks.clear()          # no pre-commit / commit-msg / post-commit shell hooks, ever: nothing from the work tree may run on the host
        return repo

    # ---- lifecycle -----------------------------------------------------------------------------------------------------------------
    @property
    def source(self):
        """The folder name the broker needs for `preview(source=...)`: relative to the tool root, no hidden part."""
        return self.work.relative_to(self.tool_root).as_posix()

    def create(self):
        if self.repo_path.exists(): raise ToolValidationError("workspace_exists")
        self.work.mkdir(parents=True)
        Repo.init(str(self.repo_path)).close()
        self._audit("DEVVM_CREATED", {"source": self.source})
        return self.source

    # ---- files and folders ---------------------------------------------------------------------------------------------------------
    def write(self, path, text):
        rel = self._rel(path)
        if not isinstance(text, str): raise ToolValidationError("text_required")
        data = text.encode("utf-8")
        self._check_growth(rel, len(data))
        target = self._abs(rel)
        created = not target.parent.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + TMP_SUFFIX)
        try:
            tmp.write_bytes(data)
            for attempt in range(6):          # Windows may refuse the rename for a moment (a scanner holds the new file): try again, then give up cleanly
                try: os.replace(tmp, target); break
                except PermissionError:
                    if attempt == 5: raise
                    time.sleep(0.05 * (attempt + 1))
        except BaseException:
            tmp.unlink(missing_ok=True)       # never leave a half-written helper file in the workspace: the broker refuses such a folder for the VM
            raise
        self._audit("DEVVM_WRITE", {"path": rel, "bytes": len(data), "new_folders": created})
        return {"path": rel, "bytes": len(data)}

    def read(self, path):
        target = self._abs(self._rel(path))
        if not target.is_file(): raise ToolValidationError("file_not_found")
        return target.read_text(encoding="utf-8", errors="replace")

    def mkdir(self, path):
        rel = self._rel(path, directory=True)
        self._abs(rel).mkdir(parents=True, exist_ok=True)
        self._audit("DEVVM_MKDIR", {"path": rel})
        return rel

    def move(self, source, destination):
        src, dst = self._rel(source), self._rel(destination)
        a, b = self._abs(src), self._abs(dst)
        if not a.is_file(): raise ToolValidationError("file_not_found")
        if b.exists(): raise ToolValidationError("destination_exists")
        b.parent.mkdir(parents=True, exist_ok=True)
        a.rename(b)
        self._audit("DEVVM_MOVE", {"from": src, "to": dst})
        return {"from": src, "to": dst}

    def delete(self, path):
        """Deletes one file, or an empty folder. Never the workspace itself, never anything outside it."""
        text = SandboxBroker.relative(path, directory=True)
        target = self._abs(text)
        if target.is_file(): target.unlink()
        elif target.is_dir():
            if any(target.iterdir()): raise ToolValidationError("folder_not_empty")
            target.rmdir()
        else: raise ToolValidationError("path_not_found")
        self._audit("DEVVM_DELETE", {"path": text})
        return text

    def list(self, path=""):
        target = self._abs(self._rel(path, directory=True) if path else "")
        if not target.is_dir(): raise ToolValidationError("folder_not_found")
        return [{"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else None}
                for p in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())) if not p.is_symlink()]

    def tree(self):
        return sorted(p.relative_to(self.work).as_posix() for p in self._files())

    def search(self, text, limit=50):
        if not isinstance(text, str) or not text or len(text) > 200: raise ToolValidationError("search_text_required")
        needle, hits = text.lower(), []
        for p in self._files():
            for number, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if needle in line.lower():
                    hits.append({"path": p.relative_to(self.work).as_posix(), "line": number, "text": line.strip()[:200]})
                    if len(hits) >= limit: return hits
        return hits

    def usage(self):
        files = self._files()
        return {"files": len(files), "bytes": sum(p.stat().st_size for p in files), "max_files": self.policy["max_files"], "max_input_bytes": self.policy["max_input_bytes"]}

    # ---- git (dulwich, host side, no hooks) ----------------------------------------------------------------------------------------
    def _head_files(self, repo):
        try: head = repo.head()
        except KeyError: return {}
        out = {}
        for entry in iter_tree_contents(repo.object_store, repo[head].tree):
            out[entry.path.decode("utf-8")] = entry.sha
        return out

    def _working_files(self):
        out = {}
        for p in self._files():
            blob = Blob.from_string(p.read_bytes())
            out["work/" + p.relative_to(self.work).as_posix()] = blob.id
        return out

    def status(self):
        repo = self._repo()
        try:
            head, work = self._head_files(repo), self._working_files()
        finally: repo.close()
        strip = lambda p: p[len("work/"):]
        return {"added": sorted(strip(p) for p in work if p not in head), "modified": sorted(strip(p) for p in work if p in head and work[p] != head[p]),
                "deleted": sorted(strip(p) for p in head if p not in work)}

    def commit(self, message):
        if not isinstance(message, str) or not message.strip() or len(message) > 500: raise ToolValidationError("commit_message_required")
        repo = self._repo()
        try:
            head, work = self._head_files(repo), self._working_files()
            if head == {k: v for k, v in work.items()}: raise ToolValidationError("nothing_to_commit")
            tree = repo.get_worktree()
            tree.stage(sorted(set(work) | set(head)))               # staging a path that no longer exists removes it from the index
            sha = tree.commit(message=message.strip().encode("utf-8"), committer=IDENTITY, author=self.author, no_verify=True)
        finally: repo.close()
        self._audit("DEVVM_COMMIT", {"commit": sha.decode("ascii"), "message": message.strip()[:120]})
        return sha.decode("ascii")

    def log(self, limit=20):
        repo = self._repo()
        try:
            try: repo.head()
            except KeyError: return []
            return [{"commit": e.commit.id.decode("ascii"), "message": e.commit.message.decode("utf-8", "replace").strip().splitlines()[0] if e.commit.message.strip() else "",
                     "author": e.commit.author.decode("utf-8", "replace"), "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(e.commit.commit_time))}
                    for e in repo.get_walker(max_entries=limit)]
        finally: repo.close()

    def diff(self, path=None):
        """Unified diff of the working files against the last commit (all changed files, or one)."""
        repo = self._repo()
        try:
            head = self._head_files(repo)
            changed = self.status()
            wanted = [p for p in changed["added"] + changed["modified"] + changed["deleted"] if path in (None, p)]
            out = []
            for rel in wanted:
                old = repo[head["work/" + rel]].data.decode("utf-8", "replace").splitlines(keepends=True) if "work/" + rel in head else []
                target = self._abs(rel)
                new = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if target.is_file() else []
                out.extend(difflib.unified_diff(old, new, fromfile="a/" + rel, tofile="b/" + rel))
            return "".join(out)
        finally: repo.close()

    def restore_file(self, path):
        """One file back to its state in the last commit (a file that is not in the last commit is deleted). Returns "restored", "deleted" or "unchanged"."""
        rel = self._rel(path)
        repo = self._repo()
        try:
            head = self._head_files(repo)
            sha = head.get("work/" + rel)
            data = repo[sha].data if sha is not None else None
        finally: repo.close()
        target = self._abs(rel)
        if data is None:
            if not target.is_file(): return "unchanged"
            target.unlink(); self._audit("DEVVM_RESTORE_FILE", {"path": rel, "deleted": True}); return "deleted"
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        self._audit("DEVVM_RESTORE_FILE", {"path": rel, "deleted": False})
        return "restored"

    def restore(self, commit):
        """Puts the workspace back to the state of a commit (files of later versions are removed). Only inside `work`."""
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit): raise ToolValidationError("commit_id_required")
        repo = self._repo()
        try:
            try: tree = repo[commit.encode("ascii")].tree
            except KeyError: raise ToolValidationError("unknown_commit")
            files = {e.path.decode("utf-8"): repo[e.sha].data for e in iter_tree_contents(repo.object_store, tree)}
        finally: repo.close()
        targets = {}
        for full in sorted(files):      # every path is checked BEFORE anything is removed: a bad commit must not leave an emptied workspace
            if not full.startswith("work/"): raise ToolValidationError("commit_outside_workspace")
            targets[full] = self._abs(self._rel(full[len("work/"):]))
        for p in self._files(): p.unlink()
        for full, target in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(files[full])
        for folder in sorted((p for p in self.work.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(folder.iterdir()): folder.rmdir()
        self._audit("DEVVM_RESTORE", {"commit": commit, "files": len(files)})
        return sorted(f[len("work/"):] for f in files)

    # ---- the VM (preview only) -----------------------------------------------------------------------------------------------------
    def vm_preview(self, broker, commands, exports=None, export_dirs=None):
        """The broker's own plan for running `commands` on a copy of `work`. Starting it is the broker's job: Guard, Captain's gate, one run at a time."""
        kwargs = {"source": self.source, "commands": commands, "exports": exports}
        if export_dirs: kwargs["export_dirs"] = export_dirs
        return broker.preview(**kwargs)

    def destroy(self):
        """Removes the whole workspace of this mission (workspace and history). Only called by the Captain's decision."""
        root = self.repo_path.parent
        if root.name != self.mission_id or root.parent.name != "devvm": raise ToolPermissionError("not_a_devvm_folder")
        shutil.rmtree(root)
        self._audit("DEVVM_DESTROYED", {})
