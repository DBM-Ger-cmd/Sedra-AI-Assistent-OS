r"""Follow-up link of the night chain 2026-10-11 (Captain 2026-10-11 evening: "gebe danach den Auftrag in die Kette Nacht", review docs/REVIEW_2026-10-11.md finding 4).

    .venv\Scripts\python.exe benchmarks/night_queue_2026-10-11_b.py <project_dir> <pid of the running night queue>

Waits until the first night queue (night_queue_2026-10-11.py) has ended - it only WAITS for that process, it never stops it - and then lets GUPPI's standard coder
(coder.local_primary, Qwen3.6) build `core_boundary` in its own coder with the same settings as the night queue (DevVM, solo, --coder-ext all, engine b11160,
flash attention on, KV q8_0, ubatch 512). If the GPU canary failed, nothing is built. Results: runtime_data/measurements/night_2026-10-11/ (queue.log, summary_b.json);
nothing is integrated.
"""
import ctypes
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("night_queue_a", HERE / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)

RECIPE = "coder.local_primary"
SPEC = "core_boundary"


def running(pid):
    """True while the process exists and has not ended (Windows: OpenProcess + GetExitCodeProcess; elsewhere: signal 0)."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259     # STILL_ACTIVE
    finally:
        kernel.CloseHandle(handle)


class FollowUp(night.Queue):
    def save(self):
        (self.out / "summary_b.json").write_text(json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self, wait_pid):
        self.summary = {"started": night.stamp(), "server": night.SERVER, "engine": "b11160", "waited_for_pid": wait_pid, "builds": {}}
        self.say(f"follow-up {SPEC}: waiting for night queue PID {wait_pid}")
        while running(wait_pid):
            time.sleep(60)
        self.say(f"follow-up {SPEC}: night queue ended, starting")
        if self.canary_failed():
            self.say("GPU CANARY FAILED - follow-up not started")
            self.summary["stopped"] = "gpu_canary_failed"; self.save()
            return
        self.summary["builds"][SPEC] = {"recipe": RECIPE, **self.build(RECIPE, SPEC, [], 4 * 3600, "followup")}
        self.summary["finished"] = night.stamp(); self.save()
        self.say(f"follow-up {SPEC} finished")


if __name__ == "__main__":
    FollowUp(sys.argv[1]).main(int(sys.argv[2]))
