# Spec F3-02 – 3D Factory Pilot

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-008), nachgeprüft: Anforderungs-IDs, harte Grenzen mit Gegenproben und Gate-Anforderungen sind vorhanden, keine lokalen Pfade. **Einschränkung zu F302-17:** Eine Sitzungs-Erlaubnis darf nur die **Freigabe der Artefakte** (Markierung `freigegeben`, Export in `freigegeben/`) für eine unveränderte, schon einmal freigegebene Konfiguration wiederholen. Für **Druck, Versand, Maschinenauftrag und Veröffentlichung** gilt immer das Gate `3d_artefakt_freigabe` mit Einmal-Freigabe des Captains; keine Sitzungs-Erlaubnis, keine Dauerregel. Das ist als eigene Anforderung mit Gegenprobe zu ergänzen (Sitzungs-Erlaubnis + Druckanfrage → 403 `gate_required`), bevor Code geschrieben wird. Status: Entwurf, noch nicht vom Captain freigegeben.

**Stand:** 2026-11-14  
**Register:** SEDRA-F3-02  
**Abhängig von:** F2-01 (Registry, auf main), F3-01 (Factory Studio App)  
**Quellen:** `SEDRA_3D_Assets_Sammlung_*` (nur lesen, liegt untracked im Hauptordner), `docs/` Suche „OpenSCAD“ (Kappe v27), `docs/AUFTRAG_PAPERCLIP_3D_PIPELINE_2026-10-16.md`, `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md` (Form der Spec)  
**Ziel:** Spec für isolierte 3D-Generierung (z. B. OpenSCAD oder Blender) mit Artefaktvalidierung — **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Harte Grenze (Captain-Beschluss 14.11.2026):** Reproduzierbarer Export mit Nachweis, **keine unfreigegebene Hardware- oder Außenaktion** (kein Druck, kein Versand, keine Maschine ohne Freigabe des Captains). Alles läuft als Artefakt im Evidence Store, Validierung vor Freigabe.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Isolierte Pipeline für 3D-Modell-Generierung: Aus Bedarf/OpenSCAD-Quelltext → validiertes Artefakt (STL/GLB/SCAD) → Captain-Freigabe → Ablage im Evidence Store. Keine zweite Runtime, läuft als Factory-Type in der Registry, UI über Factory Studio App (F3-01). |
| **Was sie NICHT ist** | Kein direkter 3D-Druck, kein Versand, keine Maschinenansteuerung, kein Cloud-Rendering ohne Gate, keine automatische Veröffentlichung. Kein interaktives 3D-Viewer-Frontend (das ist separate App). |
| **Einordnung** | Factory-Type `3d_factory` (oder `openscad_factory`, `blender_factory`) in Registry. Wird über Factory Studio (F3-01) gesteuert: Project → Module (3D-Objekte) → Build → Gate → Artefakt. |

---

## 2. Anforderungen (mit IDs)

### 2.1 3D-Quelltext-Generierung (Code → SCAD/Blender-Python)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F302-01 | Eingabe: Bedarfsdaten (CSV/JSON) oder Parameter-Satz → OpenSCAD-Quelltext (`.scad`) oder Blender-Python-Script (`.py`). Parameter oben als Variablen, Maße in mm, max 200 Zeilen je Datei (Paperclip-Regel). | Unit-Test `GeneratorTest.test_scad_structure` |
| F302-02 | Generator als Factory-Modul (Type `3d_generator`), registriert in Registry (F2-01). Funktionen: `generate`, `validate`, `render`, `export`. | Integration-Test `FactoryRegistryTest.test_3d_generator_type` |
| F302-03 | Template-Basiert: Basis-Templates für Kappe (v27), Würfel, Pyramide, Zahnrad, Becher, Vase, Schraube, Buchstütze, Turm. Templates in `factory_templates/3d/` versioniert. | Unit-Test `GeneratorTest.test_templates_exist` |
| F302-04 | Parameter-Validierung: Pflichtfelder (Maße, Wandstärke, Befestigung), Typ-Prüfung, Wertebereiche (min/max). Fehlende Maße → Standardwert + Annahme-Markierung (Paperclip §4). | Unit-Test `GeneratorTest.test_param_validation` |

