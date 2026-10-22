"""Zielkette einer Aufgabe (Spec 1, D1.1, ORC-13): Vorhaben → Projekt → Elternaufgaben (Wurzel zuerst) → Aufgabe.

Rein: keine Datenbank, keine Uhr. `parents` kommt aus `board.chain_rows` (Wurzel zuerst), Vorhaben und Projekt vom Auflöser
der Fassade (`{id, titel}` oder None). Der Text ist ein abgegrenzter Datenblock für das Modell; ist er zu lang, fallen Glieder
von vorn weg, die Aufgabe bleibt immer vollständig."""

HEAD = "=== Zielkette (Daten) ==="
TAIL = "=== Ende Zielkette ==="
MISSING = "Glied nicht gefunden"
CUT = "(gekürzt)"
LABEL = {"vorhaben": "Vorhaben", "projekt": "Projekt", "eltern": "Elternaufgabe", "aufgabe": "Aufgabe"}


def _title(row):
    if not row:
        return None
    title = row.get("titel", row.get("title"))
    return title if isinstance(title, str) and title else None


def _line(link):
    return f"{LABEL[link['art']]} {link['id']}: {link['titel'] if link['titel'] is not None else MISSING}"


def build(task, parents, project, goal, max_chars=4000):
    glieder = []
    if task.get("goal_ref"):
        glieder.append({"art": "vorhaben", "id": task["goal_ref"], "titel": _title(goal)})
    if task.get("project_id"):
        glieder.append({"art": "projekt", "id": task["project_id"], "titel": _title(project)})
    parents = list(parents or [])
    top = parents[0] if parents else task
    if top.get("parent_id"):
        glieder.append({"art": "eltern", "id": top["parent_id"], "titel": None})
    for row in parents:
        glieder.append({"art": "eltern", "id": row["id"], "titel": _title(row)})
    glieder.append({"art": "aufgabe", "id": task["id"], "titel": _title(task)})

    own = [_line(glieder[-1])]
    if task.get("description"):
        own.append(str(task["description"]))
    before = [_line(g) for g in glieder[:-1]]
    cut = False
    while True:
        lines = [HEAD] + ([CUT] if cut else []) + before + own + [TAIL]
        text = "\n".join(lines)
        if len(text) <= max_chars or not before:
            break
        before.pop(0)
        cut = True
    return {"glieder": glieder, "text": text}
