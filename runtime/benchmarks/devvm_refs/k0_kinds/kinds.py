import re

SHAPE = ("type", "id", "title", "state", "summary", "actions", "links")
CHAT_TOOLS = frozenset({"talk", "planung"})
_NAME = re.compile(r"[a-z][a-z0-9_]{1,31}")


class Kind:
    def __init__(self, name, title, read, listing, verbs=(), type_verbs=(), source="desk", placeholder=False, own_actions=False):
        self.name, self.title, self.read, self.listing = name, title, read, listing
        self.verbs, self.type_verbs = tuple(verbs), tuple(type_verbs)
        self.source, self.placeholder, self.own_actions = source, placeholder, own_actions

    def verb(self, name):
        return _find(self.verbs, name)

    def type_verb(self, name):
        return _find(self.type_verbs, name)


def _find(verbs, name):
    return next((v for v in verbs if v.verb == name), None)


class Registry:
    Kind = Kind

    def __init__(self, not_found=None):
        self._kinds, self._frozen, self.problems = {}, False, []
        self._not_found = not_found

    @property
    def frozen(self):
        return self._frozen

    def register(self, kind, replace_placeholder=False):
        if self._frozen:
            raise ValueError("kinds_frozen")
        if not isinstance(kind.name, str) or not _NAME.fullmatch(kind.name):
            raise ValueError("kind_name_invalid")
        old = self._kinds.get(kind.name)
        if old is not None and not (replace_placeholder and old.placeholder):
            raise ValueError("kind_already_registered")
        self._kinds[kind.name] = kind

    def freeze(self):
        self._frozen = True

    def mark(self):
        return dict(self._kinds)

    def reset(self, mark):
        if self._frozen:
            raise ValueError("kinds_frozen")
        self._kinds = dict(mark)

    def refuse(self, source, reason):
        self.problems.append({"source": source, "reason": reason})

    def names(self):
        return sorted(self._kinds)

    def get(self, name):
        return self._kinds.get(name)

    def _kind(self, name):
        kind = self._kinds.get(name)
        if kind is None:
            raise ValueError("unknown_object_type")
        return kind

    def offered(self, obj):
        kind = self._kinds.get(obj.get("type"))
        return [v.describe() for v in (kind.verbs if kind else ()) if v.offered(obj)]

    def view(self, hub, name, oid):
        kind = self._kind(name)
        obj = kind.read(hub, oid)
        if obj is None:
            if self._not_found is None:
                raise ValueError("object_not_found")
            return self._not_found(name, oid)
        _check(obj)
        if not kind.own_actions:
            obj["actions"] = self.offered(obj)
        return obj

    def listing(self, hub, name, payload=None):
        items = list(self._kind(name).listing(hub, dict(payload or {})))
        for obj in items:
            _check(obj)
            obj["actions"] = self.offered(obj)
        return items

    def request(self, hub, payload):
        name = str(payload.get("type") or "").strip()
        self._kind(name)
        oid = payload.get("id")
        if oid:
            return self.view(hub, name, str(oid))
        return {"type": name, "items": self.listing(hub, name, payload)}

    def table(self):
        return {name: {v.verb: v for v in kind.verbs} for name, kind in sorted(self._kinds.items()) if kind.verbs or kind.type_verbs}

    def type_verb(self, name, verb):
        return self._kind(name).type_verb(verb)


def _check(obj):
    if not isinstance(obj, dict) or any(key not in obj for key in SHAPE):
        raise ValueError("object_shape_invalid")


def client_for(token_class, tool=None, tool_ok=False):
    if token_class in ("cli", "mcp"):
        return token_class
    if token_class != "browser":
        raise ValueError("unknown_token_class")
    return "chat" if tool_ok and tool in CHAT_TOOLS else "shell"


def refuse_client_field(payload):
    if isinstance(payload, dict) and "client" in payload:
        raise ValueError("client_is_set_by_server")
