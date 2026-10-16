r"""Builds from an order file one after the other, NOW and at normal priority (no lease reservation, no start hour): for continuations during the day (Claude 2026-10-14). The night chain G
(night_queue_2026-10-13_g.py) is for the night and reserves the GPU; this one just takes its turn at the lease like any other build.

    .venv\Scripts\python.exe benchmarks/resume_queue.py <project_dir> <order.json> <tag>

The order file is a list of {"spec", "seed", "from_stage", "review", "rework"} (only "spec" is required; paths relative to benchmarks/). One attempt per item, the next item is built even after a
failure. Results: runtime_data/measurements/<tag>/ (queue.log, summary.json); the last line of queue.log is `resume queue finished`. A failed GPU canary stops it."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
_spec = importlib.util.spec_from_file_location("night_queue", HERE / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)

RECIPE = "coder.local_primary"
FINISHED = "resume queue finished"


class Resume(night.Queue):
    def __init__(self, project, order, tag):
        super().__init__(project)
        self.order, self.tag = Path(order), tag
        self.out = self.project / "runtime_data" / "measurements" / tag
        self.out.mkdir(parents=True, exist_ok=True)
        self.env["TESTLAB_OWNER"] = f"claude_{tag}"
        self.summary = {"started": night.stamp(), "server": night.SERVER, "engine": "b11160", "specs": {}}

    def save(self):
        (self.out / "summary.json").write_text(json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def mode_args(item):
        args = ["--rework", str(item.get("rework", 3)), "--mode", "solo", "--self-check", "none"]
        for key, flag in (("seed", "--seed"), ("review", "--review")):
            if item.get(key):
                args += [flag, str(HERE / item[key])]
        if item.get("from_stage"):
            args += ["--from-stage", item["from_stage"]]
        return args

    def main(self):
        items = [item for item in json.loads(self.order.read_text(encoding="utf-8")) if isinstance(item, dict) and isinstance(item.get("spec"), str)]
        self.say(f"resume queue started: {[item['spec'] for item in items]}")
        for item in items:
            row = self.build(RECIPE, item["spec"], self.mode_args(item), 4 * 3600, f"r_{item['spec']}")
            row["finished"] = night.stamp()
            self.summary["specs"][item["spec"]] = row
            self.save()
            self.say(f"  {item['spec']}: {'PASSED' if row.get('passed') and row.get('passed') == row.get('stages') else 'not passed'}")
            if self.canary_failed():
                self.say("GPU CANARY FAILED - stopped (NVIDIA debug mode on?)")
                self.summary["stopped"] = "gpu_canary_failed"
                self.save()
                return
        self.say(FINISHED)


if __name__ == "__main__":
    Resume(sys.argv[1], sys.argv[2], sys.argv[3]).main()
