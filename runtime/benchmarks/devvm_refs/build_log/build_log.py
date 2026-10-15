import re

AGENT = re.compile(r"^\s+agent (?P<label>.+) (?P<model>\S+)\s+(?P<stop>\S+)\s+(?P<calls>\d+) calls\s+(?P<seconds>[\d.]+) s (?P<tokens>\d+) tokens, (?P<prompt>\d+) prompt, peak (?P<peak>\d+)\s*$")
STAGE = re.compile(r"^\s+stage (?P<name>\S+): hidden (?P<result>PASSED|FAILED) \(.*?(?P<seconds>[\d.]+) s\)\s*$")
LOAD = re.compile(r"^\s+load (?P<model>\S+) with a window of (?P<window>\d+) tokens in each of (?P<slots>\d+) slot")
HEADER = re.compile(r"^# run \S+ started (?P<started>\S+)(?: config (?P<config>.*))?$")
SPEC = re.compile(r'"spec": "(?P<spec>[^"]+)"')
S0 = re.compile(r"^S0 connection check: (?P<recipe>\S+) (?P<state>\S+)\s*$")
STOPPED = re.compile(r"^\s+stopped after the failed stage (?P<name>\S+); skipped: (?P<skipped>.*?)(?: \(.*\))?\s*$")
ATTEMPT = re.compile(r"^attempt (?P<n>\d+): hidden test (?P<result>PASSED|FAILED) \|.*\| (?P<seconds>[\d.]+) s, (?P<runs>\d+) agent runs, (?P<calls>\d+) calls -> (?P<path>.+?)\s*$")
RESUME = re.compile(r"^\s+resume: (?P<command>.+?)\s*$")
ENDED = re.compile(r"^# run ended: (?P<state>.*?)\s*$")
DONE = re.compile(r"^DONE -> (?P<report>.+?)\s*$")


def _agent(match):
    return {"label": match["label"].strip(), "model": match["model"], "stopped_by": match["stop"], "calls": int(match["calls"]), "seconds": float(match["seconds"]),
            "tokens": int(match["tokens"]), "prompt": int(match["prompt"]), "peak": int(match["peak"])}


def parse_log(text):
    parsed = {"s0": None, "spec": None, "started": None, "loads": [], "stages": [], "open_agents": [], "stopped_after": None, "skipped": [], "attempt": None,
              "resume": None, "ended": False, "end_state": None, "report": None}
    for line in str(text or "").splitlines():
        for pattern, handler in HANDLERS:
            match = pattern.match(line)
            if match:
                handler(parsed, match)
                break
    return parsed


def _s0(parsed, m):
    parsed["s0"] = {"recipe": m["recipe"], "state": m["state"]}


def _header(parsed, m):
    parsed["started"] = m["started"]
    found = SPEC.search(m["config"] or "")
    parsed["spec"] = found["spec"] if found else None


def _load(parsed, m):
    parsed["loads"].append({"model": m["model"], "window": int(m["window"]), "slots": int(m["slots"])})


def _agent_line(parsed, m):
    parsed["open_agents"].append(_agent(m))


def _stage(parsed, m):
    agents, parsed["open_agents"] = parsed["open_agents"], []
    parsed["stages"].append({"name": m["name"], "passed": m["result"] == "PASSED", "seconds": float(m["seconds"]), "agents": agents,
                             "reworks": sum(1 for a in agents if "(rework" in a["label"]), "halt": agents[-1]["stopped_by"] if agents else None})


def _stopped(parsed, m):
    parsed["stopped_after"] = m["name"]
    parsed["skipped"] = [name.strip() for name in m["skipped"].split(",") if name.strip()]


def _attempt(parsed, m):
    parsed["attempt"] = {"number": int(m["n"]), "passed": m["result"] == "PASSED", "seconds": float(m["seconds"]), "agent_runs": int(m["runs"]), "calls": int(m["calls"]), "exported_to": m["path"]}


def _resume(parsed, m):
    parsed["resume"] = m["command"]


def _ended(parsed, m):
    parsed["ended"], parsed["end_state"] = True, m["state"]


def _done(parsed, m):
    parsed["report"] = m["report"]


HANDLERS = ((S0, _s0), (HEADER, _header), (LOAD, _load), (AGENT, _agent_line), (STAGE, _stage), (STOPPED, _stopped), (ATTEMPT, _attempt), (RESUME, _resume), (ENDED, _ended), (DONE, _done))


def _count(number, one, many):
    return f"{number} {one if number == 1 else many}"


def summary(parsed):
    stages = parsed["stages"]
    passed = [s for s in stages if s["passed"]]
    failed = [s["name"] for s in stages if not s["passed"]]
    head = f"Bau {parsed['spec'] or '?'}: {len(passed)} von {len(stages) + len(parsed['skipped'])} Stufen bestanden"
    if failed:
        head += ", gescheitert: " + ", ".join(failed)
    if parsed["skipped"]:
        head += ", nicht gebaut: " + ", ".join(parsed["skipped"])
    lines = [head]
    if parsed["attempt"]:
        attempt = parsed["attempt"]
        lines.append(f"Zeit {attempt['seconds']:.0f} s, {attempt['calls']} Aufrufe, {_count(attempt['agent_runs'], 'Lauf', 'Läufe')}")
    for stage in stages:
        rework = "keine Nacharbeit" if not stage["reworks"] else _count(stage["reworks"], "Nacharbeit", "Nacharbeiten")
        if stage["passed"]:
            lines.append(f"  {stage['name']}: bestanden, {rework}, {stage['seconds']:.0f} s")
        else:
            lines.append(f"  {stage['name']}: GESCHEITERT, {rework}, letzter Halt {stage['halt']}, {stage['seconds']:.0f} s")
    if parsed["stopped_after"]:
        lines.append(f"Fortsetzbar ab Stufe {parsed['stopped_after']}")
    if not parsed["ended"]:
        lines.append("Bau läuft noch")
    return "\n".join(lines) + "\n"


def _event(line):
    for pattern, kind in ((LOAD, "load"), (AGENT, "agent"), (STAGE, "stage"), (ATTEMPT, "attempt"), (ENDED, "end")):
        match = pattern.match(line)
        if match:
            return kind, match
    return None, None


def events(text, since=0):
    raw = str(text or "")
    lines = raw.split("\n")[:-1] if raw else []
    found = []
    for line in lines[since:]:
        kind, match = _event(line.rstrip("\r"))
        if kind == "load":
            found.append({"kind": kind, "text": f"Modell geladen: {match['model']} (Fenster {match['window']})"})
        elif kind == "agent":
            found.append({"kind": kind, "text": f"Lauf {match['label'].strip()}: {match['stop']}, {match['calls']} Aufrufe, {float(match['seconds']):.0f} s"})
        elif kind == "stage":
            found.append({"kind": kind, "text": f"Stufe {match['name']} {'bestanden' if match['result'] == 'PASSED' else 'gescheitert'} ({float(match['seconds']):.0f} s)"})
        elif kind == "attempt":
            found.append({"kind": kind, "text": f"Versuch {match['n']}: {'bestanden' if match['result'] == 'PASSED' else 'gescheitert'}, {float(match['seconds']):.0f} s, {match['calls']} Aufrufe"})
        elif kind == "end":
            found.append({"kind": kind, "text": f"Bau beendet: {match['state']}"})
    return found, max(since, len(lines))
