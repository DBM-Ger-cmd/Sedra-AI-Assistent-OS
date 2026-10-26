from __future__ import annotations
from contextlib import nullcontext
from pathlib import Path
from copy import deepcopy
import ctypes
import math
import os
import statistics
import threading
import time

from ..models import LMStudioAdapter, LlamaCppServerAdapter
from ..core.util import atomic_write_json, load_json, utcnow


DEFAULT_PROMPT = "Reply with a short sentence confirming that the local model is ready."


def _rss_mb_linux(pid: int):
    p = Path(f"/proc/{int(pid)}/status")
    if not p.exists():
        return None
    try:
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("VmRSS:"):
                return round(float(line.split()[1]) / 1024.0, 2)
    except Exception:
        return None
    return None


def _rss_mb_windows(pid: int):
    if os.name != "nt":
        return None
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
        if not handle:
            return None
        counters = PMC(); counters.cb = ctypes.sizeof(PMC)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        ctypes.windll.kernel32.CloseHandle(handle)
        if not ok:
            return None
        return round(counters.WorkingSetSize / (1024 ** 2), 2)
    except Exception:
        return None


def process_rss_mb(pid: int | None):
    if not pid:
        return None
    if os.name == "nt":
        return _rss_mb_windows(pid)
    return _rss_mb_linux(pid)


class MemorySampler:
    def __init__(self, pid, interval=0.10):
        self.pid = pid
        self.interval = float(interval)
        self.samples = []
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not self.pid:
            return self
        def loop():
            while not self._stop.is_set():
                value = process_rss_mb(self.pid)
                if value is not None:
                    self.samples.append(value)
                self._stop.wait(self.interval)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        return self

    @property
    def peak_mb(self):
        return max(self.samples) if self.samples else None


class BenchmarkStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = load_json(self.path, {"schema": 1, "runs": {}}) or {"schema": 1, "runs": {}}
        self._data.setdefault("schema", 1)
        self._data.setdefault("runs", {})

    def save(self, record: dict):
        self._data["runs"][record["benchmark_id"]] = record
        atomic_write_json(self.path, self._data)
        return record

    def get(self, benchmark_id):
        rec = self._data["runs"].get(benchmark_id)
        if not rec:
            raise KeyError("unknown_benchmark_id")
        return deepcopy(rec)

    def list(self):
        return sorted((deepcopy(x) for x in self._data["runs"].values()), key=lambda x: x.get("created_at", ""), reverse=True)


