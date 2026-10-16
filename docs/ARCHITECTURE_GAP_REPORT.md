# ARCHITECTURE_GAP_REPORT – Herdr-/Harness-Integration

> **Wichtig (nach Sichtung von `herdr-master`):** Das Handoff nennt das Projekt „Herder" und schreibt ihm Job-Queue, Heartbeat/Lease und Cooldown zu. Der Quellcode zeigt einen Terminal-Multiplexer ohne diese Funktionen. Siehe §5.0.

Stand: 2026-10-01 · Basis: GUPPI v1.20 (Self-Development Foundation)
Methode: statische Code-Durchsicht der Module unter `runtime/src/guppi_runtime/`. **Es wurde nichts ausgeführt, nichts geändert und kein Test gelaufen.** Aussagen über Verhalten sind aus dem Quelltext abgeleitet.

Gelesen: `self_development.py`, `development_contracts.py`, `development_evidence.py`, `context_budget.py`, `kev.py`, `audit.py`, `guard.py`, `step_journal.py`, `artifacts.py`, `knowledge.py`, `registry.py`, `message_bus.py`, `evolution.py`, `runtime.py`, `feasibility.py`, `hardware_pass.py`, `modules/control.py`, `models/router.py`, `models/runtime_control.py`, `config/self_development.yaml`, Signaturen von `hardware_manager/manager.py` und `uix_server.py`, Guard-Aktionsliste.
Nicht im Detail gelesen: `capability_router.py`, `sandbox/*`, `candidate_*`, `tuning.py`, `benchmark.py`, `brain.py` (nur Ausschnitte). Das ist bei den Verweisen unten vermerkt.

## 1. Kurzfazit

1. v1.20 deckt die **Verträge** ab (Admission, Contracts, Manifest, Budget-Rechner, Evidence-Kette), aber **nicht die Ausführung**. Es gibt keine Queue, keinen Worker, keinen Lease-Ablauf, keinen Cooldown, kein Rollenrouting und keine Tokenzählung.
2. Es gibt **zwei** bestehende Zustandsmaschinen mit Retry-Logik, `DevelopmentJobStore` und `step_journal`. Eine dritte, generische Supervisor-Zustandsmaschine darf daneben nicht entstehen. Sie muss die beiden einbinden.
3. Mehrere Bausteine sind **vorhanden, aber nicht verdrahtet**: Der Context-Budget-Manager bekommt sein Kontextfenster von außen (Default 8192). Der Hardware-Model-Pass kennt die sicheren Kontextgrenzen, wird aber nicht abgefragt.
4. Zwei Infrastruktur-Eigenschaften blockieren Parallelität: `AuditLog.append` liest bei jedem Aufruf die **ganze Datei** und vergibt IDs ohne Sperre. Der `DevelopmentJobStore` hat keine Sperre.

## 2. Bestand gegen Handoff-Anforderung

Legende: ✅ vorhanden und nutzbar · 🟡 teilweise / nicht verdrahtet · ❌ fehlt

### 2.1 Job Supervisor

