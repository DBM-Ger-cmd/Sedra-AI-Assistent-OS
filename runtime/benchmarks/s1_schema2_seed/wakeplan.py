FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_PARTS = {
    'assign': 2,
    'comment': 1,
    'captain': 1,
    'routine': 2,
    'unblocked': 2,
    'report': 1,
    'retry': 2,
}


def _validate_parts(parts):
    for p in parts:
        if p is None or p == '':
            raise ValueError('wake_ref_invalid')


def key_for(source, ref):
    if source not in _PARTS:
        raise ValueError('wake_source_unknown')
    expected = _PARTS[source]
    if isinstance(ref, (list, tuple)):
        parts = list(ref)
    else:
        parts = [ref]
    if len(parts) != expected:
        raise ValueError('wake_ref_invalid')
    _validate_parts(parts)
    return source + ':' + ':'.join(str(p) for p in parts)


def _parse_time(t):
    from datetime import datetime, timedelta
    return datetime.strptime(t, '%Y-%m-%dT%H:%M:%SZ')


def coalesce(open_wakeups, now, coalesce_s):
    from datetime import datetime, timedelta
    now_dt = _parse_time(now)
    cutoff_dt = now_dt + timedelta(seconds=coalesce_s)
    open_rows = [r for r in open_wakeups if r['done_at'] is None and r['coalesced_into'] is None]
    by_agent = {}
    for r in open_rows:
        by_agent.setdefault(r['agent_id'], []).append(r)
    groups = []
    for agent_id, rows in by_agent.items():
        rows_sorted = sorted(rows, key=lambda r: (_parse_time(r['due_at']), r['id']))
        leader = rows_sorted[0]
        leader_due = _parse_time(leader['due_at'])
        if leader_due > now_dt:
            continue
        members = []
        for r in rows_sorted[1:]:
            if _parse_time(r['due_at']) <= cutoff_dt:
                members.append(r)
        members.sort(key=lambda r: (_parse_time(r['due_at']), r['id']))
        groups.append({'leader': leader, 'members': members})
    groups.sort(key=lambda g: (_parse_time(g['leader']['due_at']), g['leader']['id']))
    return groups


def pick_task(tasks, blockers, prefer_task_id):
    blocker_map = {}
    for b in blockers:
        tid = b['task_id']
        if b['state'] not in ('erledigt', 'abgebrochen'):
            blocker_map.setdefault(tid, []).append(b)

    def has_open_blocker(task):
        return task['id'] in blocker_map

    def is_pickable(task):
        return (task['state'] in ('zugewiesen', 'offen')
                and (task.get('checkout_by') is None or task.get('checkout_by') == '')
                and not has_open_blocker(task))

    def is_eligible(task):
        return (task['state'] in ('zugewiesen', 'offen')
                and (task.get('checkout_by') is None or task.get('checkout_by') == ''))

    pickable = [t for t in tasks if is_pickable(t)]

    prefer = None
    if prefer_task_id is not None:
        prefer = next((t for t in pickable if t['id'] == prefer_task_id), None)
    if prefer is not None:
        return (prefer, 'ok')

    if pickable:
        pickable.sort(key=lambda t: (-t.get('priority', 0), t['created_at'], t['id']))
        return (pickable[0], 'ok')

    has_eligible = any(is_eligible(t) for t in tasks)
    if has_eligible:
        return (None, 'nur_blockiert')

    has_checkout = any(t.get('checkout_by') is not None and t.get('checkout_by') != '' for t in tasks)
    if has_checkout:
        return (None, 'ausgecheckt')

    return (None, 'keine_aufgabe')


def decide_run(agent, budget_state, standing, task_reason):
    valid_reasons = ('ok', 'nur_blockiert', 'ausgecheckt', 'keine_aufgabe')
    if task_reason not in valid_reasons:
        raise ValueError('wake_reason_unknown')
    valid_budget = ('ok', 'warnung', 'gestoppt', 'zu_wenig')
    if budget_state not in valid_budget:
        raise ValueError('budget_state_unknown')
    if agent['status'] != 'aktiv':
        return 'pausiert'
    if task_reason == 'ausgecheckt':
        return 'laeuft_schon'
    if task_reason == 'nur_blockiert':
        return 'blockiert'
    if task_reason == 'keine_aufgabe':
        return 'keine_aufgabe'
    if budget_state in ('gestoppt', 'zu_wenig'):
        return 'kein_budget'
    if standing:
        return 'lauf_dauerfreigabe'
    return 'antrag'
