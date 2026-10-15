# Stärken-Inventur SEDRA und zwei Gestaltungsrichtungen (Planung, 14.10.2026, 17:50)

Captain: *beim Planen bleiben; die Stärken des Systems einsehen und ausbauen; nicht am Retro festhalten; aber es darf nicht wie ein
reines Chatfenster wirken.* Diese Inventur ist aus dem Code gezogen (`runtime/src/guppi_runtime`, Stand Build 6), nicht aus Absichten.

## 1. Was SEDRA wirklich kann – und was davon heute zu sehen ist

| # | Stärke (Modul) | Was es leistet | Heute sichtbar? | Wie die neue Oberfläche es zeigen sollte |
| --- | --- | --- | --- | --- |
| S1 | **Gebundene Freigaben** (`core/guard.py`, `request_binding.py`) | Einmal-Token, gebunden an Mission, Aktion, Ziel und Inhalt; nichts Bleibendes ohne Captain | Als Gate-Box mit JSON-Rückfrage – lästig, weil zu oft und zu technisch | Eine **Entscheidung** pro bleibender Wirkung, mit Vorschau („schreibt 2 Dateien“) und Rücknahme; Vertrauensstufe je Projekt entscheidet, was vorab erteilt ist |
| S2 | **Nachweiskette** (`audit.py`, `selfdev/development_evidence.py`, `core/step_journal.py`) | Append-only Audit, Belege für Behauptungen, Checkpoints ohne stilles Wiederholen | Nur im Logbuch als JSON | **Spur** an jeder Aufgabe: Zeit · Ereignis · Hash, lesbar in vier Zeilen (Richtung A zeigt es als eigene Spalte) |
| S3 | **Isolierte Ausführung** (`sandbox/`, `devenv/devvm*.py`, microVM, Netz aus) | Kandidat entsteht abseits des Projekts, Übernahme erst nach Prüfung | „Entwicklung READY“ im Tray; Kandidat nur als Liste | **Kandidat-Diff** als Hauptansicht der Werkbank; „Übernehmen / Erst ansehen / Verwerfen“ |
| S4 | **Verifikation statt Behauptung** (`candidate_verification.py`, `candidate_tests.py`, `verification_gate.py`, `modules/verification.py`) | Tests laufen wirklich; PREPARED_NOT_TESTED ≠ TESTED_PASS ≠ ACCEPTED | Ergebniszeile in der Karte | **Tests-Reiter** mit Tabelle, Dauer, fehlgeschlagene aufklappbar; Qualifikation als Wort, nicht als Code |
| S5 | **Lokale Modellsouveränität** (`models/role_routing.py`, `routing_profiles.py`, `llama_server_runtime.py`, `gpu_preflight.py`, `testlab.py`, `model_add.py`, `standard_test.py`) | Rollen → Rezepte → GGUF; GPU-Sperre; Standardtest findet den Kontext; neues Modell in drei Schritten | Werkstatt (seit Build 5 gut) | Bleibt als Werkstatt; im Pult nur Modell · Kontext · Token/s · GPU |
| S6 | **Selbstentwicklung mit verstecktem Test** (`selfdev/`, `devenv/buildflow_*`, `devvm_specs`, Guppy-Meter) | GUPPI baut nach Spec, Test unsichtbar für das Modell; Meter zählt GUPPI- gegen Claude-Zeilen | Meter-Fenster, Münzloch; Specs nur im Dateisystem | **Routinen** (Nachtkette) als Aufgaben mit nächstem Lauf; GUPPI-Anteil im Pult/Besatzung; „Als Skill festhalten“ aus einer gelungenen Aufgabe |
| S7 | **Schutz vor Leerlauf und Verschwendung** (`jobs/rework_watch.py`, `runaway_guard.py`, `loop_guard.py`, `token_policy.py`, `context_manager.py`, `resource_scheduler.py`) | Erkennt Wiederholungsschleifen, Endlos-Antworten, Kontextbudget, Token-Richtlinie | Unsichtbar, außer als Fehlertext | **Kosten-Reiter** je Aufgabe (Token, GPU-Zeit, Abbrüche mit Grund); Richtlinie im Pult |
| S8 | **Umgebungsbewusstes Modell** (`chat_tools.py`: get_model_status, list_models, list_missions, recent_audit, read_doc, propose_*) | Das Modell schaut nach statt zu raten; Änderungen nur als Vorschlag mit Gate | Chat antwortet richtig, Vorschlag landet in Modelle | Vorschläge erscheinen als **Entscheidung** im Gespräch und im Pult, nicht in einem anderen Fenster |
| S9 | **Rollen und Besatzung** (`agent_manager/`: Templates, Instanzen, Qualifikation, Zulassung über Gate; `routing` Rollen) | Agent wird nur durch den Captain Instanz; VERIFIED durch Abnahme-Suite | Tabellen, Organigramm (Build 5) | Besatzung als schmale Leiste mit Zustand; Details auf Klick |
| S10 | **Skill-Wissen als Daten** (`skill_library/`, Flag-Prüfung, eigene Skills mit Gate, `lesson_store`) | Nachschlagewerk für den Coder, nie ausgeführt; Lektionskarten nach Fehlern | Bibliothek (Build 5) | Bleibt; „Als Skill festhalten“ und Lektionen als Vorschlag im Gespräch |
| S11 | **Machbarkeit vorab** (`feasibility.py`, `readiness.py`, `hardware_pass.py`, `capability_router.py`) | EXECUTABLE / NOT_NOW / BLOCKED / UNSUPPORTED mit Grund, Hardwarepass, Fähigkeitslücken | Fehlertext | GUPPI sagt im Gespräch *vor* dem Start, was fehlt – und bietet den Schritt an (Modell laden, Skill fehlt, GPU belegt) |
| S12 | **Maskottchen und Metaphern** (Guppy-Stimmung, Seekarte, Münzloch) | Zustand auf einen Blick, Freude an der Bedienung | Retro-Desktop | Bleiben, aber klein: Guppy im Pult, Seekarte als Verlauf der Aufgabe, Münzloch im Kosten-Reiter |

