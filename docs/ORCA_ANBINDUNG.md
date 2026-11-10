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

## Fragen aus dem Claude-Chat (ohne eigenes Terminal)

Läuft der Terminal-Chat, ist dieselbe Sitzung auch für Fragen von außen offen (nur Loopback, Port 47635, Adresse in `runtime_data/orca_bruecke.json`). Aus einem Terminal oder von einem anderen Agenten (z. B. Claude in Orca):

`SEDRA_AGENT.bat --frage "Was ist der Stand?"` gibt die Antwort als Text aus (Exit 3, wenn kein Chat läuft).

- Freigabekarten werden dabei **immer abgelehnt** und im Antworttext vermerkt; erlauben kann nur der Captain im Terminal-Chat. Das Token des Servers verlässt den Brückenprozess nie.
- Jeder lokale Prozess kann so dem Modell Fragen stellen (lesende Werkzeuge laufen), mehr nicht.
- Beide Wege teilen eine Sitzung und eine Sperre: Fragen und Tastatur laufen nacheinander.
- `SEDRA_AGENT.bat --dienst [--modell <id>]` ist die Variante ohne Tastatur, nur für Fragen von außen. Nur ein Server gleichzeitig: ein zweiter Chat bekommt `gpu_lease_busy`.

## Grenzen

- Ohne geladenes Modell meldet die Brücke `kein_modell`; dann `/modell <id>`. Die Brücke startet einen eigenen Server (`uix_start --ohne-fenster`); ein offenes SEDRA-Fenster muss vorher zu sein.
- Freigaben der Klasse H verlangen zusätzlich ein Ja außerhalb des Browsers (G9); die Brücke zeigt den Hinweis des Servers an.
- Geprüft am 10.11.2026 in Orca: Start, Sitzung, `/modell`, Laden von `harness.nemotron_e4b`, Antwort auf „Was kannst du?“. Nicht geprüft: eine Freigabekarte im Terminal (auch Klasse H). Die Bausteine sind getestet (`runtime/tests/test_orca_bruecke.py`).
