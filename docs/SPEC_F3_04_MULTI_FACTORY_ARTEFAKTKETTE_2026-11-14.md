# Spec F3-04 – Multi-Factory Artefaktkette

> **Prüfvermerk des Koordinators (14.11.2026):** Entwurf von Pi (A-009), nachgeprüft: 24 Anforderungs-IDs (F304-01 bis -24), Provenienz, Eigentums-Check und Gate je Übergabe mit Gegenproben (ohne Gate → 403 `gate_required`), keine lokalen Pfade. Hinweis: Pis Zeilenangabe im ERGEBNIS (150) war falsch, die Datei hat 194 Zeilen. Eine Übergabe zwischen Fabriken darf nie Druck, Versand, Maschinenauftrag oder Veröffentlichung auslösen (vgl. F302-17, Vermerk in F3-02). Status: Entwurf, noch nicht vom Captain freigegeben.


**Stand:** 2026-11-14  
**Register:** SEDRA-F3-04  
**Abhängig von:** F3-02 (3D Factory Pilot), F3-03 (Webshop Factory Pilot)  
**Quellen:** `runtime/src/sedra_runtime/evidence_store.py`, `runtime/src/sedra_runtime/factory_registry.py`, `runtime/src/sedra_runtime/factory_builder.py`, `runtime/src/sedra_runtime/adapters/`, `runtime/docs/ADAPTERS.md`, `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md` (Form der Spec)  
**Ziel:** Spec für typisierte Artefakt- und Evidence-Übergaben zwischen Fachfabriken — **kein Code**, nur Dokumentation. Datei unter 400 Zeilen.

> **Harte Grenze (Captain-Beschluss 14.11.2026):** Provenienz, Eigentümermerkmale, Risiken und Freigabegrenzen durchgehend. Jede Übergabe zwischen Fabriken ist ein typisiertes Artefakt im Evidence Store mit Captain-Gate vor Überschreitung der Fabrikgrenze. Keine unbemerkte Änderung, keine Außenwirkung ohne Gate.

---

## 1. Zweck & Abgrenzung

| Aspekt | Beschreibung |
|---|---|
| **Zweck** | Typisierte Übergabe von Artefakten und Evidence zwischen Fachfabriken (z. B. 3D Factory → Webshop Factory → Factory Studio). Jede Übergabe trägt Provenienz (Herkunft, Erzeuger, Zeitstempel), Eigentümermerkmale (Besitzer, Rechte, Rolle), Risiken (Validierungsstatus, Warnungen) und Freigabegrenzen (Captain-Gate, Prüfbericht). Alles im Evidence Store nachweisbar. |
| **Was sie NICHT ist** | Keine gemeinsame Datenbank zwischen Fabriken, keine automatische Replikation, keine unbemerkte Änderung fremder Artefakte, keine Außenwirkung ohne Captain-Gate. Keine eigene Runtime, läuft über Factory Builder und Evidence Store. |
| **Einordnung** | Artefaktkette als Factory-Type `artefakt_chain` (oder `multi_factory_chain`) in Registry (F2-01). Nutzt Evidence Store (F2-03) als zentrales Nachweismittel. Übergaben werden als Gate-Evidence protokolliert. |

---

## 2. Anforderungen (mit IDs)

