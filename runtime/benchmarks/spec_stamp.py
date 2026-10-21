"""The stamp of a green spec_check (Captain 2026-10-20, line L2): spec_check writes it, devvm_build refuses to build without it.

    <project>/runtime_data/spec_stamps/<spec>.json
    {"spec", "level": "vm" | "host", "result": "ok", "spec_sha256", "ref_sha256", "ref_files", "seed_sha256", "python", "checked_at", "tool"}

level vm   = lint, reference and hidden tests ran ALSO in the python of the microVM (the python the build judges with).
level host = only on the host python (spec_check --host-only): a weaker stamp, devvm_build accepts it with a warning.
spec_sha256 is the hash of the spec file, ref_sha256 one hash over every file of the reference (path and content), seed_sha256 the same over the folder of the module field SEED of the spec ("" without SEED; PIPE-10, 2026-10-21):
a change of one of them after the check makes the stamp stale; a stamp without seed_sha256 (written before PIPE-10) is stale, too.
Standard library only (spec_check and devvm_build both import it)."""
import ast
import hashlib
import json
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
LEVELS = ("vm", "host")


def stamp_path(project, spec):
    return Path(project) / "runtime_data" / "spec_stamps" / f"{spec}.json"


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_sha256(folder):
    """(one hash over every file of the folder, number of files); __pycache__ and .git are left out. A missing folder gives ("", 0)."""
    folder = Path(folder)
    if not folder.is_dir():
        return "", 0
    total, count = hashlib.sha256(), 0
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts):
        total.update(path.relative_to(folder).as_posix().encode("utf-8") + b"\0" + file_sha256(path).encode("ascii") + b"\n")
        count += 1
    return total.hexdigest(), count


def spec_seed(spec, bench=None):
    """The module field `SEED = "benchmarks/<folder>"` of a spec (path relative to runtime/, the parent of benchmarks/), read without running the spec; "" when there is none."""
    tree = ast.parse((Path(bench or BENCH) / "devvm_specs" / f"{spec}.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SEED" for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value.strip()
    return ""


def seed_folder(spec, bench=None):
    """(the SEED text, its folder as a Path) of a spec; ("", None) without SEED. The folder may not exist."""
    seed = spec_seed(spec, bench)
    return (seed, Path(bench or BENCH).parent / seed) if seed else ("", None)


def fingerprint(spec, bench=None, ref=None):
    """The hashes the stamp is bound to: the spec file, the reference folder (devvm_refs/<spec> unless another is given) and the seed folder (SEED of the spec; a SEED that points to a missing folder gives "missing")."""
    bench = Path(bench or BENCH)
    ref = Path(ref) if ref else bench / "devvm_refs" / spec
    ref_hash, ref_files = tree_sha256(ref)
    seed, folder = seed_folder(spec, bench)
    seed_hash = (tree_sha256(folder)[0] or "missing") if seed else ""
    return {"spec_sha256": file_sha256(bench / "devvm_specs" / f"{spec}.py"), "ref_sha256": ref_hash, "ref_files": ref_files, "seed_sha256": seed_hash}


def write(project, spec, level, python, bench=None, ref=None):
    if level not in LEVELS:
        raise ValueError(f"unknown stamp level {level!r}")
    stamp = {"spec": spec, "level": level, "result": "ok", **fingerprint(spec, bench, ref), "python": python,
             "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": "spec_check"}
    path = stamp_path(project, spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stamp, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def remove(project, spec):
    """A spec_check that did NOT end ok takes an older stamp away (it would otherwise still allow a build)."""
    try:
        stamp_path(project, spec).unlink()
        return True
    except FileNotFoundError:
        return False


def gate(project, spec, skip=False, bench=None, allow_host=False):
    """The one rule for every builder (devvm_build, agent_manager run_worker): returns the log lines, or raises SystemExit with the reason as the first word
    (spec_not_checked, spec_changed_since_check, spec_stamp_host_only). skip = --skip-spec-stamp (a warning instead of the stop); allow_host = --allow-host-stamp."""
    reason, stamp = check(project, spec, bench)
    if reason is None:
        lines = [f"spec stamp: {stamp['level']} ok ({stamp.get('python') or '?'}, {stamp.get('checked_at')})"]
        if stamp["level"] != "vm":
            if not allow_host and not skip:
                raise SystemExit(f"spec_stamp_host_only: the stamp of {spec} is level host (host python only); run `benchmarks/spec_check.py {spec} --vm --project <project>` or add --allow-host-stamp")
            lines.append(f"   WARNING: spec stamp level {stamp['level']}: checked on the host python only, not in the microVM (weaker; run spec_check.py {spec} --vm)")
        return lines
    hint = f"{reason}: run `benchmarks/spec_check.py {spec} --vm --project <project>` first (stamp {stamp_path(project, spec)})"
    if not skip:
        raise SystemExit(hint)
    return [f"WARNING: --skip-spec-stamp: building WITHOUT a valid spec stamp ({reason})"]


def check(project, spec, bench=None):
    """(reason, stamp): reason None = the build may start; spec_not_checked (no stamp, unreadable, result not ok) or spec_changed_since_check (a hash differs)."""
    path = stamp_path(project, spec)
    try:
        stamp = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "spec_not_checked", None
    if stamp.get("result") != "ok" or stamp.get("level") not in LEVELS:
        return "spec_not_checked", stamp
    try:
        now = fingerprint(spec, bench)
    except OSError:
        return "spec_not_checked", stamp
    if any(stamp.get(key) != now[key] for key in ("spec_sha256", "ref_sha256", "seed_sha256")):
        return "spec_changed_since_check", stamp
    return None, stamp
