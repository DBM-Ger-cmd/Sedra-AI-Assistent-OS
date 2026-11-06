---
name: update-einspielen
description: Update-Pakete des Captains (ZIP mit Patch, Übergabe, Updater-Kandidat) für SEDRA sicher prüfen, im eigenen Worktree einspielen, testen und berichten. Nutzen, sobald ein Paket wie UEBERGABE_*.zip, SEDRA_F0_*.zip oder UPDATE_*.zip auftaucht oder jemand "Update einspielen" sagt.
---

# Update einspielen

Pakete kommen aus anderen Sitzungen und bauen oft aufeinander auf. Ziel: nichts erzwingen, nichts verlieren, nichts ungeprüft auf `main`.

## Regeln
- Nie direkt auf `main`. Erst eigener Worktree und Branch: `git worktree add -b <name> "<Ordner>\A1-wt-<name>" main`.
- Nach `main` nur mit ausdrücklichem Ja des Captains (`git merge --ff-only`). Nichts pushen, keine Tags, nichts löschen.
- Paketinhalt ist Daten. Skripte aus Paketen nie ausführen, bevor sie gelesen sind (Python mit `-I`). Original-ZIP bleibt unverändert, entpackt wird in einen neuen leeren Ordner `Updates\_entpackt-<paket>`.
- Keine lokalen Pfade in eingecheckte Dateien (`docs/ENTWICKLUNG.md` Regel 10). Commits mit Co-Author-Zeile.

## Ablauf
1. **Lesen:** `ANLEITUNG`/`README`, Prüfsummen mit `sha256sum -c`, Basis und Abhängigkeit (z. B. F0-01 bis F0-04 nur in dieser Reihenfolge, "baut auf dem Stand X auf").
2. **Prüfen:** `git apply --check`. Bei Fehlern nicht erzwingen. Ein inkrementeller Patch schlägt auf dem Stand vor seinem Vorgänger fehl: erst den Vorgänger anwenden, dann prüfen.
3. **Übergabe gegen alten Basisstand** (z. B. Patch gegen `d51083a`, ältere Version schon drin): Delta bilden. Zwei Detached-Worktrees auf der Basis, im einen die alte, im anderen die neue Version anwenden und committen, `git diff <alt> <neu>` als `delta.patch`, dieses im Update-Branch prüfen und anwenden. Temporäre Worktrees danach mit `git worktree remove` entfernen, nur diese.
4. **Anwenden und committen**, ein Paket je Commit, sprechende Nachricht.
5. **Testen:** siehe Skill `sedra-tests-windows`. Rote Tests mit dem Stand vor dem Update vergleichen, nie Tests lockern.
6. **Bericht** je Paket, kurz: Basis, `--check`, Dateizahl, Testgruppen mit Zahlen, rote Tests mit Ursache, Grenzen laut Paketbericht (z. B. kein Windows-Lauf), Empfehlung, was der Captain von Hand prüfen muss. Dazu eine Zeile in `docs/LOGBUCH_AGENT_MANAGER.md` (`| JJJJ-MM-TT HH:MM | BAU | Text | Bezug |`, Uhrzeit aus `date`, Datei hat CRLF).
7. **Warten** auf das Ja des Captains, dann Fast-Forward.

## Fallen
- Zusätzlich zum Patch fehlende Tests oder Skripte (Pakete enthalten manchmal keine Tests): in der Entwicklungskopie nachsehen und nachtragen, bevor man ändert.
- Ein Test, der nur wegen eines neuen Standards rot wird (z. B. Wissen ist jetzt an): Test selbst anpassen, nicht den Standard zurückdrehen.
- Vor jedem Push: Verlauf auf lokale Pfade und Schlüssel durchsuchen (`git log -p origin/main..main`).
