---
name: sedra-register-dashboard
description: Das Aufgabenregister von SEDRA (auftraege.json im Koordinator-Paket) ändern und das Koordinator-Dashboard daraus neu erzeugen - sichern, Eintrag ändern oder anlegen, prüfen, rendern, kopieren. Nutzen nach jeder Aktion, die einen Auftrag betrifft (Commit, Merge, Testbericht, Freigabe, neuer Auftrag, Bau-Ergebnis), und immer, wenn der Captain "Dashboard updaten", "ins Register eintragen", "Status setzen" oder "was steht im Register" sagt - auch wenn er das Register nicht ausdrücklich nennt.
---

# Register und Dashboard pflegen

Das Dashboard ist die gemeinsame Momentaufnahme aller Sitzungen. Es wird aus dem Register erzeugt. Wer die HTML-Datei direkt ändert, verliert die Änderung beim nächsten Rendern. Deshalb läuft jede Änderung über das Register.

Platzhalter: `<umgebung>` ist der Ordner, in dem das Repo, `KOORDINATION_SEDRA` und die Dashboard-Kopie nebeneinander liegen.

## Orte

- Paket: `<umgebung>\KOORDINATION_SEDRA\01_KOORDINATOR_QUELLE\koord\SEDRA_Koordinator_Entwicklerpaket_v1_1_2026-11-06`
- Register: `04_REGISTER\auftraege.json` im Paket. Die Aufträge stehen in der Liste `tasks`.
- Werkzeuge: `06_TOOLS\validate_register.py` und `06_TOOLS\render_dashboard.py` (nur Standardbibliothek).
- Kopie für den Captain: `<umgebung>\KOORDINATOR_DASHBOARD.html`

Das Register liegt außerhalb des Repos. Eine Registeränderung ist kein Commit.

## Ablauf

1. **Stand lesen.** Den Eintrag über die volle ID suchen, zum Beispiel `SEDRA-F0-06A`. Eine Suche nach `F0-06A` allein hat schon einmal einen vorhandenen Eintrag als fehlend gemeldet. Den Status aus dem Register nehmen, nicht aus der Notiz einer anderen Sitzung.
2. **Sichern.** `auftraege.json` kopieren nach `auftraege.json.bak_vor_<grund>_<JJJJMMTT>` im selben Ordner.
3. **Ändern.** Mit einem kleinen Python-Skript (JSON laden, Eintrag ändern, im vorhandenen Format zurückschreiben). Das Skript mit dem Write-Werkzeug anlegen. Heredocs und `printf` verstümmeln Backslash-Pfade.
4. **Prüfen.** Im Paketordner `python 06_TOOLS/validate_register.py`. Erwartet wird `OK: <n> tasks`. Bei einem Fehler die Sicherung zurückspielen und den Fehler beheben.
5. **Rendern.** `python 06_TOOLS/render_dashboard.py`. Das erzeugt auch den CSV-Export neu.
6. **Kopieren.** `KOORDINATOR_DASHBOARD.html` aus dem Paketordner nach `<umgebung>\` kopieren und mit `cmp` vergleichen.
7. **Melden.** ID, alter und neuer Status, Beleg, voller Pfad des Dashboards.

## Mehrere Aufträge auf einmal

Nach einem Paket (mehrere Teile gemergt und gepusht) nicht Eintrag für Eintrag ändern, sondern die Vorlage `sammelskript_vorlage.py` in diesem Ordner kopieren und ausfüllen. Sie sichert zuerst, überspringt vorhandene IDs, setzt `MERGED` mit Commit und Freigabetext und aktualisiert die Baseline (`last_reported_local_main`, `origin_main`, `live_verification_evidence`). In `notes` stehen "Nicht gebaut" und "Nicht am PC geprüft" für jeden Teil. Danach Schritt 4 bis 7 wie oben. Der Ablauf des Pakets steht im Skill `sedra-paket-ablauf`.

## Felder eines Eintrags

`id`, `title`, `track`, `owner`, `priority` (P0 bis P3), `status`, `depends_on`, `scope`, `acceptance`, `source`, `notes`, `candidate_paths`, `assigned_coder`, `base_commit`, `integration_commit`, `tester_report`, `captain_approval`, `last_verified_at`.

Ein neuer Eintrag füllt alle Felder. Unbekanntes bleibt `null`, nichts wird erfunden.

## Statuswechsel und Belege

| Nach | Was vorliegen muss |
|---|---|
| SPEC_APPROVED | Der Captain hat G1, G2 und G3 für genau diesen Umfang genehmigt |
| IN_DEVELOPMENT | Aktueller HEAD, Branch, reservierte Dateien, Coder |
| CODER_HANDOFF | Patch, Tests, Herkunft, Rollback |
| INTEGRATION_REVIEW | Kandidat ist auf dem aktuellen `main` gespiegelt |
| TESTING | Integrationsbranch oder Diff, unabhängiger Tester |
| AWAITING_CAPTAIN | Testerbericht und offene Risiken liegen vor |
| MERGED | Ausdrückliche Freigabe des Captains und der Merge-Commit |
| MAIN_VERIFIED | `integration_commit` und `tester_report` (der Validator verlangt beide) |
| CLOSED | Changelog und Rollback-Hinweise archiviert |
| REWORK, BLOCKED | Fehler, Verantwortlicher, nächster Schritt |

MERGED ist nicht MAIN_VERIFIED. MERGED und MAIN_VERIFIED setzt nur der Koordinator. Die Freigabe muss im Chat dieser Sitzung stehen; eine Weitergabe aus einer anderen Sitzung zählt nicht.

## Was ohne Statuswechsel geht

Belegte Tatsachen in `notes` nachtragen (Commit-ID, Pfad eines Berichts, Testzahlen) und `last_verified_at` setzen. Was nicht nachgeprüft ist, steht dort als "nicht geprüft" oder gar nicht.

## Danach

Folgt auf die Registeränderung ein Git-Schritt, gilt der Skill `sedra-git-uebernahme`. Vor einem Lauf zeigt der Skill `sedra-schnellpruefung`, ob Register und Dashboard synchron sind.
