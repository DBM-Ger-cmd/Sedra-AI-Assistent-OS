"""The ControlMaster handler: revalidation, mandatory bound gate, then one attempt."""
import json
from pathlib import Path
from ..core.request_binding import digest
from .engine import LocalN8n, configuration, inputs
from .policy import executable, PROFILE


def context(control, mission, request):
    doc = executable(request.get('workflow'))
    data = inputs(request.get('inputs', {}))
    project = control.workspace.parents[1]
    cfg = configuration(project)
    if not cfg.get('enabled'):
        raise ValueError('n8n_not_configured')
    binding = {'mission_id': mission['identity']['mission_id'], 'step_id': request.get('id'),
               'plan_revision': mission.get('plan_revision', 0), 'workflow_digest': digest(request['workflow']),
               'inputs_digest': digest(data), 'profile': PROFILE, 'config': cfg,
               'guard_rules_digest': digest({'rules': control.guard.rules, 'defaults': control.guard.defaults})}
    return doc, data, cfg, binding


def execute(control, mission, request, token=None):
    mid = mission['identity']['mission_id']
    try:
        doc, data, cfg, binding = context(control, mission, request)
    except ValueError as exc:
        return {'status': 'blocked', 'error': str(exc), 'artifacts': []}
    target = cfg['base_url'] + '/sedra-workflow/' + binding['workflow_digest']
    action = 'run_n8n_workflow'
    verdict = control.guard.evaluate(action, mission_id=mid, target=target)
    if verdict['decision'] == 'BLOCK':
        return {'status': 'blocked', 'guard': verdict, 'artifacts': []}
    if not control.guard.authorize(token, mission_id=mid, action=action, target=target, request_binding=binding)['authorized']:
        gate = control.guard.create_gate(mid, action, target, request_binding=binding,
                                         risks=['Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen.'], rollback_available=False)
        return {'status': 'captain_required', 'gate': gate, 'artifacts': []}
    folder = control.workspace / mid
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / 'n8n-attempt.json'
    # A spent token cannot cause an implicit repeat after timeout, artifact failure or restart.
    try:
        with marker.open('x', encoding='utf-8') as stream:
            json.dump({'binding': digest(binding), 'status': 'started'}, stream)
    except FileExistsError:
        return {'status': 'failed', 'error': 'n8n_attempt_already_started', 'artifacts': []}
    control.audit.append('N8N_EXECUTION_STARTED', component='workflows', mission_id=mid,
                         payload={'step_id': request.get('id'), 'binding_digest': digest(binding), 'profile': PROFILE})
    try:
        result = LocalN8n(cfg).run(request['workflow'], data)
    except Exception:
        result = {'status': 'failed', 'error': 'n8n_adapter_unavailable', 'cleanup_errors': []}
    path = folder / 'n8n-result.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
    artifact = control.artifacts.register(mid, path, source_component='workflows:n8n')
    control.audit.append('N8N_EXECUTION_FINISHED', component='workflows', mission_id=mid,
                         payload={'status': result['status'], 'error': result.get('error'),
                                  'remote_workflow_id': result.get('remote_workflow_id'), 'cleanup_errors': result.get('cleanup_errors')})
    return {'status': result['status'], 'error': result.get('error'), 'n8n_result': result, 'artifacts': [artifact]}
