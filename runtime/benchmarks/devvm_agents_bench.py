r"""DevVM Phase 3 acceptance: does the team beat Jan alone? (docs/DEVVM_AUFTRAG_2026-10-05.md, requirement C and phase table)

    .venv\Scripts\python.exe benchmarks/devvm_agents_bench.py <project_dir> [--seeds 3] [--modes solo,team]

The same three coding tasks as devvm_tools_bench.py (create_package, fix_and_commit, move_and_update), worded without the commit sentence (the team commits, not the developer):
  solo   Jan-code-4b alone (one coder agent, same tools, same budget); the harness commits afterwards
  team   planner Qwen3-Coder -> per step: developer Jan-code-4b -> (executed test, when the workspace has tests) -> reviewer SWE-Review-8B -> retry on FAIL (2 rounds) -> commit
  escalating   (Captain 2026-10-06, "erst allein, dann eskalieren") Jan-code-4b works ALONE first; then Qwen3-Coder writes the acceptance check (loaded anyway), the check runs
         in the VM, and only a FAILING check brings Qwen3-Coder in as developer (no model swap). No planner steps, no reviewer, no helpers.
  delegating   (Captain 2026-10-06) only the two main actors, planner and developer; THEY start helpers themselves with the `delegate` tool and are told to: the developer asks a reviewer
         (SWE-Review) to check its work and, if it cannot fix a defect, a strong coder (Qwen3-Coder); the planner may hand reading a larger workspace to an explorer. No fixed reviewer step
         and no automatic escalation: the planner's executed check judges, a failing check gives the developer another round. Helpers are leaves (depth 2), at most 4 per run.
Success = hidden checks in the VM on a copy of the workspace (the agents never see them); commits are not part of the success here. The team's `vm_runner` is a benchmark runner
(the broker's `_run` in a temporary tool root, standing in for an approved gate); production goes through broker.execute and the Captain's gate.
Per run: success, plan steps, rounds, accepted steps, agent runs by stop reason, tool calls, model swaps and load seconds, crashes, seconds. Flash-Attention off. Holds the GPU lease.
Log and result: runtime_data/measurements/logs/devvm_agents_bench_*.{log,json}
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cuda_crash_hunt as hunt                                                      # noqa: E402
import devvm_tools_bench as tb                                                      # noqa: E402
import judge as judge_mod                                                            # noqa: E402
from team_tasks import SETS                                                          # noqa: E402
from guppi_runtime.knowledge import KnowledgeStore                                   # noqa: E402
import small_team as st                                                              # noqa: E402
from guppi_runtime.devvm import DevWorkspace                                         # noqa: E402
from guppi_runtime.devvm_agents import AgentBudget, DevOrchestrator, ModelHost, run_agent  # noqa: E402
from guppi_runtime.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.run_log import RunLog                                             # noqa: E402
from guppi_runtime.sandbox.broker import SandboxBroker                               # noqa: E402
from guppi_runtime.sandbox.provider import MicrosandboxProvider                      # noqa: E402
from guppi_runtime.testlab import TestLab, default_path                              # noqa: E402

PROMPTS = {
    "create_package": ("Create a small Python package in this empty workspace: a folder `calc` with an empty `__init__.py` and `ops.py` (functions add(a, b) and sub(a, b)), and a folder `tests` "
                       "with `test_ops.py` (a unittest TestCase that tests both functions and imports them with `from calc.ops import add, sub`). Check the syntax of your Python files."),
    "fix_and_commit": ("In `textutil.py`, `slugify` must return the words in lower case joined by a dash, without leading or trailing spaces: slugify('  Hello World ') == 'hello-world' and "
                       "slugify('Many   spaces here') == 'many-spaces-here'. Fix it and look at the diff of your change."),
    "move_and_update": "Move `old/helpers.py` to `lib/helpers.py` and update every import of it so that `python3 main.py` still prints 'hi x'. Search for the usages first.",
}
SETUP = {"create_package": lambda ws: None, "fix_and_commit": lambda ws: tb.t_fix_setup(ws, None), "move_and_update": lambda ws: tb.t_move_setup(ws, None)}


BIG_WINDOW_UBATCH = 512        # default for a window above the recipe's recommended one: flash attention stays off (CUDA crashes), so the compute buffer grows with the window: 8.6 GiB at 32k with ubatch 2048 did not fit (2026-10-07). A recipe can say better in profile.big_window_server (measured with moe_sweep.py, 2026-10-09: Qwen3-Coder ubatch 1024 + n_cpu_moe 46 = 10.6 GiB, prompts 1.7x faster)


def recipe_context_maximum(project, alias, recipe_id=None):
    """The window a model's recipe in role_routing.yaml allows (profile.context.maximum), or None when no recipe names the model.
    With `recipe_id` exactly that recipe counts. Without it (jan, swe) the largest maximum of the recipes naming the model: before 2026-10-12 that was
    also used for recipes, and coder.llama_qwen35 (capped at 16k after CUDA crashes) got 65k from the switched-off LM Studio recipe of the same model."""
    import yaml
    recipes = yaml.safe_load((Path(project) / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]
    def maximum(r):
        return (r.get("profile") or {}).get("context", {}).get("maximum")
    if recipe_id is not None:
        own = [int(maximum(r)) for r in recipes if r.get("id") == recipe_id and maximum(r)]
        if own: return own[0]
    found = [int(maximum(r)) for r in recipes if r.get("model") == alias and maximum(r)]
    return max(found) if found else None


def big_window_server(spec):
    """Server settings for a window above the recipe's recommended one: the recipe's profile.big_window_server, else only a smaller ubatch."""
    return dict(spec.get("big_window") or {"ubatch": BIG_WINDOW_UBATCH})


class BenchLoader:
    """ModelHost's loader: starts one llama-server model at a time through GUPPI's own runtime (server settings from the recipe, plus server_extra)."""

    def __init__(self, runtime, project, keys, log, context=None, parallel=1, server_extra=None, sampling_extra=None):
        self.runtime, self.project, self.log = runtime, project, log
        self.server_extra = dict(server_extra or {})      # settings for EVERY model of the run on top of its recipe (a comparison, e.g. reasoning off)
        self.parallel = int(parallel)      # server slots: the window is the size of ONE slot, the server gets slots x window (capped at the recipe maximum, then each slot gets its share)
        self.context = context        # None: the recipe's window; an int: that window; "max": the maximum of each model's recipe. Always capped at the model's recipe maximum (Captain 2026-10-07: 32k for coding if possible, the maximum for larger packages)
        self.specs = {key: hunt.model_spec(key, project) for key in set(keys.values())}
        self.sampling = {key: {"temperature": st.REVIEWER["temperature"] if key == "swe" else 0.1, **dict(sampling_extra or {})} for key in self.specs}      # sampling_extra: e.g. temperature 0.7, top_p 0.8, top_k 20 for every model of the run

    def window(self, spec):
        cap = recipe_context_maximum(self.project, spec["alias"], spec.get("recipe_id")) or spec["context"]
        if self.context is None: return spec["context"]
        return cap if self.context == "max" else min(int(self.context), cap)

    def load(self, role):                 # `role` here is the model key the orchestrator passes (qwen3coder, jan, swe)
        spec = self.specs[role]
        context = self.window(spec)
        total = min(context * self.parallel, recipe_context_maximum(self.project, spec['alias'], spec.get('recipe_id')) or context * self.parallel)
        self.log.say(f"   load {spec['alias']} with a window of {total // self.parallel} tokens in each of {self.parallel} slot(s)")
        self.runtime.load_model(spec["alias"], context_length=total, gpu="max", identifier=spec["alias"], parallel=self.parallel, server={**spec["server"], **(big_window_server(spec) if context > spec["context"] and "ubatch" in spec["server"] else {}), **self.server_extra})      # 2026-10-12: the recipe decides flash attention (forced off before: with KV q8_0 recipes the server would not start); server_extra last
        return spec["alias"], st.post_factory(self.runtime.endpoint), self.sampling[role]

    def unload(self):
        self.runtime.unload_model(all_models=True); time.sleep(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--seeds", type=int, default=3); ap.add_argument("--modes", default="solo,team")
    ap.add_argument("--same-model", action="store_true", help="reviewers and explorers use the model that is loaded (team, delegating)")
    ap.add_argument("--taskset", default="three", choices=["three", "rework8"], help="three: the Phase 2/3 tasks; rework8: the eight small_team tasks through the whole pipeline (judged by judge.py in the VM)")
    args = ap.parse_args()
    project = Path(args.project)
    modes = [m for m in args.modes.split(",") if m in ("solo", "team", "delegating", "escalating")]
    log = RunLog(project / "runtime_data" / "measurements", "devvm_agents_bench", config={"seeds": args.seeds, "modes": modes, "same_model": args.same_model})
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_devvm_agents_"))
    cfg_path = tool_root / "sandbox-bench.yaml"; cfg_path.write_text((RUNTIME / "config" / "sandbox.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    broker = SandboxBroker(tool_root, tool_root / "sandbox-data", cfg_path, MicrosandboxProvider(project / "runtime_data" / "sandboxes" / "backend_home", RUNTIME), None, None)
    counter = {"n": 0}

    def vm_copy(ws, commands, extra):
        counter["n"] += 1
        copy = DevWorkspace(tool_root, f"M-CHK{counter['n']:05d}", policy=broker.policy()); copy.create()
        for path in ws.tree(): copy.write(path, ws.read(path))
        for path, text in extra.items(): copy.write(path, text)
        try:
            out = broker._run("M-BENCH", copy.vm_preview(broker, commands))
        except Exception as exc:
            return {"status": "failed", "output": f"{type(exc).__name__}: {exc}"}
        rec = out.get("sandbox") or {}
        return {"status": out["status"], "output": "\n".join(c.get("output", "") for c in rec.get("commands", []))}

    def check(task, ws):
        hidden = {"create_package": {"hidden_check.py": "from calc.ops import add, sub\nassert add(2, 3) == 5 and sub(5, 3) == 2 and add(-1, 1) == 0\nprint('ok')\n"},
                  "fix_and_commit": {"hidden_check.py": "from textutil import slugify\nassert slugify('  Hello World ') == 'hello-world'\nassert slugify('Many   spaces here') == 'many-spaces-here'\nassert slugify('x') == 'x'\nprint('ok')\n"},
                  "move_and_update": {}}[task]
        if task == "create_package":
            own = vm_copy(ws, [["python3", "-m", "unittest", "discover", "-s", "tests"]], hidden)["status"] == "completed"
            return own and vm_copy(ws, [["python3", "hidden_check.py"]], hidden)["status"] == "completed"
        if task == "fix_and_commit": return vm_copy(ws, [["python3", "hidden_check.py"]], hidden)["status"] == "completed"
        return "lib/helpers.py" in ws.tree() and "old/helpers.py" not in ws.tree() and vm_copy(ws, [["python3", "main.py"]], {})["status"] == "completed"

    prompts, setup, lessons_of = PROMPTS, SETUP, (lambda task: [])
    if args.taskset == "rework8":
        kb = KnowledgeStore(project / "runtime_data" / "knowledge" / "records.jsonl")
        by_id = {t["id"]: t for t in SETS["all"]}
        prompts = {tid: (f"The module `mod.py` in the workspace has a defect. Its contract (the docstring) is correct and the tests are correct.\n\nThe tests fail:\n{t['failure']}\n\n"
                         f"GUPPI reproduced the failure in its VM:\n{t['repro']}\n\nFix the defect in mod.py: keep the function name and the contract.") for tid, t in by_id.items()}
        setup = {tid: (lambda ws, t=t: ws.write("mod.py", t["code"])) for tid, t in by_id.items()}
        lessons_of = lambda task: [r["content"]["summary"] for r in kb.lessons_for(by_id[task]["code"] + by_id[task]["repro"], limit=1, rank=True, min_specificity=8)]

        def check(task, ws):
            try: return judge_mod.all_passed(judge_mod.judge(project, {"k": (task, ws.read("mod.py"))})["k"])
            except Exception: return False
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_agentsbench_")))
    result = {"modes": {}}
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "devvm_agents_bench"), "devvm agents bench", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        for mode in modes:
            rows = []
            keys = {"planner": "qwen3coder", "coder": "jan", "reviewer": "swe", "coder_strong": "qwen3coder"} if mode in ("team", "delegating", "escalating") else {"coder": "jan"}
            log.say(f"== {mode}: {keys}")
            for task in prompts:
                for seed in range(args.seeds):
                    counter["n"] += 1
                    ws = DevWorkspace(tool_root, f"M-{mode[:4].upper()}{counter['n']:05d}", policy=broker.policy()); ws.create()
                    setup[task](ws)
                    lessons = lessons_of(task)
                    loader = BenchLoader(runtime, project, keys, log); host = ModelHost(loader)
                    t0 = time.monotonic()
                    try:
                        if mode == "solo":
                            alias, post, sampling = host.use("jan")
                            run = run_agent("coder", prompts[task] + "".join(f"\n\nA lesson from the knowledge base that matches this code:\n- {l}" for l in lessons), ws, post, alias, sampling=sampling, exclude=("git_commit",), label="solo coder")
                            runs, extra = [run], {"stopped_by": [run["stopped_by"]]}
                            if any(ws.status().values()): ws.commit("solo: " + task)
                        else:
                            team = DevOrchestrator(ws, host, keys, vm_runner=lambda commands, ws=ws: vm_copy(ws, commands, {}), say=log.say,
                                                   mode={"delegating": "delegating", "escalating": "escalating"}.get(mode, "pipeline"), max_depth=2 if mode == "delegating" else 1,
                                                   same_model=args.same_model)
                            out = team.run(prompts[task], lessons); runs = out["agent_runs"]
                            extra = {"plan_steps": len(out["plan"]), "plan_fallback": out["plan_fallback"], "accepted": out["accepted"], "rounds": [len(s["rounds"]) for s in out["steps"]],
                                     "verdicts": [[r.get("verdict") for r in s["rounds"]] for s in out["steps"]], "swaps": out["model_swaps"], "escalations": out["escalations"], "broken_checks": out["broken_checks"], "dropped_checks": out["dropped_checks"], "replans": out["replans"], "delegations": out["delegations"], "subagents": out["subagents"], "unjudged": [s.get("unjudged") for s in out["steps"]],
                                     "overruled": [[bool(r.get("overruled_check")) for r in s["rounds"]] for s in out["steps"]], "load_seconds": out["model_load_seconds"], "crashes": out["server_crashes"],
                                     "stopped_by": dict(Counter(r["stopped_by"] for r in runs))}
                    finally:
                        host.close()
                    seconds = round(time.monotonic() - t0, 1)
                    ok = check(task, ws)
                    row = {"task": task, "seed": seed, "success": bool(ok), "seconds": seconds, "agent_runs": len(runs), "calls": sum(r["calls"] for r in runs), "completion_tokens": sum(r["completion_tokens"] for r in runs),
                           **extra, "files": {p: ws.read(p)[:1200] for p in ws.tree()}, "runs": [{**{k: r[k] for k in ("role", "model", "label", "stopped_by", "calls", "seconds", "completion_tokens", "final", "error")}, **({"journal": [(j["tool"], j["detail"][:70], j["ok"]) for j in r["journal"]]} if r["stopped_by"] != "hand_in" else {})} for r in runs]}
                    rows.append(row); result["modes"][mode] = {"keys": keys, "rows": rows}; log.save(result)
                    log.say(f"{mode:4s} {task:16s} #{seed}: {'OK  ' if ok else 'FAIL'} {seconds:6.1f} s, {len(runs)} agent runs, {row['calls']} calls | " + str({k: v for k, v in extra.items() if k in ('plan_steps', 'accepted', 'verdicts', 'stopped_by', 'swaps', 'delegations')}))
            n = len(rows)
            result["modes"][mode]["summary"] = {"runs": n, "success": f"{sum(r['success'] for r in rows)}/{n}", "median_seconds": statistics.median(r["seconds"] for r in rows),
                                                "median_calls": statistics.median(r["calls"] for r in rows), "per_task": {t: f"{sum(r['success'] for r in rows if r['task'] == t)}/{sum(1 for r in rows if r['task'] == t)}" for t in prompts}}
            log.save(result); log.say(f"  -> {mode}: {result['modes'][mode]['summary']}")
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