### 2.2 Validierung & Prüfung (Syntax, Geometrie, Druckbarkeit)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F302-05 | **Syntax-Prüfung**: OpenSCAD `openscad -q --parse-only file.scad` (Exit-Code 0 = OK). Blender: `blender --background --python script.py -- --validate`. | Unit-Test `ValidatorTest.test_syntax_check` |
| F302-06 | **Geometrie-Prüfung**: Render zu STL → `openscad -o file.stl file.scad`. Prüfung: wasserdicht (manifold), keine degenerierten Dreiecke, Volumen > 0. Tool: `admesh` oder `trimesh`. | Unit-Test `ValidatorTest.test_geometry_watertight` |
| F302-07 | **Druckbarkeits-Prüfung**: Mindestwandstärke (config, Default 0.8 mm), keine Überhänge > 45° ohne Stütze, Bounding Box in Drucker-Bauraum (config). | Unit-Test `ValidatorTest.test_printability` |
| F302-08 | **Maßhaltigkeits-Prüfung**: Kritische Maße (Bohrungen, Passungen) gegen Sollwerte ± Toleranz (config, Default 0.2 mm). | Unit-Test `ValidatorTest.test_dimensional_accuracy` |
| F302-09 | Prüfbericht als strukturiertes Artefakt: `pruefung.json` mit `status: ok|warn|fail`, `findings[]` (je: `code`, `message`, `severity`, `location`), `metrics` (Volumen, Oberfläche, Bounding Box, Druckzeit-Schätzung). | Unit-Test `ValidatorTest.test_report_structure` |

### 2.3 Artefakt-Erzeugung & Export

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F302-10 | Export-Formate: STL (binär), GLB (für Web), SCAD (Quelltext), 3MF (optional). Ein Build produziert alle konfigurierten Formate. | Unit-Test `ExportTest.test_formats` |
| F302-11 | Artefakt-Namensschema: `<project>/<module>_<variant>_<hash>.<ext>`. Hash = SHA256 der Quelldatei (erste 12 Zeichen). | Unit-Test `ExportTest.test_naming` |
| F302-12 | Ablage im Evidence Store (F2-03): Run-Eintrag mit `artifacts[]` (Pfade), `metrics`, `pruefung_json`. `sedra factory evidence show <run_id>` liefert Download-Links. | Integration-Test `EvidenceStoreTest.test_3d_artifacts` |
| F302-13 | Reproduzierbarkeit: Gleicher Input (Parameter + Template-Version + Generator-Version) → identische Artefakt-Hashes. Test: 3 Wiederholungen → gleiche Hashes. | Unit-Test `ReproducibilityTest.test_deterministic` |

### 2.4 Captain-Gate & Freigabe (harte Grenze)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F302-14 | **Keine Außenwirkung ohne Gate**: Build-Status `success` → Artefakte im Evidence Store, **aber** Gate `3d_artefakt_freigabe` (Captain) erforderlich vor: Druck, Versand, Maschinenauftrag, Veröffentlichung. | Integration-Test `GateTest.test_no_external_without_gate` |
| F302-15 | Gate-Karte zeigt: Vorschau (GLB-Render als Base64-Data-URL oder Thumbnail-PNG), Prüfbericht (Zusammenfassung), Artefakt-Hashes, Risiken (Überhänge, Wandstärke, Toleranz). | Unit-Test `GateTest.test_card_content` |
| F302-16 | Captain-Entscheidung: `approve` → Artefakte als `freigegeben` markiert, Export in `freigegeben/` Ordner, Event `factory.3d.approved`. `reject` → Grund, Artefakte bleiben `pending`, Event `factory.3d.rejected`. | Integration-Test `GateTest.test_approve_reject` |
| F302-17 | **Sitzungs-Erlaubnis (AM3-E2)** für wiederkehrende Standard-Objekte (z. B. Kappe v27): Nach erstmaliger Captain-Freigabe kann gleiche Konfiguration per Sitzungs-Erlaubnis freigegeben werden (Hash-Vergleich). | Unit-Test `GateTest.test_session_permission` |

### 2.5 Integration in Factory Studio (F3-01)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F302-18 | Project Browser: Factory-Type `3d_factory` auswählbar. Module = 3D-Objekte (je Objekt ein Modul). | Integration-Test `FactoryStudioIntegrationTest.test_3d_type_visible` |
| F302-19 | GraphView: Dependencies zwischen Objekten (z. B. Kappe → Unterteil, Oberteil). Layer: `domain` (Geometrie), `application` (Parameter), `infrastructure` (Export). | Integration-Test `FactoryStudioIntegrationTest.test_3d_graph` |
| F302-20 | Execution View: Build startet Generator → Validator → Export. Status live. Benchmark: Varianten-Vergleich (Wandstärke, Füllung, Orientierung). | Integration-Test `FactoryStudioIntegrationTest.test_3d_build_flow` |
| F302-21 | Gate Panel: `3d_artefakt_freigabe` Gate erscheint, Karte mit 3D-Vorschau (Three.js/GLB-Viewer im Gate-Panel). | Browser-Test `GatePanelTest.test_3d_preview` |

