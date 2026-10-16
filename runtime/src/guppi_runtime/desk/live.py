"""Live-Zeilen je Aufgabe (SHELL_WERKZEUG_VERTRAG_v1 §10, Cockpit-Regel 5: „Live – was gerade gebaut wird“).

Ehrlich gesagt, was das ist: die Runtime schreibt heute kein laufendes Protokoll je Aufgabe. Was sie schreibt, ist belastbarer –
das Schritt-Journal (je Schritt Beginn, Ende, Versuche, Ergebnis), die Artefakte, die Kandidatenversuche und die Audit-Kette.
Dieses Modul macht daraus die Zeilen, die der Captain sehen will, und nummeriert sie fortlaufend, damit der Ereignisstrom nur das
Neue schicken muss. Es erfindet nichts: steht eine Zeile hier, dann steht ihr Inhalt so in der Mission oder im Audit.

`lines()` ist rein (Mission und Audit rein, Zeilen raus) und wird ohne Browser geprüft."""
from __future__ import annotations

KIND_WORD = {'out': '', 'step': '›', 'ok': '✓', 'bad': '✗', 'gate': '⟂', 'note': '·'}
MAX_LINES = 300

# Aus dem Audit wird nur das zur Zeile, was der Captain beim Zusehen wissen will. „message sent“, „message processed“ und jeder
# Zustandswechsel sind für die Kette wichtig und im Logbuch vollständig da – hier wären sie Rauschen über der eigentlichen Arbeit.
AUDIT_WORDS = {
    'GUARD_BLOCKED': 'Guard hat das abgelehnt',
    'CAPTAIN_GATE_CREATED': 'Freigabe angefragt',
    'CAPTAIN_GATE_APPROVED': 'freigegeben',
    'CAPTAIN_GATE_REJECTED': 'abgelehnt',
    'EXECUTION_FAILED': 'Ausführung fehlgeschlagen',
    'MODEL_CALL_FAILED': 'Modellaufruf fehlgeschlagen',
    'CANDIDATE_TESTS_RUN': 'Tests gelaufen',
    'LOCAL_SWITCH_CHANGED': 'Schalter geändert',
    'ROUTING_RECIPE_ADDED': 'Rezept hinzugefügt',
    'UIX_TOOL_DENIED': 'ein Werkzeug wurde abgewiesen',
}


def _ms(start, end):
    if not start or not end:
        return None
    try:
        from datetime import datetime
        delta = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    except Exception:
        return None
    return f'{delta:.1f} s' if delta >= 1 else f'{round(delta * 1000)} ms'


def _step_text(plan_steps, index, entry):
    step = plan_steps[index] if index < len(plan_steps) else {}
    name = step.get('description') or step.get('action') or entry.get('id') or f'Schritt {index + 1}'
    return f'Schritt {index + 1}: {name}'


