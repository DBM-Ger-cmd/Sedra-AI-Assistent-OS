"""Prüfung des Objekts workflow nach workflow.schema.json."""
import copy

from .common import pruefe_gegen_schema
from .schemas_data import COMMON_DEFS, SCHEMAS


def pruefe_workflow(daten):
    pruefe_gegen_schema(SCHEMAS["workflow"], COMMON_DEFS, daten)
    return copy.deepcopy(daten)
