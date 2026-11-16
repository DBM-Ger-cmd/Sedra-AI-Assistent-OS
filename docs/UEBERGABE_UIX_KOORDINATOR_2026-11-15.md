# Übergabe: UIX-Koordinator für One Sedra (ab 15.11.2026)

Für den neuen Chat, der die Weiterentwicklung der Oberfläche übernimmt. Er arbeitet als Koordinator zwischen Hermes und Pi und kümmert sich ausschließlich um die UIX der Harness-Shell.

## 1. Rolle

- **Koordinator:** verteilt Aufträge an Hermes und Pi über das Postfach, prüft jedes Ergebnis selbst (Diff, Tests, Sichtprüfung im Browser) und übernimmt nur Geprüftes. Committen, Mergen, Pushen macht nur der Koordinator, Merge und Push nur mit dem Ja des Captains in diesem Chat.
- **Umfang:** nur `runtime/src/sedra_runtime/uix/` der Shell `harness` und was sie dafür vom Server braucht. Keine anderen Shells, keine Bau-Specs für andere Linien, keine Messläufe.
- **Captain:** gibt Freigaben, entscheidet über Aussehen und Reihenfolge. Antworten auf Deutsch, kurz, Ergebnis zuerst, Zahlen mit Beleg, volle Pfade.

## 2. Ort und Stand

- Worktree `<umgebung>\A1-wt-uix-3d`, Branch `uix-3d-naechste-stufe`, von `main` `1111b8a` nachgezogen. Nicht gemergt, nicht gepusht.
- Register `SEDRA-UIX-3D-01` (Status IN_DEVELOPMENT); Dashboard `<umgebung>\KOORDINATOR_DASHBOARD.html`.
- Zuerst lesen: `docs/WISSEN_SEDRA_GESAMT.md` Abschnitt 20, `docs/AUFTRAG_UIX_NAECHSTE_STUFE_2026-11-15.md` (Bausteine A bis F), `docs/SPEC_DELEGATION_IM_GESPRAECH_v1_ENTWURF.md` (Abschnitte 7 und 8).
- Prüfstart am PC: `<umgebung>\A1-wt-uix-3d\START_UIX3D_PRUEFUNG.bat` (nicht eingecheckt). `START_SEDRA.bat` startet die Hauptumgebung ohne diesen Stand. Nie zwei Server auf demselben Projekt.
- Nicht eingecheckt im Worktree: `START_UIX3D_PRUEFUNG.bat`, `docs/abnahme_delegation.md` (Datei eines Helfers aus der Abnahme).

## 3. Hermes und Pi

- Postfach: `<umgebung>\KOORDINATION_SEDRA\02_POSTFACH\POSTFACH_HERMES_PI.md`. Nur anhängen; nur per `tail`/`grep` lesen. Regeln stehen am Anfang der Datei (Regel 8: Einträge `von: Koordinator` gelten sofort).
- Dazu im selben Ordner: `KURZZEIT_GEDAECHTNIS.md` (schreibt nur der Koordinator, bei jeder Änderung neu), `LANGZEIT_GEDAECHTNIS.md`, `ARBEITSPROMPT_HERMES_PI.md`, `PROMPT_NEUES_FENSTER_HERMES.md`, `PROMPT_NEUES_FENSTER_PI.md`.
- Letzte vergebene Nummern: Aufträge bis A-020, Koordinator-Einträge bis F-048, Ergebnisse bis E-042. Kein offener Auftrag; die alten Einträge mit Status OFFEN (F-040, F-041, F-043, F-044, F-047) sind durch spätere Antworten erledigt, vor dem ersten neuen Auftrag gegen das Kurzzeitgedächtnis prüfen.
- Ein Auftrag je Agent, je Auftrag ein eigener Worktree `<umgebung>\wc_hermes_aNNN` bzw. `wc_pi_aNNN` **vom Branch `uix-3d-naechste-stufe`**, nicht von `main`. Zwei Schreiber fassen nie dieselben Dateien an.
- Erste Zeile jedes Auftrags: was nicht getan werden darf. Abnahmeblock mit Pflicht-Tests. Ergebnisse nie ungeprüft übernehmen: Pi hat schon ein Ergebnis erfunden und trotz „noch nicht bauen“ gebaut.
- Bleibt ein Agent stehen: mit der Phrase „weiter gehts“ fortsetzen, nicht neu starten. Postfach etwa alle 5 Minuten prüfen.
- Hermes und Pi nutzen Modelle (lokal oder Cloud). Ein lokaler Modellserver ist ein GPU-Lauf und braucht das Ja des Captains.

## 4. Feste Regeln der Oberfläche

- UI-Vertrag (`test_uix_contract`): keine Datei einer Shell oder eines Werkzeugs über 400 Zeilen; Farben nur als Token in `ui/tokens.css`; Texte deutsch und in den Textdateien (DE/EN, gleiche Schlüssel); jedes Bedienelement mit `aria-label`; Esc schließt.
- Nichts aus dem Netz zur Laufzeit (keine Bibliothek, keine Schrift). Kontrast mindestens 5:1.
- Die Anzeige darf ein laufendes Modell nicht bremsen: der Drache zeichnet nur im Ruhezustand oder gelandet.
- Nichts an der Oberfläche erteilt ein Recht. Entschieden wird nur auf der Freigabe-Karte.
- Ereignisse, die die Shell vom Server hören soll, müssen in `ui/bus.js` angemeldet sein.
- Nach jeder Änderung an JS oder CSS: `node --check`, Vertragstest, Sichtprüfung im Browser mit Sitzungen im Wegwerf-Projekt (ohne Sitzungen blieb der Symbol-Fehler unentdeckt).
- Tests: Exit-Code prüfen, dann committen. Rot im parallelen Lauf zuerst allein wiederholen.

## 5. Nächste Schritte (Vorschlag, Reihenfolge entscheidet der Captain)

| Nr | Was | Wer könnte es machen |
|---|---|---|
| 1 | Der Captain sieht sich Delegations-Karte, Seitenleiste und Zelle „Team“ im Prüfstart an; Korrekturen daraus | Koordinator |
| 2 | Züge und Token eines Helfers laufend anzeigen | Hermes |
| 3 | Schalter in den Einstellungen: Drache (drei Wahlen), Avatar, Avatar je Anlass | Hermes |
| 4 | Baustein E: Zustand je Sitzung in der Seitenleiste, anheften, archivieren | Pi (erst Spec), dann Hermes |
| 5 | Baustein C: Startbild als Leitstand | Koordinator mit Captain (Entwurf), dann Hermes |
| 6 | DG-15 und DG-08 mit echtem Modell prüfen | Koordinator am PC |
| 7 | Prüfen, ob die fünf nicht angemeldeten `harness.*`-Ereignisse ankommen | Pi (nur lesen, Bericht) |
| 8 | Voller Gruppenlauf, dann Übernahme nach `main` | Koordinator, mit Ja des Captains |

## 6. Was dieser Chat nicht anfasst

Andere Shells, `orchestra`, Bau- und Messläufe, Modellprofile, der Absturz des Modellservers vom 15.11. (nur melden), das Löschen der zwei verwaisten 3D-Dateien ohne Ja.
