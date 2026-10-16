import unittest

from self_diagnosis import (GIB, chain_findings, diagnose, disk_findings, gpu_driver_findings, job_findings, mission_findings,
                            path_findings)


def f(id_, severity, area, detail):
    return {"id": id_, "severity": severity, "area": area, "detail": detail}


class Chains(unittest.TestCase):
    def test_broken_unchecked_and_intact(self):
        self.assertEqual(chain_findings({"evidence": None, "audit": False, "other": True}), [
            f("audit_chain_broken", "CRITICAL", "integrity", "hash chain does not verify"),
            f("evidence_chain_unchecked", "INFO", "integrity", "not checked")])
        self.assertEqual(chain_findings({}), [])


class Missions(unittest.TestCase):
    def test_each_kind(self):
        missions = [{"mission_id": "M-1", "phase": "REWORK", "status": "waiting_captain"},
                    {"mission_id": "M-2", "phase": "REWORK", "status": "active"},
                    {"mission_id": "M-3", "phase": "CAPTAIN_REVIEW", "status": "active"},
                    {"mission_id": "M-4", "phase": "PAUSED", "status": "blocked"},
                    {"mission_id": "M-5", "phase": "CANDIDATE_REVIEW", "status": "active"},
                    {"mission_id": "M-6", "phase": "COMPLETE", "status": "closed"}]
        self.assertEqual(mission_findings(missions), [
            f("mission_waiting_for_captain", "WARNING", "missions", "M-1"),
            f("mission_waiting_for_captain", "WARNING", "missions", "M-3"),
            f("mission_paused", "WARNING", "missions", "M-4"),
            f("candidate_open", "INFO", "missions", "M-5")])


class Jobs(unittest.TestCase):
    def test_dead_and_blocked(self):
        jobs = [{"job_id": "SDJ-A", "state": "BLOCKED"}, {"job_id": "SDJ-B", "state": "ACTIVATED"}, {"job_id": "SDJ-C", "state": "DEAD"}]
        self.assertEqual(job_findings(jobs), [f("job_blocked", "WARNING", "jobs", "SDJ-A"), f("job_dead", "CRITICAL", "jobs", "SDJ-C")])


class Gpu(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(gpu_driver_findings(0, 0), [])
        self.assertEqual(gpu_driver_findings(0, 9), [])
        self.assertEqual(gpu_driver_findings(0, 10), [f("gpu_driver_errors", "WARNING", "gpu", "0 in 24h, 10 in 7d")])
        self.assertEqual(gpu_driver_findings(1, 1), [f("gpu_driver_errors", "WARNING", "gpu", "1 in 24h, 1 in 7d")])
        self.assertEqual(gpu_driver_findings(50, 446), [f("gpu_driver_errors", "CRITICAL", "gpu", "50 in 24h, 446 in 7d")])

    def test_unreadable_log(self):
        for pair in ((None, 3), (3, None), (None, None)):
            self.assertEqual(gpu_driver_findings(*pair), [f("gpu_driver_log_unreadable", "INFO", "gpu", "not checked")])


class Disk(unittest.TestCase):
    def test_free_space_levels(self):
        self.assertEqual(disk_findings(int(8.5 * GIB), None), [f("disk_space_low", "CRITICAL", "disk", "8.5 GiB free")])
        self.assertEqual(disk_findings(20 * GIB, None), [f("disk_space_low", "WARNING", "disk", "20.0 GiB free")])
        self.assertEqual(disk_findings(30 * GIB, 5 * GIB), [])

    def test_large_runtime_data_after_low_space(self):
        self.assertEqual(disk_findings(5 * GIB, 6 * GIB), [f("disk_space_low", "CRITICAL", "disk", "5.0 GiB free"),
                                                           f("runtime_data_large", "WARNING", "disk", "6.0 GiB in runtime_data")])
        self.assertEqual(disk_findings(None, None), [])


class Paths(unittest.TestCase):
    def test_capability_result(self):
        ok = {"status": "OK", "vm_path": {"longest": 197, "limit": 260, "spare": 62, "ok": True}, "stale_missions": [], "actions": []}
        self.assertEqual(path_findings(ok), [])
        bad = {"status": "ATTENTION", "vm_path": {"longest": 262, "limit": 260, "spare": -3, "ok": False},
               "stale_missions": ["M-9", "M-2"], "actions": ["shorten_project_path", "regenerate_candidates"]}
        self.assertEqual(path_findings(bad), [f("vm_path_too_long", "CRITICAL", "paths", "262 of 259 characters"),
                                              f("stale_candidate", "WARNING", "paths", "M-9"),
                                              f("stale_candidate", "WARNING", "paths", "M-2")])

    def test_unavailable(self):
        self.assertEqual(path_findings(None), [f("path_health_unavailable", "INFO", "paths", "missing")])
        self.assertEqual(path_findings({"status": "ERROR", "reason": "x"}), [f("path_health_unavailable", "INFO", "paths", "ERROR")])


class Diagnose(unittest.TestCase):
    def test_empty_facts_are_ok_but_say_what_was_not_checked(self):
        out = diagnose({})
        self.assertEqual(out["status"], "OK")
        self.assertEqual([x["id"] for x in out["findings"]], ["gpu_driver_log_unreadable", "path_health_unavailable"])
        self.assertEqual(out["counts"], {"CRITICAL": 0, "WARNING": 0, "INFO": 2})

    def test_sorted_by_severity_then_check_order(self):
        facts = {"chains": {"audit": True, "evidence": True},
                 "missions": [{"mission_id": "M-1", "phase": "CANDIDATE_REVIEW", "status": "active"},
                              {"mission_id": "M-2", "phase": "PAUSED", "status": "blocked"}],
                 "jobs": [{"job_id": "SDJ-D", "state": "DEAD"}],
                 "gpu_events_24h": 8, "gpu_events_7d": 8,
                 "free_bytes": 100 * GIB, "runtime_data_bytes": 1 * GIB,
                 "path_health": {"status": "ATTENTION", "vm_path": {"longest": 197, "limit": 260, "spare": 62, "ok": True},
                                 "stale_missions": ["M-7"], "actions": ["regenerate_candidates"]}}
        out = diagnose(facts)
        self.assertEqual(out["status"], "CRITICAL")
        self.assertEqual([(x["severity"], x["id"]) for x in out["findings"]], [
            ("CRITICAL", "job_dead"), ("WARNING", "mission_paused"), ("WARNING", "gpu_driver_errors"),
            ("WARNING", "stale_candidate"), ("INFO", "candidate_open")])
        self.assertEqual(out["counts"], {"CRITICAL": 1, "WARNING": 3, "INFO": 1})

    def test_warning_status(self):
        out = diagnose({"gpu_events_24h": 0, "gpu_events_7d": 0, "free_bytes": 20 * GIB,
                        "path_health": {"status": "OK", "vm_path": {"longest": 1, "limit": 260, "spare": 258, "ok": True},
                                        "stale_missions": [], "actions": []}})
        self.assertEqual((out["status"], [x["id"] for x in out["findings"]]), ("WARNING", ["disk_space_low"]))


if __name__ == "__main__":
    unittest.main()