### 2.1 Typisierte Artefakt-Übergaben

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F304-01 | Jede Fabrik gibt Artefakte als typisierte Übergabe aus: `artefakt_typ` (z. B. `3d_stl`, `katalog_html`, `evidence_pdf`), `fabrik_quelle`, `fabrik_ziel`, `version`, `timestamp`. | Unit-Test `ArtefaktTest.test_typed_handover` |
| F304-02 | Artefakt-Übergabe enthält Provenienz: `erzeuger` (Factory-Type ID), `erzeugt_am` (ISO8601), `build_id`, `run_id`, `template_version`, `generator_version`. | Unit-Test `ArtefaktTest.test_provenance` |
| F304-03 | Artefakt-Übergabe enthält Eigentümermerkmale: `besitzer` (Rolle/Team), `rechte` (lesen/schreiben/freigeben), `rolle` (erzeuger/prüfer/freigaber), `manifest_sha256`. | Unit-Test `ArtefaktTest.test_eigentum` |
| F304-04 | Artefakt-Übergabe enthält Risiken: `validierungs_status` (ok/warn/fail), `risiken: list[Risiko]` (je: `code`, `message`, `severity`), `prüfbericht_id`. | Unit-Test `ArtefaktTest.test_risiken` |
| F304-05 | Artefakt-Übergabe enthält Hashes je Format (SHA256) für Verifizierung beim Empfang. | Unit-Test `ArtefaktTest.test_hashes` |
| F304-06 | Übergabe-Status: `pending` → `uebergeben` / `abgewiesen`. Nur Captain-Gate darf `uebergeben` setzen. | Unit-Test `ArtefaktTest.test_status_flow` |

### 2.2 Evidence-Kette & Nachweis

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F304-07 | Jede Übergabe wird als Gate-Evidence im Evidence Store protokolliert: `gate_id`, `run_id`, `evidence_type: "artefakt_handover"`, `payload` (Provenienz, Eigentum, Risiken, Hashes), `verdict: pending/pass/fail`. | Integration-Test `EvidenceStoreTest.test_handover_evidence` |
| F304-08 | Artefakt-Hashes (SHA256) werden bei Empfang verifiziert. Hash-Abweichung → Übergabe `fail`, Artefakt nicht übernommen. | Unit-Test `ArtefaktTest.test_hash_verification` |
| F304-09 | Kette nachvollziehbar: Artefakt A (Fabrik 1) → Artefakt B (Fabrik 2) → Artefakt C (Fabrik 3). Jede Übergabe referenziert die vorherige (`vorherige_artefakt_id`). | Unit-Test `KetteTest.test_chain_traceability` |
| F304-10 | Evidence-Abruf: `sedra factory evidence show <run_id>` liefert vollständige Kette mit allen Übergaben, Provenienzen, Hashes, Verdicts. | Integration-Test `EvidenceStoreTest.test_chain_retrieval` |
| F304-11 | Kette-Status: `aktiv` → `abgeschlossen` / `abgebrochen`. Abgebrochene Ketten bleiben im Evidence Store als Nachweis. | Unit-Test `KetteTest.test_chain_status` |
| F304-12 | Kette-Zusammenfassung: Anzahl Übergaben, durchschnittliche Dauer, Fehlerrate, letzte Änderung. | Unit-Test `KetteTest.test_chain_summary` |

### 2.3 Freigabegrenzen & Captain-Gate

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F304-13 | **Übergabe nur mit Gate**: Artefakt darf Fabrikgrenze nur überschreiten, wenn Captain-Gate `artefakt_uebergabe` (oder fabrikspezifisch `artefakt_uebergabe_3d_webshop`) `approve` ist. `reject` → Artefakt bleibt in Quellfabrik. | Integration-Test `GateTest.test_handover_without_gate` |
| F304-14 | Gate-Karte zeigt: Artefakt-Typ, Quellfabrik, Zielfabrik, Provenienz-Zusammenfassung, Eigentümer, Risiken (Warnungen/Fehler), Prüfbericht, Hashes, Vorherige Übergabe. | Unit-Test `GateTest.test_handover_card` |
| F304-15 | Captain-Entscheidung: `approve` → Artefakt als `uebergeben` markiert, Zielfabrik erhält Artefakt, Event `factory.artefakt.uebergeben`. `reject` → Grund, Artefakt bleibt `pending` in Quellfabrik, Event `factory.artefakt.abgewiesen`. | Integration-Test `GateTest.test_handover_approve_reject` |
| F304-16 | **Keine unbemerkte Änderung**: Empfangende Fabrik darf Artefakt nicht still ändern. Änderungen erzeugen neues Artefakt mit neuer Provenienz und eigenem Gate. | Unit-Test `ArtefaktTest.test_no_silent_mutation` |
| F304-17 | Nach Entscheidung: Gate-Karte schließt, Status Dashboard aktualisiert, Event `harness.gate.decided` publizieren. | Integration-Test `GateTest.test_event_publish` |
| F304-18 | Eigentums-Check: Nur berechtigte Rollen dürfen Artefakte übergeben/empfangen. Unberechtigt → 403 `nicht_erlaubt`. | Unit-Test `GateTest.test_eigentums_check` |

