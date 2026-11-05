"""Process documentation in n8n's standard notes field. Never an execution grant."""
import json

PREFIX = 'SEDRA_PROCESS_V1\n'
TEXT_FIELDS = {'supplier', 'input', 'output', 'customer', 'role', 'evidence', 'completion',
               'exception', 'automation_reason', 'risk', 'original_notes'}
ENUMS = {'kind': {'start', 'task', 'decision', 'end', 'annotation', 'data', 'store'},
         'mode': {'manual', 'assisted', 'automatable'}, 'source': {'board', 'proposal'},
         'role_status': {'proposal', 'confirmed'}}


def has_process(doc):
    return any(isinstance(n.get('notes'), str) and n['notes'].startswith(PREFIX) for n in doc.get('nodes', []))


def metadata(node):
    notes = node.get('notes')
    if not isinstance(notes, str) or not notes.startswith(PREFIX):
        return None
    try:
        data = json.loads(notes[len(PREFIX):])
    except (ValueError, RecursionError) as exc:
        raise ValueError('invalid_process_metadata') from exc
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data.get('schema') != 1 or set(data) - TEXT_FIELDS - set(ENUMS) - {'schema', 'core_step'}:
        raise ValueError('invalid_process_metadata')
    for field, choices in ENUMS.items():
        if not isinstance(data.get(field), str) or data.get(field) not in choices:
            raise ValueError('invalid_process_' + field)
    core = data.get('core_step', 0)
    if type(core) is not int or not 0 <= core <= 32:
        raise ValueError('invalid_process_core_step')
    for key in TEXT_FIELDS:
        if key in data and (not isinstance(data[key], str) or len(data[key]) > 4000):
            raise ValueError('invalid_process_text:' + key)
    return data


def summary(doc):
    rows = [metadata(node) for node in doc['nodes']]
    rows = [row for row in rows if row is not None]
    return {'model_only': bool(rows), 'steps': len(rows), 'core_steps': sum(bool(r.get('core_step')) for r in rows),
            'manual': sum(r['mode'] == 'manual' for r in rows), 'proposals': sum(r['source'] == 'proposal' for r in rows)}
