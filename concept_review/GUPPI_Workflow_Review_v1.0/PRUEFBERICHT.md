# Konzeptprüfung: Workflow-Integration gegen GUPPI v1.13

Stand: 30.09.2026. Entscheidung: mit Korrekturen praktikabel; keine unveränderte Gesamtübernahme. Dies ist ein Prüf- und Planungspaket, keine Runtime-Version und keine Integrationsfreigabe.

Geprüft wurden alle drei TXT-Dateien aus dem gelieferten Handoff v1.0 und die lokale Implementierung von GUPPI v1.13. Die ursprünglichen KITEKO-Unterlagen waren nicht beigefügt; ihre Aussagen werden hier nicht unabhängig bewertet. Grundlage ist der tatsächliche Code, nicht allein die Architektur-YAMLs.

## Ergebnis des direkten Abgleichs

| Vorschlag | Tatsächlicher Stand v1.13 | Empfehlung |
| --- | --- | --- |
| Kein neuer Workflow Supervisor / Router | Brain, PlanningContext, CapabilityRouter und Control Master sind vorhanden | Übernehmen; keine zusätzliche Pflichtschicht |
| Missionsidentität | `M-XXXXXXXX`, Nachrichten, Artefakte und Audit nutzen Missions-ID | IDs behalten; Jahresnummer nur als optionale Anzeige |
| Mission Lifecycle | NEW, UNDERSTAND, PLAN, READY, EXECUTE, VERIFY, REWORK, PAUSED, CAPTAIN_REVIEW, CANDIDATE_REVIEW, COMPLETE, FAILED | Ergänzen statt umbenennen; Phase und Wartegrund trennen |
| Task Manager mit Parent/Child | Plan-Schritte und Tool-Sequenzen vorhanden; kein persistenter Task-Scheduler mit Dependency-Auswertung | Klein anfangen: erst sichere Schrittfortsetzung, dann Task-Hierarchie |
| Execution Requirements | `required_capabilities`, `runtime_requirements`, `model_policy`, Risiko, Tool-Allowlist und Lücken vorhanden | Typisierte Ausführungsanforderungen und zentrale Machbarkeitsantwort fehlen |
| Themen selbst ergänzen | Begrenzte persistente Drafts, Beispiele, Wiederverwendung; keine neuen Rechte oder ausführbaren Skills | Beibehalten; bestätigte Fälle und Promotion ergänzen |
| Hardware im Control Master | Hardware Manager ist Runtime-Dienst; Modellaufrufe nutzen Admission-Kontrolle | Fachliche Grenze übernehmen; nicht als neue zentrale Hardwareimplementierung beginnen |
| Ressourcen reservieren | RAM-Untergrenze und Job-Zähler pro Runtime-Instanz; keine globale VRAM/RAM-Reservierung | Beobachtete Kapazität, Schätzung und echte Reservierung unterscheiden |
| Gates / Policy | Guard, persistente Einmal-Tokens; Sandbox- und Hardwarepläne nutzen Digests | Allgemeine Inhalts-/Versionsbindung zuerst vervollständigen |
| Cloud optional | Lokale Modelladapter erzwingen Loopback; kein integrierter Cloud-Ausführungspfad | Cloud vorerst explizit UNSUPPORTED; Datengrenzen vor Provideraktivierung implementieren |
| Verifier / Evidence | Eigenständige Prüfung von Inspektion und Kandidaten; Legacy-Pfad prüft Artefaktvorhandensein | Nachweise nach Ergebnisart qualifizieren; Textartefakt ist keine erfüllte Fachaufgabe |
| Self-Development | Gelieferte Ersatztexte → isolierter Kandidat → Diff/Syntax/Hashes → CANDIDATE_REVIEW | Automatische Codegenerierung, echte Tests und ACCEPT bleiben offen |
| Hardwaresteuerung | Telemetrie, Profile, Admission; optionale Power-Plan-Funktion; keine qualifizierten Lüfter-/Firmware-Schreibadapter | Bestehende begrenzte Schreibfunktionen separat dokumentieren; PC-Abnahme weiter offen |

## Korrekturen am Konzept

1. **Keine zweite Zustandsmaschine einführen.** Mission-Phase beschreibt den Arbeitsabschnitt. Ergänzende Felder beschreiben Laufstatus, Wartegrund und Ergebnisqualität. WAITING_RESOURCE und WAITING_TOOL sind Gründe für eine Pause, VERIFYING entspricht VERIFY, NEEDS_CAPTAIN entspricht CAPTAIN_REVIEW. BLOCKED bedeutet eine anhaltende Sperre; RETRY ist ein kontrollierter Versuch, kein unbeschränkter Dauerzustand. CANCELLED braucht einen Abbruch- und Cleanup-Vertrag und kann danach ergänzt werden. CANDIDATE_REVIEW darf nicht mit einer Ausführungsfreigabe gleichgesetzt werden.

