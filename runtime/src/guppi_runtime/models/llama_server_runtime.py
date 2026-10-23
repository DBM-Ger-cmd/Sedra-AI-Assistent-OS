"""GUPPI starts and watches its own llama-server (Phase 8f). No LM Studio in the loop.

Why: LM Studio decides some things for GUPPI. Its stored per-model defaults set KV types, slots and a reasoning budget, a model can
be reloaded behind GUPPI's back with those defaults, and on this PC its engine died with "CUDA error: illegal memory access" under
long generations. A llama-server that GUPPI starts itself is a process GUPPI can see: every load option is explicit, a crash is an
exit code, nothing reloads silently, and a field the server does not know is ignored.

The engine is either GUPPI's own (`engine_source: guppi`, since 2026-10-03): the official llama.cpp release installed by
engine_provision.py under engines/llama.cpp/<build>/ with a manifest of file hashes, checked before use and never replaced by a
fallback; or (`engine_source: lmstudio`, the earlier default) the `llama-server.exe` that ships with LM Studio, pinned by version and
only read, never changed.

The class has the same small surface as the LM Studio controller (loaded_models / load_model / unload_model), so `ModelLoader` drives
both the same way: one model at a time on the card, started with the context the router resolved, verified through /props afterwards,
stopped explicitly. Only structured options are accepted; there is no free-form argument list, and the host is always loopback.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

import yaml

from ..models import gpu_canary
from ..models.runtime_control import RuntimeControlError

KV_TYPES = frozenset({"f16", "bf16", "q8_0", "q4_0"})
SPEC_TYPES = frozenset({"none", "draft-mtp"})
REASONING = frozenset({"auto", "on", "off"})
# How the server returns thinking. Kept as an option; for gpt-oss it is NOT enough (see `jinja` below).
REASONING_FORMATS = frozenset({"none", "deepseek", "deepseek-legacy", "auto"})
# `jinja: false` (--no-jinja) uses the built-in chat template and hands gpt-oss' raw Harmony output through. Needed because with
# the Jinja template the server's own parser rejects a correct JSON answer that carries `<|constrain|>JSON` with HTTP 500.
# Measured 2026-10-02, 3 runs each: default / --reasoning-format none / fence prompt fail 1-3 of 3, --no-jinja 3 of 3 OK.
# The adapter (models/openai_local.split_harmony) separates the final channel from the thinking.


class LlamaServerConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("llama_server_config_invalid")
        self.enabled = self._bool(raw, "enabled", False)
        # Speculative MTP drafting on this direct path. Measured: no crash in 4 of 4 long runs and about twice the speed (qwen). This is
        # the global switch; a recipe also has to ask for it (profile.server.mtp), because only some models carry an MTP head.
        self.mtp = self._bool(raw, "mtp", True)
        self.backend_version = raw.get("backend_version", "2.49.0")
        if not isinstance(self.backend_version, str) or not re.fullmatch(r"latest|\d+(\.\d+){1,3}", self.backend_version):
            raise ValueError("llama_server_config_invalid:backend_version")
        self.backend_dir = self._path(raw, "backend_dir")            # explicit directory wins over discovery
        self.engine_source = raw.get("engine_source", "lmstudio")
        if self.engine_source not in {"lmstudio", "guppi"}:
            raise ValueError("llama_server_config_invalid:engine_source")
        self.engine_build = raw.get("engine_build")
        # A measurement may run on another installed engine without touching this file (2026-10-11: the stable runs used b11160).
        if os.environ.get("GUPPI_ENGINE_BUILD") and re.fullmatch(r"b\d{3,6}", os.environ["GUPPI_ENGINE_BUILD"]):
            self.engine_build = os.environ["GUPPI_ENGINE_BUILD"]
        self.engine_assets = raw.get("engine_assets") or {}
        self.engine_root = self._path(raw, "engine_root")             # default: <GUPPI_Runtime>/engines
        if self.engine_source == "guppi" and (not isinstance(self.engine_build, str) or not re.fullmatch(r"b\d{3,6}", self.engine_build)):
            raise ValueError("llama_server_config_invalid:engine_build")
        self.vendor_dir = self._path(raw, "vendor_dir")
        self.host = raw.get("host", "127.0.0.1")
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("llama_server_config_invalid:host_must_be_loopback")
        self.port = self._int(raw, "port", 8089, 1024, 65535)
        self.startup_timeout_s = self._int(raw, "startup_timeout_s", 180, 5, 900)
        self.stop_timeout_s = self._int(raw, "stop_timeout_s", 20, 1, 120)
        self.flash_attn = raw.get("flash_attn", "on")
        self.canary = gpu_canary.CanaryConfig(raw.get("canary"))      # GPU health test before the first load after a Windows start or a crash
        if self.flash_attn not in {"on", "off", "auto"}:
            raise ValueError("llama_server_config_invalid:flash_attn")
        self.log_dir = raw.get("log_dir", "llama_server")
        if not isinstance(self.log_dir, str) or not self.log_dir or ".." in Path(self.log_dir).parts or Path(self.log_dir).is_absolute() or self.log_dir.startswith(("/", "\\")) or Path(self.log_dir).drive:
            raise ValueError("llama_server_config_invalid:log_dir")

    @staticmethod
    def _bool(raw, key, default):
        value = raw.get(key, default)
        if not isinstance(value, bool):
            raise ValueError(f"llama_server_config_invalid:{key}")
        return value

    @staticmethod
    def _int(raw, key, default, low, high):
        value = raw.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"llama_server_config_invalid:{key}")
        return value

    @staticmethod
    def _path(raw, key):
        value = raw.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError(f"llama_server_config_invalid:{key}")
        return value

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("llama_server_config_missing")
        return cls((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("llama_server") or {})


def discover_backend(config, home=None):
    """(backend_dir, vendor_dir) of the llama-server to use, or (None, None). Reads directories only.

    engine_source guppi: only GUPPI's own engine (engines/llama.cpp/<engine_build>), and only if its manifest and llama-server.exe
    check out. There is deliberately NO fallback to LM Studio: a missing or changed engine means "not available", visibly."""
    if config.engine_source == "guppi":
        from ..models.engine_provision import DEFAULT_ROOT, engine_dir, verify_engine
        root = Path(config.engine_root) if config.engine_root else DEFAULT_ROOT
        ok, _reason = verify_engine(root, config.engine_build)
        if not ok:
            return None, None
        folder = engine_dir(root, config.engine_build)
        return folder, folder                                        # the CUDA runtime DLLs are unpacked next to the server
    if config.backend_dir:
        backend = Path(config.backend_dir)
        vendor = Path(config.vendor_dir) if config.vendor_dir else None
        return (backend, vendor) if (backend / "llama-server.exe").is_file() else (None, None)
    root = Path(home or Path.home()) / ".lmstudio" / "extensions" / "backends"
    candidates = []
    for folder in root.glob("llama.cpp-win-x86_64-nvidia-cuda12-avx2-*"):
        match = re.search(r"-(\d+(?:\.\d+)+)$", folder.name)
        if match and (folder / "llama-server.exe").is_file():
            candidates.append((tuple(int(x) for x in match.group(1).split(".")), match.group(1), folder))
    if not candidates:
        return None, None
    if config.backend_version == "latest":
        chosen = max(candidates)[2]
    else:
        chosen = next((c[2] for c in candidates if c[1] == config.backend_version), None)
    vendor = Path(config.vendor_dir) if config.vendor_dir else root / "vendor" / "win-llama-cuda12-vendor-v2"
    return (chosen, vendor if vendor.is_dir() else None) if chosen else (None, None)


def build_command(executable, *, gguf, context, host, port, alias, gpu_layers=99, parallel=1, kv_type="f16", flash_attn="on",
                  spec_type="none", reasoning="auto", reasoning_budget=None, mmproj=None, cache_ram=None, ctx_checkpoints=None, n_cpu_moe=None,
                  reasoning_format=None, jinja=None, ubatch=None, mmap=None, kv_type_k=None, kv_type_v=None):
    """The argument list for one llama-server. Pure: validates and builds, starts nothing. kv_type_k / kv_type_v: the key and the value cache can differ (2026-10-09: a quantized V cache needs flash attention, a quantized K cache does not)."""
    if mmap is not None and not isinstance(mmap, bool):
        raise ValueError("invalid_mmap")
    if ubatch is not None and (type(ubatch) is not int or not 64 <= ubatch <= 8192):
        raise ValueError("invalid_ubatch")
    if reasoning_format is not None and reasoning_format not in REASONING_FORMATS:
        raise ValueError("invalid_reasoning_format")
    if jinja is not None and not isinstance(jinja, bool):
        raise ValueError("invalid_jinja")
    gguf = Path(gguf)
    if gguf.suffix.lower() != ".gguf" or not gguf.is_file():
        raise ValueError("valid_gguf_model_required")
    if type(context) is not int or not 256 <= context <= 1_048_576:
        raise ValueError("invalid_context_length")
    if type(parallel) is not int or not 1 <= parallel <= 8:
        raise ValueError("invalid_parallel")
    if type(gpu_layers) is not int or not 0 <= gpu_layers <= 999:
        raise ValueError("invalid_gpu_layers")
    if any(t is not None and t not in KV_TYPES for t in (kv_type_k, kv_type_v)):
        raise ValueError("invalid_server_option")
    if kv_type not in KV_TYPES or spec_type not in SPEC_TYPES or reasoning not in REASONING or flash_attn not in {"on", "off", "auto"}:
        raise ValueError("invalid_server_option")
    if reasoning_budget is not None and (type(reasoning_budget) is not int or not -1 <= reasoning_budget <= 65536):
        raise ValueError("invalid_reasoning_budget")
    if not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9._:/@-]{1,120}", alias):
        raise ValueError("invalid_alias")
    if cache_ram is not None and (type(cache_ram) is not int or not -1 <= cache_ram <= 262144):
        raise ValueError("invalid_cache_ram")
    if ctx_checkpoints is not None and (type(ctx_checkpoints) is not int or not 0 <= ctx_checkpoints <= 64):
        raise ValueError("invalid_ctx_checkpoints")
    if n_cpu_moe is not None and (type(n_cpu_moe) is not int or not 0 <= n_cpu_moe <= 999):
        raise ValueError("invalid_n_cpu_moe")
    argv = [str(executable), "-m", str(gguf), "-c", str(context), "-ngl", str(gpu_layers), "-np", str(parallel),
            "-ctk", kv_type_k or kv_type, "-ctv", kv_type_v or kv_type, "-fa", flash_attn, "--host", host, "--port", str(port), "--no-webui",
            "--alias", alias, "--spec-type", spec_type, "--reasoning", reasoning]
    if reasoning_budget is not None:
        argv += ["--reasoning-budget", str(reasoning_budget)]
    if reasoning_format is not None:
        argv += ["--reasoning-format", reasoning_format]
    if jinja is False:
        argv += ["--no-jinja"]
    if cache_ram is not None:
        argv += ["--cache-ram", str(cache_ram)]          # host-RAM prompt cache in MiB: 0 = off, -1 = unlimited, unset = the server's default (8192)
    if ctx_checkpoints is not None:
        argv += ["--ctx-checkpoints", str(ctx_checkpoints)]   # context checkpoints per slot: 0 = none, unset = the server's default (32)
    if mmap is False:
        # Read the weights into memory instead of mapping the file. With MoE experts in host RAM, mapping kept the file pages resident
        # NEXT TO the copy llama.cpp makes for its CPU kernels (2026-10-03, qwen3-coder: 22.7 GB working set, 0.6 GB RAM left).
        # Upstream llama.cpp replaced --no-mmap by --load-mode (b11371: "none" = read normally, no mapping).
        argv += ["--load-mode", "none"]
    if ubatch is not None:
        # Physical batch for prompt processing. With MoE experts in host RAM a bigger batch means fewer passes over the expert weights
        # per prompt (2026-10-03, qwen3-coder with all experts on the CPU read only ~170 tokens/s at the default 512). The logical
        # batch must be at least as large, so it is raised with it.
        argv += ["-b", str(max(2048, ubatch)), "-ub", str(ubatch)]
    if n_cpu_moe:
        argv += ["--n-cpu-moe", str(n_cpu_moe)]          # MoE models: expert weights of the first N layers stay in host RAM (the rest of the model uses the GPU)
    if mmproj:
        mm = Path(mmproj)
        if mm.suffix.lower() != ".gguf" or not mm.is_file():
            raise ValueError("valid_mmproj_required")
        argv += ["--mmproj", str(mm)]
    else:
        argv.append("--no-mmproj")                       # vision is not used by any role; the projector costs ~1.7 GiB of VRAM
    return argv


def _http_json(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8") or "{}")


class LlamaServerRuntime:
    id = "llama-cpp-server"
    launcher = ()      # a program that starts the server for a measurement (compute-sanitizer, 2026-10-09); set by a benchmark, never by a config file

    def __init__(self, config, state_dir, *, popen=subprocess.Popen, get_json=_http_json, sleep=time.sleep, monotonic=time.monotonic,
                 home=None, audit=None):
        self.config = config
        self.state_dir = Path(state_dir)
        self._popen, self._get_json, self._sleep, self._mono = popen, get_json, sleep, monotonic
        self.audit = audit
        self.executable_dir, self.vendor_dir = discover_backend(config, home)
        self._proc = None
        self._info = None
        self.last_exit = None

    # ---- facts
    @property
    def endpoint(self):
        host = "127.0.0.1" if self.config.host == "localhost" else self.config.host
        return f"http://{host}:{self.config.port}"

    def available(self):
        return self.executable_dir is not None

    def _audit(self, event, **payload):
        if self.audit:
            self.audit.append(event, component="llama-server", payload=payload)

    def _health(self):
        try:
            status, _ = self._get_json(self.endpoint + "/health")
            return status == 200
        except Exception:
            return False

    def _props(self):
        try:
            return self._get_json(self.endpoint + "/props")[1]
        except Exception:
            return {}

    def _reap(self):
        """A process that exited on its own is a crash. Say so once and forget the instance."""
        if self._proc is not None and self._proc.poll() is not None:
            self.last_exit = {"code": self._proc.poll(), "model": (self._info or {}).get("modelKey"), "at": time.time()}
            self._audit("LLAMA_SERVER_EXITED", **{k: v for k, v in self.last_exit.items() if k != "at"})
            if self.config.canary.enabled:
                gpu_canary.invalidate(f"server exited with {self.last_exit['code']} ({self.last_exit['model']})")
            self._proc = None
            self._info = None

    def status(self):
        self._reap()
        return {"provider": self.id, "available": self.available(), "endpoint": self.endpoint, "executable_dir": str(self.executable_dir) if self.executable_dir else None,
                "running": bool(self._info), "model": (self._info or {}).get("modelKey"), "context": (self._info or {}).get("contextLength"), "slots": (self._info or {}).get("slots"),
                "kv_cache_type": (self._info or {}).get("kv_cache_type"), "spec_type": (self._info or {}).get("spec_type"),
                "pid": getattr(self._proc, "pid", None), "last_exit": self.last_exit, **self._engine_facts()}

    def _engine_facts(self):
        facts = {"engine_source": self.config.engine_source}
        if self.config.engine_source == "guppi":
            from ..models.engine_provision import DEFAULT_ROOT, verify_engine
            root = Path(self.config.engine_root) if self.config.engine_root else DEFAULT_ROOT
            facts["engine_build"] = self.config.engine_build
            facts["engine_check"] = verify_engine(root, self.config.engine_build)[1]
        return facts

    # ---- controller surface (same shape as LMStudioRuntimeController)
    def loaded_models(self):
        self._reap()
        if self._info is None or not self._health():
            return []
        return [dict(self._info)]

    def load_model(self, model_key, *, context_length=None, gpu=None, identifier=None, estimate_only=False, yes=False, parallel=None,
                   mtp=None, server=None):
        # `mtp` (the loader's own flag) belongs to the LM Studio path and is ignored here: this runtime decides from its own
        # global switch and from the recipe.
        if estimate_only:
            return {"output": ""}                        # there is no estimator here; the recipe carries measured numbers
        if not self.available():
            raise RuntimeControlError("llama_server_not_found")
        if not isinstance(server, dict) or not server.get("gguf"):
            raise ValueError("server_profile_required")
        self._reap()
        if self._info is not None:
            raise RuntimeControlError("server_already_running")
        if self._health():
            raise RuntimeControlError(f"port_in_use:{self.config.port}")
        self._check_gpu()
        alias = identifier or model_key
        use_mtp = bool(self.config.mtp and server.get("mtp", False))
        layers = {"max": 99, "off": 0}.get(gpu, 99 if gpu is None else None)
        if layers is not None and server.get("n_gpu_layers") is not None:
            layers = server["n_gpu_layers"]      # a DENSE model that does not fit the card: the number of layers on the GPU (a MoE model uses n_cpu_moe instead)
        if layers is None:
            raise ValueError("invalid_gpu_offload")
        argv = build_command(self.executable_dir / "llama-server.exe", gguf=server["gguf"], context=context_length, host=self.config.host if self.config.host != "localhost" else "127.0.0.1",
                             port=self.config.port, alias=alias, gpu_layers=layers, parallel=parallel or 1, kv_type=server.get("kv_cache_type", "f16"), kv_type_k=server.get("kv_cache_type_k"), kv_type_v=server.get("kv_cache_type_v"),
                             flash_attn=server.get("flash_attn", self.config.flash_attn),   # per recipe since 2026-10-03 (qwen crash tests)
                             spec_type="draft-mtp" if use_mtp else "none", reasoning=server.get("reasoning", "auto"),
                             reasoning_budget=server.get("reasoning_budget"), mmproj=server.get("mmproj"), cache_ram=server.get("cache_ram"),
                             ctx_checkpoints=server.get("ctx_checkpoints"), n_cpu_moe=server.get("n_cpu_moe"),
                             reasoning_format=server.get("reasoning_format"), jinja=server.get("jinja"), ubatch=server.get("ubatch"),
                             mmap=server.get("mmap"))
        argv = [*self.launcher, *argv]
        self.state_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.state_dir / "server.log"
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(str(p) for p in (self.executable_dir, self.vendor_dir) if p) + os.pathsep + env.get("PATH", "")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        with log_path.open("wb") as log:
            self._proc = self._popen(argv, cwd=str(self.executable_dir), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     shell=False, creationflags=flags)
        started = self._mono()
        while True:
            if self._proc.poll() is not None:
                code = self._proc.poll(); self._proc = None
                raise RuntimeControlError(f"server_exited_during_start:{code}:{self._log_tail(log_path)}")
            if self._health():
                break
            if self._mono() - started > self.config.startup_timeout_s:
                self._kill()
                raise RuntimeControlError(f"server_start_timeout:{self.config.startup_timeout_s}s:{self._log_tail(log_path)}")
            self._sleep(0.5)
        # The window the server really applies PER SLOT (`-c` is split over the slots and /props reports one slot's window, b11160);
        # a build that reports the sum is divided back. Not the one that was asked for.
        slots = parallel or 1
        applied = ((self._props().get("default_generation_settings") or {}).get("n_ctx"))
        if type(applied) is int:
            per_slot = applied // slots if slots > 1 and context_length is not None and applied == context_length else applied
        else:
            per_slot = context_length // slots if context_length is not None else None
        self._info = {"modelKey": model_key, "identifier": alias, "contextLength": per_slot, "slots": slots,
                      "pid": self._proc.pid, "kv_cache_type": server.get("kv_cache_type", "f16"), "spec_type": "draft-mtp" if use_mtp else "none"}
        self._write_state()
        self._audit("LLAMA_SERVER_STARTED", model=model_key, context=self._info["contextLength"], pid=self._proc.pid, seconds=round(self._mono() - started, 1))
        return {"output": f"started {alias}", "command": argv[1:]}

    def _check_gpu(self):
        """Run the GPU canary when it has not passed since this Windows start (or since the last crash); refuse the load if it fails."""
        if not self.config.canary.enabled:
            return
        engine = self.executable_dir
        if self.config.canary.engine_build and self.config.engine_source == "guppi":
            from ..models.engine_provision import DEFAULT_ROOT, engine_dir, verify_engine
            root = Path(self.config.engine_root) if self.config.engine_root else DEFAULT_ROOT
            if not verify_engine(root, self.config.canary.engine_build)[0]:
                raise RuntimeControlError(f"gpu_canary_engine_missing:{self.config.canary.engine_build}")
            engine = engine_dir(root, self.config.canary.engine_build)
        failed = gpu_canary.ensure(self.config.canary, engine)
        if failed is not None:
            self._audit("GPU_CANARY_FAILED", result=failed.get("result"), steps=failed.get("steps"))
            if failed.get("result") == "gguf_missing":
                # not a GPU fault: the canary's model file is not at the folder of runtime/config/local_paths.yaml (2026-10-16)
                raise RuntimeControlError(f"gpu_canary_gguf_missing:{failed.get('detail')}")
            raise RuntimeControlError(f"gpu_canary_failed:{failed.get('result')}: {gpu_canary.HINT}")

    def unload_model(self, model_key=None, *, all_models=False):
        self._reap()
        if self._proc is None:
            self._info = None
            return {"output": "nothing to stop"}
        if not all_models and model_key and model_key not in {(self._info or {}).get("identifier"), (self._info or {}).get("modelKey")}:
            raise ValueError("unknown_instance")
        self._kill()
        self._audit("LLAMA_SERVER_STOPPED", model=(self._info or {}).get("modelKey"))
        self._info = None
        self._clear_state()
        return {"output": "stopped"}

    # ---- process handling
    def _kill(self):
        proc = self._proc
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=self.config.stop_timeout_s)
        except Exception:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
        self._proc = None

    @staticmethod
    def _log_tail(path, lines=4):
        try:
            tail = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-lines:]
            return " | ".join(t.strip()[:120] for t in tail)
        except OSError:
            return "no log"

    def _write_state(self):
        try:
            (self.state_dir / "state.json").write_text(json.dumps({"info": self._info, "port": self.config.port}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _clear_state(self):
        try:
            (self.state_dir / "state.json").unlink(missing_ok=True)
        except OSError:
            pass

    def leftover(self):
        """A server from an earlier GUPPI run still answers on our port (state file present, no process of ours). Reported, never killed here."""
        state = self.state_dir / "state.json"
        return bool(self._proc is None and state.exists() and self._health())
