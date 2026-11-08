# ANALYSE F0-06A – SQLite-ResourceWarnings und Test-Hygiene

**Status:** Analyse-Vorschlag, nur Lesen. Kein Code geändert, keine Warnung unterdrückt.
**Basis:** lokaler `main` = `52f33f3` (enthält `aa5962e`). Zeilen gelesen am 08.11.2026.
**Erstellt:** Nachtlauf (Claude-Sitzung), kein Coder-Lauf mit lokalem Modell; keine Testläufe während des laufenden GPU-Baus.
**Register:** SEDRA-F0-06A, Status `PLANNED`, abhängig von F0-05E.

---

## 1. Befund aus dem Register (Coder 1, 2b13daa)

- `pytest -W error::ResourceWarning` auf `test_job_supervisor.py`: 111 bestanden, aber 2 `PytestUnraisableExceptionWarning` durch nicht geschlossene SQLite-Verbindungen.
- Vermutete Ursache: drei Tests erzeugen `SedraRuntime` ohne `rt.close()`.
- Der Windows-Flaky-Test `test_uix_harness_lauf.LaufServerTests.test_stoppen_ueber_werkzeug_und_weg` ist ein eigener Befund (Zeitabhängigkeit), in dieser Analyse nicht behandelt.

## 2. Was der Quellcode zeigt

### 2.1 Entstehungsort der Verbindung

- `runtime/src/sedra_runtime/wissen/schema.py:129` – `oeffne_db()` öffnet `sqlite3.connect(...)` mit `isolation_level=None`, `check_same_thread` nach Parameter.
- Weitere `sqlite3.connect`-Stellen in der Wissen-Schicht:
  - `runtime/src/sedra_runtime/wissen/adapter.py:321` – read-only-Verbindung mit `timeout=5`
  - `runtime/src/sedra_runtime/wissen/speicher.py:151` – Kopie-Verbindung (`ziel`)
- Der Speicher schließt seine Verbindung in `runtime/src/sedra_runtime/wissen/speicher.py:168–174` (`schliessen()`), aufgerufen über `runtime.close()` (`runtime.py:594–620`).

Ergebnis: Die Warnung zeigt auf die Allokationsstelle `schema.py:129`. Die Verbindung wird von der Runtime-Instanz gehalten; wer sie schließen muss, ist der Aufrufer von `SedraRuntime(...)`.

### 2.2 Testseiten ohne Schließen

`runtime/tests/test_job_supervisor.py`:

| Zeile | Test (Kontext) | Erzeugung | Schließen |
|---|---|---|---|
| 128 | Supervisor deaktiviert, `rt.boot()` | `rt = SedraRuntime(Path(tmp)/'project', ARCH)` | kein `rt.close()` gefunden |
| 745 | `test_recover_needs_the_captain_and_never_replays_mutating_work` | `rt = SedraRuntime(...)` | kein `rt.close()` gefunden |
| 773 | `test_recover_token_is_bound_to_the_job_state` | `rt = SedraRuntime(...)` | kein `rt.close()` gefunden |

Grep über `test_job_supervisor.py` nach `rt.close` oder `.close()` liefert keinen Treffer für diese Stellen (nur die Imports und Erzeugungen). Das bestätigt die Vermutung des Befunds.

### 2.3 Einordnung

- **Der Fehler liegt in den Tests**, nicht im Produktivcode: Die Produktion schließt die Runtime über `UIXHub.close()` (`uix_server.py:3620–3642`) bzw. über den `finally`-Pfad (`uix_server.py:4245–4250`).
- **Warnungsunterdrückung ist nicht der Weg.** Die Tests sollen die Runtime nach Gebrauch schließen (z. B. `addCleanup(rt.close)` oder `try/finally`).
- **Nicht bewiesen:** Dass die Warnung exakt von diesen drei Stellen stammt. Die Zuordnung ist plausibel, aber noch nicht gemessen. Zwei unraisable-Warnungen gegenüber drei Erzeugungen lassen offen, welche Instanzen betroffen sind.

## 3. Nachweis, der noch fehlt (Prüfplan, nicht ausgeführt)

1. Gezielter Lauf nach dem GPU-Bau (CPU-only, kein Modell):
   `python -X tracemalloc=20 -W error::ResourceWarning -m pytest runtime/tests/test_job_supervisor.py -q`
   Ziel: Allokationsort der Verbindung je Warnung ausgeben und Testname zuordnen.
2. Gegenprobe: Nach Ergänzung von `addCleanup(rt.close)` an den drei Stellen muss die Warnung verschwinden, ohne Warnungsfilter.
3. Vollständigkeit: `pytest -W error::ResourceWarning` auf die gesamte Gruppe `runtime`, um weitere Stellen zu finden (Coder-1-Befund sagt nur eine Datei).
4. Windows: Die Temp-Datei-Flakiness (`WinError 32` bei `test_uix_harness_freigabe`, siehe Register-Notiz F0-05A) mit Prozess-Handles prüfen; eigene Ursache, nicht gleich mit der Connection-Warnung vermischen.

## 4. Vorschlag für den Umsetzungsschritt (nach F0-05E, nicht jetzt)

- Nur `runtime/tests/test_job_supervisor.py` (drei Stellen) plus ggf. Hilfsfunktion im Testmodul.
- Kein Eingriff in `wissen/schema.py` oder `speicher.py`, solange der Nachweis aus 3.1 nicht vorliegt.
- Abnahme: Warnungsfreier Lauf mit `-W error::ResourceWarning` auf der betroffenen Datei und auf der Gruppe `runtime`; keine Filter, kein `pytest.mark.filterwarnings`.

## 5. Offene Fragen an den Captain

1. Soll F0-06A die Tests der Gruppe `runtime` vollständig prüfen (Vorschlag: ja, Schritt 3 oben), oder nur die drei Stellen?
2. Die Flaky-Tests (`test_stoppen_ueber_werkzeug_und_weg`, `test_uix_harness_freigabe` WinError 32) – in F0-06A oder in einem eigenen Register-Eintrag? Vorschlag: eigener Eintrag, weil die Ursache anders ist.

## 6. Belege

- `runtime/src/sedra_runtime/wissen/schema.py:129` – `oeffne_db`
- `runtime/src/sedra_runtime/wissen/adapter.py:321` – read-only-Verbindung
- `runtime/src/sedra_runtime/wissen/speicher.py:151, 168–174` – Kopie und Schließen
- `runtime/src/sedra_runtime/runtime.py:594–620` – `close()`
- `runtime/tests/test_job_supervisor.py:128, 745, 773` – Erzeugung ohne Schließen
