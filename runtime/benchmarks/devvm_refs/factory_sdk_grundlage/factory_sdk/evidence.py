"""Prüfung des Objekts evidence (Referenz)."""
import copy
from .common import FabrikFehler, verlange_aufzaehlung, verlange_feld, verlange_objekt

ERGEBNISSE = ("PASS", "FAIL", "NOT_RUN")


def pruefe_evidence(daten):
    verlange_objekt(daten, "factory.evidence")
    obj = copy.deepcopy(daten)
    verlange_feld(obj, "claim")
    verlange_aufzaehlung(obj.get("outcome"), ERGEBNISSE, "outcome")
    if obj["outcome"] == "NOT_RUN" and not obj.get("reason"):
        # FC-8: ein nicht gelaufener Test braucht eine Begründung
        raise FabrikFehler("begruendung_fehlt", "reason")
    return obj
