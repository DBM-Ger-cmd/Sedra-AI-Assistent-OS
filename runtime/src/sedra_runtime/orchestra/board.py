import uuid
from . import graphs
from .store import immediate

VALID_FIELDS = {
    "id", "title", "description", "goal_ref", "project_id",
    "parent_id", "assignee", "priority", "origin", "max_level",
}
VALID_ORIGINS = {"captain", "routine", "delegation", "system"}


def _insert_task(conn, id_, title, description, goal_ref, project_id,
                  parent_id, assignee, state, priority, origin, max_level,
                  created_by, created_at):
    conn.execute(
        """INSERT INTO tasks
           (id, title, description, goal_ref, project_id, parent_id,
            assignee, state, priority, origin, max_level,
            created_by, created_at, updated_at, revision)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (id_, title, description, goal_ref, project_id, parent_id,
         assignee, state, priority, origin, max_level,
         created_by, created_at, created_at),
    )


def create(conn, fields, now, created_by):

    unknown = sorted(k for k in fields if k not in VALID_FIELDS)
    if unknown:
        raise ValueError(f"task_field_unknown:{unknown[0]}")

    title = fields.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("task_title_invalid")

    origin = fields.get("origin", "captain")
    if origin not in VALID_ORIGINS:
        raise ValueError("task_origin_invalid")

    max_level = fields.get("max_level")
    if max_level is not None and not (type(max_level) is int and 0 <= max_level <= 6):
        raise ValueError("level_not_allowed")

    priority = fields.get("priority", 0)
    if type(priority) is not int:
        raise ValueError("task_field_invalid:priority")

    with immediate(conn):
        task_id = fields.get("id")
        if not task_id:
            task_id = "T-" + uuid.uuid4().hex[:12]

        row = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is not None:
            raise ValueError("task_exists")

        parent_id = fields.get("parent_id")
        if parent_id is not None:
            prow = conn.execute(
                "SELECT 1 FROM tasks WHERE id = ?", (parent_id,)
            ).fetchone()
            if prow is None:
                raise ValueError("task_not_found")

        assignee = fields.get("assignee")
        if assignee is not None:
            arow = conn.execute(
                "SELECT status FROM agents WHERE id = ?", (assignee,)
            ).fetchone()
            if arow is None:
                raise ValueError("agent_not_found")
            if arow[0] != "aktiv":
                raise ValueError("agent_inactive")

        state = "zugewiesen" if assignee is not None else "offen"

        description = fields.get("description")
        goal_ref = fields.get("goal_ref")
        project_id = fields.get("project_id")

        _insert_task(
            conn, task_id, title, description, goal_ref, project_id,
            parent_id, assignee, state, priority, origin, max_level,
            created_by, now,
        )

        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row)


def assign(conn, task_id, agent_id, now, by):
    CLOSED = ("erledigt", "abgebrochen")

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError("task_not_found")

        task = dict(row)
        old_assignee = task["assignee"]

        if task["state"] in CLOSED:
            raise ValueError("task_closed")

        if task["checkout_by"] is not None:
            raise ValueError("task_checked_out")

        arow = conn.execute(
            "SELECT status FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if arow is None:
            raise ValueError("agent_not_found")
        if arow[0] != "aktiv":
            raise ValueError("agent_inactive")

        new_revision = task["revision"] + 1
        conn.execute(
            """UPDATE tasks
               SET assignee = ?, state = 'zugewiesen',
                   updated_at = ?, revision = ?
               WHERE id = ?""",
            (agent_id, now, new_revision, task_id),
        )

        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return {"task": dict(row), "old": old_assignee}


def checkout(conn, task_id, agent_id, run_id, now):
    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError("task_not_found")

        task = dict(row)

        if task["checkout_by"] is not None:
            raise ValueError("task_already_checked_out")

        if task["assignee"] != agent_id or task["state"] not in ("zugewiesen", "offen"):
            raise ValueError("task_not_assignable")

        blocker_rows = conn.execute(
            """SELECT 1 FROM blockers b
               JOIN tasks t ON t.id = b.blocked_by_task_id
               WHERE b.task_id = ?
               AND t.state NOT IN ('erledigt', 'abgebrochen')""",
            (task_id,),
        ).fetchall()
        if blocker_rows:
            raise ValueError("task_blocked")

        new_revision = task["revision"] + 1
        cur = conn.execute(
            """UPDATE tasks
               SET checkout_by = ?, checkout_run = ?, checkout_at = ?,
                   state = 'in_arbeit', updated_at = ?, revision = ?
               WHERE id = ? AND checkout_by IS NULL""",
            (agent_id, run_id, now, now, new_revision, task_id),
        )
        if cur.rowcount != 1:
            raise ValueError("task_already_checked_out")

        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row)


def set_blocker(conn, task_id, blocked_by, now):
    if task_id == blocked_by:
        raise ValueError("blocker_self")

    with immediate(conn):
        t1 = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if t1 is None:
            raise ValueError("task_not_found")

        t2 = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (blocked_by,)
        ).fetchone()
        if t2 is None:
            raise ValueError("task_not_found")

        existing = conn.execute(
            "SELECT 1 FROM blockers WHERE task_id = ? AND blocked_by_task_id = ?",
            (task_id, blocked_by),
        ).fetchone()
        if existing is not None:
            return None

        all_edges = conn.execute(
            "SELECT task_id, blocked_by_task_id FROM blockers"
        ).fetchall()
        all_edges.append((task_id, blocked_by))

        if graphs.has_cycle(all_edges):
            raise ValueError("blocker_cycle")

        conn.execute(
            "INSERT INTO blockers (task_id, blocked_by_task_id, created_at) VALUES (?, ?, ?)",
            (task_id, blocked_by, now),
        )


def clear_blocker(conn, task_id, blocked_by, now):
    with immediate(conn):
        cur = conn.execute(
            "DELETE FROM blockers WHERE task_id = ? AND blocked_by_task_id = ?",
            (task_id, blocked_by),
        )
        if cur.rowcount == 0:
            raise ValueError("blocker_not_found")

        row = conn.execute(
            """SELECT COUNT(*) FROM blockers b
               JOIN tasks t ON t.id = b.blocked_by_task_id
               WHERE b.task_id = ?
               AND t.state NOT IN ('erledigt', 'abgebrochen')""",
            (task_id,),
        ).fetchone()
        return row[0]


def release(conn, task_id, run_id, state, now, comment=None):
    VALID_STATES = ('zugewiesen', 'offen', 'wartet', 'erledigt')
    if state not in VALID_STATES:
        raise ValueError("task_state_invalid")

    if comment is not None:
        if not isinstance(comment, str) or not comment.strip():
            raise ValueError("comment_empty")
        if len(comment) > 8000:
            raise ValueError("text_too_long")

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError("task_not_found")

        task = dict(row)

        checkout_run = task["checkout_run"]
        if not checkout_run or checkout_run != run_id:
            raise ValueError("run_mismatch")

        new_revision = task["revision"] + 1
        if state == 'offen':
            conn.execute(
                """UPDATE tasks
                   SET state = ?, checkout_by = NULL, checkout_run = NULL,
                       checkout_at = NULL, assignee = NULL,
                       updated_at = ?, revision = ?
                   WHERE id = ?""",
                (state, now, new_revision, task_id),
            )
        else:
            conn.execute(
                """UPDATE tasks
                   SET state = ?, checkout_by = NULL, checkout_run = NULL,
                       checkout_at = NULL,
                       updated_at = ?, revision = ?
                   WHERE id = ?""",
                (state, now, new_revision, task_id),
            )

        if comment is not None:
            conn.execute(
                """INSERT INTO comments (task_id, author_kind, author_id, text, ts)
                   VALUES (?, 'system', NULL, ?, ?)""",
                (task_id, comment, now),
            )

        return dict(conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone())


def cancel(conn, task_id, now, by):
    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError("task_not_found")

        task = dict(row)

        if task["state"] in ('erledigt', 'abgebrochen'):
            raise ValueError("task_closed")

        checkout_run = task["checkout_run"]
        new_revision = task["revision"] + 1
        conn.execute(
            """UPDATE tasks
               SET state = 'abgebrochen', checkout_by = NULL,
                   checkout_run = NULL, checkout_at = NULL,
                   updated_at = ?, revision = ?
               WHERE id = ?""",
            (now, new_revision, task_id),
        )

        return {"task": dict(conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()), "run_id": checkout_run}


def comment(conn, task_id, author_kind, author_id, text, now):
    if author_kind not in ('captain', 'agent', 'system'):
        raise ValueError("comment_author_invalid")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("comment_empty")
    if len(text) > 8000:
        raise ValueError("text_too_long")

    with immediate(conn):
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError("task_not_found")

        cur = conn.execute(
            """INSERT INTO comments (task_id, author_kind, author_id, text, ts)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, author_kind, author_id, text, now),
        )
        return cur.lastrowid


