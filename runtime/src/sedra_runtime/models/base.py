from __future__ import annotations
from urllib.parse import urlparse


class ModelAdapterError(RuntimeError):
    pass


def require_loopback_url(url: str):
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"}:
        raise ModelAdapterError("unsupported_url_scheme")
    host=(parsed.hostname or "").lower()
    if host not in {"localhost","127.0.0.1","::1"}:
        raise ModelAdapterError("non_loopback_endpoint_rejected")
    return url.rstrip("/")


class BaseModelAdapter:
    id="base"
    def health(self): return False
    def list_models(self): return []
    def chat(self, messages, model=None, **kwargs): raise NotImplementedError
