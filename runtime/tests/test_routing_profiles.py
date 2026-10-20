import tempfile
import unittest
from pathlib import Path

from guppi_runtime.models.routing_profiles import ProfileError, RoutingProfiles
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

GOOD = """# comment kept
active: a
profiles:
  a:
    description: first
    coder: {prefer: [c.one]}
    rework: {prefer: [c.two], reasoning_effort: medium, temperature: 1.0}
  b:
    coder: {prefer: [c.two, c.one]}
"""


class Profiles(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.path = Path(t.name) / "routing_profiles.yaml"
        self.path.write_text(GOOD, encoding="utf-8")

    def test_active_profile_gives_preferences_and_sampling(self):
        p = RoutingProfiles.load(self.path, known_ids={"c.one", "c.two"})
        self.assertEqual(p.prefer("coder"), ["c.one"])
        self.assertEqual(p.purpose("rework"), {"prefer": ["c.two"], "reasoning_effort": "medium", "temperature": 1.0})
        self.assertEqual(p.prefer("verifier"), [])

    def test_use_switches_and_keeps_the_rest_of_the_file(self):
        p = RoutingProfiles.load(self.path)
        p.use("b")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("active: b", text); self.assertIn("# comment kept", text)
        self.assertEqual(RoutingProfiles.load(self.path).prefer("coder"), ["c.two", "c.one"])
        with self.assertRaises(ProfileError):
            p.use("nope")

    def test_missing_file_means_no_profile(self):
        p = RoutingProfiles.load(self.path.parent / "absent.yaml")
        self.assertIsNone(p.active); self.assertEqual(p.prefer("coder"), [])

    def test_invalid_files_are_refused(self):
        for bad in ({"active": "x", "profiles": {}}, {"profiles": {"Bad Name": {}}}, {"extra": 1},
                    {"profiles": {"a": {"coder": {"prefer": "c.one"}}}}, {"profiles": {"a": {"coder": {"prefer": ["c"], "x": 1}}}},
                    {"profiles": {"a": {"rework": {"temperature": 3}}}}, {"profiles": {"a": {"rework": {"reasoning_effort": "max"}}}}):
            with self.assertRaises(ProfileError, msg=str(bad)):
                RoutingProfiles(bad)
        with self.assertRaises(ProfileError):
            RoutingProfiles({"profiles": {"a": {"coder": {"prefer": ["c.unknown"]}}}}, known_ids={"c.one"})


if __name__ == "__main__":
    unittest.main()
