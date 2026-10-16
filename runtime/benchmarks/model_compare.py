r"""Saves and compares the results of the model tests (Captain 2026-10-09: keep the outcome of every test so that models can be compared later).

    .venv\Scripts\python.exe benchmarks/model_compare.py <project_dir> [--out docs/MODELL_VERGLEICH_ERGEBNISSE.md]

It reads what the tests already leave behind and writes ONE table file, so nothing has to be copied by hand:
  speed   runtime_data/measurements/moe_sweep_*.json (every moe_sweep run) and model_comparison_manual.json (rows of earlier runs whose file was overwritten)
  builds  runtime_data/measurements/logs/devvm_build_*.json with the tokens of the matching .log, per attempt (failed attempts count too), plus the built and the used code lines of the exported candidate
The table is rebuilt on every call; the sources stay untouched.
"""
import argparse
import json
import re
from pathlib import Path

TOKENS = re.compile(r" s (\d+) tokens(?:, (\d+) prompt)?")
ATTEMPT_END = re.compile(r"attempt (\d+): hidden test (?:PASSED|FAILED)")


def speed_rows(measurements):
    rows = []
    for path in sorted(Path(measurements).glob("moe_sweep_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for row in data.get("rows", []):
            if "error" not in row:
                rows.append({**row, "recipe": data.get("recipe"), "source": path.name})
    manual = Path(measurements) / "model_comparison_manual.json"
    if manual.is_file():
        try:
            rows += [{**row, "source": "manual"} for row in json.loads(manual.read_text(encoding="utf-8")).get("speed", [])]
        except (OSError, ValueError):
            pass
    return rows


def editor_rows(measurements):
    """Sessions of GUPPI models in an editor (VS Code with Cline or Continue): rows of the key "editor_sessions" in model_comparison_manual.json."""
    manual = Path(measurements) / "model_comparison_manual.json"
    try:
        return list(json.loads(manual.read_text(encoding="utf-8")).get("editor_sessions", []))
    except (OSError, ValueError):
        return []


def attempt_tokens(log_path, prompt=False):
    """{attempt number: generated tokens of all agent lines up to the line that closes that attempt} (a failed attempt counts too; with prompt=True the tokens READ IN, which the DevVM logs since 2026-10-09); None when the log is unreadable."""
    try:
        lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    totals, running = {}, 0
    for line in lines:
        found = TOKENS.search(line) if " agent " in line else None
        running += int(found.group(2 if prompt else 1) or 0) if found else 0
        closed = ATTEMPT_END.search(line)
        if closed:
            totals[int(closed.group(1))], running = running, 0
    if running and totals:
        totals[max(totals)] += running
    return totals


def code_lines(folder, seed_folder=None):
    """Non-empty lines of the code files (.py without tests and acceptance scripts) of a candidate folder; a file that is byte-identical to a file of the seed folder is the seed's, not the model's (only a seed that is not newer than the candidate: a seed copied afterwards, for a retry, is not the seed of that run)."""
    folder, count = Path(folder), 0
    if not folder.is_dir():
        return None
    for path in sorted(folder.rglob("*.py")):
        relative = path.relative_to(folder).as_posix()
        if relative.startswith("tests/") or path.name.startswith(("test_", "acceptance_")):
            continue
        seed = Path(seed_folder) / relative if seed_folder else None
        if seed and seed.is_file() and seed.stat().st_mtime <= path.stat().st_mtime + 1 and seed.read_bytes() == path.read_bytes():
            continue
        count += sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    return count


def candidate_folder(project, exported):
    text = str(exported or "").replace("\\", "/")
    marker = "runtime_data/devvm_candidates/"
    return Path(project) / "runtime_data" / "devvm_candidates" / text.split(marker, 1)[1] if marker in text else None


def build_rows(logs, project=None):
    """One row per attempt: its own tokens (failed attempts too), the code lines the model built and the lines of the attempt that passed."""
    rows = []
    for path in sorted(Path(logs).glob("devvm_build_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tokens = attempt_tokens(path.with_suffix(".log")) or {}
        prompt_tokens = attempt_tokens(path.with_suffix(".log"), prompt=True) or {}
        for attempt in data.get("attempts", []):
            stages, seconds = attempt.get("stages", []), attempt.get("seconds")
            models = attempt.get("models") or {"coder": attempt.get("coder")}
            if "fake-model" in set(str(m) for m in models.values()): continue      # a rehearsal with a scripted fake model is no measurement
            used_tokens = tokens.get(attempt.get("attempt"))
            read_in = prompt_tokens.get(attempt.get("attempt")) or None
            folder = candidate_folder(project, attempt.get("exported_to")) if project else None
            seeds = Path(project) / "runtime_data" / "agent_manager" / "seeds" / str(data.get("spec")) if project else None
            built = code_lines(folder, seeds if seeds and seeds.is_dir() else None) if folder else None
            passed = bool(attempt.get("hidden_passed"))
            rows.append({"run": path.stem, "attempt": attempt.get("attempt"), "spec": data.get("spec"), "models": sorted(set(str(m) for m in models.values() if m)), "mode": mode_label(attempt), "seconds": seconds,
                         "stages_passed": sum(1 for s in stages if s.get("hidden_passed")), "stages": len(stages), "passed": passed, "agent_runs": attempt.get("agent_runs"), "calls": attempt.get("calls"),
                         "tokens": used_tokens, "prompt_tokens": read_in, "tokens_per_second": round(used_tokens / seconds, 1) if used_tokens and seconds else None, "built_lines": built, "own_tests_failed": sum(1 for s in stages if (s.get("own_tests") or {}).get("present") and not s["own_tests"].get("passed")),
                         "used_lines": None if built is None else (built if passed else 0), "layer_cell": attempt.get("layer_cell")})
    return rows


def mode_label(attempt):
    """The way of working of an attempt: escalating (several agents) or solo, with the options of the step plan (older results have no option fields)."""
    if attempt.get("agent") == "qwen-code": return "Qwen Code (" + str(attempt.get("system_prompt") or "asis") + ") + " + str(attempt.get("self_check") or "none")
    mode = attempt.get("mode") or "escalating"
    extras = [name for name, flag in (("Plan", "plan_steps"), ("frischer Rework", "fresh_rework"), ("Syntaxprüfung", "step_syntax_check")) if attempt.get(flag)]
    return mode + (" + " + " + ".join(extras) if extras else "")


def summary_rows(builds):
    """Per spec and model over ALL attempts: the tokens that were needed (failed attempts included), the code built, the code used (of the attempts that passed) and the tokens per used line."""
    groups = {}
    for row in builds:
        group = groups.setdefault((str(row["spec"]), ", ".join(row["models"])), {"tokens": 0, "built": 0, "used": 0, "attempts": 0, "passed": 0})
        group["attempts"] += 1
        group["passed"] += 1 if row["passed"] else 0
        group["tokens"] += row["tokens"] or 0
        group["built"] += row["built_lines"] or 0
        group["used"] = max(group["used"], row["used_lines"] or 0)
    return [{"spec": spec, "models": models, **group, "tokens_per_used_line": round(group["tokens"] / group["used"]) if group["used"] else None} for (spec, models), group in sorted(groups.items())]


def render(speed, builds, editor=()):
    lines = ["# Modellvergleich: Ergebnisse der Tests", "", "Erzeugt von `benchmarks/model_compare.py` aus den Messdateien (nicht von Hand ändern).", "",
             "## Geschwindigkeit (moe_sweep: ein Prompt, höchstens 256 Token Antwort)", "", "| Rezept | Fenster | n_cpu_moe | ubatch | Prompt-Token | Einlesen Token/s | Erzeugen Token/s | frei GiB | Quelle |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(speed, key=lambda r: (str(r.get("recipe")), r.get("window") or 0, r.get("ubatch") or 0, -(r.get("n_cpu_moe") or 0))):
        lines.append(f"| {r.get('recipe')} | {r.get('window')} | {r.get('n_cpu_moe')} | {r.get('ubatch')} | {r.get('prompt_tokens')} | {r.get('prompt_tps')} | {r.get('gen_tps')} | {r.get('free_gib')} | {r.get('source')} |")
    lines += ["", "## Aufwand je Spec und Modell (alle Versuche, gescheiterte eingerechnet)", "",
              "Benötigte Token = Summe aller Versuche. Gebauter Code = Codezeilen (ohne Tests, ohne Saat-Dateien) in allen Versuchen. Genutzter Code = Zeilen des Versuchs, der die versteckten Tests bestanden hat (0 ohne Erfolg).", "",
              "| Spec | Modelle | Versuche (bestanden) | Benötigte Token | Gebauter Code (Zeilen) | Genutzter Code (Zeilen) | Token je genutzter Zeile |", "|---|---|---|---|---|---|---|"]
    for s in summary_rows(builds):
        lines.append(f"| {s['spec']} | {s['models']} | {s['attempts']} ({s['passed']}) | {s['tokens']} | {s['built']} | {s['used']} | {s['tokens_per_used_line']} |")
    lines += ["", "## Bauläufe je Versuch (DevVM, versteckte Tests)", "", "Die Token jedes Versuchs stammen aus dem Log bis zu dessen Abschlusszeile; auch gescheiterte Versuche zählen. Prompt-Token = alle an das Modell gesendeten Token einschließlich der aus dem Zwischenspeicher des Servers (usage.prompt_tokens): sie sind NICHT mit den neu verarbeiteten Token der Editor-Sitzungen (Serverlog) vergleichbar.", "",
              "| Lauf | Versuch | Spec | Modelle | Modus | Dauer s | Stufen bestanden | Aufrufe | Tokens erzeugt | Prompt-Token | Token/s | Gebauter Code | Genutzter Code | Stufen mit gescheiterten eigenen Tests | bestanden | Schichten, Anteil Zeit % (1 Server, 2 Anbindung, 3 Verhalten, 4 Budget, 5 Verständnis, ok) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in builds:
        lines.append(f"| {r['run']} | {r['attempt']} | {r['spec']} | {', '.join(r['models'])} | {r['mode']} | {r['seconds']} | {r['stages_passed']}/{r['stages']} | {r['calls']} | {r['tokens']} | {r['prompt_tokens']} | {r['tokens_per_second']} | {r['built_lines']} | {r['used_lines']} | {r['own_tests_failed']} | {'ja' if r['passed'] else 'nein'} | {r.get('layer_cell') or '–'} |")
    if editor:
        lines += ["", "## Sitzungen im Editor (VS Code, GUPPIs Modell über den lokalen Server)", "",
                  "| Werkzeug | Modell | Aufgabe | Dauer min | Anfragen | Prompt-Token | Erzeugte Token | Werkzeugaufrufe (Fehler) | versteckte Suite | Code / Tests (Zeilen) | Ordner |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in editor:
            lines.append(f"| {s.get('tool')} | {s.get('model')} | {s.get('task')} | {s.get('minutes')} | {s.get('requests')} | {s.get('prompt_tokens')} | {s.get('generated_tokens')} | {s.get('tool_calls')} ({s.get('tool_errors')}) | {s.get('suite')} | {s.get('code_lines')} / {s.get('test_lines')} | {s.get('folder')} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    project = Path(args.project)
    measurements = project / "runtime_data" / "measurements"
    text = render(speed_rows(measurements), build_rows(measurements / "logs", project), editor_rows(measurements))
    out = Path(args.out) if args.out else measurements / "MODELL_VERGLEICH_ERGEBNISSE.md"
    out.write_text(text, encoding="utf-8")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
