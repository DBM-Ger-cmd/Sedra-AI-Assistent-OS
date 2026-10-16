r"""Serves one GUPPI model through GUPPI's own llama-server runtime for an editor (VS Code with Cline or Continue) and measures what the editor asks of it (Captain 2026-10-09).

    .venv\Scripts\python.exe benchmarks/serve_model.py serve <project_dir> [--recipe coder.local_primary] [--context 32768] [--reasoning off] [--hours 4]
    .venv\Scripts\python.exe benchmarks/serve_model.py stats <project_dir>

serve  loads the model like the DevVM builds do (the recipe's settings, flash attention off, big_window_server for windows above the recommended one), holds the GPU lease and answers on http://127.0.0.1:8089/v1 (the model name is printed).
       It ends when the file <project>/runtime_data/vscode_serve/STOP appears, after --hours, or on Ctrl+C, and unloads the model.
stats  reads the server log of the session and prints what the editor used: requests, prompt tokens and speed, generated tokens and speed, time. The numbers are what the comparison table needs.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(RUNTIME / "benchmarks"))

PROMPT = re.compile(r"prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens")
EVAL = re.compile(r"(?<!prompt )eval time =\s*([\d.]+) ms /\s*(\d+) tokens")
TOTAL = re.compile(r"total time =\s*([\d.]+) ms /\s*(\d+) tokens")


def session_dir(project):
    return Path(project) / "runtime_data" / "vscode_serve"


def summarize(log_text):
    """What the editor used, from the lines llama-server writes after every request."""
    prompt_ms = prompt_tokens = gen_ms = gen_tokens = total_ms = requests = 0
    for line in log_text.splitlines():
        if (found := PROMPT.search(line)):
            prompt_ms += float(found.group(1)); prompt_tokens += int(found.group(2))
        elif (found := EVAL.search(line)):
            gen_ms += float(found.group(1)); gen_tokens += int(found.group(2))
        elif (found := TOTAL.search(line)):
            total_ms += float(found.group(1)); requests += 1
    return {"requests": requests, "prompt_tokens": prompt_tokens, "prompt_tps": round(prompt_tokens / (prompt_ms / 1000), 1) if prompt_ms else None, "generated_tokens": gen_tokens,
            "gen_tps": round(gen_tokens / (gen_ms / 1000), 1) if gen_ms else None, "busy_seconds": round(total_ms / 1000, 1)}


def serve(args):
    import devvm_agents_bench as bench
    from guppi_runtime.gpu_preflight import clear_leftovers
    from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.run_log import RunLog
    from guppi_runtime.testlab import TestLab, default_path

    project = Path(args.project)
    folder = session_dir(project)
    folder.mkdir(parents=True, exist_ok=True)
    stop = folder / "STOP"
    if stop.exists():
        stop.unlink()
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    runtime = LlamaServerRuntime(config, folder)
    log = RunLog(project / "runtime_data" / "measurements", "serve_model", config=vars(args))
    loader = bench.BenchLoader(runtime, project, {"coder": args.recipe}, log, context=int(args.context), server_extra={"reasoning": args.reasoning})
    deadline = time.monotonic() + args.hours * 3600
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "serve_model"), f"vscode serve {args.recipe}", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        alias, _, _ = loader.load(args.recipe)
        info = {"endpoint": runtime.endpoint + "/v1", "model": alias, "recipe": args.recipe, "context": int(args.context), "reasoning": args.reasoning, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "log": str(folder / "server.log")}
        (folder / "endpoint.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
        print(json.dumps(info), flush=True)
        print("SERVING (create the file STOP in " + str(folder) + " to end)", flush=True)
        try:
            while not stop.exists() and time.monotonic() < deadline:
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            loader.unload()
            result = summarize((folder / "server.log").read_text(encoding="utf-8", errors="replace")) if (folder / "server.log").is_file() else {}
            (folder / "last_stats.json").write_text(json.dumps({**info, "stats": result, "ended": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
            print("STATS", json.dumps(result), flush=True)


def stats(args):
    log = session_dir(args.project) / "server.log"
    print(json.dumps(summarize(log.read_text(encoding="utf-8", errors="replace")) if log.is_file() else {"error": "no server log yet"}, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    serving = sub.add_parser("serve")
    serving.add_argument("project")
    serving.add_argument("--recipe", default="coder.local_primary")
    serving.add_argument("--context", default="32768")
    serving.add_argument("--reasoning", choices=["auto", "on", "off"], default="off")
    serving.add_argument("--hours", type=float, default=4)
    sub.add_parser("stats").add_argument("project")
    args = ap.parse_args()
    serve(args) if args.cmd == "serve" else stats(args)


if __name__ == "__main__":
    main()
