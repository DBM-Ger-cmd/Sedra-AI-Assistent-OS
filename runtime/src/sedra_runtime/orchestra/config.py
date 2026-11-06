import re

# Grenzen der Dauerfreigabe im Guard (core/guard.py, D1.4); `standing` darf sie nur enger wählen (G2-S1-20).
STANDING_MAX_DAYS = 30
STANDING_MAX_USES = 50
STANDING_MAX_LEVEL = 3

# Schema 2 (Spec 1, G2-S1-20): neue Abschnitte mit (Vorgabe, kleinster, größter Wert); `checkout` entfällt.
SCHEMA2 = {
    "runner": {"chain_max_chars": (4000, 500, 20000), "research_max_urls": (5, 1, 5)},
    "standing": {"days": (7, 1, STANDING_MAX_DAYS), "uses": (50, 1, STANDING_MAX_USES), "max_days": (STANDING_MAX_DAYS, 1, STANDING_MAX_DAYS),
                 "max_uses": (STANDING_MAX_USES, 1, STANDING_MAX_USES), "max_level": (STANDING_MAX_LEVEL, 0, STANDING_MAX_LEVEL)},
    "decompose": {"max_subtasks": (8, 1, 20)},
}


def _check_int(section, field, value, lo, hi):
    name = f"orchestra_config_invalid:{section}.{field}"
    if type(value) is not int:
        raise ValueError(name)
    if value < lo or value > hi:
        raise ValueError(name)
    return value


def _section(raw, section, fields):
    data = raw.get(section, {})
    if not isinstance(data, dict):
        raise ValueError(f"orchestra_config_invalid:{section}")
    unknown = sorted(set(data.keys()) - set(fields))
    if unknown:
        raise ValueError(f"orchestra_config_invalid:{section}.{unknown[0]}")
    return {k: _check_int(section, k, data.get(k, default), lo, hi) for k, (default, lo, hi) in fields.items()}


