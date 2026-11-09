"""Prüfung des Objekts task_run nach task_run.schema.json (inkl. FC-6: RUNNING braucht outcome)."""
import copy

from .common import pruefe_gegen_schema
from .schemas_data import COMMON_DEFS, SCHEMAS


def pruefe_task_run(daten):
    pruefe_gegen_schema(SCHEMAS["task_run"], COMMON_DEFS, daten)
    return copy.deepcopy(daten)
