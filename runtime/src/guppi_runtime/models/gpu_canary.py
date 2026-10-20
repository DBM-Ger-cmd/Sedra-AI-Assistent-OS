"""GPU canary: a short health test of the graphics card before GUPPI puts a model on it (Captain 2026-10-11).

Why: on this PC (RTX 4070 Ti) the CUDA crashes ("illegal memory access", nvlddmkm 13/153) and the garbage answers of Qwen3.5, Gemma and
Qwen3-Coder came from the factory overclock. With the NVIDIA debug mode on (clocks at reference, valid only until the next Windows start)
Qwen3.5-9B Q6_K with flash attention ran 40/40 soak requests and every needle test up to 62k; without it, it failed at request 4.
The debug mode cannot be read by a script, so the canary repeats the sequence that used to break: 3 x 16k prompt, then 30k, each with a
hidden code that must come back (<modelle-test>/qwen35-9b-q6/guppi_canary.py, same steps).

When: once per Windows start (a pass is remembered with the boot time), and again after any llama-server crash (`invalidate`).
It starts its OWN llama-server (the small model, fully on the GPU, the settings of the successful runs: b11160, FA on, KV q8_0, ubatch 512,
1 slot) on its own port, so it takes about 25 s and never touches the caller's model. GUPPI never changes clocks or drivers itself; a failed
canary only blocks model loads and tells the Captain what to check.
"""
from __future__ import annotations

import ctypes
import json
import os
import random
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from .. import local_paths

STATE = Path(__file__).resolve().parents[4] / "runtime_data" / "gpu_canary.json"     # <GUPPI_Runtime>/runtime_data
STEPS_32K = (16000, 16000, 16000, 30000)
STEPS_16K = (8000, 8000, 8000, 14000)
WORDS = "alpha beta gamma delta kappa lambda sigma omega orbit vector signal matrix kernel buffer socket thread token cache layer".split()
HINT = "GPU instabil: Ist der NVIDIA-Debug-Modus aktiv (NVIDIA App, gilt nur bis zum Neustart)? Danach erneut laden."


class CanaryConfig:
    """llama_server.yaml, block `canary`. Absent or enabled: false means no canary (unit tests, other PCs)."""

    def __init__(self, raw):
        raw = raw or {}
        if not isinstance(raw, dict):
            raise ValueError("llama_server_config_invalid:canary")
        self.enabled = raw.get("enabled", False) is True
        self.gguf = local_paths.expand(raw.get("gguf"))
        self.disabled_reason = None
        if self.enabled and local_paths.unresolved(self.gguf):
            # The model folder is a placeholder this PC has not set (runtime/config/local_paths.yaml): no canary, like on any other PC.
            self.enabled, self.disabled_reason = False, "local_paths_missing"
        self.engine_build = raw.get("engine_build")
        self.port = raw.get("port", 8093)
        self.context = raw.get("context", 32768)
        self.timeout_s = raw.get("timeout_s", 300)
        self.config_error = self._problem()
        if self.config_error:
            # Entscheidung des Captains (2026-10-19): der Server startet trotzdem, ohne Canary; der Grund steht im Status und im Audit
            self.enabled, self.disabled_reason = False, self.config_error

    def _problem(self):
        """Der erste Fehler der Canary-Einstellungen oder None. Gilt nur, wenn der Canary eingeschaltet ist."""
        if not self.enabled: return None
        if not isinstance(self.gguf, str) or not self.gguf.lower().endswith(".gguf"): return "llama_server_config_invalid:canary.gguf"
        if self.engine_build is not None and not (isinstance(self.engine_build, str) and re.fullmatch(r"b\d{3,6}", self.engine_build)): return "llama_server_config_invalid:canary.engine_build"
        if type(self.port) is not int or not 1024 <= self.port <= 65535: return "llama_server_config_invalid:canary.port"
        if self.context not in (16384, 32768): return "llama_server_config_invalid:canary.context"
        if type(self.timeout_s) is not int or not 60 <= self.timeout_s <= 1800: return "llama_server_config_invalid:canary.timeout_s"
        return None


def boot_time():
    """Windows start as epoch seconds, rounded to the minute (stable across calls), or None off Windows."""
    try:
        uptime_ms = ctypes.windll.kernel32.GetTickCount64
        uptime_ms.restype = ctypes.c_ulonglong
        return int(round((time.time() - uptime_ms() / 1000) / 60) * 60)
    except Exception:
        return None


