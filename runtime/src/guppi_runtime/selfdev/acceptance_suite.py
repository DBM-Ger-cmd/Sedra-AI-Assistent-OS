"""Acceptance suites: hidden tests as a fixed part of GUPPI (Captain 2026-10-07, after the AM builds).

A suite is a folder OUTSIDE every model workspace:

    <root>/suite.json            id, version, criteria, the SHA-256 of every file, and the digest of all of it
    <root>/criteria/<script>.py  one hidden test script per criterion (the models never see it)
    <root>/reference/<file>.py   an independent reference implementation that must pass every criterion

Rules that keep it honest:
  * `load_suite` refuses a suite whose files or digest do not match, unlisted files and unsafe names. A changed suite is a different digest, so old evidence stops counting.
  * `validate_suite` runs the reference through the suite; a suite that its own reference fails is wrong, not the candidate (three counting mistakes of 2026-10-07 were found this way).
  * `leak_check` looks for lines of the hidden scripts in prompts, transcripts and workspace files.
  * `run_suite` runs a CANDIDATE through a runner that must be the microVM judge; the host runner below is only for trusted reference code.
  * `evidence_records` writes one deterministic PASS/FAIL record per criterion into the evidence chain, bound to the candidate hash, for the verification gate.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

from ..verification_gate import record_check

SUITE_FILE = "suite.json"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\.py")
SUITE_ID = re.compile(r"[a-z][a-z0-9_.\-]{2,63}")
CRITERION_ID = re.compile(r"[a-z][a-z0-9_.\-]{0,63}")
MAX_FILE_BYTES = 262144
MAX_FILES = 60


class SuiteError(ValueError):
    def __init__(self, code, message=""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(files):
    return _sha("".join(f"{path}\0{files[path]}\n" for path in sorted(files)).encode("utf-8"))


def candidate_hash(files):
    return _digest({name: _sha(text.encode("utf-8")) for name, text in files.items()})


class Suite:
    def __init__(self, suite_id, version, criteria, scripts, reference, digest):
        self.suite_id, self.version, self.criteria, self.scripts, self.reference, self.digest = suite_id, version, criteria, scripts, reference, digest

    def label(self):
        return f"suite:{self.suite_id}@{self.version}#{self.digest[:12]}"


def _safe_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise SuiteError("bad_name", repr(name))


def write_suite(root, suite_id, version, criteria, reference):
    """criteria: [{"id", "description", "script", "text"}]; reference: {file name: text}. Writes the folder and returns the loaded suite."""
    if not isinstance(suite_id, str) or not SUITE_ID.fullmatch(suite_id):
        raise SuiteError("bad_suite_id")
    ids = [c["id"] for c in criteria]
    if not criteria or len(set(ids)) != len(ids) or not all(isinstance(i, str) and CRITERION_ID.fullmatch(i) for i in ids):
        raise SuiteError("bad_criteria")
    files = {}
    for criterion in criteria:
        _safe_name(criterion["script"])
        files["criteria/" + criterion["script"]] = criterion["text"]
    for name, text in reference.items():
        _safe_name(name)
        files["reference/" + name] = text
    if len(files) > MAX_FILES or any(len(t.encode("utf-8")) > MAX_FILE_BYTES for t in files.values()):
        raise SuiteError("too_large")
    for path, text in files.items():
        target = os.path.join(root, *path.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    hashes = {path: _sha(text.encode("utf-8")) for path, text in files.items()}
    meta = {"schema": 1, "suite_id": suite_id, "version": str(version), "criteria": [{"id": c["id"], "description": str(c.get("description", ""))[:300], "script": c["script"]} for c in criteria],
            "files": hashes, "digest": _digest(hashes)}
    with open(os.path.join(root, SUITE_FILE), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(meta, handle, indent=1, sort_keys=True)
    return load_suite(root)


def load_suite(root):
    try:
        with open(os.path.join(root, SUITE_FILE), encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        raise SuiteError("suite_unreadable") from None
    if not isinstance(meta, dict) or meta.get("schema") != 1 or not isinstance(meta.get("files"), dict) or not isinstance(meta.get("criteria"), list):
        raise SuiteError("suite_malformed")
    on_disk = set()
    for folder in ("criteria", "reference"):
        directory = os.path.join(root, folder)
        for name in (os.listdir(directory) if os.path.isdir(directory) else []):
            on_disk.add(f"{folder}/{name}")
    if on_disk != set(meta["files"]):
        raise SuiteError("files_differ", ", ".join(sorted(on_disk ^ set(meta["files"])))[:200])
    texts = {}
    for path, expected in meta["files"].items():
        folder, _, name = path.partition("/")
        if folder not in ("criteria", "reference"):
            raise SuiteError("bad_path", path)
        _safe_name(name)
        with open(os.path.join(root, folder, name), "rb") as handle:
            raw = handle.read()
        if len(raw) > MAX_FILE_BYTES or _sha(raw) != expected:
            raise SuiteError("file_changed", path)
        texts[path] = raw.decode("utf-8")
    if _digest(meta["files"]) != meta.get("digest"):
        raise SuiteError("digest_mismatch")
    criteria, scripts = [], {}
    for criterion in meta["criteria"]:
        if not isinstance(criterion, dict) or not CRITERION_ID.fullmatch(str(criterion.get("id"))) or "criteria/" + str(criterion.get("script")) not in texts:
            raise SuiteError("bad_criterion", str(criterion)[:80])
        criteria.append(criterion)
        scripts[criterion["id"]] = (criterion["script"], texts["criteria/" + criterion["script"]])
    reference = {path.split("/", 1)[1]: text for path, text in texts.items() if path.startswith("reference/")}
    return Suite(meta["suite_id"], meta["version"], criteria, scripts, reference, meta["digest"])


def suite_from_stages(stages, criterion_prefix):
    """The stage lists of benchmarks/devvm_specs become criteria: one per hidden script, named after the stage."""
    criteria = []
    for stage in stages:
        for script, text in stage["hidden"].items():
            criteria.append({"id": f"{criterion_prefix}.{stage['name']}", "description": " ".join(stage["task"].split())[:300], "script": script, "text": text})
    return criteria


def host_runner(timeout=120):
    """Runs files with the host's Python. ONLY for trusted code (a reference implementation written by the Captain or Claude); a candidate built by a model must go through the microVM judge."""
    def run(files, commands):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in files.items():
                with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)
            outputs, status = [], "completed"
            for command in commands:
                argv = [sys.executable if command[0] in ("python3", "python") else command[0]] + list(command[1:])
                try:
                    done = subprocess.run(argv, cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
                except subprocess.TimeoutExpired:
                    return {"status": "failed", "output": "timeout"}
                outputs.append(done.stdout + done.stderr)
                if done.returncode != 0:
                    status = "failed"
                    break
            return {"status": status, "output": "\n".join(outputs)}
    return run


def run_suite(suite, candidate_files, runner):
    """Runs every criterion against the candidate files ({name: text}); runner(files, commands) -> {"status", "output"}."""
    results = []
    for criterion in suite.criteria:
        script, text = suite.scripts[criterion["id"]]
        outcome = runner({**candidate_files, script: text}, [["python3", script]])
        status = "PASS" if outcome.get("status") == "completed" else ("FAIL" if outcome.get("status") == "failed" else "ERROR")
        results.append({"criterion_id": criterion["id"], "status": status, "output_tail": str(outcome.get("output", ""))[-600:]})
    return {"suite": suite.label(), "suite_digest": suite.digest, "candidate_hash": candidate_hash(candidate_files), "results": results, "passed": all(r["status"] == "PASS" for r in results)}


def validate_suite(suite, runner):
    """A suite is valid only when its own reference passes every criterion."""
    run = run_suite(suite, suite.reference, runner)
    problems = [f"reference_fails:{r['criterion_id']}" for r in run["results"] if r["status"] != "PASS"]
    return {"ok": not problems, "problems": problems, "run": run}


def leak_check(suite, texts, min_length=40):
    """Lines of the hidden scripts that appear in `texts` ({source name: text}): prompts, transcripts, workspace files. Short lines and plain imports do not count."""
    squeeze = lambda value: re.sub(r"\s+", " ", value).strip()
    haystacks = {name: squeeze(text) for name, text in texts.items()}
    found = []
    for criterion_id, (script, text) in suite.scripts.items():
        for line in text.splitlines():
            probe = squeeze(line)
            if len(probe) < min_length or probe.startswith(("import ", "from ")):
                continue
            for source, haystack in haystacks.items():
                if probe in haystack:
                    found.append({"source": source, "criterion_id": criterion_id, "line": probe[:120]})
    return found


def evidence_records(store, job, run):
    """One deterministic record per criterion in the evidence chain, bound to the job's candidate hash; the check reference names the suite and its digest."""
    expected = (job.get("candidate") or {}).get("candidate_hash")
    if not expected or expected != run["candidate_hash"]:
        raise SuiteError("candidate_hash_mismatch", "the run was made for other files than the job's candidate")
    ids = []
    for result in run["results"]:
        status = "PASS" if result["status"] == "PASS" else "FAIL"
        record = record_check(store, job, criterion_id=result["criterion_id"], status=status, check=f"{run['suite']}:{result['criterion_id']}",
                              detail={"suite_digest": run["suite_digest"], "run_status": result["status"], "output_tail": result["output_tail"][-300:]})
        ids.append(record["evidence_id"])
    return ids