| Anforderung (Handoff §3–7) | Status | Befund |
|---|---|---|
| Persistente Job-Datei, eindeutige ID | ✅ | `DevelopmentJobStore` (`SDJ-…`, atomares JSON) |
| Zustandsübergänge validiert + auditiert | ✅ | `DevelopmentJobStore.ALLOWED`, `transition()` schreibt `SELF_DEVELOPMENT_STATE_CHANGED` |
| Zustände des Handoffs (CREATED…COMPLETED, RETRY_PENDING, DEAD, ESCALATED_*) | 🟡 | Bestand hat 12 **dev-spezifische** Zustände (BUILDING, TESTING, REWORK, READY_FOR_ACCEPTANCE …). Es fehlen CLAIMED, QUEUED, WAITING_APPROVAL, RETRY_PENDING, DEAD, CANCELLED, ESCALATED_*. Die Zustände sind nicht deckungsgleich. |
| Parent-/Child-Jobs | 🟡 | Feld `parent_job_id` existiert, wird beim Anlegen nie gesetzt (`start()` ruft `create` ohne Parent). Kein Dependency Graph. |
| Heartbeat / Lease | 🟡 | `heartbeat()` setzt nur Felder `last_heartbeat` und `lease{worker_id, lease_until, marker}`. **Nichts prüft den Ablauf.** `lease_until` wird nicht validiert, Format offen. |
| Heartbeat ≠ Progress | 🟡 | Felder getrennt. `last_progress` wird nur bei `transition()` gesetzt. Es gibt keinen Step-Hash und keine Stagnationserkennung. `marker` steckt im Lease und wird nie verglichen. |
| Stuck-/Dead-Erkennung, Grace, Suspect | ❌ | |
| Retry mit Limit und Grund | 🟡 | `attempts` wird nur gezählt. Es gibt kein Limit und keinen Retry-Grund. In `step_journal.start()` gibt es **hartes Limit 3** pro Step und die Regel „RUNNING beim Wiederaufnehmen = `UNKNOWN_EXECUTION_OUTCOME`, nie automatisch wiederholen". Das ist gutes Verhalten und muss erhalten bleiben. |
| Fehlerklassifikation (12 Klassen) | 🟡 | `SelfDevelopmentManager.classify_failure()` ist reines Substring-Matching, siehe Befund F-1. Es wird nirgends zur Steuerung verwendet. |
| Cancel | ❌ | |
| Crash-Recovery / Wiederaufnahme | 🟡 | Persistenz ✅. Recovery-Logik nur im Mission-Pfad (`brain.recover`, `step_journal`), nicht für Dev-Jobs. |
| Timeout | ❌ | |
| Concurrency-Gruppen | ❌ | |
| Approval Gates | 🟡 | Guard-Gates + Tokens ✅ (`CAPTAIN_REQUIRED`, einmalig, request-digest-gebunden, scope-geprüft). Kein Job-Zustand WAITING_APPROVAL. |
| Audit der Übergänge | ✅ | Hash-Kette in `audit.py` |
| Context-/Token-Budget je Job | 🟡 | Siehe 2.4 |

### 2.2 Role → Capability → Provider

| Anforderung | Status | Befund |
|---|---|---|
| Rollenliste | 🟡 | `assign_roles()` kennt 8 Rollen (planner, coder, tester, reviewer, verifier, documentation, security_reviewer, context_curator). Handoff nennt 11: es fehlen `researcher`, `tool_operator`, `hardware_engineer`. Die Rollen werden nur im Job **gespeichert**, nichts löst sie auf. |
| Role → Capability-Auflösung | ❌ | Der `CapabilityRouter` löst *Intent → Capability → Modul/Skill/Tool* auf, **nicht** Rollen. Ob er erweiterbar ist, ist nicht geprüft (`capability_router.py` nicht im Detail gelesen). |
| Control Master wählt Provider | 🟡 | `ControlMasterModule._model_inference` ruft `ModelRouter.chat(provider=…, model=…)`. Provider und Modell kommen **aus dem Request**, der Router nimmt sonst den **ersten gesunden Adapter**. Es gibt keine Anforderungs-basierte Auswahl. |
| Registrierte Provider | 🟡 | Nur `lm-studio` und `llama-cpp-server` (beide loopback). Kein Cloud-Adapter. `feasibility` meldet `CLOUD_NOT_IMPLEMENTED`. Kev liegt als eigener Provider daneben (`kev.py`) und nicht im `ModelRouter`. |
| Provider Health HEALTHY/DEGRADED/COOLDOWN/UNAVAILABLE | ❌ | `adapter.health()` ist ein bool und wird bei jedem `choose()` neu abgefragt. Kein Gedächtnis, kein Cooldown. |
| Fallback | 🟡 | Impliziter Fallback in `choose()`, wenn **kein** Provider angegeben ist (nächster gesunder). Das ist **nicht policy-gesteuert**. Cloud-Fallback existiert nicht. Handoff-Regel „Fallback darf Policies nie umgehen" ist für Cloud heute durch Abwesenheit erfüllt, nicht durch Prüfung. |
| Deklarative Capability-/Agent-Rezepte | 🟡 | Registry lädt Module/Services/Skills/Tools aus YAML (inkl. `capabilities`-Listen). Es fehlen `roles`, `requirements`, `permissions.max_level`, `context`, `tests`, `rollback`, `metadata.trust_level` im Schema. Das Feld `capabilities` ist eine einfache Stringliste. |
| Herkunftsstufen BUILT_IN/KNOWN_GOOD/CAPTAIN_CUSTOM/GUPPI_GENERATED/EXTERNAL_UNVERIFIED | 🟡 | Teilweise: Learning Store kennt `GUPPI_GENERATED` → `KNOWN_GOOD` nur per Captain. Modellprofile haben eigenen Known-Good-Store. Es gibt keine einheitliche `trust_level`-Quelle. |

