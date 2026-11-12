"""Betrieb im Unternehmen (SPEC_APPS_v1_AM7_UNTERNEHMEN, Betriebsart A): Anzeige, Nachweis-Export (AM7-13) und die Seite „Was SEDRA mit deinen Eingaben tut“ (AM7-14).

Nur lesen. Der Export enthält keine Inhalte – das Audit hat keine, die Vorgänge werden nur mit Klasse, Weg, Zweck und verantwortlicher Person gelistet. Die Seite für Beschäftigte sagt nur,
was aus Richtlinie, Anbieterliste und Aufbewahrung folgt, und verspricht nichts darüber hinaus. Rechtliche Begriffe sind Einordnung, keine Rechtsprüfung (AM7 §4)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

AUDIT_MAX = 2000
ENTWUERFE_STUNDEN_VORGABE = 24                 # gateway/vorgang.py STANDARD_VORGABEN


def _audit(hub):
    pfad = hub.runtime.audit.path
    kette = hub.runtime.audit.verify_chain()
    zeilen = []
    try:
        zeilen = [z for z in pfad.read_text(encoding='utf-8').splitlines() if z.strip()]
    except OSError:
        pass
    eintraege = []
    for z in zeilen[-AUDIT_MAX:]:
        try:
            e = json.loads(z)
        except ValueError:
            continue
        p = e.get('payload') or {}
        eintraege.append({'id': e.get('event_id'), 'zeit': e.get('timestamp'), 'art': e.get('event_type'), 'person': p.get('person'), 'rolle': p.get('rolle')})
    return {'kette_ok': kette, 'anzahl': len(zeilen), 'gezeigt': len(eintraege), 'eintraege': eintraege}


def _vorgaenge(hub):
    erg = []
    try:
        for kopf in hub.gw.liste():
            v = hub.gw.get(kopf['id'])
            erg.append({'id': v.id, 'zustand': v.zustand, 'klasse': kopf.get('klasse'), 'weg': v.weg, 'zweck': v.zweck, 'verantwortlich': v.verantwortlich})
    except Exception as exc:
        return [{'fehler': f'{type(exc).__name__}: {exc}'[:200]}]
    return erg


def _empfaenger(project_root):
    """AM5-08 (noch nicht gebaut): bis dahin die Anbieter aus `cloud_providers.yaml` – Name, ob an, Adresse ohne Schlüssel."""
    try:
        d = yaml.safe_load((Path(__file__).resolve().parents[3] / 'config' / 'cloud_providers.yaml').read_text(encoding='utf-8'))['cloud_providers']
        return [{'anbieter': n, 'an': bool(d.get('enabled')) and bool((m or {}).get('enabled')), 'adresse': (m or {}).get('base_url')} for n, m in sorted((d.get('providers') or {}).items())]
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        return []


def ansicht(hub):
    """GET betrieb: der Zustand der Richtlinie (nichts Geheimes)."""
    rl = hub.richtlinie
    return {'schalter': bool(hub.betrieb_an), 'richtlinie': rl.beschreibung(), 'rolle': rl.rolle, 'person': rl.person, 'grundfunktionen': rl.grundfunktionen()}


def export(hub):
    """AM7-13: der Nachweis für die Prüfung – JSON und eine lesbare Fassung, ohne Inhalte."""
    from . import verzeichnis
    v = verzeichnis.verzeichnis(hub)
    daten = {'erstellt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'betrieb': ansicht(hub), 'audit': _audit(hub), 'apps': hub.apps_verzeichnis()['apps'],
             'erweiterungen': {'arten': v['arten'], 'eintraege': [{k: e[k] for k in ('art', 'id', 'herkunft', 'vertrauen', 'version', 'zustand')} for e in v['eintraege']]},
             'empfaenger': _empfaenger(hub.project_root), 'vorgaenge': _vorgaenge(hub)}
    return {'json': daten, 'text': lesbar(daten)}


def lesbar(d):
    z = ['Nachweis für die Prüfung · ' + d['erstellt'], '']
    b = d['betrieb']['richtlinie']
    z.append('Richtlinie: ' + (f"aktiv · Rolle {b.get('rolle')} · Person {b.get('person')} · Hash {str(b.get('hash'))[:16]}" if b.get('aktiv') else 'nicht aktiv' + (f" ({', '.join(b.get('fehler') or [])})" if b.get('fehler') else '')))
    a = d['audit']
    z.append(f"Audit: Kette {'in Ordnung' if a['kette_ok'] else 'GEBROCHEN'} · {a['anzahl']} Einträge (die letzten {a['gezeigt']} im JSON), ohne Inhalte")
    z.append(f"Apps mit Gewährung: {len(d['apps'])}")
    for x in d['apps']:
        z.append(f"  - {x['id']} · {'aktiv' if x['aktiv'] else 'nicht aktiv'} · gewährt: {', '.join(x['gewaehrt']) or 'nichts'}")
    z.append('Erweiterungen: ' + ', '.join(f'{k} {n}' for k, n in d['erweiterungen']['arten'].items() if n))
    z.append('Empfänger (Cloud-Anbieter): ' + (', '.join(f"{e['anbieter']} ({'an' if e['an'] else 'aus'})" for e in d['empfaenger']) or 'keine'))
    z.append(f"Vorgänge: {len(d['vorgaenge'])}")
    for v in d['vorgaenge'][:50]:
        z.append('  - ' + ' · '.join(f'{k} {v[k]}' for k in ('id', 'zustand', 'klasse', 'weg', 'zweck', 'verantwortlich') if k in v and v[k] is not None) if 'fehler' not in v else '  - ' + v['fehler'])
    return '\n'.join(z)


def eingaben_text(hub):
    """AM7-14: „Was SEDRA mit deinen Eingaben tut“ für Beschäftigte, nur aus dem, was feststeht. Rückgabe: {titel, absaetze: [str]}."""
    rl = hub.richtlinie
    anbieter = _empfaenger(hub.project_root)
    an = [e['anbieter'] for e in anbieter if e['an'] and rl.anbieter_erlaubt(e['anbieter'])]
    auf = (rl.daten or {}).get('aufbewahrung', {}) if rl.aktiv else {}
    ent_h = auf.get('entwuerfe_stunden', ENTWUERFE_STUNDEN_VORGABE)
    absaetze = [
        'SEDRA läuft auf diesem Rechner. Was du eingibst, wird hier verarbeitet; der Server hört nur auf diesem Rechner (Loopback).',
        ('Eine Cloud-KI wird nur genutzt, wenn der Cloud-Weg für den Anbieter eingeschaltet ist und der Inhaltsschutz den Aufruf zulässt. Zurzeit eingeschaltet: '
         + (', '.join(an) if an else 'kein Anbieter') + '. Personenbezug und besondere Daten bleiben nach dem Regelwerk des Inhaltsschutzes lokal; jeder Cloud-Aufruf steht im Audit (ohne Inhalt).'),
        f'Entwürfe im GateWay werden nach {ent_h} Stunden gelöscht.' + (f" Gesprächsverläufe, die länger als {auf['gespraeche_tage']} Tage nicht berührt wurden, werden aus der Liste genommen und nach geloescht/ auf diesem Rechner verschoben; dort bleiben sie liegen, bis der Betreiber den Ordner leert." if 'gespraeche_tage' in auf else ' Für Gesprächsverläufe nennt die Richtlinie keine Frist.'),
        'Das Audit-Protokoll hält fest, dass etwas geschah (Art, Zeit' + (', Person und Rolle' if rl.aktiv else '') + '), aber nie, was du geschrieben hast.',
        ('Diese Installation gehört zu: ' + (f'{rl.person}, Rolle {rl.rolle}.' if rl.aktiv else 'keiner Richtlinie des Betreibers (Einzelplatzbetrieb).')),
        'Das ist eine Information aus der Konfiguration dieser Installation, keine Rechtsauskunft.',
    ]
    return {'titel': 'Was SEDRA mit deinen Eingaben tut', 'absaetze': absaetze}
