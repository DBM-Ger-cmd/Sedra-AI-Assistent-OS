# Spec F3-03 – Webshop Factory Pilot

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-009), nachgeprüft: 26 Anforderungs-IDs (F303-01 bis -26), harte Grenzen mit Gegenproben (Live-Publikation, Bestellung/Zahlung, Export, Preisänderung je nur mit Captain-Gate), keine lokalen Pfade. Hinweise: Pis Zeilenangabe im ERGEBNIS (151) war falsch, die Datei hat 194 Zeilen. Der Hybrid-Adapter mit n8n ist nur optional; Dateien mit `n8n`/`workflow` im Namen bleiben bis zur Freigabe durch ChatGPT-Überarbeitung unberührt. Abhängigkeit F3-01 (Oberfläche) ist selbst noch nicht geprüft. Status: Entwurf, noch nicht vom Captain freigegeben.


**Stand:** 2026-11-14  
**Register:** SEDRA-F3-03  
**Abhängig von:** F2-01 (Registry, auf main), F3-01 (Factory Studio App)  
**Quellen:** `runtime/src/sedra_runtime/evidence_store.py`, `runtime/src/sedra_runtime/factory_registry.py`, `runtime/src/sedra_runtime/factory_builder.py`, `runtime/src/sedra_runtime/adapters/`, `runtime/docs/ADAPTERS.md`, `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md` (Form der Spec)  
**Ziel:** Spec für Produkt-, Katalog- und Frontend-Pipeline mit Staging — **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Harte Grenze (Captain-Beschluss 14.11.2026):** Keine automatische Live-Publikation, keine Bestellung, keine Zahlung. Jede Außenwirkung (z. B. Staging-Veröffentlichung, Katalog-Export an Shop-System) nur über ein Captain-Gate. Alles läuft als Artefakt im Evidence Store, Validierung vor Freigabe.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Produktkatalog und Frontend-Pipeline für einen Webshop als Factory-Pipeline: Produkte anlegen, Katalog-Versionen bauen, Staging-Umgebung befüllen, Captain-Freigabe für Live-Publikation, Artefakte im Evidence Store ablegen. UI über Factory Studio App (F3-01). |
| **Was sie NICHT ist** | Kein laufender Webshop, kein Checkout, keine Zahlungsabwicklung, keine automatische Live-Publikation, keine Kundenbestellung, keine Kundendaten-Verarbeitung. Keine eigene Runtime, läuft als Factory-Type in der Registry. |
| **Einordnung** | Factory-Type `webshop` (oder `webshop_factory`, `katalog_factory`) in Registry (F2-01). Wird über Factory Studio (F3-01) gesteuert: Project → Module (Produkte, Katalogseiten) → Build → Gate → Staging-Artefakt. |

---

## 2. Anforderungen (mit IDs)

### 2.1 Produkt- und Katalog-Management

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F303-01 | Produkte anlegen: SKU, Name, Beschreibung, Preis, Kategorie, Bestand, Metadaten. Status: `draft` → `review` → `published` / `archived`. | Unit-Test `KatalogTest.test_create_product` |
| F303-02 | Produkte listen, filtern (Kategorie, Status, Bestand), suchen (Name, SKU). | Unit-Test `KatalogTest.test_list_filter` |
| F303-03 | Produkt-Details laden: Varianten, Attribute, letzte Katalog-Version, zugehörige Artefakte. | Unit-Test `KatalogTest.test_load_details` |
| F303-04 | Katalog-Version anlegen: Name, Version, Produkte (Referenzen), Erzeugungsdatum, Status `draft` → `built` → `staged` / `failed`. | Unit-Test `KatalogTest.test_create_version` |
| F303-05 | Produkt-Varianten verwalten: Größe, Farbe, Material, SKU-Suffix, Preis-Aufschlag. | Unit-Test `KatalogTest.test_variant_management` |
| F303-06 | Kategorie-Hierarchie: Eltern-Kategorie, Unterkategorien, Pfad-Anzeige. Zyklus-Erkennung bei Eltern-Verweis. | Unit-Test `KatalogTest.test_category_hierarchy` |
| F303-07 | Produkt-Archivierung: Nur ohne aktive Katalog-Version und stock = 0. | Unit-Test `KatalogTest.test_archive_product` |
| F303-08 | Produkt-Duplikat erkennen: Gleiche SKU → Fehler, kein Duplikat anlegen. | Unit-Test `KatalogTest.test_duplicate_sku` |