### 2.3 Hardware-aware Scheduling

| Anforderung | Status | Befund |
|---|---|---|
| Hardware-Inventar, Last, Temperatur | ✅ | `HardwareManager` (`preflight`, `get_state`, `_thermal_state`, `active_profile()['max_jobs']`) |
| Job-Zähler als Parallelitätsgrenze | ✅ | `HardwareManager.job()` + `feasibility.assess` liefert `NOT_NOW/JOB_LIMIT`. Bei thermischem Zustand `WARM` wird auf 1 Job begrenzt. |
| Modell-/Kontext-Fit | ✅ | `HardwareModelPass.evaluate` (RAM-Fit, Pair-Fit, Execution Mode, Kontext-Caps nach Hardwareklasse) |
| Ressourcen-Reservierung (VRAM/KV-Cache) | ❌ | `feasibility` sagt ausdrücklich `reservation=False`. KV-Cache wird laut Kommentar im Pass **absichtlich nicht modelliert**. Das Handoff-Beispiel (8,5 GB aktiv + 6 GB neu − 2 GB Reserve) ist damit nicht berechenbar. |
| Job-Ressourcenanforderung deklarieren | 🟡 | `execution_requirements` kennt nur `allowed_execution_locations`, `data_class`, `context_min_tokens`. Letzteres liefert **immer** `UNSUPPORTED/CONTEXT_CAPACITY_UNQUALIFIED`. Der Context Manager muss das auflösen. |
| Aktuelle VRAM-Belegung | 🟡 | Ob der Collector VRAM-Nutzung liefert, ist nicht geprüft (`collector.py` nicht gelesen). |

### 2.4 Context / Token

| Anforderung (Handoff §9) | Status | Befund |
|---|---|---|
| Budget je Modell | 🟡 | `ContextBudgetManager.build_budget(window)` ✅ mit Reserven und Subbudgets. Das Fenster kommt vom Aufrufer (`start(context_window=8192)`), **nicht** aus `HardwareModelPass.effective_profile.context.maximum` oder dem Control Master. |
| Watermarks GREEN/YELLOW/ORANGE/RED, konfigurierbar | ✅ | `health()` liefert Zustand + Aktionsnamen. Die Aktionen sind **nur Strings**, nichts führt sie aus. |
| Token zählen | ❌ | Es gibt keine Tokenzählung oder -schätzung. `health(used_tokens, …)` bekommt den Wert von außen, und niemand liefert ihn. |
| Context Manifest | ✅/🟡 | Contract ✅ (hash-gebunden). Es wird im Job gespeichert, **aber nicht an einen Child-Job oder Worker übergeben**. `required_files`, `exact_symbols`, `artifact_refs` bleiben leer. `checkpoint_id` wird nie gesetzt. |
| Tool Output Offloading | ❌ | `ArtifactStore` existiert (ART-ID, sha256, Provenienz), ist aber **mission- und dateigebunden** und `register()` verlangt einen Pfad. Es gibt keine Kurzfassung-plus-Referenz-Logik und kein Teilbereich-Nachladen. |
| Prompt-Eingaben begrenzen | 🟡 | Einziges Limit gefunden: `code_generation.generate` bricht bei >64 KiB Quelltext ab (`model_source_context_limit`), setzt `max_tokens=4096` und kürzt nicht. |
| Checkpoints | 🟡 | `SelfDevelopmentManager.checkpoint()` speichert 4000 Zeichen Freitext + Schritte. **Keine strukturierten Pflichtfelder** (Tests, Entscheidungen, Permission State, IDs). Daneben existiert der Ausführungs-Checkpoint `step_journal.checkpoint()` mit anderer Aufgabe. Namen sind verwechselbar. |
| Fresh Context / Task Boundary | ❌ | |
| Critical Facts strukturiert | ✅ | Contract-/Verification-Digests, Evidence-Kette (`trust_level` je Beleg), Audit-Kette. Es fehlt eine **Pin-Liste**, die garantiert, dass diese Fakten in jeden Fresh Context gelangen. |
| Relevance-Selektion | ❌ | |
| Context Health (Metriken) | 🟡 | Nur `fill_ratio`. Keine Duplikat-/Tool-Output-Anteile. |
| Context Repair | ❌ | |
| Token-/Kontext-Metriken | ❌ | Der `ModelRouter` schreibt Audit `TOOL_CALLED` mit Provider und Modell, **ohne Usage-Zahlen**. Ob die Adapter `usage` aus der Antwort durchreichen, ist nicht geprüft (`openai_local.py` nicht gelesen). |
| Projekt-/Gedächtnis-Schicht | ✅ | `KnowledgeStore` (JSONL, Textsuche). Es ist die **einzige** Memory-Schicht und bleibt es. Keine Relevanzsuche, nur Substring. |

