r"""Do two small models work better together than alone? Jan-code-4b writes the fix, SWE-Review-8B reviews it, Jan repairs on the review.

    .venv\Scripts\python.exe benchmarks/small_team.py <project_dir> [--seeds 2] [--rounds 3] [--reviewer-modes tools,inline] [--no-lessons | --all-lessons]

Extends rework_bench.py (same five tasks, same static grading: model code is never executed on this host).
Captain 2026-10-05: "erst Jan und SWE-Review testen ... nur mit tools funktionieren richtig, daher tools anbinden". Both models are Qwen3 builds with
a <tool_call> template, so both work through guppi_runtime.devenv.model_tools (read_file, check_syntax, submit_fix / submit_review) in the loop below.

Reviewer modes `test` and `test+review` (since 2026-10-05): an EXECUTED test decides, run inside GUPPI's microVM (benchmarks/judge.py, never on this host).
`test`: the coder gets the failing checks back ("input, expected, got"). `test+review`: SWE-Review is asked only for rejected candidates and its cause is added.
Their final grade is the number of candidates that pass every check (`*_pass`); the static grade stays in the rows for comparison.

Per task and seed:
  round 1   Jan repairs the module with tools                        -> graded alone = "solo"
  review    SWE-Review reads the candidate and calls submit_review    -> PASS ends the item, FAIL goes back to Jan with the cause
  repair    Jan repairs again with the review (up to --rounds rounds) -> the last candidate graded = "team"
The reviewer runs in `tools` mode (submit_review) and/or `inline` mode (verdict in plain text, as measured on 2026-10-04: 39 s, often cut off).
Reviewer quality is read against the static grade: a FAIL for a correct candidate is a false rejection, a PASS for a wrong one a false pass.
Both models fit on the 12 GB card together but run on one fixed port, so they are loaded alternately (about 5 s each). Holds the GPU lease.
Results: runtime_data/measurements/smallteam_<date>.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rework_bench import TASKS, grade                                                 # noqa: E402  (TASKS: the five original tasks, used by other benches)
from team_tasks import SETS                                                          # noqa: E402
import judge as judge_mod                                                            # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.knowledge import KnowledgeStore                                   # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.devenv.model_tools import ToolBox, run_tool_loop                         # noqa: E402
from guppi_runtime.jobs.run_log import RunLog                                             # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                              # noqa: E402

from guppi_runtime.local_paths import expand                                     # noqa: E402

MODELS_ROOT = Path(expand("<modelle>"))      # the model folder of this PC (runtime/config/local_paths.yaml)
CODER = {"alias": "jan-code-4b", "gguf": MODELS_ROOT / "janhq/Jan-code-4b-gguf/Jan-code-4b-Q4_K_M.gguf", "temperature": 0.1}
REVIEWER = {"alias": "swe-review-8b", "gguf": MODELS_ROOT / "mradermacher/SWE-Review-8B-i1-GGUF/SWE-Review-8B.i1-Q4_K_M.gguf", "temperature": 0.6}
CONTEXT = 16384


def server_profile(model):
    """Flash-Attention is off: with it on, the b11371 (CUDA 12.4) server dies with `illegal memory access` after 6-21 requests on this PC
    (cuda_crash_hunt 2026-10-05: 4 of 4 runs crashed; with it off 4 of 4 runs stayed clean for 150 requests, 0 driver events)."""
    return {"gguf": str(model["gguf"]), "flash_attn": "off"}


def pick_lessons(knowledge, task, args):
    """The lessons that go into the coder's prompt. Small models get AT MOST ONE, the best fit (lesson_cap_probe 2026-10-06: first try 46 of 48 with one lesson, 39 with two, 42 with all,
    and `isoformat_date` fell from 6/6 to 0/6 when two lessons came together); --all-lessons restores the old behaviour for comparison."""
    text = task["code"] + task["repro"]
    if args.no_lessons: return []
    if args.all_lessons: return [r["content"]["summary"] for r in knowledge.lessons_for(text)]
    return [r["content"]["summary"] for r in knowledge.lessons_for(text, limit=args.max_lessons, rank=True, min_specificity=8)]


def failure_text(task, lessons):
    text = f"The tests fail:\n{task['failure']}\n\nGUPPI reproduced the failure in its VM:\n{task['repro']}\n"
    if lessons:
        text += "\nLessons from GUPPI's knowledge base that match this code:\n" + "\n".join(f"- {l}" for l in lessons) + "\n"
    return text


def coder_prompt(review=None, previous=None, hint=None):
    base = ("Fix the Python module mod.py in the task folder. Its contract (the docstring) is correct and the tests are correct. "
            "Read mod.py and failure.txt with read_file, check your version with check_syntax (write it to fix.py first with write_file), "
            "then hand in the complete fixed module with submit_fix.")
    if review:
        base += f"\n\nYour previous version (fix.py) was reviewed and rejected: {review}\nRead fix.py, correct that defect and submit again."
    if hint:
        base += f"\n\n{hint}"
    return base


REVIEW_RULES = ("You review a repair. mod.py is the original module with a defect, failure.txt describes the failing test, candidate.py is the proposed fix. "
                "The docstring is the contract. Decide whether candidate.py fixes the failure exactly as the contract says, without changing anything else. "
                "Do not rewrite the code. ")


def reviewer_prompt(mode):
    if mode == "tools":
        return REVIEW_RULES + "Read the files with read_file, then call submit_review with verdict PASS or FAIL (and for FAIL the defect in one sentence)."
    return REVIEW_RULES + "Files:\n{files}\nAnswer in at most 6 lines and end with a line `VERDICT: PASS` or `VERDICT: FAIL - <defect in one sentence>`."


def post_factory(endpoint):
    def post(body):
        req = urllib.request.Request(endpoint + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.loads(r.read())
    return post


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", flags=re.S)
    return blocks[-1] if blocks else (text or "")


def repair(post, item, review=None, hint=None):
    folder = item["folder"]
    box = ToolBox(folder, ("read_file", "write_file", "check_syntax"), terminal="submit_fix")
    out = run_tool_loop(post, CODER["alias"], [{"role": "user", "content": coder_prompt(review, hint=hint)}], box, CODER, max_turns=8, max_tokens=4000)
    code = (out["final"] or {}).get("code") or extract_code(out.get("content"))
    if out["final"] is None and (folder / "fix.py").is_file() and not code.strip():
        code = (folder / "fix.py").read_text(encoding="utf-8")
    checks, ok = grade(item["task"], code)
    (folder / "fix.py").write_text(code or "", encoding="utf-8")
    return {"code": code, "fixed": ok, "checks": checks, "submitted": out["final"] is not None, "turns": out["turns"], "tool_calls": out["tool_calls"],
            "finish": out["finish"], "seconds": out["seconds"], "error": out.get("error")}


def review(post, item, mode):
    folder = item["folder"]
    (folder / "candidate.py").write_text(item["candidate"]["code"] or "", encoding="utf-8")
    if mode == "tools":
        box = ToolBox(folder, ("read_file", "check_syntax"), terminal="submit_review")
        out = run_tool_loop(post, REVIEWER["alias"], [{"role": "user", "content": reviewer_prompt("tools")}], box, REVIEWER, max_turns=8, max_tokens=4000)
        final = out["final"] or {}
        return {"verdict": final.get("verdict"), "cause": final.get("cause", ""), "turns": out["turns"], "tool_calls": out["tool_calls"],
                "finish": out["finish"], "seconds": out["seconds"], "error": out.get("error")}
    files = "".join(f"--- {n} ---\n{(folder / n).read_text(encoding='utf-8')}\n" for n in ("mod.py", "failure.txt", "candidate.py"))
    t0 = time.monotonic()
    try:
        data = post({"model": REVIEWER["alias"], "messages": [{"role": "user", "content": reviewer_prompt("inline").replace("{files}", files)}],
                     "max_tokens": 6000, "temperature": REVIEWER["temperature"]})
    except Exception as exc:
        return {"verdict": None, "cause": "", "finish": "error", "error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - t0, 1)}
    choice = data["choices"][0]
    text = (choice["message"].get("content") or "")
    m = re.findall(r"VERDICT:\s*(PASS|FAIL)\s*-?\s*(.*)", text)
    return {"verdict": m[-1][0] if m else None, "cause": m[-1][1][:500] if m else "", "finish": choice.get("finish_reason"),
            "seconds": round(time.monotonic() - t0, 1), "answer": text[:1500]}


def summarize(items):
    n = len(items)
    solo = sum(i["rounds"][0]["candidate"]["fixed"] for i in items)
    team = sum(i["final_fixed"] for i in items)
    reviews = [r["review"] for i in items for r in i["rounds"] if r.get("review")]
    cand = [(r["candidate"]["fixed"], r["review"]["verdict"]) for i in items for r in i["rounds"] if r.get("review")]
    return {"items": n, "solo_fixed": f"{solo}/{n}", "team_fixed": f"{team}/{n}",
            "reviews": len(reviews), "no_verdict": sum(1 for v in (c[1] for c in cand) if v is None),
            "false_rejections": sum(1 for ok, v in cand if ok and v == "FAIL"), "false_passes": sum(1 for ok, v in cand if not ok and v == "PASS"),
            "correct_calls": sum(1 for ok, v in cand if (ok and v == "PASS") or (not ok and v == "FAIL")),
            "avg_review_seconds": round(sum(r["seconds"] for r in reviews) / max(1, len(reviews)), 1),
            "avg_repair_seconds": round(sum(r["candidate"]["seconds"] for i in items for r in i["rounds"]) / max(1, sum(len(i["rounds"]) for i in items)), 1)}


def summarize_judged(items):
    n = len(items)
    passed = lambda e: judge_mod.all_passed(e)
    solo = sum(passed(i["rounds"][0]["judge"]) for i in items)
    team = sum(passed(i["rounds"][-1]["judge"]) for i in items)
    reviews = [r["review"] for i in items for r in i["rounds"] if r.get("review")]
    return {"items": n, "solo_pass": f"{solo}/{n}", "team_pass": f"{team}/{n}", "repairs": sum(len(i["rounds"]) - 1 for i in items),
            "rounds_used_avg": round(sum(len(i["rounds"]) for i in items) / max(1, n), 2), "reviewer_calls": len(reviews),
            "reviewer_no_verdict": sum(1 for r in reviews if r["verdict"] is None),
            "static_solo_fixed": f"{sum(i['rounds'][0]['candidate']['fixed'] for i in items)}/{n}", "static_team_fixed": f"{sum(i['final_fixed'] for i in items)}/{n}"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--seeds", type=int, default=2); ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--reviewer-modes", default="test,test+review", help="tools, inline (SWE-Review decides), test, test+review (an executed test decides)"); ap.add_argument("--tasks", default="all", choices=["base", "hard", "all"], help="base: rework tasks with stricter checks, hard: three harder ones"); ap.add_argument("--no-lessons", action="store_true"); ap.add_argument("--all-lessons", action="store_true"); ap.add_argument("--max-lessons", type=int, default=1)
    args = ap.parse_args()
    modes = [m for m in args.reviewer_modes.split(",") if m in ("tools", "inline", "test", "test+review")]
    tasks = SETS[args.tasks]
    project = Path(args.project)
    knowledge = KnowledgeStore(project / "runtime_data" / "knowledge" / "records.jsonl")
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_smallteam_")))
    measurements = project / "runtime_data" / "measurements"
    out_path = measurements / f"smallteam_{date.today().isoformat()}.json"      # the latest finished result; the run log keeps every run
    log = RunLog(measurements, "smallteam", config={"seeds": args.seeds, "rounds": args.rounds, "modes": modes, "tasks": args.tasks, "lessons": "none" if args.no_lessons else "all" if args.all_lessons else args.max_lessons,
                                                    "coder": CODER["alias"], "reviewer": REVIEWER["alias"]})
    work = Path(tempfile.mkdtemp(prefix="guppi_smallteam_files_"))
    result = {"tasks": [t["id"] for t in tasks], "seeds": args.seeds, "rounds": args.rounds, "lessons": "none" if args.no_lessons else "all" if args.all_lessons else args.max_lessons, "coder": CODER["alias"],
              "reviewer": REVIEWER["alias"], "modes": {}}

    crashes = []
    result["server_crashes"] = crashes
    current = {}

    def load(model):
        current["model"] = model
        runtime.load_model(model["alias"], context_length=CONTEXT, gpu="max", identifier=model["alias"], parallel=1, server=server_profile(model))
        plain = post_factory(runtime.endpoint)

        def post(body):
            # A llama-server that dies mid-run (earlier: CUDA errors on this GPU) is restarted once and the call repeated; its log is kept.
            try:
                return plain(body)
            except (ConnectionError, urllib.error.URLError, OSError) as exc:
                log = runtime.state_dir / "server.log"
                crashes.append({"model": model["alias"], "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                                "log_tail": log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.is_file() else ""})
                log.say(f"   !! server connection lost ({type(exc).__name__}), restarting {model['alias']}")
                try: runtime.unload_model(all_models=True)
                except Exception: pass
                time.sleep(3)
                runtime.load_model(model["alias"], context_length=CONTEXT, gpu="max", identifier=model["alias"], parallel=1, server=server_profile(model))
                return plain(body)
        return post

    def unload():
        runtime.unload_model(all_models=True); time.sleep(2)

    def ser(items):
        return [{**{k: v for k, v in it.items() if k not in ("task", "folder")}, "task": it["task"]["id"] if isinstance(it["task"], dict) else it["task"]} for it in items]

    def checkpoint(first_items=None, mode=None, items=None):
        """After every single result: the state so far goes to the run's own JSON (atomic), so a crash or a stop loses at most the call in flight."""
        if first_items is not None: result["first_round"] = ser(first_items)
        if mode is not None: result.setdefault("in_progress", {})[mode] = ser(items)
        log.save(result)

    def fresh_items():
        items = []
        for task in tasks:
            lessons = pick_lessons(knowledge, task, args)
            for seed in range(args.seeds):
                folder = work / f"{task['id']}_{seed}"; folder.mkdir(parents=True, exist_ok=True)
                (folder / "mod.py").write_text(task["code"], encoding="utf-8"); (folder / "failure.txt").write_text(failure_text(task, lessons), encoding="utf-8")
                items.append({"task": task, "seed": seed, "folder": folder, "rounds": [], "candidate": None})
        return items

    with log, TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "small_team"), "small team bench: jan-code-4b + swe-review-8b", ttl_s=1800, wait_s=3600,
                                              preflight=clear_leftovers):
        log.say(f"== round 1: {CODER['alias']} alone, {len(tasks) * args.seeds} items")
        post = load(CODER)
        first = fresh_items()
        try:
            for it in first:
                it["candidate"] = repair(post, it)
                log.say(f"   {it['task']['id']:24s} #{it['seed']}: {'FIXED' if it['candidate']['fixed'] else 'not fixed'}  {it['candidate']['seconds']} s, "
                      f"{it['candidate']['turns']} turns, tools {it['candidate']['tool_calls']}")
                checkpoint(first)
        finally:
            unload()
        if any(m.startswith("test") for m in modes):
            log.say("== judging the round-1 candidates in the VM")
            judged = judge_mod.judge(project, {f"{it['task']['id']}_{it['seed']}": (it["task"]["id"], it["candidate"]["code"]) for it in first})
            for it in first:
                it["candidate"]["judge"] = judged[f"{it['task']['id']}_{it['seed']}"]
                e = it["candidate"]["judge"]
                log.say(f"   {it['task']['id']:24s} #{it['seed']}: {e['passed']}/{e['total']} checks" + (f"  ({e['failures'][0][:110]})" if e["failures"] else "") + (f"  ERROR {e['error']}" if e["error"] else ""))
            checkpoint(first)
        for mode in modes:
            if mode.startswith("test"):
                items = fresh_items()
                for it, f in zip(items, first):
                    it["candidate"] = f["candidate"]
                    (it["folder"] / "fix.py").write_text(f["candidate"]["code"] or "", encoding="utf-8")
                log.say(f"== team with an executed test as judge, mode '{mode}'")
                active = list(items)
                for rnd in range(1, args.rounds + 1):
                    todo = [it for it in active if "judge" not in it["candidate"]]
                    if todo:
                        judged = judge_mod.judge(project, {f"{it['task']['id']}_{it['seed']}": (it["task"]["id"], it["candidate"]["code"]) for it in todo})
                        for it in todo: it["candidate"]["judge"] = judged[f"{it['task']['id']}_{it['seed']}"]
                    for it in active:
                        e = it["candidate"]["judge"]
                        it["rounds"].append({"round": rnd, "candidate": dict(it["candidate"]), "judge": e, "passed": judge_mod.all_passed(e)})
                        log.say(f"   r{rnd} judge {it['task']['id']:24s} #{it['seed']}: {e['passed']}/{e['total']} checks -> {'PASS' if it['rounds'][-1]['passed'] else 'FAIL'}")
                    checkpoint(mode=mode, items=items)
                    failing = [it for it in active if not it["rounds"][-1]["passed"]]
                    if rnd == args.rounds or not failing:
                        break
                    if mode == "test+review":
                        post = load(REVIEWER)
                        try:
                            for it in failing:
                                it["rounds"][-1]["review"] = review(post, it, "tools")
                                log.say(f"   r{rnd} review {it['task']['id']:24s} #{it['seed']}: {it['rounds'][-1]['review']['verdict']}  {it['rounds'][-1]['review']['seconds']} s")
                        finally:
                            unload()
                    post = load(CODER)
                    try:
                        for it in failing:
                            note = judge_mod.feedback(it["rounds"][-1]["judge"])
                            cause = (it["rounds"][-1].get("review") or {}).get("cause")
                            if cause: note += "\nA second reviewer adds: " + cause
                            it["candidate"] = repair(post, it, note)
                            log.say(f"   r{rnd} repair {it['task']['id']:24s} #{it['seed']}: {it['candidate']['seconds']} s")
                        checkpoint(mode=mode, items=items)
                    finally:
                        unload()
                    active = failing
                for it in items:
                    it["final_fixed"] = it["candidate"]["fixed"]; it["task"] = it["task"]["id"]; it["folder"] = str(it["folder"])
                summary = summarize_judged(items)
                result["modes"][mode] = {"summary": summary, "items": items}
                log.say(f"  -> {mode}: {summary}")
                out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
                log.save(result)
                continue
            log.say(f"== team with reviewer mode '{mode}'")
            items = fresh_items()
            for it, f in zip(items, first):
                it["candidate"] = f["candidate"]
                (it["folder"] / "fix.py").write_text(f["candidate"]["code"] or "", encoding="utf-8")     # the repair prompt points at fix.py
            active = list(items)
            for rnd in range(1, args.rounds + 1):
                if not active: break
                post = load(REVIEWER)
                try:
                    for it in active:
                        rev = review(post, it, mode)
                        it["rounds"].append({"round": rnd, "candidate": {k: v for k, v in it["candidate"].items()}, "review": rev})
                        log.say(f"   r{rnd} review {it['task']['id']:24s} #{it['seed']}: candidate {'ok ' if it['candidate']['fixed'] else 'BAD'} -> {rev['verdict']}  "
                              f"{rev['seconds']} s {rev.get('finish') or ''}")
                        checkpoint(mode=mode, items=items)
                finally:
                    unload()
                rejected = [it for it in active if it["rounds"][-1]["review"]["verdict"] == "FAIL"]
                if rnd == args.rounds or not rejected:
                    active = []; break
                post = load(CODER)
                try:
                    for it in rejected:
                        it["candidate"] = repair(post, it, it["rounds"][-1]["review"]["cause"] or "the fix does not satisfy the contract")
                        log.say(f"   r{rnd} repair {it['task']['id']:24s} #{it['seed']}: {'FIXED' if it['candidate']['fixed'] else 'not fixed'}  {it['candidate']['seconds']} s")
                        checkpoint(mode=mode, items=items)
                finally:
                    unload()
                active = rejected
            for it in items:
                it["final_fixed"] = it["candidate"]["fixed"]
                it["task"] = it["task"]["id"]; it["folder"] = str(it["folder"])
            summary = summarize(items)
            # the solo figure of the first round is the same candidates for every reviewer mode
            result["modes"][mode] = {"summary": summary, "items": items}
            log.say(f"  -> {mode}: {summary}")
            out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            log.save(result)
    log.say(f"  DONE -> {out_path.name}")


if __name__ == "__main__":
    main()
