# BESTAND SEDRA-MOD-02 – n8n- und Workflow-Komponenten (nur lesend)

| Feld | Wert |
|---|---|
| Auftrag | SEDRA-MOD-02 (n8n-Workflow-Adapter Bestands-/Gap-Analyse) |
| Rolle | Coder 2 – Module & Apps |
| Datum | 06.11.2026 |
| Geprüfter Stand | **`2b13daa`** (lokaler `main`), Git-Bundle `sedra_main_2b13daa.bundle`, `git rev-parse HEAD` selbst geprüft, vollständige Historie |
| Erstprüfung | `20ef720` (Repo-ZIP, identisch mit `git archive 20ef720`); Delta `20ef720..2b13daa` im Inventarbereich siehe unten |
| Angefasste Dateien im Repo | keine |
| Herkunft dieses Textes | `NEW_AI_GENERATED` (Befunde aus dem Quellcode, Zitate = `EXISTING_REUSE`) |
| Status | `CODER_HANDOFF` (Lesebefund), Auftrag selbst bleibt `PLANNED` |

**Belegregel:** Jede Zeilenangabe gilt für `2b13daa`. `git diff 20ef720 2b13daa -- runtime/src/sedra_runtime/workflows` ist leer; das ganze Paket `workflows/` ist also unverändert. Im übrigen Inventarbereich ändert sich nur `desk/freigabeklasse.py` (+1 Zeile `request:harness_prozess`, Umbenennung der approve-Stelle in `cli.py`).

## 1. Kurzbefund

Es gibt bereits eine vollständige, gate-gebundene n8n-Anbindung. Sie ist kein Plan, sondern Code mit 83 grünen Tests:

- **Austausch (breit):** n8n-JSON verlustfrei lesen, prüfen und speichern, auch mit unbekannten Knoten.
- **Ausführung (eng):** Profil `n8n-local-data-v1` mit fünf Knotentypen, nur über eine lokale n8n-Instanz auf `127.0.0.1`, nur nach Captain-Gate, genau ein Versuch.
- **Prozessmodelle:** fachliche Abläufe im Notizfeld der n8n-Knoten. Sie sind nie ausführbar.
- **Zwei Apps auf einem Speicher:** „n8n Workflows“ (`workflow`) und „Szenario Studio“ (`scenario`).

Eine zweite Workflow-Engine, ein zweiter Parser oder ein eigener Freigabeweg wären Doppelungen. Jede Factory- oder Adapterarbeit (F2-04) setzt auf diesem Paket auf.

## 2. Modulinventar (CODE_VERIFIED auf `2b13daa`)

Paket: `runtime/src/sedra_runtime/workflows/` (989 Zeilen, 10 Dateien).

