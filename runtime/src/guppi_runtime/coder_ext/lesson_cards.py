import time
import json
from collections import defaultdict

class Cards:
    def __init__(self, stale_days=14, archive_days=60):
        self.stale_days = stale_days
        self.archive_days = archive_days
        self.cards = {}
        self.next_id = 1
        self.text_index = defaultdict(set)
    
    def _get_next_id(self):
        while True:
            id = f"LC-{self.next_id:04d}"
            if id not in self.cards:
                return id
            self.next_id += 1
    
    def _normalize_text(self, text):
        return " ".join(text.lower().split())
    
    def _get_words(self, text):
        import re
        words = re.findall(r'[a-z0-9_]{3,}', text.lower())
        return set(words)
    
    def propose(self, text, source, now):
        if not isinstance(text, str):
            raise ValueError("text")
        text_stripped = text.strip()
        if len(text_stripped) < 20 or len(text_stripped) > 400:
            raise ValueError("text")
        if not isinstance(source, str):
            raise ValueError("source")
        source_stripped = source.strip()
        if not source_stripped:
            raise ValueError("source")
        
        normalized_text = self._normalize_text(text_stripped)
        if normalized_text in self.text_index:
            for card_id in self.text_index[normalized_text]:
                if self.cards[card_id]["state"] != "archived":
                    raise ValueError("duplicate")
        
        id = self._get_next_id()
        card = {
            "id": id,
            "text": text_stripped,
            "source": source_stripped,
            "state": "proposed",
            "created": now,
            "last_used": None,
            "uses": 0,
            "reason": None
        }
        self.cards[id] = card
        self.text_index[normalized_text].add(id)
        return id
    
    def approve(self, id, now):
        if id not in self.cards:
            raise ValueError("unknown_card")
        card = self.cards[id]
        if card["state"] != "proposed":
            raise ValueError("state")
        card["state"] = "active"
        card["last_used"] = now
    
    def reject(self, id, reason):
        if id not in self.cards:
            raise ValueError("unknown_card")
        card = self.cards[id]
        if card["state"] != "proposed":
            raise ValueError("state")
        card["state"] = "archived"
        card["reason"] = reason
    
    def use(self, id, now):
        if id not in self.cards:
            raise ValueError("unknown_card")
        card = self.cards[id]
        if card["state"] not in ("active", "stale"):
            raise ValueError("state")
        card["state"] = "active"
        card["last_used"] = now
        card["uses"] += 1
    
    def get(self, id):
        if id not in self.cards:
            raise ValueError("unknown_card")
        return self.cards[id].copy()
    def sweep(self, now):
        changes = []
        
        card_ids = sorted(self.cards.keys(), key=lambda id: self.cards[id]["created"])
        
        for id in card_ids:
            card = self.cards[id]
            if card["state"] in ("proposed", "archived"):
                continue
                
            if card["last_used"] is None:
                days_since_use = float('inf')
            else:
                days_since_use = (now - card["last_used"]) / 86400.0
            
            if card["state"] == "active":
                if days_since_use >= self.stale_days:
                    card["state"] = "stale"
                    changes.append((id, "stale"))
            elif card["state"] == "stale":
                if days_since_use >= self.archive_days:
                    card["state"] = "archived"
                    card["reason"] = "unused"
                    changes.append((id, "archived"))
        
        return changes
    
    def pick(self, task, limit=1):
        if not task or not isinstance(task, str):
            return []
        
        task_words = self._get_words(task)
        scored_cards = []
        
        for card in self.cards.values():
            if card["state"] != "active":
                continue
                
            card_words = self._get_words(card["text"])
            score = len(task_words & card_words)
            
            if score > 0:
                scored_cards.append((
                    score,
                    card["uses"],
                    card["id"],
                    card.copy()
                ))
        
        scored_cards.sort(key=lambda x: (-x[0], -x[1], x[2]))
        
        return [card[3] for card in scored_cards[:limit]]
    
    def dumps(self):
        count = len(self.cards) if self.cards else 0
        
        cards_in_order = []
        for id in sorted(self.cards.keys(), key=lambda id: self.cards[id]["created"]):
            cards_in_order.append(self.cards[id].copy())
        
        return json.dumps({
            "count": count,
            "cards": cards_in_order
        })
    
    @classmethod
    def loads(cls, text, stale_days=14, archive_days=60):
        data = json.loads(text)
        count = data["count"]
        cards_data = data["cards"]
        
        cards = cls(stale_days, archive_days)
        cards.next_id = count + 1
        
        for card_data in cards_data:
            cards.cards[card_data["id"]] = card_data
            normalized_text = cards._normalize_text(card_data["text"])
            cards.text_index[normalized_text].add(card_data["id"])
        
        return cards