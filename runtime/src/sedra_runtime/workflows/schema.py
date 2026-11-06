"""Lossless JSON-value interchange; this validation never grants execution rights."""
from copy import deepcopy
import json
import math
import re
from .process import metadata, summary

MAX_BYTES = 1_000_000
MAX_NODES = 256
VERSIONS = {'n8n-nodes-base.manualTrigger': [1], 'n8n-nodes-base.set': [3.4],
            'n8n-nodes-base.if': [2.2], 'n8n-nodes-base.noOp': [1], 'n8n-nodes-base.stickyNote': [1]}


def strict_json(text):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('duplicate_json_key')
            out[key] = value
        return out
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('workflow_size_limit')
    try:
        return json.loads(text.lstrip('\ufeff'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non_finite_json')))
    except (RecursionError, json.JSONDecodeError) as exc:
        raise ValueError('invalid_workflow_json') from exc


def validate(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('invalid_json_value') from exc
    if len(raw.encode('utf-8')) > MAX_BYTES:
        raise ValueError('workflow_size_limit')
    if not isinstance(value, dict) or not isinstance(value.get('name'), str) or not value['name'].strip():
        raise ValueError('workflow_name_required')
    if len(value['name']) > 200:
        raise ValueError('workflow_name_too_long')
    nodes, connections = value.get('nodes'), value.get('connections')
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES or not isinstance(connections, dict):
        raise ValueError('workflow_nodes_or_connections_invalid')
    ids, names = set(), set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError('invalid_node')
        metadata(node)
        for field, seen in (('id', ids), ('name', names)):
            item = node.get(field)
            if not isinstance(item, str) or not 1 <= len(item) <= 200 or item in seen:
                raise ValueError('invalid_or_duplicate_node_' + field)
            if item in {'__proto__', 'constructor', 'prototype'}:
                raise ValueError('reserved_node_identity')
            seen.add(item)
        pos = node.get('position')
        if not isinstance(node.get('type'), str) or not node['type'] or not isinstance(node.get('parameters'), dict):
            raise ValueError('invalid_node_type_or_parameters')
        if type(node.get('typeVersion')) not in (int, float) or not math.isfinite(node['typeVersion']):
            raise ValueError('invalid_node_version')
        if not isinstance(pos, list) or len(pos) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 100000 for x in pos):
            raise ValueError('invalid_node_position')
    for source, outputs in connections.items():
        if source not in names or not isinstance(outputs, dict):
            raise ValueError('invalid_connection_source')
        for output_type, branches in outputs.items():
            if not isinstance(output_type, str) or not isinstance(branches, list):
                raise ValueError('invalid_connection_output')
            for branch in branches:
                if not isinstance(branch, list):
                    raise ValueError('invalid_connection_branch')
                for edge in branch:
                    if not isinstance(edge, dict) or edge.get('node') not in names or not isinstance(edge.get('type'), str) or type(edge.get('index')) is not int or edge['index'] < 0:
                        raise ValueError('invalid_connection_target')
    return deepcopy(value)


def report(value):
    doc = validate(value)
    nodes = [{'id': n['id'], 'name': n['name'], 'type': n['type'],
              'supported': n['typeVersion'] in VERSIONS.get(n['type'], [])} for n in doc['nodes']]
    warnings = []
    if any(n.get('credentials') for n in doc['nodes']):
        warnings.append('Zugangsdaten-Referenzen enthalten: vor Weitergabe prüfen.')
    if any(not n['supported'] for n in nodes):
        warnings.append('Unbekannte Knoten bleiben erhalten; Ausführung ist eingeschränkt.')
    process = summary(doc)
    if process['model_only']:
        warnings.append('Prozessmodell: fachliche Schritte sind beschrieben, Ausführung noch nicht eingerichtet.')
    return {'format': 'n8n-json', 'nodes': nodes, 'warnings': warnings, 'process': process}


def redacted(value):
    """Explicit sharing copy; not claimed to find secrets in arbitrary free text."""
    secret = re.compile(r'password|secret|token|authorization|api.?key|credential|authentication|header', re.I)
    def clean(v):
        if isinstance(v, dict):
            return {k: ('[REDACTED]' if secret.search(k) else clean(x)) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        return v
    out = clean(validate(value))
    for key in ('pinData', 'staticData'):
        out.pop(key, None)
    return out
