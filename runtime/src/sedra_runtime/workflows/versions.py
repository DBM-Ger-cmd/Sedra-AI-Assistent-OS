"""Human-readable revision differences; technical secrets are never copied into summaries."""
from .process import metadata

LABELS = {'kind': 'Schrittart', 'mode': 'Arbeitsweise', 'source': 'Herkunft', 'core_step': 'Kernschritt',
          'supplier': 'Lieferant', 'input': 'Eingabe', 'output': 'Ergebnis', 'customer': 'Empfänger',
          'role': 'Zuständige Rolle', 'role_status': 'Rollenstatus', 'evidence': 'Nachweis',
          'completion': 'Abschlusskriterium', 'exception': 'Ausnahme / Stopp',
          'automation_reason': 'Automatisierungsbegründung', 'risk': 'Risiko / Hypothese'}


def compare(before, after):
    changes = []
    def add(node, field, old, new):
        if old != new:
            changes.append({'node': node, 'field': field, 'before': old, 'after': new})
    before = before or {'nodes': [], 'connections': {}}
    add('Prozess', 'Titel', before.get('name'), after.get('name'))
    old_nodes = {n['id']: n for n in before['nodes']}
    new_nodes = {n['id']: n for n in after['nodes']}
    for nid in sorted(old_nodes.keys() | new_nodes.keys()):
        old, new = old_nodes.get(nid), new_nodes.get(nid)
        if old is None:
            add(new['name'], 'Schritt hinzugefügt', None, new['name']); continue
        if new is None:
            add(old['name'], 'Schritt entfernt', old['name'], None); continue
        for key, label in (('name', 'Name'), ('type', 'Knotentyp'), ('typeVersion', 'Knotenversion'),
                           ('position', 'Position'), ('disabled', 'Deaktiviert')):
            add(new['name'], label, old.get(key), new.get(key))
        a, b = metadata(old), metadata(new)
        if a is not None or b is not None:
            for field, label in LABELS.items():
                add(new['name'], label, (a or {}).get(field), (b or {}).get(field))
        elif old.get('notes') != new.get('notes'):
            add(new['name'], 'Freie Notiz', '[bisherige Notiz]', '[geänderte Notiz]')
        excluded = {'id', 'name', 'type', 'typeVersion', 'position', 'disabled', 'notes', 'notesInFlow'}
        for key in sorted((old.keys() | new.keys()) - excluded):
            if old.get(key) != new.get(key):
                add(new['name'], 'Technisches Feld: ' + key, '[bisherige Einstellung]', '[geänderte Einstellung]')
    for source in sorted(before['connections'].keys() | after['connections'].keys()):
        def targets(doc):
            outputs = doc['connections'].get(source, {})
            return [f'{kind}:{index} → {e["node"]} (Eingang {e["index"]})'
                    for kind, branches in sorted(outputs.items()) for index, branch in enumerate(branches) for e in branch]
        add(source, 'Verbindungen', targets(before), targets(after))
    for key in sorted((before.keys() | after.keys()) - {'name', 'nodes', 'connections'}):
        if before.get(key) != after.get(key):
            add('Prozess', 'Workflow-Feld: ' + key, '[bisherige Einstellung]', '[geänderte Einstellung]')
    return changes
