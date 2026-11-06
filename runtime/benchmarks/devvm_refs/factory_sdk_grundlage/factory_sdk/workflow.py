"""Prüfung des Objekts workflow (Referenz)."""
import copy
from .common import FabrikFehler, verlange_feld, verlange_hex, verlange_objekt


def pruefe_workflow(daten):
    verlange_objekt(daten, "factory.workflow")
    obj = copy.deepcopy(daten)
    verlange_feld(obj, "workflow_id")
    verlange_hex(obj.get("digest"), "digest")
    verlange_hex(obj.get("record_digest"), "record_digest")
    ausf = obj.get("execution")
    if not isinstance(ausf, dict):
        raise FabrikFehler("execution_unzulaessig", "execution")
    if obj.get("process_model") is True and ausf.get("executable") is True:
        raise FabrikFehler("prozessmodell_nicht_ausfuehrbar", "execution/executable")
    return obj