### 2.4 Fabrikübergreifende Beispiele (3D → Webshop → Studio)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F304-19 | 3D Factory (F3-02) erzeugt STL/GLB-Artefakt → Übergabe an Webshop Factory (F3-03) für Produktkatalog (3D-Vorschau im Webshop). Gate `artefakt_uebergabe_3d_webshop`. | Integration-Test `KetteTest.test_3d_to_webshop` |
| F304-20 | Webshop Factory erzeugt Katalog-HTML-Artefakt → Übergabe an Factory Studio (F3-01) für Status-Dashboard und Gate-Panel. Gate `artefakt_uebergabe_webshop_studio`. | Integration-Test `KetteTest.test_webshop_to_studio` |
| F304-21 | Factory Studio konsolidiert: Zeigt alle eingehenden Artefakte mit Provenienz, Risiken, Freigabestatus. Offene Gates listen. | Integration-Test `FactoryStudioIntegrationTest.test_artefakt_konsolidierung` |
| F304-22 | Rückgabe an Quellfabrik möglich (z. B. Korrektur): Rückgabe-Übergabe mit eigenem Gate, referenziert Original. | Integration-Test `KetteTest.test_uebernahme_rueckgabe` |

### 2.5 Manifest & Berechtigung (App v1.1, AM3)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| F304-23 | Factory-Type Manifest (Registry): `id: artefakt_chain`, `name: "Multi-Factory Artefaktkette"`, `functions: ["uebergeben","empfangen","verifizieren","kette_nachverfolgen"]`, `gate: true`, `policies: ["artefakt_uebergabe"]`. | Schema-Test `FactoryTypeManifestTest.test_artefakt_chain` |
| F304-24 | App-Berechtigung: `rechte: [artefakt_lesen, artefakt_uebergeben, artefakt_empfangen, kette_nachverfolgen]`, `ablage: 200MB` (für Artefakt-Kopien). Werkseinstellung: nur `artefakt_lesen` und `kette_nachverfolgen` (Stufe A), `artefakt_uebergeben` und `artefakt_empfangen` (Stufe B, Gate). | Test `BerechtigungTest.test_artefakt_chain_rechte` |

---

## 3. Datenmodell

| Entität / VO | Felder (Kern) | Herkunft |
|---|---|---|
| `ArtefaktHandover` | `id`, `artefakt_typ`, `fabrik_quelle`, `fabrik_ziel`, `version`, `timestamp`, `provenienz`, `eigentum`, `risiken`, `hashes: dict[format, str]`, `vorherige_artefakt_id?`, `status` (pending/uebergeben/abgewiesen), `gate_id` | Übergabe |
| `Provenienz` | `erzeuger` (Factory-Type ID), `erzeugt_am` (ISO8601), `build_id`, `run_id`, `template_version`, `generator_version` | Quelle |
| `Eigentum` | `besitzer` (Rolle/Team), `rechte: list[str]` (lesen/schreiben/freigeben), `rolle` (erzeuger/prüfer/freigaber), `manifest_sha256` | Quelle |
| `Risiko` | `code: str` (z. B. `THIN_WALL`, `PREIS_ÄNDERUNG`, `BESTAND_NULL`), `message: str`, `severity: info|warn|fail` | Validator |
| `ArtefaktKette` | `id`, `artefakte: list[ArtefaktRef]`, `uebergaben: list[HandoverRef]`, `start_artefakt_id`, `end_artefakt_id`, `status` (aktiv/abgeschlossen/abgebrochen) | Kette |

