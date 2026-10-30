# Entscheidungen: minimale SEDRA-USB-Version auf K:\

Stand: 30.10.2026. Diese Datei hält die Entscheidungen des Captains fest, damit der Plan der Cloud-Session (Branch der Session, `docs/PLAN_USB_STICK_MINIMAL.md`) sie übernimmt.

## Umfang
- Nicht das ganze Projekt auf den Stick.
- Enthalten: Kern (`runtime/src/guppi_runtime/`), Harness-Shell (Standard in `uix.yaml`), Cockpit, Paperclip, Translator-Shell (Ordner `uix/shells/fisch`, intern noch „fisch“).
- Nicht enthalten: Start-Shell, Minimal, Gateway, Guppi-XP, Wissensbasis, Vorlagen.
- Die Translator-Shell braucht zusätzlich: Werkzeuge `uebersetzer`, `nachrichten`, `transkript`, `rekorder`; Kern-Module `fisch/` und `sprache/`; `ui/sprache.js`, `ui/wechsel.js`; `fenster/rekorder.html`. Spracherkennung braucht einen installierten Anbieter.
- Eine „Transkript-Shell“ gibt es nicht. Gemeint ist die Translator-Shell.

## Pfade (Option B)
- `engines` und `workspace` werden nicht verlinkt (exFAT kennt keine Junctions/Symlinks).
- Das Programm bekommt die Ordner über die Konfiguration (`local_paths.yaml` bzw. `runtime/src/guppi_runtime/local_paths.py`) und zeigt direkt auf die Stick-Ordner.
- Vor der Code-Änderung prüfen, wo Pfade fest verdrahtet sind (rund 186 Treffer in 45 Dateien).
- `Test-PortableRuntime.ps1` lehnt Verknüpfungen im Paket ohnehin ab; das Paket auf dem Stick besteht aus echten Ordnern.

## Modelle (vier, aus `I:\KI-Daten\modelle`)
1. Qwen3.6-35B-A3B, `unsloth/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-IQ4_XS.gguf` (17,73 GB), Hauptmodell
2. Qwen3.5-9B-MTP, `unsloth/Qwen3.5-9B-MTP-GGUF/Qwen3.5-9B-Q6_K.gguf` (7,68 GB), Ausweichmodell
3. Gemma 4 12B QAT, `lmstudio-community/gemma-4-12B-it-QAT-GGUF/gemma-4-12B-it-QAT-Q4_0.gguf` (6,98 GB) plus `mmproj-gemma-4-12B-it-QAT-BF16.gguf` (0,18 GB), Prüfer
4. Nemotron 3.5 Bolt E4B, `lmstudio-community/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF/NVIDIA-Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf` (6,18 GB), Agenten

Gesamt rund 39 GB. Die Modelle bleiben auf I:\; der Stick bekommt Kopien.

## Offen
- Der Plan muss die Stellen für die Pfade prüfen und festlegen, bevor Code geändert wird.
- Die Abnahme auf dem Rechner des Kollegen (RAM für Qwen3.6: mindestens 18 GB) ist noch nicht geklärt.
