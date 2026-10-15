"""Runaway guard: spots a model that has stopped answering and only repeats itself, while its answer is still streaming.

Why (2026-10-03/04): Gemma generated exactly 20000 tokens in 395 s three times without an answer; gpt-oss at temperature 0.1 looped through
20000 tokens twice. Each case ran to the token limit, minutes of GPU for nothing. Plan: docs/LOOP_GUARD_STARNET_EXTENSIONS_PLAN_2026-10-04.md
(item E). The guard only watches text and says "runaway"; the adapter that streams the answer closes the connection, the caller records
`model_answer_runaway` and the rework watch counts it like any other failed generation.

Two signals, both conservative (a legitimate answer, even a long file with similar lines, must not trip them):
  repetition   the tail of the text is one block repeated: the repeating span is at least `min_span` characters AND the block occurs at least
               `min_repeats(period)` times (8 for blocks up to 200 characters, 4 up to 1000, else 3). Whitespace-only blocks count: endless
               blank lines are a runaway too.
  garbage      `<unused123>`-style special tokens, at least `max_garbage` of them in the last `window` characters (the Gemma garbage output
               documented in `guppi-gemma-garbage-output`).
The guard checks every `check_every` new characters, only the last `window` characters, in linear time (prefix function of the reversed tail).
Standard library only. One guard per text channel (the answer and the model's thinking are two streams).
"""
import re

_GARBAGE = re.compile(r"<unused\d+>")


class RunawayGuard:
    def __init__(self, min_span=3000, window=6000, check_every=256, max_garbage=20):
        self.min_span = min_span
        self.window = window
        self.check_every = check_every
        self.max_garbage = max_garbage
        self._text = ""
        self._since_check = 0
        self.total_chars = 0
        self.verdict = None

    @staticmethod
    def min_repeats(period):
        return 8 if period <= 200 else 4 if period <= 1000 else 3

    def feed(self, chunk):
        """Add streamed text. Returns the verdict dict as soon as the text is a runaway (and keeps returning it), else None.
        {"reason": "repetition" | "garbage", "chars": total characters seen, "period": block length or None, "span": repeating
        characters or None, "sample": the first 80 characters of the repeating block (or of the garbage)}."""
        if self.verdict is not None:
            return self.verdict
        chunk = str(chunk or "")
        self.total_chars += len(chunk)
        self._text = (self._text + chunk)[-self.window:]
        self._since_check += len(chunk)
        if self._since_check < self.check_every:
            return None
        self._since_check = 0
        self.verdict = self._check()
        return self.verdict

    def _check(self):
        text = self._text
        garbage = _GARBAGE.findall(text)
        if len(garbage) >= self.max_garbage:
            return {"reason": "garbage", "chars": self.total_chars, "period": None, "span": None, "sample": garbage[0]}
        if len(text) < self.min_span:
            return None
        # prefix function of the reversed text: for every suffix length i of `text` the smallest period of that suffix is i - pi[i-1]
        reversed_text = text[::-1]
        n = len(reversed_text)
        pi = [0] * n
        k = 0
        for i in range(1, n):
            while k and reversed_text[i] != reversed_text[k]:
                k = pi[k - 1]
            if reversed_text[i] == reversed_text[k]:
                k += 1
            pi[i] = k
        best = None
        for i in range(self.min_span, n + 1):
            period = i - pi[i - 1]
            if period < i and i >= period * self.min_repeats(period):
                best = (i, period)              # keep the longest suffix that qualifies
        if best is None:
            return None
        span, period = best
        block = text[len(text) - period:]
        return {"reason": "repetition", "chars": self.total_chars, "period": period, "span": span, "sample": block[:80]}
