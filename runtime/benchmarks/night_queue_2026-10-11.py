r"""Night run of 2026-10-11 (Captain: "die Modelle sollen jeweils was anderes bauen, so schliessen wir die offenen Luecken"; the PC runs over night).

    .venv\Scripts\python.exe benchmarks/night_queue_2026-10-11.py <project_dir>

Every model runs in GUPPI's own coder (DevVM, solo, --coder-ext all) with the settings of the stable runs of 2026-10-11 (engine b11160 via GUPPI_ENGINE_BUILD,
flash attention on, KV q8_0, ubatch 512, 1 slot) and does three things, one after the other:
  1. the standard test bench_std (the same task for everybody, the only directly comparable number; solo-none like the reference runs),
  2. its OWN missing coder part (spec in devvm_specs/, hidden tests checked against Claude's reference in devvm_refs/),
  3. the context ladder with the same server settings (needle test up to the limit, 1 GiB VRAM reserve).
A model whose best standard run has fewer than 2 of 4 stages does not build; its part goes to Qwen3.6 at the end. If the GPU canary fails, the queue stops.
Every step holds the GPU lease on its own (TestLab). Results: runtime_data/measurements/night_2026-10-11/ (queue.log, summary.json); nothing is integrated.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
SEED = RUNTIME / "benchmarks" / "bench_std_seed"
SERVER = ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"]
CANARY = RUNTIME.parent / "runtime_data" / "gpu_canary.json"
PLAN = [   # (recipe, own spec, std trials, ladder max, ladder start)
    ("coder.local_primary", "e06_bg_jobs", 2, 131072, 32768),
    ("coder.llama_qwen3_coder", "e11_lesson_cards", 2, 131072, 32768),
    ("verifier.llama_gemma", "e10_self_repo_guard", 2, 131072, 32768),
    ("coder.llama_qwen35_q6", "layer_summary", 2, 131072, 65536),
    ("coder.llama_gptoss", "mcp_shield", 1, 65536, 32768),
    ("coder.local_q38", "s0_conn_check", 2, 65536, 32768),
]
FALLBACK = "coder.local_primary"


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Queue:
    def __init__(self, project):
        self.project = Path(project)
        self.out = self.project / "runtime_data" / "measurements" / "night_2026-10-11"
        self.out.mkdir(parents=True, exist_ok=True)
        self.summary = {"started": stamp(), "server": SERVER, "engine": "b11160", "models": {}, "leftover_builds": []}
        self.env = {**os.environ, "GUPPI_ENGINE_BUILD": "b11160", "TESTLAB_OWNER": "claude_night_2026-10-11", "PYTHONIOENCODING": "utf-8"}

    def say(self, text):
        line = f"{stamp()} {text}"
        print(line, flush=True)
        with (self.out / "queue.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def save(self):
        (self.out / "summary.json").write_text(json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def run(self, name, argv, timeout):
        log = self.out / f"{name}.log"
        self.say(f"START {name}: {' '.join(argv[1:])[:300]}")
        started = time.time()
        with log.open("w", encoding="utf-8", errors="replace") as f:
            proc = subprocess.Popen(argv, cwd=str(RUNTIME), env=self.env, stdout=f, stderr=subprocess.STDOUT)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()          # our own child only (PID of this Popen), never by name
                proc.wait()
                code = "timeout"
        self.say(f"END {name}: exit {code} after {time.time() - started:.0f} s")
        return code, started

    def newest(self, spec, after):
        logs = self.project / "runtime_data" / "measurements" / "logs"
        files = sorted((f for f in logs.glob(f"devvm_build_{spec}_*.json") if f.stat().st_mtime >= after), key=lambda f: f.stat().st_mtime)
        if not files:
            return None
        attempts = json.loads(files[-1].read_text(encoding="utf-8")).get("attempts") or []
        return attempts[-1] if attempts else None

    def build(self, recipe, spec, mode_args, timeout, tag):
        argv = [sys.executable, str(RUNTIME / "benchmarks" / "devvm_build.py"), str(self.project), "--spec", spec, "--attempts", "1",
                "--coder", recipe, "--all-models", recipe, "--context", "32768", "--tidy", "--reasoning", "off", "--coder-ext", "all"] + mode_args + (["--require-s0"] if getattr(self, "require_s0", False) else [])
        for item in SERVER:
            argv += ["--server-set", item]
        code, started = self.run(f"{tag}_{recipe}_{spec}", argv, timeout)
        record = self.newest(spec, started - 1)
        stages = (record or {}).get("stages") or []
        row = {"exit": code, "passed": sum(1 for s in stages if s.get("hidden_passed")), "stages": len(stages),
               "seconds": (record or {}).get("seconds"), "calls": (record or {}).get("calls"),
               "server_crashes": (record or {}).get("server_crashes"), "exported_to": (record or {}).get("exported_to"),
               "stage_results": {s["stage"]: bool(s.get("hidden_passed")) for s in stages}, "layer_cell": (record or {}).get("layer_cell")}
        self.say(f"  {recipe} {spec}: {row['passed']}/{row['stages']} stages, {row['seconds']} s, {row['calls']} calls")
        return row

    def canary_failed(self):
        try:
            state = json.loads(CANARY.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return state.get("passed") is False and state.get("result") != "port_in_use"

    def ladder(self, recipe, max_ctx, start):
        argv = [sys.executable, str(RUNTIME / "benchmarks" / "context_ladder.py"), str(self.project), recipe, "--max", str(max_ctx), "--probes", "2",
                "--from", str(start), "--tag", "night_fa_q8"]
        for item in SERVER:
            argv += ["--set", item]
        code, _ = self.run(f"ladder_{recipe}", argv, 3 * 3600)
        text = (self.out / f"ladder_{recipe}.log").read_text(encoding="utf-8", errors="replace")
        safe = [line for line in text.splitlines() if "SAFE MAX" in line]
        return {"exit": code, "result": safe[-1].strip() if safe else None}

    def main(self):
        self.say("night queue 2026-10-11 started")
        for recipe, spec, trials, max_ctx, start in PLAN:
            model = self.summary["models"].setdefault(recipe, {"std": [], "own": None, "ladder": None})
            for trial in range(1, trials + 1):
                model["std"].append(self.build(recipe, "bench_std", ["--seed", str(SEED), "--rework", "1", "--mode", "solo", "--self-check", "none"], 2400, f"std{trial}"))
                self.save()
                if self.canary_failed():
                    self.say("GPU CANARY FAILED - queue stopped (NVIDIA debug mode on?)")
                    self.summary["stopped"] = "gpu_canary_failed"; self.save()
                    return
            best = max((r["passed"] for r in model["std"]), default=0)
            if best < 2:
                self.say(f"  {recipe}: best standard run {best}/4 -> no own build, {spec} goes to {FALLBACK}")
                self.summary["leftover_builds"].append(spec)
            else:
                model["own"] = {"spec": spec, **self.build(recipe, spec, [], 4 * 3600, "own")}
            self.save()
            model["ladder"] = self.ladder(recipe, max_ctx, start)
            self.save()
        for spec in self.summary["leftover_builds"]:
            self.summary["models"][FALLBACK].setdefault("extra", []).append({"spec": spec, **self.build(FALLBACK, spec, [], 4 * 3600, "extra")})
            self.save()
        for trial in (1, 2):      # the reference without the coder extensions (does --coder-ext help?)
            argv_extra = ["--seed", str(SEED), "--rework", "1", "--mode", "solo", "--self-check", "none"]
            row = self.build_without_ext(FALLBACK, argv_extra, f"std_noext{trial}")
            self.summary["models"][FALLBACK].setdefault("std_without_ext", []).append(row)
            self.save()
        subprocess.run([sys.executable, str(RUNTIME / "benchmarks" / "model_compare.py"), str(self.project), "--out", str(RUNTIME.parent / "docs" / "MODELL_VERGLEICH_ERGEBNISSE.md")],
                       cwd=str(RUNTIME), env=self.env, capture_output=True)
        self.summary["finished"] = stamp(); self.save()
        self.say("night queue finished")

    def build_without_ext(self, recipe, extra, tag):
        argv = [sys.executable, str(RUNTIME / "benchmarks" / "devvm_build.py"), str(self.project), "--spec", "bench_std", "--attempts", "1",
                "--coder", recipe, "--all-models", recipe, "--context", "32768", "--tidy", "--reasoning", "off"] + extra
        for item in SERVER:
            argv += ["--server-set", item]
        code, started = self.run(f"{tag}_{recipe}", argv, 2400)
        record = self.newest("bench_std", started - 1)
        stages = (record or {}).get("stages") or []
        return {"exit": code, "passed": sum(1 for s in stages if s.get("hidden_passed")), "seconds": (record or {}).get("seconds"), "calls": (record or {}).get("calls")}


if __name__ == "__main__":
    Queue(sys.argv[1]).main()
