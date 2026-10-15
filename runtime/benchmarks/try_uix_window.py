"""Try-out of the uix_window candidate BEFORE it is integrated (Captain 2026-10-03: "wie starte ich diese um zu pruefen").

    .venv\\Scripts\\python.exe benchmarks/try_uix_window.py [--dry]

Starts GUPPI's UIX server on a free loopback port (as START_GUPPI_UIX.bat does, but without opening a browser tab), then opens the URL
it printed as an app window with the argument list from the candidate's `window_argv` (Edge or Chrome, no address bar). The candidate's
code is read from the e1_golden_path state of the uix_window scenario; nothing is installed or integrated. Close the window or press
Ctrl+C here to stop; the server is stopped with it. `--dry` only prints what would be started.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
ROOT = RUNTIME.parent
PROJECT = ROOT / "workspace" / "GUPPI_OS"
ARCH = ROOT / "architecture" / "GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
STATE = PROJECT / "runtime_data" / "e1_golden_path" / "uix_window" / "state.json"


def candidate_module():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    files = [c for c in state.get("candidate") or [] if c["path"] == "uix_window.py"]
    if not files:
        raise SystemExit("no uix_window candidate in " + str(STATE))
    ns = {}
    exec(compile(files[0]["content"], "uix_window_candidate", "exec"), ns)
    return ns, state.get("candidate_id")


def main():
    dry = "--dry" in sys.argv[1:]
    mod, cand_id = candidate_module()
    # Windows upper-cases the names in os.environ; the candidate looks up "ProgramFiles(x86)" etc. exactly as Windows documents them.
    env_names = {name: os.environ.get(name, "") for name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")}
    browser = mod["pick_browser"](mod["browser_candidates"](env_names), os.path.isfile)
    if not browser:
        raise SystemExit("neither Edge nor Chrome found")
    profile = str(Path(tempfile.gettempdir()) / "guppi-uix-window-profile")
    print(f"candidate {cand_id}; browser {browser}")
    cmd = [str(RUNTIME / ".venv" / "Scripts" / "python.exe"), "-B", "-u", "-m", "guppi_runtime.uix_server", "--root", str(PROJECT),
           "--architecture", str(ARCH)]
    if dry:
        print("would start:", " ".join(cmd))
        print("would open: ", mod["window_argv"](browser, "http://127.0.0.1:8765/", profile))
        return 0
    env = dict(os.environ, PYTHONPATH=str(RUNTIME / "src"))
    server = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(RUNTIME))
    try:
        url = None
        deadline = time.monotonic() + 60
        for line in server.stdout:
            print("server:", line.rstrip())
            m = re.search(r"(http://127\.0\.0\.1:\d+/\S*)", line)
            if m:
                url = m.group(1)
                break
            if time.monotonic() > deadline:
                break
        if not url:
            raise SystemExit("the UIX server did not print a URL")
        argv = mod["window_argv"](browser, url, profile)          # refuses anything but GUPPI's own loopback UIX
        print("window:", argv[1].split("#")[0])
        subprocess.run(argv)                                       # returns when the window is closed (a profile of its own: new process)
        print("window closed; server keeps running 5 s for a late close, then stops")
        time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        server.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
