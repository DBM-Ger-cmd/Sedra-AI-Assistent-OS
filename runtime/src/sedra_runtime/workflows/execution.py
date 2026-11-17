"""The ControlMaster handler: revalidation, mandatory bound gate, then one attempt."""
import json
from pathlib import Path
from ..core.request_binding import digest
from .engine import LocalN8n, configuration, inputs
from .policy import executable, PROFILE
from . import lokal, live


def context(control, mission, request):
    from .modellwahl import selection
    project = control.workspace.parents[1]
    cfg = configuration(project)
    art = lokal.gesamt_bewertung(request.get('workflow'), bool(cfg.get('enabled')))
    if not art['executable']:
        raise ValueError(art['reason'])
    data = inputs(request.get('inputs', {}))
    profil = art['profile']
    modellwahl = selection(request['workflow'])
    if profil == lokal.PROFILE:
        doc, cfg = request['workflow'], {'profil': 'lokal'}
    else:
        doc = executable(request.get('workflow'))
        if not cfg.get('enabled'):
            raise ValueError('n8n_not_configured')
    binding = {'mission_id': mission['identity']['mission_id'], 'step_id': request.get('id'),
               'plan_revision': mission.get('plan_revision', 0), 'workflow_digest': digest(request['workflow']),
               'inputs_digest': digest(data), 'profile': profil, 'config': cfg,
               'guard_rules_digest': digest({'rules': control.guard.rules, 'defaults': control.guard.defaults})}
    if modellwahl['provider'] != 'llama-cpp-server' or modellwahl['model'] is not None:
        binding['model_selection'] = modellwahl
    return doc, data, cfg, binding


def _modell(control, mission_id, workflow=None):
    """KI-Knoten verwenden die gespeicherte lokale oder NVIDIA-Modellwahl mit geprüftem JSON-Schema."""
    router = getattr(control, 'model_router', None)
    if router is None:
        return None
    from .modellwahl import selection
    wahl = selection(workflow or {})

    def fragen(nachrichten, schema):
        antwort = router.chat(mission_id, nachrichten, provider=wahl['provider'], model=wahl['model'], schema=schema, temperature=0, max_tokens=1200)
        return antwort.get('parsed')
    return fragen


def _live_melder(project, mission, workflow):
    """Meldet jeden Schritt eines Laufs für den Reiter Live (workflows/live.py); None, wenn der Workflow nicht gespeichert ist. Nur Anzeige."""
    wid = ((mission.get('context') or {}).get('n8n_workflow') or {}).get('id')
    if not wid:
        return None
    ids, _, _ = lokal.schritte(workflow)
    prozess, mid = live.prozess_fuer(wid), mission['identity']['mission_id']

    def melden(i, name, zustand, text):
        live.melde(project, prozess, None if i is None else 's%d' % i, zustand, text=text, lauf=mid, workflow_id=wid, ids=ids, captain=False)
    return melden


