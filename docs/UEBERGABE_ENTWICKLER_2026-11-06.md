# Entwicklerübergabe SEDRA, Stand 06.11.2026

Für eine neue Sitzung oder einen Entwickler, der nur dieses Paket und das Repository sieht. Pfade sind Platzhalter: `<sedra>` ist der Entwicklungsordner (A1), `<updates>` der Ordner der Update-Pakete, `<archiv>` das Backup-Archiv.

## 1. Stand in einem Satz

`main` steht auf `20ef720`, gleich mit `origin/main` auf GitHub. SEDRA trägt `VERSION = 1.22.3`. Das Update-Paket 1.22.3 ist gebaut und geprüft, aber nirgends eingespielt und nicht getaggt.

## 2. Was seit 05.11. entstanden ist (alles in main)

- Update 1.22.2 und UIX der Prozess-Apps (n8n Workflows, Szenario Studio): Thema hell/dunkel, Symbolsatz, Seitenleiste, Startseite, Vorlagen A/B/C, Knotenkatalog, Schnellleiste, Kantenleiste, Minimap, geführtes Einrichten, Parameteransicht.
- Selbstabbild mit sechs Abläufen, Werkzeug `prozess_beantragen`, Vorlage Prozessmodellierer.
- Wissen im Kern K1/K2/K5 (Kerndienst, `wissen_suchen`, `wissen_beantragen`, freigegebene Ordner, Word/CSV-Leser).
- F0-01 bis F0-04: Startfix, Shutdown und SQLite-Fix, Verbindungen, Boot und Service-Bereitschaft.
- Skills in `skills/` und `.claude/skills/`: update-einspielen, sedra-tests-windows, sedra-ui-vertrag, selbstabbild-erweitern, chat-sichern.
- Paketskripte `runtime/benchmarks/package_n8n_update.py`, `verify_n8n_update.py` und `release/install_n8n_update.py` (kamen aus der Codex-Entwicklungskopie).

## 3. Paket 1.22.3

- Datei: `<updates>/SEDRA-1.22.3-Prozess-Apps/SEDRA-1.22.3-Prozess-Apps-Update-Kandidat.zip`, SHA256 beginnt mit `401663eb`, volle Summe in der `.sha256` daneben.
- 846 Programmdateien, davon 833 geändert gegenüber Basis `d51083a` (1.22.0). Das 1.22.2-Paket ist als zulässiger Vorgänger eingetragen. `app_version` 0.3.0.
- Prüfung `verify_n8n_update.py`: PASS (Prüfsummen, Vorschau, falsche Bestätigung abgelehnt, Offline-Installation, lokale Daten bleiben, Rollback, Upgrade von und Rückkehr zu 1.22.2). Laufende Installation und n8n-Engine wurden nicht angefasst.
- Grenzen: Das Skript hat Basis `d51083a` und den Namen „n8n-candidate“ fest eingebaut, es nimmt nur eine feste Dokuliste mit. Vor einem öffentlichen Tag: committen und das offizielle Manifest mit `release_manifest.py` neu erzeugen.
- Nicht erledigt: Einspielen auf einer Testinstallation, Tag `v1.22.3`, Release auf GitHub.

## 4. Windows-Lauf der F0-Updates (06.11., Worktree F0, Shell Harness)

- Erststart mit `--open`: läuft und gibt Adresse mit Token aus.
- Zweitstart ohne `--replace` bei laufender Instanz: verweigert, Code 3, nennt die PIDs.
- Zweitstart mit `--replace`: beendet beide Prozesse der laufenden Instanz und startet neu.
- Ohne `--open` endet der Start mit eigenem Fenster nach etwa 3 Sekunden, wenn kein Fenster aufgeht (Server hängt am Fenster).
- Nicht untersucht: die offenen SQLite-Warnungen in Orchestra, Scheduler und Job-Supervisor.

## 5. Git-Stand

- GitHub: `main` und die vier Branches `f0-runtime-updates`, `feat/prozess-apps-uix`, `wissen-k5-v4`, `wissen-kern-k1k2` (alle ganz in `main`).
- Verlauf: Beispielpfade wurden in zwei Umbauten aus den unveröffentlichten Commits entfernt (Commits `aacf07e`/`fcdffe3` und Nachfolger haben neue Hashes), dann gepusht ohne Force. Ein Pfad in `docs/N8N_WORKFLOW_APP.md` steckt noch im alten Verlauf (Commit `2bbb381`, schon veröffentlicht) und ist seit `20ef720` nach vorn durch `<sedra>` ersetzt. Der Verlauf wurde dafür bewusst nicht umgeschrieben.
- Lokal bleiben: `claude/usb-stick-minimal-3c1b19` (ein Commit voraus, noch nicht in main, Stick-Branch bleibt) und `codex/n8n-workflow-app` (Commit `08030db`, nur lokal, Entwicklungskopie der Prozess-Apps mit 50 Dateien, Worktree unter Documents/ChatGPT).
- Entfernt: sechs abgenommene Worktrees samt Branches, beide Backup-Tags, `refs/original`.

## 6. Backup

`<archiv>/Back Up/Backup_2026-11-06/`: `sedra_git_alle_staende.bundle` (alle Branches und Tags, `git bundle`), `sedra_lokale_daten.tar.gz` (`local_config`, `runtime/runtime_data`, `local_paths.yaml`, `workspace/GUPPI_OS` ohne `sprache`), `STAND.txt`, `PRUEFSUMMEN.sha256`. Nicht gesichert: Modelle, `engines`, `.venv`, `portable`, `workspace/GUPPI_OS/sprache` (1,4 GB).

## 7. Offene Entscheidung: „GUPPI“ aus dem System entfernen

Der Captain will den Namen nur noch in der Historie. Zählung auf main: 7909 Zeilen in 1096 Dateien, 1107 Dateinamen. Geplant in drei Stufen, je eigener Worktree, volle Tests, kein Merge ohne Ja:

1. Sichtbarer Text (Anzeige, Doku, Skills, Platzhalter). Logbuch und alte Berichte bleiben. Risiko gering.
2. Ordner `GUPPI_OS`, Architekturordner `GUPPI_Architecture_v1.17/v1.20`, Umgebungsvariablen `GUPPI_*` mit Alias für die alten Namen, Migration der bestehenden Installation.
3. Paket `guppi_runtime` (2165 Stellen): Updater muss alten und neuen Pfad kennen (`PRUEFBEREICHE`, `update_anwenden.py`), eigenes Paket 1.23.0.

Welche Stufe zuerst, ist noch nicht entschieden.

## 8. Weitere offene Punkte

- Anbindung der Startseite der Prozess-Apps an den Chat bleibt bei „Sitzung starten“ (kein eigener Chat-Dialog).
- Minimal-Stick: nur Shell Harness, Werkzeuge statt Ansichten, nur committeter A1-Stand, K:-Sync erst nach E-Tests (siehe Entscheidungen im Repository).

## 9. Regeln, die gelten

- Push, Merge nach `main`, Löschen von Worktrees und Branches, Beenden fremder Prozesse nur auf ausdrückliches Ja des Captains (`docs/ENTWICKLUNG.md`).
- Keine lokalen Pfade in eingecheckte Dateien (Regel 10). Vor jedem Push den Verlauf durchsuchen (`git log -p origin/main..main`).
- Updates nie direkt auf `main`: Skill `update-einspielen`. Tests: Skill `sedra-tests-windows`, Skripte statt Heredocs.
- Tests: im Ordner `runtime` `python benchmarks/run_tests.py harness workflow runtime uix desk`.
- Antworten Deutsch und kurz. Commits mit Co-Author-Zeile.
