"""Prüfung des Objekts project (Referenz)."""
import copy
from .common import FabrikFehler, verlange_aufzaehlung, verlange_feld, verlange_objekt

STATUS = ("ACTIVE", "PAUSED")


def pruefe_project(daten):
    verlange_objekt(daten, "factory.project")
    obj = copy.deepcopy(daten)
    verlange_feld(obj, "display_name")
    verlange_aufzaehlung(obj.get("status"), STATUS, "status")
    backing = verlange_feld(obj, "backing")
    if not isinstance(backing, dict):
        raise FabrikFehler("backing_unzulaessig", "backing")
    verlange_feld(backing, "project_id")
    return obj
