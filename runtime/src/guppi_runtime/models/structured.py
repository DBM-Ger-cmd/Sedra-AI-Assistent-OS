"""Strukturierte Antworten vom lokalen Modell (Build 17, RECHERCHE_SHELL_CREATOR Empfehlung 1).

Ein Aufruf mit `schema=` bekommt eine Antwort, die dem JSON-Schema entspricht – oder einen Fehler, der sagt, warum nicht:
  1. Der Server erzwingt das Schema selbst (`response_format: json_schema` – LM Studio, llama-server, Ollama über /v1).
  2. Das Schema steht zusätzlich im Prompt (llama.cpp: die Grammatik ändert die Ausgabe, nicht das Wissen des Modells).
  3. Die Antwort wird hier geprüft; passt sie nicht, geht der Fehler als Satz zurück an das Modell – höchstens drei Runden.

Geprüft wird die **flache Teilmenge**, die llama.cpp sicher in eine Grammatik übersetzt (grammars/README): type, properties, required,
additionalProperties, enum, const, items, minItems/maxItems, minLength/maxLength, pattern (^…$), minimum/maximum (integer). Kein
$ref, kein oneOf/anyOf neben properties, kein patternProperties, keine Formate. Ein Schema außerhalb dieser Teilmenge wird vor dem
ersten Aufruf abgewiesen – damit niemand auf eine Erzwingung vertraut, die der Server still überspringt.

Kein jsonschema-Paket: das Paket hängt nur von PyYAML ab, und die Teilmenge ist klein genug, um sie zu kennen.
"""
from __future__ import annotations

import json
import re

MAX_ROUNDS = 3
SUPPORTED = frozenset({'type', 'properties', 'required', 'additionalProperties', 'enum', 'const', 'items', 'minItems', 'maxItems',
                       'minLength', 'maxLength', 'pattern', 'minimum', 'maximum', 'description', 'title', '$schema', 'default'})
