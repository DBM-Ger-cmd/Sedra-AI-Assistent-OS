"""One source for every decision the Captain has to make (SHELL_WERKZEUG_VERTRAG_v1 §10.3).

Today they live in three places: the pending gates of a mission, the change requests the chat/Werkstatt/Bibliothek keep open
(`open_requests`), and from Build 9 the project boundaries. This module brings them into one shape, so a tool (and the Gespräch,
and a later Posteingang in another shell) can show and answer all of them the same way:

    {id, kind, title, describe, mission_id, gate_id, ways:[…], binding, created_at, apply, agent_id}

`agent_id` (Spec 1, D1.3.5): der betroffene Agent eines Antrags der Orchestrierung (aus `binding.agent_id`), sonst None.

`ways` are the three or four ways out of the Cockpit rules: `einmal` (approve once), `freigeben_und_anwenden` (approve and apply a
change request in one go), `aendern` (change the boundary – Build 9), `ablehnen`. Answering goes through the same guard calls as
before: nothing here weakens the once-only token or the content binding."""
from __future__ import annotations

APPLY = {'switch': '/api/switch/apply', 'routing': '/api/routing-config/apply',
         'model_add': '/api/model/add/apply', 'skill': '/api/library/custom/apply',
         'boundaries': '/api/boundaries/apply', 'install': '/api/uix/install/apply',
         'trust': '/api/uix/trust/apply', 'gateway': '/api/gateway/apply'}
REQUEST_TITLE = {'switch': 'Schalter umstellen', 'routing': 'Modell-Einstellung ändern',
                 'model_add': 'Neues Modell hinzufügen', 'skill': 'Eigenen Skill schreiben',
                 'boundaries': 'Modus und Grenzen festlegen', 'install': 'Modul installieren',
                 'trust': 'Schreibrouten freigeben', 'gateway': 'GateWay-Vorgang freigeben'}
REQUEST_NOTE = {'switch': 'Schalter · gilt nach dem Neustart der Oberfläche', 'routing': 'Modell-Einstellung · gilt nach dem Neustart',
                'model_add': 'Neues Modell · sofort nutzbar', 'skill': 'Bibliothek · die Datei wird vorher gesichert',
                'boundaries': 'Gilt für alles, was in diesem Projekt passiert', 'install': 'Ein fremdes Modul · erst nach deiner Durchsicht',
                'trust': 'Ein fremdes Modul darf danach schreiben – genau diese Routen, nichts sonst',
                'gateway': 'Gilt genau für diesen Vorgang in diesem Stand – ändert sich Anfrage, Dokument oder Weg, ist die Freigabe hinfällig. Kein Versand.'}
WAYS = {'einmal': 'Einmal öffnen', 'freigeben_und_anwenden': 'Freigeben und anwenden', 'aendern': 'Grenze ändern …', 'ablehnen': 'Ablehnen'}


def gate_decision(mission, gate):
    """A pending mission gate as a decision."""
    request = gate.get('request') or {}
    targets = [t for t in (request.get('targets') or []) if isinstance(t, str)]
    action = request.get('exact_action') or 'Aktion'
    intent = (mission.get('captain_intent') or {}).get('original') or (mission.get('objective') or {}).get('current') or ''
    return {'id': 'gate:' + str(gate.get('gate_id')), 'kind': 'gate', 'title': str(intent)[:120] or action,
            'describe': action + (' → ' + ', '.join(targets) if targets else ''),
            'mission_id': (mission.get('identity') or {}).get('mission_id'), 'gate_id': gate.get('gate_id'),
            'risks': [r for r in (request.get('risks') or []) if isinstance(r, str)],
            'rollback': bool(request.get('rollback_available')),
            'note': 'gilt nur einmal · Rücknahme ' + ('möglich' if request.get('rollback_available') else 'nicht möglich'),
            'created_at': gate.get('created_at'), 'ways': ['einmal', 'ablehnen'], 'apply': None, 'binding': request.get('request_binding'),
            'agent_id': None}


