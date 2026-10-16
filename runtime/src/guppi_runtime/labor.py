"""KI Labor: Verbindungstest und Modelltest für Cloud-Anbieter (Captain-Wunsch 16.10.2026).

Jeder Test ist ein Aufruf auf Knopfdruck. Die Testnachricht ist kurz und enthält keine Nutzerdaten. Sie läuft durch den
Inhaltsschutz wie jeder Cloudaufruf. Der Test liest die gespeicherte Konfiguration: ist der Hauptschalter oder der Anbieter
aus, wird nichts gesendet. So prüft man die Kette vom Schlüssel bis zur Antwort, ohne auf einen Neustart zu warten.
"""
from __future__ import annotations
import time

from .core.content_guard import ContentGuard, ContentGuardStop
from .models.base import ModelAdapterError
from .models.cloud_api import provider_adapter
from .redesign_prep import pseudonymize

PING = [{"role": "user", "content": "Antworte nur mit dem Wort OK."}]
CHAT_MAX_TOKENS = 1024           # Antwort im Gespräch; Reasoning-Modelle brauchen Luft zum Denken
PING_MAX_TOKENS = 256           # Reasoning-Modelle denken vor der Antwort; mit 16 Tokens bleibt die Antwort leer (gemessen 16.10.2026)
MAX_MODELS_PER_RUN = 120          # eine Obergrenze gegen versehentliche Endlosläufe; die Anbieter liefern selten mehr
CONNECTION_TRIES = 4             # wie viele Modelle der Verbindungstest höchstens probiert
# Die Free-Endpoint-Modelle der NVIDIA-Modellseite (Stand 16.10.2026). Nur eine Reihenfolge für den Test, keine Freigabe.
FREE_ENDPOINT_HINTS = [
    'nvidia/nemotron-3.5-lightning-30b-a3b', 'nvidia/nemotron-3.5-super-vl-120b-a12b', 'nvidia/nemotron-3-ultra-550b-a55b',
    'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning', 'deepseek-ai/deepseek-v4.1-flash', 'google/gemma-4-31b-it',
    'nvidia/nemotron-3.5-content-safety', 'nvidia/nemotron-3-embed-1b', 'poolside/laguna-xs-2.1', 'stepfun-ai/step-5-preview',
    'nvidia/riva-translate-4b-instruct-v2', 'nvidia/ising-calibration-1.5-31b', 'google/diffusiongemma-26b-a4b-it',
    'meta/muse-glimmer-30b'
]
TEST_TIMEOUT_S = 25              # je Modell: ein Modell, das nicht antwortet, hält den Lauf nicht länger auf


def _enabled(config, provider_id):
    entry = (config.get("providers") or {}).get(provider_id) or {}
    return bool(config.get("enabled", False)) and bool(entry.get("enabled", False))


def _ping(adapter, model):
    """Eine Testnachricht an ein Modell. Gibt ein Ergebnis-Dict zurück, nie einen Schlüssel und nie eine Ausnahme."""
    started = time.monotonic()
    guard = ContentGuard(cloud_enabled=True)     # aufgerufen wird nur, wenn `_enabled` die gespeicherte Konfiguration bestätigt hat
    try:
        result = guard.call(PING, model=model, route="cloud",
                            complete=lambda msgs: adapter.chat(msgs, model=model, max_tokens=PING_MAX_TOKENS, temperature=0)["content"])
    except ContentGuardStop as exc:
        return {"model": model, "ok": False, "ms": 0, "detail": "Inhaltsschutz: " + ", ".join(exc.result.reasons)}
    except ModelAdapterError as exc:
        return {"model": model, "ok": False, "ms": _ms(started), "detail": str(exc)}
    reply = (result.text or "").strip()
    return {"model": model, "ok": bool(reply), "ms": _ms(started), "reply": reply[:60],
            "detail": "" if reply else "leere Antwort"}


def _ms(started):
    return int((time.monotonic() - started) * 1000)


