# Entwicklung: Wie GUPPI sich selbst weiterbaut

Stand 12.10.2026. Das Ziel des Projekts ist ein GUPPI, das sich selbst erweitert, immer hinter der Freigabe des Captains.

## Wer macht was

| Rolle | Aufgabe |
|---|---|
| **GUPPI** (lokale Modelle in der DevVM) | schreibt den Produktionscode neuer Module. Ziel: mindestens 50 % des neuen Codes; gezählt wird mit `agent_manager/code_meter` (Fenster „Code-Zähler“). |
| **Captain** | entscheidet über jedes Gate (per Gate-ID), über Übernahmen in den Kern, Rezepte, Modelle und Kontextgrenzen. |
| **Claude / KI-Sitzungen** | schreiben Specs, versteckte Abnahmetests, Referenzlösungen, Reviews und den Harness, also den Code, den GUPPI nicht an sich selbst ändern darf: Guard, Bridge, Suite-Mechanik, Bauskripte. Code der Modelle wird nur bei trivialen oder blockierenden Fehlern von Hand korrigiert, und das wird als Eingriff im Logbuch eingetragen. |

Wenn GUPPI-Bauten Stunden dauern und wiederholt scheitern, kann der Captain entscheiden, dass Claude ein Modul selbst schreibt. Der Anteil wird dann ehrlich gezählt.

## Ein Bau im Solo-Workflow (Standard seit 2026-10-10)

```
Spec (Aufgabe in Stufen + versteckte Tests)  ──►  Referenz besteht die versteckten Tests (Gegenprobe)
        │
        ▼
devvm_build.py  ── je Stufe:  Entwickler-Modell baut in EINER Unterhaltung ──► versteckter Test in der microVM
                                   ▲                                              │ besteht → Snapshot, nächste Stufe
                                   └──── Fehlerbericht (erste falsche Aussage) ◄──┘ scheitert → bis zu 3 Nacharbeiten
                                                                                    weiter rot → Stopp, Fortsetzungsbefehl im Log
        │
        ▼
Kandidat in runtime_data/devvm_candidates/<spec>/attempt_…  ──►  Review Zeile für Zeile  ──►  Captain: Übernahme ja/nein
```

**1. Spec schreiben** (`runtime/benchmarks/devvm_specs/<name>.py`):
- `NOTES`: Regeln für das Modell, zum Beispiel nur Standardbibliothek, keine Kommentare, Argumente nicht verändern.
- `STAGES`: Liste von `{"name", "task", "hidden": {"hidden_<x>.py": code}}`. Jede Stufe baut auf der vorigen auf; die letzte heißt meist `all` und dient zum Aufräumen.
- Die versteckten Tests prüfen nur das **Verhalten**, eine Prüfung pro `assert` (keine verketteten `and`), und enden mit `print("ok")`.
- Stufen klein schneiden: Code und Verlauf einer Stufe müssen in ein 32k-Fenster passen.

**2. Referenz** (`benchmarks/devvm_refs/<name>/`): eine eigene Lösung, die **vor** dem Bau alle versteckten Tests besteht. Ohne grüne Referenz kein Bau.

**3. Bauen**
```
cd runtime
.venv\Scripts\python.exe benchmarks/devvm_build.py <projekt> --spec <name> --attempts 1 ^
    --coder coder.local_primary --all-models coder.local_primary --context 32768 --tidy --reasoning off --coder-ext all ^
    --server-set flash_attn=on --server-set kv_cache_type=q8_0 --server-set ubatch=512
```
Wichtige Optionen:

| Option | Wirkung |
|---|---|
| `--mode solo` (Standard) | ein Entwickler, keine eigenen Tests, Aufräumen an, versteckter Test als Richter, bis zu 3 Nacharbeiten mit Fehlerbericht |
| `--rework N` | Anzahl der Nacharbeiten |
| `--keep-going` | nach einer gescheiterten Stufe trotzdem weiterbauen (Standard ist Stopp) |
| `--from-stage S --seed <snapshot>` | einen gestoppten Bau ab Stufe S auf dem Stand der letzten bestandenen Stufe fortsetzen; das Log nennt den Befehl |
| `--only S` | nur eine Stufe |
| `--review <datei>` | ein Review mit genauen Zeilen und Ersetzungen als Mängelliste an die Aufgabe anhängen (Nacharbeit eines Kandidaten mit `--seed`) |
| `--coder-ext all\|e01,e08,…` | Coder-Erweiterungen |
| `--context N\|max` | Fenster; immer auf das Maximum **dieses** Rezepts begrenzt |
| `--plan-steps`, `--fresh-rework`, `--step-syntax-check` | Schritt-Plan und Varianten (im Test, standardmäßig aus) |
| `--require-s0` | nicht starten ohne bestandene Verbindungsprüfung für genau diese Einstellungen |

