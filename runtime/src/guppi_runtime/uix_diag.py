"""Diagnosis for the chat window (Captain 2026-10-12: error details visible, a diagnosis side bar, commands in the chat). GUPPI's diag_core judges (explain_error, parse_command,
status_rows); this module only reads the facts of the running UIX for it and runs the chat commands. Reading changes nothing; the one command that changes something is
`/rebind ja` (the Captain types it himself), and it goes through HardwareManager.rebind, which keeps the limits and writes an audit event."""
from __future__ import annotations

import json
import time

from .diag_core import explain_error, parse_command, status_rows
from .models import gpu_canary

HELP = ["/status - Zustand von Grafikkarte, GPU-Lease, Modell, Selbsttest und Hardware-Profil",
        "/fehler - die letzten Fehler mit Erklärung",
        "/rebind - Hardware-Profil nach einem Treiber-Update neu binden (Vorschau); /rebind ja führt es aus",
        "/modelle - die Modelle und welches geladen ist",
        "/log [Zahl] - die letzten Audit-Ereignisse (höchstens 50)",
        "/plan <Auftrag> - direkt einen Plan anlegen"]
FAILURE_MARKS = ("FAILED", "DENIED", "ERROR")


def _text(value):
    return "" if value is None else str(value)


def _gpu(rt):
    try:
        gpu = (rt.hardware_manager.get_state(fresh=False).get("gpus") or [])[0]
        used, total = gpu["vram_used"], gpu["vram_total"]
        if used.get("state") == "valid" and total.get("state") == "valid":
            return {"used_gb": float(used["value"]), "total_gb": float(total["value"])}
    except Exception:
        pass
    return None


def _canary():
    try:
        state = json.loads(gpu_canary.STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if state.get("boot") != gpu_canary.boot_time(): return {"ok": None, "at": None}      # the result of an earlier Windows start does not count
    return {"ok": bool(state.get("passed")), "at": _text(state.get("at"))}


def _profile(rt):
    try:
        rt.hardware_manager.active_profile()
        return {"ok": True, "error": None, "rebind_needed": False}
    except Exception as exc:
        return {"ok": False, "error": _text(exc), "rebind_needed": _text(exc) == "active_profile_hardware_changed"}


def snapshot(hub):
    rt, holder = hub.runtime, hub.lab.holder()
    server = getattr(rt, "llama_server", None)
    status = server.status() if server is not None else {}
    lease = ({"owner": _text(holder["owner"]), "purpose": _text(holder.get("purpose")), "stale": bool(holder["stale"]),
              "mine": hub.gpu_token is not None and holder["owner"] == hub.LEASE_OWNER} if holder else None)
    return {"gpu": _gpu(rt), "lease": lease, "model": {"running": bool(status.get("running")), "model": _text(status.get("model"))},
            "canary": _canary(), "hardware_profile": _profile(rt)}


def view(hub):
    rows = status_rows(snapshot(hub))
    return {"rows": rows, "worst": max((r["state"] for r in rows), key=("ok", "warn", "bad").index)}


def explain(payload):
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str) or len(text) > 2000: raise ValueError("text_required")
    return explain_error(text)


def _events(hub, count):
    path = hub.runtime.audit.path
    lines = path.read_text(encoding="utf-8").splitlines()[-400:] if path.exists() else []
    out = []
    for line in lines:
        try: out.append(json.loads(line))
        except ValueError: continue
    return out[-count:]


def _reason(event):
    payload = event.get("payload") or {}
    rejected = payload.get("rejected") or []
    return _text(payload.get("reason") or (rejected[0].get("reason") if rejected and isinstance(rejected[0], dict) else None) or payload.get("code"))


def _failures(hub):
    lines = []
    for e in [e for e in _events(hub, 400) if any(m in _text(e.get("event_type")) for m in FAILURE_MARKS)][-8:]:
        explained = explain_error(_reason(e))
        lines.append(f"{_text(e.get('timestamp'))[11:19]} {e.get('event_type')}: {explained['title']}" + (f" - {explained['hint']}" if explained["hint"] else "") + f" [{_reason(e) or explained['code']}]")
    return lines or ["Keine Fehler in den letzten Ereignissen."]


def _rebind(hub, confirm):
    manager = hub.runtime.hardware_manager
    plan = manager.rebind_preview()
    if not plan["needed"]: return ["Das Hardware-Profil passt schon zu diesem PC, nichts zu binden."]
    lines = [f"Das Profil '{plan['active_profile']}' ist an einen früheren Stand dieses PCs gebunden ({plan['previous_fingerprint']} -> {plan['hardware_fingerprint']}). Die Grenzen bleiben unverändert."]
    if not confirm: return lines + ["Zum Binden: /rebind ja"]
    with hub.lock:
        done = manager.rebind(plan)
    return lines + ["Neu gebunden: " + ", ".join(done["rebound"])]


def _models(hub):
    view_ = hub.models_view()
    return [f"{'●' if r['loaded'] else '○'} {r['id']} ({r['model']}){'' if r['enabled'] else ' - aus'}{' - geladen' if r['loaded'] else ''}" for r in view_["recipes"]] or ["Keine Modelle."]


def command(hub, payload):
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str) or len(text) > 500: raise ValueError("text_required")
    parsed = parse_command(text)
    if parsed is None: raise ValueError("not_a_command")
    name, args = parsed["cmd"], parsed["args"]
    if name == "status": lines = [f"{r['label']}: {r['detail']}" for r in status_rows(snapshot(hub))]
    elif name == "fehler": lines = _failures(hub)
    elif name == "rebind": lines = _rebind(hub, parsed["confirm"])
    elif name == "modelle": lines = _models(hub)
    elif name == "log":
        count = int(args[0]) if args and args[0].isdigit() else 10
        lines = [f"{_text(e.get('timestamp'))[11:19]} {e.get('event_type')} ({(e.get('source') or {}).get('component')})" for e in _events(hub, max(1, min(count, 50)))]
    elif name == "hilfe": lines = HELP
    else: lines = [f"Unbekannter Befehl: /{parsed['name']}. Mit /hilfe siehst du alle Befehle."]
    return {"command": name, "lines": lines, "at": time.strftime("%H:%M:%S")}
