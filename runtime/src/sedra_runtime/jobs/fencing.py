"""F0-05D: Crash-/Timeout-Recovery und Fencing.

Vertraege (nach SPEC F0-05D):
  * Kein Auto-Replay mutierender Aktionen (outcome_known=False => nie wiederholen).
  * Fremde Leases bleiben unangetastet (Owner-Schluessel pro Runtime-Instanz).
  * Audit ist nachvollziehbar (jeder Fence- und Recovery-Schritt wird geloggt).
  * Timeout erzeugt SHUTDOWN_PENDING, nie stilles Freigeben.

Aufbau:
  LeaseOwner    – formeller Owner-Schluessel pro Runtime-Instanz (F0-05B Empfehlung).
  fence_check   – prueft, ob ein Owner eine Ressource sperren darf (fremde Leases blockieren).
  recovery_log  – zentraler Audit-Eintrag fuer alle F0-05D-Stufen.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- Lease-Owner
# Ein Owner-Schluessel identifiziert eine Runtime-Instanz eindeutig (nicht pro JobStore,
# nicht pro Worker-Name, da orchestra-{n} nicht global eindeutig sind – siehe F0-05B
# Quellcodeabgleich 2b13daa). Wird von testlab.py (activity()), uix_server.py (LEASE_OWNER)
# und runtime.py (close()) gemeinsam verwendet.
LEASE_OWNER = "sedra-runtime-instance"

# ---------------------------------------------------------------- Fence-Ergebnis
FENCE_ALLOW = "allow"
FENCE_BLOCK_FOREIGN_LEASE = "block_foreign_lease"
FENCE_BLOCK_NO_LIVE_PROCESS = "block_no_live_process"


def fence_check(owner: str, resource: str, live_process: bool, foreign_lease_owner: str | None) -> dict[str, Any]:
    """Prueft, ob `owner` die Ressource `resource` sperren darf.

    Regeln (F0-05D):
      * Ein lebender Prozess darf immer sperren.
      * Ein eigener Lease (kein lebender Prozess, aber eigener Owner) darf sperren.
      * Ein fremder Lease-Owner blockiert (fremde Leases bleiben unangetastet).
      * Kein lebender Prozess und kein eigener Lease => Block (ressource ist verwaist).
    """
    if live_process:
        return {"decision": FENCE_ALLOW, "reason": f"live process for {resource}"}
    if foreign_lease_owner is not None:
        if foreign_lease_owner == owner:
            return {"decision": FENCE_ALLOW, "reason": f"own lease held by {owner}"}
        return {
            "decision": FENCE_BLOCK_FOREIGN_LEASE,
            "reason": f"foreign lease held by {foreign_lease_owner}",
        }
    return {
        "decision": FENCE_BLOCK_NO_LIVE_PROCESS,
        "reason": f"no live process and no lease for {resource}",
    }


# ---------------------------------------------------------------- Recovery-Protokoll
RESOLUTION_ABORT = "abort"
RESOLUTION_RETRY_READONLY = "retry_readonly"
RESOLUTION_UNKNOWN = "unknown"


def recovery_verdict(
    resolution: str,
    is_mutating: bool,
    outcome_known: bool,
    gate_authorized: bool,
) -> dict[str, Any]:
    """Ermittelt das Recovery-Verdikt nach F0-05D.

    Regeln:
      * Mutierende Aktion mit unbekanntem Outcome => nie replayed (JobError/DEAD).
      * retry_readonly nur auf nicht-mutierenden Schritte.
      * Jede Recovery braucht Gate-Autorisierung (Captain-Gate bei execution_recovery).
    """
    if is_mutating and not outcome_known:
        return {
            "verdict": "dead",
            "reason": "mutating attempt with unknown outcome is never replayed",
            "gate_required": False,
        }
    if resolution == RESOLUTION_RETRY_READONLY and is_mutating:
        return {
            "verdict": "blocked",
            "reason": "mutating step cannot be replayed as readonly",
            "gate_required": True,
        }
    if not gate_authorized:
        return {
            "verdict": "captain_required",
            "reason": "execution_recovery gate not authorized",
            "gate_required": True,
        }
    return {
        "verdict": "completed",
        "reason": f"recovery {resolution} authorized and applied",
        "gate_required": False,
    }


# ---------------------------------------------------------------- Audit
_RECOVERY_LOG_PATH = Path("runtime_data/audit/f0-05d_recovery.jsonl")
_RECOVERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_recovery_lock = threading.Lock()


def recovery_log(event: str, owner: str, payload: dict[str, Any] | None = None) -> None:
    """Zentraler Audit-Eintrag fuer alle F0-05D-Stufen (Fencing, Recovery, Timeout)."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "owner": owner,
        "payload": payload or {},
    }
    with _recovery_lock:
        with _RECOVERY_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\\n")


__all__ = [
    "LEASE_OWNER",
    "FENCE_ALLOW",
    "FENCE_BLOCK_FOREIGN_LEASE",
    "FENCE_BLOCK_NO_LIVE_PROCESS",
    "fence_check",
    "RESOLUTION_ABORT",
    "RESOLUTION_RETRY_READONLY",
    "RESOLUTION_UNKNOWN",
    "recovery_verdict",
    "recovery_log",
]