Der Bau hält die GPU-Lease und exportiert jeden Versuch. Nach jeder bestandenen Stufe legt er einen Snapshot unter `runtime_data/devvm_snapshots/` an.

**4. Prüfen und übernehmen:** Claude liest **jede** Fassung Zeile für Zeile. Die versteckten Tests prüfen nur das Verhalten; Doppelungen, kopierter Code und
übersehene Review-Punkte fallen nur beim Lesen auf. Danach entscheidet der Captain. Übernommen wird unverändert, nur relative Importe werden angepasst.
Dazu kommen Tests in `runtime/tests/`. Fähigkeiten der Stufe E1 laufen über `guppi self-integrate-preview` / `self-integrate`, mit Rücknahme.

## Rezept: eine Aufgabe an GUPPI geben (Stand 13.10.2026)

Ein Bau besteht aus einer Spec, einer Referenz, dem Bau durch GUPPI und der Abnahme. Die Werkzeuge liegen in `runtime/benchmarks/`.

1. **Spec und Referenz schreiben.** Spec in `devvm_specs/<name>.py`, Referenz in `devvm_refs/<name>/`, Saat (wenn der Bau auf vorhandenem Code aufsetzt) in `<name>_seed/`. Dateien nur mit den Datei-Werkzeugen (Write/Edit) ändern, nie mit eingefügten Skripten: Backslashes und Zeilenumbrüche gehen dabei verloren.
   - Erwartete Zahlen und Texte kommen aus der Referenz (ausrechnen lassen), nicht aus dem Kopf.
   - Der Test einer Stufe prüft nur Regeln dieser und der früheren Stufen. Ein späterer Satz der Aufgabe ("im nächsten Schritt") ist keine Regel dieser Stufe.
2. **Spec prüfen:** `.venv\Scripts\python.exe benchmarks/spec_check.py <name> [--seed benchmarks/<name>_seed]`. Die Zeile `result` muss `ok` sagen: Lint, die Referenz besteht jede Stufe, die erste Stufe scheitert auf der Saat. Erst dann bauen.
3. **Bauen** (Standardbefehl siehe oben, Abschnitt "Ein Bau im Solo-Workflow"). Danach auf die Zeile `# run ended` warten, nicht abfragen.
4. **Abnahme:** den Kandidaten aus `runtime_data/devvm_candidates/<name>/attempt_…/` Zeile für Zeile lesen. Scheitert eine Stufe nach allen Nacharbeiten, zuerst `spec_check.py <name> --tree <attempt> --host-ok` (oder `--snapshots <Snapshot-Ordner> --host-ok`): zeigt die fehlschlagende Zeile und ob der Test eine spätere Regel braucht.
5. **Übernehmen:** die Datei ins Paket kopieren (die Unterpaket-Datei, nicht die Weiche), betroffene Tests laufen lassen, Mängel des Reviews ins Logbuch schreiben.
   Für Dateien der Oberfläche (`uix/ui`, `uix/shells`, `uix/tools`, `desk.html`; im Archiv `uix/js`, `uix/css`, `retro_desktop.html`) zusätzlich
   `benchmarks/uix_check.py` (echter Browser, Zeile `result ok`; ein einzelnes Werkzeug mit `--tool <id>`), siehe docs/BUILD_7_DESK_2026-10-14.md.
   Ein neues Desktop-Modul hält den Vertrag `docs/SHELL_WERKZEUG_VERTRAG_v1.md`: Manifest, nur `ctx.api()` und `ctx.bus`, zeichnen nur in den eigenen
   Container, ≤ 400 Zeilen je Datei, eine README. `tests/test_uix_contract.py` erzwingt das, `tests/test_desk_*.py` die Andockstelle.
6. **Logbuch:** `.venv\Scripts\python.exe benchmarks/logbook.py add BAU "Text" --ref "Datei"`. Die Uhrzeit setzt das Werkzeug; Pfade mit Laufwerksbuchstaben lehnt es ab.
7. **Messen:** `ab_queue.py <projekt> --spec <name> --seed … --arm A= --arm B="…" --pairs 3 --rework 0 --keep-going --tag <name>`; Ergebnis in `runtime_data/measurements/<tag>/report.txt`, Ende an der Zeile `ab queue finished`.
8. **Commit:** nur die eigenen Dateien, ohne lokale Pfade, mit Co-Autor-Zeile.

## Erkenntnisse aus den Bauten

