"""Prüfung des Abnahmesatzes wissen_goldsatz_v2.json (Spec 7, S7.5, D7.11). Nur Standardbibliothek, liest nur.

Geprüft wird: Zählungen (120 = 110 + 10; 30/50/30 je Art; je Quellgruppe mindestens 10 beantwortbare; mindestens 10 mit
Liste/Tabelle), Form jeder Frage, dass jede `datei` im Repo existiert (außer Kennungen mit Präfix knowledge:, arbeitsumfeld:,
gateway:), dass jeder `abschnitt` einer Doku-Frage als Überschrift in der Datei vorkommt (jedes Glied des Pfads), dass jede
Logbuch-Stelle genau eine Zeile trifft, dass jede Gateway-Kennung in gateway/klassen.py bzw. gateway/wissen.py steht, dass bei
„umschrieben“ und „fachbegriff“ keines der kennzeichnenden Wörter der Stelle in der Frage steht, und dass keine Frage doppelt ist.
Am Ende die SHA-256 der Datei. Aufruf: python runtime/benchmarks/wissen_goldsatz_v2_check.py  (Exit 0 = alles in Ordnung)."""
from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SATZ = REPO / 'runtime' / 'benchmarks' / 'wissen_goldsatz_v2.json'
LOGBUCH = 'docs/LOGBUCH_AGENT_MANAGER.md'
KENNUNG = ('knowledge:', 'arbeitsumfeld:', 'gateway:')
ARTEN = {'wortgleich': 30, 'umschrieben': 50, 'fachbegriff': 30, 'negativ': 10}
GRUPPEN = ('doku', 'logbuch', 'knowledge', 'arbeitsumfeld', 'gateway')
ADAPTER_JE_GRUPPE = {'doku': {'markdown', 'text'}, 'logbuch': {'logbuch'}, 'knowledge': {'knowledge'},
                     'arbeitsumfeld': {'arbeitsumfeld'}, 'gateway': {'gateway'}}
_WORT = re.compile(r'[a-zäöüß0-9_\-]{4,}')
# Wörter, die eine Stelle nicht kennzeichnen (Allerweltswörter, Gliederung, Datumsteile)
_ALLGEMEIN = frozenset('''zeile lauf regel fehler schritt zustand ordner captain stand spec eine eines einer dieses nicht ohne
sedra guppi 2026 ablage mvp dieser diese nach über ueber vorarbeiter-aktion präzedenzfall praezedenzfall zeit datei lokal'''.split())


def _woerter(text):
    return {w for w in _WORT.findall(text.lower())}


def _ueberschriften(pfad):
    out = []
    for zeile in pfad.read_text(encoding='utf-8').splitlines():
        if zeile.startswith('#'):
            out.append(zeile.lstrip('#').strip())
    return out


