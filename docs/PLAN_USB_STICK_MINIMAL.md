# Umsetzungsplan: SEDRA als Minimalversion auf dem USB-Stick (K:\)

**Stand:** 30.10.2026 · **Basis:** `origin/main` (bf20ff5) · **Status:** Plan, noch nicht umgesetzt
**Adressaten:** SEDRA-Entwickler-Agent (Umsetzung ohne Rückfrage, soweit Abschnitt 11 geklärt ist) und Captain (Entscheidung über die offenen Fragen in Abschnitt 11).

Zeichen im Text: **[OFFEN]** = Captain-Entscheidung nötig, bis dahin gilt der genannte Standard. **[GEMESSEN]** = im Repository nachgezählt. **[SCHÄTZUNG]** = nicht gemessen, beim Bau nachmessen.

---

## 0. Auftrag und Ergebnis in Kürze

- Auf dem Stick K:\ (GIGASTONE, exFAT, laut Captain 117 GiB frei) läuft eine **Minimalversion** von SEDRA. Enthalten: Kern, Harness-Shell, Cockpit, Paperclip, Transkript-Shell (Begriffe in Abschnitt 1.2). Modelle sind nicht Teil des Plans. Das Projekt geht **nicht** vollständig auf den Stick.
- Der Stick enthält die Dateien für **Windows x64**. Start über `K:\SEDRA\START_SEDRA.bat` mit einem **portablen Python** unter `runtime\portable\python\current\`, ohne Installation und ohne Pfade dieses PCs.
- Der Platzbedarf ist klein: rund **0,7 GB** mit Engine, ohne Engine rund **0,1 GB**, plus Reserve für Laufdaten [SCHÄTZUNG]. Die 117 GiB sind also nicht der Engpass. Engpass sind die exFAT-Eigenschaften (Abschnitt 7) und die Pfade zu PC-spezifischen Ordnern (Abschnitt 6).
- Der Plan gliedert sich in Schritte S0 bis S11 (Abschnitt 9). Jeder Schritt hat eine Prüfung oder Abnahme.

---

## 1. Geprüfter Ausgangsstand

### 1.1 Korrekturen zur Aufgabenstellung

| Annahme aus dem Auftrag | Befund im Repository | Folge für den Plan |
|---|---|---|
| Ordner `kern` | Es gibt keinen Ordner `kern`. Der Kern steckt in `runtime/src/guppi_runtime/core/` (22 Dateien, 220 KiB [GEMESSEN]). `sprache/kern.py` ist ein anderer, gleichnamiger Teil der Sprachfunktion. | Standard: `core/` plus Importhülle (Abschnitt 2). Bestätigung durch den Captain: **Q1**. |
| `engines` und `workspace` nutzen Junctions | Der Produktpfad legt beide als **normale Ordner** an: `START_SEDRA.bat` macht `mkdir` für `workspace\GUPPI_OS`, `Erststart_Konfig.ps1` nutzt `$Root\engines` relativ zum Paketordner. `.gitignore` führt `engines/` und `workspace/` nur als ignorierte Ordner. Junctions tauchen nur in zwei Dokumenten auf: im Entwicklungs-Worktree (`docs/BAUBERICHT_HARNESS_STUFE1_2026-10-28.md`, Zeile 113) und als verworfene Option (`docs/UMSTIEG_A1_PLATTFORM_PLAN_2026-10-26.md`, Zeile 363). | **Kein Ersatz nötig** für den Stick. Worktrees bleiben auf dem PC und sind nicht Teil des Sticks. |
| `PLAN_USB_STICK_v1` als Grundlage | Im Logbuch (Einträge 30.10.2026 08:40 bis 08:42, Versionen v14 bis v17) und in `docs/NACHTRAG_OFFENE_PUNKTE_2026-10-30.md`, Zeilen 24 und 25, genannt. Die Datei liegt **nicht** im Repository. | Dieser Plan übernimmt nur die Entscheidungen, die im Logbuch stehen (Abschnitt 11, **Q6**). |
| „USB-Härtung“ als offener Punkt | Nur eine Tabellenzeile in `docs/ABGLEICH_UEBERGABEPAKET_SEDRA_2026-10-14.md`, Zeile 38: „EXISTING; USB-Härtung OPEN“. Keine Definition. | Vorschlag für die Definition in Abschnitt 8.3, Bestätigung **Q7**. |
| 117 GiB frei, Modelle 103 GiB auf `I:\KI-Daten\modelle` | Captain-Angaben, auf diesem Rechner nicht prüfbar. | Im Plan als Eingabe übernommen. |

### 1.2 Begriffe des Auftrags und ihre Entsprechung im Code

| Begriff (Auftrag) | Entsprechung im Repository | Größe [GEMESSEN] |
|---|---|---|
| Kern | `runtime/src/guppi_runtime/core/` plus alles, was der Start braucht (Importhülle, Abschnitt 2) | Importhülle gesamt: 221 Python-Dateien, 2,1 MiB |
| Harness-Shell | `runtime/src/guppi_runtime/uix/shells/harness/` (340 KiB) und `runtime/src/guppi_runtime/harness/` (Python, 276 KiB) | 616 KiB |
| Cockpit | `runtime/src/guppi_runtime/uix/shells/cockpit/` (168 KiB) | 168 KiB |
| Paperclip | `runtime/src/guppi_runtime/uix/shells/paperclip/` (152 KiB). Der Python-Teil `paperclip_pipeline.py` ist **nicht** in der Importhülle und hat keinen Importeur im Paket. | 152 KiB |
| Transkript-Shell | `runtime/src/guppi_runtime/uix/shells/fisch/` (124 KiB, im Code „Translator“, Modus „Transkript“) und `runtime/src/guppi_runtime/fisch/` (52 KiB, u. a. `transkripte.py`). | 176 KiB |
| Shell-Start | `runtime/src/guppi_runtime/uix/shells/start/` (28 KiB). Die Übersicht ist der Standardstart von `START_SEDRA.bat` (`--uebersicht`). | 28 KiB |

**[OFFEN] Q1:** Bestätigen, dass „Kern“ = `core/` und „Transkript-Shell“ = `fisch` (Modus Transkript) ist. Ist `paperclip_pipeline.py` Teil von Paperclip?

---

## 2. Welche Dateien auf den Stick gehören

Die Auswahl erfolgt in zwei Stufen. **Stufe A:** Die Python-Importhülle wird statisch ermittelt (Importanalyse ab `guppi_runtime.uix_start`, `guppi_runtime.uix_server` und `guppi_runtime.models.engine_provision`). Das Ergebnis ist 221 Dateien mit 2,1 MiB [GEMESSEN]. Die Analyse erfasst nur statische Importe. Dynamische Importe (`importlib`, `__import__`) finden sich im Paket an wenigen Stellen: `sandbox/provider.py` und `sandbox/worker.py` (Prüfung der SDK-Version, nur DevVM), `devenv/buildflow_cli.py` (Entwicklerwerkzeug) und `harness/antraege.py` (dort nur PyYAML). Die Stellen liegen außerhalb des Minimalumfangs; S3 prüft, ob etwas davon auf dem Startweg liegt. **Stufe B:** Die Oberflächen werden nach Ordnern ausgewählt (Tabelle unten).

### 2.1 Aufnahme (auf den Stick)

| Pfad im Repository | Zielpfad auf K: (unter `K:\SEDRA\`) | Begründung | Größe [GEMESSEN] |
|---|---|---|---|
| `START_SEDRA.bat` | `START_SEDRA.bat` | Einziger Start. | klein |
| `LICENSE` | `LICENSE` | 1 Byte, Lizenzhinweis. | 1 B |
| `README.md` | `README.md` | Wird durch eine Stick-Kurzfassung ersetzt, siehe S10. | 6 KiB |
| `architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT/` | gleicher Pfad | **Pflicht:** `START_SEDRA.bat` übergibt `--architecture`, `uix_start.py` bricht ohne den Parameter ab (`p.error`). | 856 KiB |
| `runtime/config/` (ohne `local_paths.yaml`) | `runtime\config\` | Alle Schalter- und Profildateien. `local_paths.yaml` ist nie im Repository und wird pro PC geschrieben (Abschnitt 6). | 152 KiB |
| `runtime/src/guppi_runtime/` **nur Importhülle aus Stufe A** | `runtime\src\guppi_runtime\` | Python-Kern, Harness, Fisch, Desk usw. | 2,1 MiB |
| `runtime/src/guppi_runtime/uix/shells/{cockpit,harness,paperclip,fisch,start}/` | gleicher Pfad | Die fünf Oberflächen des Auftrags plus Übersicht. | 812 KiB |
| `runtime/src/guppi_runtime/uix/{ui,js,css}/` | gleicher Pfad | Gemeinsame Oberflächenbasis. | 584 KiB |
| `runtime/src/guppi_runtime/uix/tools/` **nur die Werkzeuge, die die fünf Oberflächen laden** | gleicher Pfad | Werkzeugordner ist 1,5 MiB groß. Auswahl in S3 (Abschnitt 9). | höchstens 1,5 MiB |
| `runtime/benchmarks/engine_download.py` | `runtime\benchmarks\engine_download.py` | Wird von `START_SEDRA.bat` vor dem Start aufgerufen. Der übrige Ordner `benchmarks/` ist nicht nötig. | 3 KiB |
| `runtime/Ersteinrichtung.ps1`, `runtime/Erststart_Konfig.ps1`, `runtime/Test-PortableRuntime.ps1` | gleicher Pfad | Vom Start aufgerufen. | 10 KiB |
| `runtime/build_offline_runtime.py` | gleicher Pfad | Wird von `Ersteinrichtung.ps1` aufgerufen, wenn das Python-Paket fehlt. Nur so sinnvoll, wenn der Neuaufbau auf dem Stick gewollt ist (Q5). | 9 KiB |
| `runtime/portable/python/current/` | gleicher Pfad | Portables Python mit Prüfbeleg `bundle-receipt.json`. Wird auf dem Bau-PC erzeugt (Abschnitt 8). | **[SCHÄTZUNG]** 30 bis 40 MiB |
| `runtime/portable/downloads/` | gleicher Pfad | Die geprüften Originaldateien (Python-ZIP, PyYAML, Audio-Wheels), damit ein Neuaufbau **ohne Netz** geht. | **[SCHÄTZUNG]** 14 MB |
| `engines/llama.cpp/b11160/` (aus `runtime/config/llama_server.yaml`: `engine_build: b11160`) | `engines\llama.cpp\b11160\` | Engine für jedes Modell. Ohne sie „plant“ SEDRA nur (`docs/BETRIEB.md`, Zeile 44). | **[GEMESSEN]** ca. 625 MB laut Text von `engine_provision`/`Erststart_Konfig` |
| `docs/PLAN_USB_STICK_MINIMAL.md` | nicht auf den Stick | Plan gehört ins Repository, nicht auf den Stick. | – |

### 2.2 Ausschluss (nicht auf den Stick)

| Pfad | Grund | Größe [GEMESSEN] |
|---|---|---|
| `.git/`, `.gitattributes`, `.gitignore`, `.claude/` | Versionsverwaltung und Entwicklungseinstellungen. Der Stick hat **kein** Git (Abschnitt 7). | – |
| `docs/` (ganzer Ordner) | Dokumentation des Entwicklungsstands (36 MiB). Auf dem Stick genügt die Kurzfassung aus S10. | 36 MiB |
| `runtime/tests/`, `runtime/testdaten/` | Tests, laufen auf dem Entwickler-PC. | 3,5 MiB + 12 KiB |
| `runtime/benchmarks/` außer `engine_download.py` | Bau- und Messskripte. | 3,9 MiB |
| `runtime/examples/`, `runtime/agent_templates/`, `runtime/assets/` | Beispiele und Präsentation (`assets/kmu-praesentation`). `agent_templates/` **[OFFEN]**: Prüfen, ob `agent_manager` sie zur Laufzeit liest (S3). | 184 KiB, 104 KiB, 8,4 MiB |
| `runtime/src/guppi_runtime/` außerhalb der Importhülle | Nicht auf dem Startweg. Ausnahme: alles, was S3 als dynamisch geladen nachweist. | – |
| `runtime/src/guppi_runtime/uix/shells/{gateway-kmu,gateway-studio,guppi-xp,wissensbasis,minimal,_template,_vorgabe}/` | Nicht Teil des Umfangs. `minimal` und `guppi-xp` sind optional, siehe **Q3**. | 756 + 148 + 124 + 112 + 216 + 24 + 16 KiB |
| `runtime/.venv/` | Entwicklerpfad. Auf dem Stick gilt der portable Pfad. | – |
| `runtime/portable/sandbox/` | Sandbox-SDK nur für die DevVM (Selbstentwicklung). Ohne den Ordner baut `build_offline_runtime.py` mit `sdk_version: 'none'`. | – |
| `runtime/runtime_data/`, `workspace/`, `local_config/` (Betriebsdaten) | Entstehen beim Start auf dem Stick, siehe Q9. | – |
| `runtime/run_*.bat|sh`, `setup_*`, `READY_TEST_WINDOWS.bat`, `START_SEDRA.command`, `start_sedra.sh`, `prepare_sandbox.py`, `validate_package.py`, `ready_test.py`, `pyproject.toml`, `requirements.txt` | Entwickler- und Prüfwerkzeuge bzw. macOS/Linux. Der Stick ist Windows-only (Q10). `READY_TEST_WINDOWS.bat` kann bei Bedarf dazu. | – |
| `PACKAGE_CHECKSUMS.sha256`, `PRUEFSUMMEN.sha256`, `BUILD.txt`, `README_PAKET.md`, `START_HERE.txt` | Paket- und Bauhinweise des Repositorys. Der Stick bekommt eigene Prüfsummen (S3) und eine eigene Kurzanleitung (S10). | je 255 KB bzw. kleiner |
| `concept_review/`, `redesign/`, `architecture/` außer dem Pflichtordner | Konzepte. | 40 KiB, 16 KiB, ca. 0,8 MiB |

---

## 3. Größen gegen die 117 GiB

| Bestandteil | Größe | Art |
|---|---|---|
| Python-Importhülle | 2,1 MiB | gemessen |
| Oberflächen (5 Ordner + Basis) | 1,4 MiB (+ Werkzeuge bis 1,5 MiB) | gemessen |
| Config | 152 KiB | gemessen |
| Architektur-Pflichtordner | 856 KiB | gemessen |
| Startskripte, Ersteinrichtung | unter 100 KiB | gemessen |
| Portables Python (entpackt) | 30 bis 40 MiB | Schätzung |
| Prüfdownloads für Offline-Neubau | ca. 14 MB | Text in `Ersteinrichtung.ps1` |
| Engine `b11160` | ca. 625 MB | Text in `engine_provision` |
| **Summe mit Engine** | **rund 0,7 GB** | |
| Reserve für `workspace/`, Logs, `runtime_data/` | **2 GiB** (Vorschlag) | Vorschlag |
| **Gesamt** | **rund 2,7 GB** | |

Bei 117 GiB frei bleiben nach dem Aufbau mehr als 114 GiB frei. Modelle sind nicht Teil dieses Plans. Rechnerisch würde der Modellordner `I:\KI-Daten\modelle` (103 GiB) auf den Stick passen, mit rund 11 GiB Rest. Ein hoher Füllstand gilt als ungünstig (Erfahrungswert, nicht gemessen). Modelle daher nur als eigene Entscheidung (S11).

Die Engine ist im Zweifel der größte Posten. Sie ist mit CUDA 13 gebaut (`docs/BETRIEB.md`, Zeile 13). Auf PCs ohne NVIDIA-Treiber läuft sie nicht. Das ist **Q8**.

---

## 4. Ziel-Layout auf dem Stick

```
K:\SEDRA\
  START_SEDRA.bat
  LICENSE
  README.md                       (Kurzfassung aus S10, ersetzt das Repository-README)
  architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT\
  engines\llama.cpp\b11160\       (Engine, ca. 625 MB)
  runtime\
    Ersteinrichtung.ps1  Erststart_Konfig.ps1  Test-PortableRuntime.ps1  build_offline_runtime.py
    benchmarks\engine_download.py
    config\                       (ohne local_paths.yaml)
    src\guppi_runtime\            (Importhülle + Oberflächen-Ordner laut Abschnitt 2)
    portable\
      python\current\             (portables Python, bundle-receipt.json)
      downloads\                  (Prüfdownloads für den Offline-Neubau)
    STICK_MANIFEST.json           (Prüfsummen aller Dateien, S3)
  workspace\GUPPI_OS\             (entsteht beim ersten Start; local_config, Projekte, Audit)
```

Regeln:
- Alle Pfade im Stick sind **relativ** zu `%~dp0`. Der Laufwerksbuchstabe (K:) darf sich ändern. Das ist für den Start bereits so: `START_SEDRA.bat` setzt `ROOT` aus `%~dp0`, `Erststart_Konfig.ps1` nutzt `$PSScriptRoot`, und `build_offline_runtime.py` schreibt `../../../src` relativ in die `._pth`-Datei.
- Der Ordner `K:\SEDRA\` heißt so, weil `START_SEDRA.bat` die übrigen Pfade relativ zu sich selbst bildet. Das Layout muss also den Repository-Ordnern entsprechen.

---

## 5. Start von K:\ (Ablauf)

1. Doppelklick auf `K:\SEDRA\START_SEDRA.bat` (oder `START_SEDRA.bat cockpit`, `…harness`, `…paperclip`, `…fisch`).
2. `START_SEDRA.bat` prüft `runtime\portable\python\current\python.exe`. Ist die Datei da, wird der `.venv`-Pfad und die Ersteinrichtung **übersprungen**. Fehlt sie, startet `Ersteinrichtung.ps1`, das aus dem Netz lädt. **Auf dem Stick darf das nie ohne Bestätigung passieren** (Abnahme in S8).
3. `benchmarks\engine_download.py` prüft die Engine. Ist sie da und stimmt die Prüfsumme, passiert nichts. Fehlt sie, fragt das Skript vor dem Download (`JA`-Eingabe).
4. `Erststart_Konfig.ps1` schreibt `runtime\config\local_paths.yaml` nur, wenn die Datei fehlt. Dort wird der Modellordner abgefragt (Standard `%USERPROFILE%\GUPPI\Modelle`). Abschnitt 6 beschreibt das Problem.
5. `Test-PortableRuntime.ps1` prüft jede Datei des portablen Pythons gegen die Prüfsumme aus `bundle-receipt.json`. Außerdem lehnt es Verknüpfungen (Reparse Points) und überzählige Dateien ab (`Zusaetzliche Dateien im Python-Paket.`).
6. `uix_start` startet mit `--root K:\SEDRA\workspace\GUPPI_OS --architecture K:\SEDRA\architecture\…`.

Der Ablauf setzt Windows x64 voraus. Die Oberfläche öffnet sich im App-Modus von Edge oder Chrome (`uix_window.py`, die Programmpfade liegen unter `LOCALAPPDATA` des PCs). Was ohne beide Browser geschieht, ist nicht geprüft und wird in S6 festgehalten.

---

## 6. Konfiguration ohne Pfade dieses PCs

| Stelle | Befund | Maßnahme |
|---|---|---|
| `runtime/config/local_paths.yaml` (nicht in git) | Hält den Modellordner dieses PCs, z. B. `I:\KI-Daten\modelle`. Die Datei liegt im Stick-Ordner, also wandert der Pfad mit. Ist der Laufwerksbuchstabe auf einem anderen PC nicht vorhanden, meldet der Code „nicht gesetzt“ (`local_paths.py`: `unresolved`), und die GPU-Prüfung schaltet sich ab. Das ist harmlos. | **Standard (Q4a):** Die Datei wird auf dem Stick **nicht** mitgeliefert. Der Erststart fragt beim ersten Lauf auf jedem PC nach dem Modellordner. Verhalten ohne Ordner: Modelle sind „nicht eingerichtet“, alles andere läuft. **Alternative (Q4b):** Code-Änderung in `runtime/src/guppi_runtime/local_paths.py`, damit der Pfad aus einer Umgebungsvariable oder `%LOCALAPPDATA%\SEDRA\` kommt. Das ist ein Eingriff in den Kern und braucht Captain-Freigabe. |
| `runtime/src/guppi_runtime/models/engine_provision.py`, Zeile 27 | `DEFAULT_ROOT = …/engines`, relativ zum Paket. Passt zum Stick. | Keine Änderung. |
| `runtime/config/llama_server.yaml`, Zeile 37 | `engine_source: guppi`. Es gibt **keinen** Rückfall auf LM Studio (Kommentar Zeile 35). | Keine Änderung. Abnahme in S7: auf dem Testrechner ohne LM Studio meldet die Engine „verfügbar“, wenn die Datei da ist. |
| `runtime/src/guppi_runtime/models/llama_server_runtime.py`, Zeile 129 | Der LM-Studio-Pfad hängt an `Path.home()`. Er wird nur durchlaufen, wenn `engine_source` nicht `guppi` ist. | Keine Änderung, solange `engine_source: guppi`. Abnahme in S7. |
| `runtime/src/guppi_runtime/capabilities/uix_window.py`, Zeilen 13 bis 16 | Edge- und Chrome-Pfade unter `LOCALAPPDATA`. Das sind Programme des PCs, keine Daten. | Keine Änderung. Der Stick trägt keine Browser. |
| `runtime/src/guppi_runtime/harness/befehl.py`, Zeile 29 | Umgebungsliste mit `USERPROFILE`, `HOME`. Nur eine Erlaubnisliste. | Keine Änderung. |
| `runtime/src/guppi_runtime/uix_server.py`, Zeilen 49 und 52 | Beispiele `D:\Shells\…` nur in Fehlermeldungen. | Keine Änderung. |
| Repository-Text, Beispielpfade `E:\…`, `D:\…` (z. B. `local_paths.py` Zeile 7, `docs/BETRIEB.md` Zeile 20) | Nur Beispiele. | Keine Änderung. |

**Prüfung im Repository (S3):** Die Importhülle darf nach dem Stick-Aufbau keinen absoluten Pfad zu einem Laufwerk enthalten, der nicht relativ aufgelöst wird. Dazu eine Suche nach `[A-Za-z]:\\` und `Path.home()` in den Dateien der Stick-Liste. Befunde werden in den Plan eingetragen, nicht still geändert.

---

## 7. exFAT-Einschränkungen und Ersatz

| Eigenschaft von exFAT | Befund im Projekt | Ersatz oder Maßnahme |
|---|---|---|
| Keine Junctions, Symlinks, Hardlinks | Der Produktpfad nutzt keine. Die Prüfung in `Test-PortableRuntime.ps1` (Zeilen 9 und 18) lehnt Verknüpfungen im Python-Paket ab. Der Dateizugriff weist Symlinks zurück (`tools/base.py` Zeile 52, `desk/install.py`, `sandbox/`). | **Kein Ersatz nötig.** Der Stick enthält nur echte Dateien und Ordner. Die Verknüpfungen im Entwicklungs-Worktree bleiben auf dem PC. |
| Keine Dateirechte (ACL) | Die Sicherheit liegt im Guard der Anwendung, nicht im Dateisystem. | Keine Änderung. Abnahme in S9: die Prüfungen „Pfad außerhalb“ greifen weiterhin (Tests `test_runtime`, Pfadfälle). |
| Keine Groß-/Kleinschreibung unterscheidbar | Keine Namenskollisionen in den verfolgten Dateien (geprüft). Der Paketbau weist Kollisionen ab (`build_offline_runtime.py`, `casefold`). | Keine Änderung. |
| Verbotene Zeichen, Namen wie `CON`, `NUL`, endende Punkte oder Leerzeichen | Keine Treffer in den verfolgten Dateien (geprüft mit `[<>:"|?*]` und endenden Punkten/Leerzeichen). Der Paketbau lehnt reservierte Namen ab. | Keine Änderung. |
| Pfadlänge | Längster verfolgter Pfad: 111 Zeichen (geprüft). Auf K:\ bleibt er darunter. | Keine Änderung. |
| Kein Journal, Stromverlust beim Schreiben kann Dateien beschädigen | Schreibt SEDRA während des Laufs auf den Stick (Audit, Protokolle, Lauf-Zustände). | (a) Protokoll „Sicher entfernen“ in S10. (b) Der Audit-Log ist hash-verkettet und hat eine Reparatur (`cli.py`, Zeile 116, `AuditLog.repair`). (c) Test in S9 mit erzwungenem Abziehen. |
| SQLite im WAL-Modus | `jobs/testlab.py`, Zeilen 117 und 125: `PRAGMA journal_mode=WAL`, Datenbank unter `runtime_data/testlab/testlab.db`. WAL braucht eine Shared-Memory-Datei neben der Datenbank. | Test in S9. Wenn die Datenbank auf dem Stick nicht sauber läuft: Journalmodus auf `DELETE` umstellen (Code-Änderung, braucht Freigabe) oder `runtime_data` lokal legen (Q9). |
| Zeitstempel nur auf 2 Sekunden genau | Der Paketaufbau prüft per Hash, nicht per Zeitstempel. | Keine Änderung. |
| Windows-Vorlagen und Indexdateien (`Thumbs.db`) | Windows kann in Ordnern auf Wechseldatenträgern eine `Thumbs.db` anlegen. Der Test in `Test-PortableRuntime.ps1` (Zeile 25) bricht bei überzähligen Dateien im Python-Paket ab. | Im Python-Paket nur die Dateien aus dem Bau. In S9 prüfen, ob `Thumbs.db` auftaucht. Gegebenenfalls Explorer-Miniaturansicht für den Stick aus (**Q11**). |
| Virenscanner | Jeder Start prüft im Python-Paket viele Dateien. | In S9 messen; Dauer des Starts notieren. |
| Schreibverschleiß | Laufdaten wachsen mit der Nutzung. | Zielwert: unter 100 MB pro Monat Schreiblast [SCHÄTZUNG], in S9 messen. |
| Keine Herkunftsmarkierung (Zone.Identifier) | Ohne Folgen. | Keine Änderung. |

---

## 8. Bezug zum Paketbau (`build_offline_runtime.py`) und zum Manifest

### 8.1 Was das Skript prüft (`runtime/build_offline_runtime.py`)

- Manifest: nur `schema: 1`, `platform: windows-x64`, `python_version` (3.11 bis 3.14), `python`, `pyyaml`; optional `audio` (höchstens 8 Einträge: `sounddevice`, `cffi`, `pycparser`). Jede Datei mit `file` und `sha256` (64 Hex-Zeichen). Die Manifestgröße ist auf 64 KiB begrenzt.
- Dateien: ZIP-Einträge mit Verknüpfung, Verschlüsselung, `.data`-Ordnern oder `.pth` (außer `._pth`) werden abgelehnt. Größenlimit 512 MiB und 20 000 Dateien. Kollisionen (auch Groß-/Kleinschreibung) werden abgelehnt.
- `._pth`-Datei: genau `python<abi>._pth`, geschrieben mit `python<abi>.zip`, `.`, `Lib/site-packages`, `../../../src`.
- Ziel: `runtime/portable/python/current`. Ist es schon da, bricht der Bau ab (`existing_bundle_not_overwritten`).
- Sandbox-SDK: liegt `runtime/portable/sandbox` vor, ist das Pinning (`microsandbox 0.7.4`) Pflicht. Für den Stick **ohne** diesen Ordner, damit `sdk_version: 'none'`.
- Ausgabe: `bundle-receipt.json` mit Datei-Liste, Prüfsummen und `qualification: ASSEMBLED_NOT_PC_TESTED`. Dieser Eintrag ändert sich nicht von selbst. Die PC-Abnahme steht im Logbuch.

### 8.2 Ablauf des Paketbaus für den Stick

1. Auf dem **Bau-PC** (Windows x64, Internet): `runtime\Ersteinrichtung.ps1` ausführen. Es lädt fünf Dateien nach `runtime\portable\downloads` (Python 3.14.8, PyYAML 6.0.3, und die Audio-Wheels `sounddevice`, `cffi`, `pycparser`), prüft deren Prüfsummen und ruft `build_offline_runtime.py` mit `bundle.json` auf.
2. `runtime\Test-PortableRuntime.ps1` muss grün sein.
3. Die Engine per `benchmarks\engine_download.py` installieren (S2).
4. Den Stick-Aufbau mit dem Skript aus S3 ausführen (kopiert die Liste aus Abschnitt 2, legt `STICK_MANIFEST.json` an).
5. Auf dem Stick `Test-PortableRuntime.ps1` erneut laufen lassen (S5).

### 8.3 USB-Härtung (Vorschlag, **Q7**)

Der offene Punkt „USB-Härtung“ ist nicht definiert. Vorschlag für die Definition, die dieser Plan umsetzt:

1. **Nur Lesen für das Python-Paket:** Der Start verändert `runtime\portable\` nie. Der Test in `Test-PortableRuntime.ps1` (Prüfsummen, Verknüpfungen, überzählige Dateien) läuft bei jedem Start.
2. **Keine Schreibzugriffe außerhalb von `workspace\`:** Prüfung in S9 mit Dateisystem-Überwachung (Liste der geänderten Dateien nach einem Lauf).
3. **Abziehschutz:** Protokoll „Sicher entfernen“ (S10). Zusätzlich Test in S9 mit erzwungenem Abziehen.
4. **Herkunft:** `STICK_MANIFEST.json` mit Prüfsummen aller Dateien. Der Start meldet bei Abweichung, startet aber nicht.

Der Captain bestätigt oder ändert die Definition (Q7).

---

## 9. Schritte in Reihenfolge

Jeder Schritt hat **Eingabe**, **Tätigkeit** und **Prüfung/Abnahme**. Ein Schritt gilt erst als erledigt, wenn seine Abnahme dokumentiert ist (Logbucheintrag in `docs/LOGBUCH_AGENT_MANAGER.md`, Format wie bestehende Einträge).

### S0 — Klärung
- **Eingabe:** Abschnitt 11.
- **Tätigkeit:** Captain beantwortet Q1 bis Q11 (oder nimmt den Standard). Die Antworten kommen in den Plan als Abschnitt 11 „Entscheidungen“.
- **Abnahme:** Jede Frage hat eine Antwort oder den Vermerk „Standard übernommen“.

### S1 — Bau-PC und portables Python
- **Eingabe:** Windows-x64-PC mit Internet, Zugriff auf `python.org` und `files.pythonhosted.org`.
- **Tätigkeit:** `runtime\Ersteinrichtung.ps1` ausführen (JA eingeben). Ergebnis `runtime\portable\python\current\` mit `bundle-receipt.json`.
- **Prüfung:** `runtime\Test-PortableRuntime.ps1` grün. In `bundle-receipt.json`: `sdk_version` = `none` (wenn kein SDK gewollt), `audio` mit drei Wheels, `python_version` = `3.14.8`.
- **Abnahme:** Ausgabe der drei Prüfungen im Logbuch.

### S2 — Engine
- **Eingabe:** S1, Internet.
- **Tätigkeit:** `runtime\benchmarks\engine_download.py` laufen lassen (`-I -B`), JA eingeben. Ergebnis `engines\llama.cpp\b11160\`.
- **Prüfung:** Ausgabe `(True, …)` aus `engine_provision.verify_engine`.
- **Abnahme:** Prüfsumme bestätigt. Größe notiert (Ziel ca. 625 MB).

### S3 — Stick-Aufbau mit Prüfliste
- **Eingabe:** Abschnitt 2, Abschnitt 4.
- **Tätigkeit (Code, neu):** Ein Skript im Repository, z. B. `runtime/benchmarks/stick_paket.py`, das
  1. die Liste aus Abschnitt 2 als Datei liest (nicht im Code hart verdrahtet),
  2. kopiert, ohne Verknüpfungen zu übernehmen,
  3. `STICK_MANIFEST.json` mit Größe und SHA-256 je Datei schreibt,
  4. die Importhülle prüft: eine statische Importanalyse gegen die kopierte Liste (wie in Abschnitt 2 beschrieben). Jeder fehlende Import ist ein Fehler.
  5. die Suche aus Abschnitt 6 ausführt und die Treffer ausgibt.
- **Tätigkeit (Auswahl der Werkzeuge, S3-Teil):** Prüfen, welche Dateien in `uix/tools/` von den fünf Oberflächen geladen werden. Ergebnis als Liste. Prüfen, ob `agent_manager` `runtime/agent_templates/` liest (Q2-Hinweis).
- **Prüfung:** Eigener Test (`runtime/tests/test_stick_paket.py`) mit einer Kopie in ein temporäres Verzeichnis: Start von `uix_start --liste` aus der Kopie liefert genau die fünf Oberflächen plus `start`.
- **Abnahme:** Test grün. Liste der dynamischen Importe und deren Ergebnis im Logbuch.

### S4 — Kopie auf K:\
- **Eingabe:** S3 mit Ergebnis, Stick K:\.
- **Tätigkeit:** Das Skript aus S3 auf `K:\SEDRA\` ausführen.
- **Prüfung:** Hash-Vergleich jeder Datei auf dem Stick mit dem Manifest. Keine fehlenden und keine überzähligen Dateien.
- **Abnahme:** Protokoll mit Anzahl der Dateien und Gesamtgröße.

### S5 — Start-Prüfung vom Stick (Bau-PC)
- **Eingabe:** S4.
- **Tätigkeit:** `K:\SEDRA\runtime\Test-PortableRuntime.ps1` laufen lassen. Dann `K:\SEDRA\START_SEDRA.bat --uebersicht`.
- **Prüfung:** Übersicht öffnet sich. `K:\SEDRA\workspace\GUPPI_OS\` entsteht. Keine Datei außerhalb von `K:\SEDRA\` wird angelegt (Vergleich vor und nach dem Lauf).
- **Abnahme:** Liste aller neuen Dateien nach dem Lauf im Logbuch.

### S6 — Oberflächen einzeln
- **Eingabe:** S5.
- **Tätigkeit:** Für `cockpit`, `harness`, `paperclip`, `fisch` je `START_SEDRA.bat <id>` starten. Eine Mission oder Anfrage ohne Modell stellen.
- **Prüfung:** Die Oberfläche antwortet (HTTP 200 von der lokalen Adresse, siehe `uix_start`). Ohne Modell sagt die Oberfläche klar „kein Modell“ oder „nicht eingerichtet“, sie stürzt nicht ab.
- **Abnahme:** Je Oberfläche eine Zeile im Logbuch mit Ergebnis.

### S7 — Engine und Modelle ohne PC-Pfade
- **Eingabe:** S6.
- **Tätigkeit:** Auf dem Bau-PC `local_paths.yaml` entfernen (Standard Q4a). Start erneut. Antwort des Erststarts auf den Modellordner: Enter (Standard `%USERPROFILE%\GUPPI\Modelle`).
- **Prüfung:** Engine wird gefunden. Modelle sind „nicht eingerichtet“. Keine Verbindung zu LM Studio (`Path.home()`-Pfad wird nicht genutzt).
- **Abnahme:** Protokoll aus `runtime\einrichtung.log` auf dem Stick.

### S8 — Zweiter PC ohne Netz und ohne Python
- **Eingabe:** S7.
- **Tätigkeit:** Stick an einem anderen Windows-PC anschließen, Netzwerk trennen, `START_SEDRA.bat` starten.
- **Prüfung:** Start ohne Netzwerkzugriff und ohne Installation. Kein Download, kein Aufruf von `Ersteinrichtung.ps1` mit `Invoke-WebRequest`. Die Oberfläche startet. Der Laufwerksbuchstabe ist nicht K:.
- **Abnahme:** Ausgabe im Logbuch. Hinweis: Ohne NVIDIA-Treiber wird die Engine nicht geladen (Q8); das ist dann erwartet und kein Fehler.

### S9 — Dauerprüfung exFAT
- **Eingabe:** S8.
- **Tätigkeit:**
  1. Zwei Läufe hintereinander, Dauer des Starts messen (Virenscanner, Abschnitt 7).
  2. Schreibmenge eines Laufs messen (`workspace\` vorher und nachher).
  3. WAL-Test: die Testlab-Datenbank `runtime_data\testlab\testlab.db` auf dem Stick anlegen lassen (`jobs/testlab.py`, Zeilen 117 und 125 setzen `journal_mode=WAL`) und die Schreib- und Lesetests dagegen laufen lassen.
  4. Erzwungenes Abziehen während eines Schreibvorgangs (Testlauf). Danach `audit-repair` aufrufen (Unterbefehl in `cli.py`, Zeile 106; Ablage `runtime_data\audit\events.jsonl`). Argumentreihenfolge für `--root` vorher in `cli.py` prüfen.
  5. `Thumbs.db` im Stick suchen.
- **Prüfung:** Keine Beschädigung nach dem Abziehen, oder die Reparatur stellt sie wieder her. Schreibmenge und Startdauer sind dokumentiert.
- **Abnahme:** Messwerte im Logbuch. Bei WAL-Fehler: Q9 wird entschieden, bevor S10 läuft.

### S10 — Dokumentation und Protokolle
- **Eingabe:** S9.
- **Tätigkeit:**
  1. `K:\SEDRA\README.md` schreiben: Start, Oberflächen, Modellordner pro PC, Sicher-entfernen-Protokoll, Hinweis auf Windows x64 und NVIDIA.
  2. Im Repository: `docs/BETRIEB.md` um einen Abschnitt „Stick“ ergänzen. Die Abschnitte für `START_SEDRA.bat` (Zeile 28) bleiben, sie gelten für den PC.
  3. Logbucheintrag für den Stick-Aufbau.
- **Prüfung:** Die Kurzanleitung nennt nur Schritte, die in S5 bis S9 geprüft wurden.
- **Abnahme:** Captain liest die Kurzanleitung und bestätigt.

### S11 — Optional: Modelle
- **Eingabe:** Entscheidung des Captains.
- **Tätigkeit:** Nicht Teil dieses Plans. Wenn gewünscht: Größe jedes Modells messen, Füllstand unter 90 % halten (Abschnitt 3), Rezept mit dem Modellpfad auf dem Stick oder außerhalb anlegen.
- **Abnahme:** Eigener Plan.

---

## 10. Risiken

| Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|
| `Ersteinrichtung.ps1` lädt aus dem Netz, wenn das Python-Paket fehlt | Start verlangt Netz und Ablage von Dateien auf dem fremden PC | S8: Test ohne Netz. Das Paket ist vollständig auf dem Stick. |
| Stick-Ordner unvollständig nach Kopie | Start bricht ab | S4: Hash-Vergleich. |
| Modellordner des Captain-PCs (`I:\`) fehlt auf anderem PC | Modelle fallen aus | Erwartet. Der Start läuft ohne Modell (Q4a). |
| Abziehen während eines Laufs | Beschädigte Dateien | S9: Test und Reparatur. Protokoll „Sicher entfernen“. |
| `Test-PortableRuntime.ps1` bricht durch `Thumbs.db` ab | Kein Start | S9: Test. Ggf. Miniaturansicht ausschalten (Q11). |
| SQLite WAL auf exFAT | Fehler bei Testläufen | S9: Test. Ggf. Journalmodus (Q9). |
| Engine (CUDA 13) auf einem PC ohne NVIDIA | Modell antwortet nicht | Erwartet. Anzeige in der Oberfläche prüfen (S8). |
| Der Stick ist für eine Version gedacht, das Repository ändert sich | Veralteter Inhalt | `STICK_MANIFEST.json` mit Git-Stand. Neuer Aufbau nach Änderungen. |
| Logbucheinträge zum Verhalten beim Fenster-Schließen (Abschnitt 11, Q5) widersprechen dem heutigen Verhalten | Verwirrung über den Startweg | Entscheidung vor S10 in den Texten festhalten. |

---

## 11. Offene Fragen an den Captain (Q1 bis Q11)

Jede Frage hat einen Standard. Wenn keine Antwort kommt, gilt der Standard, und der Plan geht weiter.

| Nr. | Frage | Standard, wenn keine Antwort kommt |
|---|---|---|
| **Q1** | „Kern“: Ist `runtime/src/guppi_runtime/core/` plus Importhülle gemeint? „Transkript-Shell“: Ist `fisch` (Modus Transkript) gemeint oder ein eigener Teil? Gehört `paperclip_pipeline.py` zu Paperclip? | `core/` plus Importhülle; `fisch` mit Modus Transkript; `paperclip_pipeline.py` nicht auf dem Stick, bis S3 es als nötig erkennt. |
| **Q2** | `runtime/agent_templates/` auf den Stick? Abhängig davon, ob der Agent Manager sie zur Laufzeit liest (S3). | Nur wenn S3 es als nötig nachweist. |
| **Q3** | Shells `minimal` und `guppi-xp` auf dem Stick? Die Übersicht `start` ist ohnehin enthalten. | Nicht enthalten. |
| **Q4** | Modellordner pro PC: (a) `local_paths.yaml` nicht mitliefern, Ersterfrage auf jedem PC, oder (b) Code-Änderung, damit der Pfad aus Umgebungsvariable oder `%LOCALAPPDATA%` kommt? | (a). |
| **Q5** | Verhalten beim Schließen des Fensters. Der Logbucheintrag 30.10. 08:41 und 08:42 sagt: Hintergrundbetrieb Standard **an**, Fenster schließen beendet SEDRA nicht, Symbol im Infobereich. Das heutige `START_SEDRA.bat` (Kopf) und `docs/BETRIEB.md` (Zeile 28) sagen: Fenster schließen beendet den Server und entlädt das Modell. Welches gilt auf dem Stick? | Heutiges Verhalten (Fenster schließen beendet). Die Logbuch-Entscheidung wird als eigener Schritt umgesetzt, wenn der Captain es bestätigt. |
| **Q6** | `PLAN_USB_STICK_v1` (Versionen v14 bis v17) fehlt im Repository. Soll er ergänzt werden, damit die Entscheidungen A2, C10, P7 und 16 bis 20 hier vollständig übernommen werden? | Nur die Entscheidungen aus dem Logbuch und aus `docs/NACHTRAG_OFFENE_PUNKTE_2026-10-30.md` (Zeilen 24 und 25). |
| **Q7** | Definition „USB-Härtung“ (Abschnitt 8.3). | Vorschlag aus Abschnitt 8.3. |
| **Q8** | Zielrechner: Stick nur für PCs mit NVIDIA-Treiber? Auf PCs ohne NVIDIA startet die Engine nicht. Soll die Engine trotzdem auf dem Stick liegen? | Engine auf dem Stick. Ohne NVIDIA: Hinweis in der Oberfläche, kein Fehler. |
| **Q9** | Laufdaten (`workspace/`, `runtime_data/`) auf dem Stick oder lokal auf dem PC? Schreibverschleiß und WAL (S9) sprechen eher für lokal, Portabilität für Stick. | Auf dem Stick, bis S9 gemessen ist. |
| **Q10** | Nur Windows? `start_sedra.sh` (macOS und Linux) nutzt eine `.venv` mit Symlinks; auf exFAT ist das nicht möglich. | Nur Windows. |
| **Q11** | `Thumbs.db` und Miniaturansicht: Explorer-Miniaturansicht für den Stick abschalten, oder den Test in `Test-PortableRuntime.ps1` anpassen? | Miniaturansicht abschalten (keine Codeänderung), Befund in S9 dokumentieren. |

---

## 12. Abnahme insgesamt

Der Stick gilt als fertig, wenn alle Punkte erfüllt sind:

1. Die Liste aus Abschnitt 2 ist umgesetzt, das Manifest stimmt mit dem Stick überein (S4).
2. Die Importhülle läuft vollständig aus der Kopie (S3, S5).
3. Jede Oberfläche aus Abschnitt 1.2 startet vom Stick und zeigt eine Antwort (S6).
4. Ein zweiter PC ohne Netz und ohne Python startet (S8).
5. Nach erzwungenem Abziehen lässt sich der Stand reparieren oder ist unbeschädigt (S9).
6. Die bestehenden Tests des Repositorys laufen unverändert grün. Befehl laut `runtime/README_RUNTIME.md`: `set PYTHONPATH=src;tests` und `.venv\Scripts\python.exe -m unittest tests.test_runtime`. Für Änderungen am Kern zusätzlich die betroffenen Testmodule.
7. Die Kurzanleitung auf dem Stick (S10) ist vom Captain bestätigt.

---

## 13. Was dieser Plan nicht enthält

- Keine Änderung am Kern, an Oberflächen oder am Start außer den in Q4, Q5, Q9 und S3 genannten Punkten.
- Keine Modelle, keine Rezepte für Modelle, kein Sandbox-SDK (DevVM).
- Keine macOS- und Linux-Fassung (Q10).
- Keine Veröffentlichung oder Weitergabe des Stick-Inhalts. Der Stick enthält nur eigene Dateien und die Engine aus dem Release, die per SHA-256 geprüft ist.
