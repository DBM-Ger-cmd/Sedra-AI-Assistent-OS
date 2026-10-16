# PHASE0_STATUS – Reparaturen vor dem Supervisor

Stand: 2026-10-01 · Testumgebung: **Windows 11, Python 3.14.7, PyYAML 6.0.3** (Entwickler-PC, keine Modelle, kein microVM-Image)

**Ergebnis:** Phase 0 ist umgesetzt. `python -m unittest discover -s tests` → **403 Tests, 0 Fehler, 5 übersprungen** (v1.20 hatte 362 inkl. 10 Windows-Fehler). `validate_package.py`: 116 YAML-Dateien OK. `compileall`: OK.

## Übersicht

| # | Punkt | Befund | Status |
|---|---|---|---|
| 0.1 | Audit: Tail-Lesen + Sperre | F-2 | erledigt |
| 0.2 | Evidence-Store: gleiches Muster | F-2 | erledigt |
| 0.3 | Job-Store: Sperre + Revisionszähler | F-3 | erledigt |
| 0.4 | Strukturierte Fehlerklassen | F-1 | erledigt |
| 0.5 | Eine Quelle für E1/E2/E3-Ziele | F-5 | erledigt |
| 0.6 | PASS braucht deterministischen Testbeleg | F-6 | erledigt |
| 0.7 | Windows-Testfehler | neu | erledigt |

## 0.1 / 0.2 Audit- und Evidence-Log

- `util.py`: `read_last_jsonl()` liest nur das Dateiende. `append_lock()` ist eine blockierende, zeitlich begrenzte Sperre über Threads **und** Prozesse (baut auf `mission_lock.exclusive` auf), jetzt auch **wiederholt betretbar** im selben Thread.
- `audit.py`, `development_evidence.py`: Letzte Zeile lesen, Hash bilden und schreiben laufen unter einer Sperre. Dateiformat unverändert.
- **Defekt belegt:** Ohne Sperre erzeugten 8 Threads 194 Zeilen mit nur **62 eindeutigen IDs**, `verify_chain()` = False. Mit Sperre: 200/200, Kette gültig.
- Tests (`test_log_append.py`, 11): Randfälle des Tail-Lesers, Threads, zwei Instanzen, **4 Prozesse**, Kosten bei 3000 Zeilen Vorlauf, Sperr-Timeout, Evidence-Kette.
- **Eigener Fehler, korrigiert:** Die erste Fassung rief `time.monotonic()` auf. `test_tuning` ersetzt diese Funktion global durch einen Mock. Die Zeitfunktionen werden jetzt beim Import gebunden.

## 0.3 Job-Store (F-3)

- `DevelopmentJobStore.save()` verweigert das Überschreiben eines neueren Stands (`stale_job_record`). Dafür zählt `rev` die Schreibvorgänge. v1.20-Dateien ohne `rev` zählen als 0 und bleiben nutzbar.
- Neu `mutate(job_id)`: lädt unter der Store-Sperre, gibt den Job heraus, speichert nur bei Erfolg. Alle Manager-Methoden mit Lesen-Ändern-Schreiben nutzen es (`bind_candidate`, `attach_verification`, `compare`, `checkpoint`, `prepare_development_environment`, `assign_roles`).
- `heartbeat()` liest frisch, setzt nur die Heartbeat-Felder und aktualisiert die Kopie des Aufrufers. Ein Worker mit veraltetem Stand kann so keinen Statuswechsel überschreiben.
- `transition()` stellt bei fehlgeschlagenem Speichern den alten Zustand der Kopie wieder her.
- Der Learning-Store (`capability_learning.json`) wird unter Sperre gelesen und geschrieben.
- Tests (`test_job_store_locking.py`, 12): veraltete Kopie, Threads (80/80 Updates), **4 Prozesse** (40/40), Heartbeat gegen Statuswechsel, verschachtelte Sperre, v1.20-Datei ohne `rev`, Learning-Store mit 6 Threads.
- Nicht abgedeckt: Es gibt **eine** Sperre für den ganzen Store. Bei vielen gleichzeitigen Workern wird das ein Engpass. Eine Sperrdatei `store.lock` bleibt im Job-Ordner liegen.

## 0.4 Fehlerklassen (F-1)

- Neu `failure_classes.py`: `classify(reason_code, exception=, message=)` und `retry_rule(klasse)`. Reihenfolge: **Reason-Code → Exception-Typ → Freitext** (Wortgrenzen, feste Reihenfolge). `policy_denied` wird immer zuerst geprüft, damit eine Meldung mit „policy" nie als wiederholbar gilt. Unbekanntes ergibt `unknown_failure`, nie eine wiederholbare Klasse.
- `retry_rule` setzt Handoff §7 um: Nur `transient_provider_error` und `timeout` dürfen dieselbe Anfrage erneut senden. `policy_denied`, `deterministic_test_failure`, `context_overflow`, `validation_failure` dürfen es nie. Bei `policy_denied` ist Fallback verboten und Eskalation Pflicht.
- Alle Reason-Codes des Bestands (feasibility, Hardware-Manager, Router) sind abgebildet.
- `SelfDevelopmentManager.classify_failure()` bleibt als Kompatibilität und ruft den neuen Klassifizierer.
- Tests (`test_failure_classes.py`, 11) belegen die Fälle aus F-1: „context window exceeded" → `context_overflow`, „latest release attested" → nicht mehr Testfehler, 429/503 werden erkannt, bloße Zahlen lösen nichts aus.
- **Nicht umgesetzt:** Nichts im Bestand ruft die Klassifikation oder `retry_rule` auf. Sie wird erst vom Supervisor (Phase 2) genutzt. Die Regeln sind getestet, aber **nicht gegen echte Provider-Fehler** geprüft.

