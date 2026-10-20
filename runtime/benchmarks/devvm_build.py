"""GUPPI builds a module itself in a DevVM workspace (Captain 2026-10-06: build approved, integration NOT approved).

    .venv\\Scripts\\python.exe benchmarks/devvm_build.py <project_dir> --spec <name> --profile standard

The ONE way to build (Captain 2026-10-20, line L1): first `benchmarks/spec_check.py <name> --vm --project <project_dir>` (it writes the stamp this script needs), then the
build with --profile standard (single flags override the profile). Options of finished measurements need --experimental.

A spec (benchmarks/devvm_specs/<name>.py) holds TASK (the text GUPPI gets), NOTES (a NOTES.md that is put in the workspace) and HIDDEN (acceptance files the agents never see).
The default orchestrator mode (escalating: Jan alone -> Qwen3-Coder writes the check -> executed test -> strong coder only on failure) builds the module; afterwards the hidden test
runs in the microVM against the result. Each attempt exports its files to <project>/runtime_data/devvm_candidates/<spec>/<attempt>/ and the run is logged (RunLog + TestLab lease).
Nothing is copied into the runtime source tree: integration stays a separate decision of the Captain.
"""
import argparse
import importlib
import json
import re
import shutil
import os
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import devvm_agents_bench as bench                                                   # noqa: E402
import logbook                                                                       # noqa: E402
import spec_stamp                                                                    # noqa: E402
from devvm_vm import sandbox_text, vm_env                                            # noqa: E402
from guppi_runtime.devvm import DevWorkspace
from guppi_runtime.devvm_evidence import DRIVER, bug_report, parse as parse_evidence
from guppi_runtime.devvm_style import snapshot as ws_snapshot                                         # noqa: E402
from guppi_runtime.devvm_agents import DevOrchestrator, ModelHost                    # noqa: E402
from guppi_runtime.gpu_preflight import clear_leftovers
from guppi_runtime.knowledge import KnowledgeStore
from guppi_runtime.devenv.lesson_store import default_path as lesson_cards_path, lesson_for
from guppi_runtime.layer_summary import cell as layer_cell, summary as layer_table
from guppi_runtime.s0_status import status as s0_state                              # noqa: E402
from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.run_log import RunLog                                             # noqa: E402
from guppi_runtime.testlab import TestLab, default_path                              # noqa: E402


REWORK_TASK = ("{task}\n\nThe work is in the workspace, but an acceptance test of the Captain fails (you do not see the test, only its output):\n{output}\n\n"
               "Read the files, find the cause and fix it with edit_file (small exact changes, do not write the whole file again); keep everything that already works. Do NOT commit. Hand in with submit_result.")


NL = chr(10)
DEFAULT_MODEL = "coder.local_primary"      # the standard coder of GUPPI: Qwen3.6-35B-A3B since 2026-10-09 (was Qwen3-Coder, now the recipe coder.llama_qwen3_coder, key qwen3coder)
THINK_LIMIT = 2000      # e02: thinking tokens per answer before the note, then thinking is switched down (the options --think-limit and --think-family were removed 2026-10-20, ANA-10)
THINK_FAMILY = {DEFAULT_MODEL: "qwen"}      # E-21: how a model switches its thinking down (E-02); keys whose name says it are found by think_family()


def think_family(key):
    """qwen (enable_thinking false) | gptoss (reasoning_effort low) | other (no switch) for a model key."""
    key = str(key or "")
    if key in THINK_FAMILY: return THINK_FAMILY[key]
    low = key.lower()
    return "gptoss" if "oss" in low else "qwen" if "qwen" in low else "other"


def coder_ext_config(args):
    """The config for every agent run (E-21): the coder extensions of --coder-ext (a typo stops the build before a model is loaded) and the recording of the server answers,
    which is ON for every build unless --no-record (2026-10-12: the night run had no recording, so its 135 syntax notes could not be traced to the calls). None = neither."""
    enabled = args.coder_ext or ""
    if enabled:
        from guppi_runtime.coder_ext import parse_enabled
        parse_enabled(enabled)
    skills = None
    if args.skills:
        from guppi_runtime.skill_library import SkillLibrary
        from guppi_runtime.skill_library.config import library_path
        try: skills = str(library_path(args.skills))
        except KeyError: raise SystemExit(f"--skills {args.skills}: not a configured library (core, full) and no library folder")
        SkillLibrary(skills)      # a missing or broken library stops the build here
    if not enabled and args.no_record and not args.bg_jobs and not skills: return None
    return {"enabled": enabled, "think_limit": THINK_LIMIT, "family": think_family(args.all_models or args.coder),
            "window": 32768 if args.context == "max" else int(args.context), "record": not args.no_record, "bg_jobs": args.bg_jobs, "skills": skills}


