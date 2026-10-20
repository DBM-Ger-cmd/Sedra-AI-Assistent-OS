from pathlib import Path, PurePosixPath, PureWindowsPath

SCHEMA = 1
SECTIONS = {
    "heartbeat": {"tick_s": (5, 1, 3600), "coalesce_s": (2, 0, 3600), "max_runs_per_tick": (1, 1, 16)},
    "checkout": {"stall_s": (900, 2, 86400)},
    "budget": {"warn_percent": (80, 1, 100), "stop_percent": (100, 1, 1000)},
    "routines": {"max_catch_up": (3, 0, 100)},
    "org": {"max_depth": (6, 1, 32)},
}
TOP = {"schema", "enabled", "database"} | set(SECTIONS)
DATABASE = "orchestra/orchestra.db"


def _bad(field):
    return ValueError(f"orchestra_config_invalid:{field}")


def _section(raw, name):
    section = raw.get(name, {})
    if not isinstance(section, dict):
        raise _bad(name)
    unknown = sorted(str(k) for k in section if k not in SECTIONS[name])
    if unknown:
        raise _bad(f"{name}.{unknown[0]}")
    values = {}
    for key, (default, low, high) in SECTIONS[name].items():
        value = section.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise _bad(f"{name}.{key}")
        values[key] = value
    return values


def _database(value):
    if not isinstance(value, str) or not value.strip():
        raise _bad("database")
    windows, posix = PureWindowsPath(value), PurePosixPath(value.replace("\\", "/"))
    if windows.drive or windows.root or posix.is_absolute() or ".." in posix.parts:
        raise _bad("database")
    return posix.as_posix()


class OrchestraConfig:
    def __init__(self, schema, enabled, database, sections):
        self.schema, self.enabled, self.database = schema, enabled, database
        self.sections = sections
        for values in sections.values():
            for key, value in values.items():
                setattr(self, key, value)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get("orchestra"), dict):
            raise _bad("orchestra")
        raw = data["orchestra"]
        unknown = sorted(str(k) for k in raw if k not in TOP)
        if unknown:
            raise _bad(unknown[0])
        if type(raw.get("schema")) is not int or raw["schema"] != SCHEMA:
            raise _bad("schema")
        enabled = raw.get("enabled", False)
        if not isinstance(enabled, bool):
            raise _bad("enabled")
        database = _database(raw.get("database", DATABASE))
        sections = {name: _section(raw, name) for name in SECTIONS}
        if sections["heartbeat"]["coalesce_s"] >= sections["heartbeat"]["tick_s"]:
            raise _bad("heartbeat.coalesce_s")
        if sections["budget"]["warn_percent"] >= sections["budget"]["stop_percent"]:
            raise _bad("budget.warn_percent")
        return cls(SCHEMA, enabled, database, sections)

    @classmethod
    def load(cls, path, parse=None):
        path = Path(path)
        if not path.is_file():
            raise ValueError("orchestra_config_missing")
        text = path.read_text(encoding="utf-8")
        if parse is None:
            import yaml
            parse = yaml.safe_load
        try:
            data = parse(text)
        except Exception:
            raise _bad("unreadable") from None
        return cls.from_dict(data)

    def database_path(self, runtime_data):
        return Path(runtime_data) / self.database

    def as_dict(self):
        out = {"schema": self.schema, "enabled": self.enabled, "database": self.database}
        out.update({name: dict(values) for name, values in self.sections.items()})
        return {"orchestra": out}