Value Objects: `ArtefaktId`, `HandoverId`, `FactoryId`, `ArtefaktTyp`, `HashSha256`, `Timestamp`.

---

## 4. Betroffene Dateien (nur benennen)

| Datei / Pfad | Rolle für F3-04 |
|---|---|
| `runtime/src/sedra_runtime/factory_registry.py` | Registry — Type `artefakt_chain` registrieren, Gate-Freigabe |
| `runtime/src/sedra_runtime/factory_builder.py` | Factory Builder — Build-Ausführung für Artefaktkette |
| `runtime/src/sedra_runtime/evidence_store.py` | Evidence Store — Runs, Artefakte, Gate Evidence, Kette nachverfolgen |
| `runtime/src/sedra_runtime/adapters/native/` | Native Adapter Steps für Artefaktkette (uebergeben, empfangen, verifizieren) |
| `runtime/src/sedra_runtime/adapters/hybrid/` | Hybrid Adapter für Artefaktkette (optional, Native + n8n) |
| `runtime/config/freigabe_katalog.beispiel.yaml` | Gate `artefakt_uebergabe` → `captain` (Default) |
| `runtime/src/sedra_runtime/modules/factory_studio/` | F3-01 Modul — UI für Artefaktkette (Status-Dashboard, Gate-Panel, Konsolidierung) |
| `factory_templates/artefakt_chain/` | Templates: `uebergabe_tpl.md`, `kette_tpl.md`, `verifizierung_tpl.yaml` (neu) |

---

## 5. Freigabegrenzen & Gegenproben (harte Anforderungen)

| Grenze | Beschreibung | Gegenprobe (muss fehlschlagen) |
|---|---|---|
| **Übergabe nur mit Gate** | Artefakt darf Fabrikgrenze nur mit Captain-Gate überschreiten. | Übergabe ohne Gate → 403 `gate_required` |
| **Keine unbemerkte Änderung** | Empfangende Fabrik darf Artefakt nicht still ändern. Änderungen = neues Artefakt mit neuer Provenienz. | Still-change → Hash-Abweichung → `fail` |
| **Hash-Verifizierung** | Empfang prüft SHA256-Hashes. Abweichung → Übergabe `fail`, Artefakt nicht übernommen. | Manipuliertes Artefakt → `hash_mismatch` |
| **Validierung vor Gate** | Gate-Karte zeigt nur Artefakte mit gültigem Prüfbericht. `fail` → kein Gate. | `fail` Artefakt → Gate nicht angeboten |
| **Provenienzpflicht** | Jedes Artefakt benötigt vollständige Provenienz (Erzeuger, Zeit, Build, Run). Fehlende Provenienz → Artefakt nicht registrierbar. | Ohne Provenienz → `provenienz_fehlt` |
| **Eigentums-Check** | Nur berechtigte Rollen dürfen Artefakte übergeben/empfangen. Unberechtigt → 403 `nicht_erlaubt`. | Unberechtigte Rolle → 403 |
| **Artefakt-Größenlimit** | Max 200 MB je Artefakt (Kopie in Zielfabrik). Größer → `artefakt_zu_gross`. | 500 MB Artefakt → Build `failed` |

---

## 6. Reihenfolge der Schritte (Implementierungsfolge, für späteren Auftrag)

