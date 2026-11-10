# SEDRA in Orca als Agent

Orca hat einen festen Katalog von Agenten (Claude, Pi, Hermes …) und kennt SEDRA nicht von selbst. Jeder installierte Eintrag erlaubt aber einen eigenen **Startbefehl**; das ist der Weg.

## Einrichtung (einmal)

1. `START_SEDRA.bat` mindestens einmal ausführen (richtet Python ein), danach SEDRAs Fenster schließen – die Brücke startet einen eigenen Server und startet kein zweites SEDRA neben einem laufenden.
2. Orca → **Einstellungen → Agenten**. Beim Eintrag, den du für SEDRA nutzen willst (getestet mit **OpenCode 2**; jeder Eintrag geht, der nicht gebraucht wird), auf den Pfeil rechts klappen und den Startbefehl ersetzen durch den vollen Pfad von `SEDRA_AGENT.bat` in Anführungszeichen (wegen Leerzeichen im Pfad): `"<sedra>\SEDRA_AGENT.bat"`. Danach „Aktualisieren“; der Eintrag steht unter „Installiert“ und behält Orcas Namen und Icon.
3. Beim Eintrag auf **Standard** klicken, wenn neue Worktrees damit starten sollen; sonst im Dialog „Worktree erstellen“ unter **Agent** den Eintrag wählen.
4. Unter „Agenten öffnen als“ **Terminal** wählen (die Brücke ist ein Terminal-Chat, kein Orca-Chat-Protokoll).

## Was die Brücke tut

- Startet `uix_start` im Hintergrund (ohne Fenster), liest Adresse und Token aus dessen Ausgabe und legt eine Harness-Sitzung an.
- Chat im Terminal mit Live-Text, Werkzeugzeilen und **Freigabekarten**: `j` erlauben, `s` für die Sitzung merken, alles andere lehnt ab. Die Brücke bestätigt nie von selbst.
- Das Token bleibt im Speicher des Brückenprozesses. Beim Beenden (`/ende`, Strg+D) wird der Server mitbeendet und das Modell entladen.
- `/modell` zeigt die Rezepte (geladen, passt, passt nicht mit Grund), `/modell <id>` lädt eines (dauert bis zu Minuten). Ohne geladenes Modell lädt die Brücke selbst, wenn der Katalog das für das Rezept freigibt.
- `SEDRA_AGENT.bat --einmal "Frage"` für Skripte: eine Antwort, Karten werden abgelehnt.

## Grenzen

- Ohne geladenes Modell meldet die Brücke `kein_modell`; dann `/modell <id>`. Die Brücke startet einen eigenen Server (`uix_start --ohne-fenster`); ein offenes SEDRA-Fenster muss vorher zu sein.
- Freigaben der Klasse H verlangen zusätzlich ein Ja außerhalb des Browsers (G9); die Brücke zeigt den Hinweis des Servers an.
- Geprüft am 10.11.2026 in Orca: Start, Sitzung, `/modell`, Laden von `harness.nemotron_e4b`, Antwort auf „Was kannst du?“. Nicht geprüft: eine Freigabekarte im Terminal (auch Klasse H). Die Bausteine sind getestet (`runtime/tests/test_orca_bruecke.py`).
