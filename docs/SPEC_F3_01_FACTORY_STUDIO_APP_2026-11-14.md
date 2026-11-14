# Spec F3-01 – Factory Studio App in One Sedra

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-008), nachgeprüft: Anforderungs-IDs, Freigabegrenzen mit Gegenproben vorhanden, keine lokalen Pfade. Hinweis: Das Modul `modules/factory_studio` ist nur importierbar und auf `main`, die Oberfläche (XAML/WinUI) wurde nie geprüft; die Spec setzt voraus, dass die App im Rahmen von One Sedra (Manifest, Rahmen, `uix/tools/`) entsteht und nicht als eigene Anwendung. Abhängigkeit MOD-04 (UI-Entwurf) im Register ist noch `IN_DEVELOPMENT`. Status: Entwurf, noch nicht vom Captain freigegeben.

**Stand:** 2026-11-14  
**Register:** SEDRA-F3-01  
**Abhängig von:** F2-01 (Registry, auf main), MOD-04 (Modul `modules/factory_studio`, auf main, ohne Oberflächenprüfung)  
**Quellen:** `runtime/src/sedra_runtime/modules/factory_studio/`, `runtime/docs/ADAPTERS.md`, `docs/ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md` (App-Rahmen, Manifest), `docs/SPEC_APPS_v1_AM3_BERECHTIGUNG.md`, `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md` (Form der Spec)  
**Ziel:** Spec für die operative Fabrik-Oberfläche innerhalb One Sedra — **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Hinweis:** Diese Spec beschreibt eine App nach Manifest v1.1 (Roadmap §5) mit `kind: app`, `trust: PACKAGE`, `profile: [standard, kmu, stick]`. Sie läuft im App-Rahmen (Roadmap §4) innerhalb der Harness-Shell. Keine zweite Runtime, keine zweite Shell.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Zentrale operative Oberfläche für Factory-Operationen in One Sedra: Projekte anlegen/verwalten, Modul-Dependencies & Build-Order visualisieren, Benchmarks & Runs steuern, Factory Health & Gates überwachen, Captain-Entscheidungen (Approve/Reject) direkt in der UI treffen. |
| **Was sie NICHT ist** | Keine zweite Runtime, keine eigene Shell, kein separater Prozess, kein direkter Hardwarezugriff, keine automatische Außenwirkung (kein Deploy, kein Druck, kein Versand). Alle Schreiboperationen laufen über Captain-Gates (Freigabe). |
| **Einordnung** | App im Sinne der Roadmap (A3: Shell-Funktionen als Apps). Manifest v1.1. Läuft in der Harness-Shell (`shells: [harness]`), Profile: `standard`, `kmu`, `stick`. |

---

## 2. Anforderungen (mit IDs)

### 2.1 Projekt-Management (Project Browser)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F301-01 | Projekte anlegen: Name, Anzeigename, Beschreibung, Factory-Type-ID, Metadaten. Status: `created` → `building` → `ready` / `failed` / `archived`. | Unit-Test `ProjectBrowserTest.test_create_project` |
| F301-02 | Projekte listen, filtern (Status, Factory-Type), suchen (Name). | Unit-Test `ProjectBrowserTest.test_list_filter` |
| F301-03 | Projekt-Details laden: Module, letzter Build, Metriken. | Unit-Test `ProjectBrowserTest.test_load_details` |
| F301-04 | Projekt archivieren / löschen (nur wenn keine aktiven Builds). | Unit-Test `ProjectBrowserTest.test_archive_delete` |

