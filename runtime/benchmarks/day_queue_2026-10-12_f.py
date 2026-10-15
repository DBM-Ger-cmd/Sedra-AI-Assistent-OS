r"""Chat diagnosis (Captain 2026-10-12: a real chat window, error details visible, diagnosis side bar, commands in the chat; GUPPI builds as much as possible itself): waits for the
night chain (PID in runtime_data/measurements/day_2026-10-12/queue_c.pid), then Qwen3.6 (coder.local_primary) builds benchmarks/devvm_specs/chat_diag.py in GUPPI's coder with the
settings of the night queue. Results: summary_f.json next to it. Nothing is integrated; Claude wires it into uix_server.py and the chat window after the review.

    .venv\Scripts\python.exe benchmarks/day_queue_2026-10-12_f.py <project_dir>
"""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)


def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


class ChatDiag(night.Queue):
    def __init__(self, project):
        super().__init__(project)
        self.out = self.project / "runtime_data" / "measurements" / "day_2026-10-12"
        self.summary = {"started": night.stamp(), "builds": {}}
        self.env["TESTLAB_OWNER"] = "claude_chatdiag_2026-10-12"
        self.require_s0 = True

    def save(self):
        (self.out / "summary_f.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def wait_for_chain(self):
        pid_file = self.out / "queue_c.pid"
        pid = int(pid_file.read_text().strip()) if pid_file.exists() else None
        while pid and alive(pid):
            time.sleep(60)

    def main(self):
        self.say("chat diagnosis waits for the night chain")
        self.wait_for_chain()
        self.say("chat diagnosis build started")
        self.summary["builds"]["chat_diag"] = {"recipe": "coder.local_primary", **self.build("coder.local_primary", "chat_diag", [], 3 * 3600, "chat_diag")}
        self.save()
        self.summary["finished"] = night.stamp(); self.save()
        self.say("chat diagnosis build finished")


if __name__ == "__main__":
    ChatDiag(sys.argv[1]).main()
