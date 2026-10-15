from __future__ import annotations
from pathlib import Path
import os
import subprocess
import sys
from .base import BaseTool, ToolValidationError


class ShellTool(BaseTool):
    id = "shell"
    version = "0.2.0"
    supported_operations = {"run"}
    DEFAULT_ALLOWLIST = {"python", "python3", "py"}

    def __init__(self, root: Path, guard=None, audit=None, allowlist=None, max_output_chars: int = 200_000):
        super().__init__(root, guard, audit)
        self.allowlist = set(allowlist or self.DEFAULT_ALLOWLIST)
        self.max_output_chars=int(max_output_chars)

    def execute(self, mission_id: str, operation: str, args=None, approval_token=None):
        if operation != "run":
            raise ToolValidationError(f"unsupported_shell_operation:{operation}")
        args = args or {}
        argv = args.get("argv")
        if not isinstance(argv, list) or not argv:
            raise ToolValidationError("argv_must_be_nonempty_list")
        argv = [str(x) for x in argv]
        if sum(len(x) for x in argv)>16_000:
            raise ToolValidationError("argv_too_large")
        exe_name = Path(argv[0]).name.lower()
        if exe_name.endswith(".exe"):
            exe_name = exe_name[:-4]
        if exe_name not in self.allowlist:
            raise ToolValidationError("executable_not_allowlisted")
        cwd = self._resolve(args.get("cwd", "."), must_exist=True)
        if not cwd.is_dir():
            raise ToolValidationError("shell_cwd_not_directory")
        self._validate_python(argv, exe_name, cwd)

        # Since v1.7, project test/compile code must use the sandbox broker.
        # A Captain token cannot silently turn this into host execution.
        trusted_version = (len(argv) == 2 and argv[1] in {"--version", "-V"}
                           and Path(argv[0]).resolve() == Path(sys.executable).resolve())
        if not trusted_version:
            self._audit("SANDBOX_REQUIRED", mission_id, {"operation": operation})
            return {"status": "blocked", "reason": "project_code_requires_sandbox", "tool": "sandbox"}

        binding={"operation":operation,"argv":argv,"cwd":str(cwd),"timeout":args.get("timeout",60)}
        scope_target = f"{cwd}|{' '.join(argv)}"
        verdict = self.guard.evaluate("shell_execute", mission_id=mission_id, target=scope_target) if self.guard else {"decision":"CAPTAIN_REQUIRED"}
        if verdict["decision"] == "BLOCK":
            return {"status":"blocked","guard":verdict}
        if verdict["decision"] == "CAPTAIN_REQUIRED":
            auth = self.guard.authorize(approval_token, mission_id=mission_id, action="shell_execute", target=scope_target,request_binding=binding) if self.guard else {"authorized":False}
            if not auth["authorized"]:
                gate = self.guard.create_gate(mission_id, "shell_execute", scope_target, risks=["Executes local test or compile code without OS sandboxing"], rollback_available=False,request_binding=binding)
                return {"status":"captain_required","guard":verdict,"gate":gate}

        env = self._safe_env()
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=min(max(int(args.get("timeout", 60)),1),180), shell=False, env=env)
        stdout,trunc_out=self._truncate(proc.stdout)
        stderr,trunc_err=self._truncate(proc.stderr)
        self._audit("TOOL_CALLED", mission_id, {"tool":self.id,"operation":"run","cwd":str(cwd),"executable":exe_name,"returncode":proc.returncode})
        return {"status":"completed" if proc.returncode == 0 else "failed","returncode":proc.returncode,"stdout":stdout,"stderr":stderr,"output_truncated":trunc_out or trunc_err,"command":argv}

    def _safe_env(self):
        allow={"PATH","PATHEXT","SYSTEMROOT","WINDIR","COMSPEC","TEMP","TMP","HOME","USERPROFILE","LANG","LC_ALL","VIRTUAL_ENV"}
        env={k:v for k,v in os.environ.items() if k.upper() in allow}
        env["PYTHONNOUSERSITE"]="1"
        env["PYTHONDONTWRITEBYTECODE"]="1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"
        env.pop("PYTHONSTARTUP",None)
        return env

    def _truncate(self,value):
        value=value or ""
        if len(value)<=self.max_output_chars: return value,False
        return value[:self.max_output_chars]+"\n...[truncated by GUPPI]",True

    def _validate_python(self, argv: list[str], exe_name: str, cwd: Path):
        if exe_name not in {"python", "python3", "py"}:
            return
        if len(argv) == 1:
            raise ToolValidationError("interactive_python_not_allowed")
        if any(arg in {"-c", "-i", "-"} for arg in argv[1:]):
            raise ToolValidationError("arbitrary_python_execution_not_allowed")
        if argv[1] in {"--version","-V"}:
            if len(argv)!=2: raise ToolValidationError("python_version_extra_args_not_allowed")
            return
        if argv[1] != "-m" or len(argv)<3:
            raise ToolValidationError("python_invocation_not_allowlisted")
        module=argv[2]
        rest=argv[3:]
        if module == "compileall":
            self._validate_compileall(rest,cwd); return
        if module == "unittest":
            self._validate_unittest(rest,cwd); return
        if module == "pytest":
            self._validate_pytest(rest,cwd); return
        raise ToolValidationError("python_module_not_allowlisted")

    def _inside(self,value,cwd):
        candidate=(cwd/value).resolve(strict=False)
        try: candidate.relative_to(cwd.resolve())
        except ValueError as exc: raise ToolValidationError("test_path_outside_cwd") from exc

    def _validate_compileall(self,args,cwd):
        allowed_flags={"-q","-f"}
        paths=[]
        for a in args:
            if a in allowed_flags: continue
            if a.startswith("-"): raise ToolValidationError("unsupported_compileall_argument")
            self._inside(a,cwd); paths.append(a)
        if not paths: raise ToolValidationError("compileall_path_required")

    def _validate_unittest(self,args,cwd):
        if not args or args[0] != "discover":
            raise ToolValidationError("only_unittest_discover_allowed")
        i=1
        while i<len(args):
            a=args[i]
            if a in {"-v","-q","-f"}: i+=1; continue
            if a in {"-s","--start-directory","-t","--top-level-directory"}:
                if i+1>=len(args): raise ToolValidationError("unittest_path_missing")
                self._inside(args[i+1],cwd); i+=2; continue
            if a in {"-p","--pattern"}:
                if i+1>=len(args): raise ToolValidationError("unittest_pattern_missing")
                if "/" in args[i+1] or "\\" in args[i+1]: raise ToolValidationError("unittest_pattern_must_be_filename_pattern")
                i+=2; continue
            raise ToolValidationError("unsupported_unittest_argument")

    def _validate_pytest(self,args,cwd):
        allowed_flags={"-q","-x","--disable-warnings","--tb=short","--tb=line","--tb=no"}
        for a in args:
            if a in allowed_flags: continue
            if a.startswith("--maxfail=") and a.split("=",1)[1].isdigit() and int(a.split("=",1)[1])<=10: continue
            if a.startswith("-"): raise ToolValidationError("unsupported_pytest_argument")
            self._inside(a,cwd)
