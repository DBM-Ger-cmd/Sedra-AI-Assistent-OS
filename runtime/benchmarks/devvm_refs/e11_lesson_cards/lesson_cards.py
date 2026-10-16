import json
import re

DAY = 86400
FIELDS = ("id", "text", "source", "state", "created", "last_used", "uses", "reason")


def _norm(text):
    return " ".join(text.lower().split())


def _words(text):
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) >= 3}


class Cards:
    def __init__(self, stale_days=14, archive_days=60):
        self.stale_days, self.archive_days = stale_days, archive_days
        self._cards, self._count = {}, 0

    def _card(self, card_id):
        if card_id not in self._cards:
            raise ValueError("unknown_card")
        return self._cards[card_id]

    def _need(self, card_id, *states):
        card = self._card(card_id)
        if card["state"] not in states:
            raise ValueError("state")
        return card

    def propose(self, text, source, now):
        if not isinstance(text, str) or not 20 <= len(text.strip()) <= 400:
            raise ValueError("text")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source")
        key = _norm(text)
        if any(_norm(c["text"]) == key for c in self._cards.values() if c["state"] != "archived"):
            raise ValueError("duplicate")
        self._count += 1
        card_id = f"LC-{self._count:04d}"
        self._cards[card_id] = {"id": card_id, "text": text.strip(), "source": source, "state": "proposed", "created": now,
                                "last_used": None, "uses": 0, "reason": None}
        return card_id

    def approve(self, card_id, now):
        card = self._need(card_id, "proposed")
        card["state"], card["last_used"] = "active", now

    def reject(self, card_id, reason):
        card = self._need(card_id, "proposed")
        card["state"], card["reason"] = "archived", reason

    def use(self, card_id, now):
        card = self._need(card_id, "active", "stale")
        card["state"], card["last_used"] = "active", now
        card["uses"] += 1

    def sweep(self, now):
        changes = []
        for card_id, card in self._cards.items():
            idle = None if card["last_used"] is None else now - card["last_used"]
            if card["state"] == "active" and idle is not None and idle >= self.stale_days * DAY:
                card["state"] = "stale"
                changes.append((card_id, "stale"))
            elif card["state"] == "stale" and idle >= self.archive_days * DAY:
                card["state"], card["reason"] = "archived", "unused"
                changes.append((card_id, "archived"))
        return changes

    def get(self, card_id):
        return dict(self._card(card_id))

    def pick(self, task, limit=1):
        words = _words(task or "")
        scored = [(len(words & _words(c["text"])), c) for c in self._cards.values() if c["state"] == "active"]
        scored = [(n, c) for n, c in scored if n > 0]
        scored.sort(key=lambda pair: (-pair[0], -pair[1]["uses"], pair[1]["id"]))
        return [dict(c) for _, c in scored[:limit]]

    def dumps(self):
        return json.dumps({"count": self._count, "cards": [self._cards[k] for k in self._cards]}, sort_keys=True)

    @classmethod
    def loads(cls, text, stale_days=14, archive_days=60):
        data = json.loads(text)
        cards = cls(stale_days, archive_days)
        cards._count = data["count"]
        cards._cards = {c["id"]: {k: c[k] for k in FIELDS} for c in data["cards"]}
        return cards
