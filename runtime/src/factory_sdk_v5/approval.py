import copy
import re
from .common import (
    FabrikFehler,
    _erlaube_nicht_zusaetzliche,
    _pruefe_enum,
    _pruefe_ganzzahl,
    _pruefe_laenge,
    _pruefe_muster,
    _pruefe_pflicht,
    _pruefe_typ,
)

GATE_ID_MUSTER = r"^HG-[0-9A-F]{8}$"
MISSION_ID_MUSTER = r"^M-[A-Za-z0-9_-]{1,64}$"
REQUEST_KIND_MUSTER = r"^[a-z][a-z0-9_]{1,39}$"
ACTION_MUSTER = r"^[A-Za-z][A-Za-z0-9_]{1,63}$"


def _pruefe_request_digest(request_digest, field_path):
    if not isinstance(request_digest, (dict, str)):
        raise FabrikFehler("TYPE", field_path)


def pruefe_approval(daten):
    daten = copy.deepcopy(daten)
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", "")

    pflicht = [
        "action", "decision", "gate_id", "kind", "mission_id",
        "request_digest", "risks", "rollback_available",
        "schema_version", "single_use", "status", "targets",
    ]
    _pruefe_pflicht(pflicht, daten, "")

    _pruefe_typ(daten["schema_version"], "string", "schema_version")
    if daten["schema_version"] != "1.0.0":
        raise FabrikFehler("CONST", "schema_version")

    _pruefe_typ(daten["kind"], "string", "kind")
    if daten["kind"] != "factory.approval":
        raise FabrikFehler("CONST", "kind")

    _pruefe_typ(daten["gate_id"], "string", "gate_id")
    _pruefe_muster(daten["gate_id"], GATE_ID_MUSTER, "gate_id")

    _pruefe_typ(daten["mission_id"], "string", "mission_id")
    _pruefe_muster(daten["mission_id"], MISSION_ID_MUSTER, "mission_id")

    if "request_kind" in daten:
        _pruefe_typ(daten["request_kind"], "string", "request_kind")
        _pruefe_muster(daten["request_kind"], REQUEST_KIND_MUSTER, "request_kind")

    _pruefe_typ(daten["action"], "string", "action")
    _pruefe_muster(daten["action"], ACTION_MUSTER, "action")

    _pruefe_typ(daten["targets"], "array", "targets")
    if len(daten["targets"]) > 16:
        raise FabrikFehler("RANGE", "targets")

    _pruefe_request_digest(daten["request_digest"], "request_digest")

    _pruefe_typ(daten["risks"], "array", "risks")
    if len(daten["risks"]) > 16:
        raise FabrikFehler("RANGE", "risks")

    _pruefe_typ(daten["rollback_available"], "boolean", "rollback_available")

    _pruefe_typ(daten["status"], "string", "status")
    _pruefe_enum(daten["status"], ["pending", "resolved"], "status")

    if daten["decision"] is not None:
        _pruefe_typ(daten["decision"], "string", "decision")
        _pruefe_enum(daten["decision"], ["APPROVE_ONCE", "DENY"], "decision")

    _pruefe_typ(daten["single_use"], "boolean", "single_use")
    if daten["single_use"] is not True:
        raise FabrikFehler("CONST", "single_use")

    if daten["status"] == "pending":
        if daten["decision"] is not None:
            raise FabrikFehler("CONST", "decision")
        if daten.get("decided_at") is not None:
            raise FabrikFehler("CONST", "decided_at")

    if daten["status"] == "resolved":
        if daten["decision"] not in ("APPROVE_ONCE", "DENY"):
            raise FabrikFehler("CONST", "decision")
        if "decided_at" not in daten:
            raise FabrikFehler("REQUIRED", "decided_at")
        if not isinstance(daten["decided_at"], str):
            raise FabrikFehler("TYPE", "decided_at")

    _erlaube_nicht_zusaetzliche(
        pflicht + ["request_kind", "decided_at"], daten, ""
    )