1. **Factory-Type `artefakt_chain`** in Registry registrieren (Manifest, Functions, Gate-Policy).
2. **Artefakt-Übergabe-Modul** (Native Adapter Steps): `artefakt_uebergeben` (Provenienz, Eigentum, Risiken, Hashes), `artefakt_empfangen` (Hash-Verifizierung, Übernahme), `kette_nachverfolgen` (Evidence-Abruf).
3. **Evidence Store Integration**: Gate-Evidence für jede Übergabe, Kette nachverfolgbar.
4. **Gate `artefakt_uebergabe`** in `freigabe_katalog.beispiel.yaml` → `captain`. Gate-Panel: Provenienz, Eigentum, Risiken, Hashes, Vorherige Übergabe.
5. **Fabrikübergreifende Integration**: 3D Factory → Webshop Factory → Factory Studio (F3-01 Status-Dashboard, Gate-Panel).
6. **Tests** (siehe §2, Spalte „Prüfbar durch“).
7. **Abnahme**: Captain prüft keine Übergabe ohne Gate, keine unbemerkte Änderung, Hash-Verifizierung, Provenienzpflicht, Eigentums-Check, Kette nachvollziehbar.

---

## 7. Offene Fragen (mit Vorschlag)

| Frage | Vorschlag | Begründung |
|---|---|---|
| F304-Q1: Artefakt-Kopie oder Referenz in Zielfabrik? | **Kopie** (lokal in Zielfabrik unter `empfangen/`). Referenz allein ist nicht nachweisbar, wenn Quellfabrik Artefakt löscht. | Nachweissicherheit im Evidence Store. |
| F304-Q2: Gate pro Fabrikpaar oder ein globales Gate? | **Fabrikspezifische Gates** (`artefakt_uebergabe_3d_webshop`, `artefakt_uebergabe_webshop_studio`). Kapitän kann pro Fabrikpaar entscheiden. | Feinere Kontrolle, verschiedene Risiken pro Übergang. |
| F304-Q3: Artefakt-Versionierung bei Änderung in Zielfabrik? | **Neues Artefakt** mit neuer Provenienz, referenziert vorheriges. Nie still ändern. | Nachvollziehbare Kette. |
| F304-Q4: Automatische Weitergabe bei Gate-Approve (Kette auto-forward)? | **Nein**, jeder Übergang braucht eigenes Captain-Gate. Kein Auto-Forward. | Kontrolle bei jeder Fabrikgrenze. |
| F304-Q5: Risiko-Schwellen für Gate (warn vs. fail)? | **Warn** → Gate wird angeboten, Captain sieht Warnung. **Fail** → Gate nicht angeboten, Build fehlgeschlagen. | Klare Trennung: Warnung = Hinweis, Fail = Stopp. |
| F304-Q6: Rückgabe-Kette bei Korrektur (zweiwege)? | **Ja**, Rückgabe-Übergabe mit eigenem Gate, referenziert Original. | Ermöglicht Korrektur ohne Kette zu brechen. |
| F304-Q7: Artefakt-Archivierung nach abgeschlossenem Kette? | **Ja**, Ketten nach Abschluss archivieren, nicht löschen. Nachweis bleibt erhalten. | Audit-Anforderung für Captain. |

---

## 8. Anforderungs-IDs (Zusammenfassung)

F304-01 bis F304-24 (24 Anforderungen).  
Offene Fragen: F304-Q1 bis F304-Q7 (7 Fragen).

---

## 9. Referenzen (nur Lesen)

- `runtime/src/sedra_runtime/evidence_store.py`: Runs, Benchmarks, Gate Evidence, Meta Insights (F2-03).
- `runtime/src/sedra_runtime/factory_registry.py`: Factory-Typen, Zustände, Gate-Freigabe (F2-01).
- `runtime/src/sedra_runtime/factory_builder.py`: Projekt/Modul/Service-Build, Templates (F2-02).
- `runtime/src/sedra_runtime/adapters/native/`: Native Workflow Steps für Artefaktkette.
- `runtime/src/sedra_runtime/adapters/hybrid/`: Hybrid Adapter für Artefaktkette (optional, Native + n8n).
- `runtime/docs/ADAPTERS.md`: Adapter-Dokumentation (Native, n8n, Hybrid).
- `docs/AUFTRAG_PAPERCLIP_3D_PIPELINE_2026-10-16.md`: Referenz-Pipeline (4-Rollen-Modell).
- `docs/SPEC_W3_DESKTOP_AENDERN_2026-11-14.md`: Form-Vorlage für diese Spec.
- `docs/SPEC_F3_02_3D_FACTORY_PILOT_2026-11-14.md`: 3D Factory Pilot (Quelle für 3D→Webshop-Übergabe).
- `docs/SPEC_F3_03_WEBSHOP_FACTORY_PILOT_2026-11-14.md`: Webshop Factory Pilot (Ziel für 3D→Webshop).

