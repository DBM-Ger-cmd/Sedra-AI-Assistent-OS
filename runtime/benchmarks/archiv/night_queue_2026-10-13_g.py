r"""Night chain G (Captain 2026-10-13: "den Rest in die Nacht-Warteschlange als ERSTES einfuegen, damit die anderen Laeufe damit arbeiten koennen"): GUPPI builds the blocks of
docs/ABLAUF_GESPRAECH_2026-10-13.md (test catalog, spec/test tools, ...) BEFORE the other night chains, so that they can use the results.

    .venv\Scripts\python.exe benchmarks/night_queue_2026-10-13_g.py <project_dir> [<start hour, default 22>]

What is built is read from benchmarks/night_g_order.json before every item (a list of {"spec", "seed", "from_stage", "review", "rework"}, only "spec" is required; a spec without a file is skipped,
so items can be added while the chain runs). From the start hour on the chain RESERVES the GPU lease with priority 1 (jobs/testlab.py `reserve`) for as long as it has work, and every build takes the
lease with TESTLAB_PRIORITY=1: takers without priority (the other chains) wait, also in the gaps between two builds. With no work left the reservation ends and the chain looks again every 5 minutes
until 2026-10-14 12:00. One attempt per spec; a spec that fails is recorded and not repeated (the next one is built). Results: runtime_data/measurements/night_g_2026-10-13/ (queue.log, summary.json).
Nothing is integrated: Claude reads the candidates in the morning. A failed GPU canary stops the chain."""
import datetime
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from guppi_runtime.jobs.testlab import TestLab, default_path

_spec = importlib.util.spec_from_file_location("night_queue", HERE / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)

RECIPE = "coder.local_primary"
OWNER = "claude_night_g_2026-10-13"
ORDER = HERE.parent / "night_g_order.json"
STOP = datetime.datetime(2026, 10, 14, 12, 0)


class GChain(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "night_g_2026-10-13"
        self.out.mkdir(parents=True, exist_ok=True)
        self.env["TESTLAB_OWNER"] = OWNER
        self.env["TESTLAB_PRIORITY"] = "1"
        self.summary = {"started": night.stamp(), "server": night.SERVER, "engine": "b11160", "specs": {}}
        saved = self.out / "summary.json"
        if saved.exists():
            self.summary["specs"] = json.loads(saved.read_text(encoding="utf-8")).get("specs", {})

    def save(self):
        (self.out / "summary.json").write_text(json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def items(self):
        try:
            data = json.loads(ORDER.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [item for item in data if isinstance(item, dict) and isinstance(item.get("spec"), str)]

    def pending(self):
        return [item for item in self.items() if item["spec"] not in self.summary["specs"] and (HERE / "devvm_specs" / f"{item['spec']}.py").is_file()]

    def mode_args(self, item):
        args = ["--rework", str(item.get("rework", 3)), "--mode", "solo", "--self-check", "none"]
        for key, flag in (("seed", "--seed"), ("from_stage", "--from-stage"), ("review", "--review")):
            if item.get(key):
                value = item[key]
                args += [flag, value if flag == "--from-stage" else str(HERE.parent / value)]
        return args

    def start_time(self, hour):
        now = datetime.datetime.now()
        start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now.hour < 6:
            start -= datetime.timedelta(days=1)
        return start

    def wait_until(self, moment):
        while datetime.datetime.now() < moment:
            time.sleep(min(30, max(1, (moment - datetime.datetime.now()).total_seconds())))

    def work(self, start):
        lab = TestLab(default_path(self.project))
        with lab.reserve(OWNER, "night chain G", priority=1):
            self.wait_until(start)
            while datetime.datetime.now() < STOP:
                todo = self.pending()
                if not todo:
                    return True
                item = todo[0]
                row = self.build(RECIPE, item["spec"], self.mode_args(item), 4 * 3600, f"g_{item['spec']}")
                row["finished"] = night.stamp()
                self.summary["specs"][item["spec"]] = row
                self.save()
                self.say(f"  {item['spec']}: {'PASSED' if row.get('passed') and row.get('passed') == row.get('stages') else 'not passed'}")
                if self.canary_failed():
                    self.say("GPU CANARY FAILED - chain G stopped (NVIDIA debug mode on?)")
                    self.summary["stopped"] = "gpu_canary_failed"
                    self.save()
                    return False
        return False

    def main(self, hour):
        start = self.start_time(hour)
        self.say(f"night chain G started (builds from {hour}:00; the reservation of the lease starts 2 minutes earlier, no build before {hour}:00)")
        self.wait_until(start - datetime.timedelta(minutes=2))
        while datetime.datetime.now() < STOP:
            if self.pending() and self.work(start) is False and self.summary.get("stopped"):
                return
            time.sleep(300)
        self.say("night chain G ended (12:00)")


if __name__ == "__main__":
    GChain(sys.argv[1]).main(int(sys.argv[2]) if len(sys.argv) > 2 else 22)
