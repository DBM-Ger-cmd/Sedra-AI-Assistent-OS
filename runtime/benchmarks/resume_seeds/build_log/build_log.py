import re


def parse_log(text):
    result = {"s0": None, "spec": None, "started": None, "loads": [], "open_agents": [], "stages": [], "stopped_after": None, "skipped": [], "attempt": None, "resume": None, "ended": False, "end_state": None, "report": None}
    text = str(text or "")
    lines = text.splitlines()
    for line in lines:
        if line.startswith("S0 connection check:"):
            m = re.match(r"S0 connection check:\s+(\S+)\s+(\S+)", line)
            if m:
                result["s0"] = {"recipe": m.group(1), "state": m.group(2)}
        elif line.startswith("# run ") and "started" in line and "config" in line:
            m = re.match(r"# run\s+(\S+)\s+started\s+(.+?)\s+config\s+(.*)", line)
            if m:
                result["started"] = m.group(2).strip()
                config_str = m.group(3).strip()
                spec_m = re.search(r'"spec":\s*"([^"]*)"', config_str)
                if spec_m:
                    result["spec"] = spec_m.group(1)
        elif line.startswith("# run ") and "started" in line and "config" not in line:
            m = re.match(r"# run\s+(\S+)\s+started\s+(.+)", line)
            if m:
                result["started"] = m.group(2).strip()
        elif line.startswith("   load "):
            m = re.match(r"   load\s+(\S+)\s+with a window of\s+(\d+)\s+tokens in each of\s+(\d+)\s+slot\(s\)", line)
            if m:
                result["loads"].append({
                    "model": m.group(1),
                    "window": int(m.group(2)),
                    "slots": int(m.group(3))
                })
        elif line.startswith("   agent "):
            m = re.match(r"   agent\s+(.+?)\s+(\S+)\s+(\S+)\s+(\d+)\s+calls\s+([\d.]+)\s+s\s+(\d+)\s+tokens,\s+(\d+)\s+prompt,\s+peak\s+(\d+)", line)
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
            m = re.match(r"   stage\s+(\S+):\s+hidden\s+(PASSED|FAILED)\s+\((.+)\s+([\d.]+)\s+s\)", line)
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
            m = re.match(r"   stopped after the failed stage (\S+); skipped: (.+?)(?:\s+\((.+))?$", line)
            if m:
                result["stopped_after"] = m.group(1)
                skipped_str = m.group(2).strip()
                result["skipped"] = [s.strip() for s in skipped_str.split(",")]
        elif line.startswith("attempt "):
            m = re.match(r"attempt\s+(\d+):\s+hidden test\s+(PASSED|FAILED)\s+\|\s+(.+?)\s+\|\s+([\d.]+)\s+s,\s+(\d+)\s+agent runs,\s+(\d+)\s+calls\s+->\s+(.+)", line)
            if m:
                result["attempt"] = {
                    "number": int(m.group(1)),
                    "passed": m.group(2) == "PASSED",
                    "seconds": float(m.group(3)),
                    "agent_runs": int(m.group(4)),
                    "calls": int(m.group(5)),
                    "exported_to": m.group(6).strip()
                }
        elif line.startswith("   resume: "):
            result["resume"] = line[len("   resume: "):]
        elif line.startswith("# run ended: "):
            result["ended"] = True
            result["end_state"] = line[len("# run ended: "):].strip()
        elif line.startswith("DONE -> "):
            result["report"] = line[len("DONE -> "):].strip()
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
        run_word = "Lauf" if agent_runs == 1 else "Laufe"
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
    lines = text.splitlines(True)
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
            m = re.match(r"   load\s+(\S+)\s+with a window of\s+(\d+)\s+tokens in each of\s+(\d+)\s+slot\(s\)", line)
            if m:
                result.append({"kind": "load", "text": f"Modell geladen: {m.group(1)} (Fenster {m.group(2)})"})
        elif line.startswith("   agent "):
            m = re.match(r"   agent\s+(.+?)\s+(\S+)\s+(\S+)\s+(\d+)\s+calls\s+([\d.]+)\s+s\s+(\d+)\s+tokens,\s+(\d+)\s+prompt,\s+peak\s+(\d+)", line)
            if m:
                label = m.group(1).strip()
                stopped_by = m.group(3)
                calls = m.group(4)
                seconds = float(m.group(5))
                result.append({"kind": "agent", "text": f"Lauf {label}: {stopped_by}, {calls} Aufrufe, {seconds:.0f} s"})
        elif line.startswith("   stage "):
            m = re.match(r"   stage\s+(\S+):\s+hidden\s+(PASSED|FAILED)\s+\((.+)\s+([\d.]+)\s+s\)", line)
            if m:
                name = m.group(1)
                passed_str = m.group(2)
                seconds = float(m.group(4))
                if passed_str == "PASSED":
                    result.append({"kind": "stage", "text": f"Stufe {name} bestanden ({seconds:.0f} s)"})
                else:
                    result.append({"kind": "stage", "text": f"Stufe {name} gescheitert ({seconds:.0f} s)"})
        elif line.startswith("attempt "):
            m = re.match(r"attempt\s+(\d+):\s+hidden test\s+(PASSED|FAILED)\s+\|\s+([^\|]*)\|\s+([\d.]+)\s+s,\s+(\d+)\s+agent runs,\s+(\d+)\s+calls\s+->\s+(.+)", line)
            if m:
                n = m.group(1)
                passed_str = m.group(2)
                seconds = float(m.group(3))
                calls = m.group(4)
                if passed_str == "PASSED":
                    result.append({"kind": "attempt", "text": f"Versuch {n}: bestanden, {seconds:.0f} s, {calls} Aufrufe"})
                else:
                    result.append({"kind": "attempt", "text": f"Versuch {n}: gescheitert, {seconds:.0f} s, {calls} Aufrufe"})
        elif line.startswith("# run ended: "):
            state = line[len("# run ended: "):].strip()
            result.append({"kind": "end", "text": f"Bau beendet: {state}"})
    return result, next_index
