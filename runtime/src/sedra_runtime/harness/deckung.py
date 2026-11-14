"""Die eine Deckungsfunktion der Harness-Freigabe (Spec Freigaben S4, FS-10; harter Vorbehalt FS-35).

Sie beantwortet nur die Frage: Deckt eine **vorhandene** Erlaubnis diesen Aufruf, sodass keine Karte nötig ist? Die Reihenfolge ist
dieselbe wie vor S4.2 (Test `test_harness_deckung_vergleich`: Wahrheitstabelle alt gegen neu, ohne Abweichung):

1. Stufe `frei` (Katalog): nichts wird verbraucht, keine Erlaubnis gebraucht.
2. Vorbehalt oder Warnkarte: keine Erlaubnis deckt, nie (Vorbehalt und Warnkarte bleiben beim Captain).
3. Aufgabe (nur lokale Modelle, HS-27): trifft eine aktive Aufgabe und lässt sich der Aufruf zählen, gilt sie; ein weicher Vorbehalt
   (Plan oder Werkzeug) gilt als Zusatz der Aufgabe.
4. Sitzungs-Erlaubnis: nur mit einem lokalen Modell (S4.3, E5), nur ohne weichen Vorbehalt und nur, wenn keine Aufgabe schon gedeckt hat.
5. Sonst: Karte.

Rein: keine Dateien, kein eigener Zustand. Die Ablagen (Aufgaben, Sitzungs-Erlaubnisse) werden über die übergebenen Funktionen gelesen;
`aufgabe_zaehlen` wird nur nach einem Treffer und genau einmal aufgerufen (es verbraucht den Zähler)."""
from __future__ import annotations


def deckt(*, wirkt_als, vorbehalt, warnkarte, aufgaben_aktiv, weich_werkzeug, weich_plan, aufgabe_treffer, aufgabe_zaehlen, sitzung_treffer, lokal=True):
    """{'via_aufgabe': aufgabe_id|None, 'via_sitzung': karte_id|None}. Alle Wirkungen kommen über die übergebenen Funktionen.

    `aufgaben_aktiv`: gibt es Aufgaben und ein lokales Modell (HS-27)? `weich_werkzeug()`: weicher Vorbehalt des Werkzeugs (oder None);
    `weich_plan`: weicher Vorbehalt aus dem Plan. `aufgabe_treffer(weich)`: Treffer-Datensatz mit `aufgabe_id` oder None;
    `aufgabe_zaehlen(aufgabe_id)`: bool; `sitzung_treffer()`: Datensatz mit `karte_id` oder None."""
    ergebnis = {'via_aufgabe': None, 'via_sitzung': None}
    if wirkt_als == 'frei' or vorbehalt or warnkarte:
        return ergebnis
    if aufgaben_aktiv:
        weich = weich_werkzeug() or weich_plan
        treffer = aufgabe_treffer(weich)
        if treffer and aufgabe_zaehlen(treffer['aufgabe_id']):
            ergebnis['via_aufgabe'] = treffer['aufgabe_id']
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
