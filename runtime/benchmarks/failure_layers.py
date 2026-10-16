r"""Where do the failures of a build run sit? (Captain 2026-10-10: in little-coder and Hermes the main faults were the model and the connection, not the agents - learn from that for our own process.)

    .venv\Scripts\python.exe benchmarks/failure_layers.py <logs_dir_or_log_file> [more logs ...]

Reads the protocol (.log) of DevVM builds and sorts every agent run by the LAYER its end points to, from the bottom up:
  1 server/model   a server crash (5xx, connection reset) or garbage output
  2 connection     the request was refused or malformed: HTTP 4xx (window full), no tool call at all (the chat template knows no tools), broken tool arguments
  3 model behaviour the model produced no usable answer: answer_cut (cut off), runaway (one block repeated), loop (the same call again and again)
  4 agent budget   the run hit a limit of the harness: turns, time, calls, tokens
  5 understanding  the run handed in (hand_in) but the hidden test of the stage still failed (the work does not meet a requirement)
  ok               the run handed in and the stage passed
The lower the layer, the earlier it should be fixed: a fault in layer 1 or 2 spoils every measurement above it. Pure functions (classify, tally) are tested in tests/test_failure_layers.py.
"""
import re
import sys
from pathlib import Path

LAYERS = {
    "server": "1 Server/Modell",
    "connection": "2 Anbindung",
    "behaviour": "3 Modellverhalten",
    "budget": "4 Agenten-Budget",
    "understanding": "5 Verständnis",
    "ok": "ok",
}
BY_END = {"error": "connection", "no_tool_call": "connection", "answer_cut": "behaviour", "runaway": "behaviour", "loop": "behaviour",
          "turns": "budget", "time": "budget", "calls": "budget", "tokens": "budget"}
AGENT = re.compile(r"agent (?P<label>\S+(?: \S+)*?)\s+(?P<model>\S+)\s+(?P<end>hand_in|no_tool_call|calls|time|tokens|loop|runaway|turns|answer_cut|error)\s+(?P<calls>\d+) calls\s+(?P<secs>[\d.]+) s (?P<tokens>\d+) tokens")
STAGE = re.compile(r"stage (?P<stage>\w+): hidden (?P<result>PASSED|FAILED)")
SERVER = re.compile(r"SERVER CRASH")


def classify(end, stage_passed=None, error_text=""):
    """The layer of one agent run. `stage_passed` is None while unknown (a run that is not the last of its stage); for a hand_in only the last run of a failed stage counts as a misunderstanding."""
    if end == "error" and re.search(r"HTTP Error 5\d\d|HTTP 5\d\d|Connection(Reset|Aborted|Refused)|RemoteDisconnected", error_text or ""): return "server"
    if end in BY_END: return BY_END[end]
    if end == "hand_in": return "understanding" if stage_passed is False else "ok"
    return "behaviour"


def tally(lines):
    """{layer: [count, seconds, tokens]} over the agent runs of a protocol; only the solo developer runs are counted. The result of a stage is known from the line that follows its agent runs."""
    pending, table = [], {}

    def add(layer, run):
        row = table.setdefault(layer, [0, 0.0, 0])
        row[0] += 1; row[1] += run["secs"]; row[2] += run["tokens"]
    for line in lines:
        m = AGENT.search(line)
        if m and m["label"].startswith("solo"):
            step = re.search(r"\(step (\d+)/(\d+)\)", m["label"])
            pending.append({"end": m["end"], "secs": float(m["secs"]), "tokens": int(m["tokens"]), "error": line, "inner_step": bool(step and step[1] != step[2])})
            continue
        s = STAGE.search(line)
        if s:
            passed = s["result"] == "PASSED"
            for i, run in enumerate(pending):
                last = i == len(pending) - 1
                verdict = True if run["inner_step"] else (passed if last else False)       # a hand-in that was followed by another run of the stage did not satisfy the hidden test; a step that is followed by the next step is no verdict
                add(classify(run["end"], verdict if run["end"] == "hand_in" else None, run["error"]), run)
            pending = []
    return table


def report(paths):
    total = {}
    for path in paths:
        table = tally(Path(path).read_text(encoding="utf-8", errors="replace").splitlines())
        for layer, row in table.items():
            t = total.setdefault(layer, [0, 0.0, 0])
            for k in range(3): t[k] += row[k]
    runs = sum(r[0] for r in total.values()) or 1
    secs = sum(r[1] for r in total.values()) or 1
    toks = sum(r[2] for r in total.values()) or 1
    out = ["| Schicht | Läufe | Anteil | Zeit s | Anteil Zeit | erzeugte Token | Anteil Token |", "|---|---|---|---|---|---|---|"]
    for layer in ("server", "connection", "behaviour", "budget", "understanding", "ok"):
        c, s, t = total.get(layer, [0, 0.0, 0])
        out.append(f"| {LAYERS[layer]} | {c} | {100 * c / runs:.0f} % | {s:.0f} | {100 * s / secs:.0f} % | {t} | {100 * t / toks:.0f} % |")
    return "\n".join(out)


def main():
    paths = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        paths += sorted(p.glob("*.log")) if p.is_dir() else [p]
    print(report(paths))


if __name__ == "__main__":
    main()
