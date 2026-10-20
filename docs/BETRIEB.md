# Betrieb von GUPPI OS

Stand 20.10.2026 (geändert 20.10.2026, Linie L1/L6; vorher 12.10.2026), Windows 11, RTX 4070 Ti (12 GB), Ryzen 7 7700X, 31 GB RAM.

## Einrichtung

1. **`START_SEDRA.bat`** (beim ersten Mal) führt `runtime/Ersteinrichtung.ps1` aus. Vorher prüft es, ob `runtime\portable\sandbox\` vorhanden ist; fehlt es, bricht es mit einem Hinweis ab. Es richtet Python und PyYAML im Paketordner ein (`runtime/portable/`), nichts wird global installiert, und
   vor Downloads fragt es nach. Ohne Internet: Die Dateien, die das Skript nennt, nach `runtime/portable/downloads` legen. Das Skript umgeht keine
   PowerShell-Ausführungsrichtlinie.
2. Für Entwicklung und Tests gibt es zusätzlich die venv `runtime/.venv` (`setup_windows.bat`). Die vorhandene venv wurde in einem früheren Ordner angelegt:
   `activate.bat` zeigt dorthin, und `guppi_runtime` ist darin nicht installiert. Die Skripte rufen deshalb `.venv\Scripts\python.exe` direkt auf und setzen
   `PYTHONPATH=src`. Wer die venv neu anlegt (`setup_windows.bat`), hat beides sauber.
3. **Engine:** llama.cpp-Builds unter `engines/llama.cpp/<build>/`. Standard ist **b11160** (CUDA 13); gewählt wird sie in `runtime/config/llama_server.yaml`, für einen
   einzelnen Lauf mit der Umgebungsvariable `GUPPI_ENGINE_BUILD`.
4. **Modelle:** GGUF-Dateien unter `<modelle>\<Anbieter>\<Modell>-GGUF\`. Eingebunden wird ein Modell über ein Rezept (siehe unten).
5. **Lokale Ordner:** Eingecheckte Dateien nennen die Ordner dieses PCs nur als Platzhalter: `<modelle>` (Modelldateien), `<modelle-test>`, `<hermes>`,
   `<projekte>` (Projektordner) und `<guppi>` (dieser Ordner). Die echten Ordner stehen in `runtime/config/local_paths.yaml`; diese Datei ist **nicht im Git**:
   ```yaml
   local_paths:
     modelle: 'D:\Modelle\lokale-modelle'
   ```
   Fehlt der Eintrag `modelle`, bleibt der GPU-Canary aus, wie auf jedem fremden PC. Gelesen wird die Datei von `guppi_runtime/local_paths.py`.

## Starten und Beenden

| Datei | Zweck |
|---|---|
| `START_SEDRA.bat` | **Der eine Start** (ersetzt ERSTER_START.bat, START_GUPPI.bat und GUPPI_EINRICHTEN_UND_STARTEN.bat): richtet ein, was fehlt, und öffnet SEDRAs eigenes Fenster (App-Modus von Edge oder Chrome) mit der Übersicht der Oberflächen. `START_SEDRA.bat <id>` startet direkt in eine Oberfläche (nur dieser Start; `cockpit`, `minimal`, `paperclip`, `guppi-xp` = der alte Desktop, oder eine eigene), `--gewaehlt` in die in `uix.yaml` gewählte. Läuft schon ein SEDRA – auch aus einem alten Paket –, kein zweiter Start: die Konsole nennt PID und Ordner; `--replace` beendet ihn. Fenster schließen beendet den Server und entlädt das Modell. `START_GUPPI.bat` ist der alte Name und leitet weiter. In jeder Oberfläche: der runde Knopf unten rechts (Alt+S) wechselt die Oberfläche, führt zur Übersicht und stellt Darstellung und Schriftgröße ein (Build 22). |
| `READY_TEST_WINDOWS.bat` | PC-Diagnose → `workspace/GUPPI_OS/runtime_data/reports/` |
| `runtime/run_doctor.bat` | `guppi doctor`: Startbericht (READY oder SAFE_MODE, mit dem Grund jedes abgeschalteten Teils) |
| `runtime/run_tests.bat` | alle Tests (dauert lange; im Alltag nur die betroffenen, siehe unten) |

### macOS und Linux

| Datei | Zweck |
|---|---|
| `START_SEDRA.command` | macOS: Doppelklick im Finder. Beim allerersten Mal verlangt macOS eventuell Rechtsklick → Öffnen, oder einmal `chmod +x START_SEDRA.command start_sedra.sh` im Terminal. |
| `start_sedra.sh` | macOS und Linux aus dem Terminal: `./start_sedra.sh`, Optionen wie unter Windows (`--open` normaler Browser, `--replace`). |

Der erste Lauf legt `runtime/.venv` mit dem `python3` des Systems an (3.11 oder neuer; macOS: `xcode-select --install` oder python.org) und installiert PyYAML sowie, wenn erreichbar, dulwich. Danach öffnet sich die Oberfläche als eigenes Fenster, wenn Chrome, Edge, Chromium oder Brave installiert ist (`/Applications/…` oder im PATH), sonst im Standardbrowser; dann beendet `ctrl+C` im Terminal den Server.

Unterschiede zu Windows, Stand 14.10.2026:
- Die Prozessprüfung beim Start (zweite Oberfläche, übrig gebliebene Modell-Server) und die Liste fremder Prozesse im Fenster Modelle gibt es nur unter Windows (PowerShell). Das Fenster Modelle zeigt auf macOS/Linux nur den eigenen Modell-Server.
- Modelle brauchen eine llama.cpp-Engine für das jeweilige System (macOS: Metal-Build) unter `engines/llama.cpp/<build>/` und Rezepte in `local_config/role_routing.yaml`; die GPU-Werkzeuge (`nvidia-smi`, GPU-Canary) sind NVIDIA-spezifisch und melden auf dem Mac „keine Messung“. Ohne Engine startet die Oberfläche trotzdem und plant nur.
- Die Tests laufen mit `runtime/run_tests.sh`; Windows-abhängige Tests überspringen sich mit Grund (`tests/env_skip.py`).

Die Oberfläche **nie hart beenden**, etwa mit dem Task-Manager: Sonst bleibt ein llama-server übrig, der den VRAM belegt. `uix_start` räumt solche Reste beim
nächsten Start auf. Einen Server, dessen Starter noch lebt (zum Beispiel einen Messlauf), meldet es nur.

## Konfiguration

**Paket-Vorgaben** in `runtime/config/` (im Git):

| Datei | Inhalt |
|---|---|
| `llama_server.yaml` | eigener Server: Engine-Build, Port 8089, MTP global an/aus, GPU-Canary (Modell, Port 8093) |
| `role_routing.yaml` | Vorgaben für das Routing (die tatsächlichen Rezepte stehen im Projektordner) |
| `job_supervisor.yaml`, `resource_scheduler.yaml`, `model_loader.yaml`, `token_policy.yaml` | Jobs, Reservierungen (VRAM-Reserve), Laden, Token-Budgets |
| `permission_levels.yaml` | Aktionen → Stufe 0–6, Aktionen, die nie automatisch laufen |
| `self_development.yaml` | E1/E2/E3-Regeln, automatische Entwicklung und Aktivierung (beides AUS) |
| `sandbox.yaml` | microVM-Grenzen |
| `web_access.yaml` | erlaubte Hosts für das lesende Web-Werkzeug |
| `kev.yaml` | lokaler Verifier „Kev“ (aus, bis ein Server bereitsteht) |

**Maschinenlokal** in `workspace/GUPPI_OS/local_config/` (nicht im Git):
- `role_routing.yaml`: **die Rezepte**. Vor jeder Änderung eine Sicherung `role_routing.yaml.bak-<Datum>-<Grund>` anlegen.
- `switches.yaml`: An/Aus-Schalter (context_manager, job_supervisor, llama_server, mtp …), gemeldet als `LOCAL_SWITCHES_APPLIED`.
- `routing_profiles.yaml`: Modellkombinationen, die der Captain umschalten kann (`guppi routing-profile`).

## Modelle und Rezepte

Ein Rezept nennt Modell, GGUF-Datei, Rollen, Servereinstellungen (`kv_cache_type`, `flash_attn`, `ubatch`, `n_cpu_moe`, `mtp`, `reasoning`), den gemessenen VRAM und
die Kontextgrenzen (`recommended`, `maximum`, `tiers`). **Die Standardeinstellung seit dem 11./12.10.:** Flash Attention an, KV q8_0, ubatch 512, 1 Slot, Engine b11160.

**Der kurze Weg (seit 14.10.2026):** Fenster **Werkstatt (Modelle) → Neues Modell** – oder im Kommando (Strg+K) „neues Modell“ tippen; die Werkstatt-Leiste oben im Fenster sagt danach, was als Nächstes dran ist (Laden, Kurztest, Standardtest). Seit Build 5 beginnt alles im **Deck**: ein Eingabefeld „Was willst du tun?“, Freigaben und laufende Karten daneben; Erscheinungsbild (Retro/Klar/Nacht) im Startmenü.
1. **Datei wählen …** öffnet den Dateidialog dieses PCs (Explorer unter Windows, Finder auf dem Mac, zenity unter Linux); alternativ aus dem Modellordner (`local_paths.yaml: modelle`) wählen oder den Pfad eingeben.
2. SEDRA liest den GGUF-Kopf (Name, Architektur, Quantisierung, Größe, Kontextgrenze, Schichten, Experten) und schlägt ein Rezept vor: Rollen und Standard-Kontext sind änderbar, die Rezept-ID auch; Servereinstellungen sind die Standards (Flash Attention an, KV q8_0, ubatch 512, alle Schichten auf der GPU). Der genaue YAML-Block ist aufklappbar.
3. **Rezept anlegen (Freigabe)**: eine Mission mit Gate `change_routing`; nach „Freigeben und anwenden“ wird genau dieser Block an `local_config/role_routing.yaml` angehängt (Sicherung `.bak-<Datum>-uix`, Prüfung mit dem echten Lader, Audit `ROUTING_RECIPE_ADDED`). Das Rezept ist **sofort** nutzbar, kein Neustart.
4. In der Liste darunter **Laden** (unter GPU-Sperre wie bisher), dann **Testen**: eine kurze Frage an das Modell mit Antwort, Sekunden und Token/s.
Danach gilt der lange Weg für das, was der kurze nicht misst: Tempo, Kontextleiter, S0, Standardtest. Bis dahin steht im Rezept kein `measured_vram_gb`; der Lader schätzt aus der Dateigröße.

Der lange Weg (Messen und Qualifizieren):
1. Rezept anlegen, zunächst mit `enabled: false`. Davor die Sicherung der Rezeptdatei.
2. Tempo messen: `benchmarks/moe_sweep.py` bei MoE-Modellen, bei dichten Modellen eine eigene kurze Messung.
3. Kontext messen: `benchmarks/context_ladder.py <projekt> <rezept> --probes 2`. Das ist ein Nadeltest bis zur Grenze, mit 1 GiB VRAM-Reserve und Prüfung auf Treiberfehler.
4. Verbindungsprüfung S0: `benchmarks/connection_check.py` (Werkzeugaufruf, lange Argumente, Fenster füllen).
5. Standardtest: `benchmarks/devvm_build.py <projekt> --spec bench_std --coder <rezept> --all-models <rezept>`.
6. Ein- oder Umschalten und Kontextgrenzen setzen: **nur mit Freigabe des Captains**.

Modelle entfernen nur über `guppi model-remove-preview` → `guppi model-remove --plan …` (Gate). Die Dateien kommen in die Quarantäne, die Rezepte werden
ausgeschaltet. Endgültig löscht der Captain die Quarantäne von Hand. Welche Modelle wofür taugen: [MODELLE.md](MODELLE.md).

## GPU: Lease, Canary, Reserve

- **Nur ein Prozess lädt Modelle.** Jedes Skript, das Modelle startet, nimmt die GPU-Lease von `testlab.py`, mit Wartezeit statt Abbruch. Wer die Lease gerade hält:
  `TestLab(default_path(projekt)).holder()`. Läufe anderer Sitzungen **nie** beenden. Prozesse werden nur über ihre eigene PID gestoppt, nie per Namensmuster.
- **Rezepte, Engine oder Schalter nie ändern, solange ein Lauf die GPU benutzt.** Lieber ein kleines Skript schreiben, das auf die Lease wartet, kurz ändert
  und sie wieder freigibt.
- **Canary:** Nach jedem Windows-Start und nach jedem Server-Absturz läuft zuerst der GPU-Selbsttest (`runtime_data/gpu_canary.json`). Schlägt er fehl, ist
  meist die Übertaktung der Grafikkarte schuld: im NVIDIA-Programm den **Debug-Modus** einschalten. Der Modus springt nach einem Neustart zurück.
- **VRAM-Grenze:** bis 11,5 GB nutzen, 1 GiB Reserve für den Kontext.

## Tests

```
cd runtime
set PYTHONPATH=src;tests
.venv\Scripts\python.exe -m unittest tests.test_runtime tests.test_job_supervisor
```

- **Nur die betroffenen Tests** laufen lassen: die Tests des geänderten Codes und seiner Nachbarn. Neue Tests kommen in die passende Testdatei.
- Tests sind isoliert (`tests/host_isolation.py`): kein echtes nvidia-smi, lms, powercfg oder PowerShell, eigene Ports und eigene Sandbox-Konfiguration, keine festen Zeitfenster.
- Der Grenztest des Kerns: `tests.test_core_boundary_src`.

## Messungen und Ketten

Ergebnisse unter `workspace/GUPPI_OS/runtime_data/measurements/`:
- `logs/devvm_build_<spec>_<zeit>.json/.log`: jeder Bau, mit Token, Aufrufen, Stufen und Fehlern.
- `context_ladder_*`, `moe_sweep_*`, `mtp_tune_*`: Kontext und Tempo.
- `night_<datum>/`, `day_<datum>/`: Ketten mehrerer Läufe (`queue.log`, `summary.json`).
- `benchmarks/model_compare.py` erzeugt daraus [MODELL_VERGLEICH_ERGEBNISSE.md](MODELL_VERGLEICH_ERGEBNISSE.md).

**Bauweg (geändert 20.10.2026, Linie L1):** Gebaut wird mit `devvm_build.py` direkt, Standardbefehl `--profile standard` (siehe [ENTWICKLUNG.md](ENTWICKLUNG.md#die-einheitliche-linie-captain-20102026)). Die Ketten-Skripte (`day_queue_*`, `night_queue_*`, `mtp_*`) sind Archiv unter `benchmarks/archiv/` (siehe Werkzeug) und nur noch Dokumentation. Buildflow (`guppi buildflow`) ist Reserve, kein Standardweg.

Früher galt: Eine Kette ist ein Python-Skript in `benchmarks/` (Beispiel: `night_queue_2026-10-11.py`). Es startet jeden Schritt als eigenen Prozess, prüft nach jedem Schritt
den Canary und schreibt eine Zusammenfassung. Ein Folge-Glied wartet nur auf das Ende der laufenden Kette (`night_queue_2026-10-11_b.py`) und stoppt sie nie.

## Cloud-Zugang und KI-Labor (Stand 20.10.2026)

Cloud-Modelle laufen nur über den API-Zugang (`models/cloud_api.py`, Einstellungen `cloud_settings.py`). **Standard ist aus:** `config/cloud_providers.yaml` hat `enabled: false` (Hauptschalter) und je Anbieter `enabled: false`; erst beide an, plus Modell und Schlüssel, schalten den Weg frei. Schlüssel liegen verschlüsselt (Windows-DPAPI) in `local_config/cloud_keys.json` oder als Umgebungsvariable `GUPPI_SECRET_<ANBIETER>_<ID>`. Jeder Aufruf geht durch den Inhaltsschutz und steht im Audit (`SG_MODEL_CALL`); ohne Logbuch verweigert der Inhaltsschutz den Aufruf. Das **KI-Labor** (Werkstatt, Werkzeug `labor`) testet Verbindung und Modelle auf Knopfdruck. Quellen: `docs/CHANGELOG.md` (Build 24+, 16.10.), `DOKUMENTATION_KLAUS_TORSTEN_2026-10-16.md`.

## Befehle

`guppi <befehl>` beziehungsweise `python -m guppi_runtime <befehl>` (mit `--root workspace/GUPPI_OS --architecture …`, siehe `START_SEDRA.bat`):

| Bereich | Befehle |
|---|---|
| System | `doctor`, `demo`, `audit-repair`, `list-tools`, `list-skills`, `route`, `mission-route` |
| Missionen | `new-mission`, `mission-inputs`, `run`, `resume`, `execution-check`, `list-missions`, `approve`, `recover` |
| Kandidaten | `candidate-status`, `candidate-test`, `candidate-test-verify`, `candidate-cleanup`, `self-…` (Selbst-Integration und Rücknahme) |
| Modelle | `model-status`, `model-chat`, `model-doctor`, `model-scan`, `model-catalog`, `model-pass`, `model-benchmark`, `routing-profile`, `model-remove-preview`, `model-remove`, `model-restore` |
| Hardware | `hardware`, `hardware-state`, `hardware-inventory`, `hardware-preview`, `hardware-dashboard`, `tuning-plan`, `tuning-run` |
| Sandbox | `sandbox-doctor`, `sandbox-preview`, `sandbox-run`, `sandbox-history`, `dev-image-preview`, `dev-image-import` |

## Störungen

| Zeichen | Ursache und Abhilfe |
|---|---|
| Modell liefert Zeichensalat, Canary schlägt fehl, `nvlddmkm`-Ereignisse | Grafikkarte übertaktet: NVIDIA-Debug-Modus an (nach Neustart erneut), dann den Canary laufen lassen. |
| Jedes Laden scheitert mit `hardware_pressure` | Ein übrig gebliebener llama-server hält VRAM. SEDRA über `START_SEDRA.bat` neu starten; `uix_start` räumt auf. |
| Skript wartet „waiting for the GPU lease“ | Ein anderer Lauf hält die GPU. Halter prüfen (siehe oben) und warten; nicht beenden. |
| `boot` meldet SAFE_MODE oder `*_error` | Eine Konfigurationsdatei fehlt oder ist ungültig; der Teil ist aus. `guppi doctor` nennt den Grund. |
| Windows verweigert das Ersetzen einer Datei („Zugriff verweigert“) | Ein Leser hält sie offen. Kurz wiederholen oder in-place schreiben, vorher sichern. |
| Tests finden `yaml` oder `guppi_runtime` nicht | Venv-Python direkt mit `PYTHONPATH=src;tests` aufrufen (siehe Einrichtung). |
| Audit-Log nach Absturz nicht lesbar | `guppi audit-repair` verschiebt nur die zerrissene letzte Zeile. |
