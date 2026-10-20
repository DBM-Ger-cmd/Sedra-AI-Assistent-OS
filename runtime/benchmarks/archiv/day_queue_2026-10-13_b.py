r"""Targeted rework of a built spec (Captain 2026-10-13): Qwen3.6 fixes the defects named in a review file on its own first candidate (seed = the exported attempt of the first run).
Results: summary_<tag>.json next to the day summaries. Nothing is integrated.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-13_b.py <project_dir> <spec> <seed_folder> <review_file> <tag>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "archiv" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)


class Rework(night.Queue):
    def __init__(self, project, spec, seed, review, tag):
        super().__init__(project)
        self.spec, self.seed, self.review, self.tag = spec, seed, review, tag
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.summary = {"started": night.stamp(), "builds": {}}
        self.env["TESTLAB_OWNER"] = f"claude_rework_{spec}_2026-10-13"
        self.require_s0 = True

    def save(self):
        (self.out / f"summary_{self.tag}.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say(f"{self.spec} rework started")
        self.summary["builds"][self.spec] = {"recipe": "coder.local_primary", **self.build("coder.local_primary", self.spec, ["--seed", self.seed, "--review", self.review], 3 * 3600, f"{self.spec}_rework")}
        self.summary["finished"] = night.stamp(); self.save()
        self.say(f"{self.spec} rework finished")


if __name__ == "__main__":
    Rework(*sys.argv[1:6]).main()
