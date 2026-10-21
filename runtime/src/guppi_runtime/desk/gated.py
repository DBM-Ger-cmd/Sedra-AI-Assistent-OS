"""Antrag und Anwenden für Verben mit Gate (Spec 0, D3.2, K0.10).

Das Muster von `UIXHub.boundaries_request`/`boundaries_apply` als Helfer, damit ein registrierter Typ ein Verb mit Freigabe bekommt,
ohne Code in `uix_server.py`:

    request(hub, kind, action, target, binding)   legt eine Mission mit Gate an, bindet `binding` an das Gate und merkt den Antrag
                                                  (er erscheint in den Entscheidungen); geschrieben wird nichts
    apply(hub, mission_id, do)                    nach der Freigabe: prüft den Einmal-Token mit `guard.authorize` gegen genau diese
                                                  Aktion, dieses Ziel und diese Bindung, ruft dann `do(binding)` und schließt die Mission

In Spec 0 benutzt kein Verb diesen Helfer (OP-15); die Verben von `agent`, `issue`, `routine`, `budget` baut Spec 1 darauf."""
from __future__ import annotations

CONTEXT = 'gated_request'


def request(hub, kind, action, target, binding, risks=(), rollback_available=True, level='S1'):
    """Ein Antrag: Mission mit Gate für `action` auf `target`; die Bindung ist, was nach der Freigabe genau so ausgeführt wird."""
    if not isinstance(binding, dict):
        raise ValueError('binding_must_be_an_object')
    describe = str(binding.get('describe') or f'{action} → {target}')
    binding = dict(binding, describe=describe)
    rt = hub.runtime
    with hub.lock:
        m = rt.brain.create_mission(describe[:160], None, level)
        mid = m['identity']['mission_id']
        gate = rt.guard.create_gate(mid, action, target, risks=[str(r) for r in risks],
                                    rollback_available=bool(rollback_available), request_binding=binding)
        m['human_gates']['pending'].append(gate)
        m['context'][CONTEXT] = {'kind': kind, 'action': action, 'target': target, 'binding': binding}
        rt.missions.save(m)
    return hub._remember(kind, {'mission_id': mid, 'gate': gate, 'binding': binding})


def apply(hub, mission_id, do, audit_event='DESK_GATED_APPLIED'):
    """Nach der Freigabe: dieselbe Prüfung des Einmal-Tokens wie bei den Grenzen; `do(binding)` läuft nur mit gültigem Token."""
    mission_id = str(mission_id or '').strip()
    if not mission_id:
        raise ValueError('mission_id_required')
    rt = hub.runtime
    with rt.missions.execution_lock(mission_id):
        m = rt.missions.load(mission_id)
        req = (m.get('context') or {}).get(CONTEXT)
        token = (m.get('execution') or {}).get('approval_token')
        if not req:
            raise ValueError('not_a_gated_request')
        if not token:
            raise ValueError('captain_approval_required')
        if not rt.guard.authorize(token, mission_id=mission_id, action=req['action'], target=req['target'],
                                  request_binding=req['binding'])['authorized']:
            raise ValueError('captain_approval_invalid')
        result = do(req['binding'])
        m['execution'].pop('approval_token', None)
        m['result'] = {'kind': req['kind'], 'result': result}
        m['lifecycle']['status'] = 'closed'
        rt.missions.save(m)
        rt.audit.append(audit_event, component='desk', mission_id=mission_id,
                        payload={'kind': req['kind'], 'action': req['action'], 'target': req['target']})
    hub.events.publish('decision.answered', {'id': 'request:' + mission_id, 'kind': 'request:' + req['kind'],
                                             'way': 'freigeben_und_anwenden'})
    return {'status': 'applied', 'result': result}
