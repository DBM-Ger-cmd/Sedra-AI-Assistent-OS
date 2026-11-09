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

DIGEST_MUSTER = r"^[0-9a-f]{64}$"
WORKFLOW_ID_MUSTER = r"^WF-[a-f0-9]{24}$"


def _pruefe_execution(execution, field_path):
    pflicht = ["executable", "profile", "reason"]
    _pruefe_pflicht(pflicht, execution, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, execution, field_path)

    _pruefe_typ(execution["executable"], "boolean", f"{field_path}.executable")
    executable = execution["executable"]

    _pruefe_typ(execution["profile"], "string", f"{field_path}.profile")
    if execution["profile"] != "n8n-local-data-v1":
        raise FabrikFehler("CONST", f"{field_path}.profile")

    if execution["reason"] is not None and not isinstance(execution["reason"], str):
        raise FabrikFehler("TYPE", f"{field_path}.reason")
    if isinstance(execution["reason"], str):
        _pruefe_laenge(execution["reason"], max_len=200, field_path=f"{field_path}.reason")

    if executable and execution["reason"] is not None:
        raise FabrikFehler("CONST", f"{field_path}.reason")

    if not executable and not isinstance(execution["reason"], str):
        raise FabrikFehler("TYPE", f"{field_path}.reason")


def pruefe_workflow(daten):
    daten = copy.deepcopy(daten)
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", "")

    pflicht = [
        "digest", "execution", "kind", "name", "process_model",
        "record_digest", "revision", "schema_version", "workflow_id",
    ]
    _pruefe_pflicht(pflicht, daten, "")

    _pruefe_typ(daten["schema_version"], "string", "schema_version")
    if daten["schema_version"] != "1.0.0":
        raise FabrikFehler("CONST", "schema_version")

    _pruefe_typ(daten["kind"], "string", "kind")
    if daten["kind"] != "factory.workflow":
        raise FabrikFehler("CONST", "kind")

    _pruefe_typ(daten["workflow_id"], "string", "workflow_id")
    _pruefe_muster(daten["workflow_id"], WORKFLOW_ID_MUSTER, "workflow_id")

    _pruefe_typ(daten["revision"], "integer", "revision")
    _pruefe_ganzzahl(daten["revision"], min_val=1, field_path="revision")

    _pruefe_typ(daten["digest"], "string", "digest")
    _pruefe_muster(daten["digest"], DIGEST_MUSTER, "digest")

    _pruefe_typ(daten["record_digest"], "string", "record_digest")
    _pruefe_muster(daten["record_digest"], DIGEST_MUSTER, "record_digest")

    if "previous_revision" in daten:
        pr = daten["previous_revision"]
        if pr is not None:
            _pruefe_typ(pr, "integer", "previous_revision")
            _pruefe_ganzzahl(pr, min_val=1, field_path="previous_revision")

    _pruefe_typ(daten["name"], "string", "name")
    _pruefe_laenge(daten["name"], min_len=1, max_len=200, field_path="name")

    if "change_note" in daten:
        cn = daten["change_note"]
        _pruefe_typ(cn, "string", "change_note")
        _pruefe_laenge(cn, min_len=1, max_len=500, field_path="change_note")

    _pruefe_typ(daten["process_model"], "boolean", "process_model")

    _pruefe_typ(daten["execution"], "object", "execution")
    _pruefe_execution(daten["execution"], "execution")

    if daten["process_model"] and daten["execution"]["executable"]:
        raise FabrikFehler("CONST", "execution.executable")

    if daten["revision"] == 1:
        if daten.get("previous_revision") is not None:
            raise FabrikFehler("CONST", "previous_revision")

    _erlaube_nicht_zusaetzliche(pflicht + ["previous_revision", "change_note"], daten, "")