### 2.2 Modul-Management & Dependency Graph

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F301-05 | Module zu Projekt hinzufügen: Name, Type-ID, Layer (domain/application/infrastructure/ai/app), Dependencies. Validierung: Factory-Type muss `ready`/`active` sein, keine Namenskollision. | Unit-Test `ModuleManagementTest.test_add_module` |
| F301-06 | Modul-Status: `planned` → `generating` → `generated` → `building` → `built` / `failed`. | Unit-Test `ModuleManagementTest.test_status_flow` |
| F301-07 | Dependency Graph (GraphView): Knoten (Projekt/Modul/Service), Kanten (`depends_on`, `builds`, `contains`). Layout: hierarchisch nach Layer + Dependencies. Export als JSON für Debug. | Unit-Test `GraphViewTest.test_graph_structure` |
| F301-08 | Zyklus-Erkennung bei `depends_on` → Fehler mit Pfad. | Unit-Test `GraphViewTest.test_cycle_detection` |

### 2.3 Execution View (Builds, Benchmarks, Runs)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F301-09 | Build starten (Project/Module/Service) via Factory Registry Port. Gate `build_factory` bei `kind: project`/`module` (Captain-Freigabe). | Integration-Test `ExecutionViewTest.test_build_with_gate` |
| F301-10 | Build-Status live: `pending` → `running` → `success`/`failed`/`cancelled`. Dauer, Artefakte, Fehlermeldung, Metriken anzeigen. | Unit-Test `ExecutionViewTest.test_build_status` |
| F301-11 | Benchmark konfigurieren & starten: Factory-Type, Variante, Parameter, Iterationen, Build-Type. Ergebnisse im Evidence Store speichern. | Unit-Test `ExecutionViewTest.test_benchmark_run` |
| F301-12 | Run-History aus Evidence Store laden (Filter: Type, Limit, Success). Details: Steps, Duration, Metrics, Logs. | Unit-Test `ExecutionViewTest.test_run_history` |

### 2.4 Status Dashboard (Factory Health, Gates, Captain-Entscheidungen)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F301-13 | Factory Health: Registry erreichbar, Evidence Store erreichbar, Gate-Client verbunden, offene Gates zählen. | Unit-Test `StatusDashboardTest.test_health` |
| F301-14 | Offene Gates listen (Typ: register, transition, build, benchmark). Details: Ziel, Antragsteller, Zeit, Metadaten. | Unit-Test `StatusDashboardTest.test_pending_gates` |
| F301-15 | Gate entscheiden: `approve` / `reject` mit Begründung. Audit-Eintrag `UIX_APP_RIGHTS_GRANTED` / `..._REVOKED` (AM3-27). | Integration-Test `GatePanelTest.test_approve_reject` |

### 2.5 Gate Panel (Approve/Reject direkt in UI)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F301-16 | Gate-Karte anzeigen: Typ, Ziel, Diff/Vorschau (bei Build: geplante Artefakte; bei Transition: Status-Wechsel; bei Register: Manifest). | Unit-Test `GatePanelTest.test_card_render` |
| F301-17 | Entscheidung nur durch Captain (Role `captain` oder Sitzungs-Erlaubnis per AM3-E2). Button `Genehmigen` / `Ablehnen` mit Begründungsfeld. | Unit-Test `GatePanelTest.test_captain_only` |
| F301-18 | Nach Entscheidung: Karte schließt, Status Dashboard aktualisiert, Event `harness.gate.decided` publizieren. | Integration-Test `GatePanelTest.test_event_publish` |

