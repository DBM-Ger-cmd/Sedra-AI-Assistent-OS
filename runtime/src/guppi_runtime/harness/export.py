"""Sitzung als Markdown (V6, Bau 1.11.2026): nur lesend, aus den Einträgen der JSONL-Datei – Verlauf, Werkzeugzeilen (gekürzt), Karten mit Entscheidung,
Erlaubnisse. Für Berichte und Übergaben. Rein: keine Dateien, kein Zustand. `GET /api/harness/sitzungen/<id>/export` liefert {markdown, dateiname}."""
from __future__ import annotations

import json
import re

ERGEBNIS_MAX = 1200           # Zeichen je Werkzeugausgabe im Export (die ganze steht in der Sitzung)
DATEINAME = re.compile(r'[^a-z0-9äöüß-]+')


def _zeit(e):
    z = str(e.get('zeit') or '')
    return z[11:16] if len(z) >= 16 else z


def _kurz(text, n=ERGEBNIS_MAX):
    s = str(text or '')
    return s if len(s) <= n else s[:n].rstrip() + '\n… (' + f'{len(s):,}'.replace(',', '.') + ' Zeichen, gekürzt)'


def dateiname(sid, titel):
    kern = DATEINAME.sub('-', str(titel or '').casefold()).strip('-')[:40] or 'sitzung'
    return f'{sid}-{kern}.md'


def markdown(s, sid, projekt_name=None):
    """Der Export einer geladenen Sitzung (`Sitzungen.laden`): Kopf, dann je Eintrag ein Block in Reihenfolge."""
    kopf, eintraege = s.get('kopf') or {}, s.get('eintraege') or []
    titel = s.get('titel') or 'Ohne Titel'
    zeilen = [f'# {titel}', '',
              f"Sitzung {sid} · Projekt {projekt_name or kopf.get('projekt') or '–'} · angelegt {str(kopf.get('angelegt') or '')[:16].replace('T', ' ')}"
              + (f" · Vorlage {kopf.get('vorlage')}" if kopf.get('vorlage') else '') + (f" · Modell {s.get('modell')}" if s.get('modell') else ''), '']
    karten = {e.get('karte_id'): e for e in eintraege if e.get('typ') == 'karte' and e.get('entscheidung')}
    for e in eintraege:
        typ = e.get('typ')
        if typ == 'captain':
            zeilen += [f"## Captain · {_zeit(e)}", '', str(e.get('text') or ''), '']
        elif typ == 'modell':
            zeilen.append(f"## SEDRA · {_zeit(e)}" + (f" · {e.get('ende')}" if e.get('ende') else '') + (f" · {e.get('zuege')} Züge" if e.get('zuege') else ''))
            zeilen.append('')
            if e.get('denken_zeichen'):
                zeilen += ['<details><summary>Dachte nach · ' + f"{e['denken_zeichen']:,}".replace(',', '.') + ' Zeichen</summary>', '', str(e.get('denken_text') or '(nicht gespeichert)'), '', '</details>', '']
            if e.get('zurueckgehalten'):
                zeilen += [f"> Vom Inhaltsschutz zurückgehalten: {e['zurueckgehalten']}", '']
            elif e.get('text'):
                zeilen += [str(e['text']), '']
            if e.get('grund'):
                zeilen += [f"> Fehler: {e['grund']}", '']
        elif typ == 'werkzeug':
            status, stufe, regel = e.get('status'), e.get('stufe'), e.get('regel')
            zeilen.append(f"- **{e.get('name')}** `{_kurz(json.dumps(e.get('args') or {}, ensure_ascii=False), 200)}` → {status}"
                          + (f" ({stufe}{' · ' + str(regel) if regel else ''})" if stufe else '') + (f" · {e['dauer_s']:.1f} s" if isinstance(e.get('dauer_s'), (int, float)) else ''))
            if e.get('ergebnis'):
                zeilen += ['', '  ```', *('  ' + z for z in _kurz(e['ergebnis']).splitlines()), '  ```', '']
        elif typ == 'karte' and e.get('zustand') == 'offen':
            k = karten.get(e.get('karte_id')) or {}
            ent = k.get('entscheidung')
            zeilen += [f"> **Freigabe {e.get('karte_id')}** · {e.get('werkzeug')} `{e.get('ziel')}` · "
                       + (f"{ent}" + (' (gilt für diese Sitzung)' if ent == 'sitzung' else '') + (f" von {k.get('von')}" if k.get('von') else '') if ent else 'offen')
                       + (f" · {k['notiz']}" if k.get('notiz') else ''), '']
        elif typ == 'erlaubnis' and e.get('aktiv', True) and e.get('werkzeug'):
            zeilen += [f"> Erlaubnis für diese Sitzung: {e['werkzeug']} `{e.get('muster')}` (Karte {e.get('karte_id')})", '']
        elif typ == 'titel':
            zeilen += [f"_Titel geändert: {e.get('titel')}_", '']
    zeilen.append(f'_Exportiert aus der Harness-Shell; die Sitzung selbst liegt unter runtime_data/harness/sitzungen/{sid}.jsonl._')
    return '\n'.join(zeilen).rstrip() + '\n'
