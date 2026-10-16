"""Command line for the shared test lab (see guppi_runtime/testlab.py and docs/TESTLAB.md).

    python benchmarks/testlab_cli.py status                       who holds the GPU, what is planned, the last runs and events
    python benchmarks/testlab_cli.py hold --owner NAME --purpose TEXT [--ttl 600] [--wait 1800] -- <command ...>
                                                                  take the GPU lease, run the command, give the lease back
    python benchmarks/testlab_cli.py plan --owner NAME --kind quality --what TEXT [--models a,b]
    python benchmarks/testlab_cli.py queue [--all]                planned and running rounds (--all: done and cancelled too)
    python benchmarks/testlab_cli.py check [--fix]                is every round / run that says `running` still alive? --fix puts orphans back on the plan
    python benchmarks/testlab_cli.py setstatus ID planned|running|done|cancelled [--note TEXT]
    python benchmarks/testlab_cli.py runs                         the last runs
    python benchmarks/testlab_cli.py summary RUN_ID               per model and variant: calls, share ok, mean tokens, mean seconds

`--project DIR` (before the command) names the project directory; default is workspace/GUPPI_OS next to the runtime. `hold` is meant for
anything that puts a model on the GPU without going through GUPPI: LM Studio loads, hermes runs, a manual llama-server. Exit code of `hold`
is the command's own; 75 when the lease could not be had in time.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.testlab import LeaseBusy, TestLab, default_path  # noqa: E402

from guppi_runtime.gpu_preflight import GpuNotClean, clear_leftovers


def stamp(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "-"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=str(RUNTIME.parent / "workspace" / "GUPPI_OS"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("clean", help="stop leftovers of earlier runs on the GPU (only while nobody holds the lease)")
    hold = sub.add_parser("hold")
    hold.add_argument("--owner", required=True)
    hold.add_argument("--purpose", required=True)
    hold.add_argument("--ttl", type=float, default=600)
    hold.add_argument("--wait", type=float, default=0, help="seconds to wait for a busy GPU")
    hold.add_argument("command", nargs=argparse.REMAINDER)
    plan = sub.add_parser("plan")
    plan.add_argument("--owner", required=True)
    plan.add_argument("--kind", required=True)
    plan.add_argument("--what", required=True)
    plan.add_argument("--models", default="")
    ck = sub.add_parser("check")
    ck.add_argument("--fix", action="store_true"); ck.add_argument("--min-age", type=float, default=1800, help="seconds since the last change before --fix touches an entry")
    q = sub.add_parser("queue")
    q.add_argument("--all", action="store_true")
    st = sub.add_parser("setstatus")
    st.add_argument("id", type=int)
    st.add_argument("status")
    st.add_argument("--note", default="")
    sub.add_parser("runs")
    sm = sub.add_parser("summary")
    sm.add_argument("run_id", type=int)
    args = ap.parse_args(argv)

    lab = TestLab(default_path(args.project))
    if args.cmd == "status":
        holder = lab.holder()
        if holder:
            print(f"GPU: HELD by {holder['owner']} for '{holder['purpose']}' (pid {holder['pid']}, since {stamp(holder['acquired'])}, "
                  f"heartbeat {holder['age_s']:.0f}s ago{', STALE: will be taken over' if holder['stale'] else ''})")
        else:
            print("GPU: free")
        for r in lab.reservations():
            print(f"RESERVED by {r['owner']} for '{r['purpose']}' (priority {r['priority']}, pid {r['pid']}): takers with a lower priority wait")
        print("planned/running:")
        alive = {q["id"]: q for q in lab.activity()["queue"]}
        for r in lab.queue():
            mark = "" if r["status"] != "running" else (" [alive]" if alive[r["id"]]["active"] else " [ORPHANED? nothing alive behind it, see `check`]")
            print(f"  #{r['id']} [{r['status']}] {r['owner']} {r['kind']}: {r['description']} ({r['models']}){mark}")
        print("last runs:")
        for r in lab.runs(5):
            print(f"  run {r['id']} [{r['status']}] {r['owner']} {r['kind']}: {r['label']} ({stamp(r['started'])})")
        print("last events:")
        for e in lab.events(5):
            print(f"  {stamp(e['ts'])} {e['kind']} {e['owner']} {e['detail']}")
    elif args.cmd == "clean":
        if lab.holder() and not lab.holder()["stale"]:
            print("GPU is held by a running lease; not cleaning", file=sys.stderr)
            return 75
        try:
            print("GPU in use after cleaning:", clear_leftovers(), "GiB")
        except GpuNotClean as exc:
            print(f"not clean: {exc}", file=sys.stderr)
            return 1
    elif args.cmd == "hold":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            raise SystemExit("hold needs a command after --")
        try:
            with lab.lease(args.owner, args.purpose, ttl_s=args.ttl, wait_s=args.wait, preflight=clear_leftovers):
                return subprocess.call(command)
        except LeaseBusy as busy:
            print(f"GPU busy: {busy}", file=sys.stderr)
            return 75
    elif args.cmd == "plan":
        print("planned as #%d" % lab.plan(args.owner, args.kind, args.what, [m for m in args.models.split(",") if m]))
    elif args.cmd == "check":
        seen = lab.activity()
        for q in seen["queue"]:
            print(f"round #{q['id']} {q['owner']} {q['kind']}: {'alive' if q['active'] else 'ORPHANED'} ({q['why']})")
        for r in seen["runs"]:
            print(f"run {r['id']} {r['owner']} {r['kind']}: {'alive' if r['active'] else 'ORPHANED'} ({r['why']})")
        if not seen["queue"] and not seen["runs"]: print("nothing is marked as running")
        if args.fix:
            done = lab.reap_stale(args.min_age)
            print(f"fixed: rounds back on the plan {done['queue']}, runs marked aborted {done['runs']}")
    elif args.cmd == "queue":
        for r in lab.queue(("planned", "running", "done", "cancelled") if args.all else ("planned", "running")):
            print(f"#{r['id']} [{r['status']}] {r['owner']} {r['kind']}: {r['description']} ({r['models']}) {r['note']}")
    elif args.cmd == "setstatus":
        print("ok" if lab.set_queue_status(args.id, args.status, args.note) else "no such id")
    elif args.cmd == "runs":
        for r in lab.runs():
            print(f"run {r['id']} [{r['status']}] {r['owner']} {r['kind']}: {r['label']} ({stamp(r['started'])})")
    elif args.cmd == "summary":
        for r in lab.summary(args.run_id):
            ok = "-" if r["ok_rate"] is None else f"{r['ok_rate']:.0%}"
            print(f"{r['model']:34s} {r['variant']:12s} n={r['n']:3d} ok={ok:>5s} tokens_out={r['tokens_out'] or 0:7.0f} seconds={r['seconds'] or 0:6.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
