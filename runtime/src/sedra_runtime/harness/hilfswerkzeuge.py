"""Hilfswerkzeuge auf der CPU (Plan docs/PLAN_CPU_HILFSWERKZEUGE_2026-11-04.md, P1): welche Programme und Pakete auf diesem Rechner da sind.

Nur erkennen, nie installieren oder laden: ein Programm ist da, wenn `which` es findet; ein Paket, wenn `find_spec` es kennt (ohne es zu importieren,
damit nichts Schweres geladen wird). Fehlt etwas, steht der Installationsbefehl dabei. `which` und `find_spec` sind Parameter, die Tests geben Attrappen.
Die Liste steht in `config/hilfswerkzeuge.yaml`; eine kaputte Datei ist ein ValueError mit Satz, kein Absturz an anderer Stelle."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import yaml

KONFIG = Path(__file__).resolve().parents[3] / 'config' / 'hilfswerkzeuge.yaml'
ARTEN = ('programm', 'paket')
PFLICHT = ('id', 'name', 'art', 'name_im_system', 'zweck', 'install')


def lesen(pfad=KONFIG):
    """Die Einträge der Konfiguration, geprüft: id, name, art, name_im_system, zweck, install, plan. Fehler: ValueError mit Satz."""
    try:
        doc = yaml.safe_load(Path(pfad).read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError('hilfswerkzeuge_nicht_lesbar: ' + str(exc)[:200])
    liste = doc.get('werkzeuge') if isinstance(doc, dict) else None
    if not isinstance(liste, list): raise ValueError('hilfswerkzeuge_ohne_liste')
    out, ids = [], set()
    for e in liste:
        if not isinstance(e, dict): raise ValueError('hilfswerkzeuge_eintrag_kein_objekt')
        for k in PFLICHT:
            if not isinstance(e.get(k), str) or not e[k].strip(): raise ValueError('hilfswerkzeuge_feld_fehlt: ' + str(e.get('id')) + '.' + k)
        if e['art'] not in ARTEN: raise ValueError('hilfswerkzeuge_art_unbekannt: ' + e['id'])
        if e['id'] in ids: raise ValueError('hilfswerkzeuge_id_doppelt: ' + e['id'])
        ids.add(e['id'])
        out.append({k: str(e.get(k) or '') for k in PFLICHT + ('plan',)})
    return out


def stand(pfad=KONFIG, which=shutil.which, find_spec=importlib.util.find_spec):
    """Der Stand je Werkzeug: `da` (mit Fundort) oder `fehlt` (mit Installationsbefehl). Rein bis auf which/find_spec."""
    werkzeuge = []
    for e in lesen(pfad):
        if e['art'] == 'programm':
            fund = which(e['name_im_system'])
        else:
            try:
                spec = find_spec(e['name_im_system'])
            except (ImportError, ValueError, AttributeError):
                spec = None
            fund = (getattr(spec, 'origin', None) or 'installiert') if spec else None
        werkzeuge.append(dict(e, status='da' if fund else 'fehlt', fundort=str(fund) if fund else ''))
    return {'werkzeuge': werkzeuge, 'da': sum(1 for w in werkzeuge if w['status'] == 'da'), 'gesamt': len(werkzeuge)}