### 2.2 Frontend-Pipeline (Build, Staging)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F303-09 | Frontend-Build starten (Katalog-Version → HTML/JS/CSS-Artefakte) via Factory Builder. Gate `webshop_build` (Captain-Freigabe) erforderlich. | Integration-Test `PipelineTest.test_build_with_gate` |
| F303-10 | Build-Status live: `pending` → `running` → `success`/`failed`/`cancelled`. Dauer, Artefakte, Fehlermeldung, Metriken anzeigen. | Unit-Test `PipelineTest.test_build_status` |
| F303-11 | Staging-Umgebung befüllen: Build-Artefakte in Staging-Verzeichnis kopieren, nicht live schalten. Staging-URL generieren (intern, nicht öffentlich). | Integration-Test `PipelineTest.test_staging_deploy` |
| F303-12 | Staging-Artefakte im Evidence Store ablegen: Run-Eintrag mit `artifacts[]` (Pfade), `metrics`, Prüfbericht. | Integration-Test `EvidenceStoreTest.test_webshop_artifacts` |
| F303-13 | Staging-Artefakte auflisten und löschen (nur wenn keine Live-Publikation pending). | Unit-Test `PipelineTest.test_staging_list_delete` |
| F303-14 | Staging-URL prüfen: Interner Token, nicht öffentlich erreichbar, Timeout nach 72h. | Unit-Test `PipelineTest.test_staging_url_security` |

### 2.3 Veröffentlichung & Captain-Gate (harte Grenze)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F303-15 | **Keine automatische Live-Publikation**: Build-Status `success` → Artefakte im Staging, **aber** Gate `webshop_live_publish` (Captain) erforderlich vor Veröffentlichung auf Live-System. | Integration-Test `GateTest.test_no_live_without_gate` |
| F303-16 | Gate-Karte anzeigen: Typ, Ziel (Staging/Live), Diff/Vorschau (geplante Produktänderungen, Katalog-Diff), Prüfbericht (Zusammenfassung), Artefakt-Hashes, Risiken (Preisänderung, Bestand 0). | Unit-Test `GateTest.test_card_content` |
| F303-17 | Captain-Entscheidung: `approve` → Artefakte als `freigegeben` markiert, Export in `freigegeben/` Ordner, Event `factory.webshop.published`. `reject` → Grund, Artefakte bleiben `pending`, Event `factory.webshop.rejected`. | Integration-Test `GateTest.test_approve_reject` |
| F303-18 | **Keine Bestellung, keine Zahlung**: Webshop-Artefakte enthalten keine Checkout-, Zahlungs- oder Kundenkonto-Logik. Jegliche API-Anfrage an Zahlungsdienste → 403 `verb_nicht_gewaehrt`. | Unit-Test `GateTest.test_no_payment` |
| F303-19 | Nach Entscheidung: Gate-Karte schließt, Status Dashboard aktualisiert, Event `harness.gate.decided` publizieren. | Integration-Test `GateTest.test_event_publish` |
| F303-20 | Preisänderung braucht Gate: Änderung von `price` oder `stock` erfordert Captain-Gate. | Unit-Test `GateTest.test_price_change_gate` |

### 2.4 Integration in Factory Studio (F3-01)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F303-21 | Project Browser: Factory-Type `webshop` auswählbar. Module = Produkte/Katalogseiten (je Katalog ein Modul). | Integration-Test `FactoryStudioIntegrationTest.test_webshop_type_visible` |
| F303-22 | GraphView: Dependigkeiten zwischen Produkten, Kategorien, Katalog-Versionen. Layer: `domain` (Produkt), `application` (Katalog-Logik), `infrastructure` (Frontend-Export). | Integration-Test `FactoryStudioIntegrationTest.test_webshop_graph` |
| F303-23 | Execution View: Build startet Katalog-Build → Staging → Gate-Wartezimmer. Status live. Benchmark: Varianten-Vergleich (Produktanzahl, Build-Dauer, Artefakt-Größe). | Integration-Test `FactoryStudioIntegrationTest.test_webshop_build_flow` |
| F303-24 | Gate Panel: `webshop_live_publish` Gate erscheint, Karte mit Katalog-Diff, Staging-Vorschau, Prüfbericht. | Browser-Test `GatePanelTest.test_webshop_preview` |

