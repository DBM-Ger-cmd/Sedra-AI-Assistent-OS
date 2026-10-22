from datetime import datetime

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MODES = ("normal", "drain", "exklusiv")
STATES = ("aus", "startet", "bereit", "drain", "exklusiv", "gesperrt")


def _parse_time(text):
    return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ')


def effective_priority(row, now, cfg):
    if 'priority' not in row:
        raise ValueError('priority_invalid')
    p = row['priority']
    if type(p) is not int or isinstance(p, bool) or p < 0 or p > 9:
        raise ValueError('priority_invalid')

    if 'age_after_s' not in cfg:
        raise ValueError('age_after_s_invalid')
    aas = cfg['age_after_s']
    if type(aas) is not int or isinstance(aas, bool) or aas < 1:
        raise ValueError('age_after_s_invalid')

    if 'age_cap' not in cfg:
        raise ValueError('age_cap_invalid')
    ac = cfg['age_cap']
    if type(ac) is not int or isinstance(ac, bool) or ac < 0:
        raise ValueError('age_cap_invalid')

    try:
        enqueued_dt = _parse_time(row['enqueued'])
    except (KeyError, ValueError, TypeError):
        raise ValueError('time_invalid')
    try:
        now_dt = _parse_time(now)
    except (ValueError, TypeError):
        raise ValueError('time_invalid')

    delta = now_dt - enqueued_dt
    waited = max(0, int(delta.total_seconds()))

    if p >= ac:
        return p

    return min(ac, p + waited // aas)


def order(rows, now, cfg):
    if not rows:
        return []
    result = list(rows)
    result.sort(key=lambda r: (-effective_priority(r, now, cfg), str(r.get('enqueued', '')), str(r.get('run_id', ''))))
    return result


def admit(server, active, waiting, mode, now, cfg):
    valid_modes = ('normal', 'drain', 'exklusiv')
    valid_states = ('aus', 'startet', 'bereit', 'drain', 'exklusiv', 'gesperrt')

    if mode not in valid_modes:
        raise ValueError('mode_invalid')
    if server['state'] not in valid_states:
        raise ValueError('server_state_invalid')

    if mode != 'normal' or server['state'] not in ('aus', 'bereit'):
        return []

    ordered = order(waiting, now, cfg)

    if server['state'] == 'aus':
        if len(active) == 0:
            if ordered:
                return [ordered[0]['run_id']]
            return []
        return []

    if server['state'] == 'bereit':
        slots = server['slots']
        if type(slots) is not int or isinstance(slots, bool) or slots < 1 or slots > 8:
            raise ValueError('slots_invalid')
        count = max(0, slots - len(active))
        return [r['run_id'] for r in ordered[:count]]


def decide_reason(server, wanted_recipe, mode, active, cfg):
    valid_modes = ('normal', 'drain', 'exklusiv')
    valid_states = ('aus', 'startet', 'bereit', 'drain', 'exklusiv', 'gesperrt')

    if mode not in valid_modes:
        raise ValueError('mode_invalid')
    if server['state'] not in valid_states:
        raise ValueError('server_state_invalid')

    if server['state'] == 'gesperrt':
        return 'gesperrt'

    if mode == 'exklusiv' or server['state'] == 'exklusiv':
        owner = server.get('owner', '')
        if not owner:
            owner = '?'
        return 'exklusiv:' + owner

    if mode == 'drain' or server['state'] == 'drain':
        return 'drain'

    if server['state'] == 'startet':
        return 'server_startet'

    if server['state'] == 'aus':
        if active:
            return 'server_startet'
        return None

    if server['state'] == 'bereit':
        swap = cfg.get('swap', 'none')
        if wanted_recipe and server.get('recipe') != wanted_recipe:
            if swap == 'idle' and not active:
                pass
            elif isinstance(swap, dict) and swap.get('fallback') == server.get('recipe'):
                pass
            else:
                return 'model_swap_not_allowed'

        slots = server['slots']
        if type(slots) is not int or isinstance(slots, bool) or slots < 1 or slots > 8:
            raise ValueError('slots_invalid')

        if len(active) >= slots:
            return 'kein_slot'

        return None

def needs_cloud_offer(waiting, now, cfg):
    if not waiting:
        return None
    if 'queue_max' not in cfg or type(cfg['queue_max']) is not int or isinstance(cfg['queue_max'], bool) or cfg['queue_max'] < 0:
        raise ValueError('queue_max_invalid')
    if 'wait_max_s' not in cfg or type(cfg['wait_max_s']) is not int or isinstance(cfg['wait_max_s'], bool) or cfg['wait_max_s'] < 0:
        raise ValueError('wait_max_s_invalid')
    queue_max = cfg['queue_max']
    wait_max_s = cfg['wait_max_s']
    def _oldest_key(r):
        if isinstance(r, dict):
            return (r['enqueued'], r['run_id'])
        return (r[1], r[0])
    if len(waiting) > queue_max:
        oldest = min(waiting, key=_oldest_key)
        run_id = oldest['run_id'] if isinstance(oldest, dict) else oldest[0]
        return {"run_id": run_id, "grund": 'schlange'}
    oldest = min(waiting, key=_oldest_key)
    if isinstance(oldest, dict):
        run_id = oldest['run_id']
        enqueued = oldest['enqueued']
    else:
        run_id, enqueued, priority = oldest
    try:
        enqueued_dt = _parse_time(enqueued)
    except (ValueError, TypeError):
        raise ValueError('time_invalid')
    try:
        now_dt = _parse_time(now)
    except (ValueError, TypeError):
        raise ValueError('time_invalid')
    delta = now_dt - enqueued_dt
    waited = max(0, int(delta.total_seconds()))
    if waited > wait_max_s:
        return {"run_id": run_id, "grund": 'wartezeit'}
    return None
