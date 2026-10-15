import re

ORDER = ("server", "connection", "behaviour", "budget", "understanding", "ok")
SHORT = {"server": "1", "connection": "2", "behaviour": "3", "budget": "4", "understanding": "5", "ok": "ok"}
BY_END = {"garbage": "server", "server_crash": "server", "error": "connection", "no_tool_call": "connection",
          "answer_cut": "behaviour", "runaway": "behaviour", "loop": "behaviour", "quality": "behaviour",
          "turns": "budget", "time": "budget", "calls": "budget", "tokens": "budget"}
SERVER_TEXT = re.compile(r"HTTP Error 5\d\d|HTTP 5\d\d|Connection(Reset|Aborted|Refused)|RemoteDisconnected")


def classify(run):
    end = run.get("stopped_by")
    if end == "error" and SERVER_TEXT.search(str(run.get("error") or "")):
        return "server"
    if end == "hand_in":
        return "understanding" if run.get("stage_passed") is False else "ok"
    return BY_END.get(end, "behaviour")


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def summary(runs):
    table = {layer: {"runs": 0, "seconds": 0, "tokens": 0} for layer in ORDER}
    for run in runs:
        row = table[classify(run)]
        row["runs"] += 1
        row["seconds"] += _number(run.get("seconds"))
        row["tokens"] += _number(run.get("completion_tokens"))
    return table


def shares(table, key="seconds"):
    total = sum(table[layer][key] for layer in ORDER)
    return {layer: round(100 * table[layer][key] / total) if total else 0 for layer in ORDER}


def cell(runs, key="seconds"):
    part = shares(summary(runs), key)
    return " ".join(f"{SHORT[layer]}:{part[layer]}" for layer in ORDER)