### 2.5 Manifest & Berechtigung (App v1.1, AM3)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F303-25 | Factory-Type Manifest (Registry): `id: webshop`, `name: "Webshop Factory"`, `functions: ["catalog_build","staging","publish","benchmark"]`, `gate: true`, `policies: ["webshop_live_publish"]`. | Schema-Test `FactoryTypeManifestTest.test_webshop_factory` |
| F303-26 | App-Berechtigung: `rechte: [katalog_lesen, katalog_bauen, staging_befüllen, webshop_publish]`, `ablage: 100MB` (für HTML/JS/CSS/Assets). Werkseinstellung: nur `katalog_lesen` (Stufe A), `katalog_bauen` und `staging_befüllen` (Stufe B, Gate), `webshop_publish` (Stufe C, nur Captain). | Test `BerechtigungTest.test_webshop_rechte` |

---

## 3. Datenmodell (Ergänzung zu F3-01)

| Entität / VO | Felder (Kern) | Herkunft |
|---|---|---|
| `Product` | `sku`, `name`, `description`, `price`, `category`, `stock`, `status` (ProductStatus), `created_at`, `updated_at`, `metadata`, `variants[]` | Eingabe |
| `ProductVariant` | `id`, `product_id`, `name`, `sku_suffix`, `price_surcharge`, `stock`, `attribute: dict` (Größe/Farbe/Material) | Produkt |
| `CatalogVersion` | `id`, `name`, `version`, `products: list[ProductRef]`, `status` (CatalogStatus), `created_at`, `build_id?`, `artifacts[]` | Katalog-Pipeline |
| `WebshopBuild` | `id`, `catalog_version_id`, `build_type`, `status` (BuildStatus), `started_at`, `finished_at`, `duration_ms`, `success`, `artifacts[]`, `error_message`, `metrics` | Factory Builder |
| `StagingArtifact` | `path`, `format`, `size_bytes`, `sha256`, `staging_url`, `metadata: dict` | Staging-Export |
| `PublishGate` | `id`, `gate_type`, `target_id`, `status` (pending/approved/rejected), `requested_by`, `requested_at`, `decided_by?`, `decided_at?`, `decision_reason?` | Gate |
| `CatalogDiff` | `id`, `catalog_version_id`, `changes: list[Change]` (hinzugefügt/geändert/entfernt), `before_hash`, `after_hash`, `created_at` | Diff-Berechnung |
| `Change` | `feld: str`, `typ` (added/changed/removed), `alter_wert`, `neuer_wert`, `severity` (info/warn/fail) | Diff-Eintrag |

Value Objects: `ProductRef`, `SKU`, `CatalogId`, `BuildId`, `StagingUrl`, `MetricPoint`, `ChangeSeverity`.

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für F3-03 |
|---|---|
| `runtime/src/sedra_runtime/factory_registry.py` | Registry — Type `webshop` registrieren, Gate-Freigabe |
| `runtime/src/sedra_runtime/factory_builder.py` | Factory Builder — Build-Ausführung für `webshop` Type |
| `runtime/src/sedra_runtime/evidence_store.py` | Evidence Store — Runs, Artefakte, Gate Evidence ablegen |
| `runtime/src/sedra_runtime/adapters/native/` | Native Adapter Steps für Webshop-Pipeline (produkt_anlegen, katalog_bauen, staging_befüllen) |
| `runtime/src/sedra_runtime/adapters/hybrid/` | Hybrid Adapter für Webshop (optional, Native + n8n) |
| `runtime/config/freigabe_katalog.beispiel.yaml` | Gate `webshop_live_publish` → `captain` (Default) |
| `runtime/src/sedra_runtime/modules/factory_studio/` | F3-01 Modul — UI für Webshop (Project Browser, GraphView, Execution View, Gate Panel) |
| `factory_templates/webshop/` | Templates: `produkt_tpl.md`, `katalog_tpl.md`, `frontend_build_tpl.yaml` (neu) |
| `runtime/src/sedra_runtime/uix/tools/webshop/` | Tool-Manifest `tool.yaml` für Webshop-App (Vergleich mit F3-01 factory_studio) |
| `docs/AUFTRAG_PAPERCLIP_3D_PIPELINE_2026-10-16.md` | Referenz-Pipeline (Analyst → Konstrukteur → Prüfer → Vorlage), analog für Webshop |

