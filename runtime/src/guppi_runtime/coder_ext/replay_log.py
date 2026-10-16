import json
import hashlib
import copy


def request_key(body):
    cleaned = {k: v for k, v in body.items() if k != "cache_prompt"}
    raw = json.dumps(cleaned, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ReplayExhausted(RuntimeError):
    pass


class ReplayMismatch(RuntimeError):
    pass


class ReplayedError(RuntimeError):
    pass


class Recorder:
    def __init__(self, post):
        self._post = post
        self.records = []
        self._prev_msg_count = 0

    def _compute_sent(self, body):
        msgs = body.get("messages")
        if not isinstance(msgs, list):
            self._prev_msg_count = 0
            return []
        if len(msgs) < self._prev_msg_count:
            self._prev_msg_count = len(msgs)
            return copy.deepcopy(msgs)
        sent = copy.deepcopy(msgs[self._prev_msg_count:])
        self._prev_msg_count = len(msgs)
        return sent

    def __call__(self, body):
        key = request_key(body)
        sent = self._compute_sent(body)
        try:
            answer = self._post(body)
        except Exception as exc:
            self.records.append({"key": key, "error": f"{type(exc).__name__}: {exc}", "sent": sent})
            raise
        self.records.append({"key": key, "response": copy.deepcopy(answer), "sent": sent})
        return answer


def dumps(records):
    return "".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in records)


def loads(text):
    result = []
    for idx, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            result.append(json.loads(stripped))
        except json.JSONDecodeError:
            raise ValueError(f"line {idx}")
    return result


class Player:
    def __init__(self, records, strict=True):
        self._records = copy.deepcopy(records)
        self._strict = strict
        self.used = 0
        self.mismatches = 0

    def __call__(self, body):
        if self.used >= len(self._records):
            raise ReplayExhausted("no more records")
        key = request_key(body)
        record = self._records[self.used]
        if record.get("error") is not None:
            self.used += 1
            raise ReplayedError(record["error"])
        if key != record["key"]:
            if self._strict:
                raise ReplayMismatch(f"request {self.used + 1}")
            self.mismatches += 1
        self.used += 1
        return copy.deepcopy(record["response"])