| Datei | Zweck | Wichtigste Stellen |
|---|---|---|
| `schema.py` | Austauschprüfung, nie Ausführungsrecht | `MAX_BYTES` 1 MB (Z. 8), `MAX_NODES` 256 (Z. 9), `VERSIONS` unterstützte Knoten (Z. 10), `strict_json` ohne doppelte Schlüssel/NaN (Z. 14), `validate` (Z. 31), `report` (Z. 79), `redacted` Weitergabekopie (Z. 94) |
| `store.py` | Revisionen, unveränderlich | `WorkflowStore` (Z. 14), Ablage `runtime_data/workflows/WF-<24 hex>/<000001>.json`, Symlinks abgewiesen (Z. 18 ff.), Integritäts- und Versionskette (`read`, Z. 31), optimistische Sperre `base_revision` + `exclusive(revision.lock)` (Z. 55, 67), Schreiben nur neu (`open('x')`, Z. 79) |
| `versions.py` | lesbare Unterschiede zwischen Revisionen, ohne Geheimwerte | `compare` (Z. 11) |
| `process.py` | Prozessmodell im Notizfeld (`SEDRA_PROCESS_V1`) | `PREFIX` (Z. 4), `has_process` (Z. 12), `metadata` (Z. 16), `summary` (Z. 38) |
| `policy.py` | geschlossenes Ausführungsprofil | `PROFILE = 'n8n-local-data-v1'` (Z. 7), `executable` (Z. 89): genau ein manueller Start, höchstens 32 aktive Knoten (Z. 115), azyklisch, alles erreichbar, keine Credentials/Retry/Options, Timeout 10 s (Z. 147); `assessment` (Z. 150) |
| `engine.py` | lokaler n8n-REST-Adapter | `configuration` aus `local_config/n8n.json`, nur `http://127.0.0.1:<1024–65535>` (Z. 17, 29); `LocalN8n` (Z. 53), Verbindung fest auf `127.0.0.1` (Z. 64); `run` (Z. 83): temporärer Webhook-Workflow, Anlegen → Aktivieren → Nachlesen und Vergleich → ein Aufruf → Deaktivieren/Löschen (Z. 125); Ausgang nach Auslösung bei Fehler `UNKNOWN_REMOTE_OUTCOME` (Z. 117) |
| `execution.py` | Handler im ControlMaster | `context` mit Bindung (Mission, Schritt, Plan-Revision, Digests, Guard-Regeln) (Z. 9); `execute` (Z. 23): Aktion `run_n8n_workflow` (Z. 30), Guard-BLOCK zählt, sonst Pflicht-Gate (Z. 35); Einmal-Marke `n8n-attempt.json` gegen Wiederholung (Z. 43); Ergebnis als Artefakt (Z. 56); Audit `N8N_EXECUTION_STARTED/FINISHED` |
| `desk.py` | Desk-Erweiterung (die Apps) | `register` (Z. 134): Kinds `workflow` (Z. 135), `scenario` (Z. 145), `workflow_run` (Z. 149); Verb `starten` mit `needs_gate=True` (Z. 137); `_start` legt eine Mission an und führt nur bis zum Gate (Z. 86) |
| `selbstabbild.py` | SEDRA-Abläufe als Prozessmodelle aus `runtime/config/selbstabbild.yaml` | `pruefen` (Z. 113), `abweichung` (Z. 141), `anlegen` (Z. 152), `entwurf` für den Antrag (Z. 177), `ENTWURF_PREFIX` (Z. 173) |
| `__init__.py` | Paketsatz | – |

### Einbindung außerhalb des Pakets

| Stelle | Datei:Zeile | Owner-Zone |
|---|---|---|
| Handler-Weiche `action == 'n8n_workflow'` | `modules/control.py:29` | Coder 1 (Kernnähe) |
| Machbarkeitsprüfung, Handlerliste | `feasibility.py:38`, `:40` | Coder 1 |
| Desk-Erweiterung geladen über | `desk/extensions.py:3` (`MODULES`) | geteilt, Updater koordiniert |
| Objekttypen `workflow`, `scenario` im Vertrag | `desk/gateway.py:29`, `:30` | geteilt |
| Prozess-Antrag durch SEDRA (`prozess_beantragen`) | `harness/antraege.py:23` (`KIND_PROZESS = 'harness_prozess'`), `:142`, `:159` | One-Sedra-Bereich, **nicht meiner**; die Antragsart ist auf `2b13daa` in `desk/freigabeklasse.py:25` als H eingeordnet (`9328f07`) |
| Werkzeugbeschreibung für das Modell | `harness/werkzeuge.py:96` | One Sedra |

### Oberfläche (nur gelesen, `uix/` gesperrt)

- Apps: `uix/tools/workflow/tool.yaml` („n8n Workflows“, v0.2.0, `handles: [workflow]`, `gruppe: arbeit`) und `uix/tools/scenario/tool.yaml` („Szenario Studio“, v0.2.0, `handles: [scenario]`).
- Editor in der gemeinsamen UI-Bibliothek: `uix/ui/workflow-*.js`, 11 Dateien, 1336 Zeilen (canvas, editor, ndv, model, process, process-view, extras, picker, dialog, icons, templates).
- Beide Manifeste erlauben `POST /api/harness/sitzungen` und `…/sitzungen/*`, also Gespräche aus der App. Das muss MOD-01 mit dem One-Sedra-Chat abgleichen.

### Konfiguration und Doku

