import json
import os
import tempfile
import unittest

from guppi_runtime.selfdev.acceptance_suite import SuiteError, candidate_hash, evidence_records, host_runner, leak_check, load_suite, run_suite, validate_suite, write_suite
from guppi_runtime.selfdev.development_evidence import DevelopmentEvidenceStore

REFERENCE = {"calc.py": "def add(a, b):\n    return a + b\n"}
CRITERIA = [
    {"id": "calc.add", "description": "add adds", "script": "t_add.py", "text": "from calc import add\nassert add(1, 2) == 3\nassert add(-1, 1) == 0, 'a long enough line that only the hidden script contains: sum of opposites'\n"},
    {"id": "calc.type", "description": "add keeps ints", "script": "t_type.py", "text": "from calc import add\nassert isinstance(add(1, 2), int)\n"},
]
GOOD = REFERENCE
BAD = {"calc.py": "def add(a, b):\n    return a - b\n"}


class SuiteCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "suite")
        self.suite = write_suite(self.root, "calc.demo", "1", CRITERIA, REFERENCE)


class WriteAndLoadTest(SuiteCase):
    def test_roundtrip_keeps_criteria_scripts_and_reference(self):
        loaded = load_suite(self.root)
        self.assertEqual((loaded.suite_id, loaded.version, loaded.digest), ("calc.demo", "1", self.suite.digest))
        self.assertEqual([c["id"] for c in loaded.criteria], ["calc.add", "calc.type"])
        self.assertEqual(loaded.scripts["calc.add"][0], "t_add.py")
        self.assertEqual(loaded.reference, REFERENCE)
        self.assertTrue(loaded.label().startswith("suite:calc.demo@1#"))

    def test_a_changed_script_a_new_file_or_a_new_digest_is_refused(self):
        script = os.path.join(self.root, "criteria", "t_add.py")
        with open(script, encoding="utf-8") as handle:
            original = handle.read()
        with open(script, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(original + "# weakened\n")
        with self.assertRaises(SuiteError) as ctx:
            load_suite(self.root)
        self.assertEqual(ctx.exception.code, "file_changed")
        with open(script, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(original)
        load_suite(self.root)
        extra = os.path.join(self.root, "criteria", "extra.py")
        open(extra, "w").close()
        with self.assertRaises(SuiteError) as ctx:
            load_suite(self.root)
        self.assertEqual(ctx.exception.code, "files_differ")
        os.remove(extra)
        meta_path = os.path.join(self.root, "suite.json")
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
        meta["digest"] = "0" * 64
        with open(meta_path, "w", encoding="utf-8") as handle:
            json.dump(meta, handle)
        with self.assertRaises(SuiteError) as ctx:
            load_suite(self.root)
        self.assertEqual(ctx.exception.code, "digest_mismatch")

    def test_unsafe_names_and_broken_inputs_are_refused_when_writing(self):
        for script in ("../x.py", "a/b.py", "x.txt", "", "1abc.py", "t add.py"):
            with self.assertRaises(SuiteError, msg=script):
                write_suite(os.path.join(self.tmp.name, "s2"), "calc.demo", "1", [{**CRITERIA[0], "script": script}], REFERENCE)
        with self.assertRaises(SuiteError):
            write_suite(os.path.join(self.tmp.name, "s3"), "Bad Id", "1", CRITERIA, REFERENCE)
        with self.assertRaises(SuiteError):
            write_suite(os.path.join(self.tmp.name, "s4"), "calc.demo", "1", [CRITERIA[0], CRITERIA[0]], REFERENCE)
        with self.assertRaises(SuiteError):
            write_suite(os.path.join(self.tmp.name, "s5"), "calc.demo", "1", CRITERIA, {"../evil.py": ""})
        with self.assertRaises(SuiteError) as ctx:
            load_suite(os.path.join(self.tmp.name, "missing"))
        self.assertEqual(ctx.exception.code, "suite_unreadable")


class RunTest(SuiteCase):
    def test_every_criterion_gets_its_script_and_the_candidate_files(self):
        seen = []

        def runner(files, commands):
            seen.append((sorted(files), commands))
            return {"status": "completed", "output": "ok"}
        run = run_suite(self.suite, GOOD, runner)
        self.assertTrue(run["passed"])
        self.assertEqual(seen[0], (["calc.py", "t_add.py"], [["python3", "t_add.py"]]))
        self.assertEqual(seen[1][0], ["calc.py", "t_type.py"])

    def test_status_mapping_failed_means_fail_and_anything_else_means_error(self):
        statuses = iter([{"status": "completed", "output": ""}, {"status": "failed", "output": "AssertionError"}])
        run = run_suite(self.suite, GOOD, lambda f, c: next(statuses))
        self.assertEqual([r["status"] for r in run["results"]], ["PASS", "FAIL"]); self.assertFalse(run["passed"])
        run = run_suite(self.suite, GOOD, lambda f, c: {"status": "timeout", "output": "x"})
        self.assertEqual([r["status"] for r in run["results"]], ["ERROR", "ERROR"])

    def test_candidate_hash_ignores_order_and_follows_content(self):
        a = candidate_hash({"x.py": "1", "y.py": "2"})
        self.assertEqual(a, candidate_hash({"y.py": "2", "x.py": "1"}))
        self.assertNotEqual(a, candidate_hash({"x.py": "1", "y.py": "3"}))
        self.assertNotEqual(a, candidate_hash({"x.py": "1", "z.py": "2"}))


class ValidateTest(SuiteCase):
    def test_the_reference_passes_its_own_suite(self):
        report = validate_suite(self.suite, host_runner())
        self.assertEqual((report["ok"], report["problems"]), (True, []))

    def test_a_suite_that_its_reference_fails_is_invalid(self):
        wrong = write_suite(os.path.join(self.tmp.name, "wrong"), "calc.wrong", "1", CRITERIA, BAD)
        report = validate_suite(wrong, host_runner())
        self.assertFalse(report["ok"])
        self.assertEqual(report["problems"], ["reference_fails:calc.add"])

    def test_a_candidate_is_judged_by_the_same_scripts(self):
        runner = host_runner()
        self.assertTrue(run_suite(self.suite, GOOD, runner)["passed"])
        run = run_suite(self.suite, BAD, runner)
        self.assertEqual([r["status"] for r in run["results"]], ["FAIL", "PASS"])
        self.assertIn("AssertionError", run["results"][0]["output_tail"])


class LeakTest(SuiteCase):
    def test_long_lines_of_the_hidden_scripts_are_found_in_other_texts(self):
        leaked = "prompt: please make sure that  assert add(-1, 1) == 0, 'a long enough line that only the hidden script contains: sum of opposites'  works"
        found = leak_check(self.suite, {"prompt.txt": leaked, "clean.txt": "write add(a, b) returning the sum"})
        self.assertEqual([(f["source"], f["criterion_id"]) for f in found], [("prompt.txt", "calc.add")])

    def test_short_lines_and_imports_are_not_leaks(self):
        self.assertEqual(leak_check(self.suite, {"w.txt": "from calc import add\nassert add(1, 2) == 3\nassert isinstance(add(1, 2), int)"}), [])


class EvidenceTest(SuiteCase):
    def job(self, files):
        return {"job_id": "JOB-1", "candidate": {"candidate_id": "CAND-1", "candidate_hash": candidate_hash(files)}}

    def test_one_deterministic_record_per_criterion_bound_to_the_candidate_hash(self):
        store = DevelopmentEvidenceStore(os.path.join(self.tmp.name, "evidence.jsonl"))
        run = run_suite(self.suite, BAD, host_runner())
        ids = evidence_records(store, self.job(BAD), run)
        records = store.list("JOB-1")
        self.assertEqual(len(ids), 2)
        self.assertEqual([(r["payload"]["criterion_id"], r["payload"]["status"]) for r in records], [("calc.add", "FAIL"), ("calc.type", "PASS")])
        self.assertTrue(all(r["trust_level"] == "deterministic" and r["artifact_sha256"] == candidate_hash(BAD) and r["candidate_id"] == "CAND-1" for r in records))
        self.assertIn(self.suite.digest[:12], records[0]["source_ref"])
        self.assertTrue(store.verify_chain())

    def test_evidence_for_other_files_than_the_candidate_is_refused(self):
        store = DevelopmentEvidenceStore(os.path.join(self.tmp.name, "evidence.jsonl"))
        run = run_suite(self.suite, GOOD, host_runner())
        with self.assertRaises(SuiteError) as ctx:
            evidence_records(store, self.job(BAD), run)
        self.assertEqual(ctx.exception.code, "candidate_hash_mismatch")
        self.assertEqual(store.list("JOB-1"), [])


if __name__ == "__main__":
    unittest.main()
