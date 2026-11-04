"""YouTube-Transkript ohne Zusatzpaket (04.11.2026): Fehlt `youtube_transcript_api`, holt das Web-Werkzeug die Untertitel mit yt-dlp – nur die kleine .vtt-Textdatei, kein Video."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.tools import web
from guppi_runtime.tools.web import WebAccessConfig, WebTool
from host_isolation import setUpModule, tearDownModule  # noqa: F401

VTT = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello <c>there</c>\n\n00:00:03.000 --> 00:00:05.000\nHello there\nsecond line\n\n"
       "00:01:05.000 --> 00:01:06.000\nlate\n")
INFO = {"language": "en-US", "subtitles": {}, "automatic_captions": {"en-orig": [{}], "en": [{}], "de": [{}]}}


class Ytdlp:
    def __init__(self, info=INFO, vtt=VTT, fail=None):
        self.info, self.vtt, self.fail, self.calls = info, vtt, fail, []

    def __call__(self, args, cwd):
        self.calls.append((list(args), cwd))
        if "--dump-single-json" in args:
            return (1, "") if self.fail == "info" else (0, json.dumps(self.info))
        if self.fail != "subs":
            (Path(cwd) / "t.en-orig.vtt").write_text(self.vtt, encoding="utf-8")
        return 0, ""


class Fallback(unittest.TestCase):
    def tool(self, ytdlp):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        cfg = WebAccessConfig({"allowed_domains": ["youtube.com"]})
        return WebTool(Path(t.name), None, None, config=cfg, store_dir=Path(t.name) / "ext", ytdlp=ytdlp)

    def lauf(self, ytdlp, **args):
        with mock.patch.dict("sys.modules", {"youtube_transcript_api": None}):          # Paket nicht installiert
            return self.tool(ytdlp).execute("M", "youtube_transcript", dict({"video": "i_JcH1Y8Ka4"}, **args))

    def test_ohne_paket_kommen_die_untertitel_der_videosprache_mit_zeitmarken(self):
        y = Ytdlp()
        out = self.lauf(y)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["language"], "en-orig")
        self.assertEqual(out["content"].splitlines(), ["[00:01] Hello there", "[00:03] second line", "[01:05] late"])
        self.assertEqual(out["trust"], "untrusted_external")
        sub = y.calls[1][0]
        self.assertIn("--skip-download", sub); self.assertIn("en-orig", sub); self.assertIn("--write-auto-subs", sub)

    def test_gewuenschte_sprache_und_handgemachte_untertitel_haben_vorrang(self):
        info = {"language": "en", "subtitles": {"de": [{}]}, "automatic_captions": {"en-orig": [{}], "de": [{}]}}
        y = Ytdlp(info=info)
        self.lauf(y, languages=["de"])
        self.assertIn("--write-subs", y.calls[1][0]); self.assertIn("de", y.calls[1][0])

    def test_fehler_sind_ein_satz_und_kein_absturz(self):
        self.assertEqual(self.lauf(Ytdlp(info={"language": "en", "subtitles": {}, "automatic_captions": {}}))["status"], "failed")
        self.assertIn("no_subtitles", self.lauf(Ytdlp(info={"subtitles": {}, "automatic_captions": {}}))["error"])
        self.assertIn("yt_dlp_info_failed", self.lauf(Ytdlp(fail="info"))["error"])
        self.assertIn("yt_dlp_subtitles_failed", self.lauf(Ytdlp(fail="subs"))["error"])

    def test_ohne_paket_und_ohne_ytdlp_ein_klarer_grund(self):
        with mock.patch.dict("sys.modules", {"youtube_transcript_api": None}), mock.patch.object(web.shutil, "which", return_value=None):
            t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
            w = WebTool(Path(t.name), None, None, config=WebAccessConfig({"allowed_domains": ["youtube.com"]}), store_dir=Path(t.name) / "e")
            self.assertIn("not_installed", w.execute("M", "youtube_transcript", {"video": "i_JcH1Y8Ka4"})["error"])

    def test_vtt_ohne_tags_und_ohne_wiederholte_zeilen(self):
        self.assertEqual([s["text"] for s in web.parse_vtt(VTT)], ["Hello there", "second line", "late"])


if __name__ == "__main__":
    unittest.main()
