import uuid
from . import cron
from .store import immediate

ALL_FIELDS = ("agent_id", "catch_up", "cron", "id", "task_template", "title", "timezone")
REQUIRED_ORDER = ("agent_id", "title", "cron", "catch_up")
UPDATE_FIELDS = ("agent_id", "title", "cron", "timezone", "catch_up", "task_template")


def create(conn, fields, now):
    for key in sorted(fields.keys()):
        if key not in ALL_FIELDS:
            raise ValueError(f"routine_field_unknown:{key}")

    if "title" in fields:
        if not isinstance(fields["title"], str) or not fields["title"].strip():
            raise ValueError("routine_title_invalid")

    if "catch_up" in fields:
        if fields["catch_up"] not in ("nachholen", "auslassen"):
            raise ValueError("routine_catch_up_invalid")

    for key in REQUIRED_ORDER:
        if key not in fields or fields[key] is None:
            raise ValueError(f"routine_field_missing:{key}")

    tz = fields.get("timezone", "Europe/Berlin")
    cron_parsed = cron.parse(fields["cron"])
    next_run = cron.next_after(cron_parsed, now, tz)

    with immediate(conn):
        row = conn.execute(
            "SELECT id FROM agents WHERE id = ?", (fields["agent_id"],)
        ).fetchone()
        if row is None:
            raise ValueError("agent_not_found")

        routine_id = fields.get("id")
        if routine_id is None:
            routine_id = "R-" + uuid.uuid4().hex[:12]

        row = conn.execute(
            "SELECT id FROM routines WHERE id = ?", (routine_id,)
        ).fetchone()
        if row is not None:
            raise ValueError("routine_exists")

        conn.execute(
            "INSERT INTO routines (id, agent_id, title, cron, timezone, catch_up, enabled, task_template, last_run, next_run) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (
                routine_id,
                fields["agent_id"],
                fields["title"],
                fields["cron"],
                tz,
                fields["catch_up"],
                fields.get("task_template"),
                now,
                next_run,
            ),
        )

        return {
            "id": routine_id,
            "agent_id": fields["agent_id"],
            "title": fields["title"],
            "cron": fields["cron"],
            "timezone": tz,
            "catch_up": fields["catch_up"],
            "enabled": 1,
            "task_template": fields.get("task_template"),
            "last_run": now,
            "next_run": next_run,
        }


def _row_to_dict(row):
    return {
        "id": row["id"],
        "agent_id": row["agent_id"],
        "title": row["title"],
        "cron": row["cron"],
        "timezone": row["timezone"],
        "catch_up": row["catch_up"],
        "enabled": row["enabled"],
        "task_template": row["task_template"],
        "last_run": row["last_run"],
        "next_run": row["next_run"],
    }


def update(conn, rid, fields, now):
    for key in sorted(fields.keys()):
        if key not in UPDATE_FIELDS:
            raise ValueError(f"routine_field_unknown:{key}")

    if "title" in fields:
        if not isinstance(fields["title"], str) or not fields["title"].strip():
            raise ValueError("routine_title_invalid")

    if "catch_up" in fields:
        if fields["catch_up"] not in ("nachholen", "auslassen"):
            raise ValueError("routine_catch_up_invalid")

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM routines WHERE id = ?", (rid,)
        ).fetchone()
        if row is None:
            raise ValueError("routine_not_found")

        routine = _row_to_dict(row)

        if "agent_id" in fields:
            agent_row = conn.execute(
                "SELECT id FROM agents WHERE id = ?", (fields["agent_id"],)
            ).fetchone()
            if agent_row is None:
                raise ValueError("agent_not_found")

        eff_cron = fields.get("cron", routine["cron"])
        eff_tz = fields.get("timezone", routine["timezone"])

        if "cron" in fields or "timezone" in fields:
            cron_parsed = cron.parse(eff_cron)
            next_run = cron.next_after(cron_parsed, now, eff_tz)
        else:
            next_run = routine["next_run"]

        updates = {}
        for key in UPDATE_FIELDS:
            if key in fields:
                updates[key] = fields[key]

        if ("cron" in fields or "timezone" in fields) and routine["enabled"]:
            updates["last_run"] = now
            updates["next_run"] = next_run

        if updates:
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            set_vals = list(updates.values())
            set_vals.append(rid)
            conn.execute(
                f"UPDATE routines SET {set_parts} WHERE id = ?",
                set_vals,
            )

        row = conn.execute(
            "SELECT * FROM routines WHERE id = ?", (rid,)
        ).fetchone()
        return _row_to_dict(row)


