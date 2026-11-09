import copy
import re


class FabrikFehler(ValueError):

    def __init__(self, code, field):
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


def _erlaube_nicht_zusaetzliche(felder, daten, field_path):
    if not isinstance(daten, dict):
        return
    for key in daten:
        if key not in felder:
            raise FabrikFehler("ZUSATZ", f"{field_path}.{key}")


def _pruefe_typ(daten, expected_type, field_path):
    type_map = {
        "string": str,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    if expected_type not in type_map:
        return
    expected = type_map[expected_type]
    if expected_type == "integer" and isinstance(daten, bool):
        raise FabrikFehler("TYPE", field_path)
    if not isinstance(daten, expected):
        raise FabrikFehler("TYPE", field_path)


def _pruefe_pflicht(felder, daten, field_path):
    if not isinstance(daten, dict):
        for f in felder:
            raise FabrikFehler("REQUIRED", f"{field_path}.{f}")
        return
    for f in felder:
        if f not in daten:
            raise FabrikFehler("REQUIRED", f"{field_path}.{f}")


def _pruefe_muster(wert, muster, field_path):
    if not re.match(muster, wert):
        raise FabrikFehler("PATTERN", field_path)


def _pruefe_enum(wert, erlaubte, field_path):
    if wert not in erlaubte:
        raise FabrikFehler("ENUM", field_path)


def _pruefe_laenge(wert, min_len=None, max_len=None, field_path=""):
    if min_len is not None and len(wert) < min_len:
        raise FabrikFehler("LENGTH", field_path)
    if max_len is not None and len(wert) > max_len:
        raise FabrikFehler("LENGTH", field_path)


def _pruefe_ganzzahl(wert, min_val=None, max_val=None, field_path=""):
    if min_val is not None and wert < min_val:
        raise FabrikFehler("RANGE", field_path)
    if max_val is not None and wert > max_val:
        raise FabrikFehler("RANGE", field_path)
