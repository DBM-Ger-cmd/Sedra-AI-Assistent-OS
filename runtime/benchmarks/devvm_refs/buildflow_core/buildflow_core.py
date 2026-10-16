import copy
import re
import uuid

STATES = ("draft", "checked", "spec_approved", "queued", "building", "built", "failed", "reported", "adopt_approved", "adopted", "cancelled")
TRANSITIONS = {
    ("draft", "check_ok"): "checked", ("draft", "check_failed"): "draft",
    ("checked", "approve_spec"): "spec_approved", ("checked", "check_failed"): "draft",
    ("spec_approved", "queue"): "queued",
    ("queued", "start"): "building",
    ("building", "finish_ok"): "built", ("building", "finish_failed"): "failed",
    ("failed", "requeue"): "queued",
    ("built", "report"): "reported",
    ("reported", "approve_adopt"): "adopt_approved", ("reported", "requeue"): "queued",
    ("adopt_approved", "adopt"): "adopted",
}
NOT_CANCELLABLE = ("building", "adopted", "cancelled")
CHANGES = ("review", "from_stage", "result")
WINDOWS = {"now": "jetzt", "night": "nacht"}
NAME = re.compile(r"[A-Za-z0-9_]+")


def _int_in(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"bad {name}")
    return value


def new_task(title, spec, *, now, seed="", review="", from_stage="", rework=3, priority=0, window="now", task_id=None):
    title = " ".join(str(title or "").split())
    if not title:
        raise ValueError("bad title")
    if not isinstance(spec, str) or not NAME.fullmatch(spec):
        raise ValueError("bad spec")
    if window not in WINDOWS:
        raise ValueError("bad window")
    return {"id": task_id or "BF-" + uuid.uuid4().hex[:8].upper(), "title": title, "spec": spec, "seed": str(seed), "review": str(review), "from_stage": str(from_stage),
            "rework": _int_in(rework, 0, 10, "rework"), "priority": _int_in(priority, 0, 9, "priority"), "window": window, "state": "draft", "created": now, "updated": now,
            "history": [{"at": now, "event": "created", "from": None, "to": "draft", "note": ""}], "result": {}}


def events_for(task):
    events = {event for (state, event) in TRANSITIONS if state == task["state"]}
    if task["state"] not in NOT_CANCELLABLE:
        events.add("cancel")
    return sorted(events)


def can(task, event):
    return event in events_for(task)


def transition(task, event, now, note="", **changes):
    known = {event for (_, event) in TRANSITIONS} | {"cancel"}
    if event not in known:
        raise ValueError(f"unknown_event: {event}")
    for key in changes:
        if key not in CHANGES:
            raise ValueError(f"unknown change: {key}")
    if not can(task, event):
        raise ValueError(f"illegal_transition: {task['state']} {event}")
    new_state = "cancelled" if event == "cancel" else TRANSITIONS[(task["state"], event)]
    result = copy.deepcopy(task)
    for key, value in changes.items():
        if key == "result":
            result["result"].update(value)
        else:
            result[key] = value
    result["history"].append({"at": now, "event": event, "from": task["state"], "to": new_state, "note": note})
    result["state"], result["updated"] = new_state, now
    return result


def queue_order(tasks):
    return sorted((t for t in tasks if t["state"] == "queued"), key=lambda t: (-t["priority"], t["created"], t["id"]))


def pick_next(tasks, night=False):
    for task in queue_order(tasks):
        if night or task["window"] != "night":
            return task
    return None


def line(task):
    return f"{task['id']} [{task['state']}] V{task['priority']} {WINDOWS[task['window']]} · {task['title']}"
