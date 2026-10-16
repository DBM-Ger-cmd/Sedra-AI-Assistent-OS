"""Cloud-Modelle über API-Schlüssel (Captain-Entscheidung 16.10.2026: Schalter, das Gateway prüft jeden Aufruf).

Zwei Adapter: OpenAI-kompatibel (NVIDIA, OpenAI und alle Anbieter mit /v1/chat/completions) und Anthropic Messages API.
Sie sind nur dann registriert, wenn der Captain sie in `config/cloud_providers.yaml` einschaltet (Standard: aus). Jeder Aufruf
hat `route = "cloud"` und geht durch den Inhaltsschutz (core/content_guard.py): gesperrte Kategorien verlassen den Rechner nicht.

Schlüssel stehen nie in einer Datei: die Konfiguration nennt nur `secret://anbieter/schluessel-id`, der Wert kommt aus der
Umgebungsvariable `GUPPI_SECRET_ANBIETER_SCHLUESSEL_ID`. Er wird nie gespeichert, nie protokolliert und nie in einer Fehlermeldung ausgegeben.
"""
from __future__ import annotations
import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from .base import BaseModelAdapter, ModelAdapterError
from .openai_local import normalize_usage

SECRET_REF = re.compile(r"^secret://([a-z0-9-]+)/([a-z0-9-]+)$")
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MAX_TOKENS = 1024
PASSED_OPTIONS = ("temperature", "max_tokens", "top_p")
# Diese Optionen gibt es nur bei lokalen Modellen oder sie wären ohne Prüfung nicht sicher weitergereicht. Sie werden nicht
# still verworfen, sondern laut abgelehnt (ModelAdapterError), damit kein Aufrufer glaubt, sie hätten gewirkt.
UNSUPPORTED_OPTIONS = ("response_format", "tools", "stream_guard")


def secret_env_name(ref):
    """`secret://nvidia/api-key` -> `GUPPI_SECRET_NVIDIA_API_KEY`. Ungültige Verweise sind ein Fehler, kein Standardwert."""
    match = SECRET_REF.match(ref or "")
    if not match: raise ModelAdapterError("invalid_secret_reference")
    return "GUPPI_SECRET_" + "_".join(part.upper().replace("-", "_") for part in match.groups())


def resolve_secret(ref, environ=None):
    """Den Wert eines Verweises aus der Umgebung holen. Fehlt er, sagt die Fehlermeldung nur den Namen der Variable, nie einen Wert."""
    name = secret_env_name(ref)
    value = (os.environ if environ is None else environ).get(name, "").strip()
    if not value: raise ModelAdapterError(f"secret_not_set:{name}")
    return value


def require_https_url(url):
    """Cloud nur über https. Kein Loopback-Ausweg: das ist der Unterschied zu den lokalen Adaptern."""
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or not parsed.hostname: raise ModelAdapterError("cloud_url_must_be_https")
    return url.rstrip("/")


def _error_detail(exc, headers=None):
    """Der Grund aus der Antwort des Anbieters, kurz, ohne Schlüssel. Der Text kann Prompt-Teile oder den Schlüssel spiegeln:
    deshalb werden die Kopfwerte und alles, was wie ein Schlüssel aussieht, geschwärzt."""
    try:
        raw = exc.read(400).decode("utf-8", "replace")
    except Exception:
        raw = ""
    try:
        data = json.loads(raw)
        text = str(data.get("detail") or data.get("title") or data.get("message") or "") if isinstance(data, dict) else raw
    except ValueError:
        text = raw
    for value in (headers or {}).values():
        for part in str(value).split():          # „Bearer <schlüssel>“: der Schlüssel allein muss verschwinden
            if len(part) > 12: text = text.replace(part, "[geschwärzt]")
    text = re.sub(r"(nvapi|sk)-[A-Za-z0-9_\-]{8,}", "[geschwärzt]", text)
    return " ".join(text.split())[:160]


