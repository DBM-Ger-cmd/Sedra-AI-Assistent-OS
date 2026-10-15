"""GUPPI self-diagnosis: turn collected facts into findings. Pure: no files, no processes, no clock; only the standard library.

The caller collects the facts (see `diagnose`) and passes them in; this module only judges them. Every rule below comes from
a real problem on the Captain's PC on 2026-10-02.

A finding is a dict {"id": str, "severity": "CRITICAL" | "WARNING" | "INFO", "area": str, "detail": str}.
"""

GIB = 1024 ** 3
SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def chain_findings(chains):
    """`chains` maps a chain name ("audit", "evidence") to True (intact), False (broken) or None (not checked).
    Broken -> CRITICAL finding id "<name>_chain_broken", area "integrity", detail "hash chain does not verify".
    None -> INFO finding id "<name>_chain_unchecked", area "integrity", detail "not checked". True -> nothing.
    Findings in the order of sorted chain names."""
    findings = []
    for name in sorted(chains):
        val = chains[name]
        if val is False:
            findings.append({"id": f"{name}_chain_broken", "severity": "CRITICAL", "area": "integrity", "detail": "hash chain does not verify"})
        elif val is None:
            findings.append({"id": f"{name}_chain_unchecked", "severity": "INFO", "area": "integrity", "detail": "not checked"})
    return findings


def mission_findings(missions):
    """`missions` is a list of {"mission_id", "phase", "status"}.
    - phase "REWORK" with status "waiting_captain", or phase "CAPTAIN_REVIEW": WARNING id "mission_waiting_for_captain",
      area "missions", detail = the mission_id.
    - phase "PAUSED": WARNING id "mission_paused", area "missions", detail = the mission_id.
    - phase "CANDIDATE_REVIEW": INFO id "candidate_open", area "missions", detail = the mission_id.
    Anything else: nothing. One finding per mission at most, in the order the missions are given."""
    findings = []
    for m in missions:
        phase = m.get("phase")
        status = m.get("status")
        mission_id = m.get("mission_id")
        if phase == "REWORK" and status == "waiting_captain" or phase == "CAPTAIN_REVIEW":
            findings.append({"id": "mission_waiting_for_captain", "severity": "WARNING", "area": "missions", "detail": mission_id})
        elif phase == "PAUSED":
            findings.append({"id": "mission_paused", "severity": "WARNING", "area": "missions", "detail": mission_id})
        elif phase == "CANDIDATE_REVIEW":
            findings.append({"id": "candidate_open", "severity": "INFO", "area": "missions", "detail": mission_id})
    return findings


def job_findings(jobs):
    """`jobs` is a list of {"job_id", "state"}. state "DEAD": CRITICAL id "job_dead"; state "BLOCKED": WARNING id "job_blocked";
    area "jobs", detail = the job_id. Anything else: nothing. In the order the jobs are given."""
    findings = []
    for j in jobs:
        state = j.get("state")
        job_id = j.get("job_id")
        if state == "DEAD":
            findings.append({"id": "job_dead", "severity": "CRITICAL", "area": "jobs", "detail": job_id})
        elif state == "BLOCKED":
            findings.append({"id": "job_blocked", "severity": "WARNING", "area": "jobs", "detail": job_id})
    return findings


def gpu_driver_findings(events_last_24h, events_last_7d):
    """Counts of NVIDIA driver error events (Windows log nvlddmkm 13/153). Ints, or None when they could not be read.
    - either count is None: INFO id "gpu_driver_log_unreadable", area "gpu", detail "not checked".
    - events_last_24h >= 50: CRITICAL id "gpu_driver_errors", area "gpu".
    - events_last_24h >= 1, or events_last_7d >= 10: WARNING id "gpu_driver_errors", area "gpu".
    - otherwise nothing.
    The detail of "gpu_driver_errors" is exactly "<events_last_24h> in 24h, <events_last_7d> in 7d"."""
    if events_last_24h is None or events_last_7d is None:
        return [{"id": "gpu_driver_log_unreadable", "severity": "INFO", "area": "gpu", "detail": "not checked"}]
    detail = f"{events_last_24h} in 24h, {events_last_7d} in 7d"
    if events_last_24h >= 50:
        return [{"id": "gpu_driver_errors", "severity": "CRITICAL", "area": "gpu", "detail": detail}]
    if events_last_24h >= 1 or events_last_7d >= 10:
        return [{"id": "gpu_driver_errors", "severity": "WARNING", "area": "gpu", "detail": detail}]
    return []