- Von Modellen geschriebene Prüfskripte und Reviewer sind unzuverlässig (Prüfprobe 0/4). Richter ist nur der versteckte Test.
- Eigene Tests der Modelle kosten viel Zeit und finden die Fehler nicht. Deshalb verlangt der Solo-Workflow keine.
- Die Laufzeit besteht fast nur aus Token-Erzeugung. Der Prompt-Cache macht den Verlauf billig an Zeit, aber er füllt das Fenster. Darum wird ab 60 % des Fensters verdichtet,
  alte Schreib-Aufrufe werden gekürzt, und Dateien werden in Teilen von 150 Zeilen gelesen.
- Nach einer gescheiterten Stufe weiterzubauen verschwendet nur GPU-Zeit (Nacht 11.10.: rund 80 Minuten). Deshalb Stopp und gezielte Fortsetzung.
- Reviews müssen genaue Zeilen und Ersetzungen nennen. In Aufräumrunden übergeht das Modell Review-Punkte sonst unbemerkt.
- Höchstens **eine** Lektion aus der Wissensbasis pro Aufgabe; mehr verschlechtert kleine Modelle.
- Stufentests einer Spec dürfen keine Regel einer späteren Stufe voraussetzen. Scheitert eine Stufe nach allen Nacharbeiten, zuerst den versteckten Test gegen den Kandidaten laufen lassen: Der Fehler kann in der Spec liegen (skill_rank2, 13.10.: 30 Minuten GPU-Zeit verloren).
- Der Fehlerbericht nennt die erste falsche Teilaussage mit beiden Werten. Ein roher Traceback hilft dem Modell deutlich weniger.

## Regeln für alle Sitzungen (Mensch und KI)

1. **Gates entscheidet der Captain**, einzeln und per ID. Eine Freigabe in einem Zusammenhang gilt nicht für den nächsten.
2. **GPU:** Vor dem Laden von Modellen die Lease holen. Rezepte, Engine und Schalter nie ändern, solange ein Lauf die GPU nutzt. Nur eigene Prozesse über ihre PID beenden,
   nie per Namensmuster; andere Sitzungen teilen sich GPU und Skripte.
3. **Vor jeder Konfigurationsänderung eine Sicherung** (`*.bak-<datum>-<grund>`). Danach prüfen, ob GUPPIs Lader die Datei noch annimmt.
4. **Nur betroffene Tests** laufen lassen; neue Tests in die passende Testdatei.
5. **Logbuch** ([LOGBUCH_AGENT_MANAGER.md](LOGBUCH_AGENT_MANAGER.md)): Jeder Schritt wird eingetragen, die Uhrzeit kommt aus `date`, nie geschätzt.
6. **Kein Weg wird stillschweigend geweitet:** Guard-Regeln, Token-Semantik, Audit-Kette und der Selbst-Integrationsweg (nur neue Module, nur E1) ändern sich nur nach ausdrücklicher Zustimmung.
7. **Modelle entfernen** nur über `model-remove` (Quarantäne); endgültig löscht nur der Captain.
8. **Commits** gehen auf `main`, mit Co-Autor-Zeile, wenn eine KI beteiligt war; Laufdaten, Modelle, Engines und Sicherungsdateien bleiben draußen (`.gitignore`).
9. Wenn Speicher fehlt, dürfen untätige Programme (Steam, Chrome …) geschlossen werden; was geschlossen wurde, wird gemeldet.
10. **Keine lokalen Pfade in eingecheckten Dateien**, auch nicht im Logbuch: statt `E:\…` oder `C:\Users\…` die Platzhalter `<modelle>`, `<projekte>`, `<guppi>` und `C:\Users\<user>`.
    Code, der einen solchen Ordner braucht, liest ihn über `guppi_runtime.local_paths.expand("<modelle>")` (siehe [BETRIEB.md](BETRIEB.md#einrichtung)). Tests nutzen eigene Testdaten
    (`runtime/tests/fixtures/`), nie die Konfiguration dieses PCs.
11. **Nichts auf GitHub hochladen** ohne ausdrücklichen Auftrag des Captains. Dabei gilt: Ein Push lädt die ganze Commit-Geschichte hoch. Ältere Commits enthalten noch lokale Pfade
    und müssten vorher bereinigt werden.

12. **Parallele Sitzungen arbeiten getrennt:** jede Sitzung auf einem eigenen Branch, oder sie liefert einen Patch gegen eine benannte Commit-ID (im Paket `BUILD.txt` und die ID nennen). Zusammenführen heißt dann `git merge`, nicht Dateivergleich. Pakete entstehen mit `benchmarks/make_build.py`, Build-Nummer in `BUILD.txt`, Eintrag in `docs/CHANGELOG.md`. Tests, die nur auf diesem PC laufen können (Windows, Modelle, Engines, dulwich), überspringen sich über `tests/env_skip.py` mit Grund – rot heißt kaputt.