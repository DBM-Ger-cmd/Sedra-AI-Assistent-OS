# BESTAND SEDRA-MOD-01 – One Sedra App-/Desk-Verträge (nur lesend)

| Feld | Wert |
|---|---|
| Auftrag | SEDRA-MOD-01 (One Sedra App-Verträge inventarisieren) |
| Rolle | Coder 2 – Module & Apps |
| Datum | 06.11.2026 |
| Geprüfter Stand | **`2b13daa`** (lokaler `main`), Git-Bundle `sedra_main_2b13daa.bundle`, `git rev-parse HEAD` selbst geprüft, vollständige Historie |
| Erstprüfung | `20ef720` (Repo-ZIP, identisch mit `git archive 20ef720`) |
| Angefasste Dateien im Repo | keine; `uix/shells/harness/` und `uix/ui/` wurden nur gelesen |
| Herkunft | `NEW_AI_GENERATED` (Befund), Zitate `EXISTING_REUSE` |
| Status | `CODER_HANDOFF` (Lesebefund), Auftrag bleibt `PLANNED` |

Alle Zeilenangaben gelten für `2b13daa`. Das Delta `20ef720..2b13daa` im Inventarbereich steht in §7.

## 1. Kurzbefund

Eine „App“ in One Sedra ist ein **Werkzeug nach dem Shell-/Werkzeug-Vertrag v1** (`docs/SHELL_WERKZEUG_VERTRAG_v1.md`). Die Host-Shell `harness` (Anzeigename „One Sedra“) zeigt sie im Start-Menü und öffnet sie als Reiter. Ein eigenes App-SDK gibt es nicht. Der Vertrag hat vier Teile, die schon existieren:

1. **Manifest und Dateien** (`tool.yaml`, `tool.js`, `tool.css`), geprüft in `desk/gateway.py`.
2. **Objektmodell und Verben** über `POST /api/objects` und `POST /api/actions`, registriert in `desk/kinds.py`.
3. **Freigabe** über `desk/gated.py` (Antrag → Gate → Einmal-Token → Anwenden), eingeordnet in `desk/freigabeklasse.py`.
4. **Einbau fremder Apps** über das Install-Gate (`desk/install.py`) mit Vertrauensrang.

Eine neue Hauptshell oder ein eigenes App-Framework wären Doppelungen. Neue Apps (z. B. Factory Studio, MOD-04) sind Werkzeuge in diesem Vertrag.

## 2. App-Vertrag Ist-Stand (APP_KONTRAKTE)

### 2.1 Clientseite – Werkzeug

| Element | Beleg | Regel |
|---|---|---|
| Ordner | `runtime/src/guppi_runtime/uix/tools/<id>/` (Paket, `CORE`) oder `local_config/tools/<id>/` (installiert) | Vertrag §2; `desk/registry.py:17` (`UIX_DIR`), `:19` (`MODULE_ID` `^[a-z0-9-]{2,40}$`) |
| Manifest-Schlüssel | `desk/gateway.py:65` `TOOL_KEYS` | `id, name, version, handles, kind, entry, api, events, trust, tests, needs, description, order, slot, instanzen, gedaechtnis, zweck, gruppe` |
| Schema (für Menschen/Editoren) | `uix/ui/schema/tool.schema.json` | entscheidend ist `gateway.py` (Docstring Z. 1 ff.) |
| Objekttypen (`handles`) | `desk/gateway.py:23–30` `OBJECT_TYPES` | Paket-Werkzeuge dürfen **nur** diese Typen nennen (`:164`, „im Paket gibt es keine Privatsprache“). Installierte dürfen eigene mitbringen. |
| Start-Menü-Gruppe | `desk/gateway.py:46` `GRUPPEN` | `arbeit, modelle, wissen, system, pruefung` |
| Vertrauensrang | `desk/gateway.py:52` `TRUST` | `CORE, CAPTAIN, GUPPI_BUILT, COMMUNITY`; `COMMUNITY` bekommt nur `GET` (Vertrag §6) |
| Routen ohne Manifest-Eintrag | `desk/gateway.py:50–51` | Arbeitsstand; Ablage nur mit `gedaechtnis: ablage` |
| API-Allowlist | Vertrag §6 | Kopf `X-SEDRA-Tool`, sonst 403 `tool_route_not_allowed` und Audit `UIX_TOOL_DENIED` |
| Lebenszyklus JS | `uix/tools/_template/tool.js` | nur `mount(el, ctx)` / `unmount()`; `ctx = {object, api, bus, tokens, shell, manifest}`; kein eigenes `fetch`, kein `localStorage`, kein `EventSource`; CSS nur unter `.t-<id>`; ≤ 400 Zeilen je Datei |
| Ehrliche Grenze | `desk/gateway.py` Docstring | Die Allowlist ist keine Sandbox. Gegen eigenes `fetch` schützen nur die Install-Prüfung und der Vertrauensrang. |

### 2.2 Host-Shell `harness` (nur gelesen)

- `uix/shells/harness/shell.yaml`: `id: harness`, `name: One Sedra` (seit 05.11.2026), `version: 1.9.0`, `provides: [seite, reiter, flaeche, eingabe, taskleiste]`, `umschalter: menue`.
- `uix/shells/harness/arbeitsplatz.yaml`: Apps öffnen als Reiter aus dem Start-Menü, **höchstens 8 Apps zugleich**, Nachweise rechts.
- Die Shell holt die Apps über `GET /api/uix/modules`, die Gruppe kommt aus dem Manifestfeld `gruppe` (Vertrag, Nachtrag 29.10.2026).
- `uix/shells/harness/` ist zwischen `20ef720` und `2b13daa` unverändert. `eaeb4d3` ändert nur `runtime/config/harness_laeufe.yaml` (Lauftyp `wissen_aufnahme`) und Wissen-Dateien. Dieser Bereich gehört dem One-Sedra-Chat (K3).

### 2.3 Serverseite – Objekttyp (Kind) und Verben

| Element | Beleg | Regel |
|---|---|---|
| Kind | `desk/kinds.py:1` | `Kind(name, title, read, listing, verbs, type_verbs, source, placeholder, own_actions, extra)` |
| Objektform | `desk/kinds.py:31` `SHAPE` | `type, id, title, state, summary, actions, links`; fehlt ein Schlüssel → `object_shape_invalid` |
| Registrierung | `desk/kinds.py:48` `register`, `:62` `freeze` | Name `[a-z][a-z0-9_]{1,31}`, doppelt → `kind_already_registered`, nach dem Start eingefroren |
| Laden der Erweiterungen | `desk/extensions.py:3` `MODULES`, `:13` `load` | **feste Liste im Code**: `orchestra_kinds`, `wissen.desk_wissen`, `workflows.desk`; ein Fehler setzt nur dieses Modul zurück (`DESK_KIND_REFUSED`) |
| Aufruf beim Start | `uix_server.py:159`, `:162` | `load` → `freeze`, danach kein neuer Typ über Anfragen |
| Verb | `desk/actions.py:16` `Verb(verb, label, run, needs_gate, when, confirm)` | ein Weg aus Gespräch, Werkzeug, Palette, CLI und MCP |
| Verb mit Freigabe | `desk/gated.py:58` `request`, `:85` `apply`, `:132` `decide`, `:35` `register_applier` | Antrag legt eine Mission mit Gate an, Bindung am Gate, Anwenden nur mit Einmal-Token |
| Externe Clients | Vertrag, Nachtrag Spec 0 R5 | `guppi objects/act`, `desk_mcp.py`; nur `POST /api/objects` und `/api/actions` |
| Referenz-Erweiterung | `workflows/desk.py:134` | Vorbild für eine App mit Kind, Typ-Verben und gated Verb (siehe MOD-02) |

### 2.4 Freigabeklassen (gesperrte Datei, nur gelesen)

- `desk/freigabeklasse.py`: `ARTEN` (Z. 20), `ROUTEN_SERVER` (Z. 130), `request:harness_prozess` = H (Z. 25, neu mit `9328f07`), `ROUTEN_HARNESS` (Z. 258), `HARNESS_WEGE` (Z. 290), `HARNESS_UNTERWEGE` (Z. 293), `APPROVE_STELLEN` (Z. 299).
- `harness/api.py:98` `WEG`, `:101` `GESCHUETZT` (Regex der Harness-Routen), unverändert seit `20ef720`.
- `tests/test_freigabe_vollstaendig.py` (17 Methoden) erzwingt: jede `approve`-Stelle, jede schreibende Route und **jede Antragsart aus `gated.request`** steht in `freigabeklasse.py`. Sonst schlägt der Test fehl.

**Folge für Coder 2:** Eine App, die ein Verb mit Freigabe oder eine neue Harness-Route braucht, kann ich nicht allein liefern. Der Eintrag in `freigabeklasse.py` ist gesperrt und braucht einen eigenen Captain-Auftrag (Anweisung vom 06.11.).

### 2.5 Einbau fremder Apps

- `desk/install.py`: liest den Ordner, SHA-256 je Datei (Z. 82), Textprüfung (Z. 100) auf `eval`/`new Function`, `fetch`/XHR, fremdes `import()`, `localStorage`, `document.write`/`innerHTML`. Ein Fund ist kein Urteil, er erscheint im Gate. Die Datei schreibt nichts.
- Weg: `POST /api/uix/install` → Gate `install_module` → `local_config/…` → `uix.yaml` (Vertrag §6).
- **Grenze:** Ein installiertes Werkzeug bringt **keinen Server-Code** mit. Kinds kommen nur aus `extensions.MODULES` im Paket. Eine installierte App nutzt also nur vorhandene Objekttypen und Verben.

