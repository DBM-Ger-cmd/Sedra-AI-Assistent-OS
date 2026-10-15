class ReadTracker:
    def __init__(self):
        self._known = {}

    def _parse_start_end(self, start, end, n):
        if not isinstance(start, int) or isinstance(start, bool):
            start = 1
        if not isinstance(end, int) or isinstance(end, bool):
            end = n
        if start < 1:
            start = 1
        if end > n:
            end = n
        return start, end

    def _merge_ranges(self, ranges):
        if not ranges:
            return []
        sorted_ranges = sorted(ranges, key=lambda r: (r[0], r[1]))
        merged = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def note_read(self, path, text, start=None, end=None):
        if not isinstance(path, str) or not isinstance(text, str):
            return
        n = len(text.splitlines())
        start, end = self._parse_start_end(start, end, n)
        if path not in self._known or self._known[path][0] != text:
            self._known[path] = (text, [])
        if start <= end:
            seen = self._known[path][1]
            seen.append((start, end))
            self._known[path] = (self._known[path][0], self._merge_ranges(seen))

    def note_write(self, path, text):
        if not isinstance(path, str) or not isinstance(text, str):
            return
        n = len(text.splitlines())
        if n == 0:
            self._known[path] = (text, [])
        else:
            self._known[path] = (text, [(1, n)])

    def _full_range(self, text):
        n = len(text.splitlines())
        return [(1, n)] if n > 0 else []

    def _all_seen(self, old_seen, old_n):
        if old_n == 0:
            return old_seen == []
        return old_seen == [(1, old_n)]

    def note_edit(self, path, text):
        if not isinstance(path, str) or not isinstance(text, str):
            return
        if path not in self._known:
            return
        old_text, old_seen = self._known[path]
        old_n = len(old_text.splitlines())
        if self._all_seen(old_seen, old_n):
            self._known[path] = (text, self._full_range(text))
        else:
            self._known[path] = (text, [])

    def forget(self, path):
        if path in self._known:
            del self._known[path]

    def move(self, source, destination):
        if not isinstance(source, str) or not isinstance(destination, str):
            return
        if source in self._known:
            self._known[destination] = self._known.pop(source)
        else:
            if destination in self._known:
                del self._known[destination]

    def seen(self, path):
        if path not in self._known:
            return []
        return list(self._known[path][1])

    def check_overwrite(self, path, text):
        verdict = self.check_edit(path, text)
        if verdict != "ok":
            return verdict
        n = len(text.splitlines())
        seen = self._known[path][1]
        if self._all_seen(seen, n):
            return "ok"
        return "partial"

    def check_edit(self, path, text):
        if not isinstance(path, str):
            return "unread"
        if path not in self._known:
            return "unread"
        if not isinstance(text, str):
            return "changed"
        if text != self._known[path][0]:
            return "changed"
        return "ok"
