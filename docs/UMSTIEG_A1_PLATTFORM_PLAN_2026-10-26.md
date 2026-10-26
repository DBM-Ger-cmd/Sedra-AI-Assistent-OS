# Umstiegsplan: A1 wird die einzige Arbeitsplattform (Installation `GUPPI_Runtime_v1.20` geht in A1 auf)

**Stand:** 26.10.2026, angepasst vom Vorarbeiter am 26.10.2026 (siehe Abschnitt 0a). Dies ist nur ein Plan. Es wurde nichts verändert, verschoben, gelöscht, gestoppt oder gestartet. Jeder Schritt ab U2-2 braucht eine Freigabe des Captains (Gate). Die Fassung der Prüf-Sitzung liegt unverändert im Ordner `_Entwickler_Zip_2026-10-26`.
**Pfad:** `docs/UMSTIEG_A1_PLATTFORM_PLAN_2026-10-26.md` in A1. Geschrieben nach dem Muster von `docs/UMSTIEG_INSTALLATION_PLAN_2026-10-24.md`.
**Begriffe:** `<a1>` = `E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung` (Branch `spec/agenten-orchestrierung`, selbst ein Worktree des Hub-Repos). `<rt>` = `E:\Sedra Umgebung\GUPPI_Runtime_v1.20` (läuft gerade, Branch `betrieb/a1-74de39e`, Remote `a1` zeigt auf das Hub-Repo). `<hub>` = `E:\Sedra Umgebung\SEDRA_Build_024_Cockpit_Paperclip_Arbeitsplatz_2026-10-15\GUPPI_Runtime_v1.20`. `<sich>` = `E:\Sedra Umgebung\_Aufraeumen_2026-10-24\sicherung`.
**Regeln:** A1-Code und A1-Git bleiben unberührt (außer ausdrücklich genannt und freigegeben), keine eigene Sedra-Kopie als Arbeitsort (BAUWEG Abschnitt 6: es wird in A1 hinein kopiert, kein Staging-Ordner), kein Push, keine GPU außer in Schritt U2-9 (Gate).

---

## 0. Kurzfassung

- **Code ist kein Thema.** A1 ist 276 Commits weiter als die Installation (`74de39e` gegen den heutigen Stand `7a850e1`, auf GitHub gepusht). Nach A1 müssen **Daten, Umgebung und Einstellungen**, nicht Programmdateien.
- **A1 ist selbst ein Worktree des Hub-Repos** (`<hub>\.git\worktrees\Integration_Arbeitskopie_2026-10-16`). Der Hub bleibt also dauerhaft, auch wenn die Installation verschwindet. Er darf nicht verschoben werden.
- **Drei Dinge fehlen A1 für den Betrieb, wie ihn die Installation heute leistet:**
  1. **`runtime\.venv`.** A1 hat keine, nur `runtime\portable\python` (3.14.8) ohne `microsandbox`, `dulwich`, `requests` u. a. Die Installation nutzt `.venv` (3.14.7) mit `microsandbox 0.7.4`, `dulwich 1.2.17`, `requests`, `certifi`, `charset_normalizer`, `idna`, `defusedxml`, `youtube_transcript_api`, `tzdata`, `pyyaml`, `urllib3`. **`START_SEDRA.bat` nimmt zuerst `portable\python`, nur ohne diesen den `.venv`-Weg.**
  2. **Die microVM-Daten.** A1 hat `runtime\portable\sandbox` und `devvm` nicht, und der VM-Cache (`backend_home`, 138 MB) liegt in der Installation. Die VMDK-Beschreibung enthält absolute Pfade `\\?\E:\Sedra Umgebung\GUPPI_Runtime_v1.20\…`.
  3. **Die Rezepte und Schalter.** A1 hat in `role_routing.yaml` **1 Rezept** (UIX, 19.10., ohne `slots`), die Installation **18 Rezepte** mit `per_slots` und die gestuften Schalter.
- **Nicht mischen, sondern archivieren:** Audit-Kette (`events.jsonl`, 4,3 MB, Kopf `EVT-007210`, mit Hash-Kette), `testlab.db`, `approval_tokens.json`.
- **Ablauf:** erst alles Kopieren bei **laufender** Installation (nur lesen aus `<rt>`), dann kontrolliert beenden, Nachkopie der letzten Änderungen, Prüfungen, Start aus A1. Die Installation wird dabei **nicht verändert**; der Rückweg ist, sie wieder zu starten. Erst nach einer Bewährungszeit wird sie archiviert und vom Captain gelöscht.

---

## 0a. Änderungen gegenüber der Fassung der Prüf-Sitzung (Vorarbeiter, 26.10.2026)

Grundlage: Gespräch mit dem Captain am 26.10. und die Nachprüfung am Dateisystem.

