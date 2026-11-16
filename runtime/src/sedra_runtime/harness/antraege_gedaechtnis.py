"""Antrag „Gedächtnis-Notiz“ (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md GN-05): das Modell legt eine Notiz nie selbst an, es stellt einen Antrag im Posteingang
des Captains (Klasse H, Art `request:harness_gedaechtnis`). Erst nach „Freigeben und anwenden“ entsteht oder ändert sich die Datei unter
`runtime_data/harness/gedaechtnis/<projekt>/` (harness/gedaechtnis_notizen.py). Die Bindung trägt den Stand der Zieldatei: ändert sie sich zwischen Antrag und
Freigabe, greift `binding_stale`. Die Projekt-ID setzt der Server (das Werkzeug), nie das Modell."""
from __future__ import annotations

import hashlib

from ..desk import gated
from . import gedaechtnis_notizen as gn

KIND_NOTIZ = 'harness_gedaechtnis'
AKTION = 'HARNESS_GEDAECHTNIS_WRITE'
ANTRAEGE_MAX = 5


def _stand(hub, projekt_id, name):
    pfad = gn.ordner(hub.project_root, projekt_id) / (gn._name(name) + '.md')
    return hashlib.sha256(pfad.read_bytes()).hexdigest() if pfad.is_file() else None


def _offene(hub):
    offen = getattr(hub, '_open_requests', None)
    return [r for r in (offen() if callable(offen) else []) if r.get('kind') == KIND_NOTIZ]


def notiz_antrag(hub, projekt_id, payload):
    """Prüft die Notiz (Form, Inhalt, Ähnlichkeit) und legt den Antrag an. Fehler (ValueError) nennen den Grund für das Modell."""
    p = payload if isinstance(payload, dict) else {}
    typ, name, description, text = gn.pruefen(p.get('typ'), p.get('name'), p.get('description'), p.get('text'))
    vorhanden = _stand(hub, projekt_id, name) is not None
    ersetzt = str(p.get('ersetzt') or '').strip().lower()
    if vorhanden:
        if ersetzt != name:
            raise gn.NotizFehler(f'notiz_gibt_es: {name} – setze ersetzt="{name}", um sie zu ändern, statt eine zweite anzulegen')
    else:
        if ersetzt:
            raise gn.NotizFehler(f'notiz_unbekannt: {ersetzt} – ersetzt nennt nur eine vorhandene Notiz')
        aehnlich = gn.aehnlich(hub.project_root, projekt_id, name, description)
        if aehnlich and p.get('neu') is not True:
            raise gn.NotizFehler(f'aehnlich: {aehnlich} behandelt dasselbe – ändere diese Notiz (ersetzt="{aehnlich}", dein Name = {aehnlich}); '
                                 'nur wenn es wirklich etwas anderes ist, setze neu=true')
        if len(gn.liste(hub.project_root, projekt_id)) >= gn.NOTIZEN_MAX:
            raise gn.NotizFehler(f'zu_viele_notizen: höchstens {gn.NOTIZEN_MAX} je Projekt')
    if len(_offene(hub)) >= ANTRAEGE_MAX:
        raise gn.NotizFehler(f'zu_viele_offene_antraege: {ANTRAEGE_MAX} Gedächtnis-Anträge warten schon im Posteingang')
    ziel = f'gedaechtnis/{projekt_id}/{name}'
    binding = {'werkzeug': 'gedaechtnis_vorschlagen', 'ziel': ziel, 'projekt': projekt_id, 'notiz': {'typ': typ, 'name': name, 'description': description, 'text': text},
               'aendern': vorhanden, 'ziel_stand': _stand(hub, projekt_id, name)}
    req = gated.request(hub, KIND_NOTIZ, AKTION, ziel, binding, exact=True,
                        risks=[f'Notiz „{name}“ ({typ}) {"ersetzt eine vorhandene" if vorhanden else "wird neu angelegt"}; sie steht danach im Index jeder neuen Sitzung dieses Projekts'],
                        describe=f'Gedächtnis-Notiz {"ändern" if vorhanden else "anlegen"}: {name} – {description[:80]}')
    return {'mission_id': req['mission_id'], 'name': name, 'aendern': vorhanden}


def notiz_anwenden(hub, binding):
    """Erst nach „Freigeben und anwenden“: schreibt die Notiz und führt den Index nach."""
    pid, n = str(binding.get('projekt') or ''), binding.get('notiz') or {}
    if _stand(hub, pid, n.get('name')) != binding.get('ziel_stand'):
        raise ValueError(gated.STALE)
    out = gn.speichern(hub.project_root, pid, n.get('typ'), n.get('name'), n.get('description'), n.get('text'), neu=not binding.get('aendern'))
    try:
        hub.runtime.audit.append('HARNESS_GEDAECHTNIS_NOTIZ', component='harness', payload={'projekt': pid, 'name': out['name'], 'typ': out['typ'], 'geaendert': bool(binding.get('aendern'))})
    except Exception:
        pass
    return {'geschrieben': f"gedaechtnis/{pid}/{out['name']}.md"}
