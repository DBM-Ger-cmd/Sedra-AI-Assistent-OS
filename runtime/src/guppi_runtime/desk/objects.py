"""Ein Objektmodell für alles (SHELL_WERKZEUG_VERTRAG_v1 §10.1).

Bis Build 7 brauchte jedes Fenster seine eigene Route und jedes Werkzeug seine eigene Form. Hier bekommt jedes Objekt dieselbe:

    {type, id, title, state, summary, actions: [...], links: [...]}

`state` ist ein Wort für den Zustand (`läuft`, `wartet`, `fertig`, `geladen` …), `summary` ein Satz in der Sprache des Captains,
`actions` sind die Verben, die *jetzt* möglich sind (actions.py sagt, was sie tun und welches Gate sie kennen), `links` zeigen auf
verwandte Objekte, damit ein Werkzeug einen Verweis anbieten kann, ohne ein anderes Werkzeug zu kennen.

Die alten Routen bleiben ein Jahr als Hülle (§10.1); dieses Modul liest dieselben Sichten des Hubs, es ersetzt nichts."""
from __future__ import annotations

PHASE_WORD = {'NEW': 'angenommen', 'UNDERSTAND': 'verstanden', 'PLAN': 'geplant', 'READY': 'bereit', 'EXECUTE': 'läuft',
              'VERIFY': 'in Prüfung', 'REVIEW': 'in Prüfung', 'CANDIDATE_REVIEW': 'Kandidat liegt vor',
              'CAPTAIN_REVIEW': 'wartet auf deine Durchsicht', 'REWORK': 'wird nachgebessert',
              'COMPLETE': 'fertig', 'FAILED': 'fehlgeschlagen', 'PAUSED': 'angehalten'}


def __getattr__(name):
    if name == 'TYPES':                                  # Kompatibilität: die Typen stehen im Register (Spec 0, D1)
        from .builtin_kinds import builtin
        return tuple(builtin().mark())
    raise AttributeError(name)


def _link(kind, oid, title, rel):
    return {'type': kind, 'id': oid, 'title': title, 'rel': rel}


def task_object(m, verbs=()):
    """Eine Aufgabe aus dem kompakten Missionsdatensatz (`_compact_mission`)."""
    steps = m.get('steps') or []
    done = min(m.get('steps_done') or 0, len(steps))
    waiting = (m.get('pending_gates') or 0) > 0
    phase = m.get('phase') or ''
    state = 'wartet auf dich' if waiting else PHASE_WORD.get(phase, phase.lower() or 'unbekannt')
    what = str(m.get('intent') or m.get('objective') or m.get('mission_id') or 'Aufgabe').strip()
    if waiting:
        summary = what + ' – wartet auf deine Freigabe.'
    elif phase == 'COMPLETE':
        summary = what + ' – fertig.'
    elif phase == 'FAILED':
        summary = what + ' – fehlgeschlagen; die Ursache steht im Logbuch.'
    elif phase == 'CANDIDATE_REVIEW':
        summary = what + ' – der Kandidat liegt vor; der Diff steht daneben.'
    elif steps:
        summary = what + f' – {state}, Schritt {min(done + 1, len(steps))} von {len(steps)}.'
    else:
        summary = what + f' – {state}.'
    links = [_link('logbook', 'audit', 'Logbuch', 'verlauf')]
    if waiting:
        links.insert(0, _link('decision', 'alle', 'Entscheidungen', 'wartet'))
    return {'type': 'task', 'id': m.get('mission_id'), 'title': what[:60], 'state': state, 'summary': summary,
            'steps': [{'n': i + 1, 'text': s, 'done': i < done, 'now': i == done} for i, s in enumerate(steps)],
            'progress': {'steps': len(steps), 'done': done, 'percent': round(100 * done / len(steps)) if steps else 0},
            'actions': list(verbs), 'links': links}


def candidate_object(mission, verbs=(), report=None):
    """Ein Kandidat: die Dateien, die eine Aufgabe ändern will, mit ihrem Stand im Übernahmeweg.

    `report` ist der Kandidatenbericht, wenn es ihn gibt. Aus ihm kommt `qualified`: ob die Runtime diesen Kandidaten überhaupt
    übernehmen würde. Ohne das böte die Oberfläche einen Knopf an, den die Runtime gleich darauf ablehnt – und der Captain bekäme
    eine Fehlermeldung statt einer Erklärung."""
    mid = (mission.get('identity') or {}).get('mission_id')
    execution = mission.get('execution') or {}
    acceptance = execution.get('candidate_acceptance') or {}
    plan = (mission.get('plan') or {})
    binding = ((plan.get('steps') or [{}])[0] or {}).get('binding') or {}
    changes = ((binding.get('inputs') or {}).get('changes') or [])
    status = acceptance.get('status')
    rollback = (acceptance.get('rollback') or {}).get('status')
    if rollback == 'ROLLED_BACK':
        state, summary = 'zurückgenommen', 'Die Übernahme ist zurückgenommen; die alten Dateien stehen wieder da.'
    elif status == 'APPLIED':
        state, summary = 'übernommen', f'Übernommen: {len(acceptance.get("completed") or [])} Datei(en) geschrieben, Rücknahme möglich.'
    elif status == 'REVIEW_REQUIRED':
        state, summary = 'braucht Durchsicht', 'Die Übernahme ist mittendrin stehen geblieben – nichts weiter tun, erst im Logbuch nachsehen.'
    elif status == 'RUNNING':
        state, summary = 'wird übernommen', 'Die Dateien werden gerade geschrieben.'
    elif changes:
        state, summary = 'vorgeschlagen', f'{len(changes)} Datei(en) geändert – Diff prüfen, dann übernehmen.'
    else:
        state, summary = 'keiner', 'Diese Aufgabe hat keinen Kandidaten; sie ändert keine Dateien.'
    qualified = bool((report or {}).get('ready_for_merge'))
    if changes and not status and not qualified:
        summary += ' Übernehmen geht erst, wenn die Tests gelaufen sind.'
    return {'type': 'candidate', 'id': mid, 'title': 'Kandidat · ' + (changes[0]['path'].split('/')[-1] if changes else str(mid)),
            'state': state, 'summary': summary, 'qualified': qualified,
            'files': [{'path': c.get('path'), 'bytes': len(c.get('content') or '')} for c in changes],
            'actions': list(verbs), 'links': [_link('task', mid, 'Aufgabe', 'gehört zu')]}