1. **A1 ist der Live-Stand und die einzige Arbeitsplattform.** Die Installation wird nicht „weiter betrieben“, sie geht in A1 auf und wird nach einer Bewährungszeit archiviert (unverändert U2-12).
2. **Engines und Modelle brauchen keinen Umzug.** `b11160` (aktiv) und `b11371` liegen in A1 und in `E:\Sedra Umgebung\Sedra_Engine_v1`; die Modelle liegen außerhalb unter `E:\HermesAgentOrdner\lokale-modelle`. Entscheidung F2 ist damit „nichts kopieren“ (Vorschlag), `b11530` bleibt im Archiv.
3. **Die Update-Funktion (`update_suche`, `update_holen`, `update_anwenden`) ist nicht der Weg für diesen Umzug.** Sie holt nur Release-Tags (`vX.Y.Z`, heute `v1.21.0`) und ersetzt nur `runtime/src/guppi_runtime/` und `runtime/config/` (Manifest, Rechte-Bestätigung, Sicherung). Sie bringt keine Daten, keine `.venv`, keinen VM-Cache und keine Rezepte mit, und A1 ist ein Git-Arbeitsbaum, dessen Dateien Git verwaltet. In A1 ist `git pull` bzw. der Branch der Weg für den Code. Die Funktion bleibt für spätere, saubere Installationen aus Releases.
3a. **Grundsatz Code und Daten:** Code kommt aus Git, Daten nicht (`.gitignore`: `engines/`, `workspace/`, `runtime/.venv/`, `runtime/runtime_data/`, `local_config/`). Die Prüf-Sitzung hat beide Varianten verglichen (Abschnitt 5b) und empfiehlt **erst Variante A** (Daten in A1, wie `START_SEDRA.bat` es setzt; dieser Plan, Schritte U2-2 bis U2-8), **nach der Bewährungszeit Variante B** (eigener Datenordner neben dem Code, damit ein frisches `git clone` ohne Datenverlust möglich ist; Schritt U2-B). Entscheidung des Captains: F13.
4. **Die Nachtkette zieht mit um** (Entscheidung des Captains, ersetzt „deaktivieren“). Einzige Quelle für Befund und Schritte ist Abschnitt 5a. Kurz: Die Aufgabe hat einen Anmelde-Trigger und zeigt auf eine alte Kopie, deren Skript es nicht mehr gibt (Ergebnis `4294770688`); die Ketten sind absichtlich bis 14.10.2026 12:00 befristet. Von den alten Skripten liegen einige in A1 unter `benchmarks\archiv\` (`night_queue_2026-10-13_g.py`, `…2026-10-13.py`, `…2026-10-11*.py`), andere nur im Sicherungsbranch `installation/stand-2026-10-24` (Startskript, `…_b.py`, Richter). Das neue Startskript wird als A1-Datei gebaut (nicht die alte Kette wiederbelebt), die alte Aufgabe bleibt deaktiviert.
5. **Tests ab U2-9 über `benchmarks/run_tests.py`.** Mit der kopierten `.venv` (U2-3) laufen Tests wieder, die heute übersprungen sind: Bei der Gesamtsuite am 26.10. waren 92 Tests übersprungen, darunter alle DevVM-Tests (`dulwich` fehlt im System-Python). `run_tests.py` nimmt künftig `runtime\.venv\Scripts\python.exe`, wenn es sie gibt. Neue rote Tests, die vorher übersprungen waren, sind **Befunde**, keine Umzugsfehler, und werden getrennt behandelt.
6a. **Eine Version, Einbahnstraße (Captain, 26.10.2026):** Es gibt nur noch SEDRA in A1; GUPPI (die Installation `GUPPI_Runtime_v1.20`) geht vollständig darin auf, es bleiben keine zwei Versionen. SEDRA wurde mit dem neuen Bauweg grundlegend umgestaltet, deshalb gilt: **alte Daten überschreiben nie etwas in A1.** Kopiert wird nur, was in A1 fehlt (`robocopy /XC /XN /XO`, nie `/MIR`, `/PURGE`, `/MOVE`); Konfiguration wird nur ergänzt, jede Datei vorher gesichert; Audit-Kette, `testlab.db` und Freigabe-Tokens der Installation werden nicht mit denen von A1 gemischt; was die Installation und A1 beide haben, gilt in der A1-Fassung. Der Fluss geht nur von der Installation nach A1, nie zurück. Der Platzhalter `<guppi>` in `local_paths.yaml` zeigt auf A1 (gesetzt am 26.10.2026), `projekte` und `skillsets` (zeigen auf die alte Kopie unter `E:\WEb Projekte\…`) werden nicht übernommen. Nach U2-12 gibt es die Installation nur noch als Zip im `Entwickler_Archiv`.
6. **Regeln für Sitzungen:** keine eigene Sedra-Kopie (BAUWEG Abschnitt 6, `benchmarks/hygiene.py` vor und nach dem Umzug), Projektordner für Bau und Messung nach U2-11 immer `<a1>\workspace\GUPPI_OS`.

---

## 1. Was kommt nach A1 und wie

Legende: **K** = kopieren (zusätzlich, nichts überschreiben), **M** = zusammenführen (Entscheidung), **N** = nicht übernehmen, **A** = archivieren, **–** = nichts nötig.

| Bereich (`<rt>`) | Größe | A1-Befund | Aktion | Schritt |
|---|---:|---|---|---|
| Programmcode, `docs`, `architecture`, Tests, Starter | – | A1 neuer; die 63 abweichenden Dateien sind ältere Fassungen | – | – |
| `runtime\.venv` | 0,11 GB | fehlt in A1 | **K** (Kopie), Rebuild als Rückfall | U2-3 |
| `runtime\portable\sandbox` (SDK-Wheel 39 MB, `RELEASE_LOCK.json`) und `portable\devvm\wheels` (dulwich, urllib3) | ~40 MB | fehlt in A1 | **K** | U2-3 |
| `engines\llama.cpp\b11160`, `b11371` | 1,8 GB | in A1 vorhanden, DLLs hash-gleich | – | – |
| `engines\llama.cpp\b11530` | 1,11 GB | fehlt | **N** (laut Docs als Standard abgelehnt; `engine_build: b11160`) | U2-4 (Entscheidung) |
| `engines\tools\compute-sanitizer-12.4.127` | 25 MB | fehlt | **K** nur wenn der Captain es braucht | U2-4 (Entscheidung) |
| `engines\_staging` | 1,2 GB | fehlt | **N** (Installer-Zips) | – |
| `workspace\GUPPI_OS\local_config\role_routing.yaml` | 35 KB, 18 Rezepte | A1: 1 Rezept `coder.local_qwen3_5_9b_q6_k` (UIX) | **M** | U2-5 |
| `…\routing_profiles.yaml` | | A1: Profil `standard` (nur Qwen3.5-9B); RT: aktiv `stabil` + `standard`, `gptoss` | **M** | U2-5 |
| `…\switches.yaml` | | A1: `model_loader`, `llama_server` (mtp aus); RT: 6 Schalter an, `mtp: true`, `evict_idle_models` | **M** | U2-5 |
| `…\local_config\*.bak-*` (35 Sicherungen) | 0,8 MB | – | **A** (bleiben im Archiv) | U2-12 |
| `…\local_config\skill_library` | 1 Datei | A1: 1 Datei | – | – |
| `uix.yaml`, `cloud_keys.json`, `cloud_providers.yaml`, `modell_zustand.json`, `zuletzt_geladen.json`, `gateway`, `sedra` | nur A1 | gehören A1 | **behalten, nicht anfassen** (`cloud_keys.json` ist ein Geheimnis) | – |
| `runtime\config\local_paths.yaml` | | A1: nur `modelle`; RT: + `modelle-test`, `hermes`, `projekte`, `guppi`, `skillsets` | **M**: `modelle-test`, `hermes` zufügen; `guppi` = `<a1>` (der RT-Wert zeigt auf `E:\WEb Projekte\…`, also eine dritte, alte Kopie); `projekte`, `skillsets` nach Entscheidung | U2-5 |
| `runtime\config\sandbox.yaml` | | inhaltlich gleich (nur Zeilenenden) | – | – |
| `runtime\runtime_data\skill_library` (1132 Dateien, 10 MB) und `skill_library_core` (113) | 11 MB | A1 hat `runtime\runtime_data` nicht (ignoriert) | **K** | U2-2 |
| `workspace\GUPPI_OS\runtime_data\measurements` (893 Dateien, 5,7 MB) | | A1: nicht vorhanden | **K** | U2-2 |
| `…\devvm_replays` (35 MB), `devvm_snapshots`, `devvm_candidates`, `devvm_comments`, `spec_stamps`, `context_metrics`, `missions`, `agent_manager`, `acceptance`, `e1_golden_path`, `external`, `am_seed*` | ~45 MB | teils anders belegt | **K** (nur Dateien, die in A1 fehlen) | U2-2 |
| `…\tool_workspace` (`offline-assets\python-3.12-slim.tar` 126 MB, `guppi-candidates`) | 123 MB | A1: `tool_workspace` leer/andere | **K** (das Tar braucht die Sandbox-Einrichtung, `sandbox.yaml` nennt seine Prüfsumme) | U2-2 |
| `…\sandboxes\backend_home` (`cache` 134 MB, `db` 4 MB) | 138 MB | fehlt | **K plus Pfadumstellung** | U2-7 |
| `…\sandboxes\backend_home\run` (13.353 Kleindateien), `sandboxes\jobs` (100 Dateien, 17 Läufe), `image-imports` (126 MB, doppelt zum Tar) | | | **N** (Laufzeitreste, Tar-Duplikat) | – |
| `…\audit\events.jsonl` (4,3 MB, verkettet) | | A1 hat eine eigene Kette | **N, A** | U2-8 |
| `…\testlab\testlab.db` (1,3 MB) | | A1 hat eigene | **N, A** | U2-8 |
| `…\guard\approval_tokens.json` (37 KB) | | A1 hat eigene | **N** (Freigabe-Tokens gehören zur laufenden Installation) | U2-8 |
| `…\llama_server\state.json`, `server.log`, `runtime_data\gpu_canary*.json/.log` | | | **N** (Zustand der laufenden Instanz) | – |
| `workspace\GUPPI_OS\acceptance` (80 Dateien) | | nur RT | **K** | U2-2 |
| Git der Installation: Branch `main` mit 64 lokalen Commits (7.–14.10., Bundle in `<sich>`), `installation/stand-2026-10-24`, `betrieb/a1-74de39e`, `wire-modules-2026-10-12` | 30 MB | – | **A**; optional als geschützte Referenz ins Hub-Repo (U2-10) | U2-10 |

**Zu den 64 Commits (Frage F6):** Sie gehören historisch nicht ins A1-Repo (`Sedra-AI-Assistent-OS`), weil sie aus dem alten Repo `Guppi-Self-Improve-AI-Agent` stammen und die Geschichte dort anders verläuft. Inhaltlich steckt der Stand in A1 (Build 20). Empfehlung: **Bundle plus Zip des Repo-Ordners `.git` der Installation als Archiv** und keine Verflechtung mit dem A1-Verlauf. Wer die Commits trotzdem nachschlagbar im A1-Repo haben will, nimmt die Variante in U2-10 (nur ein Namensraum `refs/archiv/…`, kein Branch, kein Push).

---

## 2. microVM

**Befund:**
- Die VMDK-Beschreibung `…\sandboxes\backend_home\cache\vmdk\sha256_b0f67293…vmdk` (1,3 KB) hat 5 Zeilen `RW … FLAT "\\?\E:\Sedra Umgebung\GUPPI_Runtime_v1.20\workspace\GUPPI_OS\runtime_data\sandboxes\backend_home\cache\{fsmeta|layers}\sha256_…erofs"`. Die Layer selbst liegen als Dateien (`cache` 134 MB).
- Es gibt einen **Präzedenzfall:** Am 20.10. (PIPE-05) wurden genau diese Pfade nach einem Ordnerumzug umgestellt (5 Pfade, Sicherung `.bak-2026-10-20-pfadumzug`), danach `vm_latency` 4/4 completed. Die VM-Daten sind also **verschiebbar**, wenn die Beschreibung angepasst wird.
- **Pfadlänge:** `backend_home` in A1 hat 115 Zeichen (Installation 92). Bei Namenslänge 18 plus 65 Zeichen Suffix bleiben **61 Zeichen Reserve** (Grenze 259). Das reicht. Wichtig: nicht tiefer verschachteln.
- **Falscher Projektordner:** `devvm_build`, `spec_check --vm --project`, `vm_latency` legen im angegebenen Projektordner ein eigenes `runtime_data\sandboxes\backend_home` an. Zeigt man auf einen Ordner ohne Cache, entsteht ein leerer Cache, und die Image-Importe müssen neu laufen. Künftig immer `<a1>\workspace\GUPPI_OS`.

**Zwei Wege, Gate ja:**
- **V1 (empfohlen): Cache kopieren und Beschreibung umschreiben** (U2-7). Dauert Minuten, braucht keine Downloads.
- **V2 (Rückfall): Cache neu aufbauen.** Der Import des Images `python:3.12-slim` kommt aus `offline-assets\python-3.12-slim.tar` (Prüfsumme in `sandbox.yaml`), braucht das SDK aus `.venv` und die Einrichtungsroutine der Sandbox (`provision.py`). Ob dafür Netz nötig ist, habe ich nicht geprüft; laut `sandbox.yaml` ist `network: deny`, das gilt aber für die VM, nicht für die Einrichtung.

---

## 3. Start aus A1 – was geprüft werden muss

- `START_SEDRA.bat` setzt `PROJ=%ROOT%\workspace\GUPPI_OS` und `ARCH=…\architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT`, also **Daten aus A1**. Das ist richtig und ändert sich nicht.
- **Pythonwahl:** `PY=runtime\portable\python\current\python.exe`, **wenn vorhanden**, sonst `.venv` (Entwicklerweg mit `PYTHONPATH=runtime\src`). A1 hat `portable\python`, **also würde A1 heute ohne Sandbox-SDK starten.** Die Installation hat kein `portable\python` und läuft über `.venv`. Für Gleichheit gibt es zwei Wege (Frage F3):
  - **P1 (empfohlen, nachgewiesen):** `runtime\portable\python` in `python.aus` umbenennen (Ordner ist ignoriert und liegt außerhalb von Git). Dann nimmt die Datei den `.venv`-Weg, wie die Installation.
  - **P2:** nach Anleitung im Skript Sandbox-Ordner kopieren, `portable\python` löschen und per `START_SEDRA.bat` neu einrichten lassen. Unklar, ob die Ersteinrichtung offline funktioniert (Download-Abfrage), deshalb nicht empfohlen.
- **Ports:** Die Oberfläche startet mit `--port 0` (freier Port, wird beim Start angezeigt). Der Modellserver nutzt **8089** (`llama_server_runtime`, Vorgabe), Messungen teils 18080. Zwei SEDRA-Instanzen kämpfen um GPU-Lease und Port 8089; `START_SEDRA.bat --replace` beendet eine noch laufende Instanz, „auch aus einem alten Paket“.
- **Die laufende Installation** (PIDs 33416 `cmd`, 24260 und 33424 `python`) muss **vor** dem ersten Start aus A1 beendet sein. Wer: der Captain (Fenster von `START_SEDRA.bat` schließen beendet Server und Modell), nicht eine Sitzung. Danach prüfen: kein Prozess aus `<rt>`, GPU-Lease frei, Port 8089 frei, kein `llama-server` (mit `benchmarks\hygiene.py`).
- **Sitzungen:** Bauten und Messungen der anderen Sitzungen nutzen `<rt>\workspace\GUPPI_OS` als Projektordner. Sie müssen vorher umgestellt oder beendet sein (Frage F5).

---

## 4. Verweise, die auf `<rt>` oder alte Pfade zeigen

| Verweis | Befund | Plan |
|---|---|---|
| Geplante Aufgabe `GUPPI Nachtkette 2026-10-13` | Aktion `powershell … -File "E:/WEb Projekte/Guppy/GUPPI v1.20_S D A/GUPPI_Runtime_v1.20/runtime/benchmarks/start_night_chains_2026-10-13.ps1"`, **Anmelde-Trigger**, zuletzt 26.10. 07:43, Ergebnis 4294770688, Zustand bereit | zeigt auf eine **dritte, alte Kopie**. Entscheidung des Captains: **mit umziehen**, nicht deaktivieren. Plan: Abschnitt 5a und U2-11b (neues Startskript in A1, Aufgabe neu anlegen, bis zur Prüfung deaktiviert) |
| Desktop-Verknüpfung `START_GUPPI - Verknüpfung.lnk` | Ziel `E:\WEb Projekte\Guppy\GUPPI v1.20_S D A\GUPPI_Runtime_v1.20\START_GUPPI.bat` | ersetzen durch Verknüpfung auf `<a1>\START_SEDRA.bat` (`START_SEDRA.bat` ersetzt `START_GUPPI.bat`), Gate U2-11 |
| Startmenü, Run-Schlüssel, Umgebungsvariablen | keine Treffer | – |
| „Zuletzt verwendet“ | Einträge auf `<hub>`, `<a1>`, `Build_024` | harmlos |
| Git-Remote `a1` der Installation | zeigt auf `<hub>` (Pfad), `alt-origin` zeigt auf `Guppi-Self-Improve-AI-Agent` (Push gesperrt) | mit der Installation archiviert; `<hub>` bleibt aus anderem Grund (A1 selbst ist sein Worktree) |
| VMDK-Beschreibung | siehe Abschnitt 2 | U2-7 |
| Messprotokolle `…\measurements\logs\*.json` mit Pfaden `E:\\Sedra Umgebung\\GUPPI_Runtime_v1.20\\…` | nur Berichte, kein Funktionspfad | unverändert kopieren (Belege), nicht umschreiben |
| `<guppi>`-Platzhalter in `wissen.yaml`, `wissen/konfig.py`, `benchmarks/logbook.py`, `slot_measurement.py`, `wissen_*_messung.py` | lösen über `local_paths.yaml` Schlüssel `guppi` auf; in A1 fehlt der Schlüssel | in U2-5 `guppi: <a1>` eintragen, danach die genannten Skripte per `--help`/Probelauf prüfen |
| Doku (`docs/BETRIEB.md`, `ENTWICKLUNG.md`) nennt `<guppi>` als Bauort | | nach dem Umstieg Text prüfen: Bauort ist `<a1>\workspace\GUPPI_OS` (eigene Doku-Änderung in A1, nicht Teil dieses Plans) |
| Laufende Sitzungen (S2.H5 u. a.) | Projektordner `<rt>\workspace\GUPPI_OS` | umstellen oder beenden, Gate U2-1 |

---

## 5. Schritte

Gate-Spalte: **ja** = der Captain gibt frei, bevor der Schritt läuft. Alle Befehle sind PowerShell-Text, nicht ausgeführt.

### U2-0 Bestandsaufnahme (nur lesen) – Gate nein
**Was:** Prozesse, Ports, GPU-Lease, Git-Stand, Hashes der zu kopierenden Dateien festhalten.
```powershell
$A1='E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung'; $RT='E:\Sedra Umgebung\GUPPI_Runtime_v1.20'
$S='E:\Sedra Umgebung\_Aufraeumen_2026-10-24\sicherung'
git -C $RT status --short; git -C $RT log -1 --format='%h %s'; git -C $A1 status --short
Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like 'E:\Sedra Umgebung*' } | select ProcessId,Name,ExecutablePath
Get-NetTCPConnection -State Listen | ? { $_.LocalPort -in 8089,18080 } | select LocalPort,OwningProcess
Get-ChildItem "$RT\workspace\GUPPI_OS\local_config","$A1\workspace\GUPPI_OS\local_config" -File | Get-FileHash | Export-Csv "$S\umstieg2_hashes_vorher.csv" -NoTypeInformation
```
**Prüfung:** `git -C $A1 status` sauber, keine unerwarteten Prozesse. **Rückweg:** keiner nötig.

### U2-1 Ruhe herstellen – Gate ja (Captain)
**Was:** Andere Sitzungen informieren: kein Bau/keine Messung mit Projektordner `<rt>\workspace\GUPPI_OS` mehr starten; ab U2-6 gilt `<a1>\workspace\GUPPI_OS`. Laufende Bauten abwarten (GPU-Lease prüfen: `TestLab(default_path(<rt>\workspace\GUPPI_OS)).holder()` leer).
**Prüfung:** Lease frei, keine `devvm_build`/`spec_check`-Prozesse. **Rückweg:** Hinweis zurücknehmen.

### U2-2 Zusätzliche Daten nach A1 kopieren (nur lesen aus `<rt>`) – Gate ja
**Was:** Alles, was in A1 fehlt, kopieren. `robocopy` mit `/E /XC /XN /XO` (vorhandene und neuere A1-Dateien bleiben, nichts wird überschrieben oder gelöscht, **kein** `/MIR`, **kein** `/PURGE`).
```powershell
$opt='/E','/XC','/XN','/XO','/COPY:DAT','/R:1','/W:1','/NP','/NFL','/NDL'
$W="$RT\workspace\GUPPI_OS\runtime_data"; $T="$A1\workspace\GUPPI_OS\runtime_data"
foreach($d in 'measurements','devvm_replays','devvm_snapshots','devvm_candidates','devvm_comments','spec_stamps','context_metrics','missions','agent_manager','e1_golden_path','external'){ robocopy "$W\$d" "$T\$d" @opt /LOG+:"$S\umstieg2_robocopy.log" }
robocopy "$W\tool_workspace" "$T\tool_workspace" @opt /LOG+:"$S\umstieg2_robocopy.log"
robocopy "$RT\workspace\GUPPI_OS\acceptance" "$A1\workspace\GUPPI_OS\acceptance" @opt /LOG+:"$S\umstieg2_robocopy.log"
robocopy "$RT\runtime\runtime_data" "$A1\runtime\runtime_data" @opt /LOG+:"$S\umstieg2_robocopy.log"
```
**Nicht dabei:** `audit`, `guard`, `testlab`, `llama_server`, `sandboxes` (eigene Schritte).
**Prüfung:** Dateizahl und Summe vergleichen (`Get-ChildItem -Recurse -File | measure Length -sum`) für jeden Ordner; Stichprobe 20 Hashes. `git -C $A1 status` bleibt sauber (alles ignoriert).
**Rückweg:** Das Robocopy-Protokoll nennt jede neu angelegte Datei; nur diese Dateien löschen. Der Rest von A1 wurde nicht verändert.

### U2-3 Python-Umgebung für A1 – Gate ja
**Was:** `.venv` und die Sandbox-Wheels nach A1.
```powershell
robocopy "$RT\runtime\.venv" "$A1\runtime\.venv" /E /COPY:DAT /R:1 /W:1 /XD __pycache__ /LOG+:"$S\umstieg2_robocopy.log"
robocopy "$RT\runtime\portable\sandbox" "$A1\runtime\portable\sandbox" /E /COPY:DAT /R:1 /W:1
robocopy "$RT\runtime\portable\devvm"   "$A1\runtime\portable\devvm"   /E /COPY:DAT /R:1 /W:1
& "$A1\runtime\.venv\Scripts\python.exe" -I -B -c "import sys,yaml,dulwich,microsandbox,requests; print(sys.prefix); print(microsandbox.__file__)"
& "$A1\runtime\.venv\Scripts\python.exe" "$A1\runtime\prepare_sandbox.py"   # nur Prüfsummen-Prüfung, ohne --install
```
**Hinweis:** In einer kopierten `.venv` sind die Startprogramme `pip.exe` & Co. an den Quellpfad gebunden; **nur `python.exe -m …` benutzen**. `pyvenv.cfg` zeigt auf das System-Python 3.14.7 (`C:\Users\David\AppData\Local\Python\pythoncore-3.14-64`), das muss bleiben. Die Umgebung ist schon einmal von `E:\WEb Projekte\…` hierher gezogen worden und lief danach.
**Prüfung:** Die Importzeile läuft, `microsandbox.__file__` liegt unter `<a1>\runtime\.venv`, `prepare_sandbox.py` meldet „Verified“.
**Rückfall (Rebuild):** `py -3.14 -m venv "$A1\runtime\.venv"`, dann `& …\python.exe -m pip install --no-index --find-links "$A1\runtime\portable\devvm\wheels" dulwich urllib3 pyyaml` und `… --find-links "$A1\runtime\portable\sandbox\wheels" microsandbox`; `requests`, `certifi`, `charset_normalizer`, `idna`, `defusedxml`, `youtube_transcript_api`, `tzdata` liegen nicht als Wheels bereit und bräuchten Netz (Gate) oder die Dateien aus der kopierten Umgebung.
**Rückweg:** `Remove-Item "$A1\runtime\.venv","$A1\runtime\portable\sandbox","$A1\runtime\portable\devvm" -Recurse` (nur Ordner, die dieser Schritt angelegt hat).

### U2-4 Engines – Gate ja (Entscheidung F2)
**Was:** Engines und Modelle brauchen **keinen Umzug als Kopie.** `b11160` und `b11371` sind in A1 vorhanden (DLLs hash-gleich, auch in `Sedra_Engine_v1\llama.cpp`), `llama_server.yaml` ist gleich (`engine_build: b11160`), die Modelle liegen außerhalb unter `E:\HermesAgentOrdner\lokale-modelle` (`local_paths.yaml`). Es gibt nur drei Dinge, die nur in der Installation liegen:
| Posten | Wofür war es gedacht (Beleg) | Empfehlung |
|---|---|---|
| `engines\llama.cpp\b11530` (1,11 GB) | Der „neueste Build“ im Absturztest zur Flash-Attention-Untersuchung vom 09.10. (`docs/FLASH_ATTENTION_UNTERSUCHUNG_2026-10-09.md`): nur 1 von 6 Läufen sauber, dazu der Fehler „Unexpected empty grammar stack“; Schluss dort: „Neuer Build b11530 als Standard? Nein“. In **keinem Rezept und keiner Konfiguration** genannt (nur in Docs). Als Zip bleibt er in `Sedra_Engine_v1` (Zip in `Back Up`, im Archiv) erhalten. | **archivieren, nicht nach A1** |
| `engines\tools\compute-sanitizer-12.4.127` (25 MB) | NVIDIA Compute Sanitizer, am 09.10. geladen und in `benchmarks/cuda_crash_hunt.py` eingebaut (Pfad `<GUPPI_Runtime>\engines\tools\…`, Varianten `sanitizer_*`). Dieses Skript ist in A1 vorhanden und sucht das Werkzeug in A1. | **kopieren**, wenn der Absturztest in A1 laufen soll (klein), sonst archivieren |
| `engines\_staging` (1,2 GB) | Heruntergeladene Zips, aus denen `engine_install.py` installierte; die Pins stehen in `llama_server.yaml`. Nur für eine Neuinstallation nötig. | **archivieren/löschen**; die Engine-Zips lassen sich aus dem Pin erneut holen |
```powershell
robocopy "$RT\engines\tools" "$A1\engines\tools" /E /COPY:DAT      # nur falls gewünscht (compute-sanitizer)
```
**Prüfung:** Hash der Engine-Dateien vergleichen: `Get-FileHash` für `…\b11160\ggml-cuda.dll` in beiden Ordnern gleich. **Rückweg:** kopierten Ordner löschen.

### U2-5 Konfiguration zusammenführen – Gate ja (Entscheidungen F1, F4)
**Was:** Keine Datei von A1 wird ersetzt; es werden Einträge ergänzt, jede Datei vorher gesichert.
1. **Sicherung:** `Copy-Item <Datei> "<Datei>.bak-2026-10-26-umstieg2"` für `role_routing.yaml`, `routing_profiles.yaml`, `switches.yaml`, `runtime\config\local_paths.yaml` in A1.
2. **`local_paths.yaml`:** `modelle-test: 'E:\HermesAgentOrdner\lokale-modelle-test'`, `hermes: 'E:\HermesAgentOrdner'`, `guppi: '<a1>'` ergänzen; `projekte`/`skillsets` nur auf Wunsch (zeigen auf `E:\WEb Projekte\…`).
3. **`role_routing.yaml`:** Die 18 Rezepte der Installation hinter das UIX-Rezept von A1 anhängen. **Rezepte mit gleicher `id` oder gleichem GGUF** (zu klären: `coder.local_qwen3_5_9b_q6_k` in A1 und das Qwen3.5-Rezept der Installation) nicht doppelt führen: der Captain wählt. Die Felder `per_slots` (Spec 2) bleiben erhalten; A1 hat den Lader dafür.
4. **`routing_profiles.yaml`:** Welches Profil aktiv ist, entscheidet der Captain: Installation `stabil` (Gemma schreibt, GPT-OSS prüft), A1 `standard` (nur Qwen3.5-9B).
5. **`switches.yaml`:** Die sechs Schalter der Installation (`job_supervisor`, `context_manager`, `resource_scheduler`, `model_loader` mit `evict_idle_models`, `llama_server` mit `mtp: true`, `token_policy`) übernehmen oder nicht; A1 hat nur `model_loader` und `llama_server` (`mtp: false`).
**Befehle (Probe, nur lesen):**
```powershell
& "$A1\runtime\.venv\Scripts\python.exe" -B -c "import sys; sys.path.insert(0,r'$A1\runtime\src'); from guppi_runtime.models.role_routing import RoutingConfig; c=RoutingConfig.load(r'$A1\runtime\config\role_routing.yaml', r'$A1\workspace\GUPPI_OS\local_config\role_routing.yaml'); print(len(c.capabilities))"
```
(Der genaue Name des Laders ist im Plan 24.10. Abschnitt 3.4 beschrieben; ggf. an A1 anpassen.)
**Prüfung:** Lader meldet alle Rezepte, `guppi doctor` ohne `*_error`. Änderung an Rezepten braucht das Gate `change_routing` (Audit-Eintrag).
**Rückweg:** `.bak-2026-10-26-umstieg2`-Dateien zurückkopieren.

### U2-6 Kontrolliert beenden der Installation – Gate ja (Captain führt aus)
**Was:** Fenster `START_SEDRA.bat` der Installation schließen (beendet Server und Modell). Danach prüfen:
```powershell
Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like 'E:\Sedra Umgebung\GUPPI_Runtime_v1.20*' }   # soll leer sein
Get-NetTCPConnection -State Listen | ? LocalPort -eq 8089                                              # soll leer sein
& "$RT\runtime\.venv\Scripts\python.exe" -B -c "from guppi_runtime.jobs.testlab import TestLab, default_path; print(TestLab(default_path(r'$RT\workspace\GUPPI_OS')).holder())"   # GPU-Lease leer
```
**Dann Nachkopie:** U2-2 für `measurements`, `devvm_*`, `acceptance` ein zweites Mal (wegen Änderungen seit der ersten Kopie).
**Rückweg:** `START_SEDRA.bat` in `<rt>` erneut starten (nichts in `<rt>` wurde verändert).

### U2-7 microVM-Cache nach A1 – Gate ja
**Was (V1):** Cache und Datenbank kopieren (ohne `run`), VMDK-Beschreibung umschreiben.
```powershell
$B="$RT\workspace\GUPPI_OS\runtime_data\sandboxes\backend_home"; $N="$A1\workspace\GUPPI_OS\runtime_data\sandboxes\backend_home"
robocopy "$B\cache" "$N\cache" /E /COPY:DAT
robocopy "$B\db"    "$N\db"    /E /COPY:DAT
$v=Get-ChildItem "$N\cache\vmdk" -Filter *.vmdk
Copy-Item $v.FullName "$($v.FullName).bak-2026-10-26-umstieg2"
(Get-Content $v.FullName -Raw).Replace('E:\Sedra Umgebung\GUPPI_Runtime_v1.20\','E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung\') | Set-Content $v.FullName -NoNewline -Encoding ASCII
Select-String -Path $v.FullName -Pattern 'FLAT' | % Line     # 5 Zeilen, alle auf <a1>
```
**Prüfung:** Dann Latenztest mit dem **A1-Projektordner**: `& "$A1\runtime\.venv\Scripts\python.exe" "$A1\runtime\benchmarks\vm_latency.py" "$A1\workspace\GUPPI_OS"` und Erwartung wie am 20.10.: `4/4 completed`, rund 1 s. Danach prüfen, dass **kein** zusätzlicher leerer Cache entstanden ist (nur ein `backend_home` unter `<a1>`).
**Abbruch:** VM startet nicht → Beschreibung aus `.bak` zurück, Ordner `backend_home` in A1 löschen und V2 versuchen (Gate).
**Rückweg:** `Remove-Item "$N" -Recurse` (nur in A1 angelegt); `<rt>` ist unverändert.

### U2-8 Audit, Tests-Datenbank, Tokens – Gate ja
**Was:** `events.jsonl` (Kette mit Kopf `EVT-007210`, Hash `ddd10dcd…6d3e`), `testlab.db` und `approval_tokens.json` der Installation **nicht** in A1 mischen. Sie gehen als Belege ins Archiv (Schritt U2-12). A1 führt seine eigene Kette weiter. Zusätzlich im Plan festhalten: der letzte Kopf der Installation, damit die Kette später nachvollziehbar bleibt.
**Prüfung:** Hash der drei Dateien vor dem Archivieren dokumentieren. **Rückweg:** keiner nötig (nichts verändert).

### U2-9 Prüfungen vor dem Umschalten – Gate ja (GPU: separates Gate)
Aus `<a1>\runtime`, mit `.venv`:
1. `run_doctor.bat` → **READY**, `LOCAL_SWITCHES_APPLIED` ohne `problems`, Schalter wie in U2-5 entschieden.
2. Tests mit der `.venv` aus A1: `python benchmarks\run_tests.py all --jobs 6` (schnelle Bahn), danach `… --slow` für die Browser-Bahn; rot ist nur, was nicht in `tests\known_red.txt` steht. Zusätzlich `test_bau_ort`, `test_local_switches`, `test_role_routing`, `test_core_boundary_src`, `test_gpu_canary` und die Spec-2-Tests einzeln benennen. Danach `benchmarks\hygiene.py` (ohne `--apply-temp`). Zahl der übersprungenen Tests vorher und nachher ins Logbuch (siehe 0a Punkt 5). Ergebnis ins Logbuch.
3. `benchmarks\uix_check.py` → Zeile **`result ok`**.
4. `vm_latency` (siehe U2-7) 4/4.
5. **Kurzstart eines Modells (GPU, eigenes Gate U-5):** GPU-Lease, Canary, ein Rezept laden, eine kurze Frage, entladen, Lease freigeben; VRAM ≤ 11,5 GB, kein Rest-Server auf 8089.
6. `devvm_build`-Trockenlauf mit `--project "$A1\workspace\GUPPI_OS"` nur nach Gate (er startet Modelle).
**Abbruch, dann zurück (U2-6 Rückweg):** doctor nicht READY, `uix_check` nicht `ok`, VM startet nicht, Canary scheitert, Lader verwirft eine Datei.

### U2-10 Git der Installation – Gate ja
**Was (empfohlen):** nichts ins A1-Repo; die Installation bleibt als Archiv. Zusätzlich ein frisches Bundle und ein Zip der `.git`-Ordner:
```powershell
git -C $RT bundle create "$S\GUPPI_Runtime_v1.20_alle_refs_umstieg2.bundle" --all
git -C $RT bundle verify "$S\GUPPI_Runtime_v1.20_alle_refs_umstieg2.bundle"
```
**Variante (nur auf ausdrücklichen Wunsch):** Die 64 Commits als geschützte Referenz ins Hub-Repo holen (ändert das gemeinsame A1-Git, aber nur um eine Referenz; kein Branch, kein Push):
```powershell
git -C $A1 fetch "$S\GUPPI_Runtime_v1.20_alle_refs_umstieg2.bundle" "refs/heads/main:refs/archiv/guppi-main-2026-10-14"
```
**Rückweg:** `git -C $A1 update-ref -d refs/archiv/guppi-main-2026-10-14`.

### U2-11 Umschalten – Gate ja
1. **Pythonweg wählen (F3, P1):** `Rename-Item "$A1\runtime\portable\python" python.aus`. **Rückweg:** zurückbenennen.
2. Start: `& "$A1\START_SEDRA.bat" --uebersicht` (oder `cockpit`), prüfen dass die Oberfläche **A1-Daten** nutzt (Fenster zeigt `Ordner: …A1…`, `workspace\GUPPI_OS` unter A1).
3. **Verknüpfung** auf dem Desktop auf `<a1>\START_SEDRA.bat` umstellen.
4. **Geplante Aufgabe (alt):** `Disable-ScheduledTask -TaskName 'GUPPI Nachtkette 2026-10-13'` (nicht löschen), weil sie auf die alte Kopie zeigt und bei jeder Anmeldung fehlschlägt; der Ersatz entsteht in U2-11b. **Rückweg:** `Enable-ScheduledTask`.
5. Sitzungen und Dokumentation: Projektordner für `devvm_build`/`spec_check`/`vm_latency` heißt ab jetzt `<a1>\workspace\GUPPI_OS`. Bauweg-Doku entsprechend anpassen (eigene A1-Änderung).

### U2-11b Nachtkette nach A1 umziehen – Gate ja (GPU-Läufe: eigenes Gate)
Ausführung nach Abschnitt 5a (N-3 Umzug, N-4 Prüfung, N-5 GPU-Lease). Neues Startskript `runtime\benchmarks\start_nachtkette.ps1` ohne festes Enddatum (Argument `-Bis`), neue Aufgabe `SEDRA Nachtkette A1 2026-10-26`, alter Eintrag nur deaktiviert. Zusätzlicher Vorschlag des Vorarbeiters: das Skript startet nur, wenn die Freigabedatei `local_config\nacht_frei.txt` existiert, damit nie ein Lauf ohne Ja des Captains die GPU belegt (Frage F12/F15).

### U2-12 Archivierung der Installation als Zip – Gate ja (Captain)
**Regel des Captains (26.10.2026):** Es gibt **eine** Startdatei: `<a1>\START_SEDRA.bat`. In der Installation wird nichts umbenannt, ergänzt oder als zweite Startdatei belassen. Das Archiv liegt **nicht** in der Sedra-Umgebung (A1 und Programmordner), sondern als `E:\Sedra Umgebung\Entwickler_Archiv\GUPPI_Runtime_v1.20.Archiv.zip`; danach gibt es den Ordner `GUPPI_Runtime_v1.20` nicht mehr.
**Zeitpunkt:** nach U2-11 (Umschalten) und dem Kurzstart eines Modells aus A1 (U2-9 Punkt 5, GPU-Gate), spätestens nach der vom Captain gewählten Bewährungszeit (Frage F9; die Installation ist bis dahin als Rückweg unverändert).
**Vorbereitet (26.10.2026), nicht ausgeführt:** Werkzeug `benchmarks\archiv_zip.py` (mit Test `tests\test_archiv_zip.py`, 6 Tests). Trockenlauf gegen die Installation: 24 967 Dateien, 4,86 GB, keine Probleme (kein Prozess, Port 8089 und Lease frei, genug Platz auf E:, Ziel noch nicht vorhanden).
**Ablauf bei Freigabe des Captains:**
1. `cd <a1>\runtime` und `python benchmarks\archiv_zip.py` (Trockenlauf, Ergebnis 0 erwartet).
2. `python benchmarks\archiv_zip.py --go` erzeugt `E:\Sedra Umgebung\Entwickler_Archiv\GUPPI_Runtime_v1.20.Archiv.zip`, `…Archiv.manifest.csv` (`path,size,sha256`) und `…Archiv.ergebnis.json` in einem Durchgang (Zip zuerst als `.part`), verifiziert jede Datei im Zip gegen das Manifest (keine fehlt, keine zu viel, `testzip`), benennt dann um und prüft den Ordner gegen das Manifest. Vorhandene Zieldateien werden nie überschrieben, nichts wird gelöscht.
3. `python benchmarks\archiv_zip.py --verify` prüft das Archiv jederzeit erneut (auch wenn der Ordner später weg ist: dann nur Zip gegen Manifest).
4. Erwartung: `zip_vs_manifest_problems` 0 und `source_vs_manifest_problems` 0 in `…Archiv.ergebnis.json`; Anzahl und Größe ins Logbuch.
5. **Löschen des Ordners macht der Captain selbst** (nach der Verifikation; Papierkorb-Limit von E: beachten). Danach: `benchmarks\hygiene.py` ohne Fund, Logbucheintrag.
Vollständig: der ganze Ordner `GUPPI_Runtime_v1.20` wird archiviert (mit `.git`, `local_config` samt Sicherungen, `audit`, `testlab.db`, `approval_tokens.json`, `sandboxes\backend_home\run`, `jobs`, `image-imports`, den Bundles, `engines` einschließlich `_staging` und `b11530`). Die Engines `b11160` und `b11371` stehen auch in A1 und in `Sedra_Engine_v1`; wer das Zip verkleinern will, kann sie mit `--exclude engines/llama.cpp/b11160` und `--exclude engines/llama.cpp/b11371` auslassen (rund 1,8 GB; nur nach Prüfung, dass die A1-Kopien vollständig sind).
**Rückweg:** Zip entpacken nach `E:\Sedra Umgebung\GUPPI_Runtime_v1.20`; die Installation lässt sich daraus wiederherstellen (die VMDK-Pfade der Installation stimmen dann wieder, weil der Ort derselbe ist).

### U2-13 A1 bekommt ein eigenes Repository – Gate ja (Captain)
**Warum:** A1 ist ein verknüpfter Worktree des Hub-Repos: die Datei `A1\.git` zeigt in `SEDRA_Build_024…\GUPPI_Runtime_v1.20\.git\worktrees\…`. Ohne diesen Schritt zerstört das Löschen des Hub-Ordners die Git-Historie von A1 (37 Branches, davon 34 nur lokal; `build25-basis` und `pruef/spec7-bau` haben je 1 Commit außerhalb des Arbeitsbranchs).
**Vorbereitet (26.10.2026), nicht ausgeführt:** Werkzeug `benchmarks\repo_unabhaengig.py` mit Test `tests\test_repo_unabhaengig.py` (6 Tests mit synthetischen Repositories: Trockenlauf ändert nichts, `--go` übernimmt alle Refs und Konfiguration, HEAD und Status bleiben gleich, der Hub ist danach löschbar, schmutziger Baum wird abgelehnt, `--rollback`, zweimal ausführen wird abgelehnt). Frisches Bundle aller Refs: `Archiv\Entwickler_Archiv\A1_alle_refs_2026-10-26.bundle` (28,6 MB, geprüft).
**Ablauf bei Freigabe:** (1) alles committen (`git status` sauber), die Installation schließen; (2) `python benchmarks\repo_unabhaengig.py` (Trockenlauf, Ergebnis 0); (3) `python benchmarks\repo_unabhaengig.py --go`: legt das Bundle an oder prüft es, baut `.git.neu` (bare) mit allen Refs und der Konfiguration des Hubs, benennt um, baut den Index neu auf (Dateien bleiben unberührt), prüft HEAD, `git status`, alle Refs, `fsck`, `worktree list`; bei jedem Fehler stellt es zurück; (4) die alte Verknüpfung liegt danach als `A1\.git\hub-link` (Rückweg: `--rollback`); (5) `git -C A1 push` bleibt unverändert möglich (Remote `origin` wird übernommen). **Danach** kann der Captain den Hub-Ordner `SEDRA_Build_024…` löschen; vorher einmal prüfen, dass `git -C A1 worktree list` nur A1 zeigt.
**Hinweis:** Die Branches `build25-basis` und `pruef/spec7-bau` werden nicht in den Arbeitsbranch gemerged (A1 wurde seitdem grundlegend umgestaltet, Regel 6a); sie bleiben als Branches im eigenen Repository und im Bundle erhalten.

## Endzustand (Zielbild des Captains, 26.10.2026)
Unter `E:\Sedra Umgebung` liegen nur noch **A1** (`A1 Sedra Main Branch Entwicklungs umgebung`, die Hauptentwicklungsumgebung mit eigenem Repository, eigener `.venv`, eigenen Engines in `engines\`, eigenen Daten in `workspace\GUPPI_OS`) und **Archiv**. Bleibende Abhängigkeiten von außen: die Modelle unter `E:\HermesAgentOrdner\lokale-modelle` (Rezepte und `local_paths.yaml`) und das System-Python, auf das `runtime\.venv` verweist (`pyvenv.cfg`: `C:\Users\David\AppData\Local\Python\pythoncore-3.14-64`). Kein Pfad in A1 zeigt auf einen anderen Ordner unter `E:\Sedra Umgebung`. Prüfung: `python benchmarks\hygiene.py` ohne Fund.

## 5a. Die geplante Aufgabe `GUPPI Nachtkette 2026-10-13` zieht nach A1 um (Ergänzung des Captains)

### N-1 Ist-Zustand (nur gelesen)
| Merkmal | Befund |
|---|---|
| Name / Pfad | `GUPPI Nachtkette 2026-10-13`, `\` (Wurzel), Zustand **Ready**, aktiviert |
| Beschreibung | „Startet die GUPPI-Nachtketten (cchat-Build, mmap-Test) nach dem Anmelden, falls sie nicht laufen. Endet selbst nach 2026-10-14 12:00.“ |
| Trigger | beim Anmelden von `MOTHER-BOARD\David` (`MSFT_TaskLogonTrigger`), ohne Verzögerung, mit Wiederholungsmuster |
| Konto | `David`, Anmeldeart **Interactive**, Rechte **Limited** |
| Aktion | `powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "E:/WEb Projekte/Guppy/GUPPI v1.20_S D A/GUPPI_Runtime_v1.20/runtime/benchmarks/start_night_chains_2026-10-13.ps1"`, Arbeitsverzeichnis leer |
| Einstellungen | `StartWhenAvailable`, nicht bei Akkubetrieb starten, **Zeitlimit PT5M**, eine Instanz (`IgnoreNew`) |
| Letzter Lauf | 26.10.2026 07:43:21, Ergebnis **4294770688 = 0xFFFD0000**, nächster Lauf: keiner |
| Ursache des Fehlschlags | **Das Skript existiert nicht mehr**: `E:\WEb Projekte\Guppy\GUPPI v1.20_S D A\GUPPI_Runtime_v1.20\runtime\benchmarks\start_night_chains_2026-10-13.ps1` ist nicht vorhanden (geprüft), der Ordner `…\GUPPI v1.20_S D A` ist weg, in `E:\WEb Projekte\Guppy` liegen nur noch Backups, Skillsets, Unterlagen. Der Code `0xFFFD0000` selbst ist kein bekannter PowerShell-Exitcode; er passt zum Start mit nicht auffindbarer Datei. Der Aufgabenplaner-Ereignislog enthält keine Einträge zur Aufgabe, daher kein Textbeleg. |
| Ist die Kette seit dem 13.10. noch gelaufen? | **Nein.** Die letzten Ergebnisdateien der Kette sind vom **14.10.2026 08:54** (`measurements\night_2026-10-13\mmap_on_moe48_ladder_1.log`, `summary_mmap.json` 08:44). Die Kette ist **absichtlich befristet**: Beim Anmelden läuft sie nur bis **2026-10-14 12:00**, danach beenden sich die Skripte selbst. Die Aufgabe selbst hat kein Ablaufdatum und startet bei jeder Anmeldung ins Leere weiter; seit dem Umzug des Ordners startet sie nicht mal mehr das Skript. |

**Folgerung:** Die Aufgabe ist ein **Überbleibsel**. Wenn die Nachtkette weiterleben soll, muss sie neu gedacht werden, nicht nur umgezogen: Ihr Programmstand ist von 13.10., das Ende ist fest im Skript (2026-10-14 12:00), und seit dem 20.10. (Linie L1) gilt der Bauweg `devvm_build.py --profile standard`, die Ketten-Skripte sind Archiv.

### N-2 Welche Skripte die Kette startet und wo sie liegen
| Skript | Aufgabe | In der Installation (Branch `installation/stand-2026-10-24`) | In A1 |
|---|---|---|---|
| `start_night_chains_2026-10-13.ps1` | Startet unten genannte Skripte beim Anmelden, wenn sie nicht laufen. Leitet `runtime` aus dem eigenen Pfad ab, nimmt `workspace\GUPPI_OS` als Projekt und `runtime\.venv\Scripts\python.exe` | ja (unversioniert, auf dem Sicherungsbranch committet) | **nein** |
| `night_queue_2026-10-13_g.py` (Kette G: Testkatalog und Werkzeuge, Lease-Reservierung `priority=1`) | | ja | `benchmarks\archiv\` |
| `night_queue_2026-10-13.py` (Chat-Build, Argument `22` = Startstunde) | | ja | `benchmarks\archiv\` |
| `night_queue_2026-10-13_b.py` (mmap-Tests) | | ja (unversioniert) | **nein** |
| `chain_judge.py`, `gpu_recovery.py`, `canary_retry.py`, `test_chain_judge.py` (Richter, Wiederaufnahme) | | ja (unversioniert) | **nein** |
| `night_g_order.json`, `night_g_order_resume.json` (Auftragsliste Kette G) | | ja | `benchmarks\` |
| `night_queue_2026-10-11.py`, `_b.py` | frühere Nachtketten | ja | `benchmarks\archiv\` |
In A1 liegen heute nur die archivierten Fassungen. **Die Aufgabe findet in A1 also kein Startskript.**

### N-3 Umzug der Aufgabe nach A1 (Gate ja)
Zwei Möglichkeiten (Frage F11): **(i) neu und leer:** nur einen sauberen Platzhalter anlegen, der eine neue Nachtkette nach dem aktuellen Bauweg startet (Inhalt später); **(ii) die alte Kette wiederbeleben** (nicht empfohlen: Ende fest im Skript, Archivstand). Beschrieben ist (i), weil der Captain Name mit Datum, A1-Aktion und alten Eintrag deaktiviert lassen will.
1. **Altes Skript nicht nach A1 kopieren.** Das neue Startskript wird als A1-Datei gebaut (z. B. `runtime\benchmarks\start_nachtkette.ps1`, Teil von A1, Commit durch die Sitzung, nicht durch diesen Plan). Es soll wie das alte `runtime` aus `$PSScriptRoot` ableiten, `workspace\GUPPI_OS` als Projekt, `runtime\.venv\Scripts\python.exe` als Python, und **kein festes Enddatum** haben, sondern ein Argument `-Bis <Datum>`.
2. **Neue Aufgabe anlegen (Text, nicht ausgeführt):**
```powershell
$a1 = 'E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung'
$act = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $a1 + '\runtime\benchmarks\start_nachtkette.ps1" -Bis 2026-11-30') `
  -WorkingDirectory ($a1 + '\runtime')
$trg = New-ScheduledTaskTrigger -AtLogOn -User 'MOTHER-BOARD\David'
$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'SEDRA Nachtkette A1 2026-10-26' -Action $act -Trigger $trg -Settings $set `
  -Description 'Startet die Nachtkette aus A1 nach dem Anmelden, falls sie nicht laeuft. Ende per Argument -Bis.' -RunLevel Limited