def set_check(conn, task_id, result, ref, now):
    if result not in ('gruen', 'rot', 'nicht_geprueft'):
        raise ValueError("check_result_invalid")

    with immediate(conn):
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError("task_not_found")

        new_revision = row["revision"] + 1
        conn.execute(
            """UPDATE tasks
               SET check_result = ?, check_ref = ?,
                   updated_at = ?, revision = ?
               WHERE id = ?""",
            (result, ref, now, new_revision, task_id),
        )

        return dict(conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone())


def chain_rows(conn, task_id):
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if row is None:
        raise ValueError("task_not_found")

    task = dict(row)
    parents = []
    visited = {task_id}
    current_id = task.get("parent_id")

    while current_id is not None:
        if current_id in visited:
            break
        visited.add(current_id)
        prow = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (current_id,)
        ).fetchone()
        if prow is None:
            break
        parents.append(dict(prow))
        current_id = prow["parent_id"]

    parents.reverse()

    return {"task": task, "parents": parents}


def children_done(conn, root_id):
    CLOSED = ("erledigt", "abgebrochen")
    rows = conn.execute(
        "SELECT * FROM tasks WHERE parent_id = ?", (root_id,)
    ).fetchall()

    if not rows:
        return False

    for row in rows:
        if row["state"] not in CLOSED:
            return False

    return True


