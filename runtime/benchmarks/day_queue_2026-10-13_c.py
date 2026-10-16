r"""Background job test with a real model (Captain 2026-10-13): Qwen3.6 (coder.local_primary) works on benchmarks/devvm_specs/bg_report.py in GUPPI's coder with --bg-jobs (shell_start, shell_log,
shell_stop; the VM limit is raised to 100 s in the build's own sandbox config). The seed holds crunch.py (about 50 s); the task needs its TOTAL and a summary.py. Results: summary_m.json
next to the day summaries; whether the job tools were used is in the journal of the run (agent_detail.tool_counts of the build result). Nothing is integrated.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-13_c.py <project_dir> [<mode: solo|delegating>]
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)


class BgReport(night.Queue):
    def __init__(self, project, mode="solo"):
        super().__init__(project)
        self.mode = mode
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.summary = {"started": night.stamp(), "builds": {}}
        self.env["TESTLAB_OWNER"] = "claude_bgreport_2026-10-13"
        self.require_s0 = True

    def save(self):
        (self.out / "summary_m.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say("bg_report build started")
        seed = str(RUNTIME / "benchmarks" / "devvm_seeds" / "bg_report")
        self.summary["builds"]["bg_report"] = {"recipe": "coder.local_primary", **self.build("coder.local_primary", "bg_report", ["--seed", seed, "--bg-jobs", "--mode", self.mode], 2 * 3600, "bg_report")}
        self.save()
        self.summary["finished"] = night.stamp(); self.save()
        self.say("bg_report build finished")


if __name__ == "__main__":
    BgReport(sys.argv[1], *(sys.argv[2:3] or ["solo"])).main()
