r"""Coin hole resume (stage coins onward) for the Guppy meter (Captain 2026-10-12, a test task of another kind): Qwen3.6 (coder.local_primary) builds benchmarks/devvm_specs/coin_hole.py in GUPPI's
coder with the settings of the night queue. Results: runtime_data/measurements/day_2026-10-12/summary_e.json. Nothing is integrated; Claude wires it in after the review.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-12_d.py <project_dir>
"""
import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "archiv" / "night_queue_2026-10-11.py")
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
        (self.out / "summary_e.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        self.say("coin hole build started")
        seed = self.project / "runtime_data" / "devvm_snapshots" / "coin_hole" / "20261012_131206" / "after_tokens"
        for spec in ("coin_hole",):       # resume at the failed stage coins (summary_e.json: tokens passed, coins failed)
            self.summary["builds"][spec] = {"recipe": "coder.local_primary", **self.build("coder.local_primary", spec, ["--from-stage", "coins", "--seed", str(seed)], 3 * 3600, spec + "_resume")}
            self.save()
        self.summary["finished"] = night.stamp(); self.save()
        self.say("coin hole build finished")


if __name__ == "__main__":
    CoinHole(sys.argv[1]).main()
