def sample():
    return {'name': 'Local test', 'nodes': [
        {'id': 'start', 'name': 'Start', 'type': 'n8n-nodes-base.manualTrigger', 'typeVersion': 1, 'parameters': {}, 'position': [0, 0]},
        {'id': 'set', 'name': 'Set', 'type': 'n8n-nodes-base.set', 'typeVersion': 3.4, 'position': [260, 0],
         'parameters': {'assignments': {'assignments': [{'id': 'value', 'name': 'text', 'value': 'Hello', 'type': 'string'}]}, 'options': {}}}],
        'connections': {'Start': {'main': [[{'node': 'Set', 'type': 'main', 'index': 0}]]}},
        'settings': {'executionOrder': 'v1'}, 'active': False}


def process_sample():
    import json
    from sedra_runtime.workflows.process import PREFIX
    doc = sample()
    for index, node in enumerate(doc['nodes']):
        node['notes'] = PREFIX + json.dumps({'schema': 1, 'kind': 'start' if index == 0 else 'task',
            'mode': 'manual', 'source': 'proposal', 'role_status': 'proposal', 'core_step': index + 1,
            'role': 'Prüfende Rolle', 'supplier': 'Anfragende Stelle', 'input': 'Anfrage', 'output': 'Geprüfter Entwurf',
            'customer': 'Verantwortliche Stelle', 'evidence': 'Belegreferenz', 'completion': 'Prüfung dokumentiert'})
        node['disabled'] = True
    return doc
