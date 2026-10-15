r"""Coin hole for the Guppy meter (Captain 2026-10-12, a test task of another kind): Qwen3.6 (coder.local_primary) builds benchmarks/devvm_specs/coin_hole.py in GUPPI's
coder with the settings of the night queue. Results: runtime_data/measurements/day_2026-10-12/summary_d.json. Nothing is integrated; Claude wires it in after the review.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-12_d.py <project_dir>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)


class CoinHole(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.summary = {"started": night.stamp(), "builds": {}}
        self.env["TESTLAB_OWNER"] = "claude_coinhole_2026-10-12"
        self.require_s0 = True      # S0 must have passed for coder.local_primary with these settings (stored in runtime_data/measurements/s0/)

    def save(self):
        (self.out / "summary_d.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say("coin hole build started")
        for spec in ("coin_hole", "churn_guard"):       # 2026-10-12: the churn guard right after the coin hole (Captain)
            self.summary["builds"][spec] = {"recipe": "coder.local_primary", **self.build("coder.local_primary", spec, [], 3 * 3600, spec)}
            self.save()
        self.summary["finished"] = night.stamp(); self.save()
        self.say("coin hole build finished")


if __name__ == "__main__":
    CoinHole(sys.argv[1]).main()
