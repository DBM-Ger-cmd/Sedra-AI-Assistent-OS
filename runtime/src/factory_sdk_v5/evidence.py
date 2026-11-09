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

EVIDENCE_DIGEST_MUSTER = r"^[0-9a-f]{64}$"
EVENT_ID_MUSTER = r"^EVT-[0-9]{6,}$"
EVENT_HASH_MUSTER = r"^[0-9a-f]{64}$"
MISSION_ID_MUSTER = r"^M-[A-Za-z0-9_-]{1,64}$"
ARTIFACT_ID_MUSTER = r"^ART-[0-9A-F]{8}$"
HASH_MUSTER = r"^[0-9a-f]{64}$"
DATUM_MUSTER = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?\+00:00$"
SUBJECT_KIND_ERLAUBT = ["factory.task_run", "factory.artifact", "factory.workflow"]
OUTCOME_ERLAUBT = ["PASS", "FAIL", "SKIPPED", "NOT_RUN", "BLOCKED"]


def _pruefe_subject(subject, field_path):
    pflicht = ["id", "kind"]
    _pruefe_pflicht(pflicht, subject, field_path)
    _erlaube_nicht_zusaetzliche(pflicht + ["revision"], subject, field_path)

    _pruefe_typ(subject["kind"], "string", f"{field_path}.kind")
    _pruefe_enum(subject["kind"], SUBJECT_KIND_ERLAUBT, f"{field_path}.kind")

    _pruefe_typ(subject["id"], "string", f"{field_path}.id")
    _pruefe_laenge(subject["id"], min_len=1, max_len=80, field_path=f"{field_path}.id")

    if "revision" in subject:
        _pruefe_typ(subject["revision"], "integer", f"{field_path}.revision")
        _pruefe_ganzzahl(subject["revision"], min_val=1, field_path=f"{field_path}.revision")

    if subject["kind"] == "factory.task_run":
        if not isinstance(subject["id"], str):
            raise FabrikFehler("TYPE", f"{field_path}.id")
        _pruefe_muster(subject["id"], r"^M-[A-Za-z0-9_-]{1,64}$", f"{field_path}.id")

    if subject["kind"] == "factory.workflow":
        if "revision" not in subject:
            raise FabrikFehler("REQUIRED", f"{field_path}.revision")


def _pruefe_source_form1(source, field_path):
    pflicht = ["event_hash", "event_id", "type"]
    _pruefe_pflicht(pflicht, source, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, source, field_path)

    _pruefe_typ(source["type"], "string", f"{field_path}.type")
    if source["type"] != "audit_event":
        raise FabrikFehler("CONST", f"{field_path}.type")

    _pruefe_typ(source["event_id"], "string", f"{field_path}.event_id")
    _pruefe_muster(source["event_id"], EVENT_ID_MUSTER, f"{field_path}.event_id")

    _pruefe_typ(source["event_hash"], "string", f"{field_path}.event_hash")
    _pruefe_muster(source["event_hash"], EVENT_HASH_MUSTER, f"{field_path}.event_hash")


def _pruefe_source_form2(source, field_path):
    pflicht = ["index", "mission_id", "type"]
    _pruefe_pflicht(pflicht, source, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, source, field_path)

    _pruefe_typ(source["type"], "string", f"{field_path}.type")
    if source["type"] != "verification":
        raise FabrikFehler("CONST", f"{field_path}.type")

    _pruefe_typ(source["mission_id"], "string", f"{field_path}.mission_id")
    _pruefe_muster(source["mission_id"], MISSION_ID_MUSTER, f"{field_path}.mission_id")

    _pruefe_typ(source["index"], "integer", f"{field_path}.index")
    _pruefe_ganzzahl(source["index"], min_val=0, field_path=f"{field_path}.index")


def _pruefe_source_form3(source, field_path):
    pflicht = ["artifact_id", "hash", "type"]
    _pruefe_pflicht(pflicht, source, field_path)
    _erlaube_nicht_zusaetzliche(pflicht, source, field_path)

    _pruefe_typ(source["type"], "string", f"{field_path}.type")
    if source["type"] != "test_report":
        raise FabrikFehler("CONST", f"{field_path}.type")

    _pruefe_typ(source["artifact_id"], "string", f"{field_path}.artifact_id")
    _pruefe_muster(source["artifact_id"], ARTIFACT_ID_MUSTER, f"{field_path}.artifact_id")

    _pruefe_typ(source["hash"], "string", f"{field_path}.hash")
    _pruefe_muster(source["hash"], HASH_MUSTER, f"{field_path}.hash")


def _pruefe_source(source, field_path):
    if not isinstance(source, dict):
        raise FabrikFehler("TYPE", field_path)

    typ = source.get("type")
    if typ == "audit_event":
        _pruefe_source_form1(source, field_path)
    elif typ == "verification":
        _pruefe_source_form2(source, field_path)
    elif typ == "test_report":
        _pruefe_source_form3(source, field_path)
    else:
        raise FabrikFehler("ENUM", f"{field_path}.type")


def pruefe_evidence(daten):
    daten = copy.deepcopy(daten)
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", "")

    pflicht = [
        "claim", "evidence_digest", "kind", "outcome",
        "recorded_at", "schema_version", "source", "subject",
    ]
    _pruefe_pflicht(pflicht, daten, "")

    _pruefe_typ(daten["schema_version"], "string", "schema_version")
    if daten["schema_version"] != "1.0.0":
        raise FabrikFehler("CONST", "schema_version")

    _pruefe_typ(daten["kind"], "string", "kind")
    if daten["kind"] != "factory.evidence":
        raise FabrikFehler("CONST", "kind")

    _pruefe_typ(daten["evidence_digest"], "string", "evidence_digest")
    _pruefe_muster(daten["evidence_digest"], EVIDENCE_DIGEST_MUSTER, "evidence_digest")

    _pruefe_typ(daten["subject"], "object", "subject")
    _pruefe_subject(daten["subject"], "subject")

    _pruefe_typ(daten["source"], "object", "source")
    _pruefe_source(daten["source"], "source")

    _pruefe_typ(daten["claim"], "string", "claim")
    _pruefe_laenge(daten["claim"], min_len=1, max_len=500, field_path="claim")

    _pruefe_typ(daten["outcome"], "string", "outcome")
    _pruefe_enum(daten["outcome"], OUTCOME_ERLAUBT, "outcome")

    if "reason" in daten:
        _pruefe_typ(daten["reason"], "string", "reason")
        _pruefe_laenge(daten["reason"], min_len=1, max_len=500, field_path="reason")

    _pruefe_typ(daten["recorded_at"], "string", "recorded_at")
    _pruefe_muster(daten["recorded_at"], DATUM_MUSTER, "recorded_at")

    if daten["outcome"] in ("SKIPPED", "NOT_RUN", "BLOCKED"):
        if "reason" not in daten:
            raise FabrikFehler("REQUIRED", "reason")

    _erlaube_nicht_zusaetzliche(pflicht + ["reason"], daten, "")
