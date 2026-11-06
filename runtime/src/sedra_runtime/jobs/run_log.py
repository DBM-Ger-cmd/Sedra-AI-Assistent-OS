"""Automatic run log for benchmarks: results must not be lost when a run crashes, is stopped, or the next run has the same date.

    with RunLog(measurements_dir, "smallteam", config={...}) as log:
        log.say("== round 1")              # printed and appended to logs/<name>_<timestamp>.log, flushed per line
        log.save(result)                   # logs/<name>_<timestamp>.json, written atomically; call after every item
    # on exit (also on an exception or Ctrl+C): the status (done / failed / interrupted) goes into logs/INDEX.jsonl

Files are never overwritten: each run gets its own timestamp. `INDEX.jsonl` has one line per run (name, start, end, status, files, config),
so `tail logs/INDEX.jsonl` answers "which runs exist and which of them finished".
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path


class RunLog:
    def __init__(self, base_dir, name, config=None, echo=lambda s: print(s, flush=True)):
        self.dir = Path(base_dir) / "logs"
        self.name = name
        self.config = config or {}
        self.echo = echo
        self.started = datetime.now()
        stamp = self.started.strftime("%Y-%m-%d_%H%M%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / f"{name}_{stamp}.log"
        self.json_path = self.dir / f"{name}_{stamp}.json"
        self._fh = None

    def __enter__(self):
        self._fh = self.log_path.open("a", encoding="utf-8")
        self.say(f"# run {self.name} started {self.started.isoformat(timespec='seconds')} config {json.dumps(self.config, default=str)}")
        self._index("running")
        return self

    def say(self, text=""):
        line = str(text)
        if self.echo: self.echo(line)
        if self._fh is not None:
            self._fh.write(f"{datetime.now().strftime('%H:%M:%S')} {line}\n"); self._fh.flush(); os.fsync(self._fh.fileno())

    def save(self, data):
        """The complete result so far, replaced atomically: a crash leaves the previous full state, never half a file."""
        tmp = self.json_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, self.json_path)

    def _index(self, status):
        entry = {"name": self.name, "started": self.started.isoformat(timespec="seconds"), "status": status,
                 "log": self.log_path.name, "json": self.json_path.name if self.json_path.exists() else None, "config": self.config}
        if status != "running":
            entry["ended"] = datetime.now().isoformat(timespec="seconds")
            entry["seconds"] = round((datetime.now() - self.started).total_seconds())
        with (self.dir / "INDEX.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    def __exit__(self, exc_type, exc, tb):
        status = "done" if exc_type is None else "interrupted" if issubclass(exc_type, KeyboardInterrupt) else "failed"
        if exc_type is not None:
            self.say(f"# run ended: {status}: {exc_type.__name__}: {str(exc)[:300]}")
        else:
            self.say("# run ended: done")
        self._index(status)
        if self._fh is not None: self._fh.close(); self._fh = None
        return False