- `runtime/config/n8n.example.json`: `enabled: false`, `base_url: http://127.0.0.1:5678`, `api_key_env: SEDRA_N8N_API_KEY`.
- `docs/N8N_WORKFLOW_APP.md` (Bedienung, Grenzen, Paketweg), `docs/N8N_VALIDATION.md` (Abnahme 1.22.2 vom 05.11.2026, Basis `d51083a`), `docs/PLAN_PROZESS_APPS_UIX.md`.
- Paketwerkzeuge: `runtime/benchmarks/package_n8n_update.py`, `verify_n8n_update.py`.

## 3. Sicherheitsgrenzen, die schon gelten

1. **Austausch ist kein Recht.** `validate`/`report` laufen bei jedem Knoten. Ausführbar ist nur, was `policy.executable` besteht (`schema.py` Satz in Z. 1, `policy.py:89`).
2. **Pflicht-Gate, das ein ALLOW nicht aufhebt.** Belegt durch `tests/test_n8n_missions.py` `test_allow_rule_cannot_remove_mandatory_gate`. Ein BLOCK des Guard zählt (`test_guard_block_is_authoritative`).
3. **Bindung am Gate:** Workflow-Digest, Eingabe-Digest, Profil, Konfiguration und Digest der Guard-Regeln (`execution.py:9 ff.`).
4. **Kein Wiederholen:** Marke `n8n-attempt.json` mit `open('x')` (`execution.py:43`). Ein Ausgang nach Auslösung bleibt `unknown` und wird nie automatisch wiederholt. Das passt zur Invariante `unknown/in_doubt` aus der Roadmap.
5. **Netz:** nur numerisches Loopback und kein API-Schlüssel in Dateien, nur die Umgebungsvariable (`engine.py:17–34`). Keine Redirects oder Proxys, Antwort höchstens 1 MB.
6. **Prozessmodelle sind nie ausführbar** (`policy.py`: `process_model_requires_implementation`).
7. **Revisionen sind unveränderlich** und über eine Hashkette verknüpft. Ein Änderungsgrund ist Pflicht bei Prozessmodellen (`store.py:55 ff.`).

## 4. Tests

Lauf auf `2b13daa` (und gleich auf `20ef720`) in einer isolierten Linux-Kopie (Python 3.13, ohne Browser-Bahn):

```
python benchmarks/run_tests.py workflow
7 Testdateien, Browser-Bahn ausgelassen: 2
83 Tests, 0 übersprungen, 0 rot, 12 s
```

| Datei | Inhalt | Ergebnis |
|---|---|---|
| `test_n8n_interchange.py` | Austausch, Grenzen, Redaktion | PASS (Teil der 83) |
| `test_n8n_engine.py` | Adapter gegen Testdoppel `EngineDouble(LocalN8n)` | PASS |
| `test_n8n_missions.py` | Gate, Guard-Vorrang, Desk-Registrierung | PASS |
| `test_process_versions.py` | Revisionen, Kette, Manipulation | PASS |
| `test_selbstabbild.py` | Selbstabbild gegen Quellen | PASS |
| `test_workflow_contract.py` | Vertrag (30 Methoden) | PASS |
| `test_pc_workflow.py` | Kandidatenübernahme (Test, Simulation, Rücknahme), 8 Methoden; liegt per Glob in der Gruppe, ist aber kein n8n-Test | PASS |
| `test_n8n_browser.py`, `test_process_browser.py` | Browser-Bahn | `NOT_RUN` (braucht `SEDRA_BROWSER=1` und einen Browser) |
| `test_harness_prozess_antrag.py` | Antrag durch SEDRA (Gruppe `harness`) | PASS im Desk-Lauf, siehe MOD-01 |
| `tests/n8n_model.test.cjs`, `workflow_ui.test.cjs` | Editorlogik (Node) | `NOT_RUN` |

**Grenze:** Es gibt keinen Lauf gegen eine echte n8n-Instanz. Das steht so auch in `docs/N8N_VALIDATION.md` („Grenzen“). Die Live-Versionskompatibilität ist unbelegt.

## 5. Gap-Analyse (WORKFLOW_GAP)