def execute(control, mission, request, token=None):
    mid = mission['identity']['mission_id']
    try:
        doc, data, cfg, binding = context(control, mission, request)
    except ValueError as exc:
        return {'status': 'blocked', 'error': str(exc), 'artifacts': []}
    eigen = binding['profile'] == lokal.PROFILE
    target = ('sedra-lokal://workflow/' if eigen else cfg['base_url'] + '/sedra-workflow/') + binding['workflow_digest']
    action = 'run_sedra_workflow' if eigen else 'run_n8n_workflow'
    verdict = control.guard.evaluate(action, mission_id=mid, target=target)
    if verdict['decision'] == 'BLOCK':
        return {'status': 'blocked', 'guard': verdict, 'artifacts': []}
    if not control.guard.authorize(token, mission_id=mid, action=action, target=target, request_binding=binding)['authorized']:
        risiken = ['Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen.']
        if eigen:
            bew = lokal.bewerten(request['workflow'])
            risiken = ['SEDRA-Eigenablauf, ganz lokal: kein Netz, keine Cloud.',
                       'Eigener Code läuft in einer abgeschotteten Node-Umgebung ohne Datei- und Netzzugriff.']
            if bew.get('schreibt'):
                risiken.append('Schreibt in lokale Tabellen: ' + ', '.join(bew['schreibt']) + '.')
            if bew.get('braucht_modell'):
                from .modellwahl import selection
                wahl=selection(request['workflow'])
                if wahl['provider']=='nvidia':
                    risiken[0]='SEDRA führt den Workflow lokal aus; KI-Schritte senden ihren Text an die ausdrücklich gewählte NVIDIA-API.'
                    risiken.append('NVIDIA-Modell: '+wahl['model']+'. Der Rechnungstext des KI-Schritts wird an diesen Anbieter übertragen.')
                else:risiken.append('Fragt das lokale Sprachmodell von SEDRA; der Rechnungstext verlässt den Rechner nicht.')
        gate = control.guard.create_gate(mid, action, target, request_binding=binding, risks=risiken, rollback_available=False)
        return {'status': 'captain_required', 'gate': gate, 'artifacts': []}
    folder = control.workspace / mid
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / ('lokal-attempt.json' if eigen else 'n8n-attempt.json')
    # A spent token cannot cause an implicit repeat after timeout, artifact failure or restart.
    try:
        with marker.open('x', encoding='utf-8') as stream:
            json.dump({'binding': digest(binding), 'status': 'started'}, stream)
    except FileExistsError:
        return {'status': 'failed', 'error': 'n8n_attempt_already_started', 'artifacts': []}
    control.audit.append('N8N_EXECUTION_STARTED', component='workflows', mission_id=mid,
                         payload={'step_id': request.get('id'), 'binding_digest': digest(binding), 'profile': PROFILE})
    try:
        if eigen:
            result = lokal.ausfuehren(request['workflow'], data, control.workspace.parents[1], modell=_modell(control, mid, request['workflow']), live=_live_melder(control.workspace.parents[1], mission, request['workflow']))
        else:
            result = LocalN8n(cfg).run(request['workflow'], data)
    except Exception:
        result = {'status': 'failed', 'error': 'n8n_adapter_unavailable', 'cleanup_errors': []}
    extra_artifacts = []
    if result.get('rechnungsauswertung') is not None:
        from .rechnung_dashboard import render, FILENAME, output_path
        auswertung = result['rechnungsauswertung']
        auswertung.update(run_id=mid, revision=((mission.get('context') or {}).get('n8n_workflow') or {}).get('revision'))
        try:
            dashboard_path = output_path(folder,request['workflow'])
            dashboard_path.parent.mkdir(parents=True,exist_ok=True)
            with dashboard_path.open('x', encoding='utf-8') as stream:
                stream.write(render(auswertung))
            extra_artifacts.append(control.artifacts.register(mid, dashboard_path, source_component='workflows:rechnung-dashboard'))
            result['dashboard'] = {'status': 'created', 'filename': FILENAME, 'artifact_id': extra_artifacts[-1]['artifact_id']}
        except Exception as exc:
            # Ein Berichtsfehler darf bereits ausgeführte Tabellenänderungen nicht zur Wiederholung freigeben.
            result['dashboard'] = {'status': 'failed', 'error': type(exc).__name__}
    path = folder / ('lokal-result.json' if eigen else 'n8n-result.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
    artifact = control.artifacts.register(mid, path, source_component='workflows:lokal' if eigen else 'workflows:n8n')
    control.audit.append('N8N_EXECUTION_FINISHED', component='workflows', mission_id=mid,
                         payload={'status': result['status'], 'error': result.get('error'),
                                  'remote_workflow_id': result.get('remote_workflow_id'), 'cleanup_errors': result.get('cleanup_errors')})
    return {'status': result['status'], 'error': result.get('error'), ('lokal_result' if eigen else 'n8n_result'): result, 'artifacts': [artifact] + extra_artifacts}