def lines(mission, audit_events=(), limit=MAX_LINES):
    """Die Zeilen einer Aufgabe, älteste zuerst, fortlaufend nummeriert: {n, kind, line, at}."""
    out = []

    def say(kind, text, at=None):
        out.append({'n': len(out) + 1, 'kind': kind, 'line': text, 'at': at})

    identity = mission.get('identity') or {}
    plan = mission.get('plan') or {}
    plan_steps = plan.get('steps') or []
    execution = mission.get('execution') or {}
    journal = (execution.get('step_journal') or {}).get('steps') or []

    say('note', 'Aufgabe angelegt: ' + str((mission.get('captain_intent') or {}).get('original') or identity.get('mission_id')), identity.get('created_at'))
    if plan_steps:
        say('note', f'Plan steht: {len(plan_steps)} Schritt(e).')

    for index, entry in enumerate(journal):
        status = entry.get('status')
        text = _step_text(plan_steps, index, entry)
        took = _ms(entry.get('started_at'), entry.get('finished_at'))
        if status == 'COMPLETED':
            result = entry.get('result') or {}
            artifacts = result.get('artifacts') or []
            extra = f' ({len(artifacts)} Artefakt{"e" if len(artifacts) != 1 else ""})' if artifacts else ''
            say('step', text, entry.get('started_at'))
            say('ok', f'fertig{" in " + took if took else ""}{extra}', entry.get('finished_at'))
            for a in artifacts[:3]:
                if isinstance(a, dict) and a.get('path'):
                    say('out', str(a['path']).split('/')[-1].split('\\')[-1])
        elif status in ('RUNNING', 'STARTED'):
            say('step', text + ' – läuft', entry.get('started_at'))
        elif status == 'FAILED':
            say('step', text, entry.get('started_at'))
            say('bad', 'fehlgeschlagen: ' + str((entry.get('result') or {}).get('reason_code') or (entry.get('result') or {}).get('error') or 'Grund steht im Logbuch'),
                entry.get('finished_at'))
        if (entry.get('attempts') or 0) > 1:
            say('note', f'{entry["attempts"]} Versuche für diesen Schritt')

    for gate in ((mission.get('human_gates') or {}).get('pending') or []):
        request = gate.get('request') or {}
        say('gate', 'wartet auf dich: ' + str(request.get('exact_action') or 'Freigabe')
            + (' → ' + ', '.join(request.get('targets') or []) if request.get('targets') else ''), gate.get('created_at'))

    acceptance = execution.get('candidate_acceptance') or {}
    if acceptance:
        done = len(acceptance.get('completed') or [])
        if acceptance.get('status') == 'APPLIED':
            say('ok', f'Übernommen: {done} Datei(en) geschrieben.', acceptance.get('finished_at'))
        elif acceptance.get('status') == 'REVIEW_REQUIRED':
            say('bad', 'Übernahme steckengeblieben: ' + str(acceptance.get('error') or 'Grund im Logbuch'), acceptance.get('finished_at'))
        elif acceptance.get('status'):
            say('note', 'Übernahme ' + str(acceptance['status']).lower() + f' ({done} von {len((acceptance.get("plan") or {}).get("files") or [])})', acceptance.get('started_at'))
        if (acceptance.get('rollback') or {}).get('status') == 'ROLLED_BACK':
            say('ok', 'Zurückgenommen – die alten Dateien stehen wieder.', (acceptance['rollback']).get('finished_at'))

    mid = identity.get('mission_id')
    for event in audit_events:
        word = AUDIT_WORDS.get(event.get('event_type'))
        if word and event.get('mission_id') == mid:
            say('bad' if 'fehlgeschlagen' in word or 'abgelehnt' in word else 'note', word, event.get('timestamp'))

    for error in (execution.get('errors') or [])[:5]:
        say('bad', str(error)[:200])

    # Der Schlusssatz gehört ans Ende, auch wenn die Mission ihn nicht datiert: er bekommt die späteste Zeit, die vorkam.
    last = max([x['at'] for x in out if x['at']] or [''])
    phase = (mission.get('lifecycle') or {}).get('phase')
    if phase == 'COMPLETE':
        say('ok', 'Aufgabe fertig.', last)
    elif phase == 'FAILED':
        say('bad', 'Aufgabe fehlgeschlagen.', last)

    # Nach Zeit sortieren, aber stabil: Zeilen ohne Zeitstempel (ein „fertig“ direkt nach seinem Schritt) bleiben, wo sie gehört
    # werden – sie erben die Zeit der letzten Zeile davor. Danach wird neu nummeriert, damit `since` eine feste Bedeutung hat.
    stamp = ''
    for item in out:
        if item['at']:
            stamp = item['at']
        item['_sort'] = stamp
    out.sort(key=lambda x: (x['_sort'], 0))
    for n, item in enumerate(out, 1):
        item['n'] = n
        del item['_sort']
    return out[-limit:]


def tail(all_lines, since=0, limit=50):
    """Die Zeilen nach `since` – das, was der Strom nachschickt, wenn ein Werkzeug sich spät anschließt."""
    return [line for line in all_lines if line['n'] > since][:limit]


def signature(all_lines):
    """Wie viele Zeilen es gibt – das Einzige, was der Schnappschuss des Stroms vergleichen muss."""
    return len(all_lines)
