"""Einstellungen des Wissensspeichers (Spec 7, D7.3 bis D7.5): die Paket-Vorgabe `runtime/config/wissen.yaml` (ohne Pfade) und die
Datei dieses Rechners `local_config/wissen.yaml` (Engine, Modell, Prüfsumme; Platzhalter `<guppi>`, `<modelle>` über `local_paths`).

Eingeschaltet wird nur über den Schalter `wissen` in `local_config/switches.yaml`; `enabled` in der Paket-Vorgabe schaltet allein
nicht ein (wie `orchestra`, OP-14). Eine fehlende oder kaputte Datei ist `ValueError('wissen_config_invalid:<grund>')`: der
Speicher bleibt dann aus und `boot()` sagt warum (`wissen_error`)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..local_paths import expand

SCHEMA = 1
ALIAS = "wissen-embed"
VERBOTENE_PORTS = (8089,)                                    # der Modellserver für Chat und Agenten (D7.4)


@dataclass
class Konfig:
    speicher: str = "wissen/wissen.sqlite"                   # relativ zu local_config (G2-S7-q)
    takt_an: bool = True
    takt_intervall_s: float = 600.0
    schritt_s: float = 120.0
    port: int = 8094
    kontext: int = 8192
    stapel: int = 16
    pooling: str = ""
    cpu_threads: int | None = None
    leerlauf_s: float = 900.0
    anfrage_timeout_s: float = 5.0
    eingabeformat: str = "e1"
    dim: int = 1024
    tiefe: int = 50
    k: int = 5
    abdeckung_min: float = 0.5
    gewichte: dict = field(default_factory=dict)
    ziel: int = 1200
    grenze: int = 1600
    je_treffer: int = 1600
    gesamt: int = 8000
    kontext_treffer: int = 5
    offene_je_agent: int = 20
    titel_max: int = 160
    text_max: int = 4000
    datei_max_bytes: int = 2_000_000
    engine: str | None = None                                # local_config: Pfad der Engine (llama-server)
    modell: str | None = None                                # local_config: Pfad der GGUF
    modell_sha256: str = ""
    modell_name: str = ""

    def modell_pfad(self):
        return Path(expand(self.modell)) if self.modell else None

    def engine_pfad(self):
        return Path(expand(self.engine)) if self.engine else None


def _lies(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("wissen_config_invalid:missing")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ValueError("wissen_config_invalid:yaml") from exc
    if not isinstance(data, dict) or not isinstance(data.get("wissen"), dict):
        raise ValueError("wissen_config_invalid:top_level")
    return data["wissen"]


def _zahl(block, key, art, vorgabe, *, mindestens=None):
    wert = block.get(key, vorgabe)
    if wert is None and vorgabe is None:
        return None
    if isinstance(wert, bool) or not isinstance(wert, (int, float)) or (art is int and type(wert) is not int):
        raise ValueError(f"wissen_config_invalid:{key}")
    if mindestens is not None and wert < mindestens:
        raise ValueError(f"wissen_config_invalid:{key}")
    return art(wert)


def load(config_path, local_path=None):
    """Die Paket-Vorgabe lesen (Pflicht), die lokale Datei dazulegen (wahlweise); Pfade bleiben Platzhalter bis `modell_pfad()`."""
    w = _lies(config_path)
    if w.get("schema") != SCHEMA:
        raise ValueError("wissen_config_invalid:schema")
    k = Konfig()
    k.speicher = str(w.get("speicher") or k.speicher)
    if k.speicher.startswith(("/", "\\")) or ".." in Path(k.speicher).parts or ":" in k.speicher:
        raise ValueError("wissen_config_invalid:speicher")
    takt = w.get("takt") or {}
    k.takt_an = bool(takt.get("an", True))
    k.takt_intervall_s = _zahl(takt, "intervall_s", float, k.takt_intervall_s, mindestens=5)
    k.schritt_s = _zahl(takt, "schritt_s", float, k.schritt_s, mindestens=1)
    e = w.get("einbetten") or {}
    k.port = _zahl(e, "port", int, k.port, mindestens=1024)
    if k.port in VERBOTENE_PORTS:
        raise ValueError("wissen_config_invalid:port")
    k.kontext = _zahl(e, "kontext", int, k.kontext, mindestens=512)
    k.stapel = _zahl(e, "stapel", int, k.stapel, mindestens=1)
    k.pooling = str(e.get("pooling") or "")
    k.cpu_threads = _zahl(e, "cpu_threads", int, None, mindestens=1)
    k.leerlauf_s = _zahl(e, "leerlauf_s", float, k.leerlauf_s, mindestens=1)
    k.anfrage_timeout_s = _zahl(e, "anfrage_timeout_s", float, k.anfrage_timeout_s, mindestens=0.1)
    k.eingabeformat = str(e.get("eingabeformat") or "e1")
    k.dim = _zahl(e, "dim", int, k.dim, mindestens=1)
    s = w.get("suche") or {}
    k.tiefe = _zahl(s, "tiefe", int, k.tiefe, mindestens=1)
    k.k = _zahl(s, "k", int, k.k, mindestens=1)
    k.abdeckung_min = _zahl(s, "abdeckung_min", float, k.abdeckung_min, mindestens=0)
    f = w.get("fusion") or {}
    if not isinstance(f, dict):
        raise ValueError("wissen_config_invalid:fusion")
    k.gewichte = dict(f)
    z = w.get("zerlegen") or {}
    k.ziel = _zahl(z, "ziel", int, k.ziel, mindestens=1)
    k.grenze = _zahl(z, "grenze", int, k.grenze, mindestens=1)
    if k.grenze < k.ziel:
        raise ValueError("wissen_config_invalid:zerlegen")
    kx = w.get("kontext") or {}
    k.je_treffer = _zahl(kx, "je_treffer", int, k.je_treffer, mindestens=1)
    k.gesamt = _zahl(kx, "gesamt", int, k.gesamt, mindestens=1)
    k.kontext_treffer = _zahl(kx, "treffer", int, k.kontext_treffer, mindestens=1)
    v = w.get("vorschlaege") or {}
    k.offene_je_agent = _zahl(v, "offen_je_agent", int, k.offene_je_agent, mindestens=1)
    k.titel_max = _zahl(v, "titel_max", int, k.titel_max, mindestens=1)
    k.text_max = _zahl(v, "text_max", int, k.text_max, mindestens=1)
    k.datei_max_bytes = _zahl(w.get("aufnahme") or {}, "datei_max_bytes", int, k.datei_max_bytes, mindestens=1)
    if local_path is not None and Path(local_path).is_file():
        lw = _lies(local_path)
        for key in ("engine", "modell"):
            wert = lw.get(key)
            if wert is not None and (not isinstance(wert, str) or not wert.strip()):
                raise ValueError(f"wissen_config_invalid:{key}")
            setattr(k, key, wert.strip() if wert else None)
        k.modell_sha256 = str(lw.get("modell_sha256") or "").strip().lower()
        k.modell_name = str(lw.get("modell_name") or "").strip()
        if "port" in lw:
            k.port = _zahl(lw, "port", int, k.port, mindestens=1024)
            if k.port in VERBOTENE_PORTS:
                raise ValueError("wissen_config_invalid:port")
        if "cpu_threads" in lw:
            k.cpu_threads = _zahl(lw, "cpu_threads", int, None, mindestens=1)
        if "pooling" in lw:
            k.pooling = str(lw.get("pooling") or "")
    return k
