"""Prüfung des Objekts approval nach approval.schema.json (kein Token im Objekt, FC-10)."""
import copy

from .common import pruefe_gegen_schema
from .schemas_data import COMMON_DEFS, SCHEMAS


def pruefe_approval(daten):
    pruefe_gegen_schema(SCHEMAS["approval"], COMMON_DEFS, daten)
    return copy.deepcopy(daten)
