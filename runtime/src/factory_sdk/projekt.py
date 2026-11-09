"""Prüfung des Objekts project nach project.schema.json."""
import copy

from .common import pruefe_gegen_schema
from .schemas_data import COMMON_DEFS, SCHEMAS


def pruefe_project(daten):
    pruefe_gegen_schema(SCHEMAS["project"], COMMON_DEFS, daten)
    return copy.deepcopy(daten)
