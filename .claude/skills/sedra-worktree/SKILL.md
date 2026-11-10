---
name: sedra-worktree
description: Einen Git-Worktree für SEDRA richtig anlegen, für Bau und Server lauffähig machen und später sauber abbauen (eigener Branch, local_paths.yaml, Junction engines, rmdir vor dem Entfernen). Nutzen, bevor eine Sitzung im SEDRA-Repo auf einem eigenen Branch arbeitet, wenn ein Lauf aus einem Worktree mit llama_server_not_found, engine_not_installed oder model_loader_unavailable scheitert und wenn Worktrees oder Branches aufgeräumt oder gelöscht werden sollen.
---

# Worktree für SEDRA

Jede schreibende Sitzung arbeitet in einem eigenen Worktree auf einem eigenen Branch (`docs/ENTWICKLUNG.md` Regel 12). So stören sich parallele Sitzungen nicht, und `main` bekommt nur, was der Captain zusammenführt. Ein frischer Worktree kann aber weder bauen noch einen Modellserver starten, weil zwei rechnerlokale Dinge nicht in Git liegen. Dieser Fehler ist mehrfach aufgetreten.

Platzhalter: `<sedra>` ist das Haupt-Repo, `<umgebung>` der Ordner darüber.

## Anlegen

```
git -C "<sedra>" worktree add -b <name> "<umgebung>\A1-wt-<name>" main
```

- Name kurz und sprechend. Die vorhandenen Worktrees heißen `A1-wt-<name>` und liegen neben dem Repo.
- Scheitern Tests an der Pfadlänge (tiefe Ordner unter `architecture`), den Worktree unter einem kurzen Pfad anlegen, zum Beispiel `C:\sb\<name>`.
- Startet eine Sitzung mit eigenem Worktree, danach mit `git worktree list` prüfen, ob er wirklich entstanden ist. Es kam vor, dass die Sitzung trotzdem im gemeinsamen Ordner lief.

## Lauffähig machen (nur für Bau, Messung oder Server)

Für reine Code- und Dokumentarbeit ist nichts weiter nötig.

1. **Lokale Pfade:** `<sedra>\runtime\config\local_paths.yaml` in denselben Ort des Worktrees kopieren. Die Datei ist in `.gitignore`, sie wird nicht eingecheckt.
2. **Engines:** eine Junction, keine Kopie:
   `cmd /c mklink /J "<worktree>\engines" "<sedra>\engines"`
3. **Python:** das der Hauptumgebung, `<sedra>\runtime\.venv\Scripts\python.exe`.
4. **Projektordner für Bauläufe:** `<sedra>\workspace\SEDRA_OS`, auch wenn das Skript aus dem Worktree läuft. `workspace` wird nicht kopiert.

Fehlt Punkt 1 oder 2, lauten die Fehler `llama_server_not_found`, `engine_not_installed` oder `model_loader_unavailable`.

Ein Server aus dem Worktree läuft nie neben einem zweiten Cockpit auf demselben Projekt. Vorher den Skill `sedra-schnellpruefung` nutzen.

## Arbeiten

- Commits gehen auf den Branch des Worktrees. Nach `main` nur über den Skill `sedra-git-uebernahme`.
- Keine eigene Kopie von SEDRA anlegen (kein Auspacken, kein zweiter Ordner). Für Vergleiche `git show` und `git diff`. `python benchmarks/hygiene.py` im Ordner `runtime` zeigt Reste an und löscht nichts.
- Das Logbuch schreibt beim Zusammenführen nur der Vorarbeiter, sonst entstehen Konflikte.

## Abbauen

Löschen braucht das ausdrückliche Ja des Captains. Fremde Worktrees werden nur genannt, nie angefasst.

1. `git worktree list` und im Worktree `git status --short`. Offene Änderungen melden, nicht verwerfen.
2. Prüfen, ob der Branch in `main` steckt: `git branch --merged main`. Ein Branch, der nicht gemergt ist, kann die einzige Kopie einer Arbeit sein.
3. **Zuerst die Junction lösen:** `cmd /c rmdir "<worktree>\engines"`. Niemals rekursiv löschen; ein rekursives Löschen folgt der Junction und entfernt die Engines der Hauptumgebung.
4. `git worktree remove "<worktree>"`.
5. `git branch -d <name>` als einzelner Befehl. Zusammengesetzte Löschbefehle lehnt der Auto-Modus ab. Remote-Branches löscht der Captain.
6. Melden, was entfernt wurde und was bleibt.