def connection_test(config, provider_id, environ=None, key_store=None):
    """Die Kette in Schritten: Schlüssel da, Anbieter erreichbar und Modelle gemeldet, eine Testnachricht beantwortet."""
    steps = []
    if not _enabled(config, provider_id):
        steps.append({"step": "Einschalten", "ok": False, "detail": "Hauptschalter oder Anbieter ist in den Einstellungen aus. Erst einschalten und speichern."})
        return {"provider": provider_id, "ok": False, "steps": steps}
    try:
        adapter = provider_adapter(config, provider_id, environ, key_store)
    except ValueError as exc:
        steps.append({"step": "Einstellungen", "ok": False, "detail": str(exc)})
        return {"provider": provider_id, "ok": False, "steps": steps}
    adapter.timeout = min(adapter.timeout, TEST_TIMEOUT_S)
    try:
        models = adapter.fetch_models()
    except ModelAdapterError as exc:
        steps.append({"step": "Schlüssel und Anbieter", "ok": False, "detail": str(exc)})
        return {"provider": provider_id, "ok": False, "steps": steps}
    steps.append({"step": "Schlüssel und Anbieter", "ok": True, "detail": f"{len(models)} Modelle gemeldet"})
    # Erst das Standardmodell, sonst die nächsten gemeldeten. Nicht jedes gemeldete Modell ist für den Account aufrufbar,
    # deshalb werden höchstens CONNECTION_TRIES versucht und jeder Versuch gezeigt.
    # Modelle, die die NVIDIA-Seite als „Free Endpoint“ führt (Schnappschuss vom 16.10.2026), kommen zuerst, sofern der Anbieter sie meldet.
    preferred = [m for m in FREE_ENDPOINT_HINTS if m in models]
    candidates = ([adapter.default_model] if adapter.default_model else []) + [m for m in preferred + models if m != adapter.default_model]
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        steps.append({"step": "Testnachricht", "ok": False, "detail": "kein Modell zum Testen"})
        return {"provider": provider_id, "ok": False, "steps": steps}
    for model in candidates[:CONNECTION_TRIES]:
        answer = _ping(adapter, model)
        steps.append({"step": "Testnachricht an " + model, "ok": answer["ok"], "detail": answer.get("reply") or answer["detail"], "ms": answer["ms"]})
        if answer["ok"]: return {"provider": provider_id, "ok": True, "steps": steps, "model": model}
    return {"provider": provider_id, "ok": False, "steps": steps}


def cloud_chat(config, provider_id, model, messages, environ=None, key_store=None):
    """Eine Gesprächsantwort aus der Cloud, für das Gespräch im Cockpit. Geht durch den Inhaltsschutz wie jeder Cloudaufruf:
    Personenbezug wird pseudonymisiert und anonymisiert, die Antwort bleibt mit Platzhaltern. Nur eingeschaltet."""
    if not _enabled(config, provider_id):
        raise ValueError("cloud_off")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model_required")
    adapter = provider_adapter(config, provider_id, environ, key_store)
    guard = ContentGuard(cloud_enabled=True)
    # Persönliche Angaben werden nicht blockiert, sondern vorher durch eigene Begriffe ersetzt (redesign_prep). Die Zuordnung
    # bleibt lokal. Was danach noch auffällt, prüft der Inhaltsschutz wie gewohnt.
    messages = [dict(m, content=pseudonymize(m["content"])[0]) if isinstance(m.get("content"), str) else m for m in messages]
    try:
        result = guard.call(messages, model=model, route="cloud",
                            complete=lambda msgs: adapter.chat(msgs, model=model, max_tokens=CHAT_MAX_TOKENS)["content"])
    except ContentGuardStop as exc:
        return {"status": "blocked", "reasons": list(exc.result.reasons), "provider": provider_id, "model": model}
    return {"status": "completed", "reply": result.text or "", "provider": provider_id, "model": model}


def model_test(config, provider_id, environ=None, key_store=None):
    """Jedes Modell des Anbieters einmal mit einer Testnachricht ansprechen. Gibt je Modell ok, Dauer und Grund zurück."""
    if not _enabled(config, provider_id):
        return {"provider": provider_id, "ok": False, "results": [], "detail": "Hauptschalter oder Anbieter ist aus."}
    adapter = provider_adapter(config, provider_id, environ, key_store)
    adapter.timeout = min(adapter.timeout, TEST_TIMEOUT_S)
    models = adapter.fetch_models()[:MAX_MODELS_PER_RUN]
    results = [_ping(adapter, m) for m in models]
    passed = sum(1 for r in results if r["ok"])
    return {"provider": provider_id, "ok": passed == len(results), "passed": passed, "total": len(results), "results": results}
