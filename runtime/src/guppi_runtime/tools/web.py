"""Read-only access to a short list of web domains (2026-10-03, Captain: GUPPI shall fetch e.g. YouTube transcripts itself;
"Liste ohne Einzelfreigabe" = domains on the list are read without a gate per call).

Rules, enforced here before the Guard is asked:
  - https only, GET only, no cookies, no credentials, no request body; a fixed GUPPI user agent,
  - the host must be on config/web_access.yaml `allowed_domains` (a subdomain of a listed domain counts); every redirect is checked
    again, so a listed site cannot forward GUPPI elsewhere,
  - at most `max_bytes` per answer, `timeout_s` per request,
  - every fetch is audited and stored under runtime_data/external/ with its sha256 and `trust: untrusted_external`: what comes back
    is DATA for a model to read, never an instruction for GUPPI.
The Guard decides the action `external_read` (GR-027: ALLOW); a host off the list is blocked by this tool and never fetched.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from ..util import utcnow
from .base import BaseTool, ToolValidationError

USER_AGENT = "GUPPI-external-read/0.1 (+local; read-only)"
VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})|^([A-Za-z0-9_-]{11})$")


class WebAccessConfig:
    def __init__(self, raw):
        raw = raw or {}
        domains = raw.get("allowed_domains") or []
        if not isinstance(domains, list) or any(not isinstance(d, str) or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", d) for d in domains):
            raise ValueError("web_access_config_invalid:allowed_domains")
        self.allowed_domains = [d.lower() for d in domains]
        self.max_bytes = int(raw.get("max_bytes", 2_000_000))
        self.timeout_s = int(raw.get("timeout_s", 30))
        if not 1_000 <= self.max_bytes <= 20_000_000 or not 1 <= self.timeout_s <= 120:
            raise ValueError("web_access_config_invalid:limits")

    @classmethod
    def load(cls, path):
        path = Path(path)
        return cls((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("web_access") if path.exists() else {})

    def host_allowed(self, host):
        host = (host or "").lower().rstrip(".")
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, config):
        self.config = config

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != "https" or not self.config.host_allowed(target.hostname):
            raise ToolValidationError(f"redirect_off_the_list:{target.hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class WebTool(BaseTool):
    id = "web"
    version = "0.1.0"
    supported_operations = {"get", "youtube_transcript"}

    def __init__(self, root: Path, guard=None, audit=None, config=None, store_dir=None, opener=None, transcript_api=None):
        super().__init__(root, guard, audit)
        self.config = config or WebAccessConfig({})
        self.store_dir = Path(store_dir) if store_dir else self.root / "external"
        self._opener = opener or urllib.request.build_opener(_CheckedRedirects(self.config))
        self._transcript_api = transcript_api            # injectable for tests; default: youtube_transcript_api if installed

    def health(self):
        return bool(self.config.allowed_domains)

    # ---- helpers
    def _check_url(self, url):
        if not isinstance(url, str) or len(url) > 2048:
            raise ToolValidationError("url_invalid")
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ToolValidationError("url_must_be_plain_https")
        return parts

    def _guard(self, mission_id, target):
        if self.guard is None:
            return {"decision": "ALLOW"}
        return self.guard.evaluate("external_read", mission_id=mission_id, target=target)

    def _store(self, mission_id, source, kind, text):
        data = text.encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        self.store_dir.mkdir(parents=True, exist_ok=True)
        (self.store_dir / f"{digest}.txt").write_bytes(data)
        record = {"source": source, "kind": kind, "sha256": digest, "bytes": len(data), "fetched_at": utcnow(), "trust": "untrusted_external",
                  "mission_id": mission_id}
        with (self.store_dir / "index.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.audit:
            self.audit.append("TOOL_CALLED", component="web", mission_id=mission_id,
                              payload={"tool": self.id, "operation": kind, "source": source, "sha256": digest, "bytes": len(data)})
        return record

    # ---- operations
    def execute(self, mission_id, operation, args=None, approval_token=None):
        args = args or {}
        if operation == "get":
            return self._get(mission_id, args.get("url"))
        if operation == "youtube_transcript":
            return self._transcript(mission_id, args.get("video"), args.get("languages"))
        raise ToolValidationError(f"unsupported_web_operation:{operation}")

    def _get(self, mission_id, url):
        parts = self._check_url(url)
        if not self.config.host_allowed(parts.hostname):
            return {"status": "blocked", "error": f"host_not_on_list:{parts.hostname}"}
        verdict = self._guard(mission_id, url)
        if verdict["decision"] != "ALLOW":
            return {"status": "blocked", "guard": verdict}
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.5"})
        try:
            with self._opener.open(req, timeout=self.config.timeout_s) as resp:
                body = resp.read(self.config.max_bytes + 1)
                ctype = resp.headers.get("Content-Type", "")
        except ToolValidationError as exc:
            return {"status": "blocked", "error": str(exc)}
        except urllib.error.HTTPError as exc:
            return {"status": "failed", "error": f"http_{exc.code}"}
        except Exception as exc:
            return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        truncated = len(body) > self.config.max_bytes
        text = body[: self.config.max_bytes].decode("utf-8", "replace")
        record = self._store(mission_id, url, "get", text)
        return {"status": "completed", "content": text, "content_type": ctype, "truncated": truncated, **record}

    def _transcript(self, mission_id, video, languages):
        if not isinstance(video, str):
            raise ToolValidationError("video_required")
        m = VIDEO_ID.search(video.strip())
        if not m:
            raise ToolValidationError("video_id_invalid")
        vid = m.group(1) or m.group(2)
        source = f"https://www.youtube.com/watch?v={vid}"
        if not self.config.host_allowed("www.youtube.com"):
            return {"status": "blocked", "error": "host_not_on_list:www.youtube.com"}
        verdict = self._guard(mission_id, source)
        if verdict["decision"] != "ALLOW":
            return {"status": "blocked", "guard": verdict}
        if languages is not None and (not isinstance(languages, list) or any(not re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2})?", l or "") for l in languages)):
            raise ToolValidationError("languages_invalid")
        api = self._transcript_api
        if api is None:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
            except ImportError:
                return {"status": "failed", "error": "youtube_transcript_api_not_installed"}
            api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(vid, languages=languages) if languages else api.fetch(vid)
            segments = [{"text": s.text, "start": float(s.start)} for s in fetched]
        except Exception as exc:
            return {"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        lines = [f"[{int(s['start']) // 60:02d}:{int(s['start']) % 60:02d}] {s['text']}" for s in segments]
        text = "\n".join(lines)[: self.config.max_bytes]
        record = self._store(mission_id, source, "youtube_transcript", text)
        return {"status": "completed", "video_id": vid, "segments": len(segments), "content": text,
                "language": getattr(fetched, "language_code", None), **record}