---

## 5. Freigabegrenzen & Gegenproben (harte Anforderungen)

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| **Keine automatische Live-Publikation** | Jede Veröffentlichung auf Live-System erfordert Captain-Gate `webshop_live_publish`. | Publish-Request ohne Gate → 403 `gate_required` |
| **Keine Bestellung, keine Zahlung** | Keine Checkout-, Zahlungs- oder Kundenkonto-Logik in Artefakten. | API-Anfrage an Zahlungsdienst → 403 `verb_nicht_gewaehrt` |
| **Validierung vor Gate** | Gate-Karte zeigt nur Artefakte mit gültigem Prüfbericht. `fail` → kein Gate, Build `failed`. | `fail` Artefakt → Gate nicht angeboten |
| **Staging ist nicht Live** | Staging-Umgebung ist intern, nicht öffentlich erreichbar. Kein automatischer Push zu Live. | Staging-URL öffentlich erreichbar → Test fehlschlägt |
| **Artefakt-Größenlimit** | Max 100 MB je Artefakt (HTML/JS/CSS/Assets), konfigurierbar. Größer → `artefakt_zu_gross`. | 200 MB Bundle → Build `failed` |
| **Katalog-Versionierung** | Katalog-Änderung → neue Version, alte Builds reproduzierbar. | Template v2 → Build mit v1 Hash ≠ v2 Hash |
| **Kein direkter Kunden-Export** | Produkte dürfen nicht direkt als CSV/JSON an Kunden-Systeme exportiert werden. Export nur über Gate `webshop_export`. | Export-Request ohne Gate → 403 `gate_required` |
| **Preisänderung braucht Gate** | Änderung von `price` oder `stock` erfordert Captain-Gate (Risiko für Live-System). | Preis-Änderung ohne Gate → 403 `preis_änderung_gesperrt` |
| **Produkt-Löschung nur ohne aktive Bestellung** | Produkt mit `stock > 0` oder in aktiver Katalog-Version darf nicht gelöscht werden. | Löschung mit stock > 0 → 409 `konflikt_aktiv` |
| **Staging-Token geheim** | Staging-URL enthält internen Token, nicht in Logs oder Chats sichtbar. | Token im Log → Test fehlschlägt |

---

## 6. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Factory-Type `webshop`** in Registry registrieren (Manifest, Functions, Gate-Policy).
2. **Produkt- und Katalog-Modul** (Native Adapter Steps): Produkte anlegen, Katalog-Version bauen, Validierung.
3. **Frontend-Build-Modul** (Native Adapter Steps): Katalog-Version → HTML/JS/CSS-Artefakte, Hashes berechnen.
4. **Staging-Export**: Artefakte in Staging-Verzeichnis kopieren, Staging-URL generieren (intern).
5. **Evidence Store Integration**: Run anlegen, Artefakte & Prüfbericht speichern.
6. **Gate `webshop_live_publish`** in `freigabe_katalog.beispiel.yaml` → `captain`. Gate-Panel: Katalog-Diff, Staging-Vorschau, Prüfbericht, Hashes.
7. **Factory Studio (F3-01) Integration**: Type in Project Browser, Module als Produkte/Katalogseiten, GraphView Dependencies, Execution View Build-Flow.
8. **Tests** (siehe §2, Spalte „Prüfbar durch“).
9. **Abnahme**: Captain prüft keine Live-Publikation ohne Gate, keine Bestellung/Zahlung, Validierung vor Gate, Staging-Internität, Reproduzierbarkeit.

---

