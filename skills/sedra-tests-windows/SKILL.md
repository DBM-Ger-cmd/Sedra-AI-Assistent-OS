---
name: sedra-tests-windows
description: SEDRA-Tests unter Windows laufen lassen und Fehler richtig einordnen (Testgruppen, Browser-Tests, Wissen-Standard, Zeitlimits, Skripte statt Heredocs). Nutzen, wenn Tests für SEDRA gestartet, rote Tests geprüft oder Testläufe in den Hintergrund gelegt werden.
---

# SEDRA testen unter Windows

## Läufe
- Gruppenlauf im Ordner `runtime`: `python benchmarks/run_tests.py <Gruppen>`. Gruppen: `harness`, `workflow` (Prozess-Apps, Selbstabbild), `runtime` (F0-Lebenszyklus), `uix`, `desk`, `orchestra`, `scheduler`, `wissen`. Browser-Tests (Edge über Playwright) laufen mit `--slow`.
- Einzelne Module: im Ordner `runtime/tests` mit `PYTHONPATH=../src:.` und `python -m unittest <modul>`. Browser-Module brauchen zusätzlich `SEDRA_BROWSER=1`.
- JavaScript-Tests: `node --test tests/n8n_model.test.cjs tests/workflow_ui.test.cjs` im Ordner `runtime`.
- Längere Läufe (über 2 Minuten) in den Hintergrund legen, nicht mit `sleep` blockieren; auf die Ausgabedatei mit Schleife warten. Umlaute der Ausgabe mit `iconv -f cp1252 -t utf-8` lesen.

## Einordnung roter Tests
- **Wissen ist Standard an.** Dadurch halten Hubs und Runtimes in Temp-Ordnern `wissen.sqlite` offen, und Windows verweigert das Aufräumen (WinError 32). Der Testlauf setzt deshalb `SEDRA_WISSEN_STANDARD=aus`. Tests, die das Wissen brauchen, schalten es selbst ein (`mock.patch.dict(os.environ, ...)` oder `setUpModule`). Neue Tests mit Hub oder Runtime schließen sie im Cleanup (`addCleanup(hub.close)` bzw. `runtime.close()`).
- **Vor dem Urteil:** läuft der Test allein grün, war es Last (30-Sekunden-Zeitlimit der Browser-Tests bei parallelen Läufen). Läuft er allein rot, mit dem Stand vor der Änderung vergleichen (Worktree auf `main`).
- Tests nie lockern, um grün zu werden. Erwartung nur ändern, wenn die Spezifikation sich bewusst geändert hat, und das im Commit sagen.
- Ein Test, der die Routen der Tools prüft (`test_uix_hardening_2026_10_30`, `test_desk_gateway`): Routen in `tool.yaml` und Zählung über das Helfer-Verzeichnis `HELFER` pflegen.

## Skripte statt Heredocs
Bash-Heredocs mit Umlauten, Anführungszeichen oder Backslashes brechen unter Git Bash (und machen Dateien kaputt). Dateien und Python-Skripte mit dem Write-Werkzeug anlegen und danach ausführen. Dateien mit CRLF beim Schreiben erhalten (`newline=''`, Zeilenenden erst ersetzen, dann zurücksetzen). Backslash im Python-Quelltext über `chr(92)` bilden.

## Nach dem Lauf
Zahlen nennen (Tests, übersprungen, rot), rote Tests mit Ursache, was nicht gelaufen ist (z. B. keine Windows-Abnahme, keine GPU).