### 2.5 Permissions / Gates

| Anforderung | Status | Befund |
|---|---|---|
| Level 0–6 | 🟡 | `development_contract.permission_level` (int 0–6) wird nur **validiert und gespeichert** (E1→2, sonst 3). **Nichts setzt es durch.** |
| Durchsetzung | ✅ (anders) | Durchgesetzt wird über den **Guard** auf Aktionsebene (`read_project_file`, `shell_execute`, `sandbox_execute`, `candidate_accept`, `model_runtime_control` …) mit Entscheidung ALLOW/BLOCK/CAPTAIN_REQUIRED. Unbekannte Aktion → `CAPTAIN_REQUIRED`. Tokens sind einmalig, an Mission, Aktion, Ziel und Request-Digest gebunden. |
| Fallback umgeht Rechte nicht | ✅ | Weil es keinen Fallback gibt. Muss beim Bau des Routings getestet werden. |

Konsequenz: Level 0–6 dürfen **keine zweite Rechteschicht** werden. Sie werden als **Abbildung Level → erlaubte Guard-Aktionen** definiert. Der Guard bleibt Entscheider.

### 2.6 Entwicklungsumgebung / Verifikation / Selbstentwicklung

| Punkt | Status | Befund |
|---|---|---|
| Entwicklungsumgebung (Sandbox) | ✅ | `SandboxBroker`, `candidate_*`. `prepare_development_environment()` setzt nur READY/BLOCKED aus `execution_ready`. Die Bindung „Job darf nur dort schreiben" prüft **nichts**. |
| Unabhängiger Verifier | 🟡 | `attach_verification` lehnt ab, wenn `verifier == builder` (**Stringvergleich** der Rollennamen). Zwei Rollen, die dasselbe Modell nutzen, bestehen den Test. Siehe F-4. |
| Baseline-vs-Candidate | 🟡 | Comparator ✅. Der automatische Baseline-Lauf fehlt (Ticket P1-007 PARTIAL). |
| Activation Gate | ✅ | `activation_decision()`. Es **aktiviert nichts**, es liefert nur eine Entscheidung. Aktivierung läuft über das bestehende `candidate_acceptance`. |
| Handoff Evolution → Self-Dev | ✅ | `EvolutionManager.handoff_to_self_development()` |
| `CORE_TARGETS` doppelt | 🟡 | `evolution.classify()` und `self_development.CORE_TARGETS` enthalten **unterschiedliche** Mengen (`soul_enforcement`, `policy`, `control_core`, `evolution_manager` nur in der zweiten). Siehe F-5. |

## 3. Datenmodell (Handoff §14)

| Struktur | Existiert als | Entscheidung |
|---|---|---|
| Job | `DevelopmentJobStore`-Datensatz (Schema 1) | **Erweitern**, nicht ersetzen. `kind`-Feld und generische Zustände als Schicht obendrauf. |
| JobDependency | – | neu (nur `depends_on: [job_id]` im Job, kein eigener Store) |
| JobAttempt | Zähler `attempts`, `step_journal.steps[].attempt_id` | **Liste `attempt_log` im Job**, kompatibel zu `ATT-`-IDs des Journals |
| Worker | – | neu, klein (`worker_id` + Rolle + Provider) |
| WorkerLease | Feld `lease` im Job | wiederverwenden, Ablaufprüfung ergänzen |
| ProviderHealth | – | neu |
| Capability | Registry-YAML | Schema erweitern (optionale Felder, rückwärtskompatibel) |
| RoleBinding | – | neu (Konfiguration, kein Code) |
| ApprovalRequest | Guard-Gate `HG-…` + Token `APR-…` | **wiederverwenden** |
| AuditEvent | `audit.py` | **wiederverwenden**, aber siehe F-2 |
| ResourceSnapshot | `HardwareManager.preflight()/get_state()` | **wiederverwenden** |
| Artifact | `ArtifactStore` (`ART-…`) | **wiederverwenden**, kleine Erweiterung für Nicht-Mission-Artefakte |
| VerificationResult | `verification_contract` | **wiederverwenden** |
| ContextManifest | `context_manifest` | **wiederverwenden** |
| ContextCheckpoint | `SelfDevelopmentManager.checkpoint()` (Freitext) | **ersetzen durch strukturierte Variante**, alter Eintrag bleibt lesbar |
| ContextMetric | – | neu |

