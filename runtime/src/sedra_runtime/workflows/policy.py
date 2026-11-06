"""Closed execution profile. Interchange support is deliberately wider."""
from copy import deepcopy
import re
from .schema import validate, VERSIONS
from .process import has_process

PROFILE = 'n8n-local-data-v1'
PATH = re.compile(r'=\{\{\s*\$json(?:\.[A-Za-z_][A-Za-z0-9_]*)+\s*\}\}')
UNSAFE_KEYS = {'__proto__', 'prototype', 'constructor'}


def _keys(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError('unsupported_parameters')


def _data(value):
    if isinstance(value, str):
        if '{{' in value or '}}' in value or value.startswith('='):
            if not PATH.fullmatch(value) or UNSAFE_KEYS.intersection(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', value)):
                raise ValueError('unsupported_expression')
    elif type(value) not in (str, int, float, bool) and value is not None:
        raise ValueError('unsupported_value')


def _scan(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in UNSAFE_KEYS:
                raise ValueError('unsafe_parameter_key')
            _scan(item)
    elif isinstance(value, list):
        for item in value:
            _scan(item)
    else:
        _data(value)


def _set(p):
    _keys(p, {'mode', 'assignments', 'includeOtherFields', 'options'})
    if p.get('mode', 'manual') != 'manual' or p.get('options', {}) != {} or type(p.get('includeOtherFields', False)) is not bool:
        raise ValueError('unsupported_set_mode')
    assignments = p.get('assignments', {})
    _keys(assignments, {'assignments'})
    rows = assignments.get('assignments', [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise ValueError('assignments_required')
    for row in rows:
        _keys(row, {'id', 'name', 'value', 'type'})
        if not isinstance(row.get('name'), str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}', row['name']) or row['name'] in UNSAFE_KEYS:
            raise ValueError('unsafe_assignment_name')
        kind = row.get('type')
        if kind not in ('string', 'number', 'boolean'):
            raise ValueError('unsupported_assignment_type')
        value = row.get('value')
        _data(value)
        expression = isinstance(value, str) and PATH.fullmatch(value)
        if not expression and ((kind == 'number' and type(value) not in (int, float)) or
                               (kind == 'boolean' and type(value) is not bool) or
                               (kind == 'string' and not isinstance(value, str))):
            raise ValueError('assignment_type_mismatch')


def _if(p):
    _keys(p, {'conditions', 'options'})
    if p.get('options', {}) != {}:
        raise ValueError('unsupported_if_options')
    conditions = p.get('conditions')
    _keys(conditions, {'options', 'conditions', 'combinator'})
    _keys(conditions.get('options', {}), {'caseSensitive', 'leftValue', 'typeValidation', 'version'})
    if conditions.get('combinator', 'and') not in ('and', 'or'):
        raise ValueError('invalid_combinator')
    for value in conditions.get('options', {}).values():
        _data(value)
    rows = conditions.get('conditions')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
        raise ValueError('conditions_required')
    operations = {'string': {'equals', 'notEquals', 'contains', 'notContains', 'empty', 'notEmpty'},
                  'number': {'equals', 'notEquals', 'gt', 'gte', 'lt', 'lte'}, 'boolean': {'true', 'false', 'equals', 'notEquals'}}
    for row in rows:
        _keys(row, {'id', 'leftValue', 'rightValue', 'operator'})
        _data(row.get('leftValue')); _data(row.get('rightValue'))
        operator = row.get('operator')
        _keys(operator, {'type', 'operation', 'singleValue'})
        if operator.get('operation') not in operations.get(operator.get('type'), set()):
            raise ValueError('unsupported_operator')


def executable(value):
    doc = validate(value)
    if has_process(doc):
        raise ValueError('process_model_requires_implementation')
    if doc.get('pinData') or doc.get('staticData'):
        raise ValueError('pinned_or_static_data_not_executable')
    active, starts = {}, []
    for node in doc['nodes']:
        kind, p = node['type'], node['parameters']
        if node['typeVersion'] not in VERSIONS.get(kind, []):
            raise ValueError('unsupported_node:' + node['name'])
        _scan(p)
        if node.get('credentials') or any(node.get(k) for k in ('disabled', 'retryOnFail', 'alwaysOutputData', 'continueOnFail', 'executeOnce')) or node.get('onError', 'stopWorkflow') != 'stopWorkflow':
            raise ValueError('unsupported_node_execution_options:' + node['name'])
        if kind.endswith('.stickyNote'):
            continue
        if kind.endswith('.set'):
            _set(p)
        elif kind.endswith('.if'):
            _if(p)
        elif p:
            raise ValueError('unsupported_parameters:' + node['name'])
        active[node['name']] = {k: deepcopy(node[k]) for k in ('id', 'name', 'type', 'typeVersion', 'parameters', 'position')}
        if kind.endswith('.manualTrigger'):
            starts.append(node['name'])
    if len(starts) != 1 or len(active) > 32:
        raise ValueError('one_manual_start_and_max_32_nodes_required')
    adjacency = {name: [] for name in active}
    indegree = {name: 0 for name in active}
    for source, outputs in doc['connections'].items():
        if source not in active or set(outputs) != {'main'}:
            raise ValueError('only_main_connections_supported')
        max_outputs = 2 if active[source]['type'].endswith('.if') else 1
        if len(outputs['main']) > max_outputs:
            raise ValueError('unsupported_output_index')
        for branch in outputs['main']:
            for edge in branch:
                if edge['node'] not in active or edge['type'] != 'main' or edge['index'] != 0 or set(edge) != {'node', 'type', 'index'}:
                    raise ValueError('unsupported_connection')
                adjacency[source].append(edge['node']); indegree[edge['node']] += 1
    queue = [name for name, count in indegree.items() if not count]
    ordered = []
    while queue:
        name = queue.pop(); ordered.append(name)
        for target in adjacency[name]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(ordered) != len(active):
        raise ValueError('cycles_not_supported')
    reachable, pending = set(), list(starts)
    while pending:
        name = pending.pop()
        if name not in reachable:
            reachable.add(name); pending.extend(adjacency[name])
    if reachable != set(active) or any(starts[0] in targets for targets in adjacency.values()):
        raise ValueError('unreachable_nodes_or_incoming_start')
    return {'name': doc['name'], 'nodes': list(active.values()), 'connections': deepcopy(doc['connections']),
            'settings': {'executionOrder': 'v1', 'executionTimeout': 10}}


def assessment(value):
    try:
        executable(value)
        return {'executable': True, 'profile': PROFILE, 'reason': None}
    except ValueError as exc:
        return {'executable': False, 'profile': PROFILE, 'reason': str(exc)}