def disk_findings(free_bytes, runtime_data_bytes):
    """Ints (bytes), or None when unknown (then that rule is skipped).
    - free_bytes < 10 GiB: CRITICAL id "disk_space_low"; free_bytes < 30 GiB: WARNING id "disk_space_low".
      Detail "<free GiB rounded to 1 decimal> GiB free" (e.g. "8.5 GiB free").
    - runtime_data_bytes > 5 GiB: WARNING id "runtime_data_large", detail "<GiB rounded to 1 decimal> GiB in runtime_data".
    Area "disk" for both. disk_space_low comes first."""
    findings = []
    if free_bytes is not None:
        free_gib = free_bytes / GIB
        rounded = round(free_gib, 1)
        detail = f"{rounded:.1f} GiB free"
        if free_bytes < 10 * GIB:
            findings.append({"id": "disk_space_low", "severity": "CRITICAL", "area": "disk", "detail": detail})
        elif free_bytes < 30 * GIB:
            findings.append({"id": "disk_space_low", "severity": "WARNING", "area": "disk", "detail": detail})
    if runtime_data_bytes is not None and runtime_data_bytes > 5 * GIB:
        runtime_gib = runtime_data_bytes / GIB
        rounded = round(runtime_gib, 1)
        detail = f"{rounded:.1f} GiB in runtime_data"
        findings.append({"id": "runtime_data_large", "severity": "WARNING", "area": "disk", "detail": detail})
    return findings


def path_findings(path_health):
    """`path_health` is the dict of GUPPI's path_health capability, or None.
    - None, or a dict whose "status" is not "OK"/"ATTENTION": INFO id "path_health_unavailable", area "paths",
      detail = its "status" (or "missing" for None).
    - vm_path.ok is False: CRITICAL id "vm_path_too_long", area "paths", detail "<longest> of <limit - 1> characters".
    - one WARNING id "stale_candidate", area "paths", detail = mission_id, for each entry of stale_missions (in that order)."""
    findings = []
    if path_health is None:
        findings.append({"id": "path_health_unavailable", "severity": "INFO", "area": "paths", "detail": "missing"})
        return findings
    status = path_health.get("status")
    if status not in ("OK", "ATTENTION"):
        findings.append({"id": "path_health_unavailable", "severity": "INFO", "area": "paths", "detail": status})
        return findings
    vm_path = path_health.get("vm_path", {})
    if not vm_path.get("ok", True):
        longest = vm_path.get("longest", 0)
        limit = vm_path.get("limit", 0)
        detail = f"{longest} of {limit - 1} characters"
        findings.append({"id": "vm_path_too_long", "severity": "CRITICAL", "area": "paths", "detail": detail})
    stale = path_health.get("stale_missions", [])
    for mission_id in stale:
        findings.append({"id": "stale_candidate", "severity": "WARNING", "area": "paths", "detail": mission_id})
    return findings


def diagnose(facts):
    """All checks together. `facts` keys (each may be missing): "chains", "missions", "jobs", "gpu_events_24h",
    "gpu_events_7d", "free_bytes", "runtime_data_bytes", "path_health". A missing list counts as empty, a missing chains dict
    as {}, a missing number as None, a missing path_health as None.

    Returns {"status": "CRITICAL" | "WARNING" | "OK", "findings": [...], "counts": {"CRITICAL": n, "WARNING": n, "INFO": n}}.
    findings are sorted by severity (CRITICAL, WARNING, INFO) and, within a severity, keep the order in which the checks
    produced them (chains, missions, jobs, gpu, disk, paths). status is the most severe one present; INFO alone is "OK"."""
    # Extract facts with defaults
    chains = facts.get("chains", {}) or {}
    missions = facts.get("missions", []) or []
    jobs = facts.get("jobs", []) or []
    gpu_24h = facts.get("gpu_events_24h")
    gpu_7d = facts.get("gpu_events_7d")
    free_bytes = facts.get("free_bytes")
    runtime_data_bytes = facts.get("runtime_data_bytes")
    path_health = facts.get("path_health")

    # Gather findings in check order
    findings = []
    findings.extend(chain_findings(chains))
    findings.extend(mission_findings(missions))
    findings.extend(job_findings(jobs))
    findings.extend(gpu_driver_findings(gpu_24h, gpu_7d))
    findings.extend(disk_findings(free_bytes, runtime_data_bytes))
    findings.extend(path_findings(path_health))

    # Sort by severity while preserving relative order within same severity
    findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 3))

    # Compute status and counts
    counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    for f in findings:
        counts[f["severity"]] += 1
    if counts["CRITICAL"] > 0:
        status = "CRITICAL"
    elif counts["WARNING"] > 0:
        status = "WARNING"
    else:
        status = "OK"

    return {"status": status, "findings": findings, "counts": counts}