Neu: 5 Strukturen (JobDependency, Worker, ProviderHealth, RoleBinding, ContextMetric). Der Rest wird wiederverwendet oder erweitert.

## 4. Befunde im Bestand (vor dem Aufbau zu klären)

| ID | Prio | Befund | Auswirkung |
|---|---|---|---|
| F-1 | mittel | `classify_failure`: Substring-Reihenfolge. `"context window exceeded"` trifft zuerst `"context"` → `context_quality_degraded`, obwohl `context_overflow` gemeint ist. `"token limit"` ist nur über `token` erreichbar. `"latest"` oder `"attestation"` enthält `"test"` → `deterministic_test_failure`. `rate_limit` und `transient_provider_error` sind **nicht abbildbar**. | Falsche Retry-Entscheidung, sobald die Klasse steuert. Muss vor dem Retry-Bau durch eine strukturierte Fehlerklasse ersetzt werden (Exception-Typ / Reason-Code statt Freitext). |
| F-2 | **hoch** | `AuditLog.append` ruft `_last()` auf, das **die gesamte Datei zeilenweise parst**, pro Event. Die Event-ID ist `letzte ID + 1` **ohne Sperre**. Gleiches Muster in `DevelopmentEvidenceStore._last`. | Mit Heartbeats, mehreren Workern oder langen Läufen: Laufzeit wächst mit Logdatei (O(n) je Event). Zwei gleichzeitige Schreiber können dieselbe ID und kaputte Hash-Kette erzeugen (Folge: `observability` meldet `audit` unhealthy → `SAFE_MODE`). **Blocker für Parallelität.** |
| F-3 | hoch | `DevelopmentJobStore`: Lesen-Ändern-Schreiben ohne Sperre (`load` → ändern → `save`). `mission_lock.exclusive` (OS-Advisory-Lock) existiert und wird hier nicht verwendet. | Zwei Prozesse (Heartbeat + Statuswechsel) überschreiben sich gegenseitig. Verlorene Updates. |
| F-4 | mittel | Unabhängigkeit des Verifiers nur per Namensgleichheit. | Der Anspruch „unabhängiger Verifier" ist schwächer als dokumentiert. Zu verlangen ist Unabhängigkeit auf Ebene **Provider/Modell-ID**, aufgelöst vom Control Master. |
| F-5 | niedrig | Zwei abweichende Core-Listen (siehe 2.6). | Ein Ziel kann je nach Pfad E2 oder E3 sein. Zusammenführen in **eine** Quelle (Config), E3 als sichere Obermenge. |
| F-6 | mittel | `attach_verification` springt BUILDING→TESTING→VERIFYING automatisch, ohne dass Testergebnisse vorliegen müssen. | Ein Job kann ohne Testlauf `READY_FOR_ACCEPTANCE` erreichen, wenn jemand `PASS` meldet. `acceptance_criteria` werden nie gegen Evidence geprüft. |
| F-7 | niedrig | `start()` setzt `parent_job_id` im Manifest auf die **eigene** Job-ID statt auf einen Parent. | Semantik unklar. Beim Child-Job-Bau korrigieren. |
| F-8 | niedrig | `ModelRouter.choose()` ruft `health()` bei jedem Chat synchron auf (HTTP-Healthcheck, 1,5 s Timeout bei llama.cpp). | Zusatzlatenz pro Aufruf und Zustandsverlust, siehe ProviderHealth. |

F-2 und F-3 sind keine Fehler im aktuellen Einzelprozess-Betrieb, sondern Voraussetzungen, die vor einer Queue behoben sein müssen.

## 5. Herder-/Harness-Muster: passend oder nicht

### 5.0 Korrektur nach Sichtung des Quellcodes (herdr 0.9.3)

