"""benchmarks/connection_check.py (S0 driver): no GPU, no server - a fake runtime and a fake HTTP layer."""
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "src"))

import connection_check as cc  # noqa: E402
from guppi_runtime.conn_check import RequestError  # noqa: E402


class FakeRuntime:
    endpoint = "http://127.0.0.1:1"

    def __init__(self, fail=None):
        self.fail, self.loaded, self.unloaded = fail, [], 0

    def load_model(self, alias, **kw):
        if self.fail:
            raise RuntimeError(self.fail)
        self.loaded.append((alias, kw["context_length"], kw["server"]))

    def unload_model(self, all_models=False):
        self.unloaded += 1


class ConnectionCheck(unittest.TestCase):
    RECIPE = {"id": "coder.x", "model": "x-model", "profile": {"server": {"gguf": "x.gguf"}}}

    def test_a_load_error_is_a_failed_check_and_nothing_runs(self):
        out = cc.check(FakeRuntime(fail="gpu_canary_failed:garbage"), self.RECIPE, 32768)
        self.assertEqual((out["ok"], out["checks"]), (False, []))
        self.assertIn("gpu_canary_failed", out["load_error"])

    def test_the_server_is_started_as_the_recipe_says_and_always_stopped(self):
        rt = FakeRuntime()
        with mock.patch.object(cc, "prompt_maker", return_value=lambda n: "x"), mock.patch.object(cc, "run_all", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                cc.check(rt, self.RECIPE, 16384)
        self.assertEqual(rt.loaded, [("x-model", 16384, {"gguf": "x.gguf"})])
        self.assertEqual(rt.unloaded, 1)

    def test_poster_sends_the_alias_and_turns_http_errors_into_request_errors(self):
        sent = {}

        def fake_open(req, timeout):
            sent.update(json.loads(req.data))
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b"exceeds the context size"))
        with mock.patch.object(cc.urllib.request, "urlopen", fake_open):
            with self.assertRaises(RequestError) as cm:
                cc.poster("http://h", "alias-1")("/v1/chat/completions", {"model": "other", "messages": []})
        self.assertEqual((cm.exception.status, sent["model"]), (400, "alias-1"))
        self.assertIn("exceeds", cm.exception.text)


if __name__ == "__main__":
    unittest.main()
