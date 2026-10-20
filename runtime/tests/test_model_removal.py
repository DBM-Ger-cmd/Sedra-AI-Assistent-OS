import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.models.model_removal import QUARANTINE, RemovalError, preview, remove, restore
from guppi_runtime.models.routing_profiles import RoutingProfiles
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

OVERLAY = """role_routing:
  enabled: true
  capabilities:
    - id: coder.a
      version: 1
      profile:
        server: {{gguf: '{a}'}}
    - id: coder.b
      version: 1
      profile:
        server: {{gguf: '{b}', mmproj: '{m}'}}
"""


class Removal(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        base = Path(t.name)
        self.project, self.models = base / "project", base / "models"
        (self.project / "local_config").mkdir(parents=True)
        for rel in ("x/a.gguf", "y/b.gguf", "y/mmproj.gguf"):
            p = self.models / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"w" * 100)
        self.a, self.b, self.m = (str(self.models / r) for r in ("x/a.gguf", "y/b.gguf", "y/mmproj.gguf"))
        (self.project / "local_config" / "role_routing.yaml").write_text(OVERLAY.format(a=self.a, b=self.b, m=self.m), encoding="utf-8")

    def enabled(self):
        caps = yaml.safe_load((self.project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]
        return {c["id"]: c.get("enabled", True) for c in caps}

    def test_preview_finds_files_users_and_profiles(self):
        profiles = RoutingProfiles({"active": "p", "profiles": {"p": {"coder": {"prefer": ["coder.b"]}}}})
        plan = preview(self.project, ["coder.b"], models_root=self.models, profiles=profiles)
        self.assertEqual(sorted(Path(f["path"]).name for f in plan["files"]), ["b.gguf", "mmproj.gguf"])
        self.assertEqual((plan["recipes_to_disable"], plan["profiles_affected"], plan["total_bytes"]), (["coder.b"], ["p.coder"], 200))
        self.assertEqual(len(plan["plan_digest"]), 64)

    def test_remove_moves_to_quarantine_and_restore_puts_everything_back(self):
        plan = preview(self.project, ["coder.b"], models_root=self.models)
        manifest = remove(self.project, plan)
        qdir = self.models / QUARANTINE / manifest["removal_id"]
        self.assertFalse(Path(self.b).exists()); self.assertTrue((qdir / "y" / "b.gguf").is_file()); self.assertTrue((qdir / "removal.json").is_file())
        self.assertEqual(self.enabled(), {"coder.a": True, "coder.b": False})
        out = restore(self.project, self.models, manifest["removal_id"])
        self.assertEqual(out["status"], "restored"); self.assertTrue(Path(self.b).is_file()); self.assertTrue(Path(self.m).is_file())
        self.assertEqual(self.enabled(), {"coder.a": True, "coder.b": True})

    def test_refusals(self):
        outside = self.project / "other.gguf"; outside.write_bytes(b"x")
        for targets, err in (([str(outside)], "outside_models_root"), (["coder.zzz"], "unknown_recipe"), ([str(self.models / "x" / "gone.gguf")], "file_missing"), ([], "nothing_to_remove")):
            with self.assertRaises(RemovalError) as ctx:
                preview(self.project, targets, models_root=self.models)
            self.assertIn(err, str(ctx.exception))
        with self.assertRaises(RemovalError) as ctx:
            preview(self.project, ["coder.a"], models_root=self.models, loaded_paths=[self.a])
        self.assertIn("model_is_loaded", str(ctx.exception))

    def test_tampered_or_changed_plan_is_refused_and_nothing_moves(self):
        plan = preview(self.project, ["coder.a"], models_root=self.models)
        bad = dict(plan, recipes_to_disable=[])
        with self.assertRaises(RemovalError):
            remove(self.project, bad)
        Path(self.a).write_bytes(b"changed")
        with self.assertRaises(RemovalError) as ctx:
            remove(self.project, plan)
        self.assertIn("file_changed_since_preview", str(ctx.exception))
        self.assertTrue(Path(self.a).is_file()); self.assertEqual(self.enabled()["coder.a"], True)


if __name__ == "__main__":
    unittest.main()
