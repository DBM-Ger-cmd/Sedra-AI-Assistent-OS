"""Langdock als Modellquelle (SPEC_APPS_v1_AM5, Richtung 1) – ein Anbieter im Kern, keine App.

Dieser Baustein ergänzt den vorhandenen Cloud-Zugang (`cloud_api.py`) um die Punkte, die nur für Langdock gelten:
  AM5-03  feste Region: nur die EU-Adresse, `…/us/…` und `…/global/…` werden abgelehnt (`langdock_region_nicht_erlaubt`)
  AM5-04  Modellliste des Betreibers (`local_config/cloud_modelle.yaml`): nur dort eingetragene Modelle sind wählbar,
          Modelle mit Aufbewahrung ≠ „keine“ nur mit `erlaubt_trotz_aufbewahrung: true`
  AM5-06  Fehlersätze für 429, 504 und 401/403 – kein automatisches Wiederholen
  AM5-08  Empfängerverzeichnis (`local_config/empfaenger.yaml`): ohne vollständigen Eintrag lässt sich der Anbieter nicht einschalten
  AM5-11  Preise je Modell, falls der Betreiber sie einträgt; sonst nur Token
Nichts hier öffnet einen Weg am Inhaltsschutz vorbei: der Adapter hat `route = "cloud"` wie alle Cloud-Adapter, `gateway/klassen.py`
bleibt unverändert (AM5-09). Die Angaben zu Langdock stammen aus Suchauszügen (Spec §1) und sind vor dem ersten Einsatz zu bestätigen.
"""
from __future__ import annotations
import datetime
import re
from pathlib import Path

import yaml

from .base import ModelAdapterError
from .cloud_api import CloudOpenAICompatibleAdapter

PROVIDER = "langdock"
REGION_ERLAUBT = ("https://api.langdock.com/openai/eu/v1",)
EMPFAENGER_ALTER_TAGE = 366
# Was der Adapter an Langdock sendet: nichts anderes (AM5-05). `n`, `service_tier`, `parallel_tool_calls`, `stream_options` werden von Langdock nicht unterstützt.
GESENDET = {"model", "messages", "stream", "temperature", "max_tokens", "top_p"}

FEHLERSAETZE = {
    429: "Langdock: Limit erreicht (Anfragen oder Token je Minute) – später erneut versuchen",
    504: "Langdock hat nach 105 s abgebrochen – kürzere Anfrage oder anderes Modell",
    401: "Langdock: Schlüssel ungültig oder ohne Scope ‚Completion API‘",
    403: "Langdock: Schlüssel ungültig oder ohne Scope ‚Completion API‘",
}
_HTTP = re.compile(r"^cloud_api_http_(\d{3}):")


# ---------------------------------------------------------------- Region (AM5-03)
def url_erlaubt(url):
    return isinstance(url, str) and url.rstrip("/") in REGION_ERLAUBT


def region_pruefen(url):
    """Wirft `ValueError("langdock_region_nicht_erlaubt")`, wenn die Adresse nicht auf der festen Liste steht."""
    if not url_erlaubt(url): raise ValueError("langdock_region_nicht_erlaubt")
    return url.rstrip("/")


# ---------------------------------------------------------------- Modellliste des Betreibers (AM5-04)
def modelle_pfad(project_root):
    return Path(project_root) / "local_config" / "cloud_modelle.yaml"


