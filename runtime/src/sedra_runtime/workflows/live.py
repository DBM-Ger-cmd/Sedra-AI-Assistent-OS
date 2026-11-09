"""Live-Meldungen laufender Prozesse: der Prozess sagt selbst, in welchem Schritt er gerade ist.

Die Prozess-Apps zeigen die Abläufe von SEDRA als Diagramm (Selbstabbild). Damit im Diagramm der aktuelle Schritt leuchtet, ohne dass die Anzeige
rät, meldet der laufende Prozess seinen Schritt in eine kleine Datei `runtime_data/live/<prozess>.json` im Projekt. Die Anzeige liest nur.
`prozess` ist die Kennung des Ablaufs in `config/selbstabbild.yaml` (z. B. `vollautomatischer-bau`), `schritt` die Kennung des Schritts darin.

Aufruf aus einem Skript:
    from sedra_runtime.workflows import live
    live.melde(projekt, 'vollautomatischer-bau', 'bauen', 'laeuft', text='Stufe S2, Versuch 3 von 6')
    live.melde(projekt, 'vollautomatischer-bau', None, 'fertig')        # Ende des Laufs
Von der Befehlszeile (jede Sprache): python -m sedra_runtime.workflows.live melde --projekt <Ordner> --prozess <id> --schritt <id> --zustand laeuft --text "…"
Zustände: laeuft · wartet (ein Mensch ist dran) · fehler · fertig. Ein neuer Lauf beginnt mit dem ersten Schritt nach `fertig` oder mit `--neu`.
Nichts hier startet, ändert oder gibt etwas frei; die Datei ist reine Anzeige und kein Recht."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ORDNER = ('runtime_data', 'live')
KENNUNG = re.compile(r'[a-z0-9][a-z0-9-]{0,60}')
ZUSTAENDE = ('laeuft', 'wartet', 'fehler', 'fertig')
MAX_VERLAUF = 200
MAX_TEXT = 240
VERALTET_S = 180


def _jetzt():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _pfad(projekt_root, prozess):
    if not isinstance(prozess, str) or not KENNUNG.fullmatch(prozess):
        raise ValueError('live_prozess_ungueltig')
    return Path(projekt_root).joinpath(*ORDNER) / (prozess + '.json')


def _lesen(pfad):
    try:
        wert = json.loads(Path(pfad).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return wert if isinstance(wert, dict) and wert.get('schema') == 1 else None


def melde(projekt_root, prozess, schritt, zustand='laeuft', *, text=None, lauf=None, neu=False, zeit=None):
    """Den aktuellen Schritt melden (atomar geschrieben). `schritt` None nur bei `fertig` oder `fehler` ohne Schritt."""
    pfad = _pfad(projekt_root, prozess)
    if zustand not in ZUSTAENDE:
        raise ValueError('live_zustand_ungueltig')
    if schritt is not None and (not isinstance(schritt, str) or not KENNUNG.fullmatch(schritt)):
        raise ValueError('live_schritt_ungueltig')
    if schritt is None and zustand in ('laeuft', 'wartet'):
        raise ValueError('live_schritt_fehlt')
    jetzt = zeit or _jetzt()
    alt = None if neu else _lesen(pfad)
    if alt and alt.get('zustand') == 'fertig' and schritt is not None:
        alt = None                                                   # nach einem Ende beginnt ein neuer Lauf
    satz = {'schema': 1, 'prozess': prozess, 'gestartet': (alt or {}).get('gestartet') or jetzt, 'verlauf': list((alt or {}).get('verlauf') or [])}
    eintrag = {'zeit': jetzt, 'schritt': schritt, 'zustand': zustand}
    if text:
        eintrag['text'] = str(text)[:MAX_TEXT]
    satz['verlauf'] = (satz['verlauf'] + [eintrag])[-MAX_VERLAUF:]
    satz.update(schritt=schritt, zustand=zustand, text=eintrag.get('text'), lauf=lauf if lauf is not None else (alt or {}).get('lauf'), aktualisiert=jetzt)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.live-', suffix='.tmp', dir=str(pfad.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(satz, f, ensure_ascii=False, indent=1)
        os.replace(tmp, pfad)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return satz


def _zeit(text):
    try:
        return datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None


def knoten(satz, prozess=None):
    """{Knotenkennung: Zustand} für das Diagramm (rein): besuchte Schritte sind fertig, sobald ein anderer folgt; der aktuelle trägt den gemeldeten
    Zustand; ein Schritt, dessen letzte Meldung `fehler` war, bleibt fehler. Die Knotenkennung ist die des Selbstabbilds (`sa-<prozess>-<schritt>`)."""
    p = prozess or satz.get('prozess')
    letzter, reihenfolge = {}, []
    for e in satz.get('verlauf') or []:
        s = e.get('schritt')
        if s is None:
            continue
        if s not in letzter:
            reihenfolge.append(s)
        letzter[s] = e.get('zustand')
    out = {}
    aktuell = satz.get('schritt')
    for s in reihenfolge:
        z = letzter[s]
        if s == aktuell and satz.get('zustand') != 'fertig':
            out['sa-%s-%s' % (p, s)] = satz.get('zustand')
        elif z == 'fehler':
            out['sa-%s-%s' % (p, s)] = 'fehler'
        else:
            out['sa-%s-%s' % (p, s)] = 'fertig'
    return out


def lesen(projekt_root, *, jetzt=None, veraltet_s=VERALTET_S):
    """Alle Meldungen, neueste zuerst; `veraltet`: laufend oder wartend, aber seit `veraltet_s` Sekunden nichts mehr gemeldet. Kaputte Dateien fehlen."""
    ordner = Path(projekt_root).joinpath(*ORDNER)
    jetzt = jetzt or datetime.now(timezone.utc)
    out = []
    if not ordner.is_dir():
        return out
    for pfad in sorted(ordner.glob('*.json')):
        satz = _lesen(pfad)
        if not satz or not KENNUNG.fullmatch(str(satz.get('prozess') or '')) or satz.get('zustand') not in ZUSTAENDE:
            continue
        t = _zeit(satz.get('aktualisiert'))
        alter = int((jetzt - t).total_seconds()) if t else None
        out.append(dict(satz, knoten=knoten(satz), alter_s=alter, veraltet=bool(alter is not None and alter > veraltet_s and satz['zustand'] in ('laeuft', 'wartet'))))
    return sorted(out, key=lambda s: str(s.get('aktualisiert') or ''), reverse=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='befehl', required=True)
    m = sub.add_parser('melde')
    m.add_argument('--projekt', required=True)
    m.add_argument('--prozess', required=True)
    m.add_argument('--schritt')
    m.add_argument('--zustand', default='laeuft', choices=ZUSTAENDE)
    m.add_argument('--text')
    m.add_argument('--lauf')
    m.add_argument('--neu', action='store_true')
    a = p.parse_args(argv)
    try:
        melde(a.projekt, a.prozess, a.schritt, a.zustand, text=a.text, lauf=a.lauf, neu=a.neu)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
