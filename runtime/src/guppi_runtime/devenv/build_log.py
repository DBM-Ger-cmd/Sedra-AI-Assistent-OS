import re

S0_RE = re.compile(r"S0 connection check:\s+(\S+)\s+(\S+)")
RUN_STARTED_CONFIG_RE = re.compile(r"# run\s+(\S+)\s+started\s+(.+?)\s+config\s+(.*)")
RUN_STARTED_RE = re.compile(r"# run\s+(\S+)\s+started\s+(.+)")
LOAD_RE = re.compile(r"   load\s+(\S+)\s+with a window of\s+([0-9]+)\s+tokens in each of\s+([0-9]+)\s+slot\(s\)")
AGENT_RE = re.compile(r"   agent\s+(.+?)\s+(\S+)\s+(\S+)\s+([0-9]+)\s+calls\s+([0-9.]+)\s+s\s+([0-9]+)\s+tokens,\s+([0-9]+)\s+prompt,\s+peak\s+([0-9]+)")
STAGE_RE = re.compile(r"   stage\s+(\S+):\s+hidden\s+(PASSED|FAILED)\s+\((.+)\s+([0-9.]+)\s+s\)")
STOPPED_RE = re.compile(r"   stopped after the failed stage (\S+); skipped: (.+?)(?:\s+\((.+))?$")
ATTEMPT_RE = re.compile(r"attempt\s+(?P<number>[0-9]+):\s+hidden test\s+(?P<passed>PASSED|FAILED)\s+\|\s+(?P<middle>.+?)\s+\|\s+(?P<seconds>[0-9.]+)\s+s,\s+(?P<agent_runs>[0-9]+)\s+agent runs,\s+(?P<calls>[0-9]+)\s+calls\s+->\s+(?P<exported_to>.+)")
RESUME_RE = re.compile(r"   resume:\s+(.+)")
RUN_ENDED_RE = re.compile(r"# run ended:\s+(.+)")
DONE_RE = re.compile(r"DONE -> (.+)")
SPEC_RE = re.compile(r'"spec":\s*"([^"]*)"')


def parse_log(text):
    result = {"s0": None, "spec": None, "started": None, "loads": [], "open_agents": [], "stages": [], "stopped_after": None, "skipped": [], "attempt": None, "resume": None, "ended": False, "end_state": None, "report": None}
    text = str(text or "")
    lines = text.splitlines()
    for line in lines:
        if line.startswith("S0 connection check:"):
            m = S0_RE.match(line)
            if m:
                result["s0"] = {"recipe": m.group(1), "state": m.group(2)}
        elif line.startswith("# run ") and "started" in line and "config" in line:
            m = RUN_STARTED_CONFIG_RE.match(line)
            if m:
                result["started"] = m.group(2).strip()
                config_str = m.group(3).strip()
                spec_m = SPEC_RE.search(config_str)
                if spec_m:
                    result["spec"] = spec_m.group(1)
        elif line.startswith("# run ") and "started" in line and "config" not in line:
            m = RUN_STARTED_RE.match(line)
            if m:
                result["started"] = m.group(2).strip()
        elif line.startswith("   load "):
            m = LOAD_RE.match(line)
            if m:
                result["loads"].append({
                    "model": m.group(1),
                    "window": int(m.group(2)),
                    "slots": int(m.group(3))
                })
        elif line.startswith("   agent "):
            m = AGENT_RE.match(line)
            if m:
                label = m.group(1).strip()
                result["open_agents"].append({
                    "label": label,
                    "model": m.group(2),
                    "stopped_by": m.group(3),
                    "calls": int(m.group(4)),
                    "seconds": float(m.group(5)),
                    "tokens": int(m.group(6)),
                    "prompt": int(m.group(7)),
                    "peak": int(m.group(8))
                })
        elif line.startswith("   stage "):
            stage_agents = list(result["open_agents"])
            result["open_agents"] = []
            m = STAGE_RE.match(line)
            if m:
                name = m.group(1)
                passed_str = m.group(2)
                seconds = float(m.group(4))
                passed = passed_str == "PASSED"
                reworks = sum(1 for a in stage_agents if "(rework" in a["label"])
                halt = stage_agents[-1]["stopped_by"] if stage_agents else None
                result["stages"].append({
                    "name": name,
                    "passed": passed,
                    "seconds": seconds,
                    "agents": stage_agents,
                    "reworks": reworks,
                    "halt": halt
                })
        elif line.startswith("   stopped after the failed stage "):
            m = STOPPED_RE.match(line)
            if m:
                result["stopped_after"] = m.group(1)
                skipped_str = m.group(2).strip()
                result["skipped"] = [s.strip() for s in skipped_str.split(",")]
        elif line.startswith("attempt "):
            m = ATTEMPT_RE.match(line)
            if m:
                result["attempt"] = {
                    "number": int(m.group("number")),
                    "passed": m.group("passed") == "PASSED",
                    "seconds": float(m.group("seconds")),
                    "agent_runs": int(m.group("agent_runs")),
                    "calls": int(m.group("calls")),
                    "exported_to": m.group("exported_to").strip()
                }
        elif line.startswith("   resume: "):
            m = RESUME_RE.match(line)
            if m:
                result["resume"] = m.group(1)
        elif line.startswith("# run ended: "):
            result["ended"] = True
            m = RUN_ENDED_RE.match(line)
            if m:
                result["end_state"] = m.group(1).strip()
        elif line.startswith("DONE -> "):
            m = DONE_RE.match(line)
            if m:
                result["report"] = m.group(1).strip()
    return result


def summary(parsed):
    lines = []
    stages = parsed.get("stages", [])
    skipped = parsed.get("skipped", [])
    spec = parsed.get("spec")
    passed_count = sum(1 for s in stages if s["passed"])
    total = len(stages) + len(skipped)
    failed_names = [s["name"] for s in stages if not s["passed"]]
    spec_str = spec if spec is not None else "?"
    line1 = f"Bau {spec_str}: {passed_count} von {total} Stufen bestanden"
    if failed_names:
        line1 += f", gescheitert: {', '.join(failed_names)}"
    if skipped:
        line1 += f", nicht gebaut: {', '.join(skipped)}"
    lines.append(line1)
    attempt = parsed.get("attempt")
    if attempt is not None:
        seconds = attempt["seconds"]
        calls = attempt["calls"]
        agent_runs = attempt["agent_runs"]
        run_word = "Lauf" if agent_runs == 1 else "Läufe"
        lines.append(f"Zeit {seconds:.0f} s, {calls} Aufrufe, {agent_runs} {run_word}")
    for s in stages:
        reworks = s["reworks"]
        if reworks == 0:
            rework_text = "keine Nacharbeit"
        elif reworks == 1:
            rework_text = "1 Nacharbeit"
        else:
            rework_text = f"{reworks} Nacharbeiten"
        if s["passed"]:
            lines.append(f"  {s['name']}: bestanden, {rework_text}, {s['seconds']:.0f} s")
        else:
            halt = s.get("halt")
            lines.append(f"  {s['name']}: GESCHEITERT, {rework_text}, letzter Halt {halt}, {s['seconds']:.0f} s")
    stopped_after = parsed.get("stopped_after")
    if stopped_after is not None:
        lines.append(f"Fortsetzbar ab Stufe {stopped_after}")
    if not parsed.get("ended", False):
        lines.append("Bau läuft noch")
    return "\n".join(lines) + "\n"


def events(text, since=0):
    result = []
    lines = (text or "").splitlines(True)
    complete_lines = []
    for i, line in enumerate(lines):
        if line.endswith("\n"):
            complete_lines.append((i, line[:-1]))
        else:
            break
    next_index = max(len(complete_lines), since)
    for idx, (line_num, line) in enumerate(complete_lines):
        if line_num < since:
            continue
        if line.startswith("   load "):
            m = LOAD_RE.match(line)
            if m:
                result.append({"kind": "load", "text": f"Modell geladen: {m.group(1)} (Fenster {m.group(2)})"})
        elif line.startswith("   agent "):
            m = AGENT_RE.match(line)
            if m:
                label = m.group(1).strip()
                stopped_by = m.group(3)
                calls = m.group(4)
                seconds = float(m.group(5))
                result.append({"kind": "agent", "text": f"Lauf {label}: {stopped_by}, {calls} Aufrufe, {seconds:.0f} s"})
        elif line.startswith("   stage "):
            m = STAGE_RE.match(line)
            if m:
                name = m.group(1)
                passed_str = m.group(2)
                seconds = float(m.group(4))
                if passed_str == "PASSED":
                    result.append({"kind": "stage", "text": f"Stufe {name} bestanden ({seconds:.0f} s)"})
                else:
                    result.append({"kind": "stage", "text": f"Stufe {name} gescheitert ({seconds:.0f} s)"})
        elif line.startswith("attempt "):
            m = ATTEMPT_RE.match(line)
            if m:
                n = m.group("number")
                passed_str = m.group("passed")
                seconds = float(m.group("seconds"))
                calls = m.group("calls")
                if passed_str == "PASSED":
                    result.append({"kind": "attempt", "text": f"Versuch {n}: bestanden, {seconds:.0f} s, {calls} Aufrufe"})
                else:
                    result.append({"kind": "attempt", "text": f"Versuch {n}: gescheitert, {seconds:.0f} s, {calls} Aufrufe"})
        elif line.startswith("# run ended: "):
            state = line[len("# run ended: "):].strip()
            result.append({"kind": "end", "text": f"Bau beendet: {state}"})
    return result, next_index