```
3. **Alten Eintrag nur deaktivieren, nicht löschen:** `Disable-ScheduledTask -TaskName 'GUPPI Nachtkette 2026-10-13'`.

### N-4 Prüfung
- Zuerst **Trockenlauf ohne GPU:** `powershell -NoProfile -File "$a1\runtime\benchmarks\start_nachtkette.ps1" -Bis 2026-11-30 -Trocken` (das neue Skript soll im Trockenlauf nur die Befehle ausgeben, die es starten würde). Erwartung: Ausgabe mit den A1-Pfaden, **Exitcode 0**, kein `python`-Prozess entsteht.
- Dann `Start-ScheduledTask -TaskName 'SEDRA Nachtkette A1 2026-10-26'` und `Get-ScheduledTaskInfo` → **LastTaskResult 0**; Log in `workspace\GUPPI_OS\runtime_data\measurements\night_<datum>\`.
- Der erste echte Lauf mit GPU nur mit Gate U-5/U2-9 und bei freier GPU-Lease.
- Vorab prüfen, dass alle im Skript genannten Dateien existieren (`Test-Path`), dass die Aufgabe nicht während der Arbeitszeit des Captains Modelle lädt (Startstunde im Skript), und dass die Zeitbegrenzung der Aufgabe (5 Minuten) für das **Starten** der Kette reicht (die Kette selbst läuft als eigener Prozess weiter).

### N-5 Wechselwirkung mit GPU-Lease und Modell-Scheduler (D2.7)
- **Heute (A1-Code, `jobs/testlab.py`):** Die Kette hält eine **Reservierung mit `priority=1`** (`TestLab.reserve`). Solange sie lebt (Prozess am Leben und Herzschlag frisch), werden alle Nehmer mit niedrigerer Priorität (Standard 0) zurückgestellt, auch zwischen zwei Bauten. Das Ereignis heißt `deferred`.
- **Spec 2 / D2.7 (Übergabe an Benchmarks):** Wenn der Modell-Scheduler (`sedra-scheduler`) die Lade-Lease `gpu` hält, bekommt ein anderer Prozess sie nur über die **Übergabe** (`exklusiv`, `drain_max_s` 1800, **keine Verdrängung**, `erzwingen` nur durch den Captain). `TestLab.acquire` trägt sich beim ersten Fehlversuch in `handover_requests` ein.
- **Offen, im Probelauf zu klären (Frage F12):** „Nachtkette hat Vorrang“ muss bedeuten: Sie stellt eine Übergabeanforderung, der Scheduler leert seine Slots (bis 30 min) und gibt die Lease ab; die Reservierung `priority=1` verhindert, dass der Scheduler sie sofort wieder nimmt. Ob die Reservierung auch den Scheduler selbst (Nehmer mit Priorität 0) zurückstellt, steht im A1-Code nur für `try_acquire`; ob der Scheduler denselben Weg nutzt, ist nicht geprüft. Vor dem ersten Echtlauf: Test mit laufendem Scheduler und Reservierung (ohne GPU, mit Attrappe).
- Ohne Reservierung und ohne Scheduler ändert sich nichts („the race of the polling takers stays as it was“).

**Rückweg (Aufgabe):** `Unregister-ScheduledTask -TaskName 'SEDRA Nachtkette A1 2026-10-26' -Confirm:$false` (nur die neue Aufgabe), `Enable-ScheduledTask -TaskName 'GUPPI Nachtkette 2026-10-13'` (der alte Eintrag war nur deaktiviert). Gate: **ja** (Anlegen, Deaktivieren, erster Echtlauf).

---

## 5b. Ort der Daten: Variante A oder B (Ergänzung des Captains)

**Grundsatz:** Der Code kommt aus Git (A1, Branch `spec/agenten-orchestrierung`). Was nicht nach Git gehört, ist durch `.gitignore` ausgeschlossen: `engines/`, `workspace/`, `runtime/.venv/`, `runtime/runtime_data/`, `/runtime_data/`, `/local_config/`, `runtime/config/local_paths.yaml`, `runtime/portable/`, `*.sqlite`, `*.log`, `*.bak-*`, `**/tokens.json`. Frage: Kann die Laufzeit ihre Daten aus einem Ordner **neben** dem Code lesen, damit ein frisches `git clone` ohne Datenverlust möglich ist?

**Befund (aus dem Code gelesen):**
| Was | Wo gelesen | Steuerbar? |
|---|---|---|
| Projektwurzel (`local_config`, `runtime_data`: Audit, TestLab, Messungen, `sandboxes\backend_home` = VM-Cache, `sprache`, `fisch`, `acceptance` …) | Argument `--root` von `uix_start` und der Bauwerkzeuge (`devvm_build <projekt>`, `spec_check --project`, `vm_latency <projekt>`) | **ja**, aber `START_SEDRA.bat` setzt `PROJ=%ROOT%\workspace\GUPPI_OS` fest (Zeile 14), ohne Umgebungsvariable oder Argument zum Überschreiben |
| Architektur-Ordner | `--architecture` (fest `%ROOT%\architecture\…`, ist im Git) | gehört zum Code |
| Engines | `engine_root` in der Server-Konfiguration; Vorgabe ist `<GUPPI_Runtime>\engines` (`engine_provision.DEFAULT_ROOT = parents[4]/"engines"`, also **neben `runtime`**) | ja, über `engine_root` (ob dort `<name>`-Platzhalter aus `local_paths.yaml` gelten, nicht geprüft) |
| Modelle | `<modelle>` aus `runtime\config\local_paths.yaml` | ja, schon außerhalb |
| `local_paths.yaml`, `runtime\runtime_data\skill_library`, Wurzel-`runtime_data\gpu_canary*.json`, `local_config\update\` | relativ zum Code (`Path(__file__).parents[…]`) | **nein**, liegen im Codeordner |
| `.venv`, `portable\python`, `portable\sandbox` | `START_SEDRA.bat`: `%RT%\.venv`, `%RT%\portable\python` | **nein**, codegebunden |
| VM-Cache-Pfade (VMDK) | absolute Pfade in der Beschreibungsdatei, abgeleitet vom Projektordner | folgen dem Projektordner |

### Variante A – Daten in A1 unter den ignorierten Ordnern (Plan oben, U2-2 bis U2-8)
- **Vorteile:** Keine Änderung an A1-Code oder Starter. Genau der heutige Zustand, nur mit mehr Daten. Aufwand wie in Abschnitt 5 beschrieben (~2–3 h).
- **Nachteile:** Daten und Code teilen den Ordner. Ein `git clone` in einen neuen Ordner startet leer; der Captain muss `workspace`, `engines`, `.venv`, `local_paths.yaml`, `portable` von Hand mitnehmen. Wer den A1-Ordner ersetzt oder löscht (oder `git clean -fdx` ausführt), verliert alles Ignorierte. Der VM-Cache hängt am langen A1-Pfadnamen (61 Zeichen Reserve). Alle Worktrees haben je eigene (leere) `workspace`-Ordner oder müssen auf A1 zeigen.

### Variante B – Daten in einem eigenen Ordner, z. B. `E:\Sedra Umgebung\Sedra_Daten`
Aufbau: `Sedra_Daten\workspace\GUPPI_OS\…` (Projektwurzel), dazu `Sedra_Daten\engines`, `Sedra_Daten\sicherung_env` (Kopie von `.venv`-Listen, `local_paths.yaml`, `portable\sandbox`).
- **Nötige Änderungen (klein, aber im Git):**
  1. `START_SEDRA.bat`: Zeile 14 ersetzen durch `if defined SEDRA_DATEN (set "PROJ=%SEDRA_DATEN%\workspace\GUPPI_OS") else (set "PROJ=%ROOT%\workspace\GUPPI_OS")`. Dasselbe in `start_sedra.sh`. Ohne gesetzte Variable bleibt alles wie heute (andere Rechner unverändert).
  2. Umgebungsvariable `SEDRA_DATEN` (Benutzerebene) setzen; Bauwerkzeuge bekommen den Projektordner weiter als Argument (`devvm_build "$env:SEDRA_DATEN\workspace\GUPPI_OS"`).
  3. Engines: `engine_root` in der lokalen Serverkonfiguration (nicht im Git) auf `Sedra_Daten\engines` setzen – oder Engines in A1 lassen (sie sind aus dem Zip wiederholbar und hash-gleich in `Sedra_Engine_v1`).
  4. Alternative zu 1 ohne Git-Änderung: Verzeichnis-Junction `mklink /J "<a1>\workspace" "…\Sedra_Daten\workspace"`. **Nicht empfohlen:** Git behandelt eine Junction womöglich nicht als „Ordner“ im Sinn von `workspace/` in `.gitignore` und listet sie als unversioniert (nicht getestet).
- **Vorteile:** Frisches `git clone` (oder ein Wechsel des Branches/Worktrees, `git clean -fdx`) berührt die Daten nicht. Daten und Code sind unabhängig sicherbar. Alle Worktrees und Sitzungen benutzen **einen** Projektordner, auch der Bauort für `devvm_build`/`spec_check`/`vm_latency` ist dauerhaft derselbe (Fehlerquelle „falscher Projektordner → leerer VM-Cache“ entfällt). Ein kurzer Pfad gibt dem VM-Cache mehr Reserve: `E:\Sedra Umgebung\Sedra_Daten\workspace\GUPPI_OS\runtime_data\sandboxes\backend_home` ist **84** Zeichen lang (A1: 115), Reserve **92** statt 61 Zeichen. Die VMDK-Pfade müssen nur **einmal** umgeschrieben werden und bleiben bei späterem Umbenennen oder Neuklonen von A1 gültig.
- **Nachteile:** Eine kleine, aber echte Änderung an Starter-Skripten in Git (Gate). Zwei Orte statt einem; `hygiene.py` kennt `Sedra_Daten` nicht (prüft „unbekannte Ordner unter `E:\Sedra Umgebung`“, Eintrag nötig). `.venv`, `portable\python`, `local_paths.yaml`, `runtime\runtime_data`, `engines` (ohne `engine_root`) bleiben im Codeordner und müssen bei einem Neuklon aus einer Kopie in `Sedra_Daten\sicherung_env` zurückgeholt werden – das Datenproblem ist also gelöst, das Umgebungsproblem nur halb. Die heutigen A1-Daten (`workspace\GUPPI_OS`, inkl. `sprache` 556 MB, `cloud_keys.json`) müssten **verschoben** werden: das ist ein Eingriff in den laufenden Stand des Captains (Gate und Ruhefenster).
- **Zusätzlicher Aufwand gegenüber A:** ~1 h (Starter ändern, Variable, Verschieben der A1-Daten, einmal VMDK umschreiben, `hygiene` anpassen, Test mit `uix_check`/`vm_latency` am neuen Ort).

**Empfehlung:** **Variante B**, weil sie genau das Ziel „späteres frisches `git clone` ohne Datenverlust“ erfüllt und dabei die VM-Pfadreserve verbessert. Umsetzung in dieser Reihenfolge: (1) Erst die Installation nach A1 integrieren wie in Abschnitt 5 (Variante A, Daten bleiben in A1). (2) Nach der Bewährungszeit (U2-12) die Daten in einem eigenen Schritt U2-B nach `Sedra_Daten` verlegen (Starter-Änderung als kleiner Commit, Daten verschieben, VMDK umschreiben, Tests wiederholen). So gibt es nie einen Zustand, in dem der Captain weder Installation noch A1 als sicheren Rückweg hat. Wer sofort B will: U2-2 bis U2-8 mit Ziel `Sedra_Daten` statt `<a1>\workspace\GUPPI_OS` ausführen und zuvor die A1-Daten dorthin verschieben (zusätzliches Ruhefenster).

**Neue Fragen:** **F11** Nachtkette neu (i) oder alte beleben (ii)? **F12** Soll die Kette über die Übergabe D2.7 laufen (Scheduler leert die Slots) oder nur außerhalb der Scheduler-Zeiten? **F13** Variante A zuerst und B später (Empfehlung), sofort B oder dauerhaft A? **F14** Name und Ort des Datenordners (Vorschlag `E:\Sedra Umgebung\Sedra_Daten`)?

---

## 6. Zeitbedarf und Unterbrechung

| Schritt | Dauer (Schätzung) | Unterbricht die Installation? |
|---|---|---|
| U2-0, U2-1 | 10 min | nein |
| U2-2 (Kopieren, ~0,3 GB Daten, ~20.000 Dateien) | 5–10 min | nein (nur lesen) |
| U2-3 (`.venv` 0,11 GB, ~1.500 Dateien, Sandbox-Wheels 40 MB) | 5 min | nein |
| U2-4 | 0–5 min | nein |
| U2-5 (Konfiguration, Entscheidungen) | 30–60 min inkl. Probe | nein |
| U2-6 (Beenden, Nachkopie) | 10 min | **ja, beendet** |
| U2-7 (VM-Cache, Latenztest) | 10 min | läuft erst nach U2-6 |
| U2-8, U2-10 | 10 min | nein |
| U2-9 (Prüfungen, ohne GPU) | 30–45 min; mit GPU +10 min | nein |
| U2-11 | 10 min | nein |
| U2-11b (Skripte, Aufgabe, Trockenlauf; GPU-Probe separat) | 30–45 min | nein |
| U2-12 | 7 Tage Wartezeit, dann 30 min | nein |

Ohne Wartezeit auf Freigaben insgesamt rund 2–3 Stunden; **ohne Unterbrechung der Installation** geht alles bis U2-5, danach ein kurzes Fenster (U2-6 bis U2-9).

## 7. Risiken

- **Pythonwahl:** Ohne P1 startet `START_SEDRA.bat` aus A1 mit `portable\python` (kein Sandbox-SDK) und die DevVM geht nicht. P1 ändert nur einen ignorierten Ordnernamen.
- **Falscher Projektordner** legt einen leeren VM-Cache an; deshalb in jedem Befehl den A1-Pfad ausdrücklich angeben.
- **Gleichzeitiger Start** von Installation und A1: GPU-Lease und Port 8089; deshalb U2-6 vor jedem A1-Start.
- **`robocopy`-Optionen:** `/MIR`, `/PURGE`, `/MOVE` sind nicht vorgesehen. Überschreiben ist durch `/XC /XN /XO` ausgeschlossen.
- **Geheimnisse:** `cloud_keys.json` und `approval_tokens.json` werden weder kopiert noch ersetzt.
- **Mischen von Konfiguration:** Gate `change_routing` mit Audit; Sicherung `.bak-2026-10-26-umstieg2` je Datei.
- **Pfadlänge der VM:** 61 Zeichen Reserve in A1; der Ordnername `A1 Sedra Main Branch Entwicklungs umgebung` darf nicht länger werden.
- **Worktree-Eigenschaft von A1:** A1 darf nur per `git worktree move` verlegt werden, der Hub bleibt.

## 8. Entscheidungen des Captains

- **F1 Rezepte und Profile:** Welche der 18 Rezepte der Installation kommen nach A1, was passiert mit dem UIX-Rezept `coder.local_qwen3_5_9b_q6_k`, welches Profil ist aktiv (`stabil` oder `standard`)?
- **F2 Engines:** Engines und Modelle sind in A1 bzw. außerhalb vorhanden (0a Punkt 2). Offen nur: `b11530` und `compute-sanitizer` übernehmen oder nicht (Vorschlag: nein / nur Sanitizer bei Bedarf)?
- **F3 Pythonweg:** P1 (`portable\python` umbenennen, `.venv`-Weg wie die Installation) oder P2 (Ersteinrichtung mit SDK)?
- **F4 Schalter:** Die sechs Schalter und `mtp: true` der Installation übernehmen? `local_paths`: `projekte` und `skillsets` (zeigen nach `E:\WEb Projekte\…`) übernehmen?
- **F5 Sitzungen:** Welche Sitzungen nutzen `<rt>\workspace\GUPPI_OS` als Bauort, und wann werden sie umgestellt oder beendet?
- **F6 64 Commits:** Nur Archiv (Empfehlung) oder zusätzlich als geschützte Referenz ins Hub-Repo (U2-10 Variante)?
- **F7 VM:** V1 (Cache kopieren, Pfade umschreiben, Empfehlung) oder V2 (neu aufbauen, braucht ggf. Netz)?
- **F8 Verknüpfung:** Desktop-Verknüpfung auf `<a1>\START_SEDRA.bat` umstellen (Vorschlag ja). Die Nachtkette selbst: F11 bis F12 (Abschnitt 5a).
- **F9 Bewährungszeit:** Wie lange läuft die Installation unverändert als Rückweg liegen (Vorschlag 7 Tage), bevor sie archiviert wird?
- **F10 Zeitpunkt:** Wann ist ein Zeitfenster ohne Bau und Messung für U2-6 bis U2-11b?
- **F11 bis F14:** siehe Abschnitt 5a und 5b (Nachtkette neu oder alte beleben, Übergabe D2.7, Variante A/B, Datenordner). Zu F11: der Captain hat entschieden, dass die Nachtkette mit umzieht; offen ist nur, ob sie neu (empfohlen) oder als alte Kette weiterleben soll, und welche Warteschlange sie fährt.
- **F15 Freigabedatei:** `local_config\nacht_frei.txt` als Schutz vor GPU-Läufen ohne Ja des Captains (Vorschlag ja).
- **F16 Update-Funktion:** nicht für diesen Umzug (0a Punkt 3); für spätere Installationen aus Releases beibehalten? (Vorschlag ja, keine Änderung.)

## 9. Nicht geprüft

- Ob die Ersteinrichtung (P2) und das Anlegen eines neuen VM-Caches (V2) offline gehen.
- Ob die zwei Rezepte für Qwen3.5-9B (A1 und Installation) fachlich identisch sind; nur das gleiche GGUF ist belegt.
- Der genaue Name des Rezeptladers in A1 (der Befehl in U2-5 ist ein Muster).
- Der Inhalt von `events.jsonl` (nur der Kopf `EVT-007210` wurde gelesen).
- Ob Skripte außerhalb von `runtime\src`, `runtime\config` und `runtime\benchmarks` den Pfad `<rt>` nennen (Stichprobe in den Konfigurationen, 2.716 Dateien, ohne Treffer).
