"""Die eine Deckungsfunktion der Harness-Freigabe (Spec Freigaben S4, FS-10; harter Vorbehalt FS-35).

Sie beantwortet nur die Frage: Deckt eine **vorhandene** Erlaubnis diesen Aufruf, sodass keine Karte nötig ist? Die Reihenfolge ist
dieselbe wie vor S4.2 (Test `test_harness_deckung_vergleich`: Wahrheitstabelle alt gegen neu, ohne Abweichung):

1. Stufe `frei` (Katalog): nichts wird verbraucht, keine Erlaubnis gebraucht.
2. Vorbehalt oder Warnkarte: keine Erlaubnis deckt, nie (Vorbehalt und Warnkarte bleiben beim Captain).
3. Aufgabe (nur lokale Modelle, HS-27): trifft eine aktive Aufgabe und lässt sich der Aufruf zählen, gilt sie; ein weicher Vorbehalt
   (Plan oder Werkzeug) gilt als Zusatz der Aufgabe.
3b. Master-Modus (nur wenn die Sitzung ihn an hat; siehe master.py): deckt nie bei weichem Vorbehalt der Oberfläche.
4. Sitzungs-Erlaubnis: nur mit einem lokalen Modell (S4.3, E5), nur ohne weichen Vorbehalt und nur, wenn keine Aufgabe schon gedeckt hat.
5. Sonst: Karte.

Rein: keine Dateien, kein eigener Zustand. Die Ablagen (Aufgaben, Sitzungs-Erlaubnisse) werden über die übergebenen Funktionen gelesen;
`aufgabe_zaehlen` wird nur nach einem Treffer und genau einmal aufgerufen (es verbraucht den Zähler)."""
from __future__ import annotations


def deckt(*, wirkt_als, vorbehalt, warnkarte, aufgaben_aktiv, weich_werkzeug, weich_plan, aufgabe_treffer, aufgabe_zaehlen, sitzung_treffer, lokal=True,
          master_treffer=None):
    """{'via_aufgabe': aufgabe_id|None, 'via_sitzung': karte_id|None} – mit `master_treffer` zusätzlich `via_master`. Alle Wirkungen kommen über die übergebenen Funktionen.

    `aufgaben_aktiv`: gibt es Aufgaben und ein lokales Modell (HS-27)? `weich_werkzeug()`: weicher Vorbehalt des Werkzeugs (oder None);
    `weich_plan`: weicher Vorbehalt aus dem Plan. `aufgabe_treffer(weich)`: Treffer-Datensatz mit `aufgabe_id` oder None;
    `aufgabe_zaehlen(aufgabe_id)`: bool; `sitzung_treffer()`: Datensatz mit `karte_id` oder None.
    Master-Modus (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md MM-12, Quelle 3b): `master_treffer()` liefert einen Datensatz mit `sitzung_id` oder None; er wird nur gefragt,
    wenn keine Aufgabe gedeckt hat, das Modell lokal ist und kein weicher Vorbehalt der Oberfläche vorliegt (ein weicher Vorbehalt „Modell“ deckt er). Ohne `master_treffer`
    ist alles wie vor dem Master-Modus (Vergleichstest) und das Ergebnis hat keinen Schlüssel `via_master`."""
    ergebnis = {'via_aufgabe': None, 'via_sitzung': None}
    if master_treffer is not None:
        ergebnis['via_master'] = None
    if wirkt_als == 'frei' or vorbehalt or warnkarte:
        return ergebnis
    if aufgaben_aktiv:
        weich = weich_werkzeug() or weich_plan
        treffer = aufgabe_treffer(weich)
        if treffer and aufgabe_zaehlen(treffer['aufgabe_id']):
            ergebnis['via_aufgabe'] = treffer['aufgabe_id']
    if master_treffer is not None and lokal and not ergebnis['via_aufgabe']:
        weich = weich_werkzeug() or weich_plan
        if not (isinstance(weich, dict) and weich.get('oberflaeche')):
            treffer = master_treffer()
            if treffer:
                ergebnis['via_master'] = treffer['sitzung_id']
                return ergebnis
    if lokal and not ergebnis['via_aufgabe'] and not weich_werkzeug():      # S4.3 FS-13 (E5 = nein): mit einem Cloud-Modell deckt keine Sitzungs-Erlaubnis
        treffer = sitzung_treffer()
        if treffer:
            ergebnis['via_sitzung'] = treffer['karte_id']
    return ergebnis



