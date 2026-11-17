"""Vorprüfer: sagt VOR dem Start, was der Inhaltsschutz mit diesem Text tun würde – und blockt selbst nie.

Der Inhaltsschutz (core/content_guard) bleibt die einzige harte Stelle. Der Vorprüfer ist beratend: er ruft kein Modell, speichert
nichts, schreibt keinen Text ins Ergebnis (nur Fundarten und Anzahlen) und liefert eine Empfehlung in Klartext. Jede Oberfläche
(Workflow Studio, Chat-Anhänge, Startassistent) zeigt das Ergebnis als Hinweis; der Captain entscheidet.

    vorpruefen(text, route='cloud', modell='nvidia/…') -> {'stufe': 'ok' | 'hinweis' | 'warnung', ...}

Stufen: ok = würde durchgehen; hinweis = geht durch, aber mit Notiz oder Entscheidung; warnung = würde angehalten.
"""
from __future__ import annotations

from collections import Counter

from .b6core.normalize import normalize
from .content_policy import BLOCK, PSEUDO, REVIEW, SegmentScan, TRUST_LEVELS, ScanFailure, effective, evaluate, reason_text, scan_content

VORPRUEF_MAX = 200_000
_ROUTEN = ('local', 'cloud')


def _fundart(rule_id):
    from ..gateway.probe import label_of      # eine Quelle für die Namen der Funde
    return label_of(rule_id)


def vorpruefen(text, route='local', modell='', vertrauen='untrusted', datenschutz_eu=True):
    """Ergebnis ohne Text. Wirft nie; ein Prüffehler wird zur Warnung 'Vorprüfung nicht möglich' (der Guard entscheidet später)."""
    ergebnis = {'stufe': 'ok', 'route': route, 'modell': str(modell or ''), 'kurz': 'Keine Auffälligkeiten.',
                'funde': [], 'gruende': [], 'empfehlung': '', 'blockt_spaeter': False, 'beratend': True,
                'datenschutz_eu': bool(datenschutz_eu)}
    if route not in _ROUTEN or vertrauen not in TRUST_LEVELS:
        return _unklar(ergebnis, 'Route oder Herkunft unbekannt.')
    if not isinstance(text, str) or not text.strip():
        ergebnis['kurz'] = 'Kein Text zum Prüfen.'
        return ergebnis
    if len(text) > VORPRUEF_MAX:
        return _unklar(ergebnis, 'Text größer als die Vorprüfung (%d Zeichen).' % VORPRUEF_MAX)
    try:
        sauber = normalize(text).clean
        treffer = scan_content(sauber)
    except ScanFailure:
        return _unklar(ergebnis, 'Die Prüfung ist nicht vollständig gelaufen.')
    except Exception:                                   # beratend: nie den Start der Oberfläche stören
        return _unklar(ergebnis, 'Die Prüfung ist fehlgeschlagen.')
    urteil = evaluate([SegmentScan(0, 'user', vertrauen, '', len(sauber), treffer)], route, ergebnis['modell'] or 'vorpruefung', True)
    ausgang, scharf, beobachtet = effective(urteil, lambda g: True, bool(datenschutz_eu))   # Modus Datenschutz EU aus: nur beobachtet
    zaehler = Counter(_fundart(h.rule_id) for h in treffer)
    ergebnis['funde'] = [{'art': a, 'anzahl': n} for a, n in sorted(zaehler.items())]
    ergebnis['gruende'] = [{'code': c, 'text': reason_text(c)} for c in scharf]
    ergebnis['beobachtet'] = [{'code': c, 'text': reason_text(c)} for c in beobachtet]
    if ausgang == BLOCK:
        ergebnis['stufe'] = 'warnung'
        ergebnis['blockt_spaeter'] = True
    elif ausgang in (REVIEW, PSEUDO) or beobachtet or (route == 'cloud' and urteil.notes):   # lokal bleibt reine Notiz still
        ergebnis['stufe'] = 'hinweis'
    ergebnis['kurz'] = _kurz(ergebnis, ausgang)
    ergebnis['empfehlung'] = _empfehlung(ergebnis, urteil)
    if beobachtet and not scharf:
        ergebnis['empfehlung'] = 'Modus Datenschutz EU ist aus: Personenbezug geht in die Cloud und wird nur im Logbuch gezählt.'
    return ergebnis


def _unklar(ergebnis, grund):
    ergebnis.update(stufe='hinweis', kurz='Vorprüfung nicht möglich: ' + grund,
                    empfehlung='Du kannst trotzdem starten; der Inhaltsschutz prüft beim Senden erneut.')
    return ergebnis


def _kurz(erg, ausgang):
    arten = ', '.join('%s (%d)' % (f['art'], f['anzahl']) for f in erg['funde'])
    if erg['stufe'] == 'warnung':
        return 'Würde angehalten – gefunden: %s.' % (arten or 'siehe Gründe')
    if erg['stufe'] == 'hinweis':
        return 'Geht durch, mit Hinweis – gefunden: %s.' % (arten or 'siehe Gründe')
    return 'Keine Auffälligkeiten.'


def _empfehlung(erg, urteil):
    if erg['stufe'] == 'ok':
        return ''
    codes = {g['code'] for g in erg['gruende']}
    if erg['route'] == 'cloud' and codes & {'SG_PERSONAL_CLOUD', 'SG_SENSITIVE_CLOUD', 'SG_SECRET_CLOUD', 'SG_KEY_FORMAT'}:
        return ('Mit einem lokalen Modell läuft das ohne Sperre – die Daten bleiben auf dem Rechner. '
                'Oder nur den Teil ohne Personenbezug an die Cloud geben.')
    if erg['stufe'] == 'warnung':
        return 'Inhalt prüfen oder ändern, dann starten. Der Inhaltsschutz hält den Aufruf sonst an.'
    return 'Ansehen und bewusst entscheiden; der Start ist nicht gesperrt.'
