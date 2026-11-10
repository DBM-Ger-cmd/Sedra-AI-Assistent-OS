# SEDRA in Orca als Agent

Orca hat einen festen Katalog von Agenten (Claude, Pi, Hermes …) und kennt SEDRA nicht von selbst. Jeder installierte Eintrag erlaubt aber einen eigenen **Startbefehl**; das ist der Weg.

## Einrichtung (einmal)

1. `START_SEDRA.bat` mindestens einmal ausführen (richtet Python ein), danach SEDRAs Fenster schließen – die Brücke startet einen eigenen Server und startet kein zweites SEDRA neben einem laufenden.
2. Orca → **Einstellungen → Agenten**. Beim Eintrag, den du für SEDRA nutzen willst (z. B. **Hermes**, nur Terminal), auf den Pfeil rechts klappen und den Startbefehl ersetzen durch den vollen Pfad von `SEDRA_AGENT.bat`, z. B. `C:\Pfad\zu\SEDRA\SEDRA_AGENT.bat`.
3. Beim Eintrag auf **Standard** klicken, wenn neue Worktrees damit starten sollen; sonst im Dialog „Worktree erstellen“ unter **Agent** den Eintrag wählen.
4. Unter „Agenten öffnen als“ **Terminal** wählen (die Brücke ist ein Terminal-Chat, kein Orca-Chat-Protokoll).

## Was die Brücke tut

- Startet `uix_start` im Hintergrund (ohne Fenster), liest Adresse und Token aus dessen Ausgabe und legt eine Harness-Sitzung an.
- Chat im Terminal mit Live-Text, Werkzeugzeilen und **Freigabekarten**: `j` erlauben, `s` für die Sitzung merken, alles andere lehnt ab. Die Brücke bestätigt nie von selbst.
- Das Token bleibt im Speicher des Brückenprozesses. Beim Beenden (`/ende`, Strg+D) wird der Server mitbeendet und das Modell entladen.
- `SEDRA_AGENT.bat --einmal "Frage"` für Skripte: eine Antwort, Karten werden abgelehnt.

## Grenzen

- Ein Modell muss geladen werden können; sonst meldet die Brücke den Grund (`kein_modell`). Dann einmal über SEDRAs Fenster ein Rezept laden oder Auto-Laden einstellen.
- Freigaben der Klasse H verlangen zusätzlich ein Ja außerhalb des Browsers (G9); die Brücke zeigt den Hinweis des Servers an.
- Nicht geprüft: ein vollständiger Lauf mit geladenem Modell in Orca (dieser Rechner hatte hier kein Modell geladen). Getestet sind die Bausteine (`runtime/tests/test_orca_bruecke.py`).
