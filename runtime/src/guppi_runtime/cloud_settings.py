"""Einstellungen für Cloud-Modelle mit API-Schlüssel: Lesen, Speichern, Schlüsselablage (Captain-Wunsch 16.10.2026: „alles, was man braucht“).

- Die Einstellungen stehen in `local_config/cloud_providers.yaml` (gleiche Ebene wie die anderen Schalter). Fehlt die Datei,
  gilt `config/cloud_providers.yaml` (Standard: alles aus). Wirkt erst nach dem nächsten Start, wie die übrigen Schalter.
- Schlüssel stehen in `local_config/cloud_keys.json`, verschlüsselt mit der Windows-DPAPI: nur dieser Benutzer auf diesem PC kann
  sie lesen. Außerhalb von Windows gibt es keine Ablage; dort bleibt die Umgebungsvariable (GUPPI_SECRET_...).
- Die Oberfläche bekommt nie einen Schlüssel zurück, nur den Zustand („umgebung“, „gespeichert“, „fehlt“).
"""
from __future__ import annotations
import base64
import ctypes
import json
import secrets
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlparse

import yaml

PROVIDER_ID = re.compile(r"^[a-z0-9-]{2,30}$")
MODEL_NAME = re.compile(r"^[A-Za-z0-9._/:\-]{1,120}$")
KEY_MIN, KEY_MAX = 8, 400
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "cloud_providers.yaml"


class KeyStoreError(ValueError):
    pass


