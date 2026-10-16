import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from guppi_runtime.tools.base import ToolValidationError
from guppi_runtime.tools.web import WebAccessConfig, WebTool
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests


class FakeResponse(io.BytesIO):
    def __init__(self, body, ctype="text/plain"):
        super().__init__(body); self.headers = {"Content-Type": ctype}
    def __enter__(self): return self
    def __exit__(self, *a): return False


class FakeOpener:
    def __init__(self, body=b"hello"):
        self.body, self.urls = body, []
    def open(self, req, timeout=None):
        self.urls.append((req.full_url, req.get_method(), dict(req.header_items())))
        return FakeResponse(self.body)


class FakeGuard:
    def __init__(self, decision="ALLOW"):
        self.decision, self.calls = decision, []
    def evaluate(self, action, mission_id=None, target=None):
        self.calls.append((action, target)); return {"decision": self.decision}


class WebToolTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.config = WebAccessConfig({"allowed_domains": ["youtube.com", "github.com"], "max_bytes": 1000, "timeout_s": 5})

    def tool(self, opener=None, guard=None, api=None):
        return WebTool(self.root, guard or FakeGuard(), None, config=self.config, store_dir=self.root / "external", opener=opener, transcript_api=api)

    def test_listed_host_is_read_stored_and_marked_untrusted(self):
        opener, guard = FakeOpener(b"page"), FakeGuard()
        out = self.tool(opener, guard).execute("M-1", "get", {"url": "https://www.github.com/x"})
        self.assertEqual((out["status"], out["content"], out["trust"]), ("completed", "page", "untrusted_external"))
        self.assertEqual(guard.calls, [("external_read", "https://www.github.com/x")])
        self.assertEqual(opener.urls[0][1], "GET"); self.assertNotIn("Cookie", opener.urls[0][2])
        self.assertTrue((self.root / "external" / f"{out['sha256']}.txt").is_file())
        self.assertEqual(json.loads((self.root / "external" / "index.jsonl").read_text().splitlines()[0])["trust"], "untrusted_external")

    def test_off_list_http_and_credentials_are_never_fetched(self):
        opener = FakeOpener()
        t = self.tool(opener)
        self.assertEqual(t.execute("M", "get", {"url": "https://evil.example/"})["status"], "blocked")
        self.assertEqual(t.execute("M", "get", {"url": "https://notgithub.com/"})["status"], "blocked")
        for bad in ("http://github.com/", "https://user:pw@github.com/", "ftp://github.com/", None):
            with self.assertRaises(ToolValidationError):
                t.execute("M", "get", {"url": bad})
        self.assertEqual(opener.urls, [])

    def test_guard_can_still_stop_it_and_size_is_capped(self):
        out = self.tool(FakeOpener(), FakeGuard("CAPTAIN_REQUIRED")).execute("M", "get", {"url": "https://github.com/"})
        self.assertEqual(out["status"], "blocked")
        out = self.tool(FakeOpener(b"x" * 5000)).execute("M", "get", {"url": "https://github.com/"})
        self.assertEqual((len(out["content"]), out["truncated"]), (1000, True))

    def test_transcript_through_the_api_with_timestamps(self):
        seg = [SimpleNamespace(text="hello", start=0.0), SimpleNamespace(text="world", start=65.2)]
        api = SimpleNamespace(fetch=lambda vid, languages=None: seg)
        out = self.tool(api=api).execute("M", "youtube_transcript", {"video": "https://www.youtube.com/watch?v=m0VHx73SAG0"})
        self.assertEqual((out["status"], out["video_id"], out["segments"]), ("completed", "m0VHx73SAG0", 2))
        self.assertEqual(out["content"], "[00:00] hello\n[01:05] world")
        with self.assertRaises(ToolValidationError):
            self.tool(api=api).execute("M", "youtube_transcript", {"video": "not a video"})
        with self.assertRaises(ToolValidationError):
            self.tool(api=api).execute("M", "youtube_transcript", {"video": "m0VHx73SAG0", "languages": ["english!"]})

    def test_config_refuses_bad_domains(self):
        for bad in ({"allowed_domains": ["*"]}, {"allowed_domains": "github.com"}, {"allowed_domains": ["github.com"], "max_bytes": 5}):
            with self.assertRaises(ValueError):
                WebAccessConfig(bad)


if __name__ == "__main__":
    unittest.main()
