"""Info-Hub der Harness (Captain 05.11.2026: „es steht alles im Log – falls nicht, richten wir einen Info-Hub ein“): liest das Audit-Log und sagt in Klartext, welche Modelle
laufen (mit Fenster, Slots, Grafikspeicher), was zuletzt abgelehnt wurde und warum, und liefert die letzten Ereignisse gefiltert. Nur lesen: nichts wird geschrieben, nichts
freigegeben. Die Antwort ist reine Daten (Zahlen und Texte); die Oberfläche macht nie HTML daraus."""
from __future__ import annotations

import json
import re
from pathlib import Path

LESE_BYTES = 6_000_000                      # so viel vom Ende der Datei genügt für Stunden bis Tage; die Datei kann sehr groß werden
MAX_EREIGNISSE = 200
FEHLER_MARKEN = ('FAILED', 'DENIED', 'ERROR', 'REJECTED', 'EXITED', 'PROBLEM')
MODELL_EREIGNISSE = ('HARNESS_BELOHNUNG', 'LADEPROBE', 'MODEL_', 'SLOT_SERVER_', 'ROLE_RESOLVED', 'ROLE_RESOLUTION_FAILED', 'RESOURCE_', 'LLAMA_SERVER_')
FREIGABE_EREIGNISSE = ('HARNESS_FREIGABE', 'HARNESS_APPROVED_BY', 'CAPTAIN_GATE_', 'HARNESS_AUFGABE', 'HARNESS_ERLAUBNIS', 'HARNESS_KARTE')
ARTEN = ('alle', 'modelle', 'fehler', 'freigaben')

# Gründe der Ablehnung in Klartext (role_routing / resource_scheduler); unbekannte Gründe bleiben wörtlich stehen
GRUENDE = {
    'vram_insufficient': 'zu wenig Grafikspeicher für dieses Fenster',
    'ram_insufficient': 'zu wenig Arbeitsspeicher',
    'hardware_pressure': 'die Hardware ist zu stark belegt',
    'no_capability': 'kein Rezept für diese Rolle vorhanden',
}


def _lesen(pfad):
    """Die Zeilen vom Ende der Datei (höchstens LESE_BYTES); eine angeschnittene erste Zeile fällt weg."""
    p = Path(pfad)
    try:
        with p.open('rb') as f:
            f.seek(0, 2)
            groesse = f.tell()
            f.seek(max(0, groesse - LESE_BYTES))
            roh = f.read()
    except OSError as exc:
        raise ValueError('audit_nicht_lesbar:' + type(exc).__name__)
    zeilen = roh.decode('utf-8', errors='replace').splitlines()
    if groesse > LESE_BYTES and zeilen:
        zeilen = zeilen[1:]
    out = []
    for z in zeilen:
        try:
            e = json.loads(z)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def _gb(x):
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None


def _grund(code):
    return GRUENDE.get(str(code), str(code))


def klartext(e):
    """Ein Satz für ein Ereignis; bei unbekannten Arten der Typ mit dem kurzen Inhalt."""
    t, p = e.get('event_type') or '', e.get('payload') or {}
    if t == 'BOOT_STARTED':
        return 'Sedra gestartet'
    if t == 'HARNESS_BELOHNUNG':
        return '%s: Sitzung %s, Vorlage %s, Modell %s (Wort „%s“%s)' % ('Korrigierte Antwort' if p.get('urteil') == 'korrektur' else ('Besonders gute Antwort' if p.get('stufe') == 2 else 'Gute Antwort'),
                                                                           p.get('sitzung_id'), p.get('vorlage') or 'ohne', p.get('modell') or '?', p.get('ausloeser'), ', Code' if p.get('code') else '')
    if t in ('LADEPROBE', 'LADEPROBE_PROBLEM'):
        return str(p.get('satz') or t)
    if t == 'SLOT_SERVER_STARTED':
        return 'Modellserver gestartet: %s, %s Slots, je %s Token Fenster, %s GB Grafikspeicher' % (p.get('recipe'), p.get('slots'), p.get('context_per_slot'), _gb(p.get('vram_gb')))
    if t == 'SLOT_SERVER_STOPPED':
        return 'Modellserver beendet: %s (%s)' % (p.get('recipe'), p.get('reason'))
    if t == 'MODEL_LOADED':
        return 'Modell geladen: %s, Fenster %s' % (p.get('model'), p.get('context_length'))
    if t == 'MODEL_UNLOADED':
        return 'Modell entladen: %s' % (p.get('model'),)
    if t == 'MODEL_LOAD_FAILED':
        return 'Laden gescheitert: %s – %s' % (p.get('recipe_id'), p.get('detail'))
    if t == 'ROLE_RESOLVED':
        return 'Rolle %s bekommt %s' % (p.get('role'), p.get('capability_id'))
    if t == 'ROLE_RESOLUTION_FAILED':
        gruende = ', '.join('%s: %s' % (r.get('capability_id'), _grund(r.get('reason'))) for r in (p.get('rejected') or []) if isinstance(r, dict))
        return 'Rolle %s abgelehnt – %s' % (p.get('role'), gruende or _grund(p.get('code')))
    if t == 'RESOURCE_RESERVED':
        return 'Speicher reserviert für %s: %s GB Grafik, %s GB RAM' % (p.get('job_id'), _gb(p.get('vram_gb')), _gb(p.get('ram_gb')))
    if t == 'RESOURCE_RELEASED':
        return 'Speicher frei gegeben für %s' % (p.get('job_id'),)
    inhalt = json.dumps(p, ensure_ascii=False)
    return t + (' – ' + (inhalt if len(inhalt) <= 160 else inhalt[:159] + '…') if inhalt not in ('{}', 'null') else '')


