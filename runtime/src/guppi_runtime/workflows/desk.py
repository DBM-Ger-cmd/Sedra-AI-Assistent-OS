"""Desk extension; the editor has no approval route and no engine credentials."""
from ..desk.actions import Verb
from ..core.request_binding import digest
from .store import WorkflowStore
from .schema import report, strict_json
from .policy import assessment
from .engine import configuration, inputs
from .versions import compare


def _store(hub):
    return WorkflowStore(hub.project_root)


def _object(kind, oid, title, state, **extra):
    return dict(type=kind, id=oid, title=title, state=state, summary=title, actions=[], links=[], **extra)


def _workflow(record):
    return _object('workflow', record['id'], record['workflow']['name'], 'gespeichert',
                   revision=record['revision'], digest=record['digest'], workflow=record['workflow'],
                   compatibility=report(record['workflow']), execution=assessment(record['workflow']))


def _read(hub, oid):
    if oid == 'alle':
        try:
            engine = configuration(hub.project_root)
        except ValueError:
            engine = {'enabled': False, 'error': 'invalid_n8n_configuration'}
        return _object('workflow', 'alle', 'Workflows', 'bereit', items=_listing(hub, {}),
                       engine=engine, runs=_runs(hub, {}))
    return dict(_workflow(_store(hub).read(oid)), revisions=_store(hub).revisions(oid))


def _listing(hub, payload):
    return [_workflow(record) for record in _store(hub).listing()]


def _check(hub, oid, args):
    value = strict_json(args['text']) if 'text' in args else args.get('workflow')
    return dict(report(value), workflow=value, execution=assessment(value))


def _save(hub, oid, args):
    with hub.lock:
        record = _store(hub).save(args.get('workflow'), oid, args.get('base_revision'), args.get('change_note'))
        hub.runtime.audit.append('WORKFLOW_REVISION_SAVED', component='workflows',
                                 payload={'workflow_id': record['id'], 'revision': record['revision'], 'digest': record['digest'],
                                          'record_digest': record['record_digest'], 'previous_revision': record['previous_revision']})
    return dict(_workflow(record), revisions=_store(hub).revisions(record['id']))


def _run_read(hub, mid):
    m = hub.runtime.missions.load(mid)
    ref = (m.get('context') or {}).get('n8n_workflow')
    if not ref:
        raise ValueError('not_a_workflow_mission')
    result = next((r.get('n8n_result') for r in reversed(m['execution']['results']) if r.get('n8n_result')), None)
    return _object('workflow_run', mid, 'Lauf: ' + ref['name'], m['lifecycle']['phase'],
                   workflow_id=ref['id'], revision=ref['revision'], result=result, wait=m.get('wait'),
                   mission_id=mid, artifacts=m['execution']['artifacts'],
                   steps=[{'id': s['id'], 'status': s['status'], 'attempts': s['attempts']}
                          for s in (m['execution'].get('step_journal') or {}).get('steps', [])])


def _runs(hub, payload):
    return [_run_read(hub, m['identity']['mission_id']) for m in hub.runtime.missions.list()
            if (m.get('context') or {}).get('n8n_workflow')][-50:]


def _start(hub, oid, args):
    with hub.lock:
        record = _store(hub).read(oid)
        if args.get('revision') != record['revision']:
            raise ValueError('workflow_revision_conflict')
        check = assessment(record['workflow'])
        if not check['executable']:
            raise ValueError(check['reason'])
        cfg = configuration(hub.project_root)
        if not cfg.get('enabled'):
            raise ValueError('n8n_not_configured')
        data = inputs(args.get('inputs', {}))
        rt = hub.runtime
        m = rt.brain.create_mission('n8n: ' + record['workflow']['name'])
        mid = m['identity']['mission_id']
        m['context']['n8n_workflow'] = {'id': oid, 'revision': record['revision'], 'name': record['workflow']['name'], 'digest': record['digest']}
        m['plan_revision'] = 1
        m['plan'] = {'version': 1, 'revision': 1, 'status': 'ready', 'workflow': 'n8n-local-data-v1',
                     'steps': [{'id': 'N8N-1', 'action': 'n8n_workflow', 'workflow': record['workflow'], 'inputs': data,
                                'execution_requirements': {'allowed_execution_locations': ['local'], 'data_class': 'internal', 'context_min_tokens': 0}}],
                     'dependencies': [], 'acceptance_criteria': [{'type': 'artifact_exists', 'min_count': 1}]}
        rt.missions.save(m)
        for phase in ('UNDERSTAND', 'PLAN', 'READY'):
            rt.missions.transition(m, phase)
        # This only reaches the mandatory gate. Nothing is approved here.
        rt.brain.run(mid, max_steps=2)
        hub.events.publish('task.changed', {'id': mid})
        return _run_read(hub, mid)


def _continue(hub, mid, args):
    hub.run_mission({'mission_id': mid, 'max_steps': 4})
    hub.events.publish('task.changed', {'id': mid})
    return _run_read(hub, mid)


def _history(hub, oid, args):
    store, wid = _store(hub), args.get('id')
    return {'versions': [{k: v for k, v in store.read(wid, revision).items() if k != 'workflow'}
                         for revision in store.revisions(wid)[-100:]]}


def _compare(hub, oid, args):
    store, wid = _store(hub), args.get('id')
    a, b = store.read(wid, args.get('from_revision')), store.read(wid, args.get('to_revision'))
    return {'from_revision': a['revision'], 'to_revision': b['revision'], 'changes': compare(a['workflow'], b['workflow'])}


def register(registry, hub):
    registry.register(registry.Kind('workflow', 'Workflows', _read, _listing,
        verbs=[Verb('speichern', 'Neue Revision speichern', _save),
               Verb('starten', 'Lauf zur Freigabe vorlegen', _start, needs_gate=True)],
        type_verbs=[Verb('importieren', 'Workflow speichern', _save),
                    Verb('versionen', 'Versionshistorie lesen', _history), Verb('vergleichen', 'Versionen vergleichen', _compare),
                    Verb('revision_lesen', 'Frühere Revision lesen', lambda h, o, a: _workflow(_store(h).read(a.get('id'), a.get('revision')))),
                    Verb('pruefen', 'Kompatibilität prüfen', _check)]))
    canonical = registry.get('workflow')
    registry.register(registry.Kind('scenario', 'Szenario Studio',
        lambda h, oid: dict(_read(h, oid), type='scenario'),
        lambda h, p: [dict(item, type='scenario') for item in _listing(h, p)],
        verbs=canonical.verbs, type_verbs=canonical.type_verbs, source='workflows'))
    registry.register(registry.Kind('workflow_run', 'Workflow-Lauf', _run_read, _runs,
        verbs=[Verb('fortsetzen', 'Nach Freigabe fortsetzen', _continue, when=lambda o: o['state'] in ('CAPTAIN_REVIEW', 'READY', 'EXECUTE', 'VERIFY')),
               Verb('abbrechen', 'Lauf beenden', lambda h, o, a: h.mission_lifecycle(o, 'beenden'),
                    when=lambda o: o['state'] in ('READY', 'CAPTAIN_REVIEW', 'PAUSED', 'EXECUTE'))]))
