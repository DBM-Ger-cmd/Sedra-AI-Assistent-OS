"""E-11 lesson cards on disk (docs/ERWEITERUNGSPLAN): the card store of coder_ext.lesson_cards in one JSON file under runtime_data, and the two things the rest of GUPPI needs from it.
`lesson_for(path, task)` gives the best matching ACTIVE card for a task (and counts the use); the Captain proposes, approves and rejects cards with `guppi lessons ...` (nothing is active
before he approves it). The file is written atomically; a damaged file is reported, never silently replaced."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..coder_ext.lesson_cards import Cards


def default_path(project_root):
    return Path(project_root) / "runtime_data" / "lesson_cards.json"


def load(path):
    path = Path(path)
    return Cards.loads(path.read_text(encoding="utf-8")) if path.exists() else Cards()


def save(path, cards):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(cards.dumps(), encoding="utf-8")
    os.replace(tmp, path)


def lesson_for(path, task, now=None):
    """The text of the best active card for the task, or None. A used card is counted and saved; a missing or damaged file means no lesson (the build goes on)."""
    try:
        cards = load(path)
        found = cards.pick(task, limit=1)
        if not found: return None
        cards.use(found[0]["id"], time.time() if now is None else now)
        save(path, cards)
        return found[0]["text"]
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def manage(path, action, *, text=None, source=None, card_id=None, reason=None, now=None):
    """The Captain's actions: list, propose, approve, reject, sweep. Returns a JSON-able dict; a bad request raises ValueError."""
    now = time.time() if now is None else now
    cards = load(path)
    if action == "list":
        return {"cards": [cards.get(i) for i in sorted(cards.cards)]}
    if action == "propose":
        result = {"proposed": cards.propose(text, source or "captain", now)}
    elif action == "approve":
        cards.approve(card_id, now); result = {"approved": card_id}
    elif action == "reject":
        cards.reject(card_id, reason or "rejected by the Captain"); result = {"rejected": card_id}
    elif action == "sweep":
        result = {"swept": cards.sweep(now)}
    else:
        raise ValueError("unknown_action")
    save(path, cards)
    return result