AKTIONEN = ('erteilt', 'zurueckgenommen', 'abgelaufen', 'erschoepft', 'gedeckelt')
DAUERN = ('einmal', 'sitzung', 'befristet', 'immer')
AUFGABE_EREIGNISSE = {'HARNESS_AUFGABE_ANGELEGT': 'erteilt', 'HARNESS_AUFGABE_ZURUECKGENOMMEN': 'zurueckgenommen',
                      'HARNESS_AUFGABE_ABGELAUFEN': 'abgelaufen', 'HARNESS_AUFGABE_ERSCHOEPFT': 'erschoepft'}


def ereignis(aktion, erlaubnis_id, dauer, herkunft, kanal):
    """Payload des einen Audit-Ereignisses `HARNESS_ERLAUBNIS` (FS-31) – zusätzlich zu den alten Ereignissen, die ein Jahr bleiben.
    Eine unbekannte Aktion oder Dauer ist ein Fehler (kein stilles Schlucken im Audit)."""
    if aktion not in AKTIONEN:
        raise ValueError(f'erlaubnis_aktion_unbekannt: {aktion}')
    if dauer not in DAUERN:
        raise ValueError(f'erlaubnis_dauer_unbekannt: {dauer}')
    return {'aktion': aktion, 'id': str(erlaubnis_id), 'dauer': dauer, 'herkunft': str(herkunft), 'kanal': str(kanal)}


DECKEL_FEST = 2      # S4.5 FS-42 (E2 = Wert 2): fest im Code; eine Einstellung darf ihn nur enger stellen


def deckel_wert(einstellung=None):
    """Der geltende Deckel: ohne Einstellung der feste Wert; eine engere Einstellung (1 oder 2) gilt, eine weitere wird abgelehnt (FS-42)."""
    if einstellung is None:
        return DECKEL_FEST
    if isinstance(einstellung, bool) or not isinstance(einstellung, int) or einstellung < 1:
        raise ValueError(f'deckel_ungueltig: {einstellung!r}')
    if einstellung > DECKEL_FEST:
        raise ValueError(f'deckel_zu_weit: {einstellung} (hoechstens {DECKEL_FEST})')
    return einstellung


class Wiederholung:
    """S4.5 (FS-40/41): Wie oft hat eine Erlaubnis **denselben Aufruf** schon gedeckt, ohne dass dazwischen etwas geschrieben wurde?
    Derselbe Aufruf = gleiche Bindung (Werkzeug, Ziel, Hash der Argumente). Ein Schreiben (`schreibe()`) beginnt eine neue Runde: ein Testlauf nach
    einer Korrektur am Code zählt nicht als Wiederholung. Ist der Deckel erreicht, geht der nächste gleiche Aufruf als Karte an den Captain; die
    Erlaubnis selbst bleibt bestehen. Rein im Speicher, je Kiste (also je Zug der Sitzung)."""

    def __init__(self, deckel=DECKEL_FEST):
        self.deckel = deckel_wert(deckel)
        self._runde = 0
        self._stand = {}

    @staticmethod
    def schluessel(werkzeug, ziel, args):
        import hashlib
        import json
        roh = json.dumps([werkzeug, str(ziel), args], ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(roh.encode('utf-8')).hexdigest()

    def _anzahl(self, schluessel):
        runde, n = self._stand.get(schluessel, (self._runde, 0))
        return n if runde == self._runde else 0

    def erreicht(self, schluessel):
        return self._anzahl(schluessel) >= self.deckel

    def zaehlen(self, schluessel):
        self._stand[schluessel] = (self._runde, self._anzahl(schluessel) + 1)

    def schreibe(self):
        self._runde += 1
