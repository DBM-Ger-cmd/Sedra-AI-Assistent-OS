r"""DevVM Phase 2: do the workspace tools work for the sub-models? (docs/DEVVM_AUFTRAG_2026-10-05.md, requirement B3: measure the tool format with every intended model)

    .venv\Scripts\python.exe benchmarks/devvm_tools_bench.py <project_dir> [--seeds 2] [--models jan,qwen3coder,swe]

Four small tasks in a fresh git workspace per run, run through model_tools.run_tool_loop with a DevToolBox (devvm_tools.py):
  create_package   (coder)    make folders and files, check syntax, commit                 success: the package works (VM) and the commit exists
  fix_and_commit   (coder)    fix a function, look at the diff, commit                      success: hidden checks pass (VM), commit exists
  move_and_update  (coder)    search usages, move a file to a new folder, fix the import   success: `python3 main.py` prints the expected line (VM), file moved, commit
  review_diff      (reviewer) read the uncommitted change, PASS or FAIL (good and bad variant)   success: verdict agrees with the hidden checks (VM)
Per run: tool calls, calls that came back as errors, unknown tool names, arguments that were not valid JSON, turns without any tool call, finish reasons, whether the model handed in
(terminal call), limit hit (40 calls / 10 minutes), seconds, success. Success is judged by running hidden checks on a COPY of the workspace in the VM through the broker's `_run`
(a benchmark path in a temporary tool root, like devvm_phase1_check.py; the agent itself never gets a VM tool here). Flash-Attention stays off. Holds the GPU lease.
Log and result: runtime_data/measurements/logs/devvm_tools_bench_*.{log,json}
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cuda_crash_hunt as hunt                                                      # noqa: E402
import small_team as st                                                              # noqa: E402
from guppi_runtime.devenv.devvm import DevWorkspace                                         # noqa: E402
from guppi_runtime.devenv.devvm_tools import DevToolBox                                     # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.devenv.model_tools import parse_calls, run_tool_loop                     # noqa: E402
from guppi_runtime.jobs.run_log import RunLog                                             # noqa: E402
from guppi_runtime.sandbox.broker import SandboxBroker                               # noqa: E402
from guppi_runtime.sandbox.provider import MicrosandboxProvider                      # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                              # noqa: E402

GREET = "def greet(name):\n    return 'hi ' + name\n"


def seed_committed(ws, files, message="start"):
    for path, text in files.items(): ws.write(path, text)
    ws.commit(message)


# ---- the tasks: setup(ws, variant) -> prompt; check(ws, vm) -> (ok, detail); vm(ws, commands, extra_files) -> bool (hidden checks in the VM)
def t_create_setup(ws, variant):
    return ("Create a small Python package in this empty workspace: a folder `calc` with an empty `__init__.py` and `ops.py` (functions add(a, b) and sub(a, b)), and a folder `tests` "
            "with `test_ops.py` (a unittest TestCase that tests both functions and imports them with `from calc.ops import add, sub`). Check the syntax of your Python files, then commit with the message 'add calc package'.")


def t_create_check(ws, vm):
    hidden = {"hidden_check.py": "from calc.ops import add, sub\nassert add(2, 3) == 5 and sub(5, 3) == 2 and add(-1, 1) == 0\nprint('ok')\n"}
    own = vm(ws, [["python3", "-m", "unittest", "discover", "-s", "tests"]], hidden)
    works = vm(ws, [["python3", "hidden_check.py"]], hidden)
    committed = any("calc package" in e["message"] for e in ws.log())
    return own and works and committed and not any(ws.status().values()), f"own tests {own}, hidden {works}, commit {committed}, status {ws.status()}"


def t_fix_setup(ws, variant):
    seed_committed(ws, {"textutil.py": "def slugify(text):\n    return text.lower().replace(' ', '_')\n"})
    return ("In `textutil.py`, `slugify` must return the words in lower case joined by a dash, without leading or trailing spaces: slugify('  Hello World ') == 'hello-world' and "
            "slugify('Many   spaces here') == 'many-spaces-here'. Fix it, look at the diff of your change, then commit with a message.")


def t_fix_check(ws, vm):
    hidden = {"hidden_check.py": "from textutil import slugify\nassert slugify('  Hello World ') == 'hello-world'\nassert slugify('Many   spaces here') == 'many-spaces-here'\nassert slugify('x') == 'x'\nprint('ok')\n"}
    works = vm(ws, [["python3", "hidden_check.py"]], hidden)
    commits = len(ws.log())
    return works and commits >= 2 and not any(ws.status().values()), f"hidden {works}, commits {commits}, status {ws.status()}"


def t_move_setup(ws, variant):
    seed_committed(ws, {"old/helpers.py": GREET, "main.py": "from old.helpers import greet\n\nprint(greet('x'))\n"})
    return ("Move `old/helpers.py` to `lib/helpers.py` and update every import of it so that `python3 main.py` still prints 'hi x'. Search for the usages first. Commit when done.")


def t_move_check(ws, vm):
    moved = "lib/helpers.py" in ws.tree() and "old/helpers.py" not in ws.tree()
    runs = vm(ws, [["python3", "main.py"]], {})
    return moved and runs and len(ws.log()) >= 2 and not any(ws.status().values()), f"moved {moved}, main.py runs {runs}, commits {len(ws.log())}, status {ws.status()}"


def t_review_setup(ws, variant):
    seed_committed(ws, {"util.py": "def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n"})
    body = "n % 2 == 0" if variant == "good" else "n % 2 == 1"
    ws.write("util.py", "def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n\n\ndef is_even(n):\n    return " + body + "\n")
    return "The uncommitted change is meant to add one function `is_even(n)` (True for even numbers, False for odd) and to change nothing else. Review it."


def t_review_check_factory(variant):
    def check(ws, vm, final=None):
        hidden = {"hidden_check.py": "from util import clamp, is_even\nassert clamp(5, 0, 3) == 3 and clamp(-1, 0, 3) == 0\nassert is_even(2) and not is_even(3) and is_even(0)\nprint('ok')\n"}
        truth = vm(ws, [["python3", "hidden_check.py"]], hidden)
        verdict = (final or {}).get("verdict")
        return verdict == ("PASS" if truth else "FAIL"), f"change is {'correct' if truth else 'wrong'} (VM), verdict {verdict}"
    return check


TASKS = [
    {"id": "create_package", "role": "coder", "setup": t_create_setup, "check": t_create_check, "variants": [None]},
    {"id": "fix_and_commit", "role": "coder", "setup": t_fix_setup, "check": t_fix_check, "variants": [None]},
    {"id": "move_and_update", "role": "coder", "setup": t_move_setup, "check": t_move_check, "variants": [None]},
    {"id": "review_diff", "role": "reviewer", "setup": t_review_setup, "check": None, "variants": ["good", "bad"]},
]
MODELS = {"jan": ("coder", "jan"), "qwen3coder": ("coder", "qwen3coder"), "swe": ("reviewer", "swe")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--seeds", type=int, default=2); ap.add_argument("--models", default="jan,qwen3coder,swe")
    args = ap.parse_args()
    project = Path(args.project)
    names = [m for m in args.models.split(",") if m in MODELS]
    log = RunLog(project / "runtime_data" / "measurements", "devvm_tools_bench", config={"seeds": args.seeds, "models": names})
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_devvm_bench_"))
    cfg_path = tool_root / "sandbox-bench.yaml"
    cfg_path.write_text((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    provider = MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME)
    broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg_path, provider, None)
    counter = {"n": 0}

    def vm(ws, commands, extra):
        """Hidden checks on a COPY of the workspace in the VM (benchmark path through the broker's _run; the agent has no VM tool in this bench)."""
        counter["n"] += 1
        copy = DevWorkspace(tool_root, f"M-CHK{counter['n']:05d}", policy=broker.policy()); copy.create()
        for path in ws.tree(): copy.write(path, ws.read(path))
        for path, text in extra.items(): copy.write(path, text)
        try:
            return broker._run("M-BENCH", copy.vm_preview(broker, commands))["status"] == "completed"
        except Exception:
            return False

    result = {"models": {}}
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_devbench_")))
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "devvm_tools_bench"), "devvm tools bench", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        for mname in names:
            role, key = MODELS[mname]
            model = hunt.model_spec(key, project)
            sampling = {"temperature": st.REVIEWER["temperature"] if role == "reviewer" else 0.1}
            server = {**model["server"], "flash_attn": "off"}
            log.say(f"== {mname} ({model['alias']}, role {role})")
            runtime.load_model(model["alias"], context_length=model["context"], gpu="max", identifier=model["alias"], parallel=1, server=server)
            rows = []
            try:
                plain = st.post_factory(runtime.endpoint)
                for task in [t for t in TASKS if t["role"] == role]:
                    for variant in task["variants"]:
                        for seed in range(args.seeds):
                            counter["n"] += 1
                            ws = DevWorkspace(tool_root, f"M-{mname[:4].upper()}{counter['n']:05d}", policy=broker.policy()); ws.create()
                            prompt = task["setup"](ws, variant)
                            box = DevToolBox(ws, role)
                            stats = {"bad_json_args": 0, "text_only_turns": 0, "length_finishes": 0}

                            def post(body, stats=stats):
                                data = plain(body)
                                choice = data["choices"][0]
                                calls = parse_calls(choice.get("message") or {})
                                stats["bad_json_args"] += sum(1 for c in calls if c[2] is None)
                                stats["text_only_turns"] += 0 if calls else 1
                                stats["length_finishes"] += choice.get("finish_reason") == "length"
                                return data
                            out = run_tool_loop(post, model["alias"], [{"role": "system", "content": box.system}, {"role": "user", "content": prompt}], box, sampling, max_turns=30, max_tokens=4000)
                            check = task["check"] if task["check"] else t_review_check_factory(variant)
                            ok, detail = check(ws, vm, box.final) if task["id"] == "review_diff" else check(ws, vm)
                            errors = [j for j in box.journal if not j["ok"]]
                            row = {"task": task["id"], "variant": variant, "seed": seed, "success": bool(ok), "detail": detail, "calls": len(box.calls), "error_calls": len(errors),
                                   "unknown_tool": sum("unknown tool" in str(j) for j in errors), "terminal": box.final is not None, "limit_hit": box.limit_hit, "turns": out["turns"],
                                   "finish": out["finish"], "seconds": out["seconds"], **stats, "journal": box.journal,
                                   "files": {p: ws.read(p)[:1500] for p in ws.tree()}, "final": box.final}
                            rows.append(row)
                            log.say(f"   {task['id']:16s} {variant or '':5s} #{seed}: {'OK  ' if ok else 'FAIL'} {len(box.calls):2d} calls, {len(errors)} errors, terminal {box.final is not None}, "
                                    f"{out['seconds']} s, bad json {stats['bad_json_args']}, text-only turns {stats['text_only_turns']} | {detail[:110]}")
                            result["models"][mname] = {"model": model["alias"], "role": role, "rows": rows}
                            log.save(result)
            finally:
                try: runtime.unload_model(all_models=True)
                except Exception: pass
            n = len(rows)
            summary = {"runs": n, "success": f"{sum(r['success'] for r in rows)}/{n}", "handed_in": f"{sum(r['terminal'] for r in rows)}/{n}",
                       "median_calls": statistics.median(r["calls"] for r in rows), "error_call_share": round(sum(r["error_calls"] for r in rows) / max(1, sum(r["calls"] for r in rows)), 2),
                       "bad_json_args": sum(r["bad_json_args"] for r in rows), "unknown_tool_calls": sum(r["unknown_tool"] for r in rows), "limit_hits": sum(bool(r["limit_hit"]) for r in rows),
                       "median_seconds": statistics.median(r["seconds"] for r in rows)}
            result["models"][mname]["summary"] = summary
            log.save(result)
            log.say(f"  -> {mname}: {summary}")
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