def save_replays(project, spec_name, target, agent_runs):
    """The recorded server answers (and what was sent, "sent") of every agent run as JSONL, one file per run (runtime_data/devvm_replays/<spec>/<attempt>/<n>_<label>.jsonl)."""
    from guppi_runtime.coder_ext.replay_log import dumps
    folder = Path(project) / "runtime_data" / "devvm_replays" / spec_name / target.name
    for n, run in enumerate(agent_runs, 1):
        if not run.get("replay_records"): continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{n:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', run.get('label') or run.get('role') or 'agent').strip('_')}.jsonl").write_text(dumps(run["replay_records"]), encoding="utf-8")


def propose_lessons(project, spec_name, stamp, stage_rows, agent_runs, say):
    """E-11: known mistakes in the error texts of this attempt (failed stages, failed tool calls) become lesson card PROPOSALS in runtime_data/lesson_cards.json. Nothing is used before
    the Captain approves a card (`guppi lessons approve --id ...`). A problem here never ends a build."""
    try:
        from guppi_runtime.devenv.lesson_proposer import propose
        from guppi_runtime.devenv.lesson_store import default_path, load, manage
        failures = [{"stage": r.get("stage"), "text": r.get("error") or r.get("hidden_output") or ""} for r in stage_rows if not r.get("hidden_passed") and not r.get("skipped")]
        for run in agent_runs:
            for entry in run.get("journal") or []:
                if not entry.get("ok") and entry.get("error"): failures.append({"stage": run.get("label") or "agent", "text": entry["error"]})
        path = default_path(project)
        made = 0
        for item in propose(failures, f"{spec_name}-{stamp}", known=[c["text"] for c in load(path).cards.values()]):
            try: manage(path, "propose", text=item["text"], source=item["source"]); made += 1
            except ValueError: continue      # a duplicate of an open card, or a text the card store refuses
        if made: say(f"   lesson proposals: {made} new (guppi lessons list)")
    except Exception as exc:
        say(f"   lesson proposals skipped: {type(exc).__name__}: {str(exc)[:120]}")


def clean_old_work(work_root, max_age_s=24 * 3600):
    """Work folders of runs that were killed (crash, reboot) stay behind: remove the ones older than a day."""
    for folder in Path(work_root).glob("build_*"):
        try:
            if folder.is_dir() and time.time() - folder.stat().st_mtime > max_age_s: shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            continue


def host_node(ws, files):
    """Runs node scripts on the HOST against a copy of the workspace (for JS, which the python microVM cannot judge). Returns {"status", "output"} like vm_copy."""
    import shutil, subprocess
    tmp = Path(tempfile.mkdtemp(prefix="guppi_build_node_"))
    try:
        for path in ws.tree():
            (tmp / path).parent.mkdir(parents=True, exist_ok=True); (tmp / path).write_text(ws.read(path), encoding="utf-8")
        for name, text in files.items(): (tmp / name).write_text(text, encoding="utf-8")
        outputs = []
        for name in files:
            run = subprocess.run(["node", name], cwd=tmp, capture_output=True, text=True, timeout=60)
            outputs.append(run.stdout + run.stderr)
            if run.returncode != 0: return {"status": "failed", "output": NL.join(outputs)}
        return {"status": "completed", "output": NL.join(outputs)}
    except Exception as exc:
        return {"status": "failed", "output": f"{type(exc).__name__}: {exc}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def own_verdict(out):
    """The own check only counts when it really judged: a stage with an unjudged step (no usable check) reports None, never "accepted" (finding of docs/AM_BAU_FEHLERANALYSE_2026-10-07.md)."""
    return None if any(s.get("unjudged") for s in out["steps"]) else out["accepted"]


def own_text(verdict):
    return "UNJUDGED" if verdict is None else str(verdict)


def acceptance(vm_copy, ws, stage):
    results = []
    if stage.get("hidden"): results.append(vm_copy(ws, [["python3", name] for name in stage["hidden"]], stage["hidden"]))
    if stage.get("host_hidden"): results.append(host_node(ws, stage["host_hidden"]))
    bad = [r for r in results if r["status"] != "completed"]
    return {"status": "completed" if results and not bad else "failed", "output": NL.join(r["output"] for r in (bad or results))}


SOLO_REWORK = 3
TEST_DUTY = (re.compile(r"\s*Add (?:tests|a test) to `tests/[^`]+`\."), re.compile(r"\s*Add `tests/[^`]+` \(unittest\) with your own tests\."),
             re.compile(r"Run the whole test file `tests/[^`]+` and read"))
NO_TESTS = " Do not write tests: an independent acceptance test judges your work."


def without_test_duty(task):
    """The task without the duty to write its own tests (Captain 2026-10-09: the own tests were the time sink and did not find the defects; the hidden test judges). Unchanged when the task never asked for tests."""
    changed = TEST_DUTY[2].sub("Read", TEST_DUTY[1].sub("", TEST_DUTY[0].sub("", task)))
    return changed + NO_TESTS if changed != task else task


def own_tests(vm_copy, ws):
    """The model's OWN test files (tests/test_*.py) run in the microVM: not a gate, but a finding. In the am008 build 3 of 21 own tests contradicted the model's own code and nobody noticed (2026-10-09). {"present", "passed", "output"}."""
    if not any(path.startswith("tests/test_") and path.endswith(".py") for path in ws.tree()):
        return {"present": False, "passed": None, "output": ""}
    result = vm_copy(ws, [["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."]], {})
    return {"present": True, "passed": result["status"] == "completed", "output": result["output"][-400:]}


def hidden_report(vm_copy, ws, stage, limit=2):
    """A bug report of the first failing assertions of the first hidden script of a stage that fails (what the test expects, what the work gives); empty when the driver reports nothing."""
    for name, text in (stage.get("hidden") or {}).items():
        out = vm_copy(ws, [["python3", "acceptance_evidence.py", name]], {name: text, "acceptance_evidence.py": DRIVER})
        table = parse_evidence(out.get("output", ""))
        report = bug_report(table, limit) if table else ""
        if report:
            return report
    return ""


def export_snapshot(ws, project, spec_name, stamp, stage_name):
    """The state of the workspace after a PASSED stage, as a folder that can seed a later run of the next stage alone (--only <next stage> --seed <folder>)."""
    folder = Path(project) / "runtime_data" / "devvm_snapshots" / spec_name / stamp / f"after_{stage_name}"
    for path in ws.tree():
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ws.read(path), encoding="utf-8")
    return folder


def apply_mode_defaults(args):
    """The SOLO WORKFLOW is the standard (Captain 2026-10-10): ONE developer builds and checks in one conversation (tasks without the duty to write tests, comments and helper files tidied), the hidden acceptance test judges
    and a failed stage goes back to the SAME developer with a bug report, up to 3 times. The other modes keep their own settings (rework 0 unless asked)."""
    if args.mode == "solo":
        args.hidden_feedback = args.tidy = args.no_own_tests = True
        if args.rework is None: args.rework = SOLO_REWORK
    elif args.rework is None: args.rework = 0
    return args


def server_settings(items):
    """KEY=VALUE pairs of --server-set as a dict: on/off/auto stay strings (YAML would read off as False), numbers become int, true/false bool."""
    out = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise SystemExit(f"--server-set needs KEY=VALUE, got {item!r}")
        value = value.strip()
        out[key.strip()] = value if value.lower() in ("on", "off", "auto") else int(value) if re.fullmatch(r"-?\d+", value) else {"true": True, "false": False}.get(value.lower(), value)
    return out


def layer_runs(outs, stage_rows):
    """The agent runs of all stages for the layer summary: the last run of a stage carries its hidden result, an earlier hand-in of the same stage did not satisfy the test (like failure_layers)."""
    runs = []
    for out, row in zip(outs, stage_rows):
        stage_runs = out["agent_runs"]
        for i, run in enumerate(stage_runs):
            runs.append({**{k: run.get(k) for k in ("stopped_by", "error", "seconds", "completion_tokens")}, "stage_passed": row["hidden_passed"] if i == len(stage_runs) - 1 else False})
    return runs


def select_stages(stages, only=None, from_stage=None):
    """The stages to run: all, only one (--only) or one and every stage after it (--from-stage). An unknown name stops the build before a model is
    loaded (before 2026-10-12 a typo in --only ran no stage at all, every attempt, and reported FAILED); so does a stage without a hidden test."""
    names = [s["name"] for s in stages]
    for name in (only, from_stage):
        if name is not None and name not in names:
            raise SystemExit(f"unknown stage {name!r}; the spec has {', '.join(names)}")
    if only is not None and from_stage is not None:
        raise SystemExit("--only and --from-stage exclude each other")
    chosen = [s for s in stages if s["name"] == only] if only else stages[names.index(from_stage):] if from_stage else list(stages)
    blind = [s["name"] for s in chosen if not s.get("hidden") and not s.get("host_hidden")]
    if blind:
        raise SystemExit(f"stage without a hidden test (nothing could ever pass it): {', '.join(blind)}")
    return chosen


def seed_files(folder):
    """(relative path, text) of a seed folder. __pycache__ and files that are not UTF-8 text are left out (a .pyc stopped a seeded build with UnicodeDecodeError)."""
    out, skipped = [], []
    for f in sorted(Path(folder).rglob("*")):
        rel = f.relative_to(folder).as_posix()
        if not f.is_file() or rel == "NOTES.md": continue
        if "__pycache__" in f.parts:
            skipped.append(rel); continue
        try:
            out.append((rel, f.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            skipped.append(rel)
    return out, skipped


def skipped_row(stage):
    """A stage that did not run because an earlier one failed: it counts as not passed, so `passed/stages` stays comparable with older runs."""
    return {"stage": stage["name"], "hidden_passed": False, "skipped": True, "own_check_accepted": None, "unjudged": [], "escalations": 0, "reworks": 0,
            "seconds": 0, "hidden_output": "", "own_tests": {"present": False, "passed": None, "output": ""}}


def resume_hint(args, failed_stage, snapshot):
    """The command that continues a stopped build at the failed stage, from the snapshot of the last passed stage."""
    seed = f' --seed "{snapshot}"' if snapshot else ""
    return f"resume: benchmarks/devvm_build.py <project> --spec {args.spec} --from-stage {failed_stage}{seed} (plus the options of this run)"


def coder_window(loader, key, project, fallback):
    """The window the developer model really gets (recipe maximum with --context max, else min(--context, recipe maximum)). The orchestrator derives its
    compaction and read limits from it; before 2026-10-12 --context max told it 32768 while the server loaded up to 131072."""
    try:
        return int(loader.window(bench.hunt.model_spec(key, project)))
    except Exception:
        return fallback


def s0_report(project, keys, extras, engine_build):
    """The S0 state of every model of the run (process 'from the bottom up'): ok, missing, failed or settings_changed; jan and swe are no recipes."""
    out = []
    for key in sorted(set(keys.values())):
        if key in ("jan", "swe"):
            out.append({"recipe": key, "state": "not_a_recipe", "measured_at": None}); continue
        rid = "coder.llama_qwen3_coder" if key == "qwen3coder" else key
        out.append(s0_state(project, rid, {**bench.hunt.model_spec(key, project)["server"], **extras}, engine_build))
    return out

def spec_stamp_gate(project, spec_name, skip, bench=None, allow_host=False):
    """L2 (Captain 2026-10-20): no build without a green spec_check of exactly this spec and reference (benchmarks/spec_stamp.py, rule in spec_stamp.gate). Returns the lines
    for the log; a missing or stale stamp stops the build before a model is loaded, unless --skip-spec-stamp (then a warning in the log). A stamp of level host
    (spec_check --host-only) is accepted only with --allow-host-stamp (PIPE-07, Captain 2026-10-20); otherwise spec_stamp_host_only."""
    return spec_stamp.gate(project, spec_name, skip, bench, allow_host)


def count_lines(folder, only=lambda rel: True):
    """Lines of the text files below folder (a missing folder: 0); only(relative posix path) picks the files; __pycache__ is left out."""
    folder, total = Path(folder), 0
    if not folder.is_dir(): return 0
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        if not only(path.relative_to(folder).as_posix()): continue
        try: total += len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError): pass
    return total


def logbook_entry(spec_name, row, lease_seconds, bench_dir=None):
    """V1 (Captain 2026-10-20): the text of the BAU logbook row of one build, and its ref. SEDRA = lines of the exported candidate without tests and NOTES.md; Claude = lines of
    the spec file plus the reference folder (L4: the quota says how much Claude wrote for each line SEDRA wrote)."""
    bench_dir = Path(bench_dir or Path(__file__).resolve().parent)
    stages = row["stages"]
    passed = sum(1 for s in stages if s.get("hidden_passed"))
    sedra = count_lines(row["exported_to"], lambda rel: rel.endswith(".py") and not rel.startswith("tests/") and not Path(rel).name.startswith("test_"))
    claude = count_lines(bench_dir / "devvm_refs" / spec_name) + (len((bench_dir / "devvm_specs" / f"{spec_name}.py").read_text(encoding="utf-8").splitlines()) if (bench_dir / "devvm_specs" / f"{spec_name}.py").is_file() else 0)
    quota = f"{claude / sedra:.1f}" if sedra else "-"
    reworks = sum(s.get("reworks", 0) for s in stages)
    text = (f"Bau {spec_name}: {'bestanden' if row['hidden_passed'] else 'NICHT bestanden'}, Stufen {passed}/{len(stages)}, Dauer {row['seconds']:.0f} s, GPU-Lease {lease_seconds:.0f} s, "
            f"{row['calls']} Modellaufrufe in {row['agent_runs']} Agentenläufen, Nacharbeiten {reworks}, Eskalationen {row['escalations']}, "
            f"Zeilen SEDRA (Kandidat) {sedra}, Zeilen Claude (Spec + Referenz) {claude}, Quote Claude/SEDRA {quota}")
    return text, f"devvm_candidates/{spec_name}"


def write_logbook(spec_name, row, lease_seconds, file=None, bench_dir=None):
    """Appends the BAU row (benchmarks/logbook.py); returns the row text. A failure here must never fail a finished build, so the caller catches it."""
    text, ref = logbook_entry(spec_name, row, lease_seconds, bench_dir)
    line = logbook.make_row("BAU", text, ref)
    logbook.append(file or logbook.DEFAULT, line)
    return line


PROFILES = {      # Captain 2026-10-20, line L1: ONE way to build; the standard command of docs/ENTWICKLUNG.md as a profile (single flags given on the command line win)
    "standard": {"attempts": 1, "coder": "coder.local_primary", "all_models": "coder.local_primary", "context": "32768", "tidy": True, "reasoning": "off", "coder_ext": "all",
                 "server_set": ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"]},
}
EXPERIMENTAL = ("plan_steps", "fresh_rework", "step_syntax_check", "parallel_check", "checker", "arbiter")      # finished measurements: only with --experimental


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--spec", required=True); ap.add_argument("--attempts", type=int, default=2)
    ap.add_argument("--mode", default="solo", choices=["escalating", "pipeline", "delegating", "solo"], help="pipeline: the planner splits a larger task into steps, each with its own check and a reviewer")
    ap.add_argument("--rework", type=int, default=None, help="rounds in which the strong model gets the output of a failed acceptance test of a stage (not the test code), like the rework loop of the E1 golden path")
    ap.add_argument("--reasoning", choices=["auto", "on", "off"], help="thinking of the models for this run (the recipe's setting when left out): Qwen3.6 thinks until the token limit and the answer is cut (answer_cut), 2026-10-09")
    ap.add_argument("--reasoning-budget", type=int, help="most thinking tokens per answer (llama-server --reasoning-budget; -1 unlimited, 0 none)")
    ap.add_argument("--sampling", help="JSON of sampling settings for EVERY model of the run, e.g. '{\"temperature\": 0.7, \"top_p\": 0.8, \"top_k\": 20, \"presence_penalty\": 1.0}' (the recommended non-thinking values of Qwen3.x instead of the near-greedy 0.1)")
    ap.add_argument("--plan-steps", action="store_true", help="solo mode: the planner splits the task and the developer builds ONE step per fresh conversation (short history)")
    ap.add_argument("--step-syntax-check", action="store_true", help="with --plan-steps: a Python file that does not parse after a step goes back to the developer (at most twice)")
    ap.add_argument("--fresh-rework", action="store_true", help="solo mode: a rework starts a NEW conversation (complete task, map of the workspace, bug report) instead of continuing the old one")
    ap.add_argument("--self-check", choices=["full", "light", "none"], default="full", help="solo mode: how much the developer checks his own work (full: a check script and up to 8 VM runs; light: one small check, 2 runs; none: he cannot run code)")
    ap.add_argument("--no-own-tests", action="store_true", help="the tasks lose their duty to write own tests (the hidden test judges); on by default with --mode solo")
    ap.add_argument("--all-models", help="a model key or recipe id for EVERY role (coder, checker, strong coder, reviewer, arbiter): a pure comparison of one model against the reference build")
    ap.add_argument("--hidden-feedback", action="store_true", help="a rework round gets a bug report (what the hidden test expects and what the work gives, first 2 failing assertions) instead of the raw traceback")
    ap.add_argument("--seed", help="a candidate folder whose files are put in the workspace first (continue an earlier build)")
    ap.add_argument("--only", help="run only this stage")
    ap.add_argument("--from-stage", help="run this stage and every stage after it (continue a stopped build, usually with --seed <snapshot of the last passed stage>)")
    ap.add_argument("--keep-going", action="store_true", help="build the next stages even after a stage failed its hidden test (the old behaviour; night 2026-10-11 it cost about 80 GPU minutes on a broken base)")
    ap.add_argument("--review", help="a text file with the Captain's review of the seed; it is appended to the task as defects to fix")
    ap.add_argument("--context", default="32768", help="window of the models in tokens (a 450-line file overflowed 16k: stop reason error), or max for the maximum of each model's recipe (larger packages); always capped at the recipe maximum of the model (Jan and SWE: 16384, Qwen3-Coder: 49152)")
    ap.add_argument("--require-s0", action="store_true", help="refuse to start when a model of the run has no passing S0 connection check for exactly these settings (benchmarks/connection_check.py)")
    ap.add_argument("--server-set", action="append", default=[], metavar="KEY=VALUE", help="a server setting for EVERY model of this run on top of its recipe, e.g. flash_attn=on, kv_cache_type=q8_0, ubatch=512 (the recipe file is not changed)")
    ap.add_argument("--pidfile", help="write the PID of this run here, so that it can be stopped by PID and nothing else (other sessions run the same script)")
    ap.add_argument("--tidy", action="store_true", help="after every coder turn: strip comments and docstrings, delete new helper files (devvm_style); long functions and copied code are reported")
    ap.add_argument("--check-first", action="store_true", help="the acceptance check is written from the task alone, before the code exists (independent of the code)")
    ap.add_argument("--parallel-check", action="store_true", help="with --check-first and the same model for coder and checker: write code and check at the same time (needs --parallel 2)")
    ap.add_argument("--parallel", type=int, default=1, help="model server slots (each with the window of --context, capped at the recipe maximum)")
    ap.add_argument("--checker", help="model key of the model that writes the acceptance check (default: qwen3coder). Evidence 2026-10-07: with the coder's own model family only 1 of 6 own checks of AM-005 was right")
    ap.add_argument("--arbiter", help="model key of the arbiter that may overrule a failing check (default: the planner/checker model); another model family makes the judgement independent")
    ap.add_argument("--coder", default=DEFAULT_MODEL, help="model key of the first developer (default: the standard coder, Qwen3.6 = recipe coder.local_primary since 2026-10-09; jan = small; qwen3coder = Qwen3-Coder)")
    ap.add_argument("--coder-ext", help="coder extensions for every agent run (E-21): all, or a list such as e01,e08 (e01 read before change, e02 thinking budget, e03 answers without a tool call, e04 record, e05 prune, e07 tool cards, e08 tolerant edit, e09 syntax note, e12 churn guard); off by default")
    ap.add_argument("--bg-jobs", action="store_true", help="give the coder the background job tools shell_start, shell_log, shell_stop (E-06/E-10): each job is one VM run in a thread (vm_process); needs the VM, so it has no effect with --self-check none")
    ap.add_argument("--skills", nargs="?", const="core", metavar="NAME|DIR", help="skill library by name (config/skill_library.yaml: core, full; bare --skills = core) or folder: the coder gets the read-only tools skill_search and skill_read; off by default")
    ap.add_argument("--no-record", action="store_true", help="do NOT save the server answers and what was sent of every agent run (runtime_data/devvm_replays); recording is on by default since 2026-10-12")
    ap.add_argument("--skip-spec-stamp", action="store_true", help="build although spec_check has no valid stamp for this spec (L2 exception; a warning goes into the log)")
    ap.add_argument("--no-logbook", action="store_true", help="do NOT write the BAU row of this build into docs/LOGBUCH_AGENT_MANAGER.md at the end (V1; for tests)")
    ap.add_argument("--allow-host-stamp", action="store_true", help="accept a spec stamp of level host (spec_check --host-only, host python only) instead of stopping with spec_stamp_host_only (PIPE-07)")
    ap.add_argument("--profile", choices=sorted(PROFILES), help="standard = the standard command of docs/ENTWICKLUNG.md (--attempts 1, coder and all models coder.local_primary, --context 32768, --tidy, --reasoning off, --coder-ext all, flash_attn=on, kv_cache_type=q8_0, ubatch=512); a flag given here overrides its value")
    ap.add_argument("--experimental", action="store_true", help="allow the options of finished measurements (" + ", ".join("--" + k.replace("_", "-") for k in EXPERIMENTAL) + ")")
    return ap


def apply_profile(args, explicit):
    """The values of --profile for every option NOT given on the command line (explicit = the names given); --server-set pairs are merged by key, a given key wins."""
    profile = PROFILES.get(args.profile or "")
    if not profile: return args
    for key, value in profile.items():
        if key == "server_set":
            given = {item.partition("=")[0].strip() for item in args.server_set}
            args.server_set = [item for item in value if item.partition("=")[0] not in given] + list(args.server_set)
        elif key not in explicit:
            setattr(args, key, value)
    return args


def parse_args(argv=None):
    """Arguments with --profile applied and the experimental options checked (an experimental option without --experimental stops with a hint)."""
    ap = build_parser()
    args = ap.parse_args(argv)
    quiet = build_parser()
    for action in quiet._actions: action.default = argparse.SUPPRESS
    explicit = set(vars(quiet.parse_args(argv)))
    used = [k for k in EXPERIMENTAL if getattr(args, k)]
    if used and not args.experimental:
        ap.error(", ".join("--" + k.replace("_", "-") for k in used) + " is an experimental option (finished measurement): add --experimental, or use --profile standard")
    return apply_profile(args, explicit)


def main():
    args = parse_args()
    apply_mode_defaults(args)
    coder_ext = coder_ext_config(args)
    project = Path(args.project)
    stamp_lines = spec_stamp_gate(project, args.spec, args.skip_spec_stamp, allow_host=args.allow_host_stamp)
    if args.pidfile: Path(args.pidfile).write_text(str(os.getpid()), encoding="utf-8")
    spec = importlib.import_module(f"devvm_specs.{args.spec}")
    all_stages = getattr(spec, "STAGES", None) or [{"name": "all", "task": spec.TASK, "hidden": spec.HIDDEN}]
    run_stages = select_stages(all_stages, args.only, args.from_stage)
    log = RunLog(project / "runtime_data" / "measurements", f"devvm_build_{args.spec}", config={"spec": args.spec, "attempts": args.attempts, "profile": args.profile})
    log_stamp = time.strftime("%Y%m%d_%H%M%S")
    for line in stamp_lines: log.say(line)
    work_root = project / "runtime_data" / "devvm_work"      # not %TEMP%: a cleaner or another program there took away the git folder of a running build (2026-10-13, NotGitRepository)
    work_root.mkdir(parents=True, exist_ok=True)
    clean_old_work(work_root)
    tool_root = Path(tempfile.mkdtemp(prefix="build_", dir=work_root))
    broker, vm_copy = vm_env(project, tool_root, args.bg_jobs)      # the same VM environment spec_check --vm uses (devvm_vm.py)

    keys = {"planner": DEFAULT_MODEL, "coder": args.coder, "reviewer": "swe", "coder_strong": DEFAULT_MODEL}
    if args.checker: keys["planner"] = args.checker
    if args.all_models: keys = {role: args.all_models for role in keys}      # one model for every role (a model comparison: no swaps to Qwen3-Coder in between)
    if args.arbiter: keys["arbiter"] = args.arbiter
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    s0 = s0_report(project, keys, server_settings(args.server_set), config.engine_build)
    log.say("S0 connection check: " + ", ".join(f"{r['recipe']} {r['state']}" for r in s0))
    if args.require_s0 and any(r["state"] not in ("ok", "not_a_recipe") for r in s0):
        log.say("refused: --require-s0 and a model has no passing S0 check for these settings -> run benchmarks/connection_check.py first")
        raise SystemExit(4)
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_devvm_build_rt_")))
    kb = KnowledgeStore(project / "runtime_data" / "knowledge" / "records.jsonl")
    out_root = project / "runtime_data" / "devvm_candidates" / args.spec
    result = {"spec": args.spec, "attempts": []}
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "devvm_build"), f"devvm build {args.spec}", ttl_s=1800, wait_s=36000, preflight=clear_leftovers, priority=int(os.environ.get("TESTLAB_PRIORITY", "0"))):
        lease_t0 = time.monotonic()
        for attempt in range(1, args.attempts + 1):
            ws = DevWorkspace(tool_root, f"M-BUILD{attempt:03d}", policy=broker.policy()); ws.create()
            ws.write("NOTES.md", spec.NOTES)
            if args.seed:
                seeded, skipped = seed_files(args.seed)
                for rel, text in seeded: ws.write(rel, text)
                if skipped: log.say(f"   seed: left out {len(skipped)} file(s) that are not text: {', '.join(skipped[:5])}")
            loader = bench.BenchLoader(runtime, project, keys, log, context=args.context if args.context == "max" else int(args.context), parallel=args.parallel, server_extra={**server_settings(args.server_set), **{k: v for k, v in (("reasoning", args.reasoning), ("reasoning_budget", args.reasoning_budget)) if v is not None}}, sampling_extra=json.loads(args.sampling) if args.sampling else None)
            window = coder_window(loader, keys["coder"], project, 32768 if args.context == "max" else int(args.context))
            if coder_ext: coder_ext["window"] = window
            host = ModelHost(loader)
            t0 = time.monotonic()
            stages = list(run_stages)
            outs, stage_rows = [], []
            last_snapshot = Path(args.seed) if args.seed else None
            try:
                if args.review: stages = [{**s, "task": s["task"] + NL * 2 + "The existing code in the workspace was reviewed. These defects must be fixed (keep everything else):" + NL + Path(args.review).read_text(encoding="utf-8")} for s in stages]
                for index, stage in enumerate(stages):  # stages build on the same workspace; every stage has its own hidden test
                    if args.no_own_tests or args.mode == "solo": stage = {**stage, "task": without_test_duty(stage["task"])}
                    team = DevOrchestrator(ws, host, keys, vm_runner=(lambda commands, ws=ws: vm_copy(ws, commands, {})) if stage.get("hidden") and (not stage.get("no_own_check") or args.mode == "solo") else None, say=log.say,      # JS stages: no python check, the host test judges
                                           mode=args.mode, max_depth=2 if args.mode == "delegating" else 1, check_first=args.check_first, plan_steps=args.plan_steps, self_check=args.self_check, context=window, step_syntax_check=args.step_syntax_check, fresh_rework=args.fresh_rework, parallel_check=args.parallel_check, tidy=args.tidy,
                                           comment_log=Path(project) / "runtime_data" / "devvm_comments" / args.spec / f"{log_stamp}.jsonl", comment_meta={"spec": args.spec, "stage": stage["name"]}, coder_ext=coder_ext)
                    lessons = [r["content"]["summary"] for r in kb.lessons_for(stage["task"], limit=1, rank=True, min_specificity=8)]      # at most one, like the team test
                    if not lessons:      # E-11: an approved lesson card of the Captain, when the knowledge base has nothing for this task
                        card = lesson_for(lesson_cards_path(project), stage["task"])
                        lessons = [card] if card else []
                    if lessons: log.say(f"   lesson for stage {stage['name']}: {lessons[0][:70]}...")
                    stage_t0 = time.monotonic()
                    try:
                        out = team.run(stage["task"], lessons)
                        outs.append(out)
                        check = acceptance(vm_copy, ws, stage)
                        reworks = 0
                        while check["status"] != "completed" and reworks < args.rework:
                            reworks += 1
                            before = ws_snapshot(ws) if args.tidy else None
                            if args.mode == "solo":       # the SAME developer continues his conversation with the bug report (he remembers what he did)
                                team.continue_solo(hidden_report(vm_copy, ws, stage) or check["output"][-1500:], f"solo developer (rework {reworks})")
                            else:
                                team._agent("coder", REWORK_TASK.format(task=stage["task"], output=(hidden_report(vm_copy, ws, stage) if args.hidden_feedback else "") or check["output"][-1500:]), f"coder (rework {reworks})", model_role="coder_strong", exclude=("git_commit",))
                                team.tidy_files(before, stage["task"])
                            if any(ws.status().values()): ws.commit(f"rework {reworks}: {stage['name']}")
                            check = acceptance(vm_copy, ws, stage)
                    except Exception as exc:
                        # A stage that raised (model host gave up, VM broker error ...) used to end the whole build without a result row or an exported
                        # workspace. Now it is a failed stage with the error, and the attempt is saved like any other.
                        log.say(f"   stage {stage['name']}: ERROR {type(exc).__name__}: {str(exc)[:300]}")
                        stage_rows.append({**skipped_row(stage), "skipped": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}", "seconds": round(time.monotonic() - stage_t0, 1)})
                        stage_rows.extend(skipped_row(s) for s in stages[index + 1:])
                        break
                    mine = own_tests(vm_copy, ws)
                    if check["status"] == "completed":
                        try: last_snapshot = export_snapshot(ws, project, args.spec, log_stamp, stage["name"])
                        except Exception as exc: log.say(f"   snapshot of {stage['name']} failed: {type(exc).__name__}")
                    stage_rows.append({"stage": stage["name"], "hidden_passed": check["status"] == "completed", "own_check_accepted": own_verdict(out), "unjudged": [s.get("unjudged") for s in out["steps"]],
                                       "escalations": out["escalations"], "reworks": reworks, "seconds": out["seconds"], "hidden_output": check["output"][-600:], "own_tests": mine})
                    log.say(f"   stage {stage['name']}: hidden {'PASSED' if check['status'] == 'completed' else 'FAILED'} (own check accepted={own_text(own_verdict(out))}, own tests {'none' if not mine['present'] else 'ok' if mine['passed'] else 'FAILED'}, {out['seconds']} s)")
                    if check["status"] != "completed" and not args.keep_going and index + 1 < len(stages):
                        # Later stages build on this one; on a base that fails its test they only burn GPU time (night 2026-10-11: e06 ~50 min, e10 ~33 min).
                        stage_rows.extend(skipped_row(s) for s in stages[index + 1:])
                        log.say(f"   stopped after the failed stage {stage['name']}; skipped: {', '.join(s['name'] for s in stages[index + 1:])} (--keep-going builds them anyway)")
                        log.say("   " + resume_hint(args, stage["name"], last_snapshot))
                        break
            finally:
                host.close()
            seconds = round(time.monotonic() - t0, 1)
            ok = bool(stage_rows) and stage_rows[-1]["hidden_passed"] and all(r["hidden_passed"] for r in stage_rows)
            ran = [r for r in stage_rows if not r.get("skipped")]
            hidden = {"output": (ran[-1].get("error") or ran[-1]["hidden_output"]) if ran else ""}      # the stage that stopped the build, not a skipped one after it
            out = {"accepted": all(o["accepted"] for o in outs), "rejected_checks": [c for o in outs for c in o["rejected_checks"]], "steps": [s for o in outs for s in o["steps"]],
                   "escalations": sum(o["escalations"] for o in outs), "agent_runs": [r for o in outs for r in o["agent_runs"]], "model_swaps": host.swaps}
            crashes = list(host.crashes)                                       # server crashes the model host had to restart from (flash attention crash hunt, 2026-10-06)
            errors = [{"label": r["label"], "model": r["model"], "stopped_by": r["stopped_by"], "error": r.get("error")} for r in out["agent_runs"] if r["stopped_by"] == "error"]
            for e in errors: log.say(f"   agent error: {e['label']} ({e['model']}): {e['error']}")
            for c in crashes: log.say(f"   SERVER CRASH: {c}")
            files = {p: ws.read(p) for p in ws.tree()}
            target = out_root / f"attempt_{attempt:02d}_{time.strftime('%Y%m%d_%H%M%S')}"
            for path, text in files.items():
                (target / path).parent.mkdir(parents=True, exist_ok=True); (target / path).write_text(text, encoding="utf-8")
            if coder_ext and coder_ext["record"]: save_replays(project, args.spec, target, out["agent_runs"])
            row = {"attempt": attempt, "hidden_passed": ok, "stages": stage_rows, "hidden_output": hidden["output"][-1500:], "own_check_accepted": own_verdict(out), "rejected_checks": out["rejected_checks"], "unjudged": [s.get("unjudged") for s in out["steps"]], "coder": args.coder, "models": keys, "mode": args.mode, "plan_steps": bool(args.plan_steps), "fresh_rework": bool(args.fresh_rework), "self_check": args.self_check, "step_syntax_check": bool(args.step_syntax_check), "rescued": out.get("rescued"), "seconds": seconds, "escalations": out["escalations"],
                   "agent_runs": len(out["agent_runs"]), "agent_detail": [{k: r.get(k) for k in ("label", "stopped_by", "calls", "seconds", "completion_tokens", "prompt_tokens", "prompt_peak", "tool_counts", "nudges", "coder_ext")} for r in out["agent_runs"]], "calls": sum(r["calls"] for r in out["agent_runs"]), "swaps": out["model_swaps"], "s0": s0, "layers": layer_table(layer_runs(outs, stage_rows)), "layer_cell": layer_cell(layer_runs(outs, stage_rows)), "files": sorted(files), "exported_to": str(target),
                   "server_crashes": crashes, "agent_errors": errors, "context": args.context or "recipe", "coder_ext": coder_ext}
            result["attempts"].append(row); log.save(result)
            log.say(f"attempt {attempt}: hidden test {'PASSED' if ok else 'FAILED'} | own check accepted={own_text(own_verdict(out))} | {seconds} s, {row['agent_runs']} agent runs, {row['calls']} calls -> {target}")
            propose_lessons(project, args.spec, log_stamp, stage_rows, out["agent_runs"], log.say)
            if ok: break
    lease_seconds = time.monotonic() - lease_t0
    if not args.no_logbook and result["attempts"]:
        try: log.say("logbook: " + write_logbook(args.spec, result["attempts"][-1], lease_seconds))
        except Exception as exc: log.say(f"logbook row not written: {type(exc).__name__}: {str(exc)[:200]}")
    log.say(f"DONE -> {log.json_path.name}")
    shutil.rmtree(tool_root, ignore_errors=True)      # the candidates are exported already; the workspaces of this run are not needed any more
    if args.pidfile:      # only our own PID file: a later run may already have written its PID there
        try:
            if Path(args.pidfile).read_text(encoding="utf-8").strip() == str(os.getpid()): Path(args.pidfile).unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