| # | Lücke | Wirkung | Vorschlag (keine Umsetzung) | Owner/Gate |
|---|---|---|---|---|
| G1 | Kein Live-Test gegen echtes n8n, keine Versionsmatrix | Adapter nur gegen Testdoppel belegt | dedizierte lokale Testinstanz mit protokollierter Version; Testplan als eigener Auftrag | Captain (Installation und Lauf) |
| G2 | Ausführungsprofil eng: 5 Knotentypen, keine HTTP-, Code- oder KI-Knoten | gewollt (Sicherheit) | jede Erweiterung als neues Profil `n8n-local-data-v2`, nicht `v1` aufweichen | Captain G1/G2 |
| G3 | Ein Lauf = eine Mission mit genau einem Schritt `N8N-1` (`desk.py:86 ff.`) | keine Mehrschritt-Pipelines aus Workflows | für Factory über den Missionsplan lösen, keine eigene Orchestrierung | MOD-03 / F2-04 |
| G4 | Ergebnis ist nur ein Artefakt `n8n-result.json`, Qualifikation `ARTIFACT_ONLY` | keine typisierten Artefakte und kein Nachweis über den fachlichen Erfolg | typisierte Artefakt- und Evidence-Hülle im Factory-SDK (MOD-03), Store bleibt | MOD-03 |
| G5 | Kein Import/Export-Endpunkt für Dateien außer über Desk-Verben (`importieren` = `_save`) | gewollt: keine Pfade vom Client | beibehalten | – |
| G6 | Redaktion findet Geheimnisse nur über Schlüsselnamen (`schema.py:94`, eigener Hinweis im Docstring) | Freitext-Geheimnisse bleiben | Hinweis beibehalten, ggf. Prüfschritt im Export-Dialog | Coder 2, später |
| G7 | Selbstabbild ist nur Darstellung, ohne Rückrichtung | gewollt | – | – |
| G8 | Neue Kinds oder Verben brauchen Einträge in geteilten Dateien (`desk/extensions.py`, `desk/gateway.py`, bei Gates `desk/freigabeklasse.py`) | Konfliktgefahr zwischen Codern | siehe MOD-01 §5, Interface-Request | Updater/Captain |

## 6. Adaptervertrag (WORKFLOW_ADAPTER_KONTRAKT, Ist-Stand)

Wer künftig Workflows nutzt (Factory, F2-04), spricht **nur** diese Wege an:

| Zweck | Weg | Gate |
|---|---|---|
| lesen, auflisten | `POST /api/objects {type: workflow, id: <WF-…>|alle}` | nein |
| prüfen | `POST /api/actions {type: workflow, verb: pruefen, args: {text|workflow}}` | nein |
| speichern, neue Revision | Verb `speichern` / `importieren` mit `base_revision`, `change_note` | nein (Audit `WORKFLOW_REVISION_SAVED`) |
| Historie, Vergleich | Verben `versionen`, `vergleichen`, `revision_lesen` | nein |
| ausführen | Verb `starten {revision, inputs}` → Mission → Gate `run_n8n_workflow` → `workflow_run` `fortsetzen` | **ja**, Captain |
| Lauf lesen | `POST /api/objects {type: workflow_run, id: <Mission>}` | nein |

Python-seitig wiederverwendbar ohne Desk: `WorkflowStore`, `schema.validate/report`, `policy.assessment`, `process.summary`, `versions.compare`. **`LocalN8n.run` nie direkt aufrufen.** Der einzige Weg zur Ausführung ist der Missionsschritt `action: n8n_workflow` über `execution.execute`.

## 7. Risiken

- `2b13daa` ist nicht gepusht. Wird vor der Integration noch etwas auf `main` gelegt, muss der Diff für `workflows/` erneut leer sein.
- Die Apps erlauben Harness-Sitzungsrouten. Bei Änderungen am One-Sedra-Chat ist ein Abgleich nötig.

## 8. Fehlende Freigaben

- Captain: ob eine echte n8n-Testinstanz für G1 vorgesehen ist (Download und Lauf nur mit Ja).
- Captain: G1 für MOD-03, bevor die Adapterhülle (G3, G4) spezifiziert wird.
