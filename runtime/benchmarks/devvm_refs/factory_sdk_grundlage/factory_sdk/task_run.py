"""Prüfung des Objekts task_run (Referenz)."""
import copy
from .common import FabrikFehler, verlange_feld, verlange_objekt


def pruefe_task_run(daten):
    verlange_objekt(daten, "factory.task_run")
    obj = copy.deepcopy(daten)
    verlange_feld(obj, "mission_id")
    schritte = obj.get("steps")
    if not isinstance(schritte, list):
        raise FabrikFehler("schritte_unzulaessig", "steps")
    for i, s in enumerate(schritte):
        if not isinstance(s, dict):
            raise FabrikFehler("schritt_unzulaessig", f"steps/{i}")
        if s.get("status") == "RUNNING" and not s.get("outcome"):
            # FC-6: ein laufender Schritt darf kein Ergebnis vortäuschen; ohne outcome ist er nicht prüfbar
            raise FabrikFehler("outcome_fehlt", f"steps/{i}/outcome")
    return obj
