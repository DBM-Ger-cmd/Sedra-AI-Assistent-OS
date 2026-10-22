from datetime import datetime

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MODES = ("normal", "drain", "exklusiv")
STATES = ("aus", "startet", "bereit", "drain", "exklusiv", "gesperrt")


def _time(text):
    try:
        return datetime.strptime(text, FORMAT)
    except (TypeError, ValueError):
        raise ValueError("time_invalid") from None


def _waited(row, now):
    return max(0, int((_time(now) - _time(row["enqueued"])).total_seconds()))


def _number(cfg, key, low):
    value = cfg.get(key) if isinstance(cfg, dict) else None
    if type(value) is not int or value < low:
        raise ValueError(key + "_invalid")
    return value


def _check(server, mode):
    if mode not in MODES:
        raise ValueError("mode_invalid")
    if server.get("state") not in STATES:
        raise ValueError("server_state_invalid")


def _slots(server):
    slots = server.get("slots")
    if type(slots) is not int or not 1 <= slots <= 8:
        raise ValueError("slots_invalid")
    return slots


def effective_priority(row, now, cfg):
    priority = row.get("priority")
    if type(priority) is not int or not 0 <= priority <= 9:
        raise ValueError("priority_invalid")
    after, cap = _number(cfg, "age_after_s", 1), _number(cfg, "age_cap", 0)
    if priority >= cap:
        return priority
    return min(cap, priority + _waited(row, now) // after)


def order(rows, now, cfg):
    keyed = [(-effective_priority(r, now, cfg), r["enqueued"], r["run_id"], r) for r in rows]
    keyed.sort(key=lambda k: k[:3])
    return [k[3] for k in keyed]


def admit(server, active, waiting, mode, now, cfg):
    _check(server, mode)
    if mode != "normal" or server["state"] not in ("aus", "bereit"):
        return []
    ranked = order(waiting, now, cfg)
    if server["state"] == "aus":
        return [] if active else [r["run_id"] for r in ranked[:1]]
    return [r["run_id"] for r in ranked[:max(0, _slots(server) - len(active))]]


def _swap_ok(server, active, cfg):
    swap = cfg.get("swap", "none")
    if swap == "idle":
        return not active
    return isinstance(swap, dict) and server.get("recipe") == swap.get("fallback")


def decide_reason(server, wanted_recipe, mode, active, cfg):
    _check(server, mode)
    state = server["state"]
    if state == "gesperrt":
        return "gesperrt"
    if mode == "exklusiv" or state == "exklusiv":
        return "exklusiv:" + str(server.get("owner") or "?")
    if mode == "drain" or state == "drain":
        return "drain"
    if state == "startet":
        return "server_startet"
    if state == "aus":
        return "server_startet" if active else None
    if wanted_recipe and server.get("recipe") != wanted_recipe and not _swap_ok(server, active, cfg):
        return "model_swap_not_allowed"
    return "kein_slot" if len(active) >= _slots(server) else None


def needs_cloud_offer(waiting, now, cfg):
    if not waiting:
        return None
    queue_max, wait_max = _number(cfg, "queue_max", 0), _number(cfg, "wait_max_s", 0)
    oldest = min(waiting, key=lambda r: (r["enqueued"], r["run_id"]))
    if len(waiting) > queue_max:
        return {"run_id": oldest["run_id"], "grund": "schlange"}
    if _waited(oldest, now) > wait_max:
        return {"run_id": oldest["run_id"], "grund": "wartezeit"}
    return None
