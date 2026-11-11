"""Herkunft eingebauter Module (AM0-02, SPEC_APPS_v1_AM0_G2 §2): was beim Einbau in `local_config/<tools|shells>/<id>/` lag, als Hashes in einer Datei
AUSSERHALB des Modulordners (`local_config/uix_herkunft/<tools|shells>/<id>.json`). `Gateway._load` prüft damit jedes COMMUNITY-Modul.

Gebaut als Kandidat von SEDRAs Factory-Bau (`am0_herkunft`, 10.11.2026), von Hand nachgearbeitet: Importkopf geordnet, ein kaputtes JSON meldet
`herkunft_unlesbar` (der Kandidat ließ den Text des JSON-Fehlers durch), der Zwischenspeicher hält je Ordner einen Eintrag statt unbegrenzt zu
wachsen, `aktualisieren` ist neu (für `trust_apply`)."""
import hashlib
import json
import os
import pathlib
import re
from datetime import datetime, timezone

ORDNER = "uix_herkunft"

def _validate_area(area):
    if not isinstance(area, str) or area not in ("tools", "shells"):
        raise ValueError("area")

def _validate_mid(mid):
    if not isinstance(mid, str) or not re.match(r'^[a-z0-9][a-z0-9-]{1,39}$', mid):
        raise ValueError("id")

def pfad(project_root, area, mid):
    _validate_area(area)
    _validate_mid(mid)
    project_root = pathlib.Path(project_root)
    return project_root / "local_config" / ORDNER / area / (mid + ".json")

def erfassen(folder, area):
    _validate_area(area)
    folder = pathlib.Path(folder)
    if not folder.is_dir():
        raise ValueError("ordner")
    result = {}
    for root, dirs, files in os.walk(folder):
        rel_root = pathlib.Path(root).relative_to(folder)
        if rel_root.parts and any(p.startswith('.') for p in rel_root.parts):
            raise ValueError("punkt_pfad")
        for d in dirs:
            if d.startswith('.'):
                raise ValueError("punkt_pfad")
        for fname in files:
            if fname.startswith('.'):
                raise ValueError("punkt_pfad")
            full_path = pathlib.Path(root) / fname
            rel_path = full_path.relative_to(folder)
            rel_str = "/".join(rel_path.parts)
            with open(full_path, 'rb') as f:
                h = hashlib.sha256(f.read()).hexdigest()
            result[rel_str] = h
    return dict(sorted(result.items()))
def _schreibe_datei(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = str(p) + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, str(p))


def schreiben(project_root, area, mid, folder, *, quelle, mission_id, vertrauen):
    _validate_area(area)
    _validate_mid(mid)
    p = pfad(project_root, area, mid)
    p.parent.mkdir(parents=True, exist_ok=True)
    dateien = erfassen(folder, area)
    jetzt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {
        "schema": 1,
        "art": area,
        "id": mid,
        "vertrauen_beim_einbau": vertrauen,
        "quelle": str(quelle),
        "commit": None,
        "mission_id": mission_id,
        "eingebaut_am": jetzt,
        "dateien": dateien,
    }
    _schreibe_datei(p, data)
    return data


def aktualisieren(project_root, area, mid, folder):
    alt = lesen(project_root, area, mid)
    if alt is None:
        return None
    alt["dateien"] = erfassen(folder, area)
    _schreibe_datei(pfad(project_root, area, mid), alt)
    return alt


def lesen(project_root, area, mid):
    _validate_area(area)
    _validate_mid(mid)
    p = pfad(project_root, area, mid)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        raise ValueError("herkunft_unlesbar")
    if not isinstance(data, dict):
        raise ValueError("herkunft_unlesbar")
    if data.get("schema") != 1:
        raise ValueError("herkunft_unlesbar")
    return data

def entfernen(project_root, area, mid):
    _validate_area(area)
    _validate_mid(mid)
    p = pfad(project_root, area, mid)
    if p.exists():
        p.unlink()

def pruefen(folder, area, eintrag):
    _validate_area(area)
    if not isinstance(eintrag, dict) or "dateien" not in eintrag or not isinstance(eintrag["dateien"], dict):
        return ["herkunft_unlesbar"]
    folder_path = pathlib.Path(folder)
    if not folder_path.is_dir():
        folder_dateien = {}
    else:
        try:
            folder_dateien = erfassen(folder, area)
        except ValueError:
            return ["herkunft_pfad_ungueltig"]
    eintrag_dateien = eintrag["dateien"]
    alle_pfade = sorted(set(list(eintrag_dateien.keys()) + list(folder_dateien.keys())))
    ergebnis = []
    for pfad in alle_pfade:
        im_eintrag = pfad in eintrag_dateien
        im_ordner = pfad in folder_dateien
        if im_eintrag and not im_ordner:
            ergebnis.append(f"herkunft_datei_fehlt:{pfad}")
        elif im_ordner and not im_eintrag:
            ergebnis.append(f"herkunft_datei_neu:{pfad}")
        elif im_eintrag and im_ordner:
            if eintrag_dateien[pfad] != folder_dateien[pfad]:
                ergebnis.append(f"herkunft_abweichung:{pfad}")
    return ergebnis

class HerkunftsPruefer:
    def __init__(self):
        self.hash_laeufe = 0
        self._cache = {}

    def pruefen(self, folder, area, eintrag):
        folder_path = pathlib.Path(folder).resolve()
        folder_key = str(folder_path)
        eintrag_text = json.dumps(eintrag, sort_keys=True, default=str)
        if not folder_path.is_dir():
            self.hash_laeufe += 1
            return pruefen(folder, area, eintrag)
        try:
            status = self._status(folder_path)
        except ValueError:
            self.hash_laeufe += 1
            return pruefen(folder, area, eintrag)
        alt = self._cache.get(folder_key)
        if alt is not None and alt[0] == status and alt[1] == eintrag_text:
            return list(alt[2])
        result = pruefen(folder, area, eintrag)
        self._cache[folder_key] = (status, eintrag_text, result)
        self.hash_laeufe += 1
        return list(result)

    def _status(self, folder_path):
        status = {}
        for root, dirs, files in os.walk(folder_path):
            rel_root = pathlib.Path(root).relative_to(folder_path)
            if rel_root.parts and any(p.startswith('.') for p in rel_root.parts):
                raise ValueError("punkt_pfad")
            for d in dirs:
                if d.startswith('.'):
                    raise ValueError("punkt_pfad")
            for fname in files:
                if fname.startswith('.'):
                    raise ValueError("punkt_pfad")
                full_path = pathlib.Path(root) / fname
                rel_path = full_path.relative_to(folder_path)
                rel_str = "/".join(rel_path.parts)
                st = os.stat(full_path)
                status[rel_str] = (rel_str, st.st_size, st.st_mtime_ns)
        return tuple(sorted(status.values(), key=lambda x: x[0]))
