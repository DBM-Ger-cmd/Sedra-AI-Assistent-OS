---
name: sedra-schnellpruefung
description: Schnelle, nur lesende Prüfung des Zustands von SEDRA vor einem GPU-Lauf, einem Test oder einer Übernahme (Router, Modellserver, laufende Bau- und Testprozesse, GPU-Speicher, Git-Stand, Register, Dashboard). Nutzen, wenn der Captain fragt, was läuft, was offen ist oder ob ein Lauf starten kann.
---

# Schnellprüfung SEDRA

Nur lesen. Diese Prüfung beendet, startet und ändert nichts. Ein Prozess wird nur auf ausdrückliches Ja des Captains beendet.

## Ablauf (in dieser Reihenfolge, alles parallel möglich)

1. **Router auf Port 8090:** `curl -s -m 5 http://127.0.0.1:8090/health` (erwartet `{"status":"ok"}`), dann `curl -s -m 5 http://127.0.0.1:8090/v1/models`. Das Feld `status.value` zeigt `loaded` oder `unloaded`.
2. **Laufende SEDRA-Prozesse mit Urteil:** `python runtime/benchmarks/prozess_pruefung.py` (nur lesend, beendet nichts). Urteile: AKTIV (CPU steigt), ROUTER, STILL (über 30 min ohne CPU, prüfen), JUNG_STILL. Ein STILL-Prozess wird nur nach Ja des Captains beendet.
   Alternativ von Hand, PowerShell:
   `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'llama-server|devvm_build|bau_schleife|unittest|uix_server' } | Select-Object ProcessId,Name,CreationDate,WorkingSetSize,CommandLine`
   Laufzeit und Speicher nennen, nicht die ganze Befehlszeile.
3. **GPU-Speicher:** `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader`. Ein Lauf mit `devvm_build` oder `clear_leftovers` verlangt ruhige GPU (Basis höchstens 3 GiB).
4. **Git-Stand:** `git -C "<Repo>" status --short`, `git rev-parse --abbrev-ref HEAD`, `git rev-list --left-right --count origin/main...main`. Ungetrackte Dateien fremder Sitzungen nur nennen, nie committen.
5. **Register:** `python 06_TOOLS/validate_register.py` im Koordinator-Paket (Ordner `06_TOOLS`). Erwartet `OK: <n> tasks`.
6. **Dashboard:** `python 06_TOOLS/render_dashboard.py` erzeugt die Datei neu. Danach mit `cmp` gegen die Kopie unter `E:\Sedra Umgebung\KOORDINATOR_DASHBOARD.html` vergleichen.
7. **Nachtlauf-Sitzungen:** `mcp__ccd_session_mgmt__list_sessions` mit `linked: true`. Ausgesetzte Sitzungen melden keine laufenden Prozesse.

## Ausgabe an den Captain (eine Tabelle, kurz)

| Punkt | Stand | Beleg |
|---|---|---|
| Router 8090 | läuft / Modell geladen oder nicht | Health und Modellliste |
| Bau-Prozesse | keine oder PID, Laufzeit | Prozessliste |
| GPU | Speicher in GiB | nvidia-smi |
| Git | Stand, Abstand zu origin | git |
| Register | Zahl Aufträge, Validator | validate_register |
| Dashboard | synchron ja/nein | cmp |

Danach eine Zeile: was ein Lauf jetzt blockieren würde. Nichts beenden, nichts starten.

## Grenzen

- Der Build `devvm_build.py` stoppt beim Start alle SEDRA-llama-server über `clear_leftovers` (Datei `runtime/src/sedra_runtime/models/gpu_preflight.py`). Ein laufender Router wird dabei beendet. Dafür braucht es eine Freigabe, siehe dort.
- Ein Modell im Router ist nur geladen, wenn `status.value` `loaded` zeigt. Ob Speicher belegt ist, zeigt nur nvidia-smi.
