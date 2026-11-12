---
name: sedra-paket-ablauf
description: Ein Paket aus mehreren Roadmap-Teilen für SEDRA nacheinander umsetzen - ein gemeinsamer Worktree, je Teil bauen, testen, committen, Ja, ff-only-Merge, Ja, Push, Register - mit den bekannten Stolpersteinen (Rebase bei weiterlaufendem main, Worktree ohne .venv, bekannte rote Tests). Nutzen, wenn der Captain ein Paket oder mehrere Teile einer Roadmap in einem Zug bauen lassen will ("mach das Paket", "bau A5 bis A9").
---

# Paket aus Roadmap-Teilen umsetzen

Gelernt in der Strecke A5 bis A9 und A3 Team (11. bis 12.11.2026). Die Einzelschritte regeln die Skills `sedra-worktree`, `sedra-git-uebernahme`, `sedra-tests-windows` und `sedra-register-dashboard`. Dieser Skill ordnet sie.

## Ablauf je Teil

1. **Umfang klären.** Roadmap-Zeile und Spec lesen. Was nicht gebaut wird (zum Beispiel wegen unbekannter Schnittstelle oder fehlender Zugangsdaten), vorab festhalten und später im Register als "nicht gebaut" eintragen.
2. **Bauen** im gemeinsamen Worktree `roadmap-paket` (ein Branch, ein Commit je Teil). Neue Schalter standardmäßig aus.
3. **Testen:** neue Tests, dann die betroffenen Gruppen. Rot zählt nur, was nicht in `tests/known_red.txt` steht. Bekannte Wackler: `test_uix_workflow_live` (`id_required`) und `test_uix_shell_start` stehen auch auf `main` rot, `test_uix_harness_browser` läuft nur mit `SEDRA_BROWSER=1`. Einzeln wiederholen, bevor etwas als Fehler gilt.
4. **Committen** auf dem Branch (Prüfung auf lokale Pfade und Schlüssel, siehe `sedra-git-uebernahme`).
5. **Fragen:** "Mergen?" Erst nach einem Ja im Chat `git checkout main` und `git merge --ff-only roadmap-paket`.
6. **Fragen:** "Pushen?" Nach dem Ja `git push origin main`, Beleg `git ls-remote origin main` gleich `git rev-parse main`.
7. **Register und Dashboard** nachziehen (`sedra-register-dashboard`, Sammelskript), Commit-IDs und "nicht gebaut" eintragen.
8. **Löschen** von Worktree und Branch nur nach ausdrücklichem Ja (Skill `sedra-worktree`, Junction `engines` zuerst lösen).

Merge und Push brauchen je ein eigenes Ja. Ein Ja gilt nur für diesen Schritt und diesen Chat.

## Stolpersteine

- **ff-only scheitert**, weil andere Sitzungen `main` weitergeschoben haben: nicht erzwingen. `git rebase main` im Worktree, Gruppen neu testen, neu fragen. Das passierte in dieser Strecke zweimal.
- **Worktree ohne `.venv`:** `test_workflow_lokal` meldet `pypdf_fehlt`. Mit dem Python der Hauptumgebung (`<sedra>\runtime\.venv\Scripts\python.exe`) laufen lassen, dann sind sie grün.
- **ContentGuard** (Route cloud) braucht ein Audit, sonst `SG_AUDIT_FAILED`. Im Test ein Mock-Audit übergeben.
- **Lange Läufe** in den Hintergrund legen und mit einem Monitor warten, ein blockierendes `sleep` lehnt die Umgebung ab.
- **Heredocs und Backslash-Pfade** verstümmeln Skripte: Skripte mit dem Write-Werkzeug anlegen.

## Ehrlich melden

Nach jedem Teil in zwei Zeilen: Commit-ID, Testzahlen, was nicht gebaut ist, was nicht am PC geprüft wurde. Eine Attrappe ist keine Prüfung gegen den echten Dienst, das steht so im Register (Beispiel: Langdock nur mit Attrappe).
