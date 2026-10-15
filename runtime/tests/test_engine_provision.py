import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from guppi_runtime.engine_provision import EngineError, MANIFEST, engine_dir, provision, verify_engine
from guppi_runtime.llama_server_runtime import LlamaServerConfig, discover_backend
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EngineProvision(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.dl, self.root = Path(t.name) / "dl", Path(t.name) / "engines"
        self.dl.mkdir()
        self.assets = {"llama-b1234-bin.zip": make_zip(self.dl / "llama-b1234-bin.zip", {"llama-server.exe": b"MZserver", "ggml-cuda.dll": b"cuda"}),
                       "cudart.zip": "sha256:" + make_zip(self.dl / "cudart.zip", {"cudart64_12.dll": b"rt"})}

    def test_install_writes_manifest_and_verifies(self):
        m = provision(self.dl, build="b1234", assets=self.assets, root=self.root)
        target = engine_dir(self.root, "b1234")
        self.assertEqual(sorted(m["files"]), ["cudart64_12.dll", "ggml-cuda.dll", "llama-server.exe"])
        self.assertTrue((target / MANIFEST).is_file())
        self.assertEqual(verify_engine(self.root, "b1234"), (True, "ok"))
        self.assertEqual(verify_engine(self.root, "b1234", full=True), (True, "ok"))
        self.assertFalse(any(p.name.startswith(".staging") for p in target.parent.iterdir()))

    def test_wrong_hash_missing_zip_and_reinstall_are_refused(self):
        bad = dict(self.assets, **{"cudart.zip": "0" * 64})
        with self.assertRaises(EngineError) as ctx:
            provision(self.dl, build="b1234", assets=bad, root=self.root)
        self.assertIn("engine_asset_sha256_mismatch:cudart.zip", str(ctx.exception))
        self.assertFalse(engine_dir(self.root, "b1234").exists())
        with self.assertRaises(EngineError):
            provision(self.dl, build="b1234", assets=dict(self.assets, **{"other.zip": "1" * 64}), root=self.root)
        provision(self.dl, build="b1234", assets=self.assets, root=self.root)
        with self.assertRaises(EngineError) as ctx:
            provision(self.dl, build="b1234", assets=self.assets, root=self.root)
        self.assertIn("engine_already_installed", str(ctx.exception))

    def test_unsafe_zip_and_missing_server_leave_nothing_behind(self):
        evil = {"evil.zip": make_zip(self.dl / "evil.zip", {"../outside.exe": b"x", "llama-server.exe": b"MZ"})}
        with self.assertRaises(EngineError) as ctx:
            provision(self.dl, build="b1234", assets=evil, root=self.root)
        self.assertIn("engine_zip_unsafe_path", str(ctx.exception))
        noserver = {"n.zip": make_zip(self.dl / "n.zip", {"readme.txt": b"x"})}
        with self.assertRaises(EngineError) as ctx:
            provision(self.dl, build="b1234", assets=noserver, root=self.root)
        self.assertIn("engine_llama_server_missing", str(ctx.exception))
        self.assertEqual([p for p in (self.root / "llama.cpp").iterdir()], [])

    def test_changed_server_or_dll_is_detected(self):
        provision(self.dl, build="b1234", assets=self.assets, root=self.root)
        target = engine_dir(self.root, "b1234")
        (target / "ggml-cuda.dll").write_bytes(b"patched")
        self.assertEqual(verify_engine(self.root, "b1234"), (True, "ok"))              # quick check: server only
        self.assertEqual(verify_engine(self.root, "b1234", full=True), (False, "engine_file_changed:ggml-cuda.dll"))
        (target / "llama-server.exe").write_bytes(b"MZpatched")
        self.assertEqual(verify_engine(self.root, "b1234"), (False, "engine_file_changed:llama-server.exe"))
        self.assertEqual(verify_engine(self.root, "b9999"), (False, "engine_not_installed"))
        self.assertEqual(verify_engine(self.root, "../x"), (False, "engine_build_invalid"))

    def test_a_planted_file_next_to_the_server_is_detected_by_the_quick_check(self):
        provision(self.dl, build="b1234", assets=self.assets, root=self.root)
        target = engine_dir(self.root, "b1234")
        (target / "version.dll").write_bytes(b"planted")          # llama-server.exe would load it from its own folder
        self.assertEqual(verify_engine(self.root, "b1234"), (False, "engine_unlisted_file:version.dll"))
        self.assertEqual(verify_engine(self.root, "b1234", full=True), (False, "engine_unlisted_file:version.dll"))
        (target / "version.dll").unlink()
        self.assertEqual(verify_engine(self.root, "b1234"), (True, "ok"))

    def test_runtime_uses_only_the_own_engine_never_lmstudio(self):
        home = Path(self.root.parent) / "home"
        lm = home / ".lmstudio" / "extensions" / "backends" / "llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.49.0"
        lm.mkdir(parents=True); (lm / "llama-server.exe").write_bytes(b"MZlm")
        cfg = LlamaServerConfig({"engine_source": "guppi", "engine_build": "b1234", "engine_root": str(self.root)})
        self.assertEqual(discover_backend(cfg, home), (None, None))                    # not installed: no LM Studio fallback
        provision(self.dl, build="b1234", assets=self.assets, root=self.root)
        target = engine_dir(self.root, "b1234")
        self.assertEqual(discover_backend(cfg, home), (target, target))
        old = LlamaServerConfig({})
        self.assertEqual(discover_backend(old, home)[0], lm)                           # the earlier default still works
        for raw in ({"engine_source": "cloud"}, {"engine_source": "guppi"}, {"engine_source": "guppi", "engine_build": "latest"}):
            with self.assertRaises(ValueError):
                LlamaServerConfig(raw)


if __name__ == "__main__":
    unittest.main()