## 3. Modulinventar (MODUL_INVENTAR)

| Modul | Pfad | Vertrag | Beleg-Test | Reife | Owner | Wiederverwenden/Gap |
|---|---|---|---|---|---|---|
| App-Gateway | `desk/gateway.py` | Manifest, Dateien, Allowlist | `test_desk_gateway.py` | CODE_VERIFIED | geteilt | wiederverwenden |
| Shell-/Werkzeug-Register | `desk/registry.py` | `local_config/uix.yaml` | `test_desk_*` | CODE_VERIFIED | geteilt | wiederverwenden |
| Objekttypen | `desk/kinds.py`, `builtin_kinds.py` | Kind/SHAPE/freeze | `test_desk_kinds.py`, `test_desk_objects.py` | CODE_VERIFIED | geteilt | wiederverwenden |
| Erweiterungen | `desk/extensions.py` | feste `MODULES` | `test_desk_kinds.py` (importiert `extensions`) | CODE_VERIFIED | Updater | **Gap A** (§5) |
| Verben | `desk/actions.py` | Verb | `test_desk_*` | CODE_VERIFIED | geteilt | wiederverwenden |
| Gated-Anträge | `desk/gated.py` | request/apply/decide | `test_desk_gated.py` | CODE_VERIFIED | geteilt | wiederverwenden |
| Freigabeklassen | `desk/freigabeklasse.py` | Klassen H/N/sonder | `test_freigabe_vollstaendig.py`, `test_freigabe_klasse.py` | CODE_VERIFIED (`9328f07`: +1 Antragsart) | **gesperrt** | **Gap B** (§5) |
| Install-Gate | `desk/install.py` | Scan, Hashes | `test_desk_install.py` | CODE_VERIFIED | geteilt | wiederverwenden |
| Entscheidungen | `desk/decisions.py` | eine Quelle | `test_desk_decisions.py` | CODE_VERIFIED | geteilt | wiederverwenden |
| Ereignisstrom | `desk/events.py` | SSE, `snapshot` je Erweiterung | `test_desk_events.py` | CODE_VERIFIED | geteilt | wiederverwenden |
| Host-Shell | `uix/shells/harness/` | shell.yaml 1.9.0 | `test_harness_*`, `test_uix_harness_*` | CODE_VERIFIED (gelesen) | One-Sedra-Chat | nur lesen |
| Werkzeugvorlage | `uix/tools/_template/` | mount/unmount | – | CODE_VERIFIED | Coder 2 | Startpunkt für neue Apps |
| App öffnen aus dem Chat | `harness` Werkzeug `app_oeffnen` | – | `test_harness_app_oeffnen.py` | CODE_VERIFIED | One Sedra | nur lesen |
| Artefakte | `artifacts.py:6` `ArtifactStore.register` (Z. 9) | – | – | CODE_VERIFIED | Coder 1 (Kern) | für MOD-03 |
| Projekte | `projects.py:5` `ProjectRegistry` | – | – | CODE_VERIFIED | Coder 1 | für MOD-03 |
| Audit | `core/audit.py:24` `AuditLog.append` (Z. 32) | – | – | CODE_VERIFIED | Coder 1 | für MOD-03 |
| Guard/Gates | `core/guard.py:76` `create_gate`, `:79` `approve`, `:119` `authorize` | Einmal-Token, Bindung | `test_runtime.py`, `test_permission_levels.py`, `test_guard_standing.py` (rufen `authorize`) | CODE_VERIFIED | Coder 1 | nur über `gated.py` nutzen |
| Factory-SDK | – | NOT_IMPLEMENTED | NONE | PROPOSED | Coder 2 | MOD-03 |

## 4. Tests (isolierte Linux-Kopie, Python 3.13)

```
python benchmarks/run_tests.py desk test_freigabe_vollstaendig test_freigabe_klasse \
       test_harness_app_oeffnen test_harness_prozess_antrag test_uix_vertrag11
```

| Stand | Ergebnis |
|---|---|
| **`2b13daa`** | **289 Tests, 0 übersprungen, 0 rot** |
| `20ef720` (Vergleich) | 289 Tests, 2 rot, beide in `test_freigabe_vollstaendig`: `request:harness_prozess` nicht eingeordnet und die approve-Stelle `cli.py:_execute_runtime_command` (Z. 342) nicht eingeordnet |

Damit ist belegt, dass `9328f07` genau diese zwei Lücken schließt. Das ist ein Hinweis für SEDRA-GATE-01 (GATE-01-3); die Sicherheitsprüfung GATE-01-1/2 bleibt beim Tester.

`NOT_RUN`: Gruppen `harness` und `uix` vollständig, Browser-Bahn, Windows. Grund: Lesearbeit, kein geänderter Code; Windows-Läufe macht der Tester.

## 5. Lücken (API_GAPS)

| # | Lücke | Wirkung | Vorschlag (keine Umsetzung) | Owner |
|---|---|---|---|---|
| A | Neue Kinds nur über eine Zeile in `desk/extensions.MODULES` (geteilte Datei) | Jede neue App mit Server-Teil berührt dieselbe Zeile → `CONFLICT_PENDING` zwischen Codern | Interface-Request: Updater reserviert die Zeile je Auftrag, oder Coder 1 spezifiziert einen Eintragspunkt (z. B. eine Liste je Paket). Entscheidung Captain/Coder 1. | Updater / Coder 1 |
| B | Jedes freigabepflichtige Verb braucht einen Eintrag in der gesperrten `freigabeklasse.py` | Factory-Apps (Gates sind Pflicht) sind ohne Captain-Auftrag nicht lieferbar | pro App ein eigener Captain-Auftrag „Freigabeklasse für <Antragsart>“; Coder 2 liefert die Antragsarten nur als Liste | Captain |
| C | Paket-Werkzeuge dürfen nur `OBJECT_TYPES` nennen (`gateway.py:23–30`, `:164`) | Neuer Objekttyp (z. B. `factory_project`) = Änderung in geteilter Datei | im selben Interface-Request wie A | Updater |
| D | Kein eigenes App-SDK, Doku verteilt auf den Vertrag und 6 Nachträge | Einstieg für neue Apps teuer | Kurzleitfaden „App in One Sedra“ als Doku (nur `docs/`, konfliktfrei) | Coder 2 |
| E | Installierte Apps bringen keinen Server-Code mit | gewollt (Sicherheit) | beibehalten; Factory-Apps kommen als `CORE` im Paket | – |
| F | Höchstens 8 Apps zugleich (`arbeitsplatz.yaml`) | Factory Studio + n8n + Wissen + … wird eng | nur beobachten | One Sedra |
| G | `workflow`/`scenario` erlauben `POST /api/harness/sitzungen*` | Kopplung an One-Sedra-Routen | im Abgleich mit dem One-Sedra-Chat klären, nicht selbst ändern | Koordinator |

## 6. Abgrenzung zum One-Sedra-Chat (K3 Wissen)

- Keine Datei unter `uix/shells/harness/` und `uix/ui/` geändert. Gelesen wurden `shell.yaml`, `arbeitsplatz.yaml` und die Dateiliste.
- `wissen/` und `uix/tools/wissen/` nur als Erweiterung in `MODULES` gesehen, nicht inventarisiert. Das gehört K3.
- Kein Widerspruch zu K3 gefunden. Lücke G ist ein Abstimmungspunkt für den Koordinator.

## 7. Delta `20ef720..2b13daa` im Inventarbereich (geprüft)

```bash
git diff --stat 20ef720 2b13daa -- runtime/src/guppi_runtime/desk runtime/src/guppi_runtime/harness/api.py \
    runtime/src/guppi_runtime/harness/antraege.py runtime/src/guppi_runtime/workflows \
    runtime/src/guppi_runtime/uix/shells/harness runtime/src/guppi_runtime/uix/tools/workflow \
    runtime/src/guppi_runtime/uix/tools/scenario runtime/src/guppi_runtime/uix/ui runtime/src/guppi_runtime/uix_server.py \
    runtime/src/guppi_runtime/modules/control.py runtime/src/guppi_runtime/feasibility.py runtime/src/guppi_runtime/core
```

Ergebnis: nur `desk/freigabeklasse.py` (+3/−2, `9328f07`) und `desk/orchestra_runner.py` (+16/−2, `2b13daa`, F0-05, Coder-1-Zone, nicht Teil dieses Inventars). Alle anderen Belege in §2, §3 und MOD-02 sind auf beiden Ständen gleich.

## 8. Empfehlung: höchstens zwei konfliktfreie nächste Arbeiten

1. **MOD-03 Factory-SDK-Spec (nur `docs/` und Schema-Dateien, kein Code).** Bausteine: Project (`projects.py`), Workflow (`WorkflowStore`), Task/Run (Mission + `workflow_run`), Artifact (`ArtifactStore`), Evidence (Audit + Testberichte), Approval (`gated.py` + Freigabeklasse). Sie mappt auf Vorhandenes und erfindet keinen zweiten Kern. **Braucht G1 des Captains.**
2. **Interface-Request IR-MOD-01 an Coder 1/Updater** zu den Lücken A und C (Registrierung neuer Kinds und Objekttypen ohne Zeilenkonflikt), dazu die Liste der Antragsarten für Lücke B. Reiner Text, berührt keinen Code.

Der Kurzleitfaden (Lücke D) ist ebenfalls konfliktfrei, aber nachrangig.
