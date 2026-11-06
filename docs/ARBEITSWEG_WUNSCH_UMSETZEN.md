# Arbeitsweg: einen Wunsch aus dem Chat umsetzen (feste Wege, 02.11.2026)

Gilt für Sedra und die Harness-Shell. Wo etwas liegt: `workspace/SEDRA_OS/wunsch_umsetzen/` (Beschreibung dort in `README.md`).

## Wege
- **Wunsch:** `01_wuensche/W-<Datum>-<kurz>.md`. Der Wunsch des Captains in seinen Worten, dazu was das Modell verstanden hat.
- **Auftrag:** `02_auftraege/A-<Datum>-<kurz>.md`. Ziel, Schritte mit Werkzeug und Freigabe, Abnahmekriterien, Status (entwurf, freigegeben, in Arbeit, abgenommen, abgebrochen).
- **Ergebnis:** `03_ergebnisse/<Auftrag>/`. Berichte und Nachweise. Code liegt nur im Schreibbereich des Projekts (`runtime/`, `docs/`, `redesign/`).
- **Lücke:** `04_luecken/L-<Datum>-<kurz>.md`. Fehlt ein Werkzeug oder eine Berechtigung, wird es hier festgehalten, nicht umgangen.
- **Vorlagen:** `00_vorlagen/` (Wunsch, Auftrag, Lücke).

## Regeln
- Erst festhalten, dann bauen: Wunsch → Auftrag → Werkzeuge prüfen → umsetzen → Abnahme durch den Captain.
- Das Modell beantragt Projekte und Wirkung, der Captain entscheidet. Was kein Werkzeug getan hat, wird nicht behauptet.
- Fenster der Oberfläche öffnet das Werkzeug `app_oeffnen` (zum Beispiel `aufnahme` für den Rekorder); es startet und ändert nichts, Aufnehmen und Bestätigen tut der Captain.
- Ein neues Projekt beantragt das Modell mit `projekt_beantragen` (nur ein Antrag im Posteingang); angelegt wird es erst nach der Freigabe des Captains. Ordner entstehen mit `datei_schreiben` (fehlende Ordner im Pfad werden angelegt), nicht mit `befehl mkdir`.
- Das Hauptprojekt schreibt nur in `runtime/**`, `docs/**`, `redesign/**`. Der Ordner `wunsch_umsetzen` ist ein eigenes Projekt, das der Captain einmal beantragt und freigibt (Ordner öffnen …, Schreibbereich `**`).

## Warum es das gibt
In der Sitzung S-1278AB07 (02.11.2026) scheiterte „starte Voice Rekorder, lege das als Auftrag und Projekt an“ an fehlenden Werkzeugen: kein Fenster öffnen,
kein Auftrag und kein Projekt anlegen, `mkdir` nicht als Programm startbar, Schreiben außerhalb des Schreibbereichs. Die Analyse und die Vorgabe stehen in
`docs/AUFTRAG_WERKZEUGKETTE_CHAT_AKTIONEN_2026-11-02.md`. Die festen Wege sollen verhindern, dass dieselben Lücken im Chat versanden.
