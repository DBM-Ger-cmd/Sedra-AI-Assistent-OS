"""Desk extension; the editor has no approval route and no engine credentials."""
from ..desk.actions import Verb
from ..core.request_binding import digest
from .store import WorkflowStore
from .schema import report, strict_json
from .policy import assessment
from .engine import configuration, inputs
from . import lokal
from .lokal_daten import Eingaben, Tabellen
from .versions import compare


def _store(hub):
    return WorkflowStore(hub.project_root)


def _object(kind, oid, title, state, **extra):
    return dict(type=kind, id=oid, title=title, state=state, summary=title, actions=[], links=[], **extra)


def _bewertung(hub, workflow):
    """Wie sich der Workflow ausführen lässt: n8n (wenn eingerichtet), der SEDRA-Eigenablauf oder gar nicht (mit Grund)."""
    try:
        bereit = bool(configuration(hub.project_root).get('enabled'))
    except ValueError:
        bereit = False
    return lokal.gesamt_bewertung(workflow, bereit)


def _workflow(record, hub):
    return _object('workflow', record['id'], record['workflow']['name'], 'gespeichert',
                   revision=record['revision'], digest=record['digest'], workflow=record['workflow'],
                   compatibility=report(record['workflow']), execution=_bewertung(hub, record['workflow']))


def _read(hub, oid):
    if oid == 'alle':
        try:
            engine = configuration(hub.project_root)
        except ValueError:
            engine = {'enabled': False, 'error': 'invalid_n8n_configuration'}
        return _object('workflow', 'alle', 'Workflows', 'bereit', items=_listing(hub, {}),
                       engine=engine, runs=_runs(hub, {}), eigenablauf={'node': bool(lokal.shutil.which('node'))}, tabellen=Tabellen(hub.project_root).liste())
    return dict(_workflow(_store(hub).read(oid), hub), revisions=_store(hub).revisions(oid))


def _listing(hub, payload):
    return [_workflow(record, hub) for record in _store(hub).listing()]


def _check(hub, oid, args):
    value = strict_json(args['text']) if 'text' in args else args.get('workflow')
    return dict(report(value), workflow=value, execution=_bewertung(hub, value))


def _save(hub, oid, args):
    with hub.lock:
        record = _store(hub).save(args.get('workflow'), oid, args.get('base_revision'), args.get('change_note'))
        hub.runtime.audit.append('WORKFLOW_REVISION_SAVED', component='workflows',
                                 payload={'workflow_id': record['id'], 'revision': record['revision'], 'digest': record['digest'],
                                          'record_digest': record['record_digest'], 'previous_revision': record['previous_revision']})
    return dict(_workflow(record, hub), revisions=_store(hub).revisions(record['id']))


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


def _abgelehnt_abgleichen(hub, satz):
    """Eine Meldung "wartet auf den Captain", deren Mission inzwischen angehalten oder beendet ist (Freigabe abgelehnt), zeigt die Live-Ansicht als Fehler statt ewig wartend."""
    from . import live
    if not (satz.get('zustand') == 'wartet' and satz.get('wartet_captain') and str(satz.get('lauf') or '').startswith('M-')):
        return satz
    try:
        phase = hub.runtime.missions.load(satz['lauf'])['lifecycle']['phase']
    except Exception:
        return satz
    if phase not in ('PAUSED', 'FAILED', 'CANCELLED', 'CLOSED'):
        return satz
    live.melde(hub.project_root, satz['prozess'], None, 'fehler', text='Freigabe abgelehnt, der Lauf ist angehalten')
    return next((s for s in live.lesen(hub.project_root) if s['prozess'] == satz['prozess']), satz)