# ---------------------------------------------------------------- Schlüsselablage (Windows-DPAPI)
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))          # muss während des Aufrufs leben
    inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)): raise KeyStoreError("dpapi_failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


class CloudKeyStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    @staticmethod
    def available() -> bool:
        return sys.platform == "win32"

    def _load(self) -> dict:
        """Die gespeicherten Schlüssel. Eine vorhandene, aber unlesbare Datei ist ein Fehler – sie gilt nicht als leer,
        sonst würde das nächste Speichern alle Schlüssel löschen (Befund F4 der Gesamtprüfung)."""
        if not self.path.exists(): return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise KeyStoreError("key_store_unreadable")
        if not isinstance(data, dict) or not isinstance(data.get("keys", {}), dict):
            raise KeyStoreError("key_store_unreadable")
        return data.get("keys", {}) or {}

    def _save(self, keys: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + "." + secrets.token_hex(4) + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps({"schema": 1, "keys": keys}, indent=2))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def has(self, provider_id: str) -> bool:
        try:
            return provider_id in self._load()
        except KeyStoreError:
            return False

    def get(self, provider_id: str):
        """Der Klartext-Schlüssel, nur im Speicher des Aufrufers. Ohne Windows oder ohne Eintrag: None."""
        try:
            blob = self._load().get(provider_id)
        except KeyStoreError:
            return None
        if not blob or not self.available(): return None
        try:
            return _dpapi(base64.b64decode(blob), protect=False).decode("utf-8")
        except (KeyStoreError, ValueError, OSError):
            return None

    def set(self, provider_id: str, value: str):
        if not self.available(): raise KeyStoreError("key_store_windows_only")
        keys = self._load()
        keys[provider_id] = base64.b64encode(_dpapi(value.encode("utf-8"), protect=True)).decode("ascii")
        self._save(keys)

    def delete(self, provider_id: str):
        keys = self._load()
        if provider_id in keys:
            del keys[provider_id]
            self._save(keys)


def check_key_value(value):
    if not isinstance(value, str): raise KeyStoreError("key_must_be_text")
    value = value.strip()
    if not KEY_MIN <= len(value) <= KEY_MAX or any(c.isspace() for c in value): raise KeyStoreError("key_format_invalid")
    return value


# ---------------------------------------------------------------- Einstellungen lesen und speichern
def settings_path(project_root: Path) -> Path:
    return Path(project_root) / "local_config" / "cloud_providers.yaml"


def key_store_path(project_root: Path) -> Path:
    return Path(project_root) / "local_config" / "cloud_keys.json"


def load_config(project_root: Path) -> dict:
    """Die wirksame Konfiguration: die Datei der Captain-Einstellungen, sonst der Standard aus config/."""
    path = settings_path(project_root)
    if not path.exists(): path = DEFAULT_CONFIG
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("cloud_providers", {}) or {}


MODULE_NAME = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


def module_model(config: dict, module: str):
    """Das Modell, das ein Modul nutzen soll: (Anbieter, Modell) aus `module_models` in der Konfiguration, oder None.
    Ein Eintrag mit unbekanntem Anbieter zählt nicht; so ein Modul fällt auf keinen Anbieter still um."""
    if not MODULE_NAME.match(module or ""): return None
    entry = ((config or {}).get("module_models") or {}).get(module)
    if not isinstance(entry, dict): return None
    pid, model = entry.get("provider"), entry.get("model")
    if pid not in ((config or {}).get("providers") or {}) or not isinstance(model, str) or not model.strip(): return None
    return pid, model.strip()


def _key_state(provider_id, store, environ):
    env_name = "GUPPI_SECRET_" + provider_id.upper().replace("-", "_") + "_API_KEY"
    if (environ or {}).get(env_name, "").strip(): return "umgebung"
    if store is not None and store.has(provider_id): return "gespeichert"
    return "fehlt"


def provider_status(master: bool, enabled: bool, base_url: str, model, key: str):
    """Was mit einem Anbieter gerade los ist, in einem Wort und den Gründen dazu. Gespeichert heißt „bereit“, nicht „läuft“:
    ob er läuft, sagt der laufende Server (`live`)."""
    if not master: return "aus", ["Hauptschalter aus"]
    if not enabled: return "aus", ["Anbieter aus"]
    reasons = []
    if not model: reasons.append("kein Modell eingetragen")
    if key == "fehlt": reasons.append("kein Schlüssel")
    if not (base_url or "").startswith("https://"): reasons.append("Adresse ist nicht https")
    return ("nicht bereit" if reasons else "bereit"), reasons


def view(project_root: Path, store: CloudKeyStore, environ=None) -> dict:
    cfg = load_config(project_root)
    master = bool(cfg.get("enabled", False))
    providers = []
    for pid, entry in (cfg.get("providers") or {}).items():
        entry = entry or {}
        enabled = bool(entry.get("enabled", False))
        key = _key_state(pid, store, environ)
        status, reasons = provider_status(master, enabled, entry.get("base_url") or "", entry.get("default_model"), key)
        providers.append({"id": pid, "kind": entry.get("kind"), "enabled": enabled,
                          "base_url": entry.get("base_url") or "", "default_model": entry.get("default_model"),
                          "key": key, "key_store_available": CloudKeyStore.available(), "status": status, "reasons": reasons})
    return {"enabled": master, "providers": providers, "path": str(settings_path(project_root)),
            "module_models": {m: {"provider": e.get("provider"), "model": e.get("model")} for m, e in (cfg.get("module_models") or {}).items()
                              if isinstance(e, dict)}}


def set_module_model(project_root: Path, module: str, provider, model):
    """Setzt oder löscht (provider None) das Modell eines Moduls. Nur bekannte Anbieter; alles andere bleibt unverändert."""
    if not MODULE_NAME.match(module or ""): raise ValueError("module_name_invalid")
    cfg = load_config(project_root)
    if provider is None:
        models = dict(cfg.get("module_models") or {})
        models.pop(module, None)
    else:
        if provider not in (cfg.get("providers") or {}): raise ValueError("unknown_provider")
        if not isinstance(model, str) or not MODEL_NAME.match(model.strip()): raise ValueError("model_name_invalid")
        models = dict(cfg.get("module_models") or {})
        models[module] = {"provider": provider, "model": model.strip()}
    cfg = dict(cfg, module_models=models)
    path = settings_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ("# Captain-Einstellungen für Cloud-Modelle (über das Fenster Einstellungen geschrieben).\n"
              "# Schlüssel stehen NICHT hier, sondern in cloud_keys.json (verschlüsselt) oder in den Umgebungsvariablen.\n")
    path.write_text(header + yaml.safe_dump({"cloud_providers": cfg}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return models


def save(project_root: Path, payload: dict) -> dict:
    """Schreibt die Captain-Einstellungen vollständig neu. Unbekannte Anbieter und Felder werden abgelehnt, nie übernommen."""
    if not isinstance(payload, dict): raise ValueError("payload_invalid")
    cfg = load_config(project_root)
    known = cfg.get("providers") or {}
    if type(payload.get("enabled")) is not bool: raise ValueError("enabled_must_be_boolean")
    wanted = payload.get("providers")
    if not isinstance(wanted, dict): raise ValueError("providers_invalid")
    out = {"schema": 1, "enabled": payload["enabled"], "providers": {},
           "module_models": cfg.get("module_models") or {}}          # die Zuordnung Modul → Modell bleibt beim Speichern erhalten
    for pid, entry in known.items():
        entry = dict(entry or {})
        change = wanted.get(pid, {}) if isinstance(wanted.get(pid), dict) else {}
        if type(change.get("enabled", entry.get("enabled", False))) is not bool: raise ValueError(f"enabled_must_be_boolean:{pid}")
        entry["enabled"] = change.get("enabled", entry.get("enabled", False))
        if "default_model" in change:
            model = change["default_model"]
            if model in (None, ""): model = None
            elif not isinstance(model, str) or not MODEL_NAME.match(model): raise ValueError(f"model_name_invalid:{pid}")
            entry["default_model"] = model
        if "base_url" in change:
            url = change["base_url"]
            parsed = urlparse(url if isinstance(url, str) else "")
            if parsed.scheme != "https" or not parsed.hostname or len(url) > 200: raise ValueError(f"base_url_must_be_https:{pid}")
            entry["base_url"] = url.rstrip("/")
        out["providers"][pid] = entry
    if set(wanted) - set(known): raise ValueError("unknown_provider")
    path = settings_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ("# Captain-Einstellungen für Cloud-Modelle (über das Fenster Einstellungen geschrieben).\n"
              "# Schlüssel stehen NICHT hier, sondern in cloud_keys.json (verschlüsselt) oder in den Umgebungsvariablen.\n")
    # Härtung E2 (30.10.): Sicherung mit Zeitstempel, dann Temp + replace – nie eine halbe Datei, nie ohne Rückweg
    sicherung = None
    if path.is_file():
        import time
        sicherung = path.with_name(path.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
        if not sicherung.exists(): sicherung.write_bytes(path.read_bytes())
    from .core.util import atomic_write_text
    atomic_write_text(path, header + yaml.safe_dump({"cloud_providers": out}, allow_unicode=True, sort_keys=False))
    return {"path": str(path), "enabled": out["enabled"], "sicherung": sicherung.name if sicherung else None}


def base_url_aenderungen(project_root: Path, payload: dict) -> list:
    """Härtung E2: welche Anbieter-Adressen der Captain ändern will – [{provider, alt, neu}]. Diese Änderung geht nur über ein Gate
    (der API-Schlüssel ginge danach an den neuen Host); alles andere speichert `save` sofort."""
    cfg = load_config(project_root)
    known = cfg.get("providers") or {}
    wanted = payload.get("providers") if isinstance(payload, dict) else None
    out = []
    for pid, change in (wanted or {}).items():
        if not isinstance(change, dict) or "base_url" not in change or pid not in known: continue
        url = change["base_url"]
        parsed = urlparse(url if isinstance(url, str) else "")
        if parsed.scheme != "https" or not parsed.hostname or len(url) > 200: raise ValueError(f"base_url_must_be_https:{pid}")
        neu = url.rstrip("/")
        alt = (known[pid] or {}).get("base_url")
        if neu != alt: out.append({"provider": pid, "alt": alt, "neu": neu})
    return out


def ohne_base_url(payload: dict) -> dict:
    """Die Nutzlast ohne `base_url`-Felder (die gehen über das Gate)."""
    out = dict(payload)
    out["providers"] = {pid: {k: v for k, v in (ch or {}).items() if k != "base_url"} if isinstance(ch, dict) else ch
                        for pid, ch in (payload.get("providers") or {}).items()}
    return out


def signature(project_root: Path, store: CloudKeyStore, environ=None) -> str:
    """Ein Fingerabdruck der wirksamen Einstellungen. Weicht er vom Stand beim Start ab, braucht es einen Neustart."""
    v = view(project_root, store, environ)
    relevant = {"enabled": v["enabled"], "providers": [(p["id"], p["enabled"], p["base_url"], p["default_model"], p["key"] != "fehlt")
                                                      for p in v["providers"]]}
    return json.dumps(relevant, sort_keys=True)
