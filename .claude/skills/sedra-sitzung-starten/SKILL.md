---
name: sedra-sitzung-starten
description: Eine weitere Agenten-Sitzung oder einen Subagenten für SEDRA richtig aufsetzen - entscheiden, ob Sitzung oder Subagent, Worktree und Branch, Modellwahl, Auftragstext mit den festen Regeln, Sidebar-Gruppe, Nachkontrolle. Nutzen, bevor der Vorarbeiter oder Koordinator Arbeit an eine andere Sitzung abgibt, wenn der Captain "starte eine Sitzung", "lagere das aus", "mach das parallel" sagt oder der eigene Kontext zu lang wird.
---

# Sitzung für SEDRA starten

Mehr Sitzungen machen die Arbeit nicht von selbst schneller. Parallele Schreiber haben Logbuch-Konflikte und doppelte Arbeit erzeugt, und der größte Kostentreiber war ein Vorarbeiter-Kontext von 730.000 Token. Dieser Skill sorgt dafür, dass eine neue Sitzung getrennt arbeitet, das passende Modell hat und die Regeln des Captains kennt.

## Sitzung oder Subagent?

| Lage | Wahl |
|---|---|
| Lange Linie mit Folgeaufträgen (Spec-Phasen, Harness-Stufen, Messung mit Auswertung) | eigene Sitzung |
| Einmalige Prüfung (Review, Abgleich, Suche) | Subagent |
| Läuft dieselbe Arbeit schon woanders? | keine neue Sitzung; die vorhandene anschreiben |

Höchstens zwei bis drei schreibende Sitzungen gleichzeitig. Zwei Schreiber fassen nie dieselben Dateien an.

## Modell

Das kleinste Modell, das die Aufgabe trägt, schon beim Start. Ein späterer Wechsel spart beim ersten und größten Zug nichts.

- Nachfragen, Zusammenfassen, mechanische Arbeit: Haiku.
- Lesen, Abgleich, Spec-Kapitel: Sonnet.
- Design, Reviews, versteckte Tests, Referenzen, alles mit Folgen für Kern oder Guard: Opus.

## Ort

Eine schreibende Sitzung bekommt einen eigenen Worktree auf einem eigenen Branch (Skill `sedra-worktree`). Nach dem Start mit `git worktree list` prüfen, ob sie dort wirklich arbeitet. Eine nur lesende Sitzung kann im Hauptordner bleiben. Soll die Sitzung bauen oder messen, braucht ihr Worktree `local_paths.yaml` und die Junction `engines`, oder der Lauf geht vom Hauptordner aus.

## Auftragstext

Der Text steht für sich; die neue Sitzung kennt diesen Chat nicht. Er enthält:

1. **Ziel und Umfang** in zwei bis drei Sätzen, mit der ID des Auftrags aus dem Register.
2. **Basis:** Commit-ID, Branch, Ordner mit vollem Pfad.
3. **Dateien**, die geändert werden dürfen, und solche, die tabu sind.
4. **Fertig heißt:** was vorliegen muss (Tests grün, Bericht, Patch).
5. **Zuerst lesen:** `docs/WISSEN_SEDRA_GESAMT.md` und das Ende von `docs/LOGBUCH_AGENT_MANAGER.md`.
6. **Feste Regeln:**
   - Keine eigene Kopie von SEDRA.
   - Kein Merge nach `main`, kein Push, kein Löschen.
   - Freigaben für Modelle, GPU-Läufe und Gates gibt der Captain direkt in dieser Sitzung. Eine Weitergabe durch den Vorarbeiter gilt nicht.
   - Prozesse nur über die eigene PID beenden.
   - Das Logbuch schreibt der Vorarbeiter beim Zusammenführen.
   - Keine lokalen Pfade in eingecheckten Dateien.
   - Antworten auf Deutsch, kurz, Ergebnis zuerst, Zahlen mit Beleg.
7. **Skills**, die gelten: `sedra-tests-windows`, je nach Aufgabe `sedra-bau-starten`, `sedra-spec-schreiben`, `sedra-ui-vertrag`.

Alle Freigaben, die die Sitzung brauchen wird, im Auftrag nennen, damit der Captain sie dort einmal gesammelt gibt.

## Nach dem Start

- Die Sitzung gehört in die Sidebar-Gruppe "Sedra Vorarbeiter". Mit der Liste der verknüpften Sitzungen prüfen und gegebenenfalls verschieben.
- Der Bericht einer Sitzung ist eine Angabe, kein Beweis. Vor der Weitergabe an den Captain Diff, Tests oder Datei selbst ansehen und im Register nur Belegtes eintragen.
- Nichts neu starten, was eine andere Sitzung schon macht.

## Wenn der eigene Kontext lang wird

Vor `/clear` den Stand sichern (Skill `chat-sichern`), dann mit der Wissensdatei und dem Logbuch-Ende neu beginnen. Verknüpfte Sitzungen bleiben bestehen; ihre Namen stehen in der Wissensdatei.