class _CloudAdapter(BaseModelAdapter):
    route = "cloud"

    def __init__(self, adapter_id, base_url, api_key_ref, default_model, timeout=60, environ=None, key_store=None):
        self.id = adapter_id
        self.base_url = require_https_url(base_url)
        self.api_key_ref = api_key_ref
        self.default_model = default_model
        self.timeout = int(timeout)
        self._environ = environ
        self._key_store = key_store          # cloud_settings.CloudKeyStore: verschlüsselt abgelegte Schlüssel (Windows), Rückfall

    def _key(self):
        try:
            return resolve_secret(self.api_key_ref, self._environ)
        except ModelAdapterError:
            value = self._key_store.get(self.id) if self._key_store is not None else None
            if value: return value
            raise

    def health(self):
        # Kein Netzwerkaufruf: health() läuft vor jedem Aufruf. Bereit heißt: Modell gesetzt und Schlüssel vorhanden.
        try:
            self._key()
        except ModelAdapterError:
            return False
        return bool(self.default_model)

    def list_models(self):
        return [self.default_model] if self.default_model else []

    def fetch_models(self):
        """Die Modelle, die der Anbieter für diesen Schlüssel anbietet. Nur ein Lesen: es geht kein Prompt hinaus, nur der Schlüssel."""
        data = self._get(self.models_path, self._auth_headers())
        return sorted({m["id"] for m in (data.get("data") or []) if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]})

    def _get(self, path, headers):
        req = Request(self.base_url + path, method="GET", headers=dict(headers))
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelAdapterError(f"cloud_api_http_{exc.code}:{_error_detail(exc, headers)}") from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ModelAdapterError(f"cloud_api_error:{type(exc).__name__}") from None

    def _post(self, path, payload, headers):
        body = json.dumps(payload).encode("utf-8")
        req = Request(self.base_url + path, data=body, method="POST", headers=dict(headers, **{"Content-Type": "application/json"}))
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelAdapterError(f"cloud_api_http_{exc.code}:{_error_detail(exc, headers)}") from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ModelAdapterError(f"cloud_api_error:{type(exc).__name__}") from None

    @staticmethod
    def _check_options(kwargs):
        for name in UNSUPPORTED_OPTIONS:
            if kwargs.get(name): raise ModelAdapterError(f"cloud_option_unsupported:{name}")

    def _model(self, model):
        model = model or self.default_model
        if not model: raise ModelAdapterError("cloud_model_required")
        return model

    def _result(self, model, content, finish, usage, raw):
        return {"provider": self.id, "model": model, "content": content, "raw": raw, "usage": normalize_usage(usage),
                "finish_reason": finish, "truncated": finish == "length", "reasoning_chars": 0,
                "empty_answer": not content.strip(), "message": None}


class CloudOpenAICompatibleAdapter(_CloudAdapter):
    """POST {base}/chat/completions mit Bearer-Schlüssel (NVIDIA, OpenAI, Mistral, Groq, OpenRouter …)."""
    models_path = "/models"

    def _auth_headers(self):
        return {"Authorization": "Bearer " + self._key()}

    def chat(self, messages, model=None, **kwargs):
        if not isinstance(messages, list) or not messages: raise ModelAdapterError("messages_required")
        self._check_options(kwargs)
        model = self._model(model)
        payload = {"model": model, "messages": messages, "stream": False}
        for key in PASSED_OPTIONS:
            if kwargs.get(key) is not None: payload[key] = kwargs[key]
        headers = {"Authorization": "Bearer " + self._key()}
        data = self._post("/chat/completions", payload, headers)
        choices = data.get("choices") or []
        if not choices: raise ModelAdapterError("no_completion_choice")
        message = choices[0].get("message", {}) or {}
        content = message.get("content") or ""
        return self._result(model, content, choices[0].get("finish_reason"), data.get("usage"), data)


