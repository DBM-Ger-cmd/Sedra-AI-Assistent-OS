r"""Qwen3.6-35B-A3B IQ4_XS against Q4_K_M in agent mode (Captain 2026-10-12: "Q4_K_M behalten und pruefen gegeneinander auch im Agenten-Modus").

Same runner and settings as the night queue (GUPPI's coder, DevVM, solo, --coder-ext all, b11160, FA on, KV q8_0, ubatch 512). IQ4_XS = coder.local_primary (n_cpu_moe 28),
Q4_K_M = coder.local_q4km (n_cpu_moe 32, recipe off, server settings set per run). Order: S0 connection check of Q4_K_M with exactly these settings (the comparison stops when it fails; every build then runs with --require-s0), Q4_K_M standard test 2x, then E-06 and E-10 as FRESH builds (no seed, no review)
for both quantisations alternately, then the agent test AG-01 (benchmarks/devvm_specs/ag01_shop.py) for both in --mode delegating (helpers allowed) and --mode solo, then the context
ladder of Q4_K_M. The IQ4_XS standard tests and ladder of the night run are the reference. Results:
runtime_data/measurements/day_2026-10-12/summary_c.json. Nothing is integrated.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-12_c.py <project_dir>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)

IQ4, Q4KM = "coder.local_primary", "coder.local_q4km"
STD = ["--seed", str(night.SEED), "--rework", "1", "--mode", "solo", "--self-check", "none"]


class QuantCompare(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.out.mkdir(parents=True, exist_ok=True)
        self.summary = {"started": night.stamp(), "server": night.SERVER, "engine": "b11160", "models": {IQ4: {}, Q4KM: {}}}
        self.env["TESTLAB_OWNER"] = "claude_quant_2026-10-12"

    def save(self):
        (self.out / "summary_c.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say("quant compare IQ4_XS vs Q4_K_M started")
        argv = [sys.executable, str(RUNTIME / "benchmarks" / "connection_check.py"), str(self.project), Q4KM]
        for item in night.SERVER:
            argv += ["--set", item]
        self.run("s0_" + Q4KM, argv, 3600)
        from guppi_runtime.s0_status import status as s0_state
        import yaml
        recipe = next(r for r in yaml.safe_load((self.project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"] if r["id"] == Q4KM)
        server = {**recipe["profile"]["server"], **{k: (int(v) if v.isdigit() else v) for k, v in (i.split("=", 1) for i in night.SERVER)}}
        self.summary["models"][Q4KM]["s0"] = s0_state(self.project, Q4KM, server, "b11160")
        self.save()
        if self.summary["models"][Q4KM]["s0"]["state"] != "ok":
            self.say(f"S0 for {Q4KM} is {self.summary['models'][Q4KM]['s0']['state']} - comparison stopped (see s0_{Q4KM}.log)")
            self.summary["stopped"] = "s0_failed"; self.save()
            return
        self.require_s0 = True
        for trial in (1, 2):
            self.summary["models"][Q4KM].setdefault("std", []).append(self.build(Q4KM, "bench_std", STD, 2400, f"qstd{trial}"))
            self.save()
            if self.canary_failed():
                self.say("GPU CANARY FAILED - queue stopped"); self.summary["stopped"] = "gpu_canary_failed"; self.save()
                return
        for spec in ("e06_bg_jobs", "e10_self_repo_guard"):
            for recipe in (Q4KM, IQ4):
                self.summary["models"][recipe][spec] = self.build(recipe, spec, [], 4 * 3600, "quant")
                self.save()
        shop = ["--seed", str(RUNTIME / "benchmarks" / "devvm_seeds" / "ag01_shop")]
        for mode in ("delegating", "solo"):           # AG-01: a change across an existing package; delegating = the developer may use helper agents (explorer, reviewer, strong coder)
            for recipe in (Q4KM, IQ4):
                self.summary["models"][recipe][f"ag01_shop_{mode}"] = self.build(recipe, "ag01_shop", shop + ["--mode", mode], 4 * 3600, f"agent_{mode}")
                self.save()
        self.summary["models"][Q4KM]["ladder"] = self.ladder(Q4KM, 131072, 32768)
        self.summary["finished"] = night.stamp(); self.save()
        self.say("quant compare finished")


if __name__ == "__main__":
    QuantCompare(sys.argv[1]).main()
