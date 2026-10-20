"""What does the working set save in a real session, and does the model still answer correctly? (a measurement, not a test)

A synthetic coding session on a real model through GUPPI's own path (loader -> model_call -> router -> llama-server): N modules, one step
per module. At each step the tool output (the module's source, ~2k tokens) enters the history and the model is asked for one fact from
that module. The last steps ask for facts from the EARLIEST modules, which in the working-set run live only in the archive.

    naive         every step sends the whole history from the first message (what handlers did before Phase 9)
    working_set   every step sends head + archive index + the recent turns + excerpts recalled for that step (window = --window)

Per step it records the prompt tokens the server counted, seconds, and whether the answer holds the expected value (deterministic grader).
It also records the working set's own numbers (reuse of the previous prompt, archived blocks, recalled excerpts). It takes the shared GPU
lease and writes its calls to the test lab database.

    python benchmarks/workingset_real_run.py <project_dir_with_local_config> [--model google/gemma-4-12b-qat] [--modules 24] [--window 16384]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

PROVIDER = "llama-cpp-server"
SYSTEM = "You are a coding assistant. Answer with the requested value only, no explanation."
NAMES = ["ledger", "router", "cache", "parser", "scheduler", "auditor", "encoder", "planner", "monitor", "indexer", "sampler", "mapper",
         "loader", "tracker", "filter", "buffer", "resolver", "builder", "walker", "mixer", "gateway", "packer", "reader", "writer"]


def module_source(index, name):
    """Deterministic ~2k-token Python-like module with one unique constant the question asks for."""
    value = 1000 + (index * 7919) % 8999
    second = 100 + (index * 313) % 8801                     # asked only in the recall steps at the end, never in the module's own step
    lines = [f'"""Module {name}: part {index} of the synthetic project."""', f"MAX_{name.upper()}_ENTRIES = {value}", f"{name.upper()}_TIMEOUT_MS = {second}", ""]
    for i in range(48):
        lines += [f"def {name}_step_{i}(value, offset={i}):", f'    """{name} step {i}: adds offset {i} and checks against the unit table."""',
                  f"    result = value + offset * {index + 2} - {i}", f"    if result > {500 + i * 13}:", f"        return result % {97 + i}", "    return result", ""]
    return chr(10).join(lines), value, second


def session(modules):
    """[(tool_output_or_None, question, expected)]: one step per module, then recall questions about the earliest modules."""
    steps, values = [], {}
    for i in range(modules):
        name = NAMES[i % len(NAMES)]
        text, value, second = module_source(i, name)
        values[name] = second
        steps.append((f"FILE {name}.py\n{text}", f"What is the value of MAX_{name.upper()}_ENTRIES in {name}.py? Reply with the number only.", str(value)))
    for i in (1, 3, 5, 0):
        name = NAMES[i]
        steps.append((None, f"Earlier in this session you saw {name}.py. What is the value of {name.upper()}_TIMEOUT_MS there? Reply with the number only.", str(values[name])))
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--model", default="google/gemma-4-12b-qat")
    ap.add_argument("--modules", type=int, default=24)
    ap.add_argument("--window", type=int, default=16384, help="window the working set compacts against")
    ap.add_argument("--modes", default="naive,working_set")
    ap.add_argument("--effort", default="none", help="reasoning_effort of every call: none | low | medium | high (gpt-oss knows no 'none')")
    ap.add_argument("--max-tokens", type=int, default=60, help="answer budget; a model that thinks needs room for it")
    ap.add_argument("--context", type=int, default=102400, help="context the server is started with")
    args = ap.parse_args()

    from guppi_runtime.selfdev.development_contracts import development_contract
    from guppi_runtime.runtime import GuppiRuntime
    from guppi_runtime.jobs.testlab import TestLab, default_path
    from guppi_runtime.models.gpu_preflight import clear_leftovers

    lab = TestLab(default_path(args.project))
    owner = os.environ.get("TESTLAB_OWNER", "workingset_real_run")
    with lab.lease(owner, f"workingset real run {args.model}", ttl_s=600, wait_s=1800, preflight=clear_leftovers):
        run_id = lab.start_run(owner, "workingset", f"{args.model} {args.modules} modules", vars(args))
        try:
            tmp = Path(tempfile.mkdtemp())
            project = tmp / "GUPPI_OS"
            shutil.copytree(Path(args.project) / "local_config", project / "local_config")
            arch = sorted((RUNTIME.parent / "architecture").glob("GUPPI_Architecture_v*"))[-1]
            rt = GuppiRuntime(project, architecture_root=arch)
            if not (rt.model_loader and rt.model_loader.enabled and rt.context_manager and rt.context_manager.enabled):
                sys.exit("model_loader and context_manager must be enabled by the local switches")
            rt.model_router.adapters[PROVIDER].timeout = 900
            recipe = next(r for r in rt.role_router.config.recipes if r["model"] == args.model and r["provider"] == PROVIDER)
            resolution = {"model": args.model, "provider_ref": PROVIDER, "context_window": args.context, "estimated_resources": {},
                          "load_profile": {"gpu_layers": recipe["profile"].get("gpu_layers"), "server": recipe["profile"].get("server")}}
            rt.model_loader.evict_idle(set())
            print("loading", args.model, "context", args.context, rt.model_loader.ensure(resolution), flush=True)
            steps = session(args.modules)
            contract = development_contract(objective="synthetic coding session for a measurement", classification="E1",
                                            acceptance_criteria=[{"type": "x", "id": "a"}], verification_plan=[{"type": "deterministic_tests"}])
            for mode in args.modes.split(","):
                job = {"job_id": "SDJ-0123456789AB", "parent_job_id": None, "permission_level": 2, "state": "BUILDING", "attempt_log": [], "contract": contract}
                ws = rt.working_set(job, task="answer questions about the modules", window=args.window) if mode == "working_set" else None
                history, totals = [], {"tokens": 0, "seconds": 0.0, "correct": 0}
                for n, (tool_output, question, expected) in enumerate(steps):
                    if mode == "naive":
                        if tool_output:
                            history.append({"role": "user", "content": f"[tool result] {tool_output}"})
                        messages = [{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": question}]
                        info = {}
                    else:
                        # The file the step is about belongs to the CURRENT step. Only afterwards it goes into the history, where a large
                        # tool result is offloaded and a later question can recall the part it needs.
                        composed = ws.compose(tool_output + chr(10) * 2 + question if tool_output else question)
                        messages, info = composed["messages"], {"reuse": composed["reuse_of_previous"], "blocks": composed["archived_blocks"], "recalled": len(composed["recalled"])}
                    request = {"provider": PROVIDER, "model": args.model, "messages": messages, "max_tokens": args.max_tokens, "temperature": 0,
                               "job_id": f"WS-{mode}", "attempt_id": f"S{n:02d}", "role": "bench", "reasoning_effort": args.effort}
                    started = time.time()
                    reply = rt.control.model_call(f"WS-{mode}", request)
                    seconds = time.time() - started
                    result = reply.get("model_result") or {}
                    answer = (result.get("content") or "").strip()
                    tokens = (result.get("usage") or {}).get("input_tokens") or 0
                    correct = reply.get("status") == "completed" and expected in answer.replace(",", "")
                    totals["tokens"] += tokens; totals["seconds"] += seconds; totals["correct"] += bool(correct)
                    lab.record(run_id, args.model, variant=mode, task=f"S{n:02d}", ok=correct, tokens_in=tokens, tokens_out=(result.get("usage") or {}).get("output_tokens"),
                               seconds=round(seconds, 2), recall_step=tool_output is None, answer_tail=answer[-120:], finish=result.get("finish_reason"), **info)
                    if mode == "naive":
                        history.append({"role": "user", "content": question}); history.append({"role": "assistant", "content": answer or "(empty answer)"})
                    else:
                        if tool_output:
                            ws.add("tool_result", tool_output, role="tool")
                        ws.add("turn", question, role="user"); ws.add("turn", answer or "(empty answer)", role="assistant")   # an empty answer (thinking used the budget) must not stop the run
                    print(f"{mode:12s} step {n:2d} {'recall ' if tool_output is None else 'module '} {'ok ' if correct else 'BAD'} prompt={tokens:6d} {seconds:5.1f}s {info}", flush=True)
                print(f"== {mode}: prompt tokens sent in total {totals['tokens']}, seconds {totals['seconds']:.0f}, correct {totals['correct']}/{len(steps)}\n", flush=True)
            rt.model_loader.unload(resolution)
        except BaseException:
            lab.finish_run(run_id, "failed")
            raise
        lab.finish_run(run_id)
    print(f"test lab run {run_id}: python benchmarks/testlab_cli.py summary {run_id}")


if __name__ == "__main__":
    main()
