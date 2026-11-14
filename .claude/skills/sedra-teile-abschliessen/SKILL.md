---
name: sedra-teile-abschliessen
description: Ungetrackte Teile eines SEDRA-Repos prüfen, reparieren, testen, in Themen-Commits festhalten und auf main bringen - mit Ausschlussliste (Secrets, Laufdaten, Backups, fremde Agenten-Ordner), Syntax- und Importprüfung, Test im sauberen Worktree, Pfad- und Schlüssel-Scan, ff-only-Merge und Push nur mit Ja. Nutzen, wenn der Captain "Teile tracken", "alles committen und mergen", "Rest committen" oder "neuer Workflow" sagt oder wenn viele ungetrackte Dateien aus mehreren Quellen liegen.
---

# Ungetrackte Teile abschließen

Dieser Ablauf ist der Weg, wie offene Arbeit aus dem Arbeitsbaum in `main` kommt. Er ersetzt das Einzel-Commit-Vorgehen der Sitzungen. Die Git-Regeln stehen in `sedra-git-uebernahme`; dieser Skill sagt, was in welchen Commit kommt und in welcher Reihenfolge geprüft wird.

## 1. Inventur

- `git status --short --untracked-files=all` in eine Datei im Scratchpad schreiben, nach Oberordner gruppieren (`cut -d/ -f1-4 | sort | uniq -c`).
- Jede Gruppe einer Entscheidung zuordnen: **Code** (committen), **Tests** (committen, wenn sie zum Code gehören), **Doku** (committen, wenn nicht persönlich), **Ausschluss** (nicht committen).

## 2. Ausschlussliste (nie committen, ohne ausdrückliches Ja)

- Laufdaten und Zustände: `runtime/local_config/`, `local_config/evidence/*.db`, `my_test_project/`, `.hermes/` (Hermes-Agent), `KOORDINATION_SEDRA/`, `*/Hilfsarbeiten/`, Notizdateien des Captains.
- Sicherungen: `*.bak*`, `*.backup`.
- Generierte Dashboards und Übersichten: `PROJEKT_DASHBOARD.html`, `dashboard_data.json`, `INDEX.md`, `build_index.py` im Wurzelordner.
- Große Binär-Sammlungen ohne Code (z. B. `SEDRA_3D_Assets_Sammlung_*`) als eigenes Thema mit Ja.
- Ergebnisdateien von Läufen (`*_fallen.json`, Nachtprotokolle) bleiben draußen.
- Tests, die ein nicht installiertes Paket brauchen (z. B. Appium): nicht committen, im Bericht nennen.
- Verdächtige Duplikate (z. B. `*_fix.py`, die nirgends importiert werden): nicht committen, nennen.

## 3. Prüfen je Thema

- `python -m py_compile` auf alle Python-Dateien des Themas. Ein Fehler wird repariert, nicht übersprungen.
- Importkette: in einem sauberen Worktree (`git worktree add --detach <scratchpad>/verify HEAD`) mit `PYTHONPATH=<worktree>/runtime/src` importieren. Ein fehlendes Modul ist ein Befund, kein Grund, die Datei stillschweigend mitzunehmen.
- Abhängigkeiten: `grep` nach `factory_studio` und ähnlichen Namen zeigt, ob etwas den Code braucht.

## 4. Reparieren

- Syntaxfehler in eingebetteten XAML- oder Textblöcken: Ende des Literals und Verschachtelung prüfen (unterminierte `"""`, falsch verschachtelte Elemente, ausgeschriebene `\"\"\"`).
- Ein Test, der einen fehlenden Dienst braucht, bekommt keinen Umbau, sondern wird aus dem Commit genommen und genannt.
- Änderungen am bestehenden Verhalten nur, wenn ein Test sie verlangt und der Captain es weiß.

## 5. Testen

- Gruppen im sauberen Worktree laufen lassen, nicht im Arbeitsbaum (Editable-Install zeigt sonst auf einen anderen Checkout). `PYTHONPATH=<worktree>/runtime/src:<worktree>/runtime/tests`, `SEDRA_WISSEN_STANDARD=aus`.
- Lange Läufe (über 2 Minuten) im Hintergrund, nicht mit `sleep` warten. `benchmarks/run_tests.py` kann bei 290 Sekunden abbrechen; dann einzelne Module nachlaufen lassen.
- Rot prüfen: ist der Fehler auch auf dem Stand vor der Änderung rot, ist er vorbestehend. Das im Bericht getrennt nennen.
- Windows-Dateisperren beim Aufräumen (WinError 32) sind bekannt; Test einzeln wiederholen, bevor man urteilt.

## 6. Prüfen vor dem Commit

- `git add <pfad>` mit ausgeschriebenen Pfaden, nie `git add -A`.
- `git diff --cached --text | grep -nE "[A-Za-z]:\\\\Users|/Users/"`: Treffer durch Platzhalter ersetzen. XAML-Namespaces wie `using:Sedra.FactoryStudio` sind keine Pfade.
- `git diff --cached --text | grep -niE "(api[_-]?key|secret|passw|bearer )[^,)]*[=:] *['\"][A-Za-z0-9_\-]{12,}"`: jeden Treffer ansehen. Feldnamen und Testwerte sind kein Befund, echte Werte schon.

## 7. Commit

- Ein Thema je Commit, sprechende Nachricht, am Ende die Co-Autor-Zeile.
- Reihenfolge: zuerst die Teile, von denen andere abhängen (Kern, Module), dann Tests und Doku.
- Nach jedem Commit `git worktree add` und Importprüfung im Commit selbst.

## 8. Merge nach main

- Liegt die Arbeit auf `main`, ist kein Merge nötig. Liegt sie auf einem Branch: `git merge-base --is-ancestor main <branch>` prüfen, dann mit `git branch -f main <branch>` vorrücken (ff-only, ohne Arbeitsbaum umzuschalten), danach `git switch main`.
- Vorher `git fetch origin` und prüfen, ob `origin/main` sich bewegt hat. Hat sich etwas verschoben, nicht erzwingen: rebasen, neu testen, neu fragen.

## 9. Push

- Nur mit ausdrücklichem Ja des Captains in diesem Chat. Ein Ja für den Merge gilt nicht für den Push.
- Vor dem Push `git log -p origin/main..main` auf lokale Pfade und Schlüssel scannen.
- Beleg: `git ls-remote origin main` und `git rev-parse main` müssen dieselbe ID zeigen.

## 10. Gleichzeitige Agenten

- Andere Agenten (Hermes, Pi, ChatGPT-Sitzungen) können im selben Repo arbeiten. Vor dem Merge `git fetch` und Stand prüfen. Ihre Logs liegen unter `<benutzer>\AppData\Local\hermes\logs\` (agent.log, errors.log) und `<benutzer>\.pigent\`. Abgelehnte Schreibversuche dort sind ein Warnzeichen: Dateien nicht parallel anfassen.
- Dateien, die gerade ein anderer Agent bearbeitet, nicht mit committen.

## 11. Bericht

- Commit-IDs, Anzahl Tests und Ergebnis je Gruppe, vorbestehende Fehler getrennt.
- Ausgeschlossene Teile mit Grund, Liste zur Entscheidung.
- Was nicht lauffähig ist (z. B. fehlende Pakete) und was nicht getestet wurde.
- Offen: Push nur mit Ja.
