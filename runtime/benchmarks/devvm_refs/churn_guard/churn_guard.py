WRITES = ("write_file", "append_file", "edit_file")


class ChurnGuard:
    def __init__(self, limit=3):
        self.limit = limit
        self.cycles, self.bad, self.written, self.deleted, self.warned = {}, {}, set(), set(), set()
        self.warnings = 0

    def _reset(self, path):
        self.cycles[path] = 0
        self.bad[path] = 0
        self.warned.discard(path)

    def feed(self, name, args, result):
        path = (args or {}).get("path") if isinstance(args, dict) else None
        if not isinstance(path, str) or not isinstance(result, str) or result.startswith("error"):
            return None
        if name == "read_file":
            self._reset(path)
            return None
        if name == "delete_file":
            if path in self.written:
                self.deleted.add(path)
            return None
        if name not in WRITES:
            return None
        if path in self.deleted:
            self.deleted.discard(path)
            self.cycles[path] = self.cycles.get(path, 0) + 1
        self.written.add(path)
        self.bad[path] = self.bad.get(path, 0) + 1 if "syntax error" in result else 0
        if path in self.warned:
            return None
        if self.cycles.get(path, 0) >= self.limit:
            reason = f"deleted and written again {self.cycles[path]} times"
        elif self.bad[path] >= self.limit:
            reason = f"{self.bad[path]} writes in a row with a syntax error"
        else:
            return None
        self.warned.add(path)
        self.warnings += 1
        return f"churn: {path} ({reason}). Read the file with read_file, then change it with edit_file; do not delete and rewrite it again."
