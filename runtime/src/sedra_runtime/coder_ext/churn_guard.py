class ChurnGuard:
    def __init__(self, limit=3):
        self.limit = limit
        self.warnings = 0
        self._paths = {}
        self._written = set()
        self._deleted = set()

    def feed(self, name, args, result):
        if not isinstance(args, dict):
            return None
        if "path" not in args or not isinstance(args["path"], str):
            return None
        if not isinstance(result, str):
            return None
        if result.startswith("error"):
            return None
        path = args["path"]
        if name == "read_file":
            if path in self._paths:
                self._paths[path]["cycle_count"] = 0
                self._paths[path]["syntax_count"] = 0
                self._paths[path]["warned"] = False
            return None
        if name == "delete_file":
            if path in self._written:
                self._deleted.add(path)
            return None
        if name in ("write_file", "append_file", "edit_file"):
            if path not in self._paths:
                self._paths[path] = {"cycle_count": 0, "syntax_count": 0, "warned": False}
            if path in self._deleted:
                self._deleted.discard(path)
                self._paths[path]["cycle_count"] += 1
            self._written.add(path)
            if "syntax error" in result:
                self._paths[path]["syntax_count"] += 1
            else:
                self._paths[path]["syntax_count"] = 0
            p = self._paths[path]
            if not p["warned"] and (p["cycle_count"] >= self.limit or p["syntax_count"] >= self.limit):
                p["warned"] = True
                self.warnings += 1
                if p["cycle_count"] >= self.limit:
                    reason = f"deleted and written again {p['cycle_count']} times"
                else:
                    reason = f"{p['syntax_count']} writes in a row with a syntax error"
                return f"churn: {path} ({reason}). Read the file with read_file, then change it with edit_file; do not delete and rewrite it again."
            return None
        return None