---

## 10. Implementierungshinweise (für späteren Auftrag, nicht Teil dieser Spec)

- Artefakt-Kopien liegen in Zielfabrik unter `empfangen/<artefakt_id>/`, nie direkt im Quellverzeichnis der Zielfabrik geschrieben.
- Jede Übergabe erzeugt einen neuen Evidence-Run mit `evidence_type: "artefakt_handover"`.
- Hash-Verifizierung erfolgt vor der Übernahme im Empfangsschritt, nicht erst im Gate.
- Keine Dateien mit `n8n` oder `workflow` im Namen werden von dieser Spec erzeugt oder geändert (siehe F-006).
- Der Captain entscheidet bei der Abnahme über die endgültige Gate-Konfiguration pro Fabrikpaar.
- Das `ablage`-Limit von 200 MB wird im Empfangsschritt geprüft, bevor das Artefakt übernommen wird.
- Rückgabe-Übergaben referenzieren das Original-Artefakt über `vorherige_artefakt_id`.
- Abgebrochene Ketten bleiben im Evidence Store als Nachweis und werden nicht gelöscht.
- Jede Fabrik darf nur Artefakte empfangen, für die sie eine Gate-Freigabe hat (Eigentums-Check).
- Provenienz-Felder (`erzeuger`, `erzeugt_am`, `build_id`, `run_id`) sind Pflichtfelder bei jeder Übergabe.
- Das `manifest_sha256` im Eigentumsblock bindet die Gewährung an die exakte Manifest-Version.
- Jede Fabrik darf nur Artefakte an Fabriken senden, die im `policies`-Eintrag des Ziel-Typs aufgeführt sind.
- Die Kette darf maximal 10 Übergaben umfassen, bevor ein neuer Run angelegt werden muss.
- Artefakt-Typen sind fest vordefiniert (`3d_stl`, `3d_glb`, `katalog_html`, `evidence_pdf`), keine frei wählbaren Typen.
- Der `vorherige_artefakt_id`-Verweis darf niemals eine Zeitsprung-Rückwärtsreferenz erzeugen (Kausalität).
- Fabrik-Grenzen werden über die `fabrik_quelle`/`fabrik_ziel`-Felder im ArtefaktHandover erzwungen, nicht über Dateisystem-Pfade.
- Ein Artefakt darf nur einmal übergeben werden; Wiederholte Übergabe desselben Hashes wird abgelehnt.
- Empfangene Artefakte werden unter `empfangen/<artefakt_id>/` abgelegt, nicht im Quellverzeichnis der Zielfabrik überschrieben.
- Die `fabrik_quelle`/`fabrik_ziel`-Felder müssen im `artefakt_chain`-Factory-Type registriert sein (Eigentums-Check).
- Gate-Entscheidungen werden mit `reviewer` (Captain-Rolle) und `reviewed_at` (ISO8601) protokolliert.
- Keine automatische Replikation zwischen Fabriken ohne expliziten Übergabe-Schritt.

---

**Ende der Spec F3-04.**  
Kein Code geschrieben. Dokument liegt im Worktree `pi-a009` unter `docs/SPEC_F3_04_MULTI_FACTORY_ARTEFAKTKETTE_2026-11-14.md`.
