---
name: sedra-git-uebernahme
description: Änderungen im SEDRA-Repo committen, nach main zusammenführen und pushen - mit Prüfung auf fremde Dateien, lokale Pfade und Schlüssel, mit Tests und mit dem Ja des Captains. Nutzen vor jedem git commit, merge oder push im SEDRA-Repo, beim Übernehmen eines Kandidaten, Patches oder Worktree-Branches und wenn der Captain "committen", "übernehmen", "mergen", "pushen" oder "auf main bringen" sagt.
---

# Commit, Merge und Push für SEDRA

Git-Schreibaktionen laufen an einer Stelle zusammen, beim Koordinator. Vorher haben mehrere Sitzungen unabhängig committet und gepusht; das führte zu ungepushten Commits auf `main` und doppelter Dashboard-Pflege. Ein Push lädt die ganze Commit-Geschichte hoch und lässt sich nicht zurücknehmen. Darum steht vor jedem Schritt eine Prüfung und vor Merge und Push das Ja des Captains.

## Was ein Ja braucht

Merge nach `main`, Push, Löschen von Branches oder Worktrees. Das Ja muss im Chat dieser Sitzung stehen und gilt für genau diesen Schritt. Ein Commit auf dem eigenen Branch der Sitzung braucht kein eigenes Ja, wenn der Auftrag ihn deckt.

Nie ohne ausdrückliche Anweisung: Force-Push, `reset --hard`, Umschreiben veröffentlichter Geschichte.

## Vor dem Commit

1. `git status --short` und `git branch --show-current`. Gearbeitet wird auf dem Branch der Sitzung, nicht auf `main`.
2. Nur eigene Dateien aufnehmen, mit ausgeschriebenen Pfaden (`git add <pfad>`), nie `git add -A`. Ungetrackte Dateien anderer Sitzungen nennen, nicht committen. Laufdaten, Modelle, Engines und `*.bak`-Sicherungen bleiben draußen.
3. `git diff --cached` lesen.
4. **Lokale Pfade:** `git diff --cached | grep -nE "[A-Za-z]:\\\\|/Users/"`. Treffer durch die Platzhalter `<sedra>`, `<modelle>`, `<projekte>` und den Platzhalter für den Benutzerordner ersetzen (`docs/ENTWICKLUNG.md` Regel 10). Das gilt auch für das Logbuch.
5. **Schlüssel:** `git diff --cached | grep -niE "api[_-]?key|token|secret|passw|bearer "`. Jeden Treffer ansehen.
6. **Tests:** betroffene Gruppen mit dem Skill `sedra-tests-windows`. Rot zählt nur, was nicht in `tests/known_red.txt` steht.

## Commit

Ein Thema je Commit, sprechende Nachricht, am Ende die Co-Autor-Zeile, die das System vorgibt. In PowerShell die Nachricht mit mehreren `-m` übergeben; Heredocs funktionieren dort nicht.

## Merge nach main

Nach dem Ja: `git checkout main`, dann `git merge --ff-only <branch>`. Geht kein Fast-Forward, nicht erzwingen: den Branch auf den aktuellen `main` bringen, neu testen, neu fragen.

## Push

1. `git log -p origin/main..main` auf lokale Pfade und Schlüssel durchsuchen. Ältere Commits können Pfade enthalten; ein Treffer wird dem Captain gemeldet, nicht stillschweigend gepusht.
2. Nach dem Ja `git push origin main`. Nur `main` wird gepusht.
3. Beleg: `git ls-remote origin main` zeigt dieselbe ID wie `git rev-parse main`.

## Danach

- Register und Dashboard mit dem Skill `sedra-register-dashboard` nachziehen (Commit-ID in `integration_commit`, Status nur mit Beleg).
- Logbuch: `benchmarks/logbook.py add INTEGRATION "Text" --ref "Datei"`. Die Uhrzeit setzt das Werkzeug.
- Melden: Commit-ID, Abstand zu `origin/main`, was noch ungepusht ist.

## Fallen

- `git rev-parse --short` mit mehreren Refs bricht ab. Eine Schleife nehmen.
- Zusammengesetzte Befehle mit `branch -D` oder dem Löschen eines Remote-Branches lehnt der Auto-Modus ab. Einzeln ausführen; Remote-Branches löscht der Captain.
- Ein Commit kann den Spec-Stempel eines Baus ungültig machen. Vor dem nächsten Bau `spec_check --vm` erneuern.
- Das Register liegt außerhalb des Repos. Der Ordner `KOORDINATION_SEDRA/` taucht im Repo als ungetrackt auf und wird nie aufgenommen.
