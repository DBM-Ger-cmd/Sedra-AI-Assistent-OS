r"""Does a short rule fix the one task Jan keeps failing? isoformat_date, Jan-code-4b, executed test as judge (VM).

    .venv\Scripts\python.exe benchmarks/feedback_probe.py <project_dir> [--seeds 6] [--rounds 3] [--task isoformat_date]

In the 2026-10-05 team runs Jan answered every failure of `isoformat_date` by sniffing the library's message (`if "month" in str(e)`, then `or "day"`), never by
converting the exception unconditionally. Variants of the help the coder gets (same task, same judge, every seed on a freshly written folder):
  plain           the failing checks only (as in the team run)
  rule_feedback   failing checks + "decide by the exception type, never by the message text"
  rule_from_start the same rule already in the first prompt and in the feedback
Per variant: how many of the seeds pass every check after round 1, 2, 3. Holds the GPU lease; log and result in measurements/logs/feedback_probe_*.
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
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.run_log import RunLog                                             # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                              # noqa: E402

RULE = ("Rule: when a library call raises an exception that the contract wants turned into another one, catch the exception TYPE and raise the contract's "
        "error unconditionally. Never decide by looking at the text of the library's message.")
VARIANTS = {"plain": {"start": None, "feedback": None}, "rule_feedback": {"start": None, "feedback": RULE}, "rule_from_start": {"start": RULE, "feedback": RULE},
            # what the knowledge base really attached to this task in the team runs: lesson 0 = "re-raise every library exception as the contract's error",
            # lesson 1 = "\d matches Unicode digits in a regex" (not about dates); "lessons" lists the indexes that go into failure.txt
            "kb_both": {"start": None, "feedback": None, "lessons": [0, 1]}, "kb_first_only": {"start": None, "feedback": None, "lessons": [0]},
            "kb_second_only": {"start": None, "feedback": None, "lessons": [1]}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--variants", default=",".join(VARIANTS)); ap.add_argument("--seeds", type=int, default=6); ap.add_argument("--rounds", type=int, default=3); ap.add_argument("--task", default="isoformat_date")
    args = ap.parse_args()
    project = Path(args.project)
    task = next(t for t in SETS["all"] if t["id"] == args.task)
    log = RunLog(project / "runtime_data" / "measurements", "feedback_probe", config={"task": args.task, "seeds": args.seeds, "rounds": args.rounds})
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_probe_")))
    work = Path(tempfile.mkdtemp(prefix="guppi_probe_files_"))
    result = {"task": args.task, "variants": {}}
    from guppi_runtime.knowledge import KnowledgeStore
    kb = [r["content"]["summary"] for r in KnowledgeStore(project / "runtime_data" / "knowledge" / "records.jsonl").lessons_for(task["code"] + task["repro"])]
    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "feedback_probe"), "feedback probe isoformat", ttl_s=1800, wait_s=3600, preflight=clear_leftovers):
        for name in [v for v in args.variants.split(",") if v in VARIANTS]:
            spec = VARIANTS[name]
            items = []
            for seed in range(args.seeds):
                folder = work / f"{name}_{seed}"; folder.mkdir(parents=True)
                (folder / "mod.py").write_text(task["code"], encoding="utf-8"); (folder / "failure.txt").write_text(st.failure_text(task, [kb[i] for i in spec.get("lessons", []) if i < len(kb)]), encoding="utf-8")
                items.append({"task": task, "seed": seed, "folder": folder, "candidate": None, "history": []})
            log.say(f"== {name}")
            active, passes = list(items), []
            for rnd in range(1, args.rounds + 1):
                runtime.load_model(st.CODER["alias"], context_length=st.CONTEXT, gpu="max", identifier=st.CODER["alias"], parallel=1, server=st.server_profile(st.CODER))
                try:
                    post = st.post_factory(runtime.endpoint)
                    for it in active:
                        if rnd == 1:
                            it["candidate"] = st.repair(post, it, hint=spec["start"])
                        else:
                            note = judge_mod.feedback(it["judge"]) + (("\n" + spec["feedback"]) if spec["feedback"] else "")
                            it["candidate"] = st.repair(post, it, note, hint=spec["start"])
                finally:
                    runtime.unload_model(all_models=True)
                judged = judge_mod.judge(project, {f"{it['seed']}": (task["id"], it["candidate"]["code"]) for it in active})
                for it in active:
                    it["judge"] = judged[f"{it['seed']}"]; it["history"].append({"round": rnd, "passed": judge_mod.all_passed(it["judge"]), "checks": f"{it['judge']['passed']}/{it['judge']['total']}", "code": it["candidate"]["code"]})
                done = sum(judge_mod.all_passed(it["judge"]) for it in items)
                passes.append(done)
                log.say(f"   after round {rnd}: {done}/{len(items)} pass every check")
                active = [it for it in active if not judge_mod.all_passed(it["judge"])]
                result["variants"][name] = {"pass_after_round": passes, "items": [{"seed": it["seed"], "history": it["history"]} for it in items]}
                log.save(result)
                if not active: break
            log.say(f"  -> {name}: pass after round {passes}")
    log.say(f"DONE -> {log.json_path.name}")


if __name__ == "__main__":
    main()
