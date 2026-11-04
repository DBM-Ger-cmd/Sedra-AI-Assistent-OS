# Übersicht der Nebensitzungen und Branches (Stand 04.11.2026)

Zusammengestellt aus der Sitzungsliste der Claude-App (Titel, Datum, Gruppe, Branch) und dem Git-Stand. Die Inhalte der einzelnen Sitzungen wurden dafür **nicht** erneut gelesen; wer Einzelheiten braucht, öffnet die Sitzung über den Titel. Alle Sitzungen laufen nicht mehr und liegen in der Gruppe „Sedra Vorarbeiter“, sofern nichts anderes steht.

## Cloud-Sitzung (GitHub, nicht in der Liste der lokalen Sitzungen)

| Branch | Inhalt | Stand |
|---|---|---|
| `claude/intelligent-goldberg-7arr50` | G2 für O3+ (Schutz des Oberflächen-Codes), G9 bis G11 (Freigaben außerhalb des Browsers), E9 Variante C, E12 bis E14, Übergabe an den lokalen Vorarbeiter, Code-Stand G4 | PRs #4 bis #6, in `main` gemergt (04.11.) |
| `docs/apps-modell` | Apps v1: G4-E1 bis E4 entschieden, G2 freigegeben (Werkzeuge und Erweiterungen als Apps, siehe `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md`) | in `main` |
| `plan/usb-stick-minimal` | Stick-Liste mit `CODE_STAND.bat` (Version 1.22.0, PR #1) | in `main` |
| `fix/harness-list-projects` | `list_projects` der Harness, Wissensdatenbank USB-Stick-Minimalversion | in `main` |

## Lokale Sitzungen nach Thema

**Harness bauen und planen**
- Harness-Shell Stufe 1 bauen (29.10., Branch `claude/stufe-1-64f713`, vom Vorarbeiter-Start ausgelöst)
- Harness Stufe 3 planen, G2 und G3 (29.10., Branch `claude/stufe-3-plan-425992`)
- Start-Prompt für Sedra-Vorarbeiter (29.10. und 01.11.; die zweite ist der Einstieg für die heutige Arbeit)
- Harness-Vergleich Hermes, Unsloth, Sedra (31.10.)
- Sedra master chat window error (28.10., Vorläufer von MasterChat)

**USB-Stick (Minimalversion)**
- Sedra Minimal USB-Stick Arbeitsumgebung (31.10.)
- SEDRA: minimale USB-Version auf K:\ einrichten (31.10., Branch `claude/usb-stick-minimal-3c1b19`, Worktree vorhanden)
- Sedra USB-Stick auf K:\ einrichten (03.11.)

**Tests und Läufe**
- 6h-Lauf auswerten, dann Nemotron-Test (28.10.)
- Test: Bonsai und Nemotron gleichzeitig (30.10., Branch `claude/test-bonsai-nemotron-ac86cc`)

**Zusammenfassungen und Kurs**
- Sedra-Projekt Zusammenfassung (28.10.)
- Sedra: Kurs-Zusammenfassung und Arbeitsübersicht (28.10.)
- Sedra-Zusammenfassung für Studienkurs (28.10.)

**Betrieb und Sonstiges**
- Modelle zu KI-Daten hinzufügen (29.10., Ablage unter `I:\KI-Daten\modelle`)
- C-Laufwerk Datenmüll aufräumen (29.10.)
- Produktaktivierung Altersrestriktion (28.10.)
- StarNet einrichten und verstehen (01.11., Ordner `E:\WEb Projekte\starnet-feat-harness-backend`)
- Hermes-Einrichtung starten (28.10., Gruppe „Hermes Agent Optimierung“)
- Earth 2160 in OpenRA (02.11., keine Gruppe, gehört nicht zu Sedra)

## Git-Stand der Branches

| Branch | Stand |
|---|---|
| `main` | `a2e699e`, gleich `origin/main` |
| `claude/usb-stick-minimal-3c1b19` (lokal, mit Worktree) | trägt Stick-eigene Änderungen und einen Merge von `main` (`e0af71c`); **nicht gelöscht**, solange der Stick-Bau darauf aufsetzt |
| `fix/harness-list-projects` (lokal) | der letzte Commit steckt inhaltlich schon in `main`; lokal entfernt |
| `origin/claude/intelligent-goldberg-7arr50`, `origin/docs/apps-modell`, `origin/plan/usb-stick-minimal`, `origin/fix/harness-list-projects` | alle in `main` enthalten; können auf GitHub gelöscht werden (macht der Captain, der Auto-Modus sperrt `git push origin --delete`) |