### 2.6 Manifest & Berechtigung (App v1.1, AM3)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F302-22 | Factory-Type Manifest (Registry): `id: 3d_factory`, `name: "3D Factory"`, `functions: ["generate","validate","render","export","benchmark"]`, `gate: true`, `policies: ["3d_artefakt_freigabe"]`. | Schema-Test `FactoryTypeManifestTest.test_3d_factory` |
| F302-23 | App-Berechtigung (falls separate 3D-Viewer-App): `rechte: [datei_lesen, modell_nutzen, factory_build, factory_benchmark]`, `ablage: 50MB` (für STL/GLB). Werkseinstellung: nur `factory_build` (Stufe B, Gate), `datei_lesen` (Stufe A). | Test `BerechtigungTest.test_3d_viewer_rechte` |

---

## 3. Datenmodell (Ergänzung zu F3-01)

| Entität / VO | Felder (Kern) | Herkunft |
|---|---|---|
| `GeneratorConfig` | `template_id`, `parameters: dict`, `variant: str`, `output_formats: list[str]`, `printer_profile_id?` | Eingabe |
| `ValidationReport` | `status: ok|warn|fail`, `findings: list[Finding]`, `metrics: dict` (volume_mm3, surface_mm2, bbox_mm, est_print_time_s), `artifact_hashes: dict[format, str]` | Validator Ausgabe |
| `Finding` | `code: str` (z. B. `THIN_WALL`, `OVERHANG`, `NON_MANIFOLD`, `DIM_MISMATCH`), `message: str`, `severity: info|warn|fail`, `location: str` (Zeile/Feature) | Validator |
| `ArtifactManifest` | `project_id`, `module_id`, `build_id`, `formats: dict[format, ArtifactFile]`, `validation: ValidationReport`, `generator_version`, `template_version`, `created_at` | Export |
| `ArtifactFile` | `path`, `format`, `size_bytes`, `sha256`, `metadata: dict` (z. B. `triangle_count` für STL) | Export |

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für F3-02 |
|---|---|
| `runtime/src/sedra_runtime/factory_builder.py` | Factory Builder — Build-Ausführung für `3d_factory` Type |
| `runtime/src/sedra_runtime/factory_registry.py` | Registry — Type `3d_factory` registrieren |
| `runtime/src/sedra_runtime/evidence_store.py` | Evidence Store — Artefakte & Runs ablegen |
| `runtime/src/sedra_runtime/modules/factory_studio/` | F3-01 Modul — UI für 3D-Factory (Project Browser, GraphView, Execution View, Gate Panel) |
| `factory_templates/3d/` | Templates: `kappe_v27.scad`, `wuerfel.scad`, `pyramide.scad`, `zahnrad.scad`, `becher.scad`, `vase.scad`, `schraube.scad`, `buecherstuetze.scad`, `turm.scad` (Bestand aus `SEDRA_3D_Assets` & Nachtlauf) |
| `engines/tools/openscad-2021.01/openscad.exe` | OpenSCAD Binary (lokal, Pfad via `GUPPI_OPENSCAD` Env) |
| `runtime/config/freigabe_katalog.beispiel.yaml` | Gate `3d_artefakt_freigabe` → `captain` (Default) |
| `runtime/src/sedra_runtime/adapters/` | Adapter (Native) — 3D-Generator als Native Workflow Step |
| `docs/AUFTRAG_PAPERCLIP_3D_PIPELINE_2026-10-16.md` | Referenz-Pipeline (Bedarfsanalyst → Konstrukteur → Prüfer → Vorlage) |
| `SEDRA_3D_Assets_Sammlung_2026-11-13.zip` | Assets: GLB-Referenzen, Demos, Dokumentation (nur lesen) |

---

## 5. Freigabegrenzen & Gegenproben (harte Anforderungen)

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| **Kein Druck ohne Gate** | `3d_artefakt_freigabe` Gate zwingend vor jeder Außenwirkung. | Druck-Request ohne Gate → 403 `gate_required` |
| **Kein Versand/Maschine** | Keine API-Aufrufe an Druckdienste, Versand-APIs, Maschinen-Controller. | Code-Suche: `requests.post` mit Drucker-URL → nicht gefunden |
| **Kein Cloud-Rendering ohne Gate** | Lokales OpenSCAD/Blender nur. Cloud-Rendering (falls später) = eigenes Gate `3d_cloud_render`. | Cloud-Render-Request ohne Gate → 403 |
| **Reproduzierbarkeit** | Gleicher Input → gleiche Artefakt-Hashes (3 Wiederholungen). | Input variiert minimal → Hash anders (erwartet) |
| **Validierung vor Gate** | Gate-Karte zeigt nur Artefakte mit `validation.status != fail`. `fail` → kein Gate, Build `failed`. | `fail` Artefakt → Gate nicht angeboten |
| **Artefakt-Größenlimit** | Max 50 MB je Artefakt (STL/GLB), konfigurierbar. Größer → `artefakt_zu_gross`. | 100 MB STL → Build `failed` |
| **Template-Versionierung** | Template-Änderung → neue Version, alte Builds reproduzierbar. | Template v28 → Build mit v27 Hash ≠ v28 Hash |

