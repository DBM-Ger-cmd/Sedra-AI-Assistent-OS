# SEDRA – Entwickler-Archiv, Build 19 (Stand 15.10.2026)

Dieses Archiv gibt Entwicklern einen vollständigen Einstieg in SEDRA (technischer Name GUPPI) mit dem Stand, in dem das **KI GateWay** in SEDRA eingebaut wurde.

## Was im Archiv liegt

| Ordner / Datei | Inhalt |
|---|---|
| `00_LIES_MICH.md` | diese Seite: Inhalt, Einstieg, Hinweise zum Stand |
| `dokumentation/` | sieben Dokumente mit Überblick, Architektur, KI-GateWay-Einbindung, Werkzeugen, Entwicklung, Entscheidungen und Chronik |
| `quellcode/` | der Arbeitsstand des Pakets (Build 19) ohne `.git`, ohne Modelle, ohne Laufzeitdaten |
| `git/sedra_gupti_history.bundle` | die vollständige Git-Historie bis Commit `2692c37` (Build 19) |
| `git/GUPPI_Runtime_v1.20_Build_019_2026-10-15.patch` | der Patch von Build 18 auf Build 19 (alles, was das KI GateWay und START_SEDRA ändert) |
| `git/aenderungen_START_SEDRA_und_Auswahl.patch` | nicht committete Änderungen nach Build 19: ein einziger Start (`START_SEDRA.bat`), Oberflächenauswahl beim Start, `uix_start --liste` |
| `PRUEFSUMMEN.sha256` | SHA-256 aller Dateien im Archiv |

## Schnelleinstieg

1. **Lesen:** `dokumentation/01_UEBERBLICK_UND_HERKUNFT.md`, dann `02_ARCHITEKTUR.md`.
2. **Das KI GateWay verstehen:** `dokumentation/03_KI_GATEWAY_EINBINDUNG.md` (das Herzstück des Archivs).
3. **Starten:** Windows `START_SEDRA.bat` – der eine Start. Beim ersten Mal richtet er die Umgebung ein; danach fragt er, welche Oberfläche starten soll. macOS/Linux: `./start_sedra.sh`. Details: `docs/BETRIEB.md` im Quellcode.
4. **Tests:** `runtime/run_tests.sh` (Linux/macOS) bzw. `runtime/run_tests.bat`. Anleitung in `dokumentation/05_ENTWICKLUNG_TESTS_BUILD.md`.
5. **Git-Historie holen:** `git clone git/sedra_gupti_history.bundle sedra` – danach liegt der gesamte Verlauf lokal vor.

## Hinweise zum Stand

- **Build-Nummer:** Im Commit `2692c37` steht `BUILD.txt` noch auf 18. Die Arbeitskopie in `quellcode/` trägt Build 19; diese Änderung ist noch nicht committet.
- **Nicht im Archiv:** Modelldateien (`*.gguf`), die llama.cpp-Engine, `runtime/.venv`, `runtime/portable/`, lokale Konfiguration (`runtime/config/local_paths.yaml`) und Laufzeitdaten. Das steht so in `.gitignore`.
- **Windows: `runtime\portable\` fehlt im Archiv – die Ersteinrichtung bricht deshalb ab.** Der Ordner ist nicht im Repository (`.gitignore`) und nicht im Paket. `Ersteinrichtung.ps1` braucht aber `runtime\portable\sandbox\RELEASE_LOCK.json` und das gepinnte Wheel `runtime\portable\sandbox\wheels\microsandbox-0.7.4-cp310-abi3-win_amd64.whl`. Fehlermeldung: „Offline bundle refused … RELEASE_LOCK.json“. **Abhilfe:** den Ordner `runtime\portable\` aus einer funktionierenden SEDRA-Installation in `quellcode\runtime\` kopieren und `START_SEDRA.bat` erneut starten. Ist keine vorhanden, muss der Ordner beim Captain bzw. aus der Quelle des SDK-Wheels kommen; er wird nicht erzeugt oder nachgebaut, weil die Prüfsummen die Herkunft sichern sollen.
- **Ohne Internet:** Python- und PyYAML-Dateien nach `runtime\portable\downloads\` legen (Liste im Skript).
- **Der Ordner `quellcode/architecture/`** enthält die älteren Architekturstände (v1.17, v1.20). Die Tests brauchen ihn. Das aktuelle Gesamtbild steht in `docs/ARCHITEKTUR.md`.
- **Sprache:** Die Dokumentation ist deutsch. Code, Bezeichner und Audit-Ereignisse sind englisch oder technisch benannt (`SG_*`, `GW_*`, `UIX_*`).
- **Stand des KI GateWay:** Der Vorgang ist gebaut und getestet, aber ohne echten Cloudweg. Die Cloud ist bewusst **simuliert**. Offene fachliche Entscheidungen stehen in `06_ENTSCHEIDUNGEN_UND_OFFENES.md`.
- **Umgebungsfehler:** Ein bekannter Test (`library_not_built`) schlägt nur auf Systemen ohne gebaute Bibliothek fehl. Er ist kein Fehler im Code. Ein Test, der nur auf einem bestimmten PC laufen kann, überspringt sich mit Grund (`tests/env_skip.py`).
