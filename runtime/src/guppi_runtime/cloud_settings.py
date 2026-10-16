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
        if not self.path.exists(): return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("keys", {}) or {}
        except (ValueError, OSError):
            return {}

    def _save(self, keys: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema": 1, "keys": keys}, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def has(self, provider_id: str) -> bool:
        return provider_id in self._load()

    def get(self, provider_id: str):
        """Der Klartext-Schlüssel, nur im Speicher des Aufrufers. Ohne Windows oder ohne Eintrag: None."""
        blob = self._load().get(provider_id)
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


def _key_state(provider_id, store, environ):
    env_name = "GUPPI_SECRET_" + provider_id.upper().replace("-", "_") + "_API_KEY"
    if (environ or {}).get(env_name, "").strip(): return "umgebung"
    if store is not None and store.has(provider_id): return "gespeichert"
    return "fehlt"


def view(project_root: Path, store: CloudKeyStore, environ=None) -> dict:
    cfg = load_config(project_root)
    providers = []
    for pid, entry in (cfg.get("providers") or {}).items():
        entry = entry or {}
        providers.append({"id": pid, "kind": entry.get("kind"), "enabled": bool(entry.get("enabled", False)),
                          "base_url": entry.get("base_url") or "", "default_model": entry.get("default_model"),
                          "key": _key_state(pid, store, environ), "key_store_available": CloudKeyStore.available()})
    return {"enabled": bool(cfg.get("enabled", False)), "providers": providers, "path": str(settings_path(project_root))}


def save(project_root: Path, payload: dict) -> dict:
    """Schreibt die Captain-Einstellungen vollständig neu. Unbekannte Anbieter und Felder werden abgelehnt, nie übernommen."""
    if not isinstance(payload, dict): raise ValueError("payload_invalid")
    cfg = load_config(project_root)
    known = cfg.get("providers") or {}
    if type(payload.get("enabled")) is not bool: raise ValueError("enabled_must_be_boolean")
    wanted = payload.get("providers")
    if not isinstance(wanted, dict): raise ValueError("providers_invalid")
    out = {"schema": 1, "enabled": payload["enabled"], "providers": {}}
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
    path.write_text(header + yaml.safe_dump({"cloud_providers": out}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"path": str(path), "enabled": out["enabled"]}


def signature(project_root: Path, store: CloudKeyStore, environ=None) -> str:
    """Ein Fingerabdruck der wirksamen Einstellungen. Weicht er vom Stand beim Start ab, braucht es einen Neustart."""
    v = view(project_root, store, environ)
    relevant = {"enabled": v["enabled"], "providers": [(p["id"], p["enabled"], p["base_url"], p["default_model"], p["key"] != "fehlt")
                                                      for p in v["providers"]]}
    return json.dumps(relevant, sort_keys=True)