TYPES = {'object': dict, 'array': list, 'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'null': type(None)}
UNSUPPORTED = ('$ref', 'oneOf', 'anyOf', 'allOf', 'not', 'patternProperties', 'format', 'uniqueItems', 'prefixItems', 'if', 'then',
               'else', 'dependentRequired', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf', 'additionalItems', 'contains')
_FENCE = re.compile(r'^\s*```(?:json)?\s*(.*?)\s*```\s*$', re.DOTALL)


class SchemaError(ValueError):
    """Das Schema selbst taugt nicht – gesagt vor dem ersten Aufruf."""


def check_schema(schema, path='$'):
    """Weist alles ab, was die Teilmenge verlässt. Gibt das Schema zurück, wenn es in Ordnung ist."""
    if not isinstance(schema, dict) or not schema:
        raise SchemaError(f'{path}: ein Schema ist ein nicht leeres Objekt')
    for key in schema:
        if key in UNSUPPORTED:
            raise SchemaError(f'{path}: „{key}“ wird nicht unterstützt (llama.cpp übersetzt es nicht oder nur still falsch)')
        if key not in SUPPORTED:
            raise SchemaError(f'{path}: unbekannter Schlüssel „{key}“')
    t = schema.get('type')
    if isinstance(t, list):
        # Nullable (27.10.2026): ["string", "null"] – genau ein Typ plus null; llama.cpp übersetzt das in eine Grammatik. Der Rest wird für den Haupttyp geprüft.
        if len(t) != 2 or 'null' not in t or t[0] == t[1] or any(not isinstance(x, str) or x not in TYPES for x in t):
            raise SchemaError(f'{path}: eine Typliste ist nur „einer von {sorted(x for x in TYPES if x != "null")} plus null“ erlaubt')
        return check_schema(dict(schema, type=next(x for x in t if x != 'null')), path) and schema
    if not isinstance(t, str) or t not in TYPES:
        raise SchemaError(f'{path}: „type“ muss genau einer von {sorted(TYPES)} sein')
    if t == 'object':
        props = schema.get('properties')
        if not isinstance(props, dict) or not props:
            raise SchemaError(f'{path}: ein Objekt braucht „properties“')
        for name, sub in props.items():
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
                raise SchemaError(f'{path}: Feldname „{name}“ – nur Buchstaben, Ziffern, Unterstrich')
            check_schema(sub, f'{path}.{name}')
        req = schema.get('required', [])
        if not isinstance(req, list) or any(r not in props for r in req):
            raise SchemaError(f'{path}: „required“ nennt ein Feld, das es nicht gibt')
        if schema.get('additionalProperties', False) is not False:
            raise SchemaError(f'{path}: „additionalProperties“ muss false sein (llama.cpp erzeugt sonst kaputte Schlüssel)')
    elif t == 'array':
        if 'items' not in schema:
            raise SchemaError(f'{path}: ein Array braucht „items“')
        check_schema(schema['items'], f'{path}[]')
        for k in ('minItems', 'maxItems'):
            if k in schema and (type(schema[k]) is not int or schema[k] < 0):
                raise SchemaError(f'{path}: „{k}“ muss eine Zahl ≥ 0 sein')
    elif t == 'string':
        p = schema.get('pattern')
        if p is not None:
            if not isinstance(p, str) or not p.startswith('^') or not p.endswith('$'):
                raise SchemaError(f'{path}: „pattern“ muss mit ^ beginnen und mit $ enden')
            try:
                re.compile(p)
            except re.error as exc:
                raise SchemaError(f'{path}: „pattern“ ist kein gültiger Ausdruck ({exc})')
    elif t == 'number' and ('minimum' in schema or 'maximum' in schema):
        raise SchemaError(f'{path}: minimum/maximum gelten nur für integer (llama.cpp)')
    if 'enum' in schema and (not isinstance(schema['enum'], list) or not schema['enum']):
        raise SchemaError(f'{path}: „enum“ muss eine nicht leere Liste sein')
    return schema


def validate(value, schema, path='$'):
    """Prüft einen Wert gegen das (schon geprüfte) Schema. Gibt Sätze zurück – leer heißt gültig."""
    errors = []
    t = schema['type']
    if isinstance(t, list):                      # nullable: null ist erlaubt, sonst gilt der Haupttyp
        if value is None:
            return []
        return validate(value, dict(schema, type=next(x for x in t if x != 'null')), path)
    if t == 'integer' and (type(value) is not int):
        return [f'{path}: muss eine ganze Zahl sein']
    if t == 'number' and (isinstance(value, bool) or not isinstance(value, (int, float))):
        return [f'{path}: muss eine Zahl sein']
    if t not in ('integer', 'number') and not isinstance(value, TYPES[t]):
        return [f'{path}: muss vom Typ {t} sein']
    if t == 'boolean' and not isinstance(value, bool) or (t in ('integer', 'number') and isinstance(value, bool)):
        return [f'{path}: muss vom Typ {t} sein']
    if 'const' in schema and value != schema['const']:
        errors.append(f'{path}: muss genau {json.dumps(schema["const"], ensure_ascii=False)} sein')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: muss einer von {json.dumps(schema["enum"], ensure_ascii=False)} sein')
    if t == 'object':
        props = schema['properties']
        for r in schema.get('required', []):
            if r not in value:
                errors.append(f'{path}: Feld „{r}“ fehlt')
        for k, v in value.items():
            if k not in props:
                errors.append(f'{path}: Feld „{k}“ gibt es nicht')
            else:
                errors += validate(v, props[k], f'{path}.{k}')
    elif t == 'array':
        n = len(value)
        if 'minItems' in schema and n < schema['minItems']:
            errors.append(f'{path}: mindestens {schema["minItems"]} Einträge')
        if 'maxItems' in schema and n > schema['maxItems']:
            errors.append(f'{path}: höchstens {schema["maxItems"]} Einträge')
        for i, item in enumerate(value):
            errors += validate(item, schema['items'], f'{path}[{i}]')
    elif t == 'string':
        if 'minLength' in schema and len(value) < schema['minLength']:
            errors.append(f'{path}: mindestens {schema["minLength"]} Zeichen')
        if 'maxLength' in schema and len(value) > schema['maxLength']:
            errors.append(f'{path}: höchstens {schema["maxLength"]} Zeichen')
        if 'pattern' in schema and re.fullmatch(schema['pattern'][1:-1], value) is None:
            errors.append(f'{path}: passt nicht zum Muster {schema["pattern"]}')
    elif t == 'integer':
        if 'minimum' in schema and value < schema['minimum']:
            errors.append(f'{path}: mindestens {schema["minimum"]}')
        if 'maximum' in schema and value > schema['maximum']:
            errors.append(f'{path}: höchstens {schema["maximum"]}')
    return errors


def parse(text):
    """Nimmt die Antwort, entfernt einen Code-Zaun, lädt JSON. (Wert, Fehlersatz oder None)."""
    if not isinstance(text, str) or not text.strip():
        return None, 'Die Antwort war leer'
    m = _FENCE.match(text)
    body = m.group(1) if m else text.strip()
    try:
        return json.loads(body), None
    except json.JSONDecodeError as exc:
        return None, f'Die Antwort ist kein gültiges JSON ({exc.msg} an Stelle {exc.pos})'


def response_format(schema, name='antwort'):
    """Das Feld, das OpenAI-kompatible Server (LM Studio, llama-server, Ollama /v1) zum Erzwingen nehmen."""
    return {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}}


def hint(schema):
    """Der Satz im Prompt – die Grammatik erzwingt die Form, aber das Modell muss sie kennen, um sie zu füllen."""
    return ('Antworte ausschließlich mit einem JSON-Objekt, ohne Erklärung, ohne Code-Zaun. Es muss genau diesem Schema entsprechen:\n'
            + json.dumps(schema, ensure_ascii=False, separators=(',', ':')))


def retry_message(errors):
    return ('Die Antwort passt nicht zum Schema: ' + '; '.join(errors[:8])
            + '. Antworte noch einmal, nur mit dem JSON-Objekt, ohne Erklärung.')
