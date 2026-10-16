r"""Night chain 2026-10-13 (Captain 2026-10-13: "GUPPI soll die Spezifikation bauen, aber erst in der Nacht-Warteschlange"): GUPPI's standard coder (coder.local_primary, Qwen3.6) builds
benchmarks/devvm_specs/cchat.py (chat sessions store, SSE frames and parser; steps 1 and 2 of docs/AUFTRAG_GUPPI_CHAT_AUSBAU_2026-10-13.md) in its own coder with the settings of the night
queue (DevVM, solo, --coder-ext all, engine b11160, flash attention on, KV q8_0, ubatch 512).

    .venv\Scripts\python.exe benchmarks/night_queue_2026-10-13.py <project_dir> [<start hour, default 22>] [<pid of a running chain to wait for>]

Waits until the start hour (local time; if it is already past midnight and before the hour of the next morning it starts at once only when the hour is reached today), optionally
until the given chain process has ended (it only WAITS, it never stops anything), then checks the GPU canary; if the canary failed, nothing is built. The build itself waits for the TESTLAB
GPU lease. Results: runtime_data/measurements/night_2026-10-13/ (queue.log, summary_cchat.json); nothing is integrated, Claude wires it in after the review.
"""
import datetime
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chain_judge
import gpu_recovery
from devvm_specs import cchat as cchat_spec

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("night_queue_a", HERE / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)
_spec_b = importlib.util.spec_from_file_location("night_queue_b", HERE / "night_queue_2026-10-11_b.py")
follow = importlib.util.module_from_spec(_spec_b)
_spec_b.loader.exec_module(follow)

RECIPE = "coder.local_primary"
SPEC = "cchat"


class Chat(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "night_2026-10-13"
        self.out.mkdir(parents=True, exist_ok=True)
        self.env["TESTLAB_OWNER"] = "claude_cchat_2026-10-13"
        self.require_s0 = True

    def save(self):
        (self.out / "summary_cchat.json").write_text(json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def wait_for_hour(self, hour):
        now = datetime.datetime.now()
        start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now.hour < 6:
            start -= datetime.timedelta(days=1)       # after midnight: the night has already begun
        while datetime.datetime.now() < start:
            time.sleep(60)

    def judged_build(self):
        order = [st["name"] for st in cchat_spec.STAGES]
        args, row, attempts = [], {}, []
        for attempt in (1, 2):
            row = self.build(RECIPE, SPEC, args, 4 * 3600, f"cchat{attempt}")
            action, reason = chain_judge.judge_build(row, attempt)
            attempts.append({"attempt": attempt, "action": action, "reason": reason, "passed": row.get("passed"), "stages": row.get("stages")})
            self.say(f"  judge: {action} ({reason})")
            if action == "continue" or (self.canary_failed() and not gpu_recovery.wait_for_gpu(self)):
                break
            failed = chain_judge.first_failed(row.get("stage_results") or {}, order) if action == "resume" else None
            seed = chain_judge.seed_for(self.project / "runtime_data" / "devvm_snapshots" / SPEC, order, failed) if failed else None
            args = ["--from-stage", failed, "--seed", str(seed)] if failed and seed else []
        row["attempts"] = attempts
        return row

    def main(self, hour=22, wait_pid=None):
        if datetime.datetime.now() > datetime.datetime(2026, 10, 14, 12, 0):
            self.say("cchat: the night of 2026-10-13 is over, nothing started")
            return
        marker = self.out / "summary_cchat.json"
        if marker.exists() and json.loads(marker.read_text(encoding="utf-8") or "{}").get("finished"):
            self.say("cchat: already finished, nothing started")
            return
        self.summary = {"started": night.stamp(), "server": night.SERVER, "engine": "b11160", "start_hour": hour, "waited_for_pid": wait_pid, "builds": {}}
        self.say(f"cchat: waiting for {hour}:00" + (f" and for PID {wait_pid}" if wait_pid else ""))
        self.wait_for_hour(hour)
        while wait_pid and follow.running(wait_pid):
            time.sleep(60)
        self.say("cchat: starting")
        if self.canary_failed() and not gpu_recovery.wait_for_gpu(self):
            self.say("GPU CANARY FAILED - cchat not started")
            self.summary["stopped"] = "gpu_canary_failed"; self.save()
            return
        self.summary["builds"][SPEC] = {"recipe": RECIPE, **self.judged_build()}
        self.summary["finished"] = night.stamp(); self.save()
        self.say("cchat finished")


if __name__ == "__main__":
    Chat(sys.argv[1]).main(int(sys.argv[2]) if len(sys.argv) > 2 else 22, int(sys.argv[3]) if len(sys.argv) > 3 else None)