class CloudAnthropicAdapter(_CloudAdapter):
    """POST {base}/v1/messages (Anthropic Messages API). System-Nachrichten gehen in das Feld `system`."""
    models_path = "/v1/models"

    def _auth_headers(self):
        return {"x-api-key": self._key(), "anthropic-version": ANTHROPIC_VERSION}

    def chat(self, messages, model=None, **kwargs):
        if not isinstance(messages, list) or not messages: raise ModelAdapterError("messages_required")
        self._check_options(kwargs)
        model = self._model(model)
        system = "\n\n".join(m.get("content", "") for m in messages if m.get("role") == "system" and isinstance(m.get("content"), str))
        turns = [{"role": m.get("role"), "content": m.get("content")} for m in messages if m.get("role") != "system"]
        if not turns or any(t["role"] not in ("user", "assistant") or not isinstance(t["content"], str) for t in turns):
            raise ModelAdapterError("invalid_messages")
        payload = {"model": model, "messages": turns, "max_tokens": kwargs.get("max_tokens") or DEFAULT_ANTHROPIC_MAX_TOKENS}
        if system: payload["system"] = system
        for key in ("temperature", "top_p"):
            if kwargs.get(key) is not None: payload[key] = kwargs[key]
        headers = {"x-api-key": self._key(), "anthropic-version": ANTHROPIC_VERSION}
        data = self._post("/v1/messages", payload, headers)
        content = "".join(block.get("text", "") for block in data.get("content") or [] if block.get("type") == "text")
        finish = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length"}.get(data.get("stop_reason"), data.get("stop_reason"))
        usage = data.get("usage") or {}
        usage = {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens")}
        return self._result(model, content, finish, usage, data)


KINDS = {"openai_compatible": CloudOpenAICompatibleAdapter, "anthropic": CloudAnthropicAdapter}


def provider_adapter(config, provider_id, environ=None, key_store=None):
    """Der Adapter eines Anbieters aus der gespeicherten Konfiguration, eingeschaltet oder nicht. Für Abfragen und Tests."""
    entry = (config.get("providers") or {}).get(provider_id) if isinstance(config, dict) else None
    if not isinstance(entry, dict): raise ValueError("unknown_provider")
    kind = KINDS.get(entry.get("kind"))
    if kind is None: raise ValueError("cloud_provider_kind_unknown")
    try:
        return kind(provider_id, entry.get("base_url") or "", entry.get("api_key") or "", entry.get("default_model"),
                    timeout=entry.get("timeout_s", 60), environ=environ, key_store=key_store)
    except ModelAdapterError as exc:
        raise ValueError(f"cloud_provider_invalid:{exc}") from None


def provider_models(config, provider_id, environ=None, key_store=None):
    """Die Modellliste eines Anbieters vom Anbieter selbst. Ob der Anbieter eingeschaltet ist, spielt hier keine Rolle:
    man soll das Modell wählen können, bevor man ihn einschaltet. Fehler kommen ohne Schlüssel zurück."""
    return provider_adapter(config, provider_id, environ, key_store).fetch_models()


def build_cloud_adapters(config, environ=None, key_store=None):
    """Aus dem Abschnitt `cloud_providers` der YAML-Datei die eingeschalteten Adapter bauen. Ausgeschaltet heißt: gar nicht gebaut."""
    if not isinstance(config, dict): raise ValueError("cloud_providers_invalid")
    if not config.get("enabled", False): return []
    adapters = []
    for provider_id, entry in (config.get("providers") or {}).items():
        if not isinstance(entry, dict) or not entry.get("enabled", False): continue
        kind = KINDS.get(entry.get("kind"))
        if kind is None: raise ValueError(f"cloud_provider_kind_unknown:{provider_id}")
        try:
            adapters.append(kind(provider_id, entry.get("base_url") or "", entry.get("api_key") or "", entry.get("default_model"),
                                 timeout=entry.get("timeout_s", 60), environ=environ, key_store=key_store))
        except ModelAdapterError as exc:
            raise ValueError(f"cloud_provider_invalid:{provider_id}:{exc}") from None
    return adapters
