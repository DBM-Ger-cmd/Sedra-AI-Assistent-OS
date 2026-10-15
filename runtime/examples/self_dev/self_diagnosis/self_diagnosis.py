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
    raise NotImplementedError


def mission_findings(missions):
    """`missions` is a list of {"mission_id", "phase", "status"}.
    - phase "REWORK" with status "waiting_captain", or phase "CAPTAIN_REVIEW": WARNING id "mission_waiting_for_captain",
      area "missions", detail = the mission_id.
    - phase "PAUSED": WARNING id "mission_paused", area "missions", detail = the mission_id.
    - phase "CANDIDATE_REVIEW": INFO id "candidate_open", area "missions", detail = the mission_id.
    Anything else: nothing. One finding per mission at most, in the order the missions are given."""
    raise NotImplementedError


def job_findings(jobs):
    """`jobs` is a list of {"job_id", "state"}. state "DEAD": CRITICAL id "job_dead"; state "BLOCKED": WARNING id "job_blocked";
    area "jobs", detail = the job_id. Anything else: nothing. In the order the jobs are given."""
    raise NotImplementedError


def gpu_driver_findings(events_last_24h, events_last_7d):
    """Counts of NVIDIA driver error events (Windows log nvlddmkm 13/153). Ints, or None when they could not be read.
    - either count is None: INFO id "gpu_driver_log_unreadable", area "gpu", detail "not checked".
    - events_last_24h >= 50: CRITICAL id "gpu_driver_errors", area "gpu".
    - events_last_24h >= 1, or events_last_7d >= 10: WARNING id "gpu_driver_errors", area "gpu".
    - otherwise nothing.
    The detail of "gpu_driver_errors" is exactly "<events_last_24h> in 24h, <events_last_7d> in 7d"."""
    raise NotImplementedError


def disk_findings(free_bytes, runtime_data_bytes):
    """Ints (bytes), or None when unknown (then that rule is skipped).
    - free_bytes < 10 GiB: CRITICAL id "disk_space_low"; free_bytes < 30 GiB: WARNING id "disk_space_low".
      Detail "<free GiB rounded to 1 decimal> GiB free" (e.g. "8.5 GiB free").
    - runtime_data_bytes > 5 GiB: WARNING id "runtime_data_large", detail "<GiB rounded to 1 decimal> GiB in runtime_data".
    Area "disk" for both. disk_space_low comes first."""
    raise NotImplementedError


def path_findings(path_health):
    """`path_health` is the dict of GUPPI's path_health capability, or None.
    - None, or a dict whose "status" is not "OK"/"ATTENTION": INFO id "path_health_unavailable", area "paths",
      detail = its "status" (or "missing" for None).
    - vm_path.ok is False: CRITICAL id "vm_path_too_long", area "paths", detail "<longest> of <limit - 1> characters".
    - one WARNING id "stale_candidate", area "paths", detail = mission_id, for each entry of stale_missions (in that order)."""
    raise NotImplementedError


def diagnose(facts):
    """All checks together. `facts` keys (each may be missing): "chains", "missions", "jobs", "gpu_events_24h",
    "gpu_events_7d", "free_bytes", "runtime_data_bytes", "path_health". A missing list counts as empty, a missing chains dict
    as {}, a missing number as None, a missing path_health as None.

    Returns {"status": "CRITICAL" | "WARNING" | "OK", "findings": [...], "counts": {"CRITICAL": n, "WARNING": n, "INFO": n}}.
    findings are sorted by severity (CRITICAL, WARNING, INFO) and, within a severity, keep the order in which the checks
    produced them (chains, missions, jobs, gpu, disk, paths). status is the most severe one present; INFO alone is "OK"."""
    raise NotImplementedError
