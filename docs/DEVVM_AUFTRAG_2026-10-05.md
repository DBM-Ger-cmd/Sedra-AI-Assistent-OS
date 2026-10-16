# Auftrag: GUPPIs VM wird zur DevVM (Entwicklungsumgebung für GUPPI und seine Untermodelle)

Stand: 2026-10-05. Auftraggeber: Captain. Dieser Text ist der Auftrag an GUPPI (Self-Development, Stufe E1 auf Kandidaten) und zugleich die Vorgabe für alle, die daran bauen.

## 1. Ziel

GUPPI soll innerhalb seiner eigenen, isolierten Umgebung eine **richtige Entwicklerumgebung** haben (die „DevVM"): einen Arbeitsbereich, in dem er und seine Untermodelle
Projekte anlegen (auch neue Ordner und Dateibäume), Code schreiben, prüfen, testen und überarbeiten können, mit Werkzeugen statt nur mit Text, und in dem GUPPI **Unter-Agenten**
(kleine Modelle mit eigener Rolle) losschicken und deren Ergebnisse einsammeln kann. Nichts davon darf die Grenzen der VM oder die Gates des Captains aufweichen.

## 2. Ausgangslage (gemessen und im Code, nicht geraten)

| Bereich | Heute |
|---|---|
| VM | microsandbox 0.7.4, Gastimage `python:3.12-slim`, kein Netz, RESTRICTED, tmpfs-Wurzel (256 MiB), 1024 MiB RAM, 2 CPUs, Gastnutzer 65534, Befehls-Limit 30 s, Job-Limit 120 s, max. 200 Dateien, 1 MiB je Datei. Eine VM je Job, danach weg. `target_qualified: true` (Captain, 2026-10-02). VM-Start schlägt etwa 2 von 8 Mal fehl (Wiederholung nötig). |
| Werkzeuge für Modelle | `model_tools.py`: `read_file`, `write_file` (nur .py, 20 KB), `check_syntax`, `submit_fix`, `submit_review`; gebunden an einen Ordner, führt nie Modellcode aus. Dazu `tools/` (filesystem, shell mit Allowlist, git, web, model_runtime, hardware_manager) hinter dem Guard. |
| Richter | `benchmarks/judge.py`: führt die Prüfungen jedes Kandidaten **in der VM** aus (ein VM-Aufruf für alle, je Kandidat ein Prozess mit Zeitlimit). Ergebnis „Eingabe, erwartet, bekommen" geht an das Modell zurück. |
| Kleine Modelle | Jan-code-4b (Umsetzer) löst mit Werkzeugen 13 von 16, im Team mit Test-Richter und SWE-Review 15 von 16 (`MESSUNGEN.md` 3e/3f). Flash-Attention muss **aus** bleiben (CUDA-Abstürze, 3b/3c). Nur **eine** Lektion pro Prompt (3g). SWE-Review taugt nicht als alleiniger Richter. |
| Rechte | Stufen 0 bis 6 als Obergrenze über dem Guard (`permission_levels.py`), Standard `max_level: 2`; Captain-Gates für alles Heikle; Kandidaten-Lebenszyklus (Test, Abnahme, Rücknahme); E1 Auto-Development aus, E3 nie automatisch. |
| Betrieb | Test-Lab mit GPU-Lease (ein Modell auf der 12-GB-Karte), `run_log.py` für unverlierbare Ergebnisse, Standardstart `uix_start`. |

## 3. Anforderungen

### A. Sitzung statt Einzelaufruf
1. Ein **Arbeitsbereich pro Mission**, der über mehrere Befehle bestehen bleibt (mehrere Kommandos in einer VM-Sitzung), mit Anlegen, Verschieben, Kopieren und Löschen von Ordnern und Dateien **nur innerhalb** `/workspace`.
2. Standard-Entwicklerwerkzeuge im Gast, soweit das Image sie hat oder offline nachgeladen werden können: Python 3.12, `unittest`, Syntax-/Stilprüfung, Diff, Textsuche. Falls Git oder `pytest` fehlen: Bedarf messen und **offline** als geprüftes Paket einbringen (Prüfsumme, kein Netz, Image-Änderung nur mit Captain-Gate).
3. Grenzen sichtbar machen und bei Bedarf **vorschlagen** (nicht selbst ändern): Zeit-, Speicher-, Datei- und Dateigrößen-Limits, Startfehlerrate der VM.

### B. Werkzeugsatz für Untermodelle
1. Erweiterung von `model_tools.py` um: `list_dir`, `make_dir`, `move_file`, `search_text`, `diff_files`, `run_tests` (läuft in der VM, liefert die Prüfliste „Eingabe, erwartet, bekommen"), `run_python` (kurze Skripte, nur VM).
2. Jedes Werkzeug ist an den Arbeitsbereich gebunden (kein Pfad nach außen, keine Symlinks), hat Größen- und Zeitlimits, wird im Audit protokolliert und läuft hinter Rechtestufe und Guard.
3. Werkzeuge pro Rolle zuschneiden (Umsetzer, Prüfer, Tester bekommen je nur, was sie brauchen) und mit **jedem** vorgesehenen Modell auf Tauglichkeit messen (Tool-Aufruf-Format, Abbrüche), bevor sie freigegeben werden.
4. Neue Werkzeuge entstehen als **Kandidaten** (Admission-Gate: erst die Lücke belegen), nicht still im laufenden Betrieb.

### C. Unter-Agenten
1. GUPPI (Planer) kann Unter-Agenten mit **Rolle, Auftrag, Werkzeugsatz, Kontext und Budget** (Anzahl Aufrufe, Zeit, Tokens) starten und deren **strukturierte Übergabe** (`submit_*`) einsammeln.
2. Tiefe 1: Unter-Agenten starten keine weiteren Agenten. Höchstens ein Modell gleichzeitig auf der GPU (Lease; Wechsel nutzt die Ladezeit von wenigen Sekunden).
3. Schutz gegen Schleifen und Ausreißer ist an: `loop_guard`, `runaway_guard`, Turn-Limit mit Hinweis kurz vor dem Limit, Neustart eines abgestürzten Modell-Servers mit einem Wiederholungsversuch.
4. Jeder Agentenlauf hat ein Schrittjournal und einen Eintrag im Run-Log (wer, was, womit, Ergebnis, Dauer).

### D. Qualität zuerst
1. **Ausgeführter Test entscheidet** (Richter in der VM), nicht das Urteil eines Modells. Modell-Prüfer liefern nur Begründungen für die Nachbesserung.
2. Kleine Modelle: **höchstens eine** passende Lektion im Prompt; Flash-Attention aus.
3. Jede neue Fähigkeit bekommt Tests (nur die betroffenen Tests laufen, neue Tests werden in der Testdatei gespeichert) und eine Messung gegen die Ausgangswerte aus Abschnitt 2.

### E. Sichtbarkeit
1. Ein Fenster „DevVM" in der Oberfläche: Dateibaum des Arbeitsbereichs, laufende Agenten mit Rolle und Stand, Test- und Prüfergebnisse, Log. Nur lesen, Eingriffe laufen über die vorhandenen Karten und Freigaben.

## 4. Leitplanken (nicht verhandelbar)

- **Kein Netz**, kein unsicherer Host-Fallback, keine Host-Dateien in der VM außer ausdrücklich bereitgestellten Kopien. Modellcode läuft **nie** auf dem Host.
- Die Grenzen der VM (RESTRICTED, kein Netz, `/.msb` geschützt, Befund Port 53 dokumentiert) werden nicht gelockert. `target_qualified` ändert nur der Captain.
- **Captain-Gate** bei: Export vom Arbeitsbereich auf den Host, Änderung des Gastimages, neuem Werkzeug im Regelbetrieb, Rechtestufe über 2, jedem Löschen außerhalb des Arbeitsbereichs. Gates werden vorgelegt, nie selbst bestätigt.
- Neues entsteht als **Kandidat** mit Test, Abnahme und Rücknahmeweg (`archiv/`-Sicherung vor Änderungen an Bestehendem). E1 nur auf Kandidaten, E3 nie automatisch.
- Vor jedem Modellstart die GPU-Lease halten (`testlab_cli.py`); nach dem Lauf entladen.
- Ergebnisse gehen über `run_log.py` in `measurements/logs/`; keine Messung ohne Protokoll.

## 5. Vorgehen in Phasen (jede mit Abnahmekriterium und Bericht)

| Phase | Inhalt | Abnahme |
|---|---|---|
| 0 | Bestandsaufnahme der VM als Entwicklerumgebung: Was ist im Image, wie lange dauert Start, wie viele Fehlstarts, welche Limits stören? | Bericht mit Messwerten, offenen Lücken und Vorschlägen (ohne Änderungen) |
| 1 | Sitzung: Arbeitsbereich über mehrere Befehle, Ordner anlegen/verschieben | Test: 10 aufeinanderfolgende Befehle in einer VM, Dateien bleiben, nichts außerhalb `/workspace` erreichbar |
| 2 | Werkzeugsatz B mit Rechten, Audit, Limits | Tests je Werkzeug, Ausbruchsversuche (Pfad nach außen, Symlink, Übergröße) scheitern; Toolformat-Messung je Modell |
| 3 | Unter-Agenten C | Ein Planer-Lauf startet Umsetzer und Prüfer, Budget wird eingehalten, Schleife wird gestoppt, Journal vollständig |
| 4 | Richter und Pipeline D | Wiederholung des Teamtests (8 Aufgaben): mindestens so gut wie 15 von 16 bei ≤ 1 Lektion |
| 5 | Fenster E | Sicht auf Baum, Agenten, Ergebnisse; kein Schreibzugriff |
| 6 | Abnahmelauf | Ein neues kleines Modul (mit Ordnerstruktur und Tests) entsteht von Grund auf durch Planer und Unter-Agenten in der DevVM; alle Tests grün; Bericht |

Nach jeder Phase: kurzer Bericht (gebaut, Tests, Messwerte, offene Punkte) und Halt für die Entscheidung des Captains.

## 6. Nicht-Ziele
Kein Internetzugriff der VM, kein Dauerbetrieb von Agenten ohne Captain, keine Selbständerung der Kernmodule (E3), keine Änderung am Gastimage ohne Gate, keine neue GPU-Last neben der Lease.

## 7. Entscheidungen des Captains (2026-10-05)
1. **Git im Gast: ja.** Die Änderung des Gastimages (Git) läuft trotzdem über den Importpfad mit Prüfsumme und Gate: erst als Kandidat vorbereiten (offline beschafftes Paket, SHA256, keine Netzverbindung der VM), dem Captain zur Freigabe vorlegen, danach den Pin in `config/sandbox.yaml` ändern. Bis dahin Diff gegen Sicherungskopien.
2. **Höchstdauer eines Agentenlaufs: 10 Minuten und 40 Werkzeugaufrufe.** Beides sind harte Grenzen je Lauf; bei Überschreiten wird der Lauf beendet und das bisherige Ergebnis mit dem Grund übergeben.
3. **Neue Ordner: ja, wenn notwendig.** Unter-Agenten dürfen unter `/workspace` neue Ordner anlegen (bis 200 Dateien je Mission, wie das Eingabelimit); jede Anlage wird im Journal und im Audit vermerkt. Nie außerhalb von `/workspace`.

## 8. Phase 0: Messung (läuft)
Skript `runtime/benchmarks/devvm_probe.py`; Bericht danach in `docs/DEVVM_PHASE0_BERICHT_2026-10-05.md`.