2. **Erst Ausführungsschritte belastbar machen.** `Brain.step(EXECUTE)` führt aktuell nur `plan.steps[0]` aus. `execution.current_step` existiert, wird dort aber noch nicht für eine vollständige Planfortsetzung genutzt. `tool_sequence` besitzt einen begrenzten Resume-Ansatz mit Schritt-Tokens; ein allgemeiner persistenter Scheduler fehlt. Parent/Child-Felder allein würden diese Lücke verdecken. Zuerst Cursor, Versuch-ID, gespeichertes Ergebnis und Wiederanlaufregeln implementieren. Erst danach echte Tasks, Dependencies und Agentenbesitz ergänzen. CODE/TEST/VERIFY sind zunächst Schritte, nicht automatisch drei Agenten.

3. **Freigaben auf Inhalt und Bedingungen begrenzen.** Guard-Tokens binden heute Mission, Aktion und Ziel, allgemein aber keine Argument-/Inhaltsversion. Isolierte Reproduktion: Freigabe für Überschreiben einer temporären Datei angefordert, Token erstellt, Inhalt vor Ausführung geändert; Operation wurde dennoch abgeschlossen. Dieser Befund betrifft den allgemeinen Dateischreibpfad, nicht die bereits digestgebundene Sandbox. Neues Gate bindet Aktion, kanonisches Ziel, relevante Argumente/Inhalt, Planversion, Ausgangsversion sowie gegebenenfalls Empfänger. Zielzustand vor Ausführung erneut prüfen. Leerer Ziel-Scope darf keine unbeabsichtigte globale Freigabe ergeben. Tokenprüfung/-verbrauch muss bei konkurrierenden Ausführungen atomar werden.

4. **A0–A7 sind Klassifikation, keine Rangfolge und keine Freigabe.** Eine lokale Erstellung kann einen bestehenden Bestand überschreiben; eine Sandbox-Ausführung ist nicht allein wegen A3 automatisch zulässig. Bestehende Sandbox-Gates nicht abschwächen. Guard bleibt maßgeblich und wertet Aktion, Datenklasse, Ziel, konkrete Berechtigungen und Projektregel aus. Verifier-PASS ersetzt kein Schreibrecht. Policyänderungen und Änderungen an Sicherheitsgrenzen benötigen weiterhin ein eigenes Gate.

5. **Machbarkeit ist ein zeitgebundener Befund.** Control Master kann seine vorhandenen Dienste zu einer einheitlichen Antwort zusammenführen. Vier Fälle unterscheiden: EXECUTABLE, NOT_NOW, BLOCKED, UNSUPPORTED. Jeder Befund hat Reason-Code, Beobachtungszeitpunkt, Ablaufzeit, Requirement-Digest und Belegreferenzen. Vor Ausführung Ressourcen und Policy erneut prüfen. Eine Vorprüfung ist noch keine Reservierung. Bei tatsächlichen Reservierungen später Lease-ID, Ablauf und Freigabe vorsehen. Keine erfundenen Angaben wie „10,8 GB reserviert“, solange nur Telemetrie vorliegt.

6. **Alternativen dürfen Anforderungen nicht stillschweigend senken.** Kleineres Modell, weniger Kontext, CPU-Offload, anderer Knoten oder Cloud werden als Vorschläge zurückgegeben. Harte Bedingungen wie lokale Datenhaltung und Kontextminimum bleiben erhalten. Replan bindet alten Plan, neue Planversion, Ursache und unverändertes Ziel. Wiederholungen begrenzen und keine identischen Versuche ohne neue Information. `MissionStore.set_objective` versioniert das Ziel, erzwingt selbst aber keine Captain-Autorisierung; diese Regel braucht technische Durchsetzung.

7. **UNKNOWN ist keine freie Ressource.** Fehlende oder veraltete Sensor-/VRAM-Werte müssen in der Machbarkeitsantwort sichtbar bleiben. READ-/ANALYZE-Aufgaben dürfen nur dann weiterlaufen, wenn die fehlende Information für ihre Voraussetzungen unerheblich ist. `known_good` gilt für konkrete Hardware-, Modell-, Runtime- und Profilkombinationen mit passenden Nachweisen, nicht pauschal für eine GPU-Klasse. Das Beispiel `context_min: 24000` ist kein allgemeiner Standardwert.

8. **Draft dauerhaft speichern ist nicht Thema dauerhaft aktivieren.** v1.13 speichert Themenentwürfe bereits beim ersten Fund, erteilt damit aber keine Skills oder Rechte. Das erfüllt die gewünschte Sicherheit weitgehend. „Mehrere bestätigte Fälle“ braucht eine Definition: verschiedene Missions-IDs, verifizierte relevante Ergebnisse, Duplikatprüfung. Wiederholtes Routing desselben Textes zählt nicht mehrfach. Automatische Zusammenführung/Skillgenerierung erst später. Themenlücke und ausführungsblockierende Capability-Lücke getrennt auswerten.

