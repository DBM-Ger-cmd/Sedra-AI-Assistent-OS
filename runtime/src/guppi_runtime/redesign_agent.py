"""Das Cloud-Modell setzt einen Designauftrag im Sandbox-Bereich um (Grundsatz des Captains, 16.10.2026).

Jeder Schritt ist ein Cloudaufruf durch den Inhaltsschutz. Das Modell liest und schreibt nur über die Werkzeuge in
sandbox_edit.py, und nur unter der Sandbox-Wurzel. Die Schleife endet mit `finish`, nach höchstens MAX_TURNS Schritten, oder
nach mehreren Antworten ohne gültiges Werkzeug. Der Live-Code wird nie geändert; die Übernahme prüft der Mensch.
"""
from __future__ import annotations
import time
from .core.content_guard import ContentGuard, ContentGuardStop
from .models.base import ModelAdapterError
from .models.cloud_api import provider_adapter
from .labor import _enabled
from .sandbox_edit import Sandbox, SandboxError, TOOLS_HELP, parse_action, run_action

MAX_TURNS = 40
MAX_BAD_REPLIES = 4        # so viele Antworten ohne gültiges JSON in Folge, dann stoppt die Schleife
KEEP_HISTORY = 16          # die letzten Schritte bleiben im Gespräch, der Auftrag immer
AGENT_MAX_TOKENS = 12000   # ein Schritt kann eine ganze Datei schreiben; Reasoning-Modelle denken davor (16.10.2026 gemessen: 6000 reichte nicht)
STEP_TIMEOUT_S = 240       # die Zeit je Schritt: große Modelle brauchen für eine Datei mehr als die Standardgrenze von 60 Sekunden
RETRIES = 2                # bei Zeitüberschreitung oder Anbieterfehler wiederholen, bevor der Lauf aufgibt
RETRY_PAUSE_S = 20


def _system(task_hint):
    return ("Du bist ein Frontend-Entwickler für eine lokale Agenten-Oberfläche (reines HTML, CSS und JavaScript, ohne Framework). "
            "Du arbeitest nur in der Sandbox, die dir als Werkzeug-Wurzel dient. Halte die Projektregeln ein: Farben nur über die "
            "Tokens in ui/tokens.css (keine Hex-Werte in anderen Dateien), keine Datei länger als 400 Zeilen, keine fetch- oder "
            "localStorage-Aufrufe in Werkzeugen, und jede Datei bleibt funktionsfähig. Denke knapp, arbeite Schritt für Schritt.\n\n"
            + TOOLS_HELP + "\n\nAuftrag: " + task_hint)


def run_redesign(config, provider_id, model, task, sandbox_root, audit=None, environ=None, key_store=None,
                 max_turns=MAX_TURNS, call=None, allow=None):
    """Führt den Auftrag aus. `call` ersetzt den Modellaufruf (für Tests); sonst geht es über den Adapter und den Inhaltsschutz.
    `allow`: die Dateien, die dieser Lauf schreiben darf (siehe Sandbox)."""
    if not _enabled(config, provider_id):
        return {"status": "off", "detail": "Cloud oder Anbieter ist in den Einstellungen aus.", "writes": []}
    sandbox = Sandbox(sandbox_root, audit=audit, allow=allow)
    if call is None:
        adapter = provider_adapter(config, provider_id, environ, key_store)
        adapter.timeout = max(adapter.timeout, STEP_TIMEOUT_S)     # ein Schritt kann eine ganze Datei schreiben
        guard = ContentGuard(audit=audit, cloud_enabled=True)

        def call(messages):
            result = guard.call(messages, model=model, route="cloud",
                                complete=lambda msgs: adapter.chat(msgs, model=model, max_tokens=AGENT_MAX_TOKENS)["content"])
            return result.text or ""

    head = [{"role": "system", "content": _system(task)}, {"role": "user", "content": "Beginne. Ein JSON-Objekt, sonst nichts."}]
    history = []
    bad = 0
    for turn in range(1, max_turns + 1):
        messages = head + history[-KEEP_HISTORY:]
        reply = None
        for attempt in range(1, RETRIES + 2):
            try:
                reply = call(messages)
                break
            except ContentGuardStop as exc:
                # Eine leere Antwort ist kein Sicherheitsgrund: das Modell hat das Token-Limit oft im Nachdenken verbraucht.
                # Dann gilt sie wie eine ungültige Antwort und der Schritt wird noch einmal erbeten.
                if "SG_OUTPUT_EMPTY" in exc.result.reasons:
                    reply = ""
                    break
                return {"status": "blocked", "detail": ", ".join(exc.result.reasons), "turns": turn, "writes": sandbox.writes}
            except (ModelAdapterError, ValueError) as exc:
                # Zeitüberschreitung, Überlastung (429, 5xx) oder Verbindungsfehler: nach einer Pause noch einmal.
                text = str(exc)
                transient = "TimeoutError" in text or "cloud_api_error" in text or any(code in text for code in ("cloud_api_http_429", "cloud_api_http_5"))
                if attempt > RETRIES or not transient:
                    return {"status": "error", "detail": text[:200], "turns": turn, "writes": sandbox.writes}
                time.sleep(RETRY_PAUSE_S)
        if reply is None:
            return {"status": "error", "detail": "keine Antwort", "turns": turn, "writes": sandbox.writes}
        action = parse_action(reply)
        if action is None:
            bad += 1
            history += [{"role": "assistant", "content": reply[:2000]},
                        {"role": "user", "content": "Das war kein gültiges Werkzeug. Antworte mit genau einem JSON-Objekt mit „tool“ und „args“."}]
            if bad >= MAX_BAD_REPLIES: return {"status": "stopped", "detail": "keine gültigen Schritte", "turns": turn, "writes": sandbox.writes}
            continue
        bad = 0
        tool, args = action
        result, done = run_action(sandbox, tool, args)
        history += [{"role": "assistant", "content": reply[:2000]}, {"role": "user", "content": "Ergebnis:\n" + result[:12000]}]
        if done:
            return {"status": "finished", "summary": result, "turns": turn, "writes": sandbox.writes}
    return {"status": "turn_limit", "turns": max_turns, "writes": sandbox.writes}
