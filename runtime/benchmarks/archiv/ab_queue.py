r"""One generic A/B queue for devvm builds (Claude 2026-10-13: three near-identical copies of one script, and a stale-result bug: after a failed start the old result file was taken for the new run).

    .venv\Scripts\python.exe benchmarks/ab_queue.py <project> --spec skill_need --seed benchmarks/skill_need_seed --arm A= --arm B="--skills runtime_data/skill_library_core" --pairs 3 --rework 0 --keep-going --tag skill_need_x

Arms run alternately (A B A B ...), every build with the standard settings of the night queue (coder.local_primary, solo, --coder-ext all, FA on, KV q8_0, ubatch 512, 32k). A start that fails
(exit code not 0, e.g. the GPU preflight sees 2.6 GiB of Windows processes) is repeated up to 3 times; a result file is only taken when it is NEWER than the start of its run.
Results: runtime_data/measurements/<tag>/summary.json, report.txt (stage matrix, seconds, calls, tool calls of the model per tool from the recorded answers) and queue.log. The last line of queue.log is
`ab queue finished`, which a monitor can wait for. Nothing is changed in the project; the build holds the GPU lease itself."""
import argparse
import importlib.util
import json
import shlex
import sys
import time
from collections import Counter
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))
_spec = importlib.util.spec_from_file_location("night_queue", RUNTIME / "benchmarks" / "archiv" / "night_queue_2026-10-11.py")
night = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night)

FINISHED = "ab queue finished"


def tool_counts(replay_dir):
    counts = Counter()

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("name"), str) and "arguments" in node:
                counts[node["name"]] += 1
                if isinstance(node["arguments"], str) and '"brief": true' in node["arguments"].replace('":true', '": true'):
                    counts["brief"] += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for file in sorted(Path(replay_dir).glob("*.jsonl")):
        for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                walk(json.loads(line).get("response"))
            except ValueError:
                continue
    return counts


def report_text(summary, stages_order, replays):
    out = [f"{summary['tag']}: {summary['spec']}, {summary['recipe']}, pairs {summary['pairs']}"]
    for arm, rows in summary["arms"].items():
        total = Counter()
        for i, row in enumerate(rows, 1):
            marks = "".join("+" if row.get("stage_results", {}).get(s) else "-" for s in stages_order)
            for s in stages_order:
                total[s] += bool(row.get("stage_results", {}).get(s))
            tools = ""
            if row.get("exported_to"):
                counts = tool_counts(replays / Path(str(row["exported_to"]).replace("\\", "/")).name)
                tools = "  tools " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()) if k.startswith("skill_") or k == "brief") if counts else ""
            out.append(f"  {arm}{i}: exit {row.get('exit')}  {row.get('passed')}/{len(stages_order)}  {marks}  {row.get('seconds')} s  {row.get('calls')} calls{tools}")
        out.append(f"  {arm} per stage: " + ", ".join(f"{s} {total[s]}/{len(rows)}" for s in stages_order) + f"   all stages {sum(total.values())}/{len(rows) * len(stages_order)}")
    return "\n".join(out)


class ABQueue(night.Queue):
    def __init__(self, project, args):
        super().__init__(project)
        self.args = args
        self.out = self.project / "runtime_data" / "measurements" / args.tag
        self.out.mkdir(parents=True, exist_ok=True)
        self.env["TESTLAB_OWNER"] = f"claude_{args.tag}"
        self.summary = {"started": night.stamp(), "tag": args.tag, "spec": args.spec, "recipe": args.recipe, "pairs": args.pairs, "server": night.SERVER,
                        "arms": {name: [] for name, _ in args.arms}}

    def newest(self, spec, after):
        return super().newest(spec, after + 1)

    def build(self, *a, **kw):
        row = {}
        for attempt in range(1, 4):
            row = super().build(*a, **kw)
            if row.get("exit") == 0:
                return row
            self.say(f"  start failed (exit {row.get('exit')}), attempt {attempt} of 3, again in 40 s")
            time.sleep(40)
        return {**row, "stage_results": {}, "passed": 0, "seconds": None, "calls": None, "exported_to": None}

    def save(self):
        (self.out / "summary.json").write_text(night.json.dumps(self.summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def main(self):
        args = self.args
        self.say(f"ab queue started: {args.spec}, arms {[n for n, _ in args.arms]}, {args.pairs} pairs")
        mode = ["--rework", str(args.rework), "--mode", "solo", "--self-check", "none"] + (["--keep-going"] if args.keep_going else []) + (["--seed", args.seed] if args.seed else [])
        for pair in range(1, args.pairs + 1):
            for name, extra in args.arms:
                self.summary["arms"][name].append(self.build(args.recipe, args.spec, mode + extra, args.timeout, f"{name}{pair}"))
                self.save()
                if self.canary_failed():
                    self.say("GPU CANARY FAILED - stopped (NVIDIA debug mode on?)")
                    self.summary["stopped"] = "gpu_canary_failed"; self.save()
                    return
        order = list(next((r["stage_results"] for rows in self.summary["arms"].values() for r in rows if r.get("stage_results")), {}))
        text = report_text(self.summary, order, self.project / "runtime_data" / "devvm_replays" / args.spec)
        (self.out / "report.txt").write_text(text, encoding="utf-8")
        print(text)
        self.say(FINISHED)


def parse_arm(text):
    name, _, rest = text.partition("=")
    if not name.strip():
        raise argparse.ArgumentTypeError("--arm NAME=EXTRA ARGS")
    return name.strip(), shlex.split(rest)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--seed")
    ap.add_argument("--arm", dest="arms", action="append", type=parse_arm, required=True, help='NAME=extra devvm_build arguments, e.g. B="--skills runtime_data/skill_library_core"')
    ap.add_argument("--pairs", type=int, default=3)
    ap.add_argument("--rework", type=int, default=1)
    ap.add_argument("--keep-going", action="store_true")
    ap.add_argument("--recipe", default="coder.local_primary")
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--tag", help="result folder name (default: <spec>_<date>)")
    args = ap.parse_args(argv)
    args.tag = args.tag or f"{args.spec}_{night.stamp()[:10]}"
    if len({n for n, _ in args.arms}) != len(args.arms):
        raise SystemExit("arm names must be different")
    ABQueue(args.project, args).main()


if __name__ == "__main__":
    main()