def read_state(path=STATE):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(state, path=STATE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def passed_this_boot(path=STATE, boot=None):
    state = read_state(path)
    boot = boot if boot is not None else boot_time()
    return bool(state.get("passed") and boot is not None and abs(int(state.get("boot") or 0) - boot) <= 120)


def invalidate(reason, path=STATE):
    """A server crashed: the next model load runs the canary again."""
    state = read_state(path)
    if state.get("passed"):
        write_state({**state, "passed": False, "invalidated": reason, "invalidated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, path)


def garbage(text):
    t = (text or "").strip()
    return not t or bool(re.search(r"(.)\1{9,}", t)) or len(set(t)) <= 3


def _filler(n, seed):
    r = random.Random(seed)
    return " ".join(r.choice(WORDS) + str(r.randint(0, 99)) + (".\n" if i % 14 == 13 else "") for i in range(n))


def _post(endpoint, path, body, timeout):
    req = urllib.request.Request(endpoint + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def run_steps(endpoint, steps, post=_post, timeout=600):
    """The canary sequence against a running server. Returns (ok, rows); stops at the first bad step."""
    rows = []
    for i, size in enumerate(steps):
        seed = 5000 + i
        code = f"ZX-{random.Random(seed).randint(100000, 999999)}"
        started = time.monotonic()
        try:
            per_400 = len(post(endpoint, "/tokenize", {"content": _filler(400, seed)}, 60)["tokens"]) / 400
            text = _filler(max(50, int((size - 200) / per_400)), seed)
            cut = text.rfind("\n", 0, len(text) // 3)
            text = text[:cut] + f"\nDer geheime Projektcode lautet {code}.\n" + text[cut:]
            reply = post(endpoint, "/v1/chat/completions", {"messages": [{"role": "user", "content": text + "\n\nWie lautet der geheime Projektcode? Antworte nur mit dem Code."}],
                                                           "max_tokens": 40, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}, timeout)
        except Exception as exc:
            rows.append({"step": i, "size": size, "result": "server_error", "detail": f"{type(exc).__name__}: {exc}"[:200]})
            return False, rows
        answer = (reply["choices"][0]["message"].get("content") or "").strip()
        result = "ok" if code in answer and not garbage(answer) else ("garbage" if garbage(answer) else "wrong")
        rows.append({"step": i, "size": size, "result": result, "seconds": round(time.monotonic() - started, 1), "answer": answer[:40]})
        if result != "ok":
            return False, rows
    return True, rows


def _healthy(endpoint):
    try:
        with urllib.request.urlopen(endpoint + "/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def run_canary(canary, executable_dir, *, popen=subprocess.Popen, steps_runner=run_steps, healthy=_healthy, sleep=time.sleep,
               state_path=STATE, log_dir=None):
    """Start the canary server, run the steps, stop it, remember the result. Returns the state dict (key `passed`)."""
    from ..models.llama_server_runtime import build_command          # late import: llama_server_runtime calls into this module
    endpoint = f"http://127.0.0.1:{canary.port}"
    state = {"boot": boot_time(), "at": time.strftime("%Y-%m-%d %H:%M:%S"), "engine_dir": str(executable_dir), "gguf": canary.gguf,
             "context": canary.context, "settings": "fa on, kv q8_0, ubatch 512, np 1"}
    if healthy(endpoint):
        state.update(passed=False, result="port_in_use", detail=f"port {canary.port} already answers")
        write_state(state, state_path)
        return state
    if not Path(canary.gguf).is_file():
        # 2026-10-16: build_command used to raise ValueError("valid_gguf_model_required") here, which read as a broken MODEL recipe.
        # The canary model is simply not where runtime/config/local_paths.yaml puts it: say so, and refuse as a failed canary.
        state.update(passed=False, result="gguf_missing", detail=str(canary.gguf))
        write_state(state, state_path)
        return state
    argv = build_command(Path(executable_dir) / "llama-server.exe", gguf=canary.gguf, context=canary.context, host="127.0.0.1", port=canary.port,
                         alias="gpu-canary", gpu_layers=99, parallel=1, kv_type="q8_0", flash_attn="on", reasoning="off", ubatch=512, jinja=True)
    env = dict(os.environ)
    env["PATH"] = str(executable_dir) + os.pathsep + env.get("PATH", "")
    log_path = Path(log_dir or Path(state_path).parent) / "gpu_canary_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    started = time.monotonic()
    with log_path.open("wb") as log:
        proc = popen(argv, cwd=str(executable_dir), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, shell=False, creationflags=flags)
    try:
        while not healthy(endpoint):
            if proc.poll() is not None:
                state.update(passed=False, result="server_exited_during_start", detail=f"exit {proc.poll()}")
                write_state(state, state_path)
                return state
            if time.monotonic() - started > canary.timeout_s:
                state.update(passed=False, result="start_timeout")
                write_state(state, state_path)
                return state
            sleep(0.5)
        ok, rows = steps_runner(endpoint, STEPS_32K if canary.context >= 32768 else STEPS_16K)
        if ok and proc.poll() is not None:
            ok, rows = False, rows + [{"result": "server_died"}]
        state.update(passed=ok, result="ok" if ok else rows[-1]["result"], steps=rows, seconds=round(time.monotonic() - started, 1))
        write_state(state, state_path)
        return state
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()


def ensure(canary, executable_dir, **kwargs):
    """None when the GPU may be used (canary off, or passed since this Windows start); else the failed state dict."""
    if not canary or not canary.enabled:
        return None
    path = kwargs.get("state_path", STATE)
    if passed_this_boot(path):
        return None
    state = run_canary(canary, executable_dir, **kwargs)
    return None if state.get("passed") else state
