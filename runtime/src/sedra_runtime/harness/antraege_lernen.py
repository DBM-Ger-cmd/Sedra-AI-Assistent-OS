"""W4-Anträge: `rueckblick_schreiben` und `vorschlaege_pflegen` legen echte Anträge im Posteingang an.

Die Werkzeuge selbst schreiben nichts: `vorbereiten` baut Ziel/Vorschau/Gate, `ausfuehren` ruft hier
`rueckblick_antrag` / `vorschlag_antrag` auf, die über `gated.request` eine Mission mit einem Gate
anlegen. Der Antrag liegt danach im Posteingang des Captains. Erst nach „Freigeben und anwenden“
wird der jeweilige Applier (`_rueckblick_anwenden` / `_vorschlag_anwenden`) aufgerufen und schreibt
in `docs/AAR/LESSONS.md` bzw. `docs/AAR/VORSCHLAEGE.md` – nur im Projekt und im Schreibbereich.
Die Bindung enthält den Stand der Zieldatei, damit `binding_stale` greift, wenn sich das Ziel
zwischen Antrag und Freigabe ändert.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..desk import gated
from . import projekte as harness_projekte

KIND_RUECKBLICK = 'harness_rueckblick'
KIND_VORSCHLAG = 'harness_vorschlag'

ZIEL_RUECKBLICK = 'docs/AAR/LESSONS.md'
ZIEL_VORSCHLAG = 'docs/AAR/VORSCHLAEGE.md'

RUECKBLICK_ANTRAEGE_MAX = 5
VORSCHLAG_ANTRAEGE_MAX = 5


def _projekt(root):
    return {'id': 'p-lernen', 'name': 'Lernen', 'wurzel': str(root), 'schreibbereich': ['docs/**']}


def _stand(root: Path, ziel: str):
    pfad = root / ziel
    return hashlib.sha256(pfad.read_bytes()).hexdigest() if pfad.is_file() else None


def _im_schreibbereich(root: Path, ziel: str) -> bool:
    return harness_projekte.im_schreibbereich(_projekt(root), Path(ziel))


def _offene(hub, kind):
    offen = getattr(hub, '_open_requests', None)
    return [r for r in (offen() if callable(offen) else []) if r.get('kind') == kind]


def rueckblick_antrag(hub, payload):
    """Legt über gated.request einen Antrag „Rückblick“ im Posteingang an. Schreibt noch nichts."""
    payload = payload if isinstance(payload, dict) else {}
    titel = str(payload.get('titel') or '').strip()
    dokument = str(payload.get('dokument') or ZIEL_RUECKBLICK).strip() or ZIEL_RUECKBLICK
    if not titel:
        raise ValueError('argument_fehlt: titel')
    if dokument != ZIEL_RUECKBLICK:
        raise ValueError(f'dokument_unerlaubt: rueckblick_schreiben schreibt nur {ZIEL_RUECKBLICK}')
    if len(_offene(hub, KIND_RUECKBLICK)) >= RUECKBLICK_ANTRAEGE_MAX:
        raise ValueError(f'zu_viele_offene_antraege: {RUECKBLICK_ANTRAEGE_MAX} Rueckblick-Anträge warten schon im Posteingang')
    if not _im_schreibbereich(hub.project_root, dokument):
        raise ValueError(f'ausserhalb_schreibbereich: {dokument} – schreiben nur in docs/**')
    antrag = {k: payload[k] for k in ('titel', 'sitzung_id', 'datum', 'was_gelaufen_ist', 'was_schief_lief', 'massnahmen') if k in payload}
    binding = {
        'werkzeug': 'rueckblick_schreiben',
        'ziel': dokument,
        'dokument': dokument,
        'antrag': antrag,
        'ziel_stand': _stand(hub.project_root, dokument),
    }
    req = gated.request(
        hub, KIND_RUECKBLICK, 'HARNESS_RUECKBLICK_WRITE', dokument, binding, exact=True,
        risks=[f'Rückblick „{titel}“: nach Freigabe wird ein neuer Abschnitt in {dokument} angelegt'],
        describe=f'Rückblick anlegen: {titel}',
    )
    return {'mission_id': req['mission_id'], 'titel': titel, 'dokument': dokument}


def vorschlag_antrag(hub, payload):
    """Legt über gated.request einen Antrag „Vorschlag pflegen“ im Posteingang an. Schreibt noch nichts."""
    payload = payload if isinstance(payload, dict) else {}
    titel = str(payload.get('titel') or '').strip()
    aktion = str(payload.get('aktion') or '').strip()
    if not titel or aktion not in ('anlegen', 'aendern', 'status_setzen'):
        raise ValueError('argument_fehlt: titel und aktion (anlegen, aendern oder status_setzen)')
    dokument = ZIEL_VORSCHLAG
    if len(_offene(hub, KIND_VORSCHLAG)) >= VORSCHLAG_ANTRAEGE_MAX:
        raise ValueError(f'zu_viele_offene_antraege: {VORSCHLAG_ANTRAEGE_MAX} Vorschlag-Anträge warten schon im Posteingang')
    if not _im_schreibbereich(hub.project_root, dokument):
        raise ValueError(f'ausserhalb_schreibbereich: {dokument} – schreiben nur in docs/**')
    antrag = {k: payload[k] for k in ('titel', 'aktion', 'beschreibung', 'quelle', 'status', 'prioritaet', 'captain_zustimmung') if k in payload}
    binding = {
        'werkzeug': 'vorschlaege_pflegen',
        'ziel': dokument,
        'dokument': dokument,
        'antrag': antrag,
        'ziel_stand': _stand(hub.project_root, dokument),
    }
    req = gated.request(
        hub, KIND_VORSCHLAG, 'HARNESS_VORSCHLAG_WRITE', dokument, binding, exact=True,
        risks=[f'Vorschlag „{titel}“ ({aktion}): nach Freigabe wird die Vorschlagsliste unter {dokument} geändert'],
        describe=f'Vorschlag pflegen: {titel} ({aktion})',
    )
    return {'mission_id': req['mission_id'], 'titel': titel, 'aktion': aktion, 'dokument': dokument}


def _abschnitt_rueckblick(antrag):
    zeilen = []
    zeilen.append(f"## {antrag.get('datum', '')} · {antrag.get('titel', '(ohne Titel)')}")
    if antrag.get('sitzung_id'):
        zeilen.append(f"\nSitzung: {antrag['sitzung_id']}")
    zeilen.append(f"\n**Was lief gut:** {antrag.get('was_gelaufen_ist', '')}")
    if antrag.get('was_schief_lief'):
        zeilen.append(f"\n**Was schief lief:** {antrag['was_schief_lief']}")
    massnahmen = antrag.get('massnahmen') or []
    if massnahmen:
        zeilen.append("\n**Maßnahmen:**")
        for m in massnahmen:
            zeilen.append(f"- {m.get('beschreibung', '')} (verantwortlich: {m.get('verantwortlich', '-')}, frist: {m.get('frist?', '-')})")
    zeilen.append("\n---\n")
    return '\n'.join(zeilen)


def _abschnitt_vorschlag(antrag):
    zeilen = []
    zeilen.append(f"## {antrag.get('titel', '(ohne Titel)')} ({antrag.get('aktion', '')})")
    zeilen.append(f"\n- Aktion: {antrag.get('aktion', '')}")
    zeilen.append(f"- Quelle: {antrag.get('quelle', 'chat')}")
    zeilen.append(f"- Status: {antrag.get('status', 'offen')}")
    zeilen.append(f"- Priorität: {antrag.get('prioritaet', 'mittel')}")
    zeilen.append(f"- Captain-Zustimmung: {'ja' if antrag.get('captain_zustimmung') else 'nein'}")
    if antrag.get('beschreibung'):
        zeilen.append(f"\n{antrag['beschreibung']}")
    zeilen.append("\n---\n")
    return '\n'.join(zeilen)


def _anwenden(hub, binding, dokument, sektion):
    pfad = hub.project_root / dokument
    stand_jetzt = _stand(hub.project_root, dokument)
    if stand_jetzt != binding.get('ziel_stand'):
        raise ValueError(gated.STALE)
    if not _im_schreibbereich(hub.project_root, dokument):
        raise ValueError(gated.REFUSED + f'ausserhalb_schreibbereich: {dokument}')
    pfad.parent.mkdir(parents=True, exist_ok=True)
    alt = pfad.read_text(encoding='utf-8') if pfad.is_file() else ''
    neu = (alt + '\n' + sektion + '\n') if alt.strip() else (sektion + '\n')
    pfad.write_text(neu, encoding='utf-8')
    return {'geschrieben': dokument}


def rueckblick_anwenden(hub, binding):
    """Wird erst nach „Freigeben und anwenden“ aufgerufen: schreibt den Rückblick in LESSONS.md."""
    antrag = binding.get('antrag') or {}
    titel = antrag.get('titel', '(ohne Titel)')
    dokument = str(binding.get('dokument') or ZIEL_RUECKBLICK)
    out = _anwenden(hub, binding, dokument, _abschnitt_rueckblick(antrag))
    try:
        hub.runtime.audit.append('HARNESS_RUECKBLICK_ANGENOMMEN', component='harness', payload={'titel': titel, 'dokument': dokument})
    except Exception:
        pass
    return out


def vorschlag_anwenden(hub, binding):
    """Wird erst nach „Freigeben und anwenden“ aufgerufen: schreibt den Vorschlag in VORSCHLAEGE.md."""
    antrag = binding.get('antrag') or {}
    titel = antrag.get('titel', '(ohne Titel)')
    dokument = str(binding.get('dokument') or ZIEL_VORSCHLAG)
    out = _anwenden(hub, binding, dokument, _abschnitt_vorschlag(antrag))
    try:
        hub.runtime.audit.append('HARNESS_VORSCHLAG_ANGENOMMEN', component='harness', payload={'titel': titel, 'dokument': dokument})
    except Exception:
        pass
    return out