class OrchestraConfig:
    def __init__(self, schema, enabled, database, heartbeat_tick_s,
                 heartbeat_coalesce_s, heartbeat_max_runs_per_tick,
                 checkout_stall_s, budget_warn_percent, budget_stop_percent,
                 routines_max_catch_up, org_max_depth, runner=None, standing=None, decompose=None):
        self.schema = schema
        self.enabled = enabled
        self.database = database
        self.tick_s = heartbeat_tick_s
        self.coalesce_s = heartbeat_coalesce_s
        self.max_runs_per_tick = heartbeat_max_runs_per_tick
        self.stall_s = checkout_stall_s
        self.warn_percent = budget_warn_percent
        self.stop_percent = budget_stop_percent
        self.max_catch_up = routines_max_catch_up
        self.max_depth = org_max_depth
        defaults = {name: {k: v[0] for k, v in fields.items()} for name, fields in SCHEMA2.items()}
        self.runner = runner or defaults["runner"]
        self.standing = standing or defaults["standing"]
        self.decompose = decompose or defaults["decompose"]

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or "orchestra" not in data or not isinstance(data["orchestra"], dict):
            raise ValueError("orchestra_config_invalid:orchestra")
        raw = data["orchestra"]

        if "schema" not in raw or not isinstance(raw["schema"], int) or isinstance(raw["schema"], bool) or raw["schema"] not in (1, 2):
            raise ValueError("orchestra_config_invalid:schema")

        # Schema 1 (Spec 0) wird weiter gelesen: mit `checkout`, ohne die Abschnitte aus Schema 2.
        allowed = {"schema", "enabled", "database", "heartbeat", "budget", "routines", "org"}
        allowed |= {"checkout"} if raw["schema"] == 1 else set(SCHEMA2)
        unknown = sorted(set(raw.keys()) - allowed)
        if unknown:
            raise ValueError(f"orchestra_config_invalid:{unknown[0]}")

        if "enabled" in raw and not isinstance(raw["enabled"], bool):
            raise ValueError("orchestra_config_invalid:enabled")

        schema = raw["schema"]
        enabled = raw.get("enabled", False)
        database = raw.get("database", "orchestra/orchestra.db")

        if not isinstance(database, str) or len(database.strip()) == 0:
            raise ValueError("orchestra_config_invalid:database")
        normalized = database.replace("\\", "/")
        parts = normalized.split("/")
        for part in parts:
            if part == "..":
                raise ValueError("orchestra_config_invalid:database")
        if re.match(r'^[A-Za-z]:', normalized):
            raise ValueError("orchestra_config_invalid:database")
        if normalized.startswith("/") or normalized.startswith("\\"):
            raise ValueError("orchestra_config_invalid:database")
        database = normalized.replace("\\", "/")
        while database.startswith("./"):
            database = database[2:]
        if database == "":
            database = "."

        hb = raw.get("heartbeat", {})
        if not isinstance(hb, dict):
            raise ValueError("orchestra_config_invalid:heartbeat")
        hb_unknown = sorted(set(hb.keys()) - {"tick_s", "coalesce_s", "max_runs_per_tick"})
        if hb_unknown:
            raise ValueError(f"orchestra_config_invalid:heartbeat.{hb_unknown[0]}")
        heartbeat_tick_s = _check_int("heartbeat", "tick_s", hb.get("tick_s", 5), 1, 3600)
        heartbeat_coalesce_s = _check_int("heartbeat", "coalesce_s", hb.get("coalesce_s", 2), 0, 3600)
        heartbeat_max_runs_per_tick = _check_int("heartbeat", "max_runs_per_tick", hb.get("max_runs_per_tick", 1), 1, 16)

        checkout_stall_s = None
        if schema == 1:
            co = raw.get("checkout", {})
            if not isinstance(co, dict):
                raise ValueError("orchestra_config_invalid:checkout")
            co_unknown = sorted(set(co.keys()) - {"stall_s"})
            if co_unknown:
                raise ValueError(f"orchestra_config_invalid:checkout.{co_unknown[0]}")
            checkout_stall_s = _check_int("checkout", "stall_s", co.get("stall_s", 900), 2, 86400)

        bu = raw.get("budget", {})
        if not isinstance(bu, dict):
            raise ValueError("orchestra_config_invalid:budget")
        bu_unknown = sorted(set(bu.keys()) - {"warn_percent", "stop_percent"})
        if bu_unknown:
            raise ValueError(f"orchestra_config_invalid:budget.{bu_unknown[0]}")
        budget_warn_percent = _check_int("budget", "warn_percent", bu.get("warn_percent", 80), 1, 100)
        budget_stop_percent = _check_int("budget", "stop_percent", bu.get("stop_percent", 100), 1, 1000)

        rt = raw.get("routines", {})
        if not isinstance(rt, dict):
            raise ValueError("orchestra_config_invalid:routines")
        rt_unknown = sorted(set(rt.keys()) - {"max_catch_up"})
        if rt_unknown:
            raise ValueError(f"orchestra_config_invalid:routines.{rt_unknown[0]}")
        routines_max_catch_up = _check_int("routines", "max_catch_up", rt.get("max_catch_up", 3), 0, 100)

        org = raw.get("org", {})
        if not isinstance(org, dict):
            raise ValueError("orchestra_config_invalid:org")
        org_unknown = sorted(set(org.keys()) - {"max_depth"})
        if org_unknown:
            raise ValueError(f"orchestra_config_invalid:org.{org_unknown[0]}")
        org_max_depth = _check_int("org", "max_depth", org.get("max_depth", 6), 1, 32)

        if heartbeat_coalesce_s >= heartbeat_tick_s:
            raise ValueError("orchestra_config_invalid:heartbeat.coalesce_s")
        if budget_warn_percent >= budget_stop_percent:
            raise ValueError("orchestra_config_invalid:budget.warn_percent")

        extra = {}
        if schema == 2:
            extra = {name: _section(raw, name, fields) for name, fields in SCHEMA2.items()}
            st = extra["standing"]
            if st["days"] > st["max_days"]:
                raise ValueError("orchestra_config_invalid:standing.days")
            if st["uses"] > st["max_uses"]:
                raise ValueError("orchestra_config_invalid:standing.uses")

        return cls(schema, enabled, database, heartbeat_tick_s,
                   heartbeat_coalesce_s, heartbeat_max_runs_per_tick,
                   checkout_stall_s, budget_warn_percent, budget_stop_percent,
                   routines_max_catch_up, org_max_depth, **extra)

    @classmethod
    def load(cls, path, parse=None):
        from pathlib import Path
        p = Path(path)
        if not p.is_file():
            raise ValueError("orchestra_config_missing")
        text = p.read_text(encoding="utf-8")
        if parse is None:
            import yaml
            parsed = yaml.safe_load(text)
        else:
            try:
                parsed = parse(text)
            except Exception:
                raise ValueError("orchestra_config_invalid:unreadable")
        return cls.from_dict(parsed)

    def database_path(self, runtime_data):
        from pathlib import Path
        return Path(runtime_data) / self.database

    def as_dict(self):
        out = {
            "orchestra": {
                "schema": self.schema,
                "enabled": self.enabled,
                "database": self.database,
                "heartbeat": {
                    "tick_s": self.tick_s,
                    "coalesce_s": self.coalesce_s,
                    "max_runs_per_tick": self.max_runs_per_tick,
                },
                "budget": {
                    "warn_percent": self.warn_percent,
                    "stop_percent": self.stop_percent,
                },
                "routines": {
                    "max_catch_up": self.max_catch_up,
                },
                "org": {
                    "max_depth": self.max_depth,
                },
            }
        }
        doc = out["orchestra"]
        if self.schema == 1:
            doc["checkout"] = {"stall_s": self.stall_s}
        else:
            doc.update({"runner": dict(self.runner), "standing": dict(self.standing), "decompose": dict(self.decompose)})
        return out
