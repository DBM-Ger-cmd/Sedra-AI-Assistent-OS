---
name: sedra-logs-lesen
description: Die Logs von SEDRA finden und auswerten - Audit-Log, Harness-Sitzungen, Router und Modellserver, Bau-Logs, Kandidatenordner, Manager-Journal und Windows-Treiberereignisse. Nutzen, sobald geklärt werden soll, was SEDRA getan hat oder warum etwas scheiterte (welches Modell und Fenster geladen wurde, warum eine Rolle abgelehnt wurde, ob der Server abgestürzt ist, was im Chat geschah), und immer, wenn der Captain "schau in die Logs" sagt. Erst lesen, dann fragen.
---

# Logs von SEDRA lesen

SEDRA schreibt fast alles mit. Der Captain erwartet, dass eine Frage zum Ergebnis eines Laufs zuerst aus den Logs beantwortet wird und er nur gefragt wird, wenn die Logs es nicht hergeben. Eine Aussage über ein Ergebnis braucht einen Beleg (Datei, Zeile, Zeit). Ohne Beleg heißt es "nicht geprüft".

Alle Pfade liegen unter `<sedra>/workspace/SEDRA_OS/runtime_data/`. Ältere Notizen nennen den Ordner noch `GUPPI_OS`; das ist derselbe Ort vor dem Namenswechsel.

## Welche Frage, welches Log

| Frage | Datei |
|---|---|
| Was hat SEDRA getan, welche Rolle, welches Modell, welche Freigabe | `audit/events.jsonl` (daneben `events.jsonl.head`) |
| Was geschah in einem Harness-Gespräch | `harness/sitzungen/S-*.jsonl`, die neueste zuerst |
| Hat der Router ein Modell geladen, ist er abgestürzt | `llama_server/router/router.log`, `router_stdout.txt`, `router.pid` |
| Welche Modelle kennt der Router | `llama_server/router/modelle.ini` |
| Einzelner Modellserver | `llama_server/server.log` |
| Verlauf der Bau-Schleife | `bau_schleife_status.log`, `bau_schleife_stand.json` |
| Ein Bau-Versuch | `bau_schleife_<Stufe>_<Modell>_<Zeit>.log` |
| Warum ein versteckter Test scheiterte | `devvm_candidates/<spec>/attempt_…/` (die Baulogs nennen den Test nicht) |
| Entscheidungen des Managers | `manager/journal.jsonl` |
| Nachtlauf | `nachtlauf/` und das Nachtprotokoll im Koordinationsordner |
| Messwerte der Modelle | `model_messwerte.json`, `measurements/` |
| Was wann entschieden und gebaut wurde | `<sedra>/docs/LOGBUCH_AGENT_MANAGER.md` |

## Audit-Log

Eine Zeile je Ereignis, als JSON. Die Art steht in `event_type`, die Zeit in `timestamp` in UTC (deutsche Zeit ist eine oder zwei Stunden später), Einzelheiten in `payload`. Die Datei ist mehrere MB groß: nur das Ende oder gefilterte Zeilen lesen, nie die ganze Datei.

```
Select-String -LiteralPath "<...>\audit\events.jsonl" -Pattern '"event_type": "ROLE_RESOLUTION_FAILED"' | Select-Object -Last 5
```

Nützliche Arten:

| Art | Aussage |
|---|---|
| `SLOT_SERVER_STARTED` | Fenster je Slot (`context_per_slot`), Zahl der Slots, VRAM |
| `ROLE_RESOLVED` | Welches Rezept eine Rolle bekommen hat |
| `ROLE_RESOLUTION_FAILED` | Ablehnung mit Grund in `rejected.reason`, zum Beispiel `vram_insufficient` |
| `RESOURCE_RESERVED`, `RESOURCE_RELEASED` | Reservierung von Speicher |
| `SG_MODEL_CALL`, `SG_MODEL_ERROR`, `SG_OUTPUT_OK` | Modellaufrufe durch den Inhaltsschutz, Fehler und Erfolg |
| `TOOL_CALLED`, `EXECUTION_REQUESTED`, `EXECUTION_COMPLETED` | Werkzeugaufrufe |
| `CAPTAIN_GATE_APPROVED`, `FREIGABE_WARTET` | Freigaben |
| `HARNESS_ANTWORT` | Antworten im Gespräch |
| `BOOT_STARTED`, `SYSTEM_READY` | Neustarts von SEDRA |

Die Ereignisse sind über Hashes verkettet. Das Log wird nur gelesen, nie bearbeitet.

## Typische Befunde

- **`SERVER CRASH`, `ConnectionResetError` im Baulog:** der Modellserver ist abgestürzt. Der Versuch sagt nichts über das Modell.
- **`CUDA error: illegal memory access` oder Müll in der Antwort:** in die Windows-Ereignisse sehen:
  `Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='nvlddmkm'} -MaxEvents 20`. Treffer zur Absturzzeit (Kennungen 13 und 153) deuten auf Treiber oder Takt, nicht auf SEDRA. Nach einem Neustart des PC ist der Debug-Modus der NVIDIA-App wieder aus.
- **`hardware_pressure`, `ram_measured`, `vram_insufficient`:** es fehlt Speicher. `nvidia-smi` und den freien RAM prüfen; ein übrig gebliebener llama-server hält oft rund 10 GB.
- **Antwort ohne Text, viele Token:** das Modell hat nur gedacht oder ist in eine Schleife gelaufen. In der Sitzungsdatei die Länge der letzten Antwort ansehen.
- **`spec_not_checked`, `spec_changed_since_check`:** der Stempel fehlt oder ist veraltet. Siehe Skill `sedra-bau-starten`.

## Melden

Kurz: was das Log sagt, Datei und Zeit, was daraus folgt, was nicht geprüft ist. Schlüssel, Token und Inhalte mit Personenbezug werden nicht zitiert.

Den laufenden Zustand (Prozesse, GPU, Router) zeigt der Skill `sedra-schnellpruefung`. Dieser Skill beendet und ändert nichts.
