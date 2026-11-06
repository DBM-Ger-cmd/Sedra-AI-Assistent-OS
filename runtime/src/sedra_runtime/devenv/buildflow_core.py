import copy
import re
import uuid

WINDOWS = {"now": "jetzt", "night": "nacht"}


def _clean_title(title):
    if not isinstance(title, str):
        raise ValueError("bad title")
    cleaned = " ".join(title.split())
    if not cleaned:
        raise ValueError("bad title")
    return cleaned


def _check_spec(spec):
    if not isinstance(spec, str):
        raise ValueError("bad spec")
    if not re.fullmatch(r'[A-Za-z0-9_]+', spec):
        raise ValueError("bad spec")
    return spec


def _check_window(window):
    if window not in ("now", "night"):
        raise ValueError("bad window")
    return window


def _check_rework(rework):
    if isinstance(rework, bool):
        raise ValueError("bad rework")
    if not isinstance(rework, int):
        raise ValueError("bad rework")
    if rework < 0 or rework > 10:
        raise ValueError("bad rework")
    return rework


def _check_priority(priority):
    if isinstance(priority, bool):
        raise ValueError("bad priority")
    if not isinstance(priority, int):
        raise ValueError("bad priority")
    if priority < 0 or priority > 9:
        raise ValueError("bad priority")
    return priority


def new_task(title, spec, *, now, seed="", review="", from_stage="", rework=3, priority=0, window="now", task_id=None):
    title = _clean_title(title)
    _check_spec(spec)
    window = _check_window(window)
    rework = _check_rework(rework)
    priority = _check_priority(priority)
    if task_id is None:
        task_id = "BF-" + uuid.uuid4().hex[:8].upper()
    history = [{"at": now, "event": "created", "from": None, "to": "draft", "note": ""}]
    task = {
        "id": task_id,
        "title": title,
        "spec": spec,
        "seed": str(seed),
        "review": str(review),
        "from_stage": str(from_stage),
        "rework": rework,
        "priority": priority,
        "window": window,
        "state": "draft",
        "created": now,
        "updated": now,
        "history": history,
        "result": {},
    }
    return task


def line(task):
    wtext = WINDOWS[task["window"]]
    return '{} [{}] V{} {} · {}'.format(task["id"], task["state"], task["priority"], wtext, task["title"])

STATES = ("draft", "checked", "spec_approved", "queued", "building", "built", "failed", "reported", "adopt_approved", "adopted", "cancelled")

TRANSITIONS = {
    ("draft", "check_ok"): "checked",
    ("draft", "check_failed"): "draft",
    ("checked", "approve_spec"): "spec_approved",
    ("checked", "check_failed"): "draft",
    ("spec_approved", "queue"): "queued",
    ("queued", "start"): "building",
    ("building", "finish_ok"): "built",
    ("building", "finish_failed"): "failed",
    ("failed", "requeue"): "queued",
    ("built", "report"): "reported",
    ("reported", "approve_adopt"): "adopt_approved",
    ("reported", "requeue"): "queued",
    ("adopt_approved", "adopt"): "adopted",
}

CANCEL_STATES = set(STATES) - {"building", "adopted", "cancelled"}
for _s in CANCEL_STATES:
    TRANSITIONS[(_s, "cancel")] = "cancelled"


def events_for(task):
    state = task["state"]
    evts = []
    for (s, e), _ in TRANSITIONS.items():
        if s == state:
            evts.append(e)
    return sorted(evts)


def can(task, event):
    state = task["state"]
    return (state, event) in TRANSITIONS


def transition(task, event, now, note="", **changes):
    for name in changes:
        if name not in ("review", "from_stage", "result"):
            raise ValueError("unknown change: " + name)
    state = task["state"]
    event_exists = any(e == event for (s, e) in TRANSITIONS)
    if not event_exists:
        raise ValueError("unknown_event: " + event)
    if (state, event) not in TRANSITIONS:
        raise ValueError("illegal_transition: " + state + " " + event)
    new_state = TRANSITIONS[(state, event)]
    new_task = copy.deepcopy(task)
    new_task["state"] = new_state
    new_task["updated"] = now
    new_task["history"].append({"at": now, "event": event, "from": state, "to": new_state, "note": note})
    if "review" in changes:
        new_task["review"] = changes["review"]
    if "from_stage" in changes:
        new_task["from_stage"] = changes["from_stage"]
    if "result" in changes:
        new_task["result"].update(changes["result"])
    return new_task

def queue_order(tasks):
    queued = [t for t in tasks if t["state"] == "queued"]
    return sorted(queued, key=lambda t: (-t["priority"], t["created"], t["id"]))


def pick_next(tasks, night=False):
    ordered = queue_order(tasks)
    for t in ordered:
        if t["window"] == "night" and not night:
            continue
        return t
    return None
