import re

SERVER_ERROR_RE = re.compile(r'HTTP Error 5\d\d|HTTP 5\d\d|Connection(Reset|Aborted|Refused)|RemoteDisconnected', re.IGNORECASE)

def _classify_stopped_by(stopped_by, error, stage_passed):
    if stopped_by == "error":
        if error is not None and SERVER_ERROR_RE.search(str(error)):
            return "server"
        return "connection"
    if stopped_by == "garbage":
        return "server"
    if stopped_by == "server_crash":
        return "server"
    if stopped_by == "no_tool_call":
        return "connection"
    if stopped_by == "answer_cut":
        return "behaviour"
    if stopped_by == "runaway":
        return "behaviour"
    if stopped_by == "loop":
        return "behaviour"
    if stopped_by == "quality":
        return "behaviour"
    if stopped_by == "turns":
        return "budget"
    if stopped_by == "time":
        return "budget"
    if stopped_by == "calls":
        return "budget"
    if stopped_by == "tokens":
        return "budget"
    if stopped_by == "hand_in":
        if stage_passed is False:
            return "understanding"
        return "ok"
    return "behaviour"

def classify(run):
    stopped_by = run.get("stopped_by")
    error = run.get("error")
    stage_passed = run.get("stage_passed")
    return _classify_stopped_by(stopped_by, error, stage_passed)

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def summary(runs):
    layers = ["server", "connection", "behaviour", "budget", "understanding", "ok"]
    result = {}
    for layer in layers:
        result[layer] = {"runs": 0, "seconds": 0, "tokens": 0}
    for run in runs:
        layer = classify(run)
        result[layer]["runs"] += 1
        seconds = run.get("seconds")
        if _is_number(seconds):
            result[layer]["seconds"] += seconds
        tokens = run.get("completion_tokens")
        if _is_number(tokens):
            result[layer]["tokens"] += tokens
    return result

def shares(table, key="seconds"):
    layers = ["server", "connection", "behaviour", "budget", "understanding", "ok"]
    total = 0
    for layer in layers:
        value = table[layer].get(key, 0)
        if _is_number(value):
            total += value
    
    if total == 0:
        return {layer: 0 for layer in layers}
    
    result = {}
    for layer in layers:
        value = table[layer].get(key, 0)
        if _is_number(value):
            result[layer] = round(100 * value / total)
        else:
            result[layer] = 0
    return result

def cell(runs, key="seconds"):
    table = summary(runs)
    layer_shares = shares(table, key)
    
    short_names = {
        "server": "1",
        "connection": "2",
        "behaviour": "3",
        "budget": "4",
        "understanding": "5",
        "ok": "ok"
    }
    
    parts = []
    for layer in ["server", "connection", "behaviour", "budget", "understanding", "ok"]:
        short = short_names[layer]
        percent = layer_shares[layer]
        parts.append(f"{short}:{percent}")
    
    return " ".join(parts)
