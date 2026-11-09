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

MISSION_ID_MUSTER = r"^M-[A-Za-z0-9_-]{1,64}$"
PROJECT_ID_MUSTER = r"^PRJ-[0-9a-f]{12}$"
WORKFLOW_ID_MUSTER = r"^WF-[a-f0-9]{24}$"
DIGEST_MUSTER = r"^[0-9a-f]{64}$"
STEP_ID_MUSTER = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"

PHASE_ERLAUBT = [
    "NEW", "UNDERSTAND", "PLAN", "READY", "EXECUTE", "VERIFY",
    "CANDIDATE_REVIEW", "REWORK", "CAPTAIN_REVIEW", "PAUSED",
    "COMPLETE", "FAILED",
]
STATUS_ERLAUBT = ["active", "closed", "archived"]
STEP_STATUS_ERLAUBT = [
    "PENDING", "RUNNING", "COMPLETED", "GATE", "WAITING", "BLOCKED", "FAILED",
]
QUALIFICATION_ERLAUBT = [
    "PENDING", "ARTIFACT_ONLY", "PREPARED_NOT_TESTED", "VERIFIED_INVENTORY",
]


def _pruefe_project_ref(ref, field_path):
    pflicht = ["project_id"]
    _pruefe_pflicht(pflicht, ref, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, ref, field_path)
    _pruefe_typ(ref["project_id"], "string", f"{field_path}.project_id")
    _pruefe_muster(ref["project_id"], PROJECT_ID_MUSTER, f"{field_path}.project_id")


def _pruefe_workflow_ref(ref, field_path):
    pflicht = ["digest", "revision", "workflow_id"]
    _pruefe_pflicht(pflicht, ref, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, ref, field_path)
    _pruefe_typ(ref["workflow_id"], "string", f"{field_path}.workflow_id")
    _pruefe_muster(ref["workflow_id"], WORKFLOW_ID_MUSTER, f"{field_path}.workflow_id")
    _pruefe_typ(ref["revision"], "integer", f"{field_path}.revision")
    _pruefe_ganzzahl(ref["revision"], min_val=1, field_path=f"{field_path}.revision")
    _pruefe_typ(ref["digest"], "string", f"{field_path}.digest")
    _pruefe_muster(ref["digest"], DIGEST_MUSTER, f"{field_path}.digest")

def _pruefe_step(step, field_path):
    pflicht = ["attempts", "status", "step_id"]
    _pruefe_pflicht(pflicht, step, field_path)
    _erlaube_nicht_zusaetzliche(pflicht + ["outcome"], step, field_path)

    _pruefe_typ(step["step_id"], "string", f"{field_path}.step_id")
    _pruefe_muster(step["step_id"], STEP_ID_MUSTER, f"{field_path}.step_id")

    _pruefe_typ(step["status"], "string", f"{field_path}.status")
    _pruefe_enum(step["status"], STEP_STATUS_ERLAUBT, f"{field_path}.status")

    _pruefe_typ(step["attempts"], "integer", f"{field_path}.attempts")
    _pruefe_ganzzahl(step["attempts"], min_val=0, field_path=f"{field_path}.attempts")

    if step["status"] == "PENDING":
        if step["attempts"] != 0:
            raise FabrikFehler("CONST", f"{field_path}.attempts")

    if step["status"] == "RUNNING":
        if step["attempts"] < 1:
            raise FabrikFehler("CONST", f"{field_path}.attempts")
        if "outcome" not in step:
            raise FabrikFehler("REQUIRED", f"{field_path}.outcome")
        _pruefe_typ(step["outcome"], "string", f"{field_path}.outcome")
        _pruefe_enum(step["outcome"], ["known", "unknown"], f"{field_path}.outcome")

    if step["status"] != "RUNNING":
        if "outcome" in step:
            if step["outcome"] != "known":
                raise FabrikFehler("CONST", f"{field_path}.outcome")


def _pruefe_result(result, field_path):
    pflicht = ["accepted", "qualification"]
    _pruefe_pflicht(pflicht, result, field_path)
    _erlaube_nicht_zusaetzliche(pflicht + ["tests_executed"], result, field_path)

    _pruefe_typ(result["qualification"], "string", f"{field_path}.qualification")
    _pruefe_enum(result["qualification"], QUALIFICATION_ERLAUBT, f"{field_path}.qualification")

    _pruefe_typ(result["accepted"], "boolean", f"{field_path}.accepted")

    if result["qualification"] == "PENDING" and result["accepted"]:
        raise FabrikFehler("CONST", f"{field_path}.accepted")

    if "tests_executed" in result:
        _pruefe_typ(result["tests_executed"], "boolean", f"{field_path}.tests_executed")


def pruefe_task_run(daten):
    daten = copy.deepcopy(daten)
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", "")

    pflicht = [
        "kind", "mission_id", "phase", "project_refs", "result",
        "schema_version", "status", "steps",
    ]
    _pruefe_pflicht(pflicht, daten, "")

    _pruefe_typ(daten["schema_version"], "string", "schema_version")
    if daten["schema_version"] != "1.0.0":
        raise FabrikFehler("CONST", "schema_version")

    _pruefe_typ(daten["kind"], "string", "kind")
    if daten["kind"] != "factory.task_run":
        raise FabrikFehler("CONST", "kind")

    _pruefe_typ(daten["mission_id"], "string", "mission_id")
    _pruefe_muster(daten["mission_id"], MISSION_ID_MUSTER, "mission_id")

    _pruefe_typ(daten["phase"], "string", "phase")
    _pruefe_enum(daten["phase"], PHASE_ERLAUBT, "phase")

    _pruefe_typ(daten["status"], "string", "status")
    _pruefe_enum(daten["status"], STATUS_ERLAUBT, "status")

    _pruefe_typ(daten["project_refs"], "array", "project_refs")
    if len(daten["project_refs"]) > 8:
        raise FabrikFehler("RANGE", "project_refs")
    for i, ref in enumerate(daten["project_refs"]):
        _pruefe_project_ref(ref, f"project_refs[{i}]")

    if "workflow_ref" in daten:
        _pruefe_typ(daten["workflow_ref"], "object", "workflow_ref")
        _pruefe_workflow_ref(daten["workflow_ref"], "workflow_ref")

    _pruefe_typ(daten["steps"], "array", "steps")
    if len(daten["steps"]) > 32:
        raise FabrikFehler("RANGE", "steps")
    for i, step in enumerate(daten["steps"]):
        _pruefe_step(step, f"steps[{i}]")

    _pruefe_typ(daten["result"], "object", "result")
    _pruefe_result(daten["result"], "result")

    if daten["phase"] in ("COMPLETE", "FAILED"):
        if daten["status"] not in ("closed", "archived"):
            raise FabrikFehler("CONST", "status")

    _erlaube_nicht_zusaetzliche(
        pflicht + ["workflow_ref"], daten, ""
    )
