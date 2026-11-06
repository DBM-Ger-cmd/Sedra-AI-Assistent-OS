"""Konsole für Freigaben der Klasse H (SPEC_APPS_v1_O3PLUS_G9_G2 G9-07): außerhalb des Browsers ansehen, bestätigen, ablehnen.

    python -m sedra_runtime.desk.freigabe_konsole --root <projektordner> liste
    python -m sedra_runtime.desk.freigabe_konsole --root <projektordner> freigeben B-…
    python -m sedra_runtime.desk.freigabe_konsole --root <projektordner> ablehnen B-…

Spricht mit der laufenden Oberfläche über den Token des Konsolen-Clients (uix_clients, nur `cli`). Unter Windows: FREIGABE.bat.
Prüfstelle (O3-02): Änderungen nur durch Claude mit Freigabe des Captains."""
from __future__ import annotations

import argparse
import json
import sys


def ausfuehren(root, befehl, kennung=None):
    from .. import uix_clients
    if befehl == 'liste':
        status, out = uix_clients.call(root, 'cli', '/api/freigabe/offen', {})
        if status != 200:
            return 2, json.dumps(out, ensure_ascii=False)
        offen = (out or {}).get('offen') or []
        if not offen:
            return 0, 'Keine Freigabe wartet auf deine Bestätigung.'
        teile = []
        for b in offen:
            teile.append(f"── {b['bid']} (noch {b['rest_s'] // 60} min) ──\n{b['text']}\n")
        return 0, '\n'.join(teile) + '\nBestätigen: FREIGABE.bat freigeben <Kennung> · Ablehnen: FREIGABE.bat ablehnen <Kennung>'
    if befehl in ('freigeben', 'ablehnen'):
        if not kennung:
            return 2, 'Kennung fehlt (B-…). Erst „liste“.'
        status, out = uix_clients.call(root, 'cli', '/api/freigabe/bestaetigen', {'id': kennung, 'antwort': 'ja' if befehl == 'freigeben' else 'nein'})
        return (0 if status == 200 else 2), json.dumps(out, ensure_ascii=False, indent=2)
    return 2, 'Befehl unbekannt: liste, freigeben, ablehnen'


def main(argv=None):
    p = argparse.ArgumentParser(prog='freigabe', description='Freigaben der Klasse H außerhalb des Browsers (G9)')
    p.add_argument('--root', required=True)
    p.add_argument('befehl', choices=['liste', 'freigeben', 'ablehnen'])
    p.add_argument('kennung', nargs='?')
    a = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    try:
        code, text = ausfuehren(a.root, a.befehl, a.kennung)
    except ValueError as exc:                    # z. B. uix_not_running, keine Client-Datei
        code, text = 2, f'Fehler: {exc} – läuft SEDRA? (--root muss der Projektordner sein, z. B. workspace/SEDRA_OS)'
    print(text)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