def _live(hub, oid, args):
    """Laufende Prozesse (workflows/live.py): was die Prozesse selbst melden, mit dem Diagramm dazu. Nur lesen."""
    from . import live
    records = _store(hub).listing()
    out = []
    for satz in live.lesen(hub.project_root):
        satz = _abgelehnt_abgleichen(hub, satz)
        prefix = 'sa-%s-' % satz['prozess']
        ids = satz.get('ids') or {}
        if satz.get('workflow_id'):                                          # Lauf des Eigenablaufs: gespeicherter Workflow und Knoten stehen in der Meldung
            rec = next((r for r in records if r['id'] == satz['workflow_id']), None)
        else:
            rec = next((r for r in records if any(str(n.get('id', '')).startswith(prefix) for n in r['workflow'].get('nodes', []))), None)
        namen = {n['id']: n['name'] for n in rec['workflow']['nodes']} if rec else {}
        name = lambda schritt: (namen.get(ids.get(schritt)) if ids else namen.get('%s%s' % (prefix, schritt))) if schritt else None
        satz['verlauf'] = [dict(e, schritt_name=name(e.get('schritt'))) for e in satz['verlauf'][-12:]]
        out.append(dict(satz, workflow_id=rec['id'] if rec else None, titel=rec['workflow']['name'] if rec else satz['prozess'], schritt_name=name(satz.get('schritt'))))
    zaehler = {z: sum(1 for p in out if p['zustand'] == z and not p['veraltet']) for z in live.ZUSTAENDE}
    zaehler['veraltet'] = sum(1 for p in out if p['veraltet'])
    return {'status': 'erledigt', 'prozesse': out, 'zaehler': zaehler}


def _import_vorschau(hub, oid, args):
    """Die Vorschau eines n8n-Imports (workflows/vorschau.py): nur lesen, nichts wird gespeichert oder gestartet."""
    from . import vorschau
    return dict(vorschau.vorschau(args.get('text'), args.get('dateiname')), status='erledigt')


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
    result = next((r.get('n8n_result') or r.get('lokal_result') for r in reversed(m['execution']['results']) if r.get('n8n_result') or r.get('lokal_result')), None)
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
        check = _bewertung(hub, record['workflow'])
        if not check['executable']:
            raise ValueError(check['reason'])
        data = inputs(args.get('inputs', {}))
        if check['profile'] == lokal.PROFILE:
            for label in check.get('dateifelder', []):
                ref = data.get(label)
                if not isinstance(ref, dict):
                    raise ValueError('eingabe_datei_fehlt:' + label)
                Eingaben(hub.project_root).lesen(ref.get('datei'))
        elif not configuration(hub.project_root).get('enabled'):
            raise ValueError('n8n_not_configured')
        rt = hub.runtime
        m = rt.brain.create_mission('n8n: ' + record['workflow']['name'])
        mid = m['identity']['mission_id']
        m['context']['n8n_workflow'] = {'id': oid, 'revision': record['revision'], 'name': record['workflow']['name'], 'digest': record['digest']}
        m['plan_revision'] = 1
        m['plan'] = {'version': 1, 'revision': 1, 'status': 'ready', 'workflow': check['profile'],
                     'steps': [{'id': 'N8N-1', 'action': 'n8n_workflow', 'workflow': record['workflow'], 'inputs': data,
                                'execution_requirements': {'allowed_execution_locations': ['local'], 'data_class': 'internal', 'context_min_tokens': 0}}],
                     'dependencies': [], 'acceptance_criteria': [{'type': 'artifact_exists', 'min_count': 1}]}
        rt.missions.save(m)
        for phase in ('UNDERSTAND', 'PLAN', 'READY'):
            rt.missions.transition(m, phase)
        # This only reaches the mandatory gate. Nothing is approved here.
        rt.brain.run(mid, max_steps=2)
        if check['profile'] == lokal.PROFILE:                               # Reiter Live: der Lauf wartet auf die Freigabe des Captains
            try:
                from . import live as live_modul
                ids, _reihe, _start = lokal.schritte(record['workflow'])
                live_modul.melde(hub.project_root, live_modul.prozess_fuer(oid), 's0', 'wartet', text='Wartet auf deine Freigabe', lauf=mid, neu=True, ids=ids, workflow_id=oid, captain=True)
            except Exception:
                pass
        hub.events.publish('task.changed', {'id': mid})
        return _run_read(hub, mid)


