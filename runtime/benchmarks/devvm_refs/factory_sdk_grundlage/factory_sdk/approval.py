"""Prüfung des Objekts approval (Referenz)."""
import copy
from .common import FabrikFehler, verlange_feld, verlange_hex, verlange_objekt


def pruefe_approval(daten):
    verlange_objekt(daten, "factory.approval")
    obj = copy.deepcopy(daten)
    verlange_feld(obj, "gate_id")
    verlange_feld(obj, "action")
    verlange_hex(obj.get("request_digest"), "request_digest")
    if "token_id" in obj:
        # FC-10: ein Token gehört nicht in das Freigabeobjekt
        raise FabrikFehler("token_verboten", "token_id")
    return obj
