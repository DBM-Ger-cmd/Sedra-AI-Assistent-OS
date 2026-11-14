"""W4-Werkzeuge `rueckblick_schreiben` und `vorschlaege_pflegen` (Spec W4, 14.11.2026).

Eigene Datei, unter 400 Zeilen. `werkzeuge.py` ruft nur die beiden Zweige
(`vorbereiten` / `ausfuehren`) und fügt Schemas, NAMEN und WIRKUNGSKLASSE hinzu.
Beide Werkzeuge legen nur einen Antrag im Posteingang des Captains an: Karte,
Vorschau und Gate entstehen in `vorbereiten`; `ausfuehren` hat `wirkung: False`
und ändert keine Datei. `docs/AAR/LESSONS.md` entsteht erst bei der ersten
freigegebenen Anwendung – weder hier noch vorher (F-024).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .werkzeuge import WerkzeugFehler

GATE_RUECKBLICK = 'rueckblick_antrag'
GATE_VORSCHLAG = 'vorschlag_antrag'

TEILPFLICHT_RUECKBLICK = ('titel', 'was_gelaufen_ist')
TEILPFLICHT_VORSCHLAG = ('titel', 'aktion')
AKTIONEN = ('anlegen', 'aendern', 'status_setzen')
STATUSES = ('offen', 'geprüft', 'umgesetzt', 'abgelehnt')
QUELLEN = ('rueckblick', 'chat', 'test')
PRIORITAETEN = ('niedrig', 'mittel', 'hoch')
DOKUMENT_ZIEL_DEFAULT = 'docs/AAR/LESSONS.md'


def _jetzt():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _pflicht(args, key):
    v = args.get(key)
    if not isinstance(v, str) or not v.strip():
        raise WerkzeugFehler(f'argument_fehlt: {key}')
    return v.strip()


class WerkzeugLernen:
    def __init__(self, werkzeuge):
        self.w = werkzeuge  # Werkzeuge-Instanz (W3-Muster: eigene Datei pro Werkzeugpaar)

    # ---- Vorbereiten: Ziel, Vorschau, Gate – ohne Wirkung
    def vorbereiten(self, name, args):
        if name == 'rueckblick_schreiben':
            return self._vorbereiten_rueckblick(args if isinstance(args, dict) else {})
        if name == 'vorschlaege_pflegen':
            return self._vorbereiten_vorschlag(args if isinstance(args, dict) else {})
        raise WerkzeugFehler(f'werkzeug_unbekannt: {name}')

    def _vorbereiten_rueckblick(self, args):
        titel = _pflicht(args, 'titel')
        was_gelaufen_ist = _pflicht(args, 'was_gelaufen_ist')
        sitzung_id = str(args.get('sitzung_id') or '').strip()
        was_schief_lief = str(args.get('was_schief_lief') or '').strip()
        massnahmen = args.get('massnahmen')
        if not isinstance(massnahmen, list):
            massnahmen = []
        dokument_ziel = str(args.get('dokument_ziel') or DOKUMENT_ZIEL_DEFAULT).strip() or DOKUMENT_ZIEL_DEFAULT
        ziel = 'rueckblick/' + (sitzung_id or titel[:40])
        antrag = {
            'werkzeug': 'rueckblick_schreiben',
            'ziel': ziel,
            'dokument': dokument_ziel,
            'titel': titel,
            'sitzung_id': sitzung_id,
            'datum': _jetzt(),
            'was_gelaufen_ist': was_gelaufen_ist,
            'was_schief_lief': was_schief_lief,
            'massnahmen': massnahmen,
            'status': 'offen',
        }
        return {
            'ziel': ziel,
            'vorhanden': True,
            'vorschau': (
                f'Rückblick: {titel}\n'
                f'Sitzung: {sitzung_id or "(keine)"}\n'
                f'Was lief gut: {was_gelaufen_ist[:200]}\n'
                f'Was schief lief: {was_schief_lief[:200] or "(keine Angabe)"}\n'
                f'Maßnahmen: {len(massnahmen)}\n'
                f'Dokument: {dokument_ziel}'
            ),
            'kurz': ziel,
            'antrag': antrag,
            'gate': {
                'aktion': GATE_RUECKBLICK,
                'ziel': ziel,
                'bindung': {'werkzeug': 'rueckblick_schreiben', 'ziel': ziel, 'antrag': antrag},
            },
        }

    def _vorbereiten_vorschlag(self, args):
        titel = _pflicht(args, 'titel')
        aktion = str(args.get('aktion') or '').strip()
        if aktion not in AKTIONEN:
            raise WerkzeugFehler('argument_fehlt: aktion (anlegen, aendern oder status_setzen)')
        beschreibung = str(args.get('beschreibung') or '').strip()
        quelle = str(args.get('quelle') or 'chat').strip()
        if quelle not in QUELLEN:
            quelle = 'chat'
        status = str(args.get('status') or 'offen').strip()
        if status not in STATUSES:
            status = 'offen'
        prioritaet = str(args.get('prioritaet') or 'mittel').strip()
        if prioritaet not in PRIORITAETEN:
            prioritaet = 'mittel'
        ziel = 'vorschlag/' + titel[:40]
        antrag = {
            'werkzeug': 'vorschlaege_pflegen',
            'ziel': ziel,
            'aktion': aktion,
            'titel': titel,
            'beschreibung': beschreibung,
            'quelle': quelle,
            'status': status,
            'prioritaet': prioritaet,
            'captain_zustimmung': False,
        }
        return {
            'ziel': ziel,
            'vorhanden': True,
            'vorschau': (
                f'Vorschlag: {titel} ({aktion})\n'
                f'Quelle: {quelle} · Status: {status} · Priorität: {prioritaet}\n'
                f'{beschreibung[:200] or "(keine Beschreibung)"}'
            ),
            'kurz': ziel,
            'antrag': antrag,
            'gate': {
                'aktion': GATE_VORSCHLAG,
                'ziel': ziel,
                'bindung': {'werkzeug': 'vorschlaege_pflegen', 'ziel': ziel, 'antrag': antrag},
            },
        }

    # ---- Ausführen: echter Antrag im Posteingang, keine direkte Wirkung
    def ausfuehren(self, name, args, *, token=None, plan=None):
        plan = plan or self.vorbereiten(name, args)
        antrag = plan['antrag']
        if name == 'rueckblick_schreiben':
            anlegen = getattr(self.w, 'rueckblick_antrag', None)
            if not callable(anlegen):
                return {'status': 'fehler', 'ergebnis': 'error: Rueckblick-Anträge werden in dieser Sitzung nicht angeboten', 'wirkung': False}
            try:
                anlegen(antrag)
            except ValueError as exc:
                return {'status': 'fehler', 'ergebnis': f'error: {exc}', 'wirkung': False}
            return {
                'status': 'ok',
                'ergebnis': (
                    f'Antrag „{antrag["titel"]}“ (Rückblick) liegt im Posteingang des Captains. '
                    f'Keine direkte Wirkung: wird erst nach Freigabe in {antrag["dokument"]} eingetragen.'
                ),
                'wirkung': False,
            }
        if name == 'vorschlaege_pflegen':
            anlegen = getattr(self.w, 'vorschlag_antrag', None)
            if not callable(anlegen):
                return {'status': 'fehler', 'ergebnis': 'error: Vorschlag-Anträge werden in dieser Sitzung nicht angeboten', 'wirkung': False}
            try:
                anlegen(antrag)
            except ValueError as exc:
                return {'status': 'fehler', 'ergebnis': f'error: {exc}', 'wirkung': False}
            return {
                'status': 'ok',
                'ergebnis': (
                    f'Antrag „{antrag["titel"]}“ ({antrag["aktion"]}) liegt im Posteingang des Captains. '
                    'Keine direkte Wirkung: wird erst nach Freigabe umgesetzt.'
                ),
                'wirkung': False,
            }
        raise WerkzeugFehler(f'werkzeug_unbekannt: {name}')