def request_decision(req):
    """An open change request (switch, routing, model_add, skill) as a decision: approving and applying belong together."""
    kind = req.get('kind')
    binding = req.get('binding') or {}
    return {'id': 'request:' + str(req.get('mission_id')), 'kind': 'request:' + str(kind),
            'title': binding.get('describe') or REQUEST_TITLE.get(kind, 'Änderung'),
            'describe': REQUEST_NOTE.get(kind, str(kind)), 'mission_id': req.get('mission_id'),
            'gate_id': (req.get('gate') or {}).get('gate_id'), 'risks': [], 'rollback': True,
            'note': REQUEST_NOTE.get(kind, ''), 'created_at': (req.get('gate') or {}).get('created_at'),
            'ways': ['freigeben_und_anwenden', 'ablehnen'], 'apply': APPLY.get(kind),
            'binding': {k: v for k, v in binding.items() if k in ('section', 'key', 'old', 'new', 'describe', 'block', 'text', 'recipe_id', 'field',
                                                                 'vorgang_id', 'klasse', 'merkmale', 'weg', 'policy', 'binding',
                                                                 'agent_id', 'op')},
            'agent_id': binding.get('agent_id')}


def boundary_decision(crossing):
    """Eine Grenzüberschreitung als Entscheidung (COCKPIT_MODUL_v1 Regel 7): dieselbe Form, drei Wege – und `aendern` führt
    nicht zur Tat, sondern zu der Entscheidung, die über die Grenze selbst befindet."""
    return {'id': crossing['id'], 'kind': 'boundary', 'title': crossing['title'], 'describe': crossing['describe'],
            'mission_id': None, 'gate_id': None, 'risks': [], 'rollback': True, 'note': crossing.get('note', ''),
            'created_at': crossing.get('created_at'), 'ways': list(crossing['ways']), 'apply': None,
            'binding': {'boundary': crossing['boundary'], 'project_id': crossing['project_id'], 'amount': crossing.get('amount')},
            'agent_id': None}


def content_decision(d):
    """Ein Modellaufruf, den der Inhaltsschutz nicht ohne den Captain durchlässt (Build 16, SPEC_EIN_SICHERER_WEG S3).
    Die Bindung ist der Hash über alle Teile des Aufrufs: „einmal“ gilt genau für diesen Aufruf, zehn Minuten. Kein Text."""
    from datetime import datetime, timezone
    created = d.get('created_at')
    if isinstance(created, (int, float)):
        created = datetime.fromtimestamp(created, timezone.utc).isoformat().replace('+00:00', 'Z')
    segs = d.get('segments') or []
    where = ', '.join(sorted({f"{s.get('trust')}" for s in segs if s.get('rules')})) or 'Aufruf'
    return {'id': d['id'], 'kind': 'content', 'title': 'Modellaufruf prüfen: ' + ' '.join(d.get('describe') or [])[:120],
            'describe': f"{len(segs)} Teil(e), Fund in: {where} · Modell {d.get('model')} · Weg {d.get('route')}",
            'mission_id': d.get('mission_id') or None, 'gate_id': None, 'risks': list(d.get('describe') or []), 'rollback': True,
            'note': 'Inhaltsschutz · „einmal“ lässt genau diesen Aufruf durch, zehn Minuten lang · Abgelehnt geht nichts hinaus',
            'created_at': created, 'ways': list(d.get('ways') or ['einmal', 'ablehnen']), 'apply': None,
            'binding': {'binding': d.get('binding'), 'rules': list(d.get('rules') or []), 'reasons': list(d.get('reasons') or [])},
            'agent_id': None}


def collect(missions, open_requests, crossings=(), contents=()):
    """Every open decision, newest last. `missions` are the compact or full mission records, `open_requests` what the hub
    remembers, `crossings` the boundary crossings that wait (Build 9), `contents` the model calls the content guard holds (Build 16).

    A mission that *is* a change request is counted once – as the request, because that is the one that can be applied."""
    out = []
    request_missions = {r.get('mission_id') for r in open_requests}
    for m in missions:
        mid = (m.get('identity') or {}).get('mission_id') or m.get('mission_id')
        if mid in request_missions:
            continue
        for gate in ((m.get('human_gates') or {}).get('pending') or []):
            if isinstance(gate, dict):
                out.append(gate_decision(m, gate))
    for req in open_requests:
        out.append(request_decision(req))
    for crossing in crossings:
        out.append(boundary_decision(crossing))
    for d in contents:
        out.append(content_decision(d))
    out.sort(key=lambda d: (d.get('created_at') or '', d['id']))
    return out


def summary(decisions):
    """What the instrument in the strip shows: how many wait and what the first one is about."""
    first = decisions[0] if decisions else None
    return {'count': len(decisions), 'first': first['title'] if first else None,
            'kind': first['kind'] if first else None, 'tone': 'warn' if decisions else 'ok'}


def check_answer(decision, way):
    """Raises ValueError when the way is not one this decision offers; returns the way."""
    if decision is None:
        raise ValueError('unknown_decision')
    if way not in decision['ways']:
        raise ValueError('way_not_offered')
    return way
