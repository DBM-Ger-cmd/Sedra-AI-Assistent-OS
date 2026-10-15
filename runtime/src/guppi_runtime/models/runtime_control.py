from __future__ import annotations
from pathlib import Path
from urllib.request import urlopen
import json, os, shutil, subprocess


class RuntimeControlError(RuntimeError):
    pass


class CommandRunner:
    def run(self, argv, *, timeout=30):
        # utf-8 + replace: `lms` prints spinner glyphs that the Windows ANSI code page cannot decode. stdin is closed so a prompt can never hang.
        proc = subprocess.run(list(argv), capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout, shell=False)
        if proc.returncode != 0:
            raise RuntimeControlError(f"command_failed:{proc.returncode}:{proc.stderr.strip()}")
        return proc.stdout.strip()


class LMStudioRuntimeController:
    id = "lm-studio"

    def __init__(self, executable=None, runner=None, endpoint="http://127.0.0.1:1234", enabled=True):
        # enabled=False: never run `lms` (every call wakes the LM Studio/Bionic service, which can hang and reopen itself)
        self.executable = None if not enabled else (str(executable) if executable else shutil.which("lms"))
        self.runner = runner or CommandRunner()
        self.endpoint = endpoint.rstrip("/")

    def available(self):
        return bool(self.executable)

    def _json(self, args, timeout=30):
        if not self.available():
            raise RuntimeControlError("lms_cli_not_found")
        out = self.runner.run([self.executable, *args], timeout=timeout)
        try:
            return json.loads(out or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeControlError("invalid_lms_json") from exc

    def status(self):
        if not self.available():
            return {"provider": self.id, "available": False, "daemon": None, "server": None}
        try:
            daemon = self._json(["daemon", "status", "--json"])
        except Exception as exc:
            daemon = {"error": str(exc)}
        try:
            server = self._json(["server", "status", "--json", "--quiet"])
        except Exception as exc:
            server = {"error": str(exc)}
        return {"provider": self.id, "available": True, "executable": self.executable, "daemon": daemon, "server": server}

    def list_models(self):
        return self._json(["ls", "--json"])

    def loaded_models(self):
        return self._json(["ps", "--json"])

    def daemon_up(self):
        return self._json(["daemon", "up", "--json"], timeout=60)

    def daemon_down(self):
        if not self.available(): raise RuntimeControlError("lms_cli_not_found")
        return {"output": self.runner.run([self.executable, "daemon", "down"], timeout=60)}

    def server_start(self, port=1234):
        if not self.available(): raise RuntimeControlError("lms_cli_not_found")
        port = int(port)
        if not 1 <= port <= 65535: raise ValueError("invalid_port")
        out = self.runner.run([self.executable, "server", "start", "--port", str(port), "--bind", "127.0.0.1"], timeout=60)
        return {"output": out, "endpoint": f"http://127.0.0.1:{port}"}

    def server_stop(self):
        if not self.available(): raise RuntimeControlError("lms_cli_not_found")
        return {"output": self.runner.run([self.executable, "server", "stop"], timeout=60)}

    def load_model(self, model_key, *, context_length=None, gpu=None, identifier=None, estimate_only=False, yes=False, parallel=None, mtp=None, server=None):
        if not self.available(): raise RuntimeControlError("lms_cli_not_found")
        if not model_key: raise ValueError("model_key_required")
        argv = [self.executable, "load", str(model_key)]
        if context_length is not None:
            argv += ["--context-length", str(int(context_length))]
        if gpu is not None:
            gpu = str(gpu)
            if gpu not in {"off", "max", "auto"}:
                try:
                    value = float(gpu)
                    if not 0.0 <= value <= 1.0: raise ValueError
                except ValueError as exc:
                    raise ValueError("invalid_gpu_offload") from exc
            argv += ["--gpu", gpu]
        if parallel is not None:
            argv += ["--parallel", str(int(parallel))]
        if mtp is not None:                                  # speculative MTP drafting: explicit either way, never left to the model's default
            argv.append("--speculative-draft-mtp" if mtp else "--no-speculative-draft-mtp")
        if identifier:
            argv += ["--identifier", str(identifier)]
        if estimate_only:
            argv.append("--estimate-only")
        if yes:
            argv.append("--yes")
        return {"output": self.runner.run(argv, timeout=120), "command": argv[1:]}

    def unload_model(self, model_key=None, *, all_models=False):
        if not self.available(): raise RuntimeControlError("lms_cli_not_found")
        if all_models:
            argv = [self.executable, "unload", "--all"]
        elif model_key:
            argv = [self.executable, "unload", str(model_key)]
        else:
            raise ValueError("model_key_or_all_required")
        return {"output": self.runner.run(argv, timeout=60), "command": argv[1:]}


class LlamaCppRuntimeController:
    id = "llama-cpp-server"

    def __init__(self, executable=None, runner=None, endpoint="http://127.0.0.1:8080", process_factory=None):
        self.runner = runner or CommandRunner()
        self.endpoint = endpoint.rstrip("/")
        self.executable = str(executable) if executable else (shutil.which("llama-server") or shutil.which("llama"))
        self.process_factory = process_factory or subprocess.Popen
        self._process = None
        self._log_handle = None

    def available(self):
        return bool(self.executable)

    def _uses_unified_cli(self):
        return bool(self.executable) and Path(self.executable).stem.lower() in {"llama", "llama.exe"}

    def status(self):
        available = self.available()
        healthy = False
        if available:
            try:
                with urlopen(self.endpoint + "/health", timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    healthy = resp.status == 200 and data.get("status") == "ok"
            except Exception:
                healthy = False
        managed_running = bool(self._process is not None and self._process.poll() is None)
        return {"provider": self.id, "available": available, "executable": self.executable, "endpoint": self.endpoint, "healthy": healthy, "managed_running": managed_running, "managed_pid": getattr(self._process, "pid", None) if managed_running else None}

    def build_start_command(self, model_path: Path, profile: dict, *, port=8080):
        if not self.available(): raise RuntimeControlError("llama_cpp_binary_not_found")
        p = Path(model_path).resolve()
        if not p.exists() or not p.is_file() or p.suffix.lower() != ".gguf":
            raise ValueError("valid_gguf_model_required")
        port = int(port)
        if not 1 <= port <= 65535: raise ValueError("invalid_port")
        argv = [self.executable]
        if self._uses_unified_cli():
            argv.append("serve")
        argv += ["--model", str(p), "--host", "127.0.0.1", "--port", str(port)]
        context = (profile.get("context") or {}).get("recommended")
        if context: argv += ["--ctx-size", str(int(context))]
        threads = profile.get("cpu_threads")
        if isinstance(threads, int): argv += ["--threads", str(threads)]
        batch = profile.get("batch_size")
        if batch: argv += ["--batch-size", str(int(batch))]
        ubatch = profile.get("microbatch_size")
        if ubatch: argv += ["--ubatch-size", str(int(ubatch))]
        layers = profile.get("gpu_layers")
        if layers is not None:
            argv += ["--n-gpu-layers", str(layers)]
        parallel = profile.get("parallelism")
        if parallel: argv += ["--parallel", str(int(parallel))]
        kv = profile.get("kv_cache") or {}
        precision = kv.get("precision")
        if precision == "fp16":
            precision = "f16"
        if precision in {"f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"}:
            argv += ["--cache-type-k", precision, "--cache-type-v", precision]
        if kv.get("placement") == "cpu":
            argv += ["--no-kv-offload"]
        return argv
    def start_server(self, model_path: Path, profile: dict, *, port=8080, log_path: Path | None = None):
        if self._process is not None and self._process.poll() is None:
            raise RuntimeControlError("llama_cpp_server_already_managed")
        command = self.build_start_command(model_path, profile, port=port)
        log_path = Path(log_path or (Path(model_path).parent / "llama-server.log"))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = log_path.open("ab")
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": self._log_handle, "stderr": subprocess.STDOUT, "shell": False}
        if os.name != "nt":
            kwargs["start_new_session"] = True
        else:
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            self._process = self.process_factory(command, **kwargs)
        except Exception:
            self._log_handle.close(); self._log_handle = None
            raise
        return {"pid": getattr(self._process, "pid", None), "command": command, "log_path": str(log_path), "endpoint": f"http://127.0.0.1:{int(port)}"}

    def stop_server(self, timeout=10):
        if self._process is None or self._process.poll() is not None:
            if self._log_handle:
                self._log_handle.close(); self._log_handle = None
            self._process = None
            return {"stopped": False, "reason": "no_managed_process"}
        self._process.terminate()
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill(); self._process.wait(timeout=5)
        pid = getattr(self._process, "pid", None)
        if self._log_handle:
            self._log_handle.close(); self._log_handle = None
        self._process = None
        return {"stopped": True, "pid": pid}