def main():
    fehler = []
    daten = json.loads(SATZ.read_text(encoding='utf-8'))
    fragen = daten['fragen']
    for schluessel in ('name', 'version', 'beschreibung', 'stand_commit', 'verteilung'):
        if schluessel not in daten:
            fehler.append(f'Kopf: Feld {schluessel} fehlt')
    if daten.get('version') != 2:
        fehler.append('Kopf: version ist nicht 2')

    # Zählungen
    arten = collections.Counter(f.get('art') for f in fragen)
    gruppen_b = collections.Counter(f.get('gruppe') for f in fragen if f.get('art') != 'negativ')
    liste = sum(1 for f in fragen if f.get('liste_oder_tabelle') is True)
    if len(fragen) != 120:
        fehler.append(f'{len(fragen)} Fragen statt 120')
    for art, soll in ARTEN.items():
        if arten.get(art, 0) != soll:
            fehler.append(f'Art {art}: {arten.get(art, 0)} statt {soll}')
    for g in GRUPPEN:
        if gruppen_b.get(g, 0) < 10:
            fehler.append(f'Gruppe {g}: nur {gruppen_b.get(g, 0)} beantwortbare Fragen (mindestens 10)')
    if liste < 10:
        fehler.append(f'nur {liste} Fragen mit Liste/Tabelle (mindestens 10)')
    v = daten.get('verteilung', {})
    if v.get('je_art') != dict(arten) or v.get('je_gruppe_beantwortbar') != dict(gruppen_b) or v.get('liste_oder_tabelle') != liste:
        fehler.append('Kopf: verteilung stimmt nicht mit den Fragen überein')

    # Form, Doppelungen, IDs
    gesehen = {}
    ids = [f.get('id') for f in fragen]
    if ids != [f'A{i:03d}' for i in range(1, 121)]:
        fehler.append('IDs sind nicht A001 bis A120 in Reihenfolge')
    logbuch_text = (REPO / LOGBUCH).read_text(encoding='utf-8') if (REPO / LOGBUCH).is_file() else ''
    gw_text = ''
    for rel in ('runtime/src/guppi_runtime/gateway/klassen.py', 'runtime/src/guppi_runtime/gateway/wissen.py'):
        p = REPO / rel
        if p.is_file():
            gw_text += p.read_text(encoding='utf-8')
    ueberschriften = {}
    for f in fragen:
        fid = f.get('id')
        frage = (f.get('frage') or '').strip()
        norm = re.sub(r'\s+', ' ', frage.lower())
        if norm in gesehen:
            fehler.append(f'{fid}: Frage doppelt zu {gesehen[norm]}')
        gesehen[norm] = fid
        if not frage.endswith('?'):
            fehler.append(f'{fid}: Frage endet nicht mit Fragezeichen')
        if f.get('gruppe') not in GRUPPEN:
            fehler.append(f'{fid}: unbekannte Gruppe {f.get("gruppe")}')
        if not isinstance(f.get('liste_oder_tabelle'), bool):
            fehler.append(f'{fid}: liste_oder_tabelle fehlt oder ist kein Wahrheitswert')
        if f.get('erwartet_ueber') != 'adapter':
            fehler.append(f'{fid}: erwartet_ueber ist nicht adapter')
        quellen = f.get('quellen')
        if f.get('art') == 'negativ':
            if quellen:
                fehler.append(f'{fid}: Negativfrage mit Quellen')
            continue
        if not quellen:
            fehler.append(f'{fid}: keine Quelle')
            continue
        for qu in quellen:
            adapter, datei, abschnitt = qu.get('adapter'), qu.get('datei') or '', qu.get('abschnitt') or ''
            if not adapter or not datei or not abschnitt:
                fehler.append(f'{fid}: Quelle unvollständig {qu}')
                continue
            if adapter not in ADAPTER_JE_GRUPPE[f['gruppe']]:
                fehler.append(f'{fid}: Adapter {adapter} passt nicht zur Gruppe {f["gruppe"]}')
            if re.search(r'^[A-Za-z]:\\|^/home/|^/Users/|\\\\', datei):
                fehler.append(f'{fid}: lokaler Pfad in datei: {datei}')
            if datei.startswith(KENNUNG):
                if datei.startswith('gateway:'):
                    rid = datei.split(':', 1)[1]
                    schluessel = rid.split('-', 1)[1] if rid[:2] in ('F-', 'B-', 'Z-', 'L-') else rid
                    if rid.startswith('L-'):
                        schluessel = f"'nr': {rid[2:]}"
                    elif rid.startswith('Z-'):
                        schluessel = f"'{rid[2:]}':"
                    elif rid.startswith(('F-', 'B-')):
                        schluessel = f"'{rid[2:]}':"
                    elif rid != 'A-ABLAUF':
                        schluessel = f"'{rid}':"
                    if schluessel not in gw_text:
                        fehler.append(f'{fid}: Gateway-Kennung {datei} nicht im Code gefunden')
                continue
            pfad = REPO / datei
            if not pfad.is_file():
                fehler.append(f'{fid}: Datei fehlt im Repo: {datei}')
                continue
            if adapter == 'logbuch':
                m = re.match(r'Zeile (\S+ \S+) (\S+)$', abschnitt)
                if not m:
                    fehler.append(f'{fid}: Logbuch-Stelle hat nicht die Form "Zeile <Datum> <Uhrzeit> <Art>": {abschnitt}')
                    continue
                n = logbuch_text.count(f'| {m.group(1)} | {m.group(2)} |')
                if n != 1:
                    fehler.append(f'{fid}: Logbuch-Stelle trifft {n} Zeilen statt genau einer: {abschnitt}')
            elif adapter == 'markdown':
                if datei not in ueberschriften:
                    ueberschriften[datei] = _ueberschriften(pfad)
                for glied in abschnitt.split(' > '):
                    if not any(glied in u for u in ueberschriften[datei]):
                        fehler.append(f'{fid}: Überschrift „{glied}“ nicht in {datei}')
            # kennzeichnende Wörter der Stelle bei anderen Worten
            if f.get('art') in ('umschrieben', 'fachbegriff'):
                stelle = abschnitt.split(' > ')[-1]
                kenn = _woerter(stelle) - _ALLGEMEIN
                treffer = kenn & _woerter(frage)
                if treffer:
                    fehler.append(f'{fid}: {f["art"]} benutzt kennzeichnende Wörter der Stelle: {sorted(treffer)}')
        if f.get('art') in ('umschrieben', 'fachbegriff'):
            for qu in quellen:
                if qu.get('datei', '').startswith(KENNUNG):
                    stelle = qu.get('abschnitt', '').split(' > ')[-1]
                    kenn = _woerter(stelle) - _ALLGEMEIN - {w for w in _woerter(stelle) if '<' in stelle and w in _woerter(stelle.split('<')[0])}
                    treffer = kenn & _woerter(frage)
                    if treffer:
                        fehler.append(f'{fid}: {f["art"]} benutzt kennzeichnende Wörter der Stelle: {sorted(treffer)}')

    sha = hashlib.sha256(SATZ.read_bytes()).hexdigest()
    print(f'Fragen: {len(fragen)}  je Art: {dict(sorted(arten.items()))}')
    print(f'je Gruppe (beantwortbar): {dict(sorted(gruppen_b.items()))}  Liste/Tabelle: {liste}')
    for z in fehler:
        print('FEHLER', z)
    print(f'result {"ok" if not fehler else "fail"} ({len(fehler)} Befunde)')
    print(f'sha256 {sha}  {SATZ.relative_to(REPO).as_posix()}')
    return 0 if not fehler else 1


if __name__ == '__main__':
    sys.exit(main())
