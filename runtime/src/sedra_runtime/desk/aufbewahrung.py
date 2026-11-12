"""Aufbewahrung im Unternehmen (SPEC_APPS_v1_AM7_UNTERNEHMEN AM7-18): was die Richtlinie des Betreibers unter `aufbewahrung` nennt, wird höchstens einmal je 24 Stunden umgesetzt und ohne Inhalt protokolliert.

- Entwürfe des GateWay: die Frist `entwuerfe_stunden` gilt als Obergrenze schon beim Anlegen (`GateWay.entwuerfe_max_stunden`); der Lauf räumt abgelaufene Entwürfe weg (`GateWay.aufraeumen`).
- Gesprächsverläufe: Sitzungen der Harness, deren letzte Änderung länger als `gespraeche_tage` zurückliegt, werden nach `geloescht/` verschoben – dieselbe Regel wie beim Löschen in der Oberfläche
  („nichts wird endgültig gelöscht“, Regel des Captains). Eine laufende Antwort hält die Sitzung zurück. Endgültiges Löschen der Dateien in `geloescht/` ist nicht Teil dieses Laufs.
- Ablagen der Apps: nicht gebaut.

Es gibt keinen Hintergrunddienst: der Lauf kommt beim Start und bei jedem Blick auf den Betrieb (`GET /api/uix/betrieb`), sofern der letzte länger als 24 Stunden her ist. Der Zeitpunkt steht in
`local_config/aufbewahrung.json`. Ohne aktive Richtlinie tut der Lauf nichts. Das Audit nennt Zahlen und Fristen, nie Inhalte, Titel oder Namen."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

INTERVALL_S = 24 * 3600


def _pfad(project_root) -> Path:
    return Path(project_root) / 'local_config' / 'aufbewahrung.json'


def zuletzt(project_root):
    try:
        wert = json.loads(_pfad(project_root).read_text(encoding='utf-8')).get('zuletzt')
        return float(wert) if isinstance(wert, (int, float)) and not isinstance(wert, bool) else None
    except (OSError, ValueError, AttributeError):
        return None


def lauf(hub, jetzt=None, erzwingen=False):
    """Führt die Aufbewahrung aus, wenn eine Richtlinie aktiv ist und der letzte Lauf mehr als 24 Stunden her ist. Rückgabe: das Ergebnis (auch im Audit) oder None, wenn nichts zu tun war."""
    rl = hub.richtlinie
    if not (getattr(hub, 'betrieb_an', False) and rl.aktiv):
        return None
    jetzt = time.time() if jetzt is None else jetzt
    vorher = zuletzt(hub.project_root)
    if not erzwingen and vorher is not None and jetzt - vorher < INTERVALL_S:
        return None
    auf = (rl.daten or {}).get('aufbewahrung') or {}
    erg = {'entwuerfe_geloescht': 0, 'gespraeche_verschoben': 0, 'gespraeche_uebersprungen': 0,
           'entwuerfe_stunden': auf.get('entwuerfe_stunden'), 'gespraeche_tage': auf.get('gespraeche_tage')}
    try:
        erg['entwuerfe_geloescht'] = int(hub.gw.aufraeumen())
    except Exception:
        erg['entwuerfe_fehler'] = True
    tage = auf.get('gespraeche_tage')
    harness = getattr(hub, 'harness', None)
    if tage and harness is not None:
        grenze = jetzt - tage * 86400
        try:
            sitzungen = harness.sitzungen.liste()
        except Exception:
            sitzungen = []
            erg['gespraeche_fehler'] = True
        for z in sitzungen:
            try:
                t = datetime.fromisoformat(z['zuletzt']).timestamp()
            except (KeyError, TypeError, ValueError):
                continue
            if t >= grenze:
                continue
            try:
                harness.loeschen(z['id'])
                erg['gespraeche_verschoben'] += 1
            except Exception:
                erg['gespraeche_uebersprungen'] += 1
    try:
        pfad = _pfad(hub.project_root)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps({'zuletzt': jetzt}), encoding='utf-8')
    except OSError:
        erg['zeitpunkt_nicht_gespeichert'] = True
    hub.runtime.audit.append('AUFBEWAHRUNG_LAUF', component='desk', payload=dict(erg))
    return erg
