from __future__ import annotations
from pathlib import Path
import os
import re
import shutil
import subprocess
from ..request_binding import file_request
from .base import BaseTool, ToolValidationError


class GitTool(BaseTool):
    id = "git"
    version = "0.2.0"
    READ_ONLY = {"status", "diff", "log", "rev-parse", "ls-files"}
    MUTATING = {"init"}
    supported_operations = READ_ONLY | MUTATING

    def __init__(self, root: Path, guard=None, audit=None, max_output_chars: int = 200_000):
        super().__init__(root, guard, audit)
        self.max_output_chars=int(max_output_chars)
        self.no_hooks_dir=self.root/".guppi_no_hooks"
        self.no_hooks_dir.mkdir(exist_ok=True)

    def health(self):
        return shutil.which("git") is not None

    def execute(self, mission_id: str, operation: str, args=None, approval_token=None):
        args = args or {}
        if operation not in self.supported_operations:
            raise ToolValidationError(f"unsupported_git_operation:{operation}")
        cwd = self._resolve(args.get("cwd", "."), must_exist=True)
        if not cwd.is_dir(): raise ToolValidationError("git_cwd_not_directory")
        if not self.health(): return {"status":"failed","error":"git_not_available"}
        extra = [str(x) for x in args.get("args", [])]
        if sum(len(x) for x in extra)>16_000: raise ToolValidationError("git_arguments_too_large")
        extra = self._validate_args(operation, extra, cwd)
        action = "git_read" if operation in self.READ_ONLY else "git_init"
        scope_target = f"{cwd}|git {operation} {' '.join(extra)}".strip()
        binding=file_request(operation,args,cwd) if operation in self.MUTATING else {"operation":operation,"args":args,"cwd":str(cwd)}
        verdict = self.guard.evaluate(action, mission_id=mission_id, target=scope_target) if self.guard else {"decision":"ALLOW"}
        if verdict["decision"] == "BLOCK": return {"status":"blocked","guard":verdict}
        if verdict["decision"] == "CAPTAIN_REQUIRED":
            auth = self.guard.authorize(approval_token, mission_id=mission_id, action=action, target=scope_target,request_binding=binding) if self.guard else {"authorized":False}
            if not auth["authorized"]:
                gate = self.guard.create_gate(mission_id, action, scope_target, risks=["Changes local Git repository metadata"], rollback_available=True,request_binding=binding)
                return {"status":"captain_required","guard":verdict,"gate":gate}
        cmd = ["git", "-c", f"core.hooksPath={self.no_hooks_dir}", "-c", "credential.helper=", "--no-pager", operation] + extra
        env=self._safe_env()
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=min(max(int(args.get("timeout",30)),1),120), shell=False, env=env)
        stdout,trunc_out=self._truncate(proc.stdout)
        stderr,trunc_err=self._truncate(proc.stderr)
        self._audit("TOOL_CALLED", mission_id, {"tool":self.id,"operation":operation,"cwd":str(cwd),"returncode":proc.returncode})
        return {"status":"completed" if proc.returncode == 0 else "failed","returncode":proc.returncode,"stdout":stdout,"stderr":stderr,"output_truncated":trunc_out or trunc_err,"command":["git",operation]+extra}

    def _safe_env(self):
        allow={"PATH","PATHEXT","SYSTEMROOT","WINDIR","COMSPEC","TEMP","TMP","HOME","USERPROFILE","LANG","LC_ALL"}
        env={k:v for k,v in os.environ.items() if k.upper() in allow}
        env["GIT_TERMINAL_PROMPT"]="0"
        env["GIT_PAGER"]="cat"
        env["GIT_CONFIG_NOSYSTEM"]="1"
        env["GIT_CONFIG_GLOBAL"]=os.devnull
        env["GIT_OPTIONAL_LOCKS"]="0"
        return env

    def _truncate(self,value):
        value=value or ""
        if len(value)<=self.max_output_chars: return value,False
        return value[:self.max_output_chars]+"\n...[truncated by GUPPI]",True

    def _validate_args(self, operation: str, args: list[str], cwd: Path):
        if operation == "init":
            if args: raise ToolValidationError("git_init_arguments_not_allowed")
            return []
        if operation == "status":
            allowed={"--short","--porcelain","--branch","--untracked-files=no","--untracked-files=normal","--untracked-files=all"}
            if any(a not in allowed for a in args): raise ToolValidationError("unsupported_git_status_argument")
            return args
        if operation == "diff":
            allowed_flags={"--stat","--name-only","--name-status","--cached","--staged"}
            clean=[]
            for a in args:
                if a in allowed_flags or a == "--": clean.append(a); continue
                if a.startswith("-"): raise ToolValidationError("unsupported_git_diff_argument")
                self._validate_relative_path(a,cwd); clean.append(a)
            return ["--no-ext-diff","--no-textconv"]+clean
        if operation == "log":
            for a in args:
                if a == "--oneline": continue
                m=re.fullmatch(r"--max-count=(\d+)",a)
                n=re.fullmatch(r"-n(\d+)",a)
                if m and int(m.group(1))<=100: continue
                if n and int(n.group(1))<=100: continue
                raise ToolValidationError("unsupported_git_log_argument")
            return args or ["--oneline","--max-count=20"]
        if operation == "rev-parse":
            allowed={"--show-toplevel","--is-inside-work-tree","--short","HEAD"}
            for a in args:
                if a in allowed or re.fullmatch(r"[A-Za-z0-9._/]+",a): continue
                raise ToolValidationError("unsupported_git_rev_parse_argument")
            return args
        if operation == "ls-files":
            allowed_flags={"--cached","--modified","--deleted","--others","--exclude-standard"}
            for a in args:
                if a in allowed_flags: continue
                if a.startswith("-"): raise ToolValidationError("unsupported_git_ls_files_argument")
                self._validate_relative_path(a,cwd)
            return args
        return args

    def _validate_relative_path(self, value: str, cwd: Path):
        candidate=(cwd/value).resolve(strict=False)
        try: candidate.relative_to(cwd.resolve())
        except ValueError as exc: raise ToolValidationError("git_path_outside_cwd") from exc
