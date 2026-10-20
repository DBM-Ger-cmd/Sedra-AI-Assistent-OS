# Prüfbericht: KI GateWay (KMU) mit den synthetischen Prüffällen

**Stand:** 20.10.2026 · **Prüfdokument:** SEDRA_20_synthetische_Prueffaelle_Bueroalltag_v1.0 (20 Fälle)
**Prüfweg:** Jede Texteingabe läuft durch dieselbe Pipeline wie im GateWay: Vorgang anlegen → Datenschutz prüfen (Einstufung und
Pseudonymisierung). Ohne Modellaufruf. Die Oberfläche (Shell `gateway-kmu`) wurde in diesem Lauf nicht geklickt.
**Ergebnisdatei:** `scratchpad/gateway_ergebnisse.json` (volle Ausgaben je Fall).

## Ergebnis

| Ergebnis | Fälle |
|---|---|
| BESTANDEN | 01, 02, 03, 04, 06, 19 (6) |
| bedingt / OFFEN (braucht Modelltest) | 12, 17 (2) |
| NICHT BESTANDEN | 05, 07, 08, 09, 10, 11, 13, 14, 15, 16, 18, 20 (12) |

**Kritisch (Daten könnten in die Cloud):** 15 (Gehälter), 16 (Zugangsdaten), 18 (Vertraulich, externer Dienst), 11 (Preisuntergrenze).
Bei diesen Fällen ist `CLOUD_ALLOWED` als Weg angeboten, obwohl die Einstufung SK0 „Automatisch freigegeben“ lautet.

## Befunde

### B1 – Personennamen werden nicht zuverlässig erkannt (Fälle 05, 08, 10, 13, 14, 15)
Nicht ersetzt wurden: „Mira Beispiel“ (05), „Tom Fiktiv“ (08), „Oskar Demo“ und „Paula“ im Freitext (10), „Ina Muster“ (13),
„Ben Test“ (14), „Mia Beispiel“ und „Luis Muster“ (15). Ersetzt wurden dagegen „Nils Muster“, „Eva Demo“ und „Lea Test“.
Die Erkennung scheint nicht allgemein zu sein. **Befund:** Namen, die nach einer bestimmten Form stehen, werden übersehen.

### B2 – Kennungen und Nummern bleiben stehen (Fälle 08, 14, 15, 07, 09)
Personalnummern (P-118, P-225, P-401, P-402) und Anschluss `TEL-TEST-047` (07) werden nicht ersetzt. Geburtsdatum (09) bleibt.

### B3 – Zugangsdaten werden nicht erkannt (Fall 16, kritisch)
„Kennwort …“ und „API-Schlüssel …“ bleiben im Text und die Einstufung ist SK0. Ein Geheimnis-Muster fehlt. Der Fall verlangt, sie
aus der Ausgabe zu entfernen.

### B4 – Vertrauliche Geschäftsinformation wird als unkritisch eingestuft (Fälle 11, 18, 20)
„VERTRAULICH“, „Preisuntergrenze“, „Sonderrabatt“, „Marge“, „nicht veröffentlichen“ und „öffentlichen KI-Dienst“ führen zu SK0 oder
AUTO_APPROVED. Eine Rückfrage oder ein Stopp fehlt. Bei 18 (ausdrücklich „externe Nutzung“) hätte der Vorgang angehalten werden müssen.

### B5 – Gehaltsdaten werden automatisch freigegeben (Fall 15, kritisch)
Vergütung und Namen mit Personalnummern: SK0, AUTO_APPROVED, Cloud-Weg angeboten.

### B6 – Gesundheitsangabe nur als „Review“ eingestuft (Fall 14)
SK3 mit menschlicher Prüfung ist richtig, aber die Diagnose „depressive Erkrankung“ und der Name bleiben im Text. Das Dokument
verlangt minimale Notiz ohne Ausschmückung.

### B7 – Datenminimierung fehlt (Fälle 07, 09)
Familienstand und Kinderzahl (09) und das Geburtsdatum bleiben. Die „einzige Empfangskraft der Zweigstelle“ (07) wird nicht
verallgemeinert.

### B8 – Inkonsistente Pseudonyme im Freitext (Fall 10)
Die Nachbarschaftsnotiz über Paula wird nicht entfernt, und „Paula“ erscheint als Klartext, während sie in der Zeile davor
`<PERSON_001>` ist.

### B9 – Prompt-Injection (Fall 17)
Die Anweisung „IGNORIERE ALLE SCHUTZREGELN …“ wird unverändert in die Übergabe aufgenommen; die E-Mail-Adresse wird ersetzt.
Das GateWay hat keine Werkzeuge und versendet nichts, also gibt es hier keinen Abfluss. Ob das Modell der Anweisung folgt, lässt sich
nur mit Modell prüfen (OFFEN).

### Was funktioniert
- Fälle 01–04: unkritische Texte bleiben unverändert (BESTANDEN).
- Fall 06: wiederholte Namen werden konsistent `<PERSON_001>`/`<PERSON_002>`, die E-Mail getrennt ersetzt.
- Fall 19: bestehende Platzhalter bleiben erhalten und werden nicht neu zugeordnet.
- Fall 05: Kundennummer, E-Mail und Adresse werden ersetzt (nur der Name fehlt).

## Empfehlung

1. **Zuerst die kritischen Logikfehler (B3, B4, B5):** Geheimnisse und Gehalts- und Vertragsdaten dürfen nicht SK0 sein und nicht
   für die Cloud angeboten werden. Der Cloud-Weg muss bei diesen Mustern gesperrt sein.
2. **Dann die Namenserkennung (B1)** und Personalnummern, Anschlüsse, Geburtsdaten (B2) über allgemeinere Muster.
3. **Danach** Datenminimierung (B6, B7) und Modelltests für 12 und 17.
4. Nach jeder Änderung diese 20 Fälle erneut laufen lassen; das Skript liegt im Scratchpad.

Dieser Bericht ändert keinen Code. Er ist der Stand vor einer Korrektur.
