import re


def _valid_rule(rule):
    if not isinstance(rule, (tuple, list)):
        return None
    if len(rule) != 3:
        return None
    if not all(isinstance(x, str) for x in rule):
        return None
    try:
        return re.compile(rule[1], re.IGNORECASE)
    except re.error:
        return None


def _match_rule(rule, pattern, tool, result):
    tool_name, _, key = rule
    if tool_name != tool and tool_name != "*":
        return None
    if pattern.search(result):
        return key
    return None


def pick(rules, tool, result):
    if not isinstance(tool, str):
        return None
    if not isinstance(result, str) or not result.startswith("error:"):
        return None
    for rule in rules:
        pattern = _valid_rule(rule)
        if pattern is None:
            continue
        key = _match_rule(rule, pattern, tool, result)
        if key is not None:
            return key
    return None


class CardPicker:
    def __init__(self, cards, rules, max_per_key=1):
        if isinstance(max_per_key, bool) or not isinstance(max_per_key, int) or max_per_key < 0:
            raise ValueError("max_per_key must be an int >= 0")
        self.max_per_key = max_per_key
        self._cards = dict(cards)
        self._rules = list(rules)
        self._counts = {}

    @property
    def shown(self):
        return dict(self._counts)

    def after(self, tool, result):
        key = pick(self._rules, tool, result)
        if key is None:
            return None
        if key not in self._cards:
            return None
        current_count = self._counts.get(key, 0)
        if current_count >= self.max_per_key:
            return None
        self._counts[key] = current_count + 1
        return self._cards[key]