def set_enabled(conn, rid, on, now):
    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM routines WHERE id = ?", (rid,)
        ).fetchone()
        if row is None:
            raise ValueError("routine_not_found")

        routine = _row_to_dict(row)

        if on and routine["enabled"] == 1:
            return routine
        if not on and routine["enabled"] == 0:
            return routine

        if on:
            cron_parsed = cron.parse(routine["cron"])
            next_run = cron.next_after(cron_parsed, now, routine["timezone"])
            conn.execute(
                "UPDATE routines SET enabled = 1, last_run = ?, next_run = ? WHERE id = ?",
                (now, next_run, rid),
            )
        else:
            conn.execute(
                "UPDATE routines SET enabled = 0, next_run = NULL WHERE id = ?",
                (rid,),
            )

        row = conn.execute(
            "SELECT * FROM routines WHERE id = ?", (rid,)
        ).fetchone()
        return _row_to_dict(row)


def fire_due(conn, now, max_catch_up, make_task, errors=None):
    rows = conn.execute(
        "SELECT * FROM routines WHERE enabled = 1 ORDER BY id"
    ).fetchall()

    all_results = []

    for row in rows:
        routine = _row_to_dict(row)
        last_run = routine["last_run"]
        tz = routine["timezone"]
        catch_up = routine["catch_up"]

        try:            # Nacharbeit OP-S1-15: mit `errors` bricht eine Routine mit ungültigem Ausdruck oder Zone nur sich selbst ab
            cron_parsed = cron.parse(routine["cron"])
            dates = cron.due_between(cron_parsed, last_run, now, tz, 1000)
            if dates:
                cron.next_after(cron_parsed, now, tz)
        except ValueError as exc:
            if errors is None:
                raise
            errors.append({"routine_id": routine["id"], "error": str(exc)})
            continue
        if not dates:
            continue

        dates.sort()

        agent_row = conn.execute(
            "SELECT status FROM agents WHERE id = ?",
            (routine["agent_id"],)
        ).fetchone()
        agent_paused = agent_row is None or agent_row["status"] != "aktiv"

        prev_row = conn.execute(
            "SELECT task_id FROM routine_runs WHERE routine_id = ? AND task_id IS NOT NULL ORDER BY due_at DESC LIMIT 1",
            (routine["id"],)
        ).fetchone()
        prev_task_open = False
        if prev_row and prev_row["task_id"]:
            task_row = conn.execute(
                "SELECT state FROM tasks WHERE id = ?",
                (prev_row["task_id"],)
            ).fetchone()
            if task_row and task_row["state"] not in ("erledigt", "abgebrochen"):
                prev_task_open = True

        if agent_paused or prev_task_open:
            outcomes = ['ausgelassen'] * len(dates)
        else:
            outcomes = []
            for i, d in enumerate(dates):
                if i == len(dates) - 1:
                    outcomes.append('erzeugt')
                else:
                    if catch_up == 'nachholen' and (len(dates) - 1 - i) <= max_catch_up:
                        outcomes.append('nachgeholt')
                    else:
                        outcomes.append('ausgelassen')

        with immediate(conn):
            claimed = []
            for i, d in enumerate(dates):
                outcome = outcomes[i]
                existing = conn.execute(
                    "SELECT 1 FROM routine_runs WHERE routine_id = ? AND due_at = ?",
                    (routine["id"], d),
                ).fetchone()
                if existing is not None:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO routine_runs (routine_id, due_at, outcome) "
                    "VALUES (?, ?, ?)",
                    (routine["id"], d, outcome),
                )
                claimed.append((d, outcome))

            next_run = cron.next_after(cron_parsed, now, tz)
            conn.execute(
                "UPDATE routines SET last_run = ?, next_run = ? WHERE id = ?",
                (now, next_run, routine["id"]),
            )

            routine_results = []
            for d, outcome in claimed:
                routine_results.append({
                    "routine_id": routine["id"],
                    "due_at": d,
                    "outcome": outcome,
                    "task_id": None,
                })

            all_results.append((routine, routine_results))

        for entry in routine_results:
            if entry["outcome"] != 'ausgelassen':
                task_id = make_task(routine, entry["due_at"])
                entry["task_id"] = task_id
                conn.execute(
                    "UPDATE routine_runs SET task_id = ? WHERE routine_id = ? AND due_at = ?",
                    (task_id, routine["id"], entry["due_at"]),
                )

    results = []
    for _, routine_results in all_results:
        results.extend(routine_results)

    return results