---

## 6. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Factory-Type `3d_factory`** in Registry registrieren (Manifest, Functions, Gate-Policy).
2. **Generator-Modul** (Native Adapter Step `generate_scad`): Template laden → Parameter einsetzen → `.scad` schreiben.
3. **Validator-Modul** (Native Adapter Steps): `validate_syntax` (openscad parse), `validate_geometry` (render STL → trimesh), `validate_printability` (Wandstärke, Überhänge), `validate_dimensions` (Soll/Ist).
4. **Export-Modul**: STL (binär), GLB (via `trimesh.export`), 3MF (optional). Hashes berechnen.
5. **Evidence Store Integration**: Run anlegen, Artefakte & Prüfbericht speichern.
6. **Gate `3d_artefakt_freigabe`** in `freigabe_katalog.beispiel.yaml` → `captain`. Gate-Panel: GLB-Vorschau (Three.js), Prüfbericht, Hashes.
7. **Factory Studio (F3-01) Integration**: Type in Project Browser, Module als 3D-Objekte, GraphView Dependencies, Execution View Build-Flow.
8. **Templates finalisieren**: `kappe_v27.scad` als Referenz (aus `SEDRA_3D_Assets` / `Tools/skills/openscad-druckmodelle`), 8 weitere Basis-Templates.
9. **Tests** (siehe §2, Spalte „Prüfbar durch“).
10. **Abnahme**: Captain prüft Reproduzierbarkeit (3 Builds → gleiche Hashes), Gate-Flow, keine Außenwirkung ohne Gate, Validierung vor Gate.

---

## 7. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| F302-Q1: OpenSCAD vs. Blender als Default-Backend? | **OpenSCAD** (deterministischer, CLI-freundlich, im Repo vorhanden unter `engines/tools/openscad-2021.01`). Blender als Option `blender_factory` Type. | OpenSCAD ist funktional, reproduzierbar, keine GUI. |
| F302-Q2: GLB-Vorschau im Gate-Panel: Three.js einbinden oder statisches Thumbnail? | **Three.js** (lokal, `three.min.js` in `uix/tools/factory_studio/assets/`). GLB als Base64-Data-URL in Karte. Interaktiv drehbar. | Captain muss Geometrie prüfen können (Überhänge, Hohlräume). |
| F302-Q3: Drucker-Profile (Bauraum, Düse, Material) wo speichern? | `local_config/3d/printer_profile.yaml` (Vorbehalt `**/local_config/**`). Profil-ID in GeneratorConfig referenzierbar. | Getrennt von Code, Captain-änderbar, Hash-bindung. |
| F302-Q4: Nachtlauf-Pipeline (Paperclip) als Factory-Type `paperclip_3d` übernehmen? | **Ja**, als separater Type `paperclip_3d` mit Pipeline-Steps (Analyst → Konstrukteur → Prüfer → Vorlage). Wiederverwendet Generator/Validator. | Paperclip ist spezialisierter Anwendungsfall. |
| F302-Q5: Seedrachen-3D (GLB) als Factory-Output? | **Nein**, Seedrachen ist Visualisierung (App), nicht Factory-Artefakt. Factory liefert technische Modelle (Kappe, Zahnrad, etc.). | Trennung: Factory = technische Teile; App = Visualisierung. |

---

## 8. Anforderungs-IDs (Zusammenfassung)

F302-01 bis F302-23 (23 Anforderungen).  
Offene Fragen: F302-Q1 bis F302-Q5 (5 Fragen).

---

## 9. Referenzen (nur Lesen)

- `SEDRA_3D_Assets_Sammlung_2026-11-13.zip`: 27 Dateien (GLB-Modelle, HTML-Demos, Doku: PLAN_V0.4.md, TESTS_UND_GRENZEN.md, WEB_INTEGRATION.md, MANIFEST_SHA256.txt)
- `docs/AUFTRAG_PAPERCLIP_3D_PIPELINE_2026-10-16.md`: 4-Rollen-Pipeline (Analyst, Konstrukteur, Prüfer, Vorlage)
- `docs/LOGBUCH_AGENT_MANAGER.md`: Einträge zu OpenSCAD (Kappe v27, Nachtlauf 3D, Debug-Modus GPU)
- `Tools/skills/openscad-druckmodelle/`: Lehren, `kappe_komplett_v27.scad` (lokal, untracked)
- `runtime/docs/ADAPTERS.md`: Native Adapter für Generator/Validator/Export Steps

---

**Ende der Spec F3-02.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a008` unter `docs/SPEC_F3_02_3D_FACTORY_PILOT_2026-11-14.md`.