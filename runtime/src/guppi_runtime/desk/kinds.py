class Kind:
    def __init__(self, name, title, read, listing, verbs=(), type_verbs=(),
                 source="desk", placeholder=False, own_actions=False, extra=None):
        self.name = name
        self.title = title
        self.read = read
        self.listing = listing
        self.verbs = tuple(verbs)
        self.type_verbs = tuple(type_verbs)
        self.source = source
        self.placeholder = placeholder
        self.own_actions = own_actions
        self.extra = extra              # extra(hub, payload) -> dict: Felder neben `items` in der Liste (Spec 1, D1.3.4)

    def verb(self, name):
        for v in self.verbs:
            if v.verb == name:
                return v
        return None

    def type_verb(self, name):
        for v in self.type_verbs:
            if v.verb == name:
                return v
        return None


import re


SHAPE = ("type", "id", "title", "state", "summary", "actions", "links")
RESERVED = ("type", "items", "actions")     # Schlüssel der Liste, die `extra` nicht überschreibt


class Registry:
    Kind = Kind

    def __init__(self, not_found=None):
        self.problems = []
        self._not_found = not_found
        self._kinds = {}
        self._frozen = False

    @property
    def frozen(self):
        return self._frozen

    def register(self, kind, replace_placeholder=False):
        if self._frozen:
            raise ValueError("kinds_frozen")
        name = kind.name
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,31}', name):
            raise ValueError("kind_name_invalid")
        if name in self._kinds:
            if replace_placeholder and self._kinds[name].placeholder:
                self._kinds[name] = kind
            else:
                raise ValueError("kind_already_registered")
        else:
            self._kinds[name] = kind

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
        return sorted(self._kinds.keys())

    def get(self, name):
        return self._kinds.get(name, None)

    def _check_shape(self, obj):
        if not isinstance(obj, dict):
            raise ValueError("object_shape_invalid")
        for key in SHAPE:
            if key not in obj:
                raise ValueError("object_shape_invalid")

    def offered(self, obj):
        kind_name = obj.get("type") if isinstance(obj, dict) else None
        kind = self._kinds.get(kind_name) if kind_name else None
        if kind is None:
            return []
        return [v.describe() for v in kind.verbs if v.offered(obj)]

    def view(self, hub, name, oid):
        kind = self._kinds.get(name)
        if kind is None:
            raise ValueError("unknown_object_type")
        obj = kind.read(hub, oid)
        if obj is None:
            if self._not_found is not None:
                return self._not_found(name, oid)
            raise ValueError("object_not_found")
        self._check_shape(obj)
        if not kind.own_actions:
            obj["actions"] = self.offered(obj)
        return obj

    def listing(self, hub, name, payload=None):
        kind = self._kinds.get(name)
        if kind is None:
            raise ValueError("unknown_object_type")
        p = {} if payload is None else dict(payload)
        items = list(kind.listing(hub, p))
        for item in items:
            self._check_shape(item)
            item["actions"] = self.offered(item)
        return items

    def request(self, hub, payload):
        name = str(payload.get("type") or "").strip()
        kind = self._kinds.get(name)
        if kind is None:
            raise ValueError("unknown_object_type")
        if payload.get("id"):
            return self.view(hub, name, str(payload["id"]))
        out = {"type": name, "items": self.listing(hub, name, payload)}
        if kind.type_verbs:                 # Verben am Typ („anlegen“) stehen in der Liste (Spec 1, S1.H4)
            out["actions"] = [v.describe() for v in kind.type_verbs]
        if kind.extra is not None:
            more = kind.extra(hub, payload) or {}
            if any(k in RESERVED for k in more):
                raise ValueError("extra_key_reserved")
            out.update(more)
        return out

    def table(self):
        result = {}
        for name, kind in self._kinds.items():
            if kind.verbs or kind.type_verbs:
                result[name] = {v.verb: v for v in kind.verbs}
        return result

    def type_verb(self, name, verb):
        kind = self._kinds.get(name)
        if kind is None:
            raise ValueError("unknown_object_type")
        return kind.type_verb(verb)

CHAT_TOOLS = frozenset({"talk", "planung"})


def client_for(token_class, tool=None, tool_ok=False):
    if token_class in ("cli", "mcp"):
        return token_class
    if token_class == "browser":
        if tool_ok and tool in CHAT_TOOLS:
            return "chat"
        return "shell"
    raise ValueError("unknown_token_class")


def refuse_client_field(payload):
    if isinstance(payload, dict) and "client" in payload:
        raise ValueError("client_is_set_by_server")
    return None
