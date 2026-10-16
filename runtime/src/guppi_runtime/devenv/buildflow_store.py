"""Buildflow store (docs/BUILDFLOW_2026-10-13.md): the tasks of the build workflow as files, one JSON file per task under <project>/runtime_data/buildflow/.

    store = BuildflowStore(default_path(project))
    store.add(task)                                   # a task made by buildflow_core.new_task; refuses an id that exists
    store.update(task_id, lambda t: transition(t, "queue", now))      # read, change, write under one lock
    store.all()                                       # every task, oldest first

Writes are atomic (a temporary file, then os.replace) and every change runs under a lock file that is removed when it is older than a minute (a crashed process must not block the store).
The task id is checked (BF- and letters or digits) before it becomes a file name."""
from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

ID = re.compile(r"BF-[A-Z0-9]{4,12}")
LOCK_STALE_S = 60


def default_path(project):
    return Path(project) / "runtime_data" / "buildflow"


class BuildflowStore:
    def __init__(self, folder, *, clock=time.time):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.clock = clock

    def file(self, task_id):
        if not isinstance(task_id, str) or not ID.fullmatch(task_id):
            raise ValueError("bad_task_id")
        return self.folder / f"{task_id}.json"

    @contextmanager
    def locked(self, timeout=10.0):
        lock = self.folder / ".lock"
        deadline = self.clock() + timeout
        while True:
            try:
                handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    stale = self.clock() - lock.stat().st_mtime > LOCK_STALE_S
                except FileNotFoundError:
                    continue
                if stale:
                    lock.unlink(missing_ok=True)
                elif self.clock() > deadline:
                    raise TimeoutError("store_locked")
                else:
                    time.sleep(0.05)
        try:
            yield
        finally:
            os.close(handle)
            lock.unlink(missing_ok=True)

    def write(self, task):
        target = self.file(task["id"])
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(task, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)

    def add(self, task):
        with self.locked():
            if self.file(task["id"]).exists():
                raise ValueError("task_exists")
            self.write(task)
        return task

    def load(self, task_id):
        path = self.file(task_id)
        if not path.exists():
            raise KeyError(task_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, task_id, change):
        with self.locked():
            task = change(self.load(task_id))
            self.write(task)
        return task

    def all(self):
        tasks = []
        for path in sorted(self.folder.glob("BF-*.json")):
            try:
                tasks.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(tasks, key=lambda task: (task.get("created", ""), task.get("id", "")))
