"""Gemeinsame Bausteine des Factory SDK: Fehlerklasse und ein Prüfer für die Schema-Dialekt-Teilmenge.

Nur Python-Standardbibliothek. Die Schemata liegen als Daten in schemas_data.py (kein Dateizugriff).
Ein Fehler ist FabrikFehler(code, field): code beschreibt die verletzte Regel, field den Pfad im Objekt.
"""
import copy
import re

URN_COMMON = "urn:sedra:factory-sdk:1:common#/$defs/"


class FabrikFehler(ValueError):
    def __init__(self, code, field=""):
        self.code = code
        self.field = field
        super().__init__(f"{code} @ {field or '(Wurzel)'}")


class _Verletzt(Exception):
    def __init__(self, code, path):
        self.code = code
        self.path = path
        super().__init__(code)


def _art(wert):
    if wert is None:
        return "null"
    if isinstance(wert, bool):
        return "boolean"
    if isinstance(wert, int):
        return "integer"
    if isinstance(wert, float):
        return "number"
    if isinstance(wert, str):
        return "string"
    if isinstance(wert, list):
        return "array"
    if isinstance(wert, dict):
        return "object"
    return "unknown"


def _gleich(a, b):
    """JSON-Gleichheit: True ist nicht 1, 1 ist 1.0."""
    if _art(a) != _art(b):
        if {_art(a), _art(b)} <= {"integer", "number"}:
            return a == b
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_gleich(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_gleich(a[k], b[k]) for k in a)
    return a == b


def _join(pfad, teil):
    if not pfad:
        return teil
    if teil.startswith("["):
        return pfad + teil
    return pfad + "." + teil


class _Pruefer:
    def __init__(self, defs):
        self.defs = defs

    def aufloesen(self, schema):
        if isinstance(schema, dict) and "$ref" in schema:
            name = schema["$ref"]
            if not name.startswith(URN_COMMON):
                raise _Verletzt("REF_UNBEKANNT", "")
            ziel = self.defs.get(name[len(URN_COMMON):])
            if ziel is None:
                raise _Verletzt("REF_UNBEKANNT", "")
            rest = {k: v for k, v in schema.items() if k != "$ref"}
            return self.aufloesen_zusammen(ziel, rest)
        return schema

    def aufloesen_zusammen(self, a, b):
        if not b:
            return a
        merged = dict(a)
        merged.update(b)
        return merged

    def pruefe(self, schema, wert, pfad=""):
        schema = self.aufloesen(schema)
        if not isinstance(schema, dict):
            return
        self._typ(schema, wert, pfad)
        self._wert(schema, wert, pfad)
        self._zusammensetzung(schema, wert, pfad)
        if isinstance(wert, dict):
            self._objekt(schema, wert, pfad)
        if isinstance(wert, list):
            self._liste(schema, wert, pfad)

    def _typ(self, schema, wert, pfad):
        if "type" not in schema:
            return
        erlaubt = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        art = _art(wert)
        for e in erlaubt:
            if e == art or (e == "number" and art in ("integer", "number")):
                return
        raise _Verletzt("TYPE", pfad)

    def _wert(self, schema, wert, pfad):
        if "const" in schema and not _gleich(schema["const"], wert):
            raise _Verletzt("CONST", pfad)
        if "enum" in schema and not any(_gleich(e, wert) for e in schema["enum"]):
            raise _Verletzt("ENUM", pfad)
        if isinstance(wert, str):
            if "pattern" in schema and re.search(schema["pattern"], wert) is None:
                raise _Verletzt("PATTERN", pfad)
            if "minLength" in schema and len(wert) < schema["minLength"]:
                raise _Verletzt("MIN_LENGTH", pfad)
            if "maxLength" in schema and len(wert) > schema["maxLength"]:
                raise _Verletzt("MAX_LENGTH", pfad)
        if isinstance(wert, (int, float)) and not isinstance(wert, bool):
            if "minimum" in schema and wert < schema["minimum"]:
                raise _Verletzt("MINIMUM", pfad)
            if "maximum" in schema and wert > schema["maximum"]:
                raise _Verletzt("MAXIMUM", pfad)
        if isinstance(wert, list):
            if "maxItems" in schema and len(wert) > schema["maxItems"]:
                raise _Verletzt("MAX_ITEMS", pfad)
            if "minItems" in schema and len(wert) < schema["minItems"]:
                raise _Verletzt("MIN_ITEMS", pfad)

    def _zusammensetzung(self, schema, wert, pfad):
        for teil in schema.get("allOf", []):
            self.pruefe(teil, wert, pfad)
        if "oneOf" in schema:
            treffer = 0
            for teil in schema["oneOf"]:
                try:
                    self.pruefe(teil, wert, pfad)
                    treffer += 1
                except _Verletzt:
                    pass
            if treffer != 1:
                raise _Verletzt("ONE_OF", pfad)
        if "anyOf" in schema:
            ok = False
            for teil in schema["anyOf"]:
                try:
                    self.pruefe(teil, wert, pfad)
                    ok = True
                    break
                except _Verletzt:
                    pass
            if not ok:
                raise _Verletzt("ANY_OF", pfad)
        if "not" in schema:
            try:
                self.pruefe(schema["not"], wert, pfad)
            except _Verletzt:
                pass
            else:
                raise _Verletzt("NOT", pfad)
        if "if" in schema:
            try:
                self.pruefe(schema["if"], wert, pfad)
                wenn = True
            except _Verletzt:
                wenn = False
            if wenn and "then" in schema:
                self.pruefe(schema["then"], wert, pfad)
            if not wenn and "else" in schema:
                self.pruefe(schema["else"], wert, pfad)

    def _objekt(self, schema, wert, pfad):
        eigene = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in wert:
                raise _Verletzt("REQUIRED", _join(pfad, name))
        if schema.get("additionalProperties") is False:
            for name in wert:
                if name not in eigene:
                    raise _Verletzt("ADDITIONAL_FIELD", _join(pfad, name))
        for name, sub in eigene.items():
            if name in wert:
                self.pruefe(sub, wert[name], _join(pfad, name))

    def _liste(self, schema, wert, pfad):
        if "items" in schema:
            for i, eintrag in enumerate(wert):
                self.pruefe(schema["items"], eintrag, f"{pfad}[{i}]")


def pruefe_gegen_schema(schema, defs, daten):
    """Prüft daten gegen ein Schema. Wirft FabrikFehler mit code und field, sonst nichts."""
    try:
        _Pruefer(defs).pruefe(schema, copy.deepcopy(daten), "")
    except _Verletzt as exc:
        raise FabrikFehler(exc.code, exc.path) from None


def _pflicht(daten, feld, pfad=None):
    if not isinstance(daten, dict):
        raise FabrikFehler("TYPE", pfad or "")
    if feld not in daten:
        raise FabrikFehler("REQUIRED", feld)
    return daten[feld]