**Befund:** Die Stärken S1–S4 und S7/S11 sind die eigentlichen Alleinstellungsmerkmale (gebundene Freigaben, Nachweise, isolierte
Kandidaten, echte Verifikation, Schutz vor Verschwendung, Machbarkeit vorab) – und genau die sind heute am wenigsten sichtbar. Ein
reines Chatfenster würde sie verstecken; ein Retro-Desktop zerstreut sie auf zehn Fenster. Die Oberfläche muss **Nachweise und
Entscheidungen** nach vorn holen und das Gespräch als Steuerung daneben halten.

## 2. Zwei Richtungen (Skizzen in `shots/uix2/`)

### A · Leitstand (`uix2_A_leitstand.png`)
Oben sieben Instrumente (Zustand, Modell, GPU, Entscheidungen, Aufgaben, Vertrauen, Kommando). Darunter drei Spalten: **Aufgaben**
(mit Fortschrittsbalken, die wartende zuerst, Routinen darunter), **Nachweise** (Kandidat · Tests · Spur · Kosten für die gewählte
Aufgabe), **Besatzung · Maschine**. Das Gespräch ist eine zweizeilige Kommandozeile unten, aufklappbar.
- Stärken: zeigt S1–S4, S7 ständig; nichts wirkt wie ein Chat; viele Aufgaben bleiben überschaubar (Captain-Problem „Überblick verloren“).
- Schwächen: dichter; für Einsteiger strenger; Dateien/Explorer brauchen einen eigenen Reiter in „Nachweise“.
- Passt zu: Nachtketten, mehreren parallelen Aufgaben, Betrieb über Stunden.

### B · Werkbank (`uix2_B_werkbank.png`)
Links ein Objektbaum (Projekt, Aufgaben, Werkstatt, Besatzung, Bibliothek, System), in der Mitte die **Werkbank** mit dem Werkstück
(Kandidat links, Verlauf/Tests/Kosten rechts, Werkzeuge oben), rechts das Gespräch als schmale Seitenleiste. Pult als eine Zeile.
- Stärken: ruhig, ein Werkstück zur Zeit, Diff und Tests nebeneinander; der Baum ersetzt zehn Fenster, ohne Instrumentendichte.
- Schwächen: viele parallele Aufgaben sieht man nur im Baum; Instrumente (GPU, Token) sind Chips statt Anzeigen.
- Passt zu: konzentriertem Arbeiten an einem Projekt, Prüfen von Kandidaten, Lernen des Systems.

### Gemeinsam (unabhängig von A/B)
Entscheidungen statt Karten (eine pro bleibender Wirkung); Vertrauensstufe je Projekt; Kandidat-Diff und Tests als Nachweise;
Spur in vier Zeilen; Routinen als Aufgaben; Guppy klein im Pult; Erscheinungsbilder Retro/Klar/Nacht als Haut, nicht als Struktur.
Technisch: dieselben klassischen Skripte, dieselbe API, Werkzeug-Vertrag (`UIX_2_KONZEPT.md` §6).

### Empfehlung
**B als Grundform, mit dem Instrumentenstreifen aus A** oben (sieben Anzeigen statt Chips) und der Aufgabenliste aus A als
ausklappbarer Baumabschnitt. So bleibt die Konzentration auf ein Werkstück, ohne dass die Stärken aus dem Blick geraten.

## 3. Fragen an den Captain (vor jedem Code)

1. Richtung: A, B oder B+A-Streifen?
2. Gespräch rechts (B) oder unten (A)?
3. Welche Vertrauensstufe ist der Standard für ein neues Projekt: „Sandbox frei · Übernahme fragt“?
4. Soll der Retro-Desktop als Erscheinungsbild weiterleben (Himmel, Hügel, Fenster) oder wird er zur Erinnerung im Logbuch?