def _art(t):
    if any(m in t for m in FEHLER_MARKEN):
        return 'fehler'
    if t.startswith(MODELL_EREIGNISSE):
        return 'modelle'
    if t.startswith(FREIGABE_EREIGNISSE):
        return 'freigaben'
    return 'sonst'


def _zeile(e):
    t = e.get('event_type') or ''
    return {'zeit': e.get('timestamp'), 'typ': t, 'art': _art(t), 'text': klartext(e), 'komponente': (e.get('source') or {}).get('component')}


def modelle(ereignisse):
    """Was läuft laut Log: Wiedergabe der Start- und Stopp-Ereignisse je Rezept, ein Neustart von Sedra leert die Liste; dazu die letzte Ablehnung je Rezept."""
    laeuft, abgelehnt = {}, {}
    for e in ereignisse:
        t, p = e.get('event_type'), e.get('payload') or {}
        if t == 'BOOT_STARTED':
            laeuft.clear()                                    # Sedra neu gestartet: Server von vorher laufen nicht mehr (sie lassen kein Stopp-Ereignis zurück)
        elif t == 'SLOT_SERVER_STARTED' and p.get('recipe'):
            laeuft[p['recipe']] = {'rezept': p['recipe'], 'seit': e.get('timestamp'), 'slots': p.get('slots'), 'fenster_je_slot': p.get('context_per_slot'),
                                   'vram_gb': _gb(p.get('vram_gb'))}
        elif t == 'SLOT_SERVER_STOPPED' and p.get('recipe'):
            laeuft.pop(p['recipe'], None)
        elif t == 'ROLE_RESOLUTION_FAILED':
            for r in p.get('rejected') or []:
                if isinstance(r, dict) and r.get('capability_id'):
                    abgelehnt[r['capability_id']] = {'rezept': r['capability_id'], 'zeit': e.get('timestamp'), 'grund': _grund(r.get('reason')), 'rolle': p.get('role')}
        elif t == 'ROLE_RESOLVED' and p.get('capability_id'):
            abgelehnt.pop(p['capability_id'], None)           # danach hat es geklappt: die alte Ablehnung zählt nicht mehr
    return {'laeuft': sorted(laeuft.values(), key=lambda x: x['seit'] or ''), 'abgelehnt': sorted(abgelehnt.values(), key=lambda x: x['zeit'] or '', reverse=True)[:10]}


def stand(pfad, limit=60, such='', art='alle'):
    """Der Stand für die Seite: Modelle, dann die letzten Ereignisse (neueste zuletzt) nach Art und Suchwörtern gefiltert."""
    ereignisse = _lesen(pfad)
    art = art if art in ARTEN else 'alle'
    limit = max(1, min(int(limit or 60), MAX_EREIGNISSE))
    worte = [w for w in (re.sub(r'[^a-z0-9]', '', x) for x in str(such or '').lower().split()) if w]
    zeilen = []
    for e in reversed(ereignisse):
        z = _zeile(e)
        if z['typ'] == 'SG_MODEL_CALL' and art == 'alle' and not worte:
            continue                                          # hunderte Modellaufrufe würden alles andere verdecken; mit Filter oder Suche sind sie da
        if art != 'alle' and z['art'] != art:
            continue
        if worte and not all(w in re.sub(r'[^a-z0-9]', '', (z['typ'] + z['text']).lower()) for w in worte):
            continue
        zeilen.append(z)
        if len(zeilen) >= limit:
            break
    return {'modelle': modelle(ereignisse), 'ereignisse': list(reversed(zeilen)), 'gelesen': len(ereignisse), 'art': art}