def _tabellen(hub, oid, args):
    return {'status': 'erledigt', 'tabellen': Tabellen(hub.project_root).liste()}


def _tabelle_lesen(hub, oid, args):
    return dict(Tabellen(hub.project_root).lesen(args.get('name'), 200), status='erledigt')


def _tabelle_importieren(hub, oid, args):
    with hub.lock:
        out = Tabellen(hub.project_root).importieren(args.get('name'), args.get('text'), args.get('art', 'auto'), args.get('ersetzen', True) is not False)
        hub.runtime.audit.append('WORKFLOW_TABELLE_IMPORTIERT', component='workflows', payload={'tabelle': out['name'], 'zeilen': out['zeilen']})
    return dict(out, status='erledigt')


def _tabelle_zeile_speichern(hub, oid, args):
    with hub.lock:
        zeile = Tabellen(hub.project_root).zeile_speichern(args.get('name'), args.get('id'), args.get('werte'))
        hub.runtime.audit.append('WORKFLOW_TABELLE_ZEILE_GESPEICHERT', component='workflows', payload={'tabelle': str(args.get('name'))[:80], 'zeile': zeile['id']})
    return {'status': 'erledigt', 'zeile': zeile}


def _tabelle_zeile_loeschen(hub, oid, args):
    with hub.lock:
        out = Tabellen(hub.project_root).zeile_loeschen(args.get('name'), args.get('id'))
        hub.runtime.audit.append('WORKFLOW_TABELLE_ZEILE_GELOESCHT', component='workflows', payload={'tabelle': out['name'], 'zeile': args.get('id')})
    return dict(out, status='erledigt')


def _eingabe_hochladen(hub, oid, args):
    import base64
    import binascii
    try:
        raw = base64.b64decode(str(args.get('data') or ''), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('eingabe_daten_ungueltig') from None
    summe = Eingaben(hub.project_root).speichern(raw)
    name = str(args.get('name') or 'datei')[-120:]
    hub.runtime.audit.append('WORKFLOW_EINGABE_GESPEICHERT', component='workflows', payload={'sha256': summe, 'groesse': len(raw)})
    return {'status': 'erledigt', 'datei': summe, 'name': name, 'groesse': len(raw)}


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
                    Verb('revision_lesen', 'Frühere Revision lesen', lambda h, o, a: _workflow(_store(h).read(a.get('id'), a.get('revision')), h)),
                    Verb('tabellen', 'Lokale Tabellen auflisten', _tabellen), Verb('tabelle_lesen', 'Tabelle lesen', _tabelle_lesen),
                    Verb('tabelle_importieren', 'Tabelle aus CSV oder JSON laden', _tabelle_importieren),
                    Verb('tabelle_zeile_speichern', 'Tabellenzeile ändern oder anlegen', _tabelle_zeile_speichern), Verb('tabelle_zeile_loeschen', 'Tabellenzeile löschen', _tabelle_zeile_loeschen), Verb('eingabe_hochladen', 'Datei für einen Lauf hochladen', _eingabe_hochladen),
                    Verb('pruefen', 'Kompatibilität prüfen', _check),
                    Verb('selbstabbild_pruefen', 'Selbstabbild gegen die Quellen prüfen', _selbstabbild_pruefen),
                    Verb('selbstabbild_anlegen', 'Abläufe von SEDRA aus den Quellen anlegen', _selbstabbild_anlegen),
                    Verb('live', 'Laufende Prozesse', _live),
                    Verb('import_vorschau', 'Vorschau eines n8n-Imports', _import_vorschau), Verb('fabrik', 'Die Fabrikhalle', _fabrik), Verb('fabrik_status', 'Fabrik: angehalten?', _fabrik_status),
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
