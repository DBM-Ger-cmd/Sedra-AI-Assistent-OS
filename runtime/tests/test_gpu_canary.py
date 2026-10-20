"""GPU canary (2026-10-11): once per Windows start and after a crash; a failure blocks model loads. No real server, GPU or HTTP."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import env_skip

from host_isolation import setUpModule, tearDownModule  # noqa: F401  (also puts src/ on the path)
from guppi_runtime.models import gpu_canary
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig
from guppi_runtime.models.runtime_control import RuntimeControlError
from test_llama_server_runtime import Base, FakeProc


def canary_raw(gguf, **kw):
    return {"enabled": True, "gguf": str(gguf), "port": 8093, "context": 32768, "timeout_s": 300, **kw}


class FakePost:
    """/tokenize: 1 token per word; /v1/chat/completions answers with the code hidden in the prompt (or `answer`)."""
    def __init__(self, answer=None, fail_at=None):
        self.answer, self.fail_at, self.chats = answer, fail_at, 0

    def __call__(self, endpoint, path, body, timeout):
        if path == "/tokenize":
            return {"tokens": body["content"].split()}
        self.chats += 1
        if self.fail_at is not None and self.chats > self.fail_at:
            raise ConnectionResetError("server gone")
        text = body["messages"][0]["content"]
        code = text.split("Projektcode lautet ")[1].split(".")[0]
        return {"choices": [{"message": {"content": self.answer if self.answer is not None else code}}]}


class Steps(unittest.TestCase):
    def test_all_steps_pass_when_the_code_comes_back(self):
        ok, rows = gpu_canary.run_steps("http://x", (300, 300, 300, 500), post=FakePost())
        self.assertTrue(ok)
        self.assertEqual([r["result"] for r in rows], ["ok"] * 4)

    def test_garbage_answer_fails_the_first_step(self):
        ok, rows = gpu_canary.run_steps("http://x", (300, 500), post=FakePost(answer="GGGGGGGGGGGGGGGG"))
        self.assertFalse(ok)
        self.assertEqual(rows[-1]["result"], "garbage")
        self.assertEqual(len(rows), 1)

    def test_wrong_code_and_crash_are_failures(self):
        self.assertEqual(gpu_canary.run_steps("http://x", (300,), post=FakePost(answer="ZX-000000 ok"))[1][-1]["result"], "wrong")
        ok, rows = gpu_canary.run_steps("http://x", (300, 300, 300, 500), post=FakePost(fail_at=3))
        self.assertFalse(ok)
        self.assertEqual((rows[-1]["step"], rows[-1]["result"]), (3, "server_error"))


class Config(unittest.TestCase):
    def test_absent_block_means_off(self):
        self.assertFalse(gpu_canary.CanaryConfig(None).enabled)
        self.assertFalse(LlamaServerConfig({"enabled": True}).canary.enabled)

    def test_invalid_values_switch_the_canary_off_with_a_reason_instead_of_stopping_the_server(self):
        # Entscheidung des Captains (2026-10-19): der llama-server läuft auch ohne gültigen Canary, der Grund wird gemeldet
        for bad in ({"gguf": "model.bin"}, {"port": 80}, {"context": 65536}, {"engine_build": "latest"}, {"timeout_s": 5}):
            c = gpu_canary.CanaryConfig({**canary_raw("m.gguf"), **bad})
            self.assertFalse(c.enabled, bad)
            self.assertTrue(c.config_error and c.config_error.startswith('llama_server_config_invalid:canary'), bad)
            self.assertEqual(c.disabled_reason, c.config_error)


class State(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "gpu_canary.json"

    def test_pass_counts_only_for_the_same_boot(self):
        gpu_canary.write_state({"boot": 1_000_000, "passed": True}, self.path)
        self.assertTrue(gpu_canary.passed_this_boot(self.path, boot=1_000_060))
        self.assertFalse(gpu_canary.passed_this_boot(self.path, boot=1_090_000))      # Windows was restarted: debug mode may be off again

    def test_invalidate_after_a_crash(self):
        gpu_canary.write_state({"boot": 1_000_000, "passed": True}, self.path)
        gpu_canary.invalidate("server exited with 3", self.path)
        self.assertFalse(gpu_canary.passed_this_boot(self.path, boot=1_000_000))
        self.assertEqual(gpu_canary.read_state(self.path)["invalidated"], "server exited with 3")


class RunCanary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gguf = self.root / "canary.gguf"; self.gguf.write_bytes(b"GGUF")
        (self.root / "engine").mkdir(); (self.root / "engine" / "llama-server.exe").write_bytes(b"x")
        self.state = self.root / "gpu_canary.json"
        self.procs = []

    def popen(self, argv, **kw):
        proc = FakeProc(argv); self.procs.append(proc); return proc

    def run_with(self, steps_result, healthy=None):
        canary = gpu_canary.CanaryConfig(canary_raw(self.gguf))
        health = healthy or (lambda endpoint: bool(self.procs))
        return gpu_canary.run_canary(canary, self.root / "engine", popen=self.popen, steps_runner=lambda e, s: steps_result, healthy=health,
                                     sleep=lambda s: None, state_path=self.state)

    def test_uses_the_settings_of_the_stable_runs_and_stops_its_server(self):
        state = self.run_with((True, [{"result": "ok"}]))
        self.assertTrue(state["passed"])
        argv = self.procs[0].argv
        for flag, value in (("-fa", "on"), ("-ctk", "q8_0"), ("-ctv", "q8_0"), ("-ub", "512"), ("-np", "1"), ("-ngl", "99"), ("--port", "8093")):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertTrue(self.procs[0].terminated)
        self.assertTrue(gpu_canary.read_state(self.state)["passed"])

    def test_failure_is_remembered(self):
        state = self.run_with((False, [{"result": "garbage"}]))
        self.assertEqual((state["passed"], state["result"]), (False, "garbage"))

    def test_busy_port_starts_nothing(self):
        state = self.run_with((True, []), healthy=lambda endpoint: True)
        self.assertEqual((state["passed"], state["result"]), (False, "port_in_use"))
        self.assertEqual(self.procs, [])

    @env_skip.needs_windows
    def test_ensure_skips_when_passed_this_boot(self):
        canary = gpu_canary.CanaryConfig(canary_raw(self.gguf))
        gpu_canary.write_state({"boot": gpu_canary.boot_time(), "passed": True}, self.state)
        self.assertIsNone(gpu_canary.ensure(canary, self.root / "engine", popen=self.popen, state_path=self.state))
        self.assertEqual(self.procs, [])


class RuntimeHook(Base):
    def server(self): return {"gguf": str(self.gguf)}

    def test_failed_canary_blocks_the_load(self):
        rt = self.runtime(canary=canary_raw(self.gguf))
        with mock.patch.object(gpu_canary, "ensure", return_value={"passed": False, "result": "garbage"}):
            with self.assertRaises(RuntimeControlError) as cm:
                rt.load_model("m", context_length=4096, server=self.server())
        self.assertIn("gpu_canary_failed:garbage", str(cm.exception))
        self.assertEqual(self.env.procs, [])

    def test_passed_canary_lets_the_load_through(self):
        rt = self.runtime(canary=canary_raw(self.gguf))
        with mock.patch.object(gpu_canary, "ensure", return_value=None) as ensure:
            rt.load_model("m", context_length=4096, server=self.server())
        ensure.assert_called_once()
        self.assertEqual(len(self.env.procs), 1)

    def test_crash_invalidates_the_canary(self):
        rt = self.runtime(canary=canary_raw(self.gguf))
        with mock.patch.object(gpu_canary, "ensure", return_value=None):
            rt.load_model("m", context_length=4096, server=self.server())
        self.env.procs[-1][0].returncode = 3
        with mock.patch.object(gpu_canary, "invalidate") as invalidate:
            rt.status()
        invalidate.assert_called_once()
        self.assertIn("server exited with 3", invalidate.call_args[0][0])

    def test_engine_override_from_environment(self):
        with mock.patch.dict(os.environ, {"GUPPI_ENGINE_BUILD": "b11160"}):
            self.assertEqual(LlamaServerConfig({"enabled": True, "engine_source": "guppi", "engine_build": "b11371"}).engine_build, "b11160")
        with mock.patch.dict(os.environ, {"GUPPI_ENGINE_BUILD": "../evil"}):
            self.assertEqual(LlamaServerConfig({"enabled": True, "engine_source": "guppi", "engine_build": "b11371"}).engine_build, "b11371")


class MissingCanaryFile(Base):
    """2026-10-16: a canary model that is not on disk is a failed canary with its own reason. It used to surface as
    ValueError('valid_gguf_model_required') out of build_command, which read as a broken MODEL recipe."""
    def setUp(self):
        super().setUp()
        self.missing = self.root / "unsloth" / "nicht-da.gguf"
        self.state = self.root / "gpu_canary.json"

    def test_the_canary_reports_the_missing_file_and_starts_nothing(self):
        canary = gpu_canary.CanaryConfig(canary_raw(self.missing))
        state = gpu_canary.run_canary(canary, self.backend, healthy=lambda endpoint: False, state_path=self.state, popen=self.env.popen, sleep=lambda s: None)
        self.assertEqual((state["passed"], state["result"]), (False, "gguf_missing"))
        self.assertEqual(state["detail"], str(self.missing))
        self.assertEqual(self.env.procs, [])
        self.assertFalse(gpu_canary.passed_this_boot(self.state))

    def test_a_load_is_refused_with_the_canary_reason_and_no_server_starts(self):
        rt = self.runtime(canary=canary_raw(self.missing))
        def real_canary(canary, executable_dir, **kw):
            return gpu_canary.run_canary(canary, executable_dir, healthy=lambda endpoint: False, state_path=self.state, popen=self.env.popen, sleep=lambda s: None)
        with mock.patch.object(gpu_canary, "ensure", side_effect=real_canary):
            with self.assertRaises(RuntimeControlError) as cm:
                rt.load_model("m", context_length=4096, server={"gguf": str(self.gguf)})
        self.assertIn(f"gpu_canary_gguf_missing:{self.missing}", str(cm.exception))
        self.assertNotIn("valid_gguf_model_required", str(cm.exception))
        self.assertEqual(self.env.procs, [])


if __name__ == "__main__":
    unittest.main()
