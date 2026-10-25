r"""The measurement S2.1 of Spec 2 (model scheduler) in ONE command: main model and helper model with 1 to 4 slots (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, "Messplan-Entwurf S2.1").

    .venv\Scripts\python.exe benchmarks/slot_measurement.py <project_dir>                 prints the plan and the checks, starts NOTHING (dry run, no GPU use)
    .venv\Scripts\python.exe benchmarks/slot_measurement.py <project_dir> --go            the measurement (needs the start signal of the Captain)

    options: --recipe coder.local_primary   --small coder.llama_qwen35   --no-small   --slots 1,2,3,4   --limit-h 3   --small-limit-h 1   --max-temp 85   --wait 0

What it does, in this order, under ONE GPU lease (TestLab, with the usual leftover clean-up; refused when the card holds more than 3.0 GiB that is not a GUPPI server):
  per model and slot count N: S0 connection check (connection_check.check, S0 state NOT written), context ladder with N slots (context_ladder.ladder, window per slot),
  throughput of N parallel requests at the safe window up to 32768 (slot_throughput.throughput; for a recipe with MTP also without MTP);
  helper model additionally on the CPU (n_gpu_layers=0, slots 1 and 2, short answers).
What it never does: change a recipe, the engine or a switch (settings come from --set style overrides inside the run only; the configuration files are hashed before and after every
step and a change stops the run), stop a process by name (the runtime stops only the server it started itself, by its own PID), start a second GPU user.
It stops (partial result is still written) when: the lease or the preflight refuses; the GPU temperature goes above --max-temp; the GPU memory goes above 11.5 GiB; a step reports new
NVIDIA driver events; a step fails three times in a row; a configuration file changed; the time limit of a model is over (then the rest of that model is skipped, the next model goes on).
At the end: runtime_data/measurements/slot_messung_<date>.json and .md (the table for MODELLE.md) and one logbook row of kind MESSUNG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

VRAM_LIMIT_GIB = 11.5
WINDOW = 32768                     # the window per slot of the throughput runs (profile "standard"), lowered to the safe maximum of the ladder
LADDER_RANGE = {1: (32768, 131072), 2: (16384, 65536), 3: (16384, 49152), 4: (8192, 32768)}     # (--from, --max) per slot count; N=1 up to 32k is known from MODELLE.md
PROMPT_TPS = 800                   # assumed prompt speed for the time estimate only (not measured)
CPU_SLOTS = (1, 2)
CPU_TOKENS = 64


class Abort(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def file_hashes(paths):
    out = {}
    for path in paths:
        for f in sorted(Path(path).glob("*")):
            if f.is_file() and f.suffix.lower() in (".yaml", ".yml", ".json"):
                out[f.as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def estimate_minutes(step):
    """A rough time for the plan (assumption: PROMPT_TPS tokens/s of prompt processing; the real numbers come from this measurement)."""
    n = step["parallel"]
    if step["tool"] == "s0":
        return 4
    if step["tool"] == "throughput":
        return 3 + (2 if step.get("cpu") else 0)
    lo, hi = step.get("range") or LADDER_RANGE[n]
    tiers = [t for t in (8192, 16384, 24576, 32768, 49152, 65536, 98304, 131072) if lo <= t <= hi]
    return round(sum(1 + 2 * (n * 0.85 * t / PROMPT_TPS) / 60 for t in tiers))


def build_plan(main, small, slots, with_small=True, only=None, ranges=None):
    """only='ladder': just the context ladders; ranges: {'main': {2: [from, max], ...}, 'small': {...}} replaces LADDER_RANGE per model and slot count."""
    steps = []
    for model, label in ((main, "main"), (small, "small")):
        if model is None or (label == "small" and not with_small):
            continue
        for n in slots:
            ladder = {"model": model, "label": label, "parallel": n, "tool": "ladder"}
            given = ((ranges or {}).get(label) or {}).get(n)
            if given:
                ladder["range"] = (int(given[0]), int(given[1]))
            steps += [ladder] if only == "ladder" else [{"model": model, "label": label, "parallel": n, "tool": "s0"}, ladder,
                                                        {"model": model, "label": label, "parallel": n, "tool": "throughput"}]
        if label == "small" and only != "ladder":
            steps += [{"model": model, "label": label, "parallel": n, "tool": "throughput", "cpu": True} for n in CPU_SLOTS if n in slots]
    for step in steps:
        step["minutes"] = estimate_minutes(step)
    return steps


def describe(step):
    extra = " (CPU, n_gpu_layers=0)" if step.get("cpu") else ""
    return f"{step['model']} x{step['parallel']} {step['tool']}{extra}"


def gpu_temperature():
    out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True).stdout
    return int(out.split()[0])


def real_tools():
    from connection_check import check
    from context_ladder import driver_events_since, gpu_mib, ladder
    from slot_throughput import throughput
    return {"check": check, "ladder": ladder, "throughput": throughput, "temperature": gpu_temperature, "gpu": gpu_mib, "events": driver_events_since}


class Run:
    """The state of one measurement: the results so far, the time per model, the failure counter."""

    def __init__(self, project, recipes, tools, say, max_temp, limits, hash_paths, clock=time.monotonic, runtime_factory=None):
        self.project, self.recipes, self.tools, self.say, self.max_temp = project, recipes, tools, say, max_temp
        self.runtime_factory, self.runtime, self.on_row = runtime_factory, None, None
        self.limits, self.hash_paths, self.clock = limits, hash_paths, clock
        self.results, self.skipped, self.fails, self.started = [], [], 0, {}
        self.hashes = file_hashes(hash_paths)

    def guard(self):
        """Raises Abort when a stop condition holds (called before every step)."""
        if file_hashes(self.hash_paths) != self.hashes:
            raise Abort("config_changed")
        temp = self.tools["temperature"]()
        if temp is not None and temp > self.max_temp:
            raise Abort(f"temperature_{temp}")
        used, _total = self.tools["gpu"]()
        if used / 1024 > VRAM_LIMIT_GIB:
            raise Abort(f"vram_over_limit_{round(used / 1024, 2)}")

    def over_time(self, label):
        start = self.started.setdefault(label, self.clock())
        return self.clock() - start > self.limits[label] * 3600

    def judge(self, step, result):
        """Updates the failure counter, raises Abort for driver events, memory above the limit or three failures in a row."""
        status = status_of(result)
        events = result.get("driver_events") or sum((r.get("driver_events") or 0) for r in result.get("rows", []))
        peak = max([result.get("vram_peak_gib") or 0, (result.get("summary") or {}).get("vram_peak_gib") or 0]
                   + [r.get("vram_used_gib") or 0 for r in result.get("rows", [])])
        if events:
            raise Abort("driver_events")
        if peak > VRAM_LIMIT_GIB:
            raise Abort(f"vram_over_limit_{peak}")
        if step["tool"] == "s0" and status == "fail":
            return                                   # S0 does not pass on this PC (MODELLE.md): neither a failure nor a success
        self.fails = 0 if status == "ok" else self.fails + 1
        if status == "load_failed" and step["parallel"] == 1 and step["tool"] == "s0":
            raise Abort("server_does_not_start")
        if self.fails >= 3:
            raise Abort("three_failures_in_a_row")


def status_of(result):
    """One word for a step result: ok, fail (a check that did not pass: expected for S0 on this PC), load_failed or the status the tool gave."""
    if result.get("load_error"):
        return "load_failed"
    if "safe_max_context" in result:
        return "ok" if result["safe_max_context"] else ((result.get("rows") or [{}])[0].get("status") or "fail")
    return result.get("status") or ("ok" if result.get("ok") else "fail")


def run_step(run, step, say):
    recipe = run.recipes[step["model"]]
    tools = run.tools
    server = dict(recipe["profile"]["server"])
    if step["tool"] == "s0":
        return tools["check"](run.runtime, recipe, WINDOW, server, step["parallel"])
    if step["tool"] == "ladder":
        lo, hi = step.get("range") or LADDER_RANGE[step["parallel"]]
        return tools["ladder"](run.runtime, recipe, max_ctx=hi, probes=2, say=say, start=lo if lo > 8192 else 0, overrides=None, parallel=step["parallel"], on_row=run.on_row)
    ladder = next((r for r in reversed(run.results) if r["step"]["model"] == step["model"] and r["step"]["parallel"] == step["parallel"]
                   and r["step"]["tool"] == "ladder"), None)
    safe = ladder["result"].get("safe_max_context") if ladder else None
    window = min(WINDOW, safe) if safe else WINDOW
    if step.get("cpu"):
        return tools["throughput"](run.runtime, recipe, step["parallel"], window, 2, CPU_TOKENS, {**server, "n_gpu_layers": 0}, say=say, variant="cpu")
    variants = [("", server)]
    if server.get("mtp"):
        variants.append(("ohne_mtp", {**server, "mtp": False}))
    results = [tools["throughput"](run.runtime, recipe, step["parallel"], window, 3, 256, s, say=say, variant=name) for name, s in variants]
    return {"status": "ok" if all(r["status"] == "ok" for r in results) else next(r["status"] for r in results if r["status"] != "ok"), "variants": results,
            "summary": results[0].get("summary"), "vram_peak_gib": max((r.get("summary") or {}).get("vram_peak_gib") or 0 for r in results),
            "driver_events": sum(r.get("driver_events") or 0 for r in results)}


def table(results):
    """The rows for MODELLE.md (section "Parallele Slots") from the results: one row per model and slot count."""
    rows = ["| Modell | Slots | Fenster je Slot (sicher) | Gesamtkontext | VRAM-Spitze (GiB) | Token/s gesamt | Token/s je Slot | S0 | Hinweis |", "|---|---|---|---|---|---|---|---|---|"]
    keys = sorted({(r["step"]["model"], r["step"]["parallel"]) for r in results if not r["step"].get("cpu")}, key=lambda k: (k[0], k[1]))
    for model, n in keys:
        mine = [r for r in results if r["step"]["model"] == model and r["step"]["parallel"] == n and not r["step"].get("cpu")]
        pick = {r["step"]["tool"]: r["result"] for r in mine}
        safe = (pick.get("ladder") or {}).get("safe_max_context")
        summary = (pick.get("throughput") or {}).get("summary") or {}
        s0 = (pick.get("s0") or {})
        s0_text = "?" if not s0 else "ok" if s0.get("ok") else "Ladefehler" if s0.get("load_error") else "nicht bestanden"
        peak = summary.get("vram_peak_gib")
        notes = []
        for v in (pick.get("throughput") or {}).get("variants", [])[1:]:
            notes.append(f"{v.get('variant')}: {(v.get('summary') or {}).get('total_tps', '?')} tok/s")
        row = [model, str(n), str(safe or "?"), str(safe * n) if safe else "?", str(peak if peak is not None else "?"), str(summary.get("total_tps", "?")),
               str(summary.get("per_slot_tps", "?")), s0_text, "; ".join(notes)]
        rows.append("| " + " | ".join(row) + " |")
    for r in results:
        if r["step"].get("cpu"):
            s = (r["result"].get("summary") or {})
            rows.append(f"| {r['step']['model']} (CPU) | {r['step']['parallel']} | {r['result'].get('context_per_slot', '?')} | – | {s.get('vram_peak_gib', '?')} | "
                        f"{s.get('total_tps', '?')} | {s.get('per_slot_tps', '?')} | – | n_gpu_layers=0 |")
    return "\n".join(rows)


def execute(plan, run, lab_lease, say, logbook=None, out_dir=None, today=None):
    """Runs the plan under the lease. Returns the report dict (also when it stopped early)."""
    report = {"plan": plan, "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stopped": None, "skipped": []}
    try:
        with lab_lease as _token:
            run.runtime = run.runtime_factory()
            try:
                for step in plan:
                    if run.over_time(step["label"]):
                        report["skipped"].append(describe(step) + " (time limit)")
                        continue
                    run.guard()
                    say(f"== {describe(step)}  (about {step['minutes']} min)")
                    began = time.monotonic()
                    result = run_step(run, step, say)
                    run.results.append({"step": step, "result": result, "seconds": round(time.monotonic() - began, 1)})
                    run.judge(step, result)
            except Abort as exc:
                report["stopped"] = exc.reason
                say(f"STOP: {exc.reason}")
            except KeyboardInterrupt:
                report["stopped"] = "interrupted"
            finally:
                try:
                    run.runtime.unload_model(all_models=True)        # only the server this run started, by its own process
                except Exception:
                    pass
    except Exception as exc:                                         # lease busy or preflight refused: nothing ran
        report["stopped"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    report["results"] = run.results
    report["table"] = table(run.results)
    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if out_dir is not None:
        out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        stamp = today or date.today().isoformat()
        (out_dir / f"slot_messung_{stamp}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (out_dir / f"slot_messung_{stamp}.md").write_text(report["table"] + "\n", encoding="utf-8")
    if logbook is not None:
        good = sum(1 for r in run.results if status_of(r["result"]) == "ok")
        text = (f"Messung S2.1 Slots: {len(run.results)} von {len(plan)} Schritten gelaufen, {good} ok"
                + (f", gestoppt: {report['stopped']}" if report["stopped"] else ", vollstaendig") + f"; Tabelle und Rohdaten in slot_messung_{today or date.today().isoformat()}")
        logbook(text)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--recipe", default="coder.local_primary"); ap.add_argument("--small", default="coder.llama_qwen35"); ap.add_argument("--no-small", action="store_true")
    ap.add_argument("--slots", default="1,2,3,4"); ap.add_argument("--limit-h", type=float, default=3.0); ap.add_argument("--small-limit-h", type=float, default=1.0)
    ap.add_argument("--max-temp", type=int, default=85); ap.add_argument("--wait", type=float, default=0)
    ap.add_argument("--guppi", default=None, help="the installed runtime folder (<guppi>): its engines/ folder and runtime/config/local_paths.yaml are used when this script runs from a worktree that has neither")
    ap.add_argument("--only", choices=("ladder",), default=None, help="run only the context ladders (no S0, no throughput)")
    ap.add_argument("--ladder", default=None, help='JSON {"main": {"2": [from, max], ...}, "small": {...}}: window per slot to start at and to stop at')
    ap.add_argument("--go", action="store_true", help="really run (without it: print the plan and the checks only)")
    ap.add_argument("--logbook", default=None, help="logbook file (default: docs/LOGBUCH_AGENT_MANAGER.md)")
    args = ap.parse_args(argv)
    slots = [int(s) for s in args.slots.split(",") if s.strip()]
    if not slots or any(n not in LADDER_RANGE for n in slots):
        raise SystemExit("--slots: numbers from 1 to 4")
    project = Path(args.project)
    recipes = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
    main_id, small_id = args.recipe, (None if args.no_small else args.small)
    problems = [f"recipe {rid} is not a llama-cpp-server recipe of this project" for rid in (main_id, small_id)
                if rid and (rid not in recipes or recipes[rid].get("provider") != "llama-cpp-server")]
    problems += [f"model file of {rid} is missing" for rid in (main_id, small_id)
                 if rid and rid in recipes and not Path(str(recipes[rid]["profile"]["server"].get("gguf", ""))).is_file()]
    ranges = {lab: {int(n): rng for n, rng in per.items()} for lab, per in json.loads(args.ladder).items()} if args.ladder else None
    plan = build_plan(main_id, small_id, slots, with_small=not args.no_small, only=args.only, ranges=ranges)
    total = sum(s["minutes"] for s in plan)
    print(f"Plan: {len(plan)} steps, about {total} min ({total / 60:.1f} h; estimate from an assumed prompt speed of {PROMPT_TPS} tok/s, not measured); limits {args.limit_h} h main, {args.small_limit_h} h helper")
    for s in plan:
        print(f"  {describe(s):70s} ~{s['minutes']:3d} min")
    from guppi_runtime.jobs.testlab import TestLab, default_path
    holder = TestLab(default_path(project)).holder()
    print("GPU lease:", "free" if not holder or holder["stale"] else f"HELD by {holder['owner']} ({holder['purpose']})")
    for p in problems:
        print("PROBLEM:", p)
    if not args.go:
        print("Dry run: nothing was started. Run with --go after the start signal.")
        return 1 if problems else 0
    if problems:
        return 2
    from guppi_runtime.models.gpu_preflight import clear_leftovers
    from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    lab = TestLab(default_path(project))
    owner = os.environ.get("TESTLAB_OWNER", "slot_measurement")
    qid = lab.plan(owner, "slot-messung", "Slots 1-4 Hauptmodell und Hilfsmodell (Spec 2, S2.1)", [m for m in (main_id, small_id) if m])
    say = lambda s: print(s, flush=True)             # noqa: E731
    guppi = Path(args.guppi) if args.guppi else None
    hash_paths = [project / "local_config", RUNTIME / "config"] + ([guppi / "runtime" / "config"] if guppi else [])
    run = Run(project, recipes, real_tools(), say, args.max_temp, {"main": args.limit_h, "small": args.small_limit_h}, hash_paths)

    def factory():
        if guppi:                                    # read-only use of the installation: engines and the folders of this PC; no file of it is changed
            from guppi_runtime import local_paths
            local_paths.FILE = guppi / "runtime" / "config" / "local_paths.yaml"
        config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled, config.mtp = True, True
        if guppi:
            config.engine_root = str(guppi / "engines")
        return LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_slotmeasure_")))
    run.runtime_factory = factory
    rows_file = project / "runtime_data" / "measurements" / f"slot_messung_{date.today().isoformat()}.rows.jsonl"
    rows_file.parent.mkdir(parents=True, exist_ok=True)

    def keep_row(recipe_id, parallel, row):
        with rows_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"recipe": recipe_id, "parallel": parallel, "row": row}, ensure_ascii=False, default=str) + "\n")
    run.on_row = keep_row
    import logbook as logbook_tool

    def log(text):
        path = args.logbook or logbook_tool.DEFAULT
        logbook_tool.append(path, logbook_tool.make_row("MESSUNG", text, "benchmarks/slot_measurement.py"))
    run_id = lab.start_run(owner, "slot-messung", "S2.1 Slots", {"slots": slots, "main": main_id, "small": small_id}, queue_id=qid)
    report = execute(plan, run, lab.lease(owner, "slot measurement S2.1", ttl_s=1800, wait_s=args.wait, preflight=clear_leftovers), say, logbook=log,
                     out_dir=project / "runtime_data" / "measurements")
    lab.finish_run(run_id, "done" if not report["stopped"] else "aborted")
    print(report["table"])
    print("stopped:", report["stopped"] or "no (complete)")
    return 0 if not report["stopped"] else 3


if __name__ == "__main__":
    sys.exit(main())
