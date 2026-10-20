r"""E-10 second attempt (2026-10-12): Qwen3-Coder continues its own candidate with a review of the one remaining deviation (--git-dir / --work-tree decide by the folder,
benchmarks/devvm_reviews/e10_review_2026-10-12.txt). Same runner and settings as day_queue_2026-10-12.py. Results: runtime_data/measurements/day_2026-10-12/ (summary_b.json).

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-12_b.py <project_dir>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("day_queue", RUNTIME / "benchmarks" / "archiv" / "day_queue_2026-10-12.py")
day = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(day)


class ReworkE10(day.DayQueue):
    def save(self):
        (self.out / "summary_b.json").write_text(day.night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say("E-10 rework started")
        seed = sorted((self.project / "runtime_data" / "devvm_candidates" / "e10_self_repo_guard").glob("attempt_*"))[-1]
        review = RUNTIME / "benchmarks" / "devvm_reviews" / "e10_review_2026-10-12.txt"
        self.summary["builds"]["e10_self_repo_guard"] = {"recipe": "coder.llama_qwen3_coder", "seed": str(seed),
                                                         **self.build("coder.llama_qwen3_coder", "e10_self_repo_guard", ["--seed", str(seed), "--review", str(review)], 3 * 3600, "rework")}
        self.summary["finished"] = day.night.stamp(); self.save()
        self.say("E-10 rework finished")


if __name__ == "__main__":
    ReworkE10(sys.argv[1]).main()
