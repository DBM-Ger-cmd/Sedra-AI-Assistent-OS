from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


class ToolError(RuntimeError):
    pass


class ToolPermissionError(ToolError):
    pass


class ToolValidationError(ToolError):
    pass


@dataclass(frozen=True)
class ToolContext:
    mission_id: str
    root: Path


class BaseTool:
    id = "base"
    version = "0.0.0"
    supported_operations: set[str] = set()

    def __init__(self, root: Path, guard=None, audit=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.guard = guard
        self.audit = audit

    def health(self):
        return True

    def _resolve(self, value: str | Path, *, must_exist: bool = False) -> Path:
        raw = Path(value)
        unresolved = raw if raw.is_absolute() else self.root / raw
        lexical = Path(os.path.abspath(unresolved))
        try:
            rel = lexical.relative_to(self.root)
        except ValueError as exc:
            raise ToolPermissionError("path_outside_tool_root") from exc

        current = self.root
        for part in rel.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ToolPermissionError("symlink_path_not_allowed")

        candidate = lexical.resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ToolPermissionError("path_outside_tool_root") from exc
        if must_exist and not candidate.exists():
            raise ToolValidationError("path_not_found")
        return candidate

    def _audit(self, event_type: str, mission_id: str, payload=None):
        if self.audit:
            self.audit.append(event_type, component=f"tool:{self.id}", mission_id=mission_id, payload=payload or {})
