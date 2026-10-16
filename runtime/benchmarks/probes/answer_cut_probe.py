r"""Probe: why does an agent run end with the stop reason `answer_cut` (one answer of 8000 tokens without an end)? (Captain 2026-10-09)

    .venv\Scripts\python.exe benchmarks/probes/answer_cut_probe.py <project_dir> [--model coder.local_primary] [--stage heatmap] [--trials 2] [--reasoning off]

Runs the "coder alone" agent of the DevVM on one stage of the am008 spec (the workspace holds the code of the earlier stages), with the real tools, and records every answer of the model: finish reason, completion tokens, whether it has content,
reasoning text, or tool calls, how long the arguments of each tool call are, the first and the last characters, and whether the text repeats itself. The result tells whether the cut comes from
  - a very long single tool call (a whole file plus tests in one write_file),
  - thinking that does not stop (reasoning_content),
  - a loop of repeated text.
Nothing is integrated; the results go to <project>/runtime_data/measurements/answer_cut_probe_<stamp>.json. It holds the GPU lease.
"""
import argparse
import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(RUNTIME / "benchmarks"))


def repetition(text, size=60):
    """Share of the text that is made of 60-character pieces that occur at least twice (0 = no repetition, near 1 = a loop)."""
    pieces = [text[i:i + size] for i in range(0, max(len(text) - size, 0), size)]
    return round(1 - len(set(pieces)) / len(pieces), 2) if pieces else 0.0


def describe(data):
    """What one completion looks like: the numbers and the edges of its text, tool-call arguments and reasoning."""
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content, reasoning = message.get("content") or "", message.get("reasoning_content") or ""
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = str(function.get("arguments") or "")
        calls.append({"name": function.get("name"), "argument_chars": len(arguments), "head": arguments[:160], "tail": arguments[-160:], "repetition": repetition(arguments)})
    return {"finish": choice.get("finish_reason"), "completion_tokens": (data.get("usage") or {}).get("completion_tokens"), "content_chars": len(content), "content_head": content[:200], "content_tail": content[-200:],
            "content_repetition": repetition(content), "reasoning_chars": len(reasoning), "reasoning_tail": reasoning[-200:], "tool_calls": calls}


def verdict(answers):
    """The most likely cause of the cut of the last answer."""
    if not answers or answers[-1]["finish"] != "length":
        return "no cut"
    last = answers[-1]
    if last["reasoning_chars"] > 4 * max(last["content_chars"], 1) and not last["tool_calls"]:
        return "thinking does not stop"
    if max([last["content_repetition"]] + [c["repetition"] for c in last["tool_calls"]]) >= 0.5:
        return "loop of repeated text"
    if last["tool_calls"]:
        return "one very long tool call (" + str(max(c["argument_chars"] for c in last["tool_calls"])) + " characters)"
    return "long text answer (" + str(last["content_chars"]) + " characters)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--model", default="coder.local_primary")
    ap.add_argument("--stage", default="heatmap")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--reasoning", choices=["auto", "on", "off"], default="off")
    ap.add_argument("--context", default="32768")
    ap.add_argument("--sampling", help="JSON of sampling settings, e.g. {\"temperature\": 0.7, \"top_p\": 0.8, \"top_k\": 20, \"presence_penalty\": 1.0} (default: the near-greedy temperature 0.1 of the DevVM)")
    args = ap.parse_args()
    project = Path(args.project)

    import devvm_agents_bench as bench
    from guppi_runtime.devvm import DevWorkspace
    from guppi_runtime.devvm_agents import SOLO_TASK, AgentBudget, run_agent
    from guppi_runtime.gpu_preflight import clear_leftovers
    from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.run_log import RunLog
    from guppi_runtime.testlab import TestLab, default_path

    spec = importlib.import_module("devvm_specs.am008_meter")
    stages = {stage["name"]: stage for stage in spec.STAGES}
    done = [s for s in spec.STAGES if s["name"] == "daily"]
    reference = (project / "acceptance" / "suites" / "am008_meter" / "reference" / "code_meter.py").read_text(encoding="utf-8")
    seed = reference[:reference.index("def heatmap")] if args.stage == "heatmap" else ""      # the code of the earlier stage(s): everything before the stage under test
    log = RunLog(project / "runtime_data" / "measurements", "answer_cut_probe", config=vars(args))
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_cutprobe_rt_")))
    loader = bench.BenchLoader(runtime, project, {"coder": args.model}, log, context=int(args.context), server_extra={"reasoning": args.reasoning}, sampling_extra=json.loads(args.sampling) if args.sampling else None)
    tool_root = Path(tempfile.mkdtemp(prefix="guppi_cutprobe_"))
    policy = {"max_files": 40, "max_file_bytes": 60000, "max_input_bytes": 200000}
    results = []
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "answer_cut_probe"), "answer cut probe", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        alias, post, sampling = loader.load(args.model)
        try:
            for trial in range(args.trials):
                ws = DevWorkspace(tool_root, f"M-CUT{trial + 1:03d}", policy=dict(policy))
                ws.create()
                if seed:
                    ws.write("code_meter.py", seed)
                answers = []

                def recording_post(body):
                    data = post(body)
                    answers.append(describe(data))
                    return data

                started = time.monotonic()
                task = SOLO_TASK.format(task=stages[args.stage]["task"], lessons="")
                result = run_agent("coder", task, ws, recording_post, alias, sampling=sampling, budget=AgentBudget(), exclude=("git_commit",), label=f"cut probe {trial + 1}")
                row = {"trial": trial + 1, "stopped_by": result["stopped_by"], "calls": result["calls"], "completion_tokens": result["completion_tokens"], "seconds": round(time.monotonic() - started, 1),
                       "answers": answers, "cause": verdict(answers)}
                results.append(row)
                log.say(f"trial {trial + 1}: {row['stopped_by']} after {len(answers)} answers, {row['completion_tokens']} tokens, cause: {row['cause']}")
                print(f"trial {trial + 1}: {row['stopped_by']} after {len(answers)} answers, {row['completion_tokens']} tokens, cause: {row['cause']}", flush=True)
        finally:
            loader.unload()
    out = project / "runtime_data" / "measurements" / f"answer_cut_probe_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"model": args.model, "stage": args.stage, "reasoning": args.reasoning, "sampling": args.sampling, "trials": results}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written: {out}")
    print("PROBE DONE")


if __name__ == "__main__":
    main()
