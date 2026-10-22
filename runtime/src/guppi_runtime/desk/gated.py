"""Antrag und Anwenden für Verben mit Gate (Spec 0, D3.2, K0.10; Spec 1, D1.3.2, S1.H5).

Das Muster von `UIXHub.boundaries_request`/`boundaries_apply` als Helfer, damit ein registrierter Typ ein Verb mit Freigabe bekommt,
ohne Code in `uix_server.py`:

    request(hub, kind, action, target, binding, gates=None)
                                    legt eine Mission mit einem oder mehreren Gates an (`gates`: [(action, target)], alle an
                                    dieselbe Bindung), bindet `binding` an jedes Gate und merkt den Antrag (er erscheint in den
                                    Entscheidungen); geschrieben wird nichts
    apply(hub, mission_id, do)      Spec 0, ein Gate: nach der Freigabe prüft es den Einmal-Token mit `guard.authorize` gegen genau
                                    diese Aktion, dieses Ziel und diese Bindung, ruft dann `do(binding)` und schließt die Mission
    register_applier(kind, do)      wer einen Antrag dieser Art anwendet: `do(hub, binding)`; vor `kinds.freeze()`
    decide(hub, mission_id)         „Freigeben und anwenden“: jedes offene Gate freigeben, jeden Token prüfen, dann `do`; meldet der
                                    Applier `binding_stale`, endet der Antrag ohne Wirkung
    reject(hub, mission_id)         „Ablehnen“: alle Gates des Antrags abgelehnt, eine Entscheidung, ein Ausgang
    pending(hub, known)             gated-Anträge aus den Missionen, damit sie nach einem Neustart wieder im Posteingang stehen

`uix_server.decide` ruft `decide`/`reject` für jede Art mit Applier, ohne Typnamen (G2-S1-09).

Dauerfreigabe (G4-Entscheidung HALT 1 A mit Auflage, Captain 22.10.2026): nur für die fest eingetragene Art `standing`
(`SPENDS_TOKEN`) prüft `decide` den Token nicht selbst, sondern gibt ihn unverbraucht an den Applier, der ihn genau einmal an
`guard.grant_standing` gibt. Für jede andere Art prüft `decide` wie bisher; `register_applier` kann daran nichts ändern. Mit
`exact=True` ist die Bindung am Gate genau die übergebene (ohne `describe`/`agent_id`), weil der Guard sie selbst nachbaut."""
from __future__ import annotations

CONTEXT = 'gated_request'
AGENT_ACTIONS = ('wake_agent', 'pause_agent', 'resume_agent', 'terminate_agent', 'set_budget', 'set_org')   # D1.3.5: binding.agent_id
STALE = 'binding_stale'
REFUSED = 'guard_refused:'                   # ein Applier meldet so die Ablehnung durch den Guard; der Antrag endet mit diesem Grund
SPENDS_TOKEN = frozenset({'standing'})        # fest im Code, keine Option (Auflage HALT 1)

_APPLIERS = {}


def register_applier(kind, do, on_reject=None, registry=None):
    """Wer Anträge der Art `kind` anwendet: `do(hub, binding)`; `on_reject(hub, binding)` wird beim Ablehnen gerufen (wahlweise).
    Dieselbe Funktion noch einmal (ein zweiter Hub im selben Prozess) ist kein Fehler, eine andere schon."""
    if registry is not None and registry.frozen:
        raise ValueError('kinds_frozen')
    known = _APPLIERS.get(kind)
    if known is not None and known != (do, on_reject):
        raise ValueError('applier_already_registered')
    _APPLIERS[kind] = (do, on_reject)


def applier(kind):
    entry = _APPLIERS.get(kind)
    return entry[0] if entry else None


def _gates(action, target, gates):
    pairs = [(action, target)] if gates is None else [tuple(g) for g in gates]
    if not pairs or any(len(p) != 2 or not all(isinstance(x, str) and x for x in p) for p in pairs):
        raise ValueError('gates_invalid')
    return pairs


def request(hub, kind, action, target, binding, risks=(), rollback_available=True, level='S1', gates=None, exact=False, describe=None):
    """Ein Antrag: Mission mit einem Gate je (Aktion, Ziel); die Bindung ist, was nach der Freigabe genau so ausgeführt wird."""
    if not isinstance(binding, dict):
        raise ValueError('binding_must_be_an_object')
    pairs = _gates(action, target, gates)
    describe = str(describe or binding.get('describe') or f'{pairs[0][0]} → {pairs[0][1]}')
    if exact:
        binding = dict(binding)
    else:
        binding = dict(binding, describe=describe)
        agent = next((t[len('agent:'):] for a, t in pairs if a in AGENT_ACTIONS and t.startswith('agent:')), None)
        if agent and 'agent_id' not in binding:
            binding['agent_id'] = agent
    rt = hub.runtime
    with hub.lock:
        m = rt.brain.create_mission(describe[:160], None, level)
        mid = m['identity']['mission_id']
        made = [rt.guard.create_gate(mid, a, t, risks=[str(r) for r in risks], rollback_available=bool(rollback_available),
                                     request_binding=binding) for a, t in pairs]
        m['human_gates']['pending'].extend(made)
        m['context'][CONTEXT] = {'kind': kind, 'action': pairs[0][0], 'target': pairs[0][1], 'gates': [list(p) for p in pairs],
                                 'binding': binding, 'describe': describe}
        rt.missions.save(m)
    shown = binding if not exact else dict(binding, describe=describe)      # nur für die Anzeige; das Gate bindet `binding`
    return hub._remember(kind, {'mission_id': mid, 'gate': made[0], 'gates': made, 'binding': shown})


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
        if len(req.get('gates') or [[req['action'], req['target']]]) > 1:
            raise ValueError('several_gates_need_decide')
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


