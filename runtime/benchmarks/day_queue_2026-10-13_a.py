r"""Process starter and lesson proposals (Captain 2026-10-13: GUPPI builds the specs for the process starter and the lesson cards): Qwen3.6 (coder.local_primary) builds
benchmarks/devvm_specs/vm_process.py and lesson_proposer.py one after the other in GUPPI's coder with the settings of the night queue. Results: summary_g.json next to the other day
summaries. Nothing is integrated; Claude reads every line afterwards and wires them in.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-13_a.py <project_dir>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)


class ProcAndLessons(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.summary = {"started": night.stamp(), "builds": {}}
        self.env["TESTLAB_OWNER"] = "claude_procless_2026-10-13"
        self.require_s0 = True

    def save(self):
        (self.out / "summary_g.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say("process starter and lesson proposals build started")
        for spec in ("vm_process", "lesson_proposer"):
            self.summary["builds"][spec] = {"recipe": "coder.local_primary", **self.build("coder.local_primary", spec, [], 3 * 3600, spec)}
            self.save()
        self.summary["finished"] = night.stamp(); self.save()
        self.say("process starter and lesson proposals build finished")


if __name__ == "__main__":
    ProcAndLessons(sys.argv[1]).main()
