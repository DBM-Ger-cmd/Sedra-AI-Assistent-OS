r"""Second attempts of 2026-10-12 (Captain: "offene Punkte angehen") with the runner of the night queue (same settings: GUPPI's coder, solo, --coder-ext all,
b11160, FA on, KV q8_0, ubatch 512):
  1. E-06 bg_jobs: Qwen3.6 continues its own candidate of the night with a review of the five deviations (benchmarks/devvm_reviews/e06_review_2026-10-12.txt);
  2. E-10 self_repo_guard: Qwen3-Coder instead of Gemma (Gemma failed 0/3 on the turn limit), a fresh build.
Results: runtime_data/measurements/day_2026-10-12/ (queue.log, summary.json). Nothing is integrated.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-12.py <project_dir>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)


class DayQueue(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.out.mkdir(parents=True, exist_ok=True)
        self.summary = {"started": night.stamp(), "server": night.SERVER, "engine": "b11160", "builds": {}}
        self.env["TESTLAB_OWNER"] = "claude_day_2026-10-12"

    def main(self):
        self.say("day queue 2026-10-12 started")
        seed = sorted((self.project / "runtime_data" / "devvm_candidates" / "e06_bg_jobs").glob("attempt_*"))[-1]
        review = RUNTIME / "benchmarks" / "devvm_reviews" / "e06_review_2026-10-12.txt"
        self.summary["builds"]["e06_bg_jobs"] = {"recipe": "coder.local_primary", "seed": str(seed),
                                                 **self.build("coder.local_primary", "e06_bg_jobs", ["--seed", str(seed), "--review", str(review)], 4 * 3600, "rework")}
        self.save()
        if self.canary_failed():
            self.say("GPU CANARY FAILED - queue stopped"); self.summary["stopped"] = "gpu_canary_failed"; self.save()
            return
        self.summary["builds"]["e10_self_repo_guard"] = {"recipe": "coder.llama_qwen3_coder", **self.build("coder.llama_qwen3_coder", "e10_self_repo_guard", [], 4 * 3600, "own")}
        self.summary["finished"] = night.stamp(); self.save()
        self.say("day queue finished")


if __name__ == "__main__":
    DayQueue(sys.argv[1]).main()
