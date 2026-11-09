"""Prüfung des Objekts evidence nach evidence.schema.json (NOT_RUN, SKIPPED, BLOCKED brauchen reason, FC-8)."""
import copy

from .common import pruefe_gegen_schema
from .schemas_data import COMMON_DEFS, SCHEMAS


def pruefe_evidence(daten):
    pruefe_gegen_schema(SCHEMAS["evidence"], COMMON_DEFS, daten)
    return copy.deepcopy(daten)
