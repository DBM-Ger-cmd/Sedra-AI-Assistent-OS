import copy
import re
from .common import (
    FabrikFehler,
    _erlaube_nicht_zusaetzliche,
    _pruefe_enum,
    _pruefe_laenge,
    _pruefe_muster,
    _pruefe_pflicht,
    _pruefe_typ,
)

ARTIFACT_ID_MUSTER = r"^ART-[0-9A-F]{8}$"
MISSION_ID_MUSTER = r"^M-[A-Za-z0-9_-]{1,64}$"
PATH_MUSTER = r"^(?![A-Za-z]:)(?!/)(?!.*\\)(?!(.*/)?\.\.(/|$)).+$"
HASH_MUSTER = r"^[0-9a-f]{64}$"
SOURCE_COMPONENT_MUSTER = r"^[a-z][a-z0-9_.:-]{0,63}$"
DATUM_MUSTER = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?\+00:00$"


def _pruefe_integrity(integrity, field_path):
    pflicht = ["algorithm", "hash"]
    _pruefe_pflicht(pflicht, integrity, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, integrity, field_path)

    _pruefe_typ(integrity["algorithm"], "string", f"{field_path}.algorithm")
    if integrity["algorithm"] != "sha256":
        raise FabrikFehler("CONST", f"{field_path}.algorithm")

    _pruefe_typ(integrity["hash"], "string", f"{field_path}.hash")
    _pruefe_muster(integrity["hash"], HASH_MUSTER, f"{field_path}.hash")


def _pruefe_provenance(provenance, field_path):
    pflicht = ["created_at", "created_by", "source_component"]
    _pruefe_pflicht(pflicht, provenance, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, provenance, field_path)

    _pruefe_typ(provenance["created_by"], "string", f"{field_path}.created_by")
    if provenance["created_by"] != "system":
        raise FabrikFehler("CONST", f"{field_path}.created_by")

    _pruefe_typ(provenance["source_component"], "string", f"{field_path}.source_component")
    _pruefe_muster(provenance["source_component"], SOURCE_COMPONENT_MUSTER, f"{field_path}.source_component")

    _pruefe_typ(provenance["created_at"], "string", f"{field_path}.created_at")
    _pruefe_muster(provenance["created_at"], DATUM_MUSTER, f"{field_path}.created_at")


def pruefe_artifact(daten):
    daten = copy.deepcopy(daten)
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", "")

    pflicht = [
        "artifact_id", "artifact_type", "integrity", "kind",
        "mission_id", "path", "provenance", "schema_version", "status",
    ]
    _pruefe_pflicht(pflicht, daten, "")

    _pruefe_typ(daten["schema_version"], "string", "schema_version")
    if daten["schema_version"] != "1.0.0":
        raise FabrikFehler("CONST", "schema_version")

    _pruefe_typ(daten["kind"], "string", "kind")
    if daten["kind"] != "factory.artifact":
        raise FabrikFehler("CONST", "kind")

    _pruefe_typ(daten["artifact_id"], "string", "artifact_id")
    _pruefe_muster(daten["artifact_id"], ARTIFACT_ID_MUSTER, "artifact_id")

    _pruefe_typ(daten["mission_id"], "string", "mission_id")
    _pruefe_muster(daten["mission_id"], MISSION_ID_MUSTER, "mission_id")

    _pruefe_typ(daten["path"], "string", "path")
    _pruefe_laenge(daten["path"], min_len=1, max_len=400, field_path="path")
    _pruefe_muster(daten["path"], PATH_MUSTER, "path")

    _pruefe_typ(daten["artifact_type"], "string", "artifact_type")
    if daten["artifact_type"] != "file":
        raise FabrikFehler("CONST", "artifact_type")

    _pruefe_typ(daten["integrity"], "object", "integrity")
    _pruefe_integrity(daten["integrity"], "integrity")

    _pruefe_typ(daten["provenance"], "object", "provenance")
    _pruefe_provenance(daten["provenance"], "provenance")

    _pruefe_typ(daten["status"], "string", "status")
    if daten["status"] != "active":
        raise FabrikFehler("CONST", "status")

    if "job_id" in daten:
        _pruefe_typ(daten["job_id"], "string", "job_id")
        _pruefe_laenge(daten["job_id"], min_len=1, max_len=80, field_path="job_id")

    _erlaube_nicht_zusaetzliche(pflicht + ["job_id"], daten, "")