### 2.6 App-Rahmen & Manifest (Roadmap §4, §5)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F301-19 | Manifest `tool.yaml` mit v1.1-Feldern: `id: factory_studio`, `kind: app`, `trust: PACKAGE`, `gruppe: fabrik`, `zelle: {feld: factory_status, label: "Factory", ort: status}`, `shells: [harness]`, `profile: [standard, kmu, stick]`, `rechte: [factory_build, factory_benchmark, factory_gate, factory_registry_read]`, `woerter: [fabrik, factory, build, benchmark]`, `abhaengig_von: [factory_registry, evidence_store]`, `update: {weg: diff}`. | Schema-Test `ManifestTest.test_factory_studio` |
| F301-20 | App-Rahmen: Titel, App-Menü, Rechtsklick-Modul („Im Chat anpassen“), Zustand speichern/laden, Fehleranzeige, Verweis auf Berechtigungsseite (AM3-25). | Browser-Test `AppFrameTest.test_frame_elements` |
| F301-21 | Fremd-Kennzeichen (AM3-19): Da `trust: PACKAGE`, kein `SEDRA_BUILT` ohne Nachweis (AM3-29). Rand mit Kopfzeile „Factory Studio · fremde App · COMMUNITY“. | Browser-Test `AppFrameTest.test_fremd_kennzeichen` |
| F301-22 | Berechtigung (AM3): `rechte` im Manifest → Fähigkeiten ableiten. `factory_build` = Stufe B (Gate), `factory_benchmark` = Stufe B (Gate), `factory_gate` = Stufe C (nur Captain), `factory_registry_read` = Stufe A. Werkseinstellung: nur Stufe A gewährt (AM3-28). | Test `BerechtigungTest.test_factory_studio_rechte` |

---

## 3. Datenmodell

Basierend auf `domain/entities.py` und `domain/value_objects.py`:

| Entität | Felder (Kern) | Beziehungen |
|---|---|---|
| `FactoryProject` | id, name, display_name, description, factory_type_id, status (ProjectStatus), created_at, updated_at, metadata, modules[], last_build | 1:N Module, 1:1 last_build |
| `FactoryModule` | id, project_id, name, display_name, module_type_id, status (ModuleStatus), layer, created_at, updated_at, metadata, depends_on[] | N:1 Project, N:M depends_on (self) |
| `FactoryBuild` | id, project_id, module_id?, build_type, factory_type_id, status (BuildStatus), started_at, finished_at, duration_ms, success, artifacts[], error_message, metrics | N:1 Project, N:1 Module? |
| `FactoryBenchmark` | id, factory_type_id, variant, params, score, runs_count, aggregated_metrics, created_at, run_ids[] | — |
| `FactoryGate` | id, gate_type, target_id, status (pending/approved/rejected), requested_by, requested_at, decided_by?, decided_at?, decision_reason?, metadata | — |
| Value Objects | `ProjectId`, `ModuleId`, `FactoryTypeId`, `BuildId`, `BenchmarkConfig`, `GraphNode`, `GraphEdge`, `MetricPoint`, `ChartSeries` | — |

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für F3-01 |
|---|---|
| `runtime/src/sedra_runtime/modules/factory_studio/` | Bestandsmodul (Domain, Application, Infrastructure, App) — **nur lesen**, keine Änderung |
| `runtime/src/sedra_runtime/modules/factory_studio/app/desktop/` | ViewModels (MainVM, ProjectBrowserVM, GraphViewVM, ExecutionViewVM, StatusDashboardVM, GatePanelVM) & Views — **nur lesen** |
| `runtime/docs/ADAPTERS.md` | Adapter-Doku (Native, n8n, Hybrid) — Integration in Execution View |
| `docs/ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md` | App-Rahmen, Manifest v1.1, Profile |
| `docs/SPEC_APPS_v1_AM3_BERECHTIGUNG.md` | Berechtigungsmodell, Gates, Werkseinstellung |
| `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md` | Form-Vorlage für diese Spec |
| `runtime/src/sedra_runtime/uix/tools/` | Tool-Manifeste (Vergleich: Factory Studio als App eintragen) |
| `runtime/config/freigabe_katalog.beispiel.yaml` | Default-Regel für `factory_studio` Gates → `captain` |

**Keine neuen Code-Dateien in dieser Spec.** Implementierung erfolgt in separatem Auftrag (nach Captain-Freigabe).

---

