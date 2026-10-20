r"""Do more lessons in the prompt hurt the small coder? Jan-code-4b, all team tasks, executed test as judge (VM), round 1 only.

    .venv\Scripts\python.exe benchmarks/lesson_cap_probe.py <project_dir> [--seeds 6] [--variants none,cap1,cap2,all]

Found on 2026-10-05 (feedback_probe.py): on `isoformat_date` each of the two lessons the knowledge base attaches works alone (6/6) but both together fail (0/6), and
an extra rule in the first prompt fails too (0/6). Here the same question over the whole task set: the lessons that `knowledge.lessons_for` returns, cut to the first
N (none, 1, 2, all). Result per variant and task: how many of the seeds pass every check on the first try. Holds the GPU lease; log in measurements/logs/lesson_cap_probe_*.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import judge as judge_mod                                                            # noqa: E402
import small_team as st                                                              # noqa: E402
from team_tasks import SETS                                                          # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.knowledge import KnowledgeStore                                   # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.run_log import RunLog                                             # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                              # noqa: E402

CAPS = {"none": 0, "cap1": 1, "cap2": 2, "all": 99}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--seeds", type=int, default=6); ap.add_argument("--variants", default=",".join(CAPS))
    args = ap.parse_args()
    project = Path(args.project)
    names = [v for v in args.variants.split(",") if v in CAPS]
    kb = KnowledgeStore(project / "runtime_data" / "knowledge" / "records.jsonl")
    log = RunLog(project / "runtime_data" / "measurements", "lesson_cap_probe", config={"seeds": args.seeds, "variants": names})
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_cap_")))
    work = Path(tempfile.mkdtemp(prefix="guppi_cap_files_"))
    result = {"variants": {}}
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "lesson_cap_probe"), "lesson cap probe", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        for name in names:
            items = []
            for task in SETS["all"]:
                lessons = [r["content"]["summary"] for r in kb.lessons_for(task["code"] + task["repro"])][:CAPS[name]]
                for seed in range(args.seeds):
                    folder = work / f"{name}_{task['id']}_{seed}"; folder.mkdir(parents=True)
                    (folder / "mod.py").write_text(task["code"], encoding="utf-8"); (folder / "failure.txt").write_text(st.failure_text(task, lessons), encoding="utf-8")
                    items.append({"task": task, "seed": seed, "folder": folder})
            log.say(f"== {name}: {len(items)} first tries")
            runtime.load_model(st.CODER["alias"], context_length=st.CONTEXT, gpu="max", identifier=st.CODER["alias"], parallel=1, server=st.server_profile(st.CODER))
            try:
                post = st.post_factory(runtime.endpoint)
                for it in items: it["candidate"] = st.repair(post, it)
            finally:
                runtime.unload_model(all_models=True)
            judged = judge_mod.judge(project, {f"{i}": (it["task"]["id"], it["candidate"]["code"]) for i, it in enumerate(items)})
            per_task = {}
            for i, it in enumerate(items):
                per_task.setdefault(it["task"]["id"], []).append(judge_mod.all_passed(judged[f"{i}"]))
            total = sum(sum(v) for v in per_task.values())
            result["variants"][name] = {"total": f"{total}/{len(items)}", "per_task": {k: f"{sum(v)}/{len(v)}" for k, v in per_task.items()}}
            log.save(result)
            log.say(f"  -> {name}: {total}/{len(items)}  " + "  ".join(f"{k} {sum(v)}/{len(v)}" for k, v in per_task.items()))
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