9. **Nachweise qualifizieren.** PREPARED_NOT_TESTED bleibt von TESTED_PASS und ACCEPTED getrennt. Inspektions-Hashes belegen Dateiinventar, keine semantische Repositoryanalyse. Syntaxprüfung belegt weder Funktion noch Sandbox-Isolation. LLM-Text darf keine Performancequalifikation erzeugen. Ein Evidence-Record braucht Art, Produzent, Mission/Schritt/Versuch, Version/Digest, Ergebnis, Grenzen und Artefaktreferenzen. Ein nicht benötigter Test muss ausdrücklich als NOT_REQUIRED mit Regel begründet sein.

10. **Cloud und externe Wirkungen erst mit eigenem Vertrag.** Ausgehende Datenklasse kann nicht vom LLM oder Router allein freigegeben werden. Provider-/Empfänger-Allowlist, minimaler Payload, Digestbindung und Guard müssen vor dem Aufruf geprüft werden. Lokaler Fallback muss dieselben fachlichen Anforderungen erfüllen. Für externen Timeout zusätzlich UNKNOWN_REMOTE_OUTCOME vorsehen: Status-/Idempotenzprüfung oder Captain-Klärung; niemals blind erneut senden. Ein Flag `cloud_allowed: false` allein beweist keine durchgesetzte Grenze. Noch nicht implementierte externe Aktionen bleiben unsupported.

## Empfohlene Integration in kleinen Schritten

**P0 – Nachweis und Freigabe:** allgemein digestgebundene Gates, Ergebnisqualifikation und stabile Scope-Regeln. Anschließend Gate-Tamper- und Inhaltsänderungstests. Keine ACCEPT-/MERGE-Funktion vorher.

**P1 – Machbarkeit und Pause:** versionierter Requirement-/Response-Vertrag in bestehenden Router-/Control-Strukturen; strukturierte Wartegründe. Hardware-/Providerblockaden werden derzeit teilweise zu Exceptions und anschließend FAILED. Wartbare Ressourcenknappheit künftig als NOT_NOW/PAUSED abbilden, dauerhaft fehlende Capability als UNSUPPORTED/BLOCKED. Neuprüfung beim Resume.

**P2 – Schrittfortsetzung:** persistenter Cursor, Versuchbudget, Idempotenz und Wiederanlauf. Kein Replay bereits abgeschlossener Nebenwirkungen. Candidate-Staging benötigt konkrete Resume-/Cleanup-Regeln; v1.13 kann bei Abbruch Teilstände zurücklassen und bei erneutem Versuch einen neuen UUID-Pfad anlegen.

**P3 – echter Testpfad:** qualifiziertes/pinnbares Guest-Image, Offlinebereitstellung, Testparameter-Binder, reale Testergebnisse, unabhängige Prüfung; erst danach kontrollierter Accept-Handler. Vollständige Windows-/USB-/MicroVM-Qualifikation bleibt beim vereinbarten PC-Ready-Test. Handoff-Phase „Hardware neu integrieren“ entfällt zugunsten gezielter Adapter- und Qualifikationsarbeit am vorhandenen Manager.

**P4 – optionale Erweiterungen:** bestätigte Themen-Promotion; Parent/Child-Tasks erst bei konkretem Bedarf; Cloud-Adapter erst mit enforced Datengrenzen; echte Agentenplanung erst nach Scheduler-/Ressourcenvertrag. Kein zusätzlicher Supervisor.

Das nächste Entwicklungspaket sollte P0 und einen begrenzten P1-Vertrag abdecken. Eine gleichzeitige Integration aller Handoff-Punkte würde den Entwicklungszyklus unnötig vergrößern.

## Belegstellen im bestehenden Paket

Alle Pfade relativ zu `GUPPI_Runtime_v1.13/runtime/src/guppi_runtime/`:

- `mission.py`: IDs, ALLOWED, Missionsschema und `set_objective`.
- `brain.py`: Zustandsbehandlung, erstes Plan-Step, FAIL/REWORK, CANDIDATE_REVIEW.
- `modules/planning.py` und `capability_router.py`: Route, Requirements, Blueprint, Binder.
- `guard.py`, `tools/filesystem.py`: Gate-/Tokenbindung und Schreibprüfung.
- `sandbox/broker.py`: Digestbindung und Zielqualifikationsblocker.
- `hardware_manager/manager.py`, `models/router.py`: Admission, Job-Zähler, Fehlerpfad.
- `model_profiles.py`: hardwarebezogene bekannte Profile.
- `models/openai_local.py`: lokale Providergrenze.
- `topics.py`: beschränkte Drafts und Beispielsammlung.
- `code_candidate.py`, `candidate_verification.py`, `modules/verification.py`: getrennte Nachweisqualitäten und Legacy-Artefaktprüfung.

Testausführung und Grenzen sind in `VALIDATION.json` dokumentiert. Produktcode und ursprüngliches Konzeptpaket bleiben unverändert.