Das Projekt liegt unter `…\herdr-master\herdr-master` und heißt **herdr** (nicht „Herder"). Es wurde gelesen: `README.md`, `AGENTS.md`, `Cargo.toml`, `LICENSE`, `skills/herdr/SKILL.md`, `docs/next/…/agent-automation.mdx`, `session-state.mdx`, Verzeichnisstruktur `src/`, `src/detect/manifests/`, sowie Begriffssuchen über alle `src/**/*.rs`. Nicht gelesen: `pane.rs` (220 KB), `server/`, `api/`, `integration/`, `socket-api.mdx` im Detail.

**Was herdr ist:** ein Terminal-Multiplexer für Coding-Agents (Rust, ratatui, eigener PTY-/Server-Prozess, Ghostty-VT in `vendor`/`crates`). Er verwaltet Workspaces, Tabs und Panes, erkennt laufende Agents per Bildschirm-Detektion und erlaubt Steuerung per CLI und Socket-API. Lizenz **Apache-2.0**, Version 0.9.3 (vor 1.0).

**Was herdr nicht ist:** ein Job-Supervisor. Der Handoff (§2, §20) schreibt ihm Eigenschaften zu, die im Quellcode **nicht vorhanden** sind:

| Handoff-Annahme | Befund in herdr |
|---|---|
| persistente Job Queue | Keine. Gespeichert wird nur das **Layout** (`session.json`, Snapshots). Ein Neustart stellt Layout wieder her, **Prozesse überleben nicht** (`session-state.mdx`). |
| Heartbeat | 0 Treffer im gesamten `src/`. |
| Lease für Worker | `lease` kommt nur als SSH-Agent-/Client-Verbindungs-Lease und in der Windows-Aktivierung vor. Es ist keine Arbeits-Lease. |
| Provider Cooldown / Backoff | 0 Treffer. |
| Retry/Fallback zwischen Providern | `retry` nur bei Update-Download, Handoff und API-Wiederholung. Kein Provider-Fallback. |
| Token-/Kostenmetriken | Keine Zählung von Input/Output-Tokens. |
| Kontextfenster-/Task-Grenzen | 0 Treffer für Kontextfenster. Herdr sieht den Agent-Inhalt nur als Terminalbild. |
| Concurrency-/Hardware-Regeln | Keine. Anzahl der Panes ist nicht ressourcengesteuert. |
| Berechtigungsmodi | `permission` bezieht sich auf Dateirechte und Plattformrechte. Genehmigungen des Agents erkennt herdr nur (Zustand `blocked`), es entscheidet nicht. |

Die Handoff-Zusammenfassung (§20) beruht offenbar auf einer Diskussion, nicht auf dem Code. **Das Ergebnis dieses Abschnitts ersetzt die Annahmen im Handoff:** Die in §2 gelisteten Muster müssen GUPPI-nativ entworfen werden. Herdr liefert dafür kaum Vorlage, mit den folgenden Ausnahmen.

**Übertragbare Ideen aus herdr (aus Quellcode und Doku belegt):**

| Idee | Beleg | Nutzen für GUPPI |
|---|---|---|
| Fünf Zustände `working / blocked / idle / done / unknown`; **`unknown` beweist keine Fertigstellung** | `SKILL.md`, `agent-automation.mdx` | Passt zum Job-Zustand `INCONCLUSIVE` und zu `UNKNOWN_EXECUTION_OUTCOME` im `step_journal`. Bestätigt die Regel, dass unbekannt nie als Erfolg zählt. |
| `blocked` = Freigabe-/Rückfrage-UI erkannt; `agent prompt` an einen blockierten Agent wird **abgelehnt, ohne Eingabe zu senden** (`agent_blocked`) | `agent-automation.mdx` | Vorbild für den Zustand WAITING_APPROVAL: ein Supervisor darf einen wartenden Job nicht durch neue Eingabe „weiterschieben". |
| **Stall-Erkennung bei der Übergabe:** nach dem Senden wird bis zu 5 s auf `working` oder `blocked` gewartet, sonst Fehler `agent_prompt_stalled` | `agent-automation.mdx` | Ein konkretes, kleines Muster für Progress-vs-Heartbeat: „Übergabe angenommen" ist nicht „Arbeit begonnen". |
| `completion_seq` / `state_change_seq`: Abschluss als **Sequenznummer**, unabhängig davon, wer es angesehen hat | `agent-automation.mdx` | Monotone Zähler statt Zeitstempel für Fortschritts-/Abschlussereignisse. Robust gegen Uhrsprünge (vgl. Risikotabelle im Integrationsplan). |
| Evidenzbasierte Detektion: nur **unveränderliche sichtbare Elemente** als explizite UND/ODER-Regeln, nie zufälliger Text; Detektion liest einen Screen-Snapshot, nicht den Viewport | `AGENTS.md` | Prinzip für Fehlerklassifikation (F-1): strukturierte, belegte Regeln statt Substring-Raten. |
| Stabile, **nie wiederverwendete** IDs (`w1`, `w1:t1`, `w1:p1`); Alias folgt dem aktuellen Inhaber und wird beim Verlassen gelöscht | `SKILL.md` | Job-/Attempt-IDs nie wiederverwenden. Bestätigt das `ATT-`/`SDJ-`-Vorgehen. |
| Session-Recovery: bei unlesbarer `session.json` Originalbytes **vor** dem Überschreiben sichern, 3 Recovery-Kopien, bis zu 48 Layout-Snapshots, nie automatisch zurückspielen | `session-state.mdx` | Für Job-Store und Evidence-Datei: beschädigte Datei sichern statt überschreiben. Ergänzt F-2/F-3. |
| Ehrliche Tabelle „Was überlebt" (Detach/Server-Neustart/Update) | `session-state.mdx` | Vorlage für unsere Recovery-Dokumentation: was nach Absturz wiederkommt und was nicht. |
| Aktion bei Nichtklassifizierbarkeit: Pane/Name bleibt erhalten, Fehler wird angezeigt, nichts verschwindet stillschweigend | `session-state.mdx` | Passt zu BLOCKED statt stillem Verwerfen. |
| Kompatibilitätsdisziplin: benannte Codecs unveränderlich, neue Felder optional, unbekannte Enum-Werte → `Unknown`, fehlende optionale Fähigkeit deaktiviert nur die Aktion | `AGENTS.md` | Passt zu Schema-2-Plan (zusätzliche Felder, Schema 1 lesbar). Zusätzlich: Enum-Werte append-only, mit `UNKNOWN`-Fallback beim Lesen. |
| Trennung Runtime-Fakt vs. UI-Zustand („neutrale Namen, nicht UI-Begriffe") | `AGENTS.md` | Bestätigt: Supervisor-Zustand gehört in die Runtime, nicht in die UIX. |
| „Multiplikative Pfade": Arbeit je Event × Panes × Clients vor dem Einbau bewerten | `AGENTS.md` | Genau die Denkweise, die F-2 (Audit pro Event O(n)) verlangt. |

**Fremdcode-Einbindung (Handoff §2: Lizenz, Reife, Kopplung, Wartung, Sicherheit, interne Alternative):**

| Kriterium | Bewertung |
|---|---|
| Lizenz | Apache-2.0. Weitergabe/Einbindung erlaubt, mit Lizenztext und Hinweis. Kompatibel. |
| Sprache/Technik | **Rust** (+ Zig für Ghostty). GUPPI ist Python und soll portabel ohne zusätzliche Installation laufen (Auftrag v1.19). Eine Einbindung würde einen Rust-Build oder eine Binärdatei erzwingen. |
| Reife | Version 0.9.3, Windows nur „beta" (`windows-beta.mdx`), schneller Release-Takt (CHANGELOG 142 KB). |
| Kopplung | Hoch: Schnittstelle ist ein eigener Server/Socket und Terminalbild-Erkennung von Agent-UIs. Das widerspricht dem Prinzip, dass der Control Master Runtimes direkt anbindet. |
| Fit | Gering: herdr löst „mehrere interaktive CLI-Agents sichtbar halten". GUPPI braucht Job-Zustand, Lease, Retry, Budget. Das Problem ist ein anderes. |
| Sicherheit | Zusatz-Prozess mit Socket-API und Schreibzugriff auf Terminals fremder Agents. Müsste in Guard/Policy eingebunden werden. Eine echte Sicherheitsprüfung wurde **nicht** durchgeführt. |
| Wartung | Upstream-Updates mit Kompatibilitätsbrüchen vor 1.0 zu erwarten. |

**Empfehlung:** Herdr **nicht** einbinden. Nur die Ideen oben übernehmen. Einziger sinnvoller späterer Einsatz wäre ein **optionaler externer Visualisierer** für CLI-Agents (z. B. falls GUPPI später CLI-Agents wie Claude Code/Codex als Worker startet). Dann als Provider-Typ hinter dem Control Master mit eigener Guard-Aktion und eigener Prüfung, nicht als Kern.

### 5.1 Bewertung der Muster aus dem Handoff

Die Zeilen bewerten die Muster als **Ideen**. Dort, wo Herdr keine Vorlage liefert, ist das vermerkt.

| Muster | Urteil | Begründung / GUPPI-nativ |
|---|---|---|
| Persistente Job Queue | **übernehmen** | Dateibasiert, wie der bestehende Job-Store. Keine DB-Abhängigkeit. |
| Heartbeat/Lease/Stuck | **übernehmen** | Felder vorhanden, Reaper fehlt. |
| Rollenbasierte Ausführung | **übernehmen** | als Konfiguration `role → capability → Anforderungen`. Auflösung beim Control Master. |
| Retry + Fehlerklassen | **übernehmen** | auf Basis strukturierter Reason-Codes (F-1). Das Journal-Verhalten „unbekannter Ausgang wird nie automatisch wiederholt" bleibt Vorrang. |
| Provider Cooldown | **übernehmen** | im Control-Master-Umfeld, nicht im Supervisor. |
| Concurrency-Regeln | **übernehmen, klein** | zuerst Slots + Hardware-`max_jobs`, Reservierung erst später. |
| Berechtigungsmodi, Approve/Reject | **übernehmen als Abbildung** | auf Guard-Aktionen, keine zweite Rechteschicht. |
| Deklarative Agentenprofile | **übernehmen** | Erweiterung des Registry-Schemas, optionale Felder. |
| Strukturierte Logs, Token-/Kostenmetriken | **übernehmen** | `ContextMetric`, getrennt vom hash-verketteten Audit (Heartbeats nicht ins Audit). |
| Context-Grenzen, Tool-Output sparsam | **übernehmen** | Context Manager. |
| Herder als Orchestrator über GUPPI | **nicht** | Handoff §2. |
| Cloud-/CLI-Agent-Anbindung | **zurückstellen** | Es gibt keinen Adapter, `CLOUD_NOT_IMPLEMENTED`. Erst entwerfen, wenn Routing und Policies stehen. |
| Fremdcode-Einbindung von herdr | **nicht empfohlen** | Siehe 5.0: Rust statt Python, Version 0.9.3, Windows nur Beta, hohe Kopplung, anderes Problem. Lizenz (Apache-2.0) wäre unkritisch. Eine Sicherheitsprüfung wurde nicht durchgeführt, ist aber nur nötig, falls die Einbindung doch gewünscht wird. |
| Quelle der Muster | **Hinweis** | Die Muster „Queue, Lease, Heartbeat, Cooldown, Token-Metriken" stammen **nicht** aus herdr (5.0). Sie sind eigene Entwürfe nach gängiger Praxis. Wo möglich, sind sie hier gegen die Bestandsmechanik (`step_journal`, Guard, Audit) abgesichert statt gegen ein Vorbild. |

## 6. Überschneidungen, die vermieden werden müssen

1. **Dritte Zustandsmaschine** neben `DevelopmentJobStore` und `step_journal`.
2. **Zweites Audit-/Metrik-Format** neben `audit.py` und der Evidence-Kette.
3. **Zweite Rechteschicht** neben dem Guard.
4. **Zweite Provider-Wahl** neben `ModelRouter` und Control Master.
5. **Zweite Memory-Schicht** neben `KnowledgeStore`.
6. **Zwei „Checkpoint"-Begriffe**: Ausführungs-Checkpoint (`step_journal`) und Kontext-Checkpoint. Im Code und in der UI klar benennen (`context_checkpoint`).
7. **Zwei Budget-Rechner**: `ContextBudgetManager` bleibt die einzige Stelle für Budgets.

## 7. Offene Prüfpunkte (nicht im Code verifiziert)

- Liefern `LMStudioAdapter`/`LlamaCppServerAdapter` Usage-Zahlen? (`models/openai_local.py`)
- Liefert `hardware_manager/collector.py` aktuelle VRAM-Belegung und Temperatur je GPU?
- Kann `capability_router.py` eine Rollen-Ebene aufnehmen, oder braucht es ein eigenes Modul?
- Wie lang sind reale Audit-Dateien nach einem Testlauf? (Zur Quantifizierung von F-2 messen, nicht schätzen.)
- Sind alle 19 Testdateien auf dem Zielsystem lauffähig? Der Testreport nennt einen Lauf, der in ein Zeitlimit lief.
- Ob `lease_until` ein Zeitstempel (ISO) oder eine Dauer sein soll, ist im Bestand nicht festgelegt.