## 0.5 E1/E2/E3-Ziele (F-5)

- Neu `evolution_targets.py` als einzige Quelle (bewusst im Code, nicht in YAML, weil die Liste den Kern schützt). Vereinigung beider alter Listen. `evolution.classify()` und `CapabilityAdmissionGate` nutzen dieselbe Funktion.
- Vorher war z. B. `policy` auf dem Evolution-Pfad E1, auf dem Admission-Pfad E3.
- Auch Groß-/Kleinschreibung und Leerzeichen umgehen den Kernschutz nicht mehr (`' Guard '` → E3). Core gewinnt, wenn ein Name in beiden Mengen stünde.
- Tests (`test_evolution_targets.py`, 8): nichts wurde laxer, beide Pfade stimmen für jedes gelistete Ziel überein.
- **Offen (Entwurfsfrage):** Unbekannte oder falsch geschriebene Zielnamen werden weiterhin **E1** (geringste Prüfung). Sicherer wäre eine Positivliste für E1. Das ändert Verhalten und braucht eine Entscheidung.

## 0.6 PASS braucht Belege (F-6)

- `attach_verification(result='PASS')` wird zu **INCONCLUSIVE** herabgestuft (Job → BLOCKED), wenn nicht mindestens ein referenzierter Beleg im hash-verketteten Evidence-Store vorliegt, der **deterministisch** ist, `status == PASS` meldet und zu **diesem Job und diesem Kandidaten** gehört.
- Weitere Regeln: ungültige Evidence-Kette → herabgestuft. Ein referenzierter deterministischer Beleg mit anderem Status wirkt als Veto. `model_assessment` (z. B. Kev) allein reicht nie. Ohne Store (`evidence_store=None`) ist kein PASS möglich. Ein unbekannter Zusatzverweis stört einen bewiesenen PASS nicht.
- Die Begründung steht in den `findings` (`pass_downgraded:…`). `FAIL` und `INCONCLUSIVE` brauchen keinen Beleg.
- Fünf bestehende Tests behaupteten `PASS` mit erfundener ID `EVD-1` oder ganz ohne Beleg. Sie wurden auf echte Belege umgestellt. Das ist eine **bewusste Verhaltensänderung**. Neu: 10 Tests.
- **Nicht geprüft:** Ob der Beleg **tatsächlich zu den `acceptance_criteria`** passt. Es wird nur geprüft, dass ein bestandener deterministischer Beleg existiert, nicht, dass er die Kriterien abdeckt. Die Prüfung, dass der Beleg wirklich aus einem Testlauf stammt, liegt beim Erzeuger des Belegs.
- `trust_level='deterministic'` wird vom Aufrufer gesetzt. Ein Aufrufer könnte es fälschlich setzen. Der Store prüft das nicht.

## 0.7 Windows-Testfehler

| Test | Ursache | Behebung |
|---|---|---|
| `test_uix_server.test_persisted_intent_html_is_escaped` | `read_text()` ohne Kodierung (cp1252) bei UTF-8-Datei | `encoding='utf-8'` |
| 8 Tests `test_step_journal.CandidateLifecycleCase` | Hypothese „Pfadtrenner" war **falsch**. Tatsächliche Ursache: `write_text('x=1\n')` schreibt unter Windows `x=1\r\n`, der erwartete SHA-256 passte nicht → Bindungsfehler `expected_source_sha256_mismatch` | `write_bytes(b'x=1\n')` im Test. Der Produktcode (Hash über Bytes) ist korrekt. Die Pfadtrenner-Anpassung im Test ist trotzdem behalten, sie schadet nicht. |
| `test_workflow_contract.test_binding_rejects_symlink` | Symlinks anlegen braucht unter Windows ein Recht (WinError 1314) | Test überspringt, wenn nicht erlaubt |

**Wichtige Lücke:** Alle **5 übersprungenen Tests sind Symlink-Tests**. Die Symlink-Abwehr (Quelle, ausgewählte Datei, Projekt, Dateisystem-Tool, Binding) ist auf diesem PC **ungetestet**. Das ist ein Sicherheitsbereich. Mit aktivierten Windows-Entwicklermodus (oder als Administrator) laufen die Tests. Das sollte vor einer Abnahme einmal geschehen.

## Offene Punkte nach Phase 0

- Symlink-Tests mit Entwicklermodus ausführen (siehe oben).
- Beschädigtes Dateiende eines Logs (abgebrochener Schreibvorgang): weiterhin Fehler. Eine Sicherung vor der Reparatur ist nicht umgesetzt.
- Leistungsmessung gegen ein großes **reales** Audit-Log.
- `PACKAGE_CHECKSUMS.sha256` im Paketstamm ist **veraltet** (Quelldateien und Tests geändert). Sie wird erst beim nächsten Paketbau neu erzeugt. `docs/` ist nicht enthalten.
- Unbekannte Zielnamen → E1 (Entwurfsfrage, siehe 0.5).
- Keine reale Abnahme: kein Zielgerät mit Qwen3.5 und Kev, kein microVM-Image.