def _load(rt, mission_id):
    m = rt.missions.load(mission_id)
    req = (m.get('context') or {}).get(CONTEXT)
    if not req:
        raise ValueError('not_a_gated_request')
    entry = _APPLIERS.get(req['kind'])
    if entry is None:
        raise ValueError('decision_cannot_be_applied')
    return m, req, entry


def _payload(req):
    gates = req.get('gates') or [[req['action'], req['target']]]
    return {'kind': req['kind'], 'gates': gates, 'target': gates[0][1], 'agent_id': req['binding'].get('agent_id')}


def decide(hub, mission_id):
    """„Freigeben und anwenden“ für einen gated-Antrag mit einem oder mehreren Gates. Ist ein Token ungültig, läuft nichts."""
    mission_id = str(mission_id or '').strip()
    if not mission_id:
        raise ValueError('mission_id_required')
    rt = hub.runtime
    with rt.missions.execution_lock(mission_id):
        m, req, (do, _) = _load(rt, mission_id)
        pending = list((m.get('human_gates') or {}).get('pending') or [])
        if not pending:
            raise ValueError('no_pending_human_gate')
        tokens = m['execution'].setdefault('approval_tokens', {})
        for gate in pending:
            tokens[gate['gate_id']] = rt.guard.approve(gate)
            m['human_gates']['resolved'].append(gate)
        m['human_gates']['pending'] = []
        rt.missions.save(m)
        for gate in pending if req['kind'] not in SPENDS_TOKEN else ():
            request_ = gate['request']
            target = (request_.get('targets') or [''])[0]
            if not rt.guard.authorize(tokens[gate['gate_id']], mission_id=mission_id, action=request_['exact_action'], target=target,
                                      request_binding=req['binding'])['authorized']:
                raise ValueError('captain_approval_invalid')
        payload = _payload(req)
        try:
            if req['kind'] in SPENDS_TOKEN:
                result = do(hub, req['binding'], {g['gate_id']: tokens[g['gate_id']] for g in pending})
            else:
                result = do(hub, req['binding'])
        except ValueError as exc:
            code = str(exc)
            if code != STALE and not code.startswith(REFUSED):
                raise
            m['execution'].pop('approval_tokens', None)
            m['result'] = {'kind': req['kind'], 'error': code}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            if code == STALE:
                rt.audit.append('DESK_GATED_STALE', component='desk', mission_id=mission_id, payload=payload)
                return {'status': STALE, 'result': None}
            rt.audit.append('DESK_GATED_REFUSED', component='desk', mission_id=mission_id, payload=dict(payload, reason=code[len(REFUSED):]))
            return {'status': 'guard_refused', 'reason': code[len(REFUSED):], 'result': None}
        m['execution'].pop('approval_tokens', None)
        m['result'] = {'kind': req['kind'], 'result': result}
        m['lifecycle']['status'] = 'closed'
        rt.missions.save(m)
        rt.audit.append('DESK_GATED_APPLIED', component='desk', mission_id=mission_id, payload=payload)
    return {'status': 'applied', 'result': result}


def reject(hub, mission_id):
    """„Ablehnen“: jedes offene Gate des Antrags wird abgelehnt, kein Token entsteht; die Mission ist danach geschlossen."""
    mission_id = str(mission_id or '').strip()
    if not mission_id:
        raise ValueError('mission_id_required')
    rt = hub.runtime
    with rt.missions.execution_lock(mission_id):
        m, req, (_, on_reject) = _load(rt, mission_id)
        pending = list((m.get('human_gates') or {}).get('pending') or [])
        if not pending:
            raise ValueError('no_pending_human_gate')
        for gate in pending:
            m['human_gates']['resolved'].append(rt.guard.reject(gate))
        m['human_gates']['pending'] = []
        m['result'] = {'kind': req['kind'], 'rejected': True}
        m['lifecycle']['status'] = 'closed'
        rt.missions.save(m)
        rt.audit.append('DESK_GATED_REJECTED', component='desk', mission_id=mission_id, payload=_payload(req))
    result = on_reject(hub, req['binding']) if on_reject is not None else None
    return {'status': 'rejected', 'result': result}


def pending(hub, known_mission_ids):
    """Offene gated-Anträge aus den Missionen (nach einem Neustart ist die Merkliste des Hubs leer, das Gate steht noch)."""
    out = []
    known = set(known_mission_ids)
    for m in hub.runtime.missions.list():
        mid = (m.get('identity') or {}).get('mission_id')
        req = (m.get('context') or {}).get(CONTEXT)
        if not mid or mid in known or not req:
            continue
        gates = [g for g in (m.get('human_gates') or {}).get('pending', []) if isinstance(g, dict) and g.get('gate_id')]
        if gates:
            out.append({'kind': req['kind'], 'mission_id': mid, 'gate': gates[0], 'binding': req['binding']})
    return out
