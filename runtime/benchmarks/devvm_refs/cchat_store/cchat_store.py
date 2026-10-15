import json
import os
import re
from pathlib import Path

_ID = re.compile(r"[0-9]{10,16}")
_ROLES = ("user", "assistant")


def valid_id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _message(raw):
    if not isinstance(raw, dict) or raw.get("role") not in _ROLES or not isinstance(raw.get("content"), str):
        return None
    out = {"role": raw["role"], "content": raw["content"][:20000]}
    if raw["role"] == "assistant" and isinstance(raw.get("model"), str) and raw["model"]:
        out["model"] = raw["model"][:80]
    return out


def _normalize(session_id, data):
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise ValueError("invalid_session")
    title = data["title"].strip()[:80] if isinstance(data.get("title"), str) else ""
    messages = [m for m in (_message(x) for x in data["messages"]) if m]
    return {"id": session_id, "title": title or "Neuer Chat", "updated": _int(data.get("updated")), "messages": messages[-200:]}


class ChatStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id):
        return self.root / (session_id + ".json")

    def _read(self, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and isinstance(data.get("messages"), list) else None

    def get(self, session_id):
        return self._read(self._path(session_id)) if valid_id(session_id) else None

    def list(self):
        rows = []
        for path in self.root.glob("*.json"):
            if not valid_id(path.stem):
                continue
            data = self._read(path)
            if data:
                rows.append({"id": path.stem, "title": data.get("title", ""), "updated": _int(data.get("updated")), "count": len(data["messages"])})
        return sorted(rows, key=lambda r: (r["updated"], r["id"]), reverse=True)

    def delete(self, session_id):
        if not valid_id(session_id):
            return False
        try:
            self._path(session_id).unlink()
        except OSError:
            return False
        return True

    def put(self, session_id, data):
        if not valid_id(session_id):
            raise ValueError("invalid_id")
        item = _normalize(session_id, data)
        rows = [r for r in self.list() if r["id"] != session_id]
        for old in reversed(rows[199:]):
            self.delete(old["id"])
        target = self._path(session_id)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)
        return item