class ModelBenchmarkRunner:
    def __init__(self, manager, hardware, profile_store, data_root: Path, audit=None, policy_path: Path | None = None):
        self.manager = manager
        self.hardware = hardware
        self.profile_store = profile_store
        self.data_root = Path(data_root)
        self.audit = audit
        self.store = BenchmarkStore(self.data_root / "models" / "benchmarks.json")
        self.policy = self._load_policy(policy_path)
        self._lab = None
        self._held = None                      # the GPU lease of a managed server that keeps running (keep_running)

    @staticmethod
    def _load_policy(path):
        import yaml
        if path and Path(path).exists():
            return (yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}).get("benchmark_policy", {})
        return {}

    def _adapter(self, provider, endpoint):
        if provider == "llama-cpp-server":
            return LlamaCppServerAdapter(endpoint, timeout=int(self.policy.get("request_timeout_seconds", 120)))
        if provider == "lm-studio":
            return LMStudioAdapter(endpoint, timeout=int(self.policy.get("request_timeout_seconds", 120)))
        raise ValueError("unsupported_benchmark_provider")

    def _wait_ready(self, adapter, timeout=None):
        timeout = float(timeout or self.policy.get("startup_timeout_seconds", 180))
        interval = float(self.policy.get("ready_poll_seconds", 0.25))
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            if adapter.health():
                return round(time.perf_counter() - start, 4)
            time.sleep(interval)
        raise TimeoutError("model_runtime_startup_timeout")

    @staticmethod
    def _token_info(result):
        raw = result.get("raw") or {}
        usage = raw.get("usage") or {}
        value = usage.get("completion_tokens")
        if isinstance(value, int) and value >= 0:
            return value, False, "provider_usage"
        text = result.get("content") or ""
        # Explicit fallback only. Not used as exact tokenizer accounting.
        estimate = max(1, int(math.ceil(len(text) / 4.0))) if text else 0
        return estimate, True, "char_estimate_4_per_token"

    def _run_samples(self, adapter, model, prompt, repeats, warmups, max_tokens):
        repeats = max(1, int(repeats))
        warmups = max(0, int(warmups))
        messages = [{"role": "user", "content": prompt or DEFAULT_PROMPT}]
        hw=getattr(self.manager,"hardware_manager",None)
        for _ in range(warmups):
            with hw.job() if hw else nullcontext():
                adapter.chat(messages, model=model, max_tokens=max_tokens, temperature=0)
        samples = []
        errors = []
        for index in range(repeats):
            started = time.perf_counter()
            try:
                with hw.job() if hw else nullcontext():
                    result = adapter.chat(messages, model=model, max_tokens=max_tokens, temperature=0)
                elapsed = max(0.000001, time.perf_counter() - started)
                tokens, estimated, source = self._token_info(result)
                samples.append({
                    "index": index + 1,
                    "elapsed_seconds": round(elapsed, 6),
                    "completion_tokens": tokens,
                    "tokens_estimated": estimated,
                    "token_source": source,
                    "tokens_per_second": round(tokens / elapsed, 3) if tokens else 0.0,
                })
            except Exception as exc:
                errors.append({"index": index + 1, "error": f"{type(exc).__name__}:{exc}"})
        return samples, errors

    def _qualify(self, metrics, repeats):
        q = self.policy.get("qualification", {})
        min_repeats = int(q.get("min_repeats", 2))
        min_success_rate = float(q.get("min_success_rate", 1.0))
        min_tps = float(q.get("min_median_tokens_per_second", 0.1))
        max_start = float(q.get("max_startup_seconds", 180))
        max_ram_ratio = float(q.get("max_peak_rss_ratio_of_ram", 0.90))
        reasons = []
        success_rate = metrics.get("successful_runs", 0) / max(1, int(repeats))
        if repeats < min_repeats:
            reasons.append("insufficient_repeats")
        if success_rate < min_success_rate:
            reasons.append("success_rate_below_threshold")
        if float(metrics.get("median_tokens_per_second", 0) or 0) < min_tps:
            reasons.append("token_rate_below_threshold")
        startup = metrics.get("startup_seconds")
        if startup is not None and startup > max_start:
            reasons.append("startup_time_above_threshold")
        peak = metrics.get("peak_process_rss_mb")
        ram_gb = getattr(self.hardware, "ram_gb", None)
        if peak is not None and ram_gb:
            if peak > float(ram_gb) * 1024 * max_ram_ratio:
                reasons.append("process_memory_above_threshold")
        return {
            "status": "PASS" if not reasons else "FAIL",
            "reasons": reasons,
            "success_rate": round(success_rate, 4),
            "policy": {
                "min_repeats": min_repeats,
                "min_success_rate": min_success_rate,
                "min_median_tokens_per_second": min_tps,
                "max_startup_seconds": max_start,
                "max_peak_rss_ratio_of_ram": max_ram_ratio,
            },
        }

    def _record(self, provider, model_info, profile_pass, samples, errors, startup_seconds, peak_rss_mb, managed_start):
        tps = [x["tokens_per_second"] for x in samples]
        elapsed = [x["elapsed_seconds"] for x in samples]
        metrics = {
            "requested_runs": len(samples) + len(errors),
            "successful_runs": len(samples),
            "failed_runs": len(errors),
            "startup_seconds": startup_seconds,
            "mean_tokens_per_second": round(statistics.mean(tps), 3) if tps else 0.0,
            "median_tokens_per_second": round(statistics.median(tps), 3) if tps else 0.0,
            "min_tokens_per_second": round(min(tps), 3) if tps else 0.0,
            "max_tokens_per_second": round(max(tps), 3) if tps else 0.0,
            "mean_inference_seconds": round(statistics.mean(elapsed), 6) if elapsed else None,
            "peak_process_rss_mb": peak_rss_mb,
            "memory_source": "managed_process_rss" if peak_rss_mb is not None else "unavailable",
        }
        qualification = self._qualify(metrics, metrics["requested_runs"])
        raw_id = f'{provider}|{model_info.get("id") or model_info.get("model")}|{getattr(self.hardware, "hardware_class", "unknown")}|{utcnow()}'
        import hashlib
        bid = "BM-" + hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16].upper()
        record = {
            "schema": 1,
            "benchmark_id": bid,
            "created_at": utcnow(),
            "provider": provider,
            "managed_start": bool(managed_start),
            "hardware": {**self.hardware.to_dict(), "fingerprint": self.hardware.fingerprint()},
            "model": model_info,
            "profile_pass": profile_pass,
            "samples": samples,
            "errors": errors,
            "metrics": metrics,
            "qualification": qualification,
        }
        self.store.save(record)
        if self.audit:
            self.audit.append("MODEL_BENCHMARK_COMPLETED", component="model-benchmark", payload={"benchmark_id": bid, "provider": provider, "qualification": qualification["status"]})
        return record

    def benchmark_active(self, provider, *, model=None, model_id=None, profile_id=None, prompt=DEFAULT_PROMPT, repeats=3, warmups=1, max_tokens=128):
        ctl = self.manager.controller(provider)
        endpoint = ctl.endpoint
        adapter = self._adapter(provider, endpoint)
        if not adapter.health():
            raise RuntimeError("provider_not_healthy")
        model_info = {"id": model_id, "model": model}
        size_gb = None
        if model_id:
            rec = self.manager.catalog.get(model_id)
            model_info = rec
            size_gb = rec.get("size_gb")
        profile_pass = self.manager.profile_for(profile_id, size_gb, model_id=model_id, runtime=provider)
        if model is None:
            models = adapter.list_models()
            if not models:
                raise RuntimeError("no_models_available")
            model = models[0]
        model_info = {**model_info, "served_model": model}
        pid = (ctl.status() or {}).get("managed_pid")
        sampler = MemorySampler(pid).start()
        try:
            samples, errors = self._run_samples(adapter, model, prompt, repeats, warmups, max_tokens)
        finally:
            sampler.stop()
        return self._record(provider, model_info, profile_pass, samples, errors, None, sampler.peak_mb, False)

    def _test_lab(self):
        if self._lab is None:
            from ..jobs.testlab import TestLab
            self._lab = TestLab(self.data_root / "testlab" / "testlab.db")
        return self._lab

    def _take_gpu(self, purpose):
        """The GPU lease for a server this runner starts (Spec 2, D2.7, SCH-11): it waits like every benchmark (and stands in `handover_requests`, so a
        running model scheduler hands the GPU over), and a heartbeat keeps it while the server runs. Returns the release function."""
        lab = self._test_lab()
        wait_s = float(self.policy.get("gpu_wait_s", 600))
        token = lab.acquire("benchmark-managed", purpose, ttl_s=300, wait_s=wait_s, poll_s=5)
        stop = threading.Event()

        def beat():
            while not stop.wait(30):
                if not lab.heartbeat(token):
                    return
        threading.Thread(target=beat, name="benchmark-managed-lease", daemon=True).start()

        def release():
            stop.set()
            lab.release(token)
        return release

    def release_managed_gpu(self):
        """The lease of a managed server that was left running (`keep_running`) goes back when that server is stopped."""
        held, self._held = self._held, None
        if held is not None:
            held()

    def benchmark_managed_llamacpp(self, *, model_id, profile_id=None, prompt=DEFAULT_PROMPT, repeats=3, warmups=1, max_tokens=128, port=18080, keep_running=False, profile_override=None):
        provider = "llama-cpp-server"
        ctl = self.manager.controller(provider)
        if ctl.status().get("managed_running"):
            raise RuntimeError("managed_llama_cpp_already_running")
        rec = self.manager.catalog.get(model_id)
        profile_pass = self.manager.profile_for(profile_id, rec.get("size_gb"), model_id=model_id, runtime=provider)
        if profile_pass["status"] == "REVIEW":
            raise RuntimeError("hardware_model_pass_requires_review")
        if profile_override is not None:
            hw=getattr(self.manager,"hardware_manager",None)
            if hw: profile_override=hw.constrain_runtime_profile(profile_override)
            profile_pass = self.manager.hardware_pass.evaluate(profile_override, model_size_gb=rec.get("size_gb"))
            if profile_pass["status"] != "PASS":
                raise RuntimeError("hardware_model_pass_requires_review")
        release = self._take_gpu(f"benchmark managed {model_id}")           # no lease, no server
        kept = False
        try:
            return self._managed_run(ctl, provider, rec, profile_pass, model_id, prompt, repeats, warmups, max_tokens, port, keep_running)
        finally:
            kept = bool(keep_running) and ctl.status().get("managed_running")
            if kept:
                self.release_managed_gpu()
                self._held = release
            else:
                release()

    def _managed_run(self, ctl, provider, rec, profile_pass, model_id, prompt, repeats, warmups, max_tokens, port, keep_running):
        started_at = time.perf_counter()
        hw=getattr(self.manager,"hardware_manager",None)
        if hw: hw.preflight()
        started = ctl.start_server(Path(rec["path"]), profile_pass["effective_profile"], port=port, log_path=self.data_root / "models" / "logs" / f"benchmark-{model_id}.log")
        adapter = self._adapter(provider, started["endpoint"])
        sampler = MemorySampler(started.get("pid")).start()
        try:
            ready_elapsed = self._wait_ready(adapter)
            startup_seconds = round(time.perf_counter() - started_at, 4)
            models = adapter.list_models()
            served_model = models[0] if models else None
            samples, errors = self._run_samples(adapter, served_model, prompt, repeats, warmups, max_tokens)
            rec2 = {**rec, "served_model": served_model}
            return self._record(provider, rec2, profile_pass, samples, errors, startup_seconds, sampler.peak_mb, True)
        finally:
            sampler.stop()
            if not keep_running:
                ctl.stop_server()

    def promote_known_good(self, benchmark_id: str, profile_id: str | None = None):
        rec = self.store.get(benchmark_id)
        if rec.get("qualification", {}).get("status") != "PASS":
            raise ValueError("benchmark_not_qualified")
        profile = deepcopy((rec.get("profile_pass") or {}).get("effective_profile") or {})
        if not profile:
            raise ValueError("benchmark_profile_missing")
        model = rec.get("model") or {}
        hw = rec.get("hardware") or {}
        provider = rec.get("provider")
        if not profile_id:
            seed = f'{hw.get("fingerprint")}|{model.get("id") or model.get("served_model")}|{provider}'
            import hashlib
            profile_id = "kgp-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        score = float(rec.get("metrics", {}).get("median_tokens_per_second", 0) or 0)
        record = {
            "status": "confirmed",
            "confirmed_at": utcnow(),
            "runtime": provider,
            "hardware": {"fingerprint": hw.get("fingerprint"), "hardware_class": hw.get("hardware_class")},
            "model": {"id": model.get("id"), "filename": model.get("filename"), "served_model": model.get("served_model"), "size_gb": model.get("size_gb")},
            "benchmark_id": benchmark_id,
            "score": score,
            "profile": profile,
        }
        saved = self.profile_store.save_known_good(profile_id, record)
        if self.audit:
            self.audit.append("KNOWN_GOOD_PROFILE_CONFIRMED", component="model-benchmark", payload={"profile_id": profile_id, "benchmark_id": benchmark_id, "score": score})
        return {"profile_id": profile_id, "record": saved}
