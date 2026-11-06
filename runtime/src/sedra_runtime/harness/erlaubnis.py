"""Sitzungs-Erlaubnisse der Harness-Shell (Bau 1.11.2026, Paket P0 M1 – aus dem Harness-Vergleich vom 31.10.).

Auf einer Freigabe-Karte kann der Captain statt „Erlauben“ auch **„Für diese Sitzung erlauben“** wählen: der Aufruf läuft wie bei
`erlauben`, und dazu merkt sich die Sitzung ein Muster, das gleichartige Aufrufe bis zum Schließen der Sitzung ohne Karte durchlässt
(Audit `HARNESS_APPROVED_BY sitzung:<karte>`). Grenzen (nicht verhandelbar, im Code):
- nie für `verboten`, nie für einen festen Vorbehalt (harness/vorbehalte.py), nie für eine Warnkarte (W-2);
- der Schreibbereich des Projekts bleibt die harte Grenze (werkzeuge.py prüft ihn bei jedem Aufruf);
- Läufe: nur genau dieses Ziel (Lauf-Typ); `modell_laden`/`modell_entladen` nie (weicher Vorbehalt HS-28 – nur eine Aufgabe, die das Modell nennt).
Rein: keine Dateien, kein Zustand – die Ablage ist der Sitzungs-JSONL (Eintrag `erlaubnis`, Rücknahme als `aktiv: false`)."""
from __future__ import annotations

from .katalog import befehl_normal, passt, pfad_normal

GENAU = ('modell_laden', 'modell_entladen', 'lauf_starten', 'lauf_stoppen')
DATEI = ('datei_schreiben', 'datei_aendern', 'datei_lesen', 'dateien_auflisten', 'suchen')


def muster_fuer(werkzeug, ziel):
    """Das Muster, das eine Karte für die Sitzung öffnet: Dateien → der Ordner der Datei (`ordner/**`, Wurzel → `*`);
    Befehl → der Anfang der Zeile (`python -m unittest*`, `git commit*`); Modelle und Läufe → genau das Ziel."""
    if werkzeug in GENAU:
        return str(ziel or '').strip()
    if werkzeug == 'befehl':
        teile = befehl_normal(ziel).split(' ')
        kopf = teile[:1]
        if len(teile) > 1:
            kopf = teile[:3] if teile[1] == '-m' and len(teile) > 2 else teile[:2]
        return ' '.join(kopf) + '*'
    rel = pfad_normal(ziel)
    ordner = rel.rsplit('/', 1)[0] if '/' in rel else ''
    return ordner + '/**' if ordner else '*'


def deckt(erlaubnisse, werkzeug, ziel):
    """Die erste aktive Erlaubnis der Sitzung, die diesen Aufruf deckt – oder None."""
    for e in erlaubnisse or ():
        if not isinstance(e, dict) or e.get('aktiv') is False or e.get('werkzeug') != werkzeug:
            continue
        muster = e.get('muster')
        if not muster:
            continue
        if werkzeug in GENAU:
            if str(muster).strip() == str(ziel or '').strip():
                return e
        elif passt(muster, werkzeug, ziel):
            return e
    return None


def aktive(eintraege):
    """Aus den Einträgen einer Sitzung die geltenden Erlaubnisse (Rücknahme `aktiv: false` zur selben Karte hebt auf), in Reihenfolge."""
    stand = {}
    for e in eintraege or ():
        if not isinstance(e, dict) or e.get('typ') != 'erlaubnis':
            continue
        kid = e.get('karte_id')
        if e.get('aktiv') is False:
            stand.pop(kid, None)
        elif kid and e.get('werkzeug') and e.get('muster'):
            stand[kid] = {'karte_id': kid, 'werkzeug': e['werkzeug'], 'muster': e['muster'], 'regel': e.get('regel'), 'zeit': e.get('zeit'), 'aktiv': True}
    return list(stand.values())


def erlaubt_fuer_karte(karte):
    """Darf diese Karte eine Sitzungs-Erlaubnis werden? Nein bei Vorbehalt, Warnkarte, Aufgabenkarte oder Stufe verboten."""
    if not isinstance(karte, dict) or karte.get('art', 'werkzeug') != 'werkzeug':
        return False
    if karte.get('vorbehalt') or karte.get('warnung') or karte.get('stufe') == 'verboten':
        return False
    if karte.get('werkzeug') in ('modell_laden', 'modell_entladen'):
        return False
    return bool(karte.get('werkzeug')) and karte.get('ziel') is not None
