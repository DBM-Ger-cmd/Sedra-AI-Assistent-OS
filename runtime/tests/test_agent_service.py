import os
import shutil
import tempfile
import unittest

from guppi_runtime.agent_manager.service import AgentManager

ARCHIVE = r"C:\Users\<user>\AppData\Local\Temp\claude\C--Users-<user>\f0a5651b-ba8d-432f-be11-58e72b5ca9ea\scratchpad\am\GUPPI_Agent_Manager_Developer_Archive_v1.0\examples\templates"


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = os.path.join(self.tmp.name, "templates")
        os.makedirs(self.folder)
        self.manager = AgentManager(os.path.join(self.tmp.name, "registry.sqlite"))
        self.addCleanup(self.manager.close)

    def write(self, name, yaml_text, soul="# SOUL\n"):
        folder = os.path.join(self.folder, name)
        os.makedirs(folder)
        with open(os.path.join(folder, "template.yaml"), "w", encoding="utf-8", newline="") as f:
            f.write(yaml_text)
        if soul is not None:
            with open(os.path.join(folder, "SOUL.md"), "w", encoding="utf-8", newline="") as f:
                f.write(soul)

    def template(self, sha, extra="", trust="DRAFT", soul_path="SOUL.md"):
        return (f"schema_version: guppi.agent-template/v1\nid: guppi.agent.demo\nversion: 1.0.0\nrole: Demo\nsoul: {{path: {soul_path}, version: 1.0.0, sha256: {sha}}}\n"
                "capabilities: []\ntools: []\npermissions: {tools_allowed: [], workspace_mode: none, network_mode: deny, external_write: false, privileged: false}\n"
                f"initial_qualification: {trust}\n{extra}")

    def sha(self, text="# SOUL\n"):
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def test_good_template_is_registered_unverified_and_import_is_idempotent(self):
        self.write("demo", self.template(self.sha()))
        first = self.manager.import_templates(self.folder)
        self.assertEqual(first, [{"folder": "demo", "key": "guppi.agent.demo@1.0.0", "status": "created", "problems": []}])
        self.assertEqual(self.manager.import_templates(self.folder)[0]["status"], "unchanged")
        listing = self.manager.list_templates()
        self.assertEqual(listing, [{"ref": "guppi.agent.demo@1.0.0", "role": "Demo", "trust": "UNVERIFIED", "ok": True, "problems": []}])

    def test_claimed_trust_is_registered_without_trust(self):
        self.write("demo", self.template(self.sha(), trust="TRUSTED"))
        result = self.manager.import_templates(self.folder)[0]
        self.assertEqual(result["problems"], ["claimed_trust"])
        self.assertEqual(self.manager.get_template(result["key"])["trust"], "UNVERIFIED")
        self.assertFalse(self.manager.list_templates()[0]["ok"])

    def test_tampered_soul_and_missing_soul_are_found(self):
        self.write("tampered", self.template(self.sha("# other\n")))
        self.assertEqual(self.manager.import_templates(self.folder)[0]["problems"], ["soul_hash"])

    def test_traversal_in_soul_path_is_refused_and_never_read(self):
        with open(os.path.join(self.tmp.name, "secret.md"), "w") as f:
            f.write("secret")
        self.write("evil", self.template(self.sha("secret"), soul_path="../../secret.md"), soul=None)
        self.assertEqual(self.manager.import_templates(self.folder)[0]["problems"], ["soul_path"])

    def test_duplicate_keys_and_aliases_are_refused_without_registering(self):
        self.write("dup", self.template(self.sha(), extra="role: Other\n"))
        self.write("alias", self.template(self.sha(), extra="x: &a 1\ny: *a\n"))
        results = {r["folder"]: r for r in self.manager.import_templates(self.folder)}
        self.assertEqual({k: (v["status"], v["problems"]) for k, v in results.items()}, {"dup": ("refused", ["yaml_refused"]), "alias": ("refused", ["yaml_refused"])})
        self.assertEqual(self.manager.list_templates(), [])

    def test_changed_template_is_reported_not_overwritten(self):
        self.write("demo", self.template(self.sha()))
        self.manager.import_templates(self.folder)
        with open(os.path.join(self.folder, "demo", "template.yaml"), "a", encoding="utf-8") as f:
            f.write("tags: [x]\n")
        self.assertEqual(self.manager.import_templates(self.folder)[0]["status"], "changed")
        self.assertNotIn("tags", self.manager.get_template("guppi.agent.demo@1.0.0")["template"])

    def test_promotion_needs_the_declared_suite_every_case_a_review_and_a_decision(self):
        self.write("demo", self.template(self.sha(), extra="verification: {suite_id: calc.demo, suite_version: '1', required_cases: [calc.add, calc.type]}\n"))
        self.manager.import_templates(self.folder)
        ref = "guppi.agent.demo@1.0.0"

        def run(label="suite:calc.demo@1#abcdef123456", **status):
            return {"suite": label, "results": [{"criterion_id": k, "status": v} for k, v in {"calc.add": "PASS", "calc.type": "PASS", **status}.items()]}
        self.assertEqual(self.manager.promotion_gaps(ref, run(), True, True), [])
        self.assertEqual(self.manager.promotion_gaps(ref, run(), False, False), ["guppi_decision_missing", "independent_review_missing"])
        self.assertEqual(self.manager.promotion_gaps(ref, run(**{"calc.type": "FAIL"}), True, True), ["case_not_passed:calc.type"])
        self.assertEqual(self.manager.promotion_gaps(ref, run(**{"calc.add": "ERROR"}), True, True), ["case_not_passed:calc.add"])
        self.assertEqual(self.manager.promotion_gaps(ref, None, True, True), ["suite_not_run"])
        self.assertEqual(self.manager.promotion_gaps(ref, run("suite:other.suite@1#abc"), True, True), ["wrong_suite"])
        self.assertEqual(self.manager.promotion_gaps(ref, run("suite:calc.demo@2#abc"), True, True), ["wrong_suite_version"])
        partial = {"suite": "suite:calc.demo@1#abc", "results": [{"criterion_id": "calc.add", "status": "PASS"}]}
        self.assertEqual(self.manager.promotion_gaps(ref, partial, True, True), ["case_not_passed:calc.type"])
        self.assertEqual(self.manager.promotion_gaps("guppi.agent.nobody@1.0.0", run(), True, True), ["template_unknown"])

    def test_a_template_without_a_declared_suite_cannot_be_promoted(self):
        self.write("demo", self.template(self.sha()))
        self.manager.import_templates(self.folder)
        self.assertEqual(self.manager.promotion_gaps("guppi.agent.demo@1.0.0", {"suite": "x", "results": []}, True, True), ["no_suite_declared"])

    def test_matcher_excludes_unverified_templates_with_reasons(self):
        self.write("demo", self.template(self.sha(), extra="").replace("capabilities: []", "capabilities: [{id: code.write, version: 1.2.0, side_effect: reversible_write}]"))
        self.manager.import_templates(self.folder)
        requirement = {"must": [{"id": "code.write", "minimum_version": "1.0.0"}], "can": [], "min_qualification": "VERIFIED", "effects_allowed": ["reversible_write"]}
        result = self.manager.match_templates(requirement, {"cpu_cores": 4, "ram_mib": 8000})
        self.assertEqual(result["eligible"], [])
        self.assertEqual([e["agent_id"] for e in result["excluded"]], ["guppi.agent.demo@1.0.0"])
        codes = [r["reason_code"] for r in result["excluded"][0]["reasons"]]
        self.assertEqual(codes, ["admission_invalid", "qualification_too_low"])
        self.assertEqual(result["gaps"], [])
        gap = self.manager.match_templates({**requirement, "must": [{"id": "deploy", "minimum_version": "1.0.0"}]}, {})
        self.assertEqual(gap["gaps"], [{"missing_capabilities": ["deploy"]}])

    @unittest.skipUnless(os.path.isdir(ARCHIVE), "archive examples are not on this machine")
    def test_archive_examples(self):
        copy = os.path.join(self.tmp.name, "archive")
        shutil.copytree(ARCHIVE, copy)
        results = self.manager.import_templates(copy)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r["status"] == "created" for r in results), results)
        self.assertTrue(all(t["trust"] == "UNVERIFIED" for t in self.manager.list_templates()))
        print("archive example problems:", {r["folder"]: r["problems"] for r in results})


if __name__ == "__main__":
    unittest.main()