def orphans(conn, live_run_ids):
    live_set = set(live_run_ids)
    rows = conn.execute(
        "SELECT * FROM tasks WHERE checkout_run IS NOT NULL"
    ).fetchall()

    result = []
    for row in rows:
        if row["checkout_run"] not in live_set:
            result.append(dict(row))

    result.sort(key=lambda t: t["id"])
    return result


def delegate(conn, parent_id, frm, items, now):
    if not items:
        raise ValueError("delegate_empty")

    with immediate(conn):
        prow = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (parent_id,)
        ).fetchone()
        if prow is None:
            raise ValueError("task_not_found")

        parent = dict(prow)

        if parent["state"] in ("erledigt", "abgebrochen"):
            raise ValueError("task_closed")

        if parent.get("decomposed_at") is not None:
            raise ValueError("task_already_decomposed")

        frow = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (frm,)
        ).fetchone()
        if frow is None:
            raise ValueError("agent_not_found")
        frm_row = dict(frow)

        agent_rows = conn.execute(
            "SELECT * FROM agents"
        ).fetchall()
        all_agents = [dict(r) for r in agent_rows]

        new_tasks = []
        for item in items:
            agent_id = item.get("agent_id")

            if agent_id is None:
                raise ValueError("agent_not_found")

            arow = conn.execute(
                "SELECT * FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()
            if arow is None:
                raise ValueError("agent_not_found")

            graphs.check_delegation(
                all_agents, frm, agent_id,
                frm_row.get("can_delegate", 0)
            )

            title = item.get("titel")
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                raise ValueError("task_title_invalid")

            beschreibung = item.get("beschreibung", "")
            akzeptanz = item.get("akzeptanz", "")
            if akzeptanz:
                description = beschreibung + "\n\nAkzeptanz: " + akzeptanz
            else:
                description = beschreibung

            parent_max = parent.get("max_level")
            agent_row = dict(arow)
            agent_perm = agent_row.get("permission_level")
            max_level = graphs.inherit_level(parent_max, agent_perm)

            task_id = "T-" + uuid.uuid4().hex[:12]

            _insert_task(
                conn, task_id, title, description, None, None,
                parent_id, agent_id, "zugewiesen", 0, "delegation",
                max_level, frm, now,
            )

            trow = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            new_tasks.append(dict(trow))

        for idx, item in enumerate(items):
            blockers = item.get("blocker") or []
            new_task = new_tasks[idx]
            for blocker_idx in blockers:
                blocker_task = new_tasks[blocker_idx]
                conn.execute(
                    "INSERT INTO blockers (task_id, blocked_by_task_id, created_at) VALUES (?, ?, ?)",
                    (new_task["id"], blocker_task["id"], now),
                )

        new_revision = parent["revision"] + 1
        conn.execute(
            """UPDATE tasks
               SET decomposed_at = ?, updated_at = ?, revision = ?
               WHERE id = ?""",
            (now, now, new_revision, parent_id),
        )

        return new_tasks