def model_object(recipe, server=None, verbs=()):
    loaded = bool(recipe.get('loaded'))
    bits = []
    if recipe.get('model'):
        bits.append(str(recipe['model']).split('/')[-1].split('\\')[-1])
    if recipe.get('context_recommended'):
        bits.append('Kontext ' + str(recipe['context_recommended']))
    if not recipe.get('enabled'):
        bits.append('ausgeschaltet')
    if not recipe.get('model'):
        bits.append('kein Modell hinterlegt')
    state = 'geladen' if loaded else ('bereit' if recipe.get('enabled') and recipe.get('model') else 'nicht einsatzbereit')
    summary = recipe['id'] + ' – ' + (' · '.join(bits) or recipe.get('provider', ''))
    if loaded and (server or {}).get('context'):
        summary += ' · läuft mit Kontext ' + str(server['context'])
    return {'type': 'model', 'id': recipe['id'], 'title': recipe['id'], 'state': state, 'summary': summary,
            'roles': recipe.get('roles') or [], 'actions': list(verbs),
            'links': [_link('meter', 'meter', 'Guppy-Meter', 'kosten')]}


def intent_object(entry, state, summary, verbs=()):
    """Ein Vorhaben (Regel 8): der Satz des Captains, die Aufgaben daraus, und sonst nichts – es führt nichts aus."""
    return {'type': 'intent', 'id': entry['id'], 'title': entry['title'][:60], 'state': state,
            'summary': entry['title'] + ' – ' + summary, 'text': entry.get('text') or '',
            'tasks': list(entry.get('tasks') or []), 'created_at': entry.get('created_at'),
            'actions': list(verbs),
            'links': [_link('task', t, 'Aufgabe ' + t, 'daraus entstanden') for t in (entry.get('tasks') or [])[:8]]}


def boundary_object(view, verbs=()):
    """Modus und die vier Grenzen eines Projekts als Objekt – damit „Grenze ändern …“ irgendwohin führt (Regel 7)."""
    confirmed = bool(view.get('confirmed'))
    return {'type': 'boundary', 'id': view.get('project_id') or 'projekt', 'title': 'Modus und Grenzen',
            'state': 'bestätigt' if confirmed else 'nicht bestätigt',
            'summary': (view.get('sentence') or '') + ('' if confirmed else ' – ' + str(view.get('reason') or '')),
            'mode': view.get('mode'), 'boundaries': view.get('boundaries') or {}, 'confirmed': confirmed,
            'reason': view.get('reason'), 'note': view.get('note'), 'measured_limit': view.get('measured_limit'),
            'actions': list(verbs), 'links': []}


def decision_object(d):
    return {'type': 'decision', 'id': d['id'], 'title': d['title'], 'state': 'wartet',
            'summary': d['title'] + ' – ' + (d.get('describe') or ''),
            'actions': [{'verb': w, 'label': w, 'needs_gate': False} for w in d.get('ways') or []],
            'links': [_link('task', d['mission_id'], 'Aufgabe', 'gehört zu')] if d.get('mission_id') else []}


def skill_object(s):
    return {'type': 'skill', 'id': s.get('id'), 'title': s.get('name') or s.get('id'), 'state': 'vorhanden',
            'summary': (s.get('description') or '').strip() or 'Kein Beschreibungssatz hinterlegt.',
            'actions': [], 'links': []}


def project_object(p):
    return {'type': 'project', 'id': p.get('project_id') or p.get('name'), 'title': p.get('name') or 'Projekt',
            'state': 'offen', 'summary': (p.get('name') or 'Projekt') + ' – ' + str(p.get('workspace_path') or p.get('path') or ''),
            'actions': [], 'links': []}


def not_found(kind, oid):
    return {'type': kind, 'id': oid, 'title': str(oid), 'state': 'nicht gefunden',
            'summary': f'Dieses Objekt gibt es nicht (mehr). Im Logbuch ist es erhalten.', 'actions': [], 'links': []}
