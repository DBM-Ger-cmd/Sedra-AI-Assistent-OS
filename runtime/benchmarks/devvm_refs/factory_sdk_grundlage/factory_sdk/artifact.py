"""Prüfung des Objekts artifact (Referenz)."""
import copy
from .common import FabrikFehler, verlange_feld, verlange_hex, verlange_objekt


def pruefe_artifact(daten):
    verlange_objekt(daten, "factory.artifact")
    obj = copy.deepcopy(daten)
    verlange_feld(obj, "artifact_id")
    pfad = verlange_feld(obj, "path")
    if not isinstance(pfad, str) or pfad.startswith("/") or ".." in pfad.replace("\\", "/").split("/"):
        # FC-9: Pfad bleibt innerhalb der Mission
        raise FabrikFehler("pfad_unzulaessig", "path")
    integritaet = obj.get("integrity")
    if not isinstance(integritaet, dict) or integritaet.get("algorithm") != "sha256":
        raise FabrikFehler("integritaet_unzulaessig", "integrity")
    verlange_hex(integritaet.get("hash"), "integrity/hash")
    return obj
