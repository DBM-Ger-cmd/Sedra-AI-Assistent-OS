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

DATUM_MUSTER = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?\+00:00$"
PROJECT_ID_MUSTER = r"^PRJ-[0-9a-f]{12}$"
WORKSPACE_PATH_MUSTER = r"^projects/PRJ-[0-9a-f]{12}$"
HARNESS_PROJECT_ID_MUSTER = r"^[a-z0-9][a-z0-9-]{0,39}$"


def _pruefe_backing_form1(backing, field_path):
    pflicht = ["created_at", "project_id", "qualification", "store", "workspace_path"]
    _pruefe_pflicht(pflicht, backing, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, backing, field_path)
    _pruefe_typ(backing["store"], "string", f"{field_path}.store")
    if backing.get("store") != "project_registry":
        raise FabrikFehler("CONST", f"{field_path}.store")
    _pruefe_typ(backing["project_id"], "string", f"{field_path}.project_id")
    _pruefe_muster(backing["project_id"], PROJECT_ID_MUSTER, f"{field_path}.project_id")
    _pruefe_typ(backing["workspace_path"], "string", f"{field_path}.workspace_path")
    _pruefe_muster(backing["workspace_path"], WORKSPACE_PATH_MUSTER, f"{field_path}.workspace_path")
    _pruefe_typ(backing["qualification"], "string", f"{field_path}.qualification")
    if backing.get("qualification") != "MANAGED_WORKSPACE_NOT_VM":
        raise FabrikFehler("CONST", f"{field_path}.qualification")
    _pruefe_typ(backing["created_at"], "string", f"{field_path}.created_at")
    _pruefe_muster(backing["created_at"], DATUM_MUSTER, f"{field_path}.created_at")


def _pruefe_backing_form2(backing, field_path):
    pflicht = ["project_id", "store"]
    _pruefe_pflicht(pflicht, backing, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, backing, field_path)
    _pruefe_typ(backing["store"], "string", f"{field_path}.store")
    if backing.get("store") != "harness_projekt":
        raise FabrikFehler("CONST", f"{field_path}.store")
    _pruefe_typ(backing["project_id"], "string", f"{field_path}.project_id")
    _pruefe_muster(backing["project_id"], HARNESS_PROJECT_ID_MUSTER, f"{field_path}.project_id")


def _pruefe_backing(backing, field_path):
    if not isinstance(backing, dict):
        raise FabrikFehler("TYPE", field_path)
    store = backing.get("store")
    if store == "project_registry":
        _pruefe_backing_form1(backing, field_path)
    elif store == "harness_projekt":
        _pruefe_backing_form2(backing, field_path)
    else:
        raise FabrikFehler("ENUM", f"{field_path}.store")


def pruefe_project(daten):
    daten = copy.deepcopy(daten)
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", "")

    pflicht = ["backing", "display_name", "kind", "schema_version", "status"]
    _pruefe_pflicht(pflicht, daten, "")

    _pruefe_typ(daten["schema_version"], "string", "schema_version")
    if daten["schema_version"] != "1.0.0":
        raise FabrikFehler("CONST", "schema_version")

    _pruefe_typ(daten["kind"], "string", "kind")
    if daten["kind"] != "factory.project":
        raise FabrikFehler("CONST", "kind")

    _pruefe_backing(daten["backing"], "backing")

    _pruefe_typ(daten["display_name"], "string", "display_name")
    _pruefe_laenge(daten["display_name"], min_len=1, max_len=80, field_path="display_name")

    _pruefe_typ(daten["status"], "string", "status")
    _pruefe_enum(daten["status"], ["ACTIVE"], "status")

    _erlaube_nicht_zusaetzliche(pflicht, daten, "")
