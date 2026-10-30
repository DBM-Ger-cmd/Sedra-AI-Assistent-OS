# Plan: SEDRA als Minimalversion auf dem USB-Stick (K:\)

**Stand:** 30.10.2026 · **Basis:** `origin/main` (bf20ff5) · **Entscheidungen:** `docs/ENTSCHEIDUNGEN_USB_STICK.md` (gelten, nicht neu verhandeln)
**Ersetzt:** den Entwurf von `origin/plan/usb-stick-minimal` (07f49fa). Dort stand „Modelle nicht Teil des Plans“; das ist durch die Entscheidung des Captains überholt (vier Modelle, Abschnitt 3).

## 1. Ergebnis in Kürze

- Auf K:\ (GIGASTONE, exFAT, 125,8 GB frei) liegt `K:\SEDRA\`: Kern, Harness-Shell (Standard), Cockpit, Paperclip, Translator-Shell (Ordner `fisch`), plus die vier Modelle unter `K:\SEDRA\modelle\`.
- Pfade laufen über die Konfiguration. Der Code braucht dafür genau eine Änderung: relative Ordner in `local_paths.yaml` zählen ab dem Laufzeitordner (`runtime\`). Damit zeigt `..\modelle` auf `K:\SEDRA\modelle`, egal welcher Laufwerksbuchstabe.
- Keine Verknüpfungen (Junctions, Symlinks) im Paket. Der Bau (`stick_paket.py`) bricht bei einer Verknüpfung ab.
- Start: `K:\SEDRA\START_SEDRA.bat` (Standard `--gewaehlt`, Harness), mit dem portablen Python `runtime\portable\python\current\`.

## 2. Befunde zum Ausgangsstand

| Punkt | Befund | Folge |
|---|---|---|
| Hart verdrahtete Pfade | Suche `engines|workspace|parents[n]|Path.home()|Laufwerk` in `runtime/src`: 276 Treffer in 77 Dateien (grobe Suche, viele Kommentare und Beispiele). Die Laufzeitpfade sind **relativ zum Paket**: `workspace\GUPPI_OS` über `parents[3]`, `engines` über `engine_provision.DEFAULT_ROOT`. Beides stimmt auf dem Stick ohne Verknüpfung. | Kein Umbau von 45 Dateien nötig. Einzige Stelle mit PC-Bezug: die Modellordner in `local_paths.yaml` (Code: `runtime/src/guppi_runtime/local_paths.py`). |
| Modellordner | `local_paths.yaml` hält `modelle: 'I:\KI-Daten\modelle'`. Platzhalter `<modelle>` in `llama_server.yaml`, `gpu_canary`, `uix_server` (Modellwahl). | Option B umgesetzt (Abschnitt 4). |
| Start ohne Netz | `START_SEDRA.bat` ruft `Ersteinrichtung.ps1` nur auf, wenn `runtime\portable\python\current\python.exe` fehlt. | Auf dem Stick ist das Python vorhanden. Der Aufruf bleibt im Paket, lädt aber nur bei fehlendem Python. |
| Engine | `engines\llama.cpp\b11160\` liegt auf dem Bau-PC (Hauptcheckout, 715 MB inkl. Ordner; `b11160` allein ist der Bezug). `engine_source: guppi`, kein LM-Studio-Rückfall. | Kopie, kein Download. |
| Portables Python | Auf dem Bau-PC liegt ein fertig gebauter Bundle unter `runtime\portable\python.aus\current\` (Python 3.14.8, PyYAML 6.0.3, Audio-Wheels, `sdk_version: none`, Qualifikation `ASSEMBLED_NOT_PC_TESTED`). Das Verzeichnis heißt `python.aus`, nicht `current`. | Kopie nach `runtime\portable\python\current\`, Prüfung über `Test-PortableRuntime.ps1`. Der Bundle-Name `python.aus` bleibt im Bau-PC unverändert. |
| Fenster `fenster/rekorder.html` (Entscheidung) | Im Repository nicht vorhanden (Suche über den ganzen Baum). | **Offen**, siehe Abschnitt 8. |
| Übersicht `start` | Entscheidung: Start-Shell nicht enthalten. Der Befehl ohne Argument im `START_SEDRA.bat` führt in das Menü mit der Übersicht. | Auf dem Stick wird die Standard-Oberfläche per `uix.yaml` gesetzt; der Menüpfad bleibt, nutzt die Übersicht aber nicht als Standard. |

## 3. Umfang und Modelle

### 3.1 Umfang (Liste `runtime/benchmarks/stick_liste.txt`)

- Kern: `runtime/src/guppi_runtime/core/`, dazu alles, was der Start über statische Importe braucht (Importhülle, ermittelt von `stick_paket.py`).
- Harness: `uix/shells/harness/`, `guppi_runtime/harness/`. Standard in `local_config\uix.yaml` des Sticks.
- Cockpit: `uix/shells/cockpit/`. Paperclip: `uix/shells/paperclip/`.
- Translator-Shell: `uix/shells/fisch/`, `guppi_runtime/fisch/`, `guppi_runtime/sprache/`, Werkzeuge `uebersetzer`, `nachrichten`, `transkript`, `rekorder`, `uix/ui/` (enthält `sprache.js` und `wechsel.js`).
- Oberflächenbasis: `uix/js/`, `uix/css/`, `uix/ui/`.
- Architektur-Pflichtordner `architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT/` (Pflicht für `--architecture`).
- Konfiguration `runtime/config/` (ohne `local_paths.yaml`, die schreibt der Stick, Abschnitt 4).
- Start: `START_SEDRA.bat`, `LICENSE`, `Ersteinrichtung.ps1`, `Erststart_Konfig.ps1`, `Test-PortableRuntime.ps1`, `benchmarks/engine_download.py`.
- Nicht enthalten: Start-, Minimal-, Gateway-, Guppi-XP-, Wissensbasis-Shell, Vorlagen, das Projekt als Ganzes, Entwicklungswerkzeuge, Tests, Dokumentation außer `README`-Kurzfassung.

### 3.2 Modelle (Kopien; die Originale auf `I:\KI-Daten\modelle` bleiben)

| Modell | Quelle (relativ zu `I:\KI-Daten\modelle`) | Größe |
|---|---|---|
| Qwen3.6-35B-A3B (Hauptmodell) | `unsloth\Qwen3.6-35B-A3B-GGUF\Qwen3.6-35B-A3B-UD-IQ4_XS.gguf` | 16,51 GiB |
| Qwen3.5-9B-MTP (Ausweichmodell) | `unsloth\Qwen3.5-9B-MTP-GGUF\Qwen3.5-9B-Q6_K.gguf` | 7,16 GiB |
| Gemma 4 12B QAT (Prüfer) | `lmstudio-community\gemma-4-12B-it-QAT-GGUF\gemma-4-12B-it-QAT-Q4_0.gguf` + `mmproj-gemma-4-12B-it-QAT-BF16.gguf` | 6,50 + 0,16 GiB |
| Nemotron 3.5 Bolt E4B (Agenten) | `lmstudio-community\NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF\NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf` | 5,76 GiB |

Summe rund 36 GiB. Auf dem Stick liegen sie unter `K:\SEDRA\modelle\` mit denselben Unterordnern. Platz: 125,8 GB frei, Rest nach dem Kopieren rund 85 GB. Der Stick hat keinen Platz-Engpass.

Eine Einordnung: `unsloth\Qwen3.5-9B-MTP-GGUF\...` ist im Repository der Canary-Modellpfad (`llama_server.yaml`, `<modelle>`). Die anderen drei haben im Repository kein Rezept. Ein Modell startet über SEDRA erst, wenn ein Rezept (Modellprofil) es nennt. Die Prüfung in Abschnitt 6 startet deshalb den Canary-Pfad.

## 4. Option B: Pfade über die Konfiguration

- `runtime/src/guppi_runtime/local_paths.py`: `load()` übersetzt relative Ordner über `folder()` gegen `RUNTIME` (= `runtime\`). Absolute Pfade bleiben unverändert. Test: `runtime/tests/test_local_paths.py::test_a_relative_folder_counts_from_the_runtime_folder`.
- Stick-Konfiguration `K:\SEDRA\runtime\config\local_paths.yaml`:
  ```yaml
  local_paths:
    modelle: '..\modelle'
  ```
  Keine PC-Pfade (`I:\`, `E:\`) im Stick.
- Keine weitere Code-Änderung: Engine und Laufdaten liegen relativ zum Paket.
- `local_config\uix.yaml` auf dem Stick wird mit `uix_start --als-standard harness` geschrieben (Standard Harness). Der Befehl läuft nur auf dem Stick.

## 5. Bau und Prüfung (Schritte)

| Schritt | Tätigkeit | Prüfung |
|---|---|---|
| S1 | Code: `local_paths.py` (relative Ordner), `stick_paket.py` (Liste, Importhülle, Kopie, Manifest), `stick_liste.txt`, Tests `test_local_paths.py`, `test_stick_paket.py`. | Tests grün (Abschnitt 6). |
| S2 | Vorab-Prüfung der Kopie: `stick_paket.py --pruefen` gegen den Worktree und den Hauptcheckout. | Plan-Liste ausgegeben (731 Dateien, Ausgabe im Bericht). |
| S3 | **Vor dem ersten Schreiben auf K:\** Kopierliste im Bericht (Abschnitt 7). | Bericht enthält Liste und Größen. |
| S4 | Kopie des Pakets nach `K:\SEDRA\` mit `stick_paket.py --ziel K:\SEDRA`; Manifest `STICK_MANIFEST.json`. | Manifest-Datei vorhanden, Anzahl Dateien und Summe stehen im Bericht. |
| S5 | Modelle nach `K:\SEDRA\modelle\` kopieren; Größen vergleichen. | Größe je Datei gleich dem Original. |
| S6 | Stick-Konfiguration schreiben: `runtime\config\local_paths.yaml`, `local_config\uix.yaml` (Harness). | Datei-Inhalt geprüft. |
| S7 | `Test-PortableRuntime.ps1` auf K:\ laufen lassen. | Ausgabe im Bericht. |
| S8 | Start: `START_SEDRA.bat --gewaehlt` (Harness); HTTP-Abfrage der Oberfläche. | HTTP 200, keine Abstürze. Protokoll `runtime\einrichtung.log`. |
| S9 | Engine und Modell: Canary-Modell (Qwen3.5-9B-MTP) über den Engine-Start prüfen. | Antwort des Modells oder klare Fehlerangabe. |

## 6. Prüfungen im Repository

- `runtime\tests\test_local_paths.py`, `runtime\tests\test_stick_paket.py` (Importhülle, Liste, Kopie ohne Verknüpfung, Manifest).
- Gesamtlauf der Unit-Tests: `runtime\` mit `PYTHONPATH=src;tests`, `python -B -m unittest discover -s tests -p "test_*.py"`. Fehlstand wird im Bericht mit Ausgabe benannt.

## 7. Kopierliste (vor dem ersten Schreiben auf K:\ im Bericht)

Quelle `repo` ist der Worktree dieser Session, Quelle `bestand` der Hauptcheckout. Die Liste ist in `stick_liste.txt` festgelegt. Die Zählung kommt aus `stick_paket.py --pruefen`.

- Programmdateien: Importhülle und Ordner nach Abschnitt 3.1.
- `bestand engines/llama.cpp/b11160/` → `K:\SEDRA\engines\llama.cpp\b11160\`.
- `bestand runtime/portable/python.aus/current/` → `K:\SEDRA\runtime\portable\python\current\`.
- Modelle (Abschnitt 3.2) nach `K:\SEDRA\modelle\`.
- Keine Stick-Dateien außerhalb von `K:\SEDRA\`.

## 8. Offen

1. `fenster/rekorder.html` (Translator-Shell) fehlt im Repository. Ohne die Datei zeigt das Fenster des Rekorders keine Seite. Vorschlag: nicht nachbauen, sondern als offen melden, Captain entscheidet.
2. Keine NVIDIA-Abnahme auf einem zweiten PC (Q8). Der Testrechner hat RTX 4070 Ti (12 GB), Treiber 617.42.
3. Zweiter PC ohne Netz und ohne Python (S8 im früheren Entwurf): nicht geprüft, weil nur ein Bau-PC zur Verfügung steht.
4. Laufdaten: `workspace\` und `runtime_data\` entstehen auf dem Stick (Q9 Standard, bis gemessen).
5. Modellrezepte für Gemma, Nemotron und Qwen3.6: nicht angelegt (Abschnitt 3.2).
6. Q5 (Fenster schließen) bleibt wie heute: Fenster schließen beendet SEDRA.
7. Hashes der großen Modelle: nur Größenvergleich in S5. Die SHA-256-Prüfung der Modelle ist nicht gemacht.

## 9. Was nicht geändert wird

- `local_config/` im Repository (nur der Captain gibt es frei). Die Konfiguration des Sticks liegt nur auf K:\.
- Kein Push, kein Merge in `main`.
