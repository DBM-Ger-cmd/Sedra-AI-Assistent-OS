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


def _selbstabbild_pruefen(hub, oid, args):
    from . import selbstabbild
    return {'probleme': selbstabbild.pruefen(), 'abweichung': selbstabbild.abweichung(_store(hub))}


def _selbstabbild_anlegen(hub, oid, args):
    from . import selbstabbild
    with hub.lock:
        out = selbstabbild.anlegen(_store(hub))
        hub.runtime.audit.append('WORKFLOW_SELBSTABBILD_ERZEUGT', component='workflows',
                                 payload={'ablaeufe': [{'workflow_id': r['id'], 'revision': r['revision'], 'status': r['status']} for r in out]})
    return {'ergebnis': out}


def _live(hub, oid, args):
    """Laufende Prozesse (workflows/live.py): was die Prozesse selbst melden, mit dem Diagramm dazu. Nur lesen."""
    from . import live
    records = _store(hub).listing()
    out = []
    for satz in live.lesen(hub.project_root):
        prefix = 'sa-%s-' % satz['prozess']
        rec = next((r for r in records if any(str(n.get('id', '')).startswith(prefix) for n in r['workflow'].get('nodes', []))), None)
        namen = {n['id']: n['name'] for n in rec['workflow']['nodes']} if rec else {}
        name = lambda schritt: namen.get('%s%s' % (prefix, schritt)) if schritt else None
        satz['verlauf'] = [dict(e, schritt_name=name(e.get('schritt'))) for e in satz['verlauf'][-12:]]
        out.append(dict(satz, workflow_id=rec['id'] if rec else None, titel=rec['workflow']['name'] if rec else satz['prozess'], schritt_name=name(satz.get('schritt'))))
    zaehler = {z: sum(1 for p in out if p['zustand'] == z and not p['veraltet']) for z in live.ZUSTAENDE}
    zaehler['veraltet'] = sum(1 for p in out if p['veraltet'])
    return {'status': 'erledigt', 'prozesse': out, 'zaehler': zaehler}


def _fabrik(hub, oid, args):
    """Was die Harness gerade tut (workflows/fabrik.py): Läufe, aktive Aufgaben, offene Freigaben. Nur lesen; ohne Harness eine leere Übersicht."""
    from . import fabrik
    h = getattr(hub, 'harness', None)
    if h is None:
        return dict(fabrik.uebersicht([], [], []), status='erledigt')
    from ..harness import aufgabe as harness_aufgabe
    laeufe = h.laeufe.alle()
    aufgaben = [harness_aufgabe.oeffentlich(a, lauf_namen=h._lauf_namen()) for a in h.aufgaben.alle('aktiv')]
    try:
        offen = hub.decisions_view()['items']                          # alles im Posteingang: Missionen, Anträge, Harness-Karten
    except (AttributeError, KeyError, TypeError):
        offen = h.entscheidungen()
    out = fabrik.uebersicht(laeufe, aufgaben, offen, h.laeufe.belegt())
    out['status'] = 'erledigt'
    out['angehalten'] = fabrik.angehalten(hub.project_root)
    return out


def _fabrik_status(hub, oid, args):
    """Nur die Haltemarke (billig genug für eine Abfrage alle paar Sekunden aus jedem Reiter)."""
    from . import fabrik
    return {'status': 'erledigt', 'angehalten': fabrik.angehalten(hub.project_root)}


def _fabrik_stopp(hub, oid, args):
    """Der rote Knopf: Fabrik sofort anhalten (workflows/fabrik.py `notaus`). Kein Gate: Anhalten ist immer erlaubt; nur das Freigeben ist die Entscheidung des Captains."""
    from . import fabrik
    h = getattr(hub, 'harness', None)
    if h is None:
        return {'status': 'erledigt', 'marke': fabrik.anhalten(hub.project_root), 'laeufe': [], 'aufgaben': [], 'antworten': [], 'bau': None, 'prozesse': [], 'fehler': []}
    return dict(fabrik.notaus(h, hub.project_root, 'Notaus durch den Captain (roter Knopf)'), status='erledigt')


def _fabrik_freigeben(hub, oid, args):
    from . import fabrik
    war = fabrik.freigeben(hub.project_root)
    h = getattr(hub, 'harness', None)
    if war and h is not None:
        try:
            h._audit('FABRIK_FREIGEGEBEN', {'von': 'captain'})
        except Exception:
            pass
    return {'status': 'erledigt', 'war_angehalten': war}


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
                    Verb('pruefen', 'Kompatibilität prüfen', _check),
                    Verb('selbstabbild_pruefen', 'Selbstabbild gegen die Quellen prüfen', _selbstabbild_pruefen),
                    Verb('selbstabbild_anlegen', 'Abläufe von SEDRA aus den Quellen anlegen', _selbstabbild_anlegen),
                    Verb('live', 'Laufende Prozesse', _live),
                    Verb('fabrik', 'Die Fabrikhalle', _fabrik), Verb('fabrik_status', 'Fabrik: angehalten?', _fabrik_status),
                    Verb('fabrik_stopp', 'Fabrik anhalten (roter Knopf)', _fabrik_stopp), Verb('fabrik_freigeben', 'Fabrik wieder freigeben', _fabrik_freigeben)]))
    canonical = registry.get('workflow')
    registry.register(registry.Kind('scenario', 'Szenario Studio',
        lambda h, oid: dict(_read(h, oid), type='scenario'),
        lambda h, p: [dict(item, type='scenario') for item in _listing(h, p)],
        verbs=canonical.verbs, type_verbs=canonical.type_verbs, source='workflows'))
    registry.register(registry.Kind('workflow_run', 'Workflow-Lauf', _run_read, _runs,
        verbs=[Verb('fortsetzen', 'Nach Freigabe fortsetzen', _continue, when=lambda o: o['state'] in ('CAPTAIN_REVIEW', 'READY', 'EXECUTE', 'VERIFY')),
               Verb('abbrechen', 'Lauf beenden', lambda h, o, a: h.mission_lifecycle(o, 'beenden'),
                    when=lambda o: o['state'] in ('READY', 'CAPTAIN_REVIEW', 'PAUSED', 'EXECUTE'))]))
