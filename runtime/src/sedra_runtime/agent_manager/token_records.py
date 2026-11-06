"""Token records of the DevVM builds for the meter's coin hole: one record per build log (date, spec, model, completion tokens)."""
from __future__ import annotations

import re
from pathlib import Path

LOG_NAME = re.compile(r"^devvm_build_(?P<spec>.+)_(?P<date>\d{4}-\d{2}-\d{2})_\d{6}\.log$")
AGENT_LINE = re.compile(r"^\S+\s+agent\s+.+?\s(?P<model>\S+)\s+\S+\s+\d+ calls\s+[\d.]+ s (?P<tokens>\d+) tokens,")


def token_records(project_root):
    records = []
    for path in sorted((Path(project_root) / "runtime_data" / "measurements" / "logs").glob("devvm_build_*.log")):
        named = LOG_NAME.match(path.name)
        if not named:
            continue
        tokens, model = 0, None
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            hit = AGENT_LINE.match(line.strip())
            if hit:
                tokens += int(hit.group("tokens")); model = hit.group("model")
        if tokens:
            records.append({"date": named.group("date"), "spec": named.group("spec"), "model": model, "tokens": tokens})
    return records