def modelle_laden(project_root):
    """{modell: Eintrag}. Fehlt die Datei oder ist sie unlesbar, ist die Liste leer – dann ist kein Modell wählbar (fail-closed)."""
    if project_root is None: return {}
    try:
        data = yaml.safe_load(modelle_pfad(project_root).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return {}
    eintraege = data.get(PROVIDER) if isinstance(data, dict) else None
    return {str(m): dict(e) for m, e in (eintraege or {}).items() if isinstance(e, dict)}


def modell_pruefen(modelle, modell):
    """(True, None) oder (False, Grund). Gründe: `langdock_modell_nicht_geprueft`, `langdock_modell_aufbewahrung`."""
    eintrag = (modelle or {}).get(modell)
    if not isinstance(eintrag, dict): return False, "langdock_modell_nicht_geprueft"
    if str(eintrag.get("aufbewahrung", "")).strip().lower() != "keine" and eintrag.get("erlaubt_trotz_aufbewahrung") is not True:
        return False, "langdock_modell_aufbewahrung"
    return True, None


def abgleich(modelle, angeboten):
    """Die Modelle, die Langdock anbietet, gegen die Liste des Betreibers: {geprueft, nicht_geprueft, nicht_angeboten}."""
    angeboten = set(angeboten or [])
    return {"geprueft": sorted(m for m in angeboten if modell_pruefen(modelle, m)[0]),
            "nicht_geprueft": sorted(m for m in angeboten if not modell_pruefen(modelle, m)[0]),
            "nicht_angeboten": sorted(m for m in (modelle or {}) if m not in angeboten)}


def kosten_eur(modelle, modell, usage):
    """Euro für einen Aufruf, nur wenn der Betreiber Preise je Million Token eingetragen hat; sonst None (AM5-11: dann zeigt SEDRA nur Token)."""
    preis = ((modelle or {}).get(modell) or {}).get("preis_eur_je_million_token")
    if not isinstance(preis, dict) or not isinstance(usage, dict): return None
    try:
        return round((float(usage.get("input_tokens") or 0) * float(preis["eingabe"]) + float(usage.get("output_tokens") or 0) * float(preis["ausgabe"])) / 1e6, 6)
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Empfängerverzeichnis (AM5-08)
def empfaenger_pfad(project_root):
    return Path(project_root) / "local_config" / "empfaenger.yaml"


PFLICHT = ("name", "rolle", "region", "aufbewahrung", "zweck", "gepflegt_von", "geprueft_am")
PFLICHT_VERTRAG = ("fassung", "datum", "fundstelle")


def _datum(wert):
    if isinstance(wert, datetime.datetime): return wert.date()
    if isinstance(wert, datetime.date): return wert
    try:
        return datetime.date.fromisoformat(str(wert)[:10])
    except ValueError:
        return None


def empfaenger_status(project_root, heute=None):
    """{status: fehlt|unvollstaendig|ok|alt, grund, hinweis}. `fehlt` und `unvollstaendig` verhindern das Einschalten; `alt` (Angaben über 12 Monate) ist nur ein Hinweis."""
    if project_root is None: return {"status": "fehlt", "grund": "empfaenger_fehlt", "hinweis": "Kein Empfängerverzeichnis"}
    try:
        data = yaml.safe_load(empfaenger_pfad(project_root).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        data = {}
    eintrag = ((data.get("empfaenger") if isinstance(data, dict) else None) or {}).get(PROVIDER)
    if not isinstance(eintrag, dict):
        return {"status": "fehlt", "grund": "empfaenger_fehlt", "hinweis": "Kein Eintrag für Langdock im Empfängerverzeichnis"}
    leer = [f for f in PFLICHT if not str(eintrag.get(f) or "").strip()]
    vertrag = eintrag.get("vertrag") if isinstance(eintrag.get("vertrag"), dict) else {}
    leer += ["vertrag." + f for f in PFLICHT_VERTRAG if not str(vertrag.get(f) or "").strip()]
    uav = eintrag.get("unterauftragsverarbeiter") if isinstance(eintrag.get("unterauftragsverarbeiter"), dict) else {}
    if not uav.get("liste") or not uav.get("datum"): leer.append("unterauftragsverarbeiter")
    if leer:
        return {"status": "unvollstaendig", "grund": "empfaenger_unvollstaendig:" + ",".join(leer), "hinweis": "Empfängerangaben unvollständig: " + ", ".join(leer)}
    if str(eintrag["region"]).strip().lower() != "eu":
        return {"status": "unvollstaendig", "grund": "empfaenger_unvollstaendig:region", "hinweis": "Region im Empfängerverzeichnis ist nicht eu"}
    geprueft = _datum(eintrag["geprueft_am"])
    heute = heute or datetime.date.today()
    if geprueft is None or (heute - geprueft).days > EMPFAENGER_ALTER_TAGE:
        return {"status": "alt", "grund": None, "hinweis": "Angaben prüfen (zuletzt geprüft: " + (geprueft.isoformat() if geprueft else "unbekannt") + ")"}
    return {"status": "ok", "grund": None, "hinweis": None}


def einschaltpruefung(project_root, url, heute=None):
    """Alles, was gegen das Einschalten spricht – leere Liste heißt: darf gebaut werden."""
    gruende = []
    if not url_erlaubt(url): gruende.append("langdock_region_nicht_erlaubt")
    st = empfaenger_status(project_root, heute)
    if st["status"] in ("fehlt", "unvollstaendig"): gruende.append(st["grund"])
    return gruende


def zusatzgruende(project_root, url, heute=None):
    """Für die Anzeige: warum Langdock „nicht bereit“ ist, in Sätzen."""
    saetze = []
    if not url_erlaubt(url): saetze.append("Adresse nicht in der festen EU-Liste")
    st = empfaenger_status(project_root, heute)
    if st["status"] in ("fehlt", "unvollstaendig"): saetze.append(st["hinweis"])
    return saetze


# ---------------------------------------------------------------- Adapter
class LangdockAdapter(CloudOpenAICompatibleAdapter):
    """OpenAI-kompatibler Adapter mit Modellliste des Betreibers und Fehlersätzen. Ohne Liste ist kein Modell wählbar."""

    def __init__(self, *a, modelle=None, **kw):
        super().__init__(*a, **kw)
        self.modelle = dict(modelle or {})
        region_pruefen(self.base_url)

    def health(self):
        return super().health() and modell_pruefen(self.modelle, self.default_model)[0]

    def list_models(self):
        return [m for m in super().list_models() if modell_pruefen(self.modelle, m)[0]]

    def chat(self, messages, model=None, **kwargs):
        wahl = model or self.default_model
        if wahl:
            ok, grund = modell_pruefen(self.modelle, wahl)
            if not ok: raise ModelAdapterError(f"{grund}:{wahl}")
        return super().chat(messages, model=model, **kwargs)

    def _post(self, path, payload, headers):
        try:
            return super()._post(path, payload, headers)
        except ModelAdapterError as exc:
            treffer = _HTTP.match(str(exc))
            satz = FEHLERSAETZE.get(int(treffer.group(1))) if treffer else None
            if satz: raise ModelAdapterError(f"cloud_api_http_{treffer.group(1)}:{satz}") from None
            raise
