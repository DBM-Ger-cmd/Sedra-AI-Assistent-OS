"""Verknüpfungen der Seitenleiste (Captain 02.11.2026): eigene Knöpfe links, die ein Fenster der Oberfläche öffnen (Rekorder, Logbuch …).

Der Captain legt sie über den Chat an („mach mir eine Verknüpfung zum Rekorder“) und nimmt sie mit dem Kreuz wieder weg. Eine Verknüpfung ist eine
Wahl, keine Erlaubnis: sie öffnet nur ein Fenster, das es ohnehin gibt – deshalb kein Gate (wie `vorgaben`). Grenzen: nur bekannte Orte, höchstens
`MAX` Stück, ein Ort nur einmal, der Name höchstens `NAME_MAX` Zeichen ohne Steuerzeichen. Ablage `<projekt>/runtime_data/harness/verknuepfungen.json`, atomar."""
from __future__ import annotations

import json
import re
import secrets
import threading
from pathlib import Path

from ..core.util import atomic_write_text

MAX = 12
NAME_MAX = 30
ID = re.compile(r'V-[0-9A-F]{8}')
_LOCK = threading.Lock()


class VerknuepfungFehler(ValueError):
    """Der Text ist der Grund; er geht als Antwort an das Modell oder den Captain."""


def datei(projekt_root):
    return Path(projekt_root) / 'runtime_data' / 'harness' / 'verknuepfungen.json'


def laden(projekt_root):
    try:
        doc = json.loads(datei(projekt_root).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out = []
    for e in doc.get('verknuepfungen', []) if isinstance(doc, dict) else []:
        if isinstance(e, dict) and ID.fullmatch(str(e.get('id'))) and isinstance(e.get('ort'), str) and isinstance(e.get('name'), str):
            out.append({'id': e['id'], 'ort': e['ort'], 'name': e['name']})
    return out[:MAX]


def _schreiben(projekt_root, liste):
    p = datei(projekt_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(p, json.dumps({'version': 1, 'verknuepfungen': liste}, ensure_ascii=False, indent=1))


def hinzufuegen(projekt_root, ort, name, orte):
    """`orte`: {id: (Name, Hinweis)} – die Orte der Oberfläche. Rückgabe: der neue Eintrag."""
    ort = str(ort or '').strip()
    if ort not in orte:
        raise VerknuepfungFehler('ort_unbekannt: ' + ort + ' – erlaubt: ' + ', '.join(orte))
    name = re.sub(r'[\x00-\x1f\x7f]', ' ', str(name or '')).strip()[:NAME_MAX] or orte[ort][0][:NAME_MAX]
    with _LOCK:
        liste = laden(projekt_root)
        vorhanden = next((e for e in liste if e['ort'] == ort), None)
        if vorhanden:
            raise VerknuepfungFehler(f"schon_vorhanden: {orte[ort][0]} hat schon die Verknüpfung „{vorhanden['name']}“")
        if len(liste) >= MAX:
            raise VerknuepfungFehler(f'zu_viele: höchstens {MAX} Verknüpfungen – der Captain nimmt erst eine weg')
        neu = {'id': 'V-' + secrets.token_hex(4).upper(), 'ort': ort, 'name': name}
        _schreiben(projekt_root, liste + [neu])
    return neu


def entfernen(projekt_root, vid):
    if not ID.fullmatch(str(vid)):
        raise VerknuepfungFehler('id_ungueltig')
    with _LOCK:
        liste = laden(projekt_root)
        rest = [e for e in liste if e['id'] != vid]
        if len(rest) == len(liste):
            raise VerknuepfungFehler('unbekannt: ' + str(vid))
        _schreiben(projekt_root, rest)
    return {'id': vid}