## 7. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| F303-Q1: Staging-URL-Format (intern, nicht öffentlich)? | `http://localhost:8080/staging/<run_id>/` oder relativer Pfad. Nicht über öffentliche Domain. | Verhindert versehentliche Live-Erreichbarkeit. |
| F303-Q2: Katalog-Diff im Gate-Panel: JSON-Diff oder gerendertes HTML-Vorschau? | **Beides**: JSON-Diff für präzise Änderungen, HTML-Vorschau (Base64) für visuelle Prüfung. | Captain muss Inhalt und Optik prüfen können. |
| F303-Q3: Produkt-Attribute (Preis, Bestand) als séparates Gate `katalog_preis_änderung`? | **Nein**, vorerst ein Gate `webshop_live_publish` für alle Änderungen. Captain entscheidet pro Gate-Eintrag. | Weniger Gate-Komplexität für MVP. |
| F303-Q4: Mehrsprachige Kataloge (DE/EN)? | **Nein**, vorerst deutsche Kataloge. Mehrsprachigkeit als spätere Erweiterung (eigener Factory-Type). | Fokus auf Kern-Pipeline ohne Gate-Erweiterung. |
| F303-Q5: Automatischer Staging-Rebuild bei Produktänderung? | **Nein**, manueller Build-Start mit Gate. Kein automatischer Trigger. | Verhindert unkontrollierte Außenwirkung. |
| F303-Q6: Staging-Verzeichnis pro Build oder gemeinsam? | **Pro Build**: `staging/<run_id>/`. Gemeinsames Verzeichnis riskiert Vermischung von Versionen. | Klare Trennung der Builds, einfachere Löschung. |
| F303-Q7: Webshop-App als eigene App oder Modul in Factory Studio? | **Modul in Factory Studio** (F3-01), keine separate App. Nutzt bestehende UI-Komponenten. | Weniger Aufwand, konsistente Oberfläche. |
| F303-Q8: Produkt-Bild-Assets (Bilder) im Evidence Store? | **Nein**, vorerst keine Bilder. Nur Text/HTML/JS/CSS. Bilder als spätere Erweiterung. | Bilder erhöhen Artefakt-Größe und brauchen eigenes Gate. |
| F303-Q9: Staging-URL mit Authentifizierung oder offen? | **Mit einfachem Token** (intern). Keine öffentliche Authentifizierung, aber nicht ratbar. | Verhindert versehentlichen Zugriff durch Dritte. |

---

## 8. Anforderungs-IDs (Zusammenfassung)

F303-01 bis F303-26 (26 Anforderungen).  
Offene Fragen: F303-Q1 bis F303-Q9 (9 Fragen).

---

## 9. Referenzen (nur Lesen)

- `runtime/src/sedra_runtime/evidence_store.py`: Runs, Benchmarks, Gate Evidence, Meta Insights (F2-03).
- `runtime/src/sedra_runtime/factory_registry.py`: Factory-Typen, Zustände, Gate-Freigabe (F2-01).
- `runtime/src/sedra_runtime/factory_builder.py`: Projekt/Modul/Service-Build, Templates (F2-02).
- `runtime/src/sedra_runtime/adapters/native/`: Native Workflow Steps für Webshop-Pipeline.
- `runtime/src/sedra_runtime/adapters/hybrid/`: Hybrid Adapter für Webshop (optional, Native + n8n).
- `runtime/docs/ADAPTERS.md`: Adapter-Dokumentation (Native, n8n, Hybrid).
- `docs/AUFTRAG_PAPERCLIP_3D_PIPELINE_2026-10-16.md`: Referenz-Pipeline (4-Rollen-Modell).
- `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md`: Form-Vorlage für diese Spec.
- `docs/ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md`: App-Rahmen, Manifest v1.1, Profile.
- `docs/SPEC_APPS_v1_AM3_BERECHTIGUNG.md`: Berechtigungsmodell, Gates, Werkseinstellung.

## 10. Implementierungshinweise (für späteren Auftrag, nicht Teil dieser Spec)

- Produkte werden als JSON im Evidence Store gespeichert, nicht als Dateien im Dateisystem.
- Staging-URLs dürfen niemals in E-Mails oder Chats veröffentlicht werden (interner Token).
- Der Katalog-Diff wird serverseitig berechnet und nicht clientseitig, um Manipulation zu vermeiden.
- Alle Gate-Entscheidungen werden im Evidence Store als `gate_evidence` mit `verdict` protokolliert.
- Build-Logs werden als separates Artefakt im Evidence Store abgelegt, nicht im Staging-Verzeichnis.
- Das `ablage`-Limit von 100 MB wird im Build-Schritt geprüft, bevor Artefakte geschrieben werden.
- Staging-URLs laufen über einen internen Reverse-Proxy, nicht direkt über den Webserver.
- Keine Dateien mit `n8n` oder `workflow` im Namen werden von dieser Spec erzeugt oder geändert (siehe F-006).
- Der Captain entscheidet bei der Abnahme über die endgültige Gate-Konfiguration.

---

**Ende der Spec F3-03.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a009` unter `docs/SPEC_F3_03_WEBSHOP_FACTORY_PILOT_2026-11-14.md`.