## 5. Freigabegrenzen & Gegenproben

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| Kein direkter Build ohne Gate | Jeder Build (`project`/`module`/`service`) erfordert Captain-Freigabe (`build_factory` Gate). | Build-Request ohne Gate → 403 `gate_required` |
| Keine Außenwirkung | Kein Deploy, kein Druck, kein Versand, keine Maschine. Nur Artefakte im Evidence Store. | Versuch `factory_deploy` → 403 `verb_nicht_gewaehrt` (AM3-11) |
| Kein Captain-Ersatz | Model/Chat kann Rechte *beantragen* (AM3-10), aber nicht gewähren/aktivieren. | Chat ruft `grant_app_rights` → 403 `nicht_erlaubt` |
| Manifest-Hash bindet Gewährung | `manifest_sha256` in `berechtigung.yaml` muss Matchen (AM3-06). | Manifest geändert, alte Gewährung → `gewaehrung_veraltet` |
| Profil-Bindung | App nur in `standard`, `kmu`, `stick` sichtbar. Andere Profile → nicht geladen. | Profil `developer` → App nicht im Start-Menü |
| Zelle nur in Harness | `zelle` erscheint nur in Harness-Leiste (`leiste.json`), nicht in KMU/Stick ohne Captain-Eintrag. | KMU-Leiste ohne Eintrag → Zelle fehlt |

---

## 6. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Manifest `tool.yaml`** unter `runtime/src/sedra_runtime/uix/tools/factory_studio/` anlegen (v1.1, alle Felder).
2. **App-Einstieg** in `uix/tools/factory_studio/app.py` (lädt ViewModels, registriert bei Harness).
3. **ViewModels & Views** aus `modules/factory_studio/app/desktop/` in App-Rahmen einbinden (Roadmap §4).
4. **Ports implementieren**: `FactoryRegistryPort` → `factory_builder.py` / HTTP, `EvidenceStorePort` → `evidence_store.py` / HTTP, `GateClientPort` → `desk/gateway.py` / Harness-Gate.
5. **Berechtigung eintragen**: `factory_studio` in `freigabe_katalog.beispiel.yaml` → `captain` für `factory_build`, `factory_benchmark`, `factory_gate`.
5. **Tests schreiben** (siehe §2, Spalte „Prüfbar durch“).
6. **Abnahme**: Captain prüft Manifest-Hash, Gate-Flow, App-Rahmen, Fremd-Kennzeichen.

---

## 7. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| F301-Q1: Soll `factory_studio` `trust: SEDRA_BUILT` erhalten? | **Nein**, vorerst `COMMUNITY`. `SEDRA_BUILT` nur mit abgenommenem Kandidaten-Nachweis (AM3-29). Captain entscheidet bei Abnahme. | Sicherheit: Kein Vorgriff auf Abnahme. |
| F301-Q2: `zelle` in KMU/Stick Profil standardmäßig anzeigen? | **Nein**, nur in Harness (`leiste.json`). KMU/Stick per Captain-Eintrag. | KMU/Stick sind reduzierte Profile; Factory-Status ist Fachfunktion. |
| F301-Q3: `rechte` Granularität: ein Recht `factory_build` oder split `factory_build_project`, `factory_build_module`, `factory_build_service`? | **Split** in drei Rechte (Stufe B je). Feinere Kontrolle für Captain. | AM3-07: Jede Fähigkeit einzeln im Gate. |
| F301-Q4: GraphView Layout-Algorithmus (hierarchisch vs. Force-Directed)? | **Hierarchisch nach Layer + Dependencies**. Deterministisch, besser für Factory-Module. | Force-Directed ist unvorhersagbar; Factory hat feste Layer. |
| F301-Q5: Benchmark-Vergleich (Varianten) in Execution View oder eigene View? | **In Execution View** als Tab „Vergleich“. Nutzt `EvidenceStorePort.compare_variants`. | Weniger Views, konsistenter Ort für Runs. |

---

## 8. Anforderungs-IDs (Zusammenfassung)

F301-01 bis F301-22 (22 Anforderungen).  
Offene Fragen: F301-Q1 bis F301-Q5 (5 Fragen).

---

**Ende der Spec F3-01.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a008` unter `docs/SPEC_F3_01_FACTORY_STUDIO_APP_2026-11-14.md`.