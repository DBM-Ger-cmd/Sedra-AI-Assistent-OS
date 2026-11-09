"""Prüfung des Objekts artifact nach artifact.schema.json (Pfad ohne '..' und ohne absolute Angabe, FC-9)."""
import copy

from .common import pruefe_gegen_schema
from .schemas_data import COMMON_DEFS, SCHEMAS


def pruefe_artifact(daten):
    pruefe_gegen_schema(SCHEMAS["artifact"], COMMON_DEFS, daten)
    return copy.deepcopy(daten)
