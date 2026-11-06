# ENTWURF – Schnittstellen, die SEDRA-MOD-04 (Factory-Studio-Mock) braucht

| Feld | Wert |
|---|---|
| Auftrag | Auftrag v4 Punkt 3: Vorbereitung MOD-04, **nur Entwurf** |
| Basis | `87ce2a65f4a8476976dfafa86f835cce5b68319a` (`origin/main`) |
| Status MOD-04 | **gesperrt** (Register). Vorbedingungen: IF-MOD-01 umgesetzt, Antwort von One Sedra K3 |
| Bezug | `docs/IR_MOD-01_ENTWURF.md` (Z1, Z2, Z3), `docs/ABSTIMMUNG_K3_SITZUNGSROUTEN.md`, `docs/FACTORY_SDK_SPEC.md`, `docs/BESTAND_MOD_01_APPS.md` |
| Herkunft | `NEW_AI_GENERATED`; Fundstellen `EXISTING_REUSE` |
| Was dieser Entwurf **nicht** ist | keine UI-Datei, keine Route, nichts unter `uix/tools/`, keine Reservierung |

## 1. Was MOD-04 zeigen soll (aus `02_ROADMAP/CODER_2_ARBEITSPAKETE.md`)

Projektbrowser, Workflow-Graph, Run-Monitor, Nachweise und Captain-Gates. Alles als Mock oder Prototyp, **nur mit Simulation**, innerhalb von One Sedra (kein eigenes Desktop-System). Mock und Produktiv müssen sichtbar getrennt sein.

## 2. Schnittstellen je Ansicht

| Ansicht | SDK-Objekt (Spec §3) | vorhandener Weg (`87ce2a6`) | reicht das? |
|---|---|---|---|
| Projektbrowser | Project | `POST /api/objects {type: project}`; Kind `project` (`desk/builtin_kinds.py:158`), Objektbau `desk/objects.py:162` | ja zum Lesen. Offen: L-P1, das Objekt nimmt `project_id` **oder** `name` als ID |
| Workflow-Graph | Workflow | `POST /api/objects {type: workflow}` (`workflows/desk.py:135`); Zeichnung mit den vorhandenen UI-Bausteinen `uix/ui/workflow-canvas.js` und `workflow-model.js`, nur benutzen | ja, nur lesend |
| Run-Monitor | Task/Run | `POST /api/objects {type: workflow_run}` (`workflows/desk.py:149`, liefert Schritte, `wait`, Artefakte); allgemein `task` (`desk/builtin_kinds.py:152`, `desk/objects.py:41`: Schritte und Fortschritt, **ohne** Artefakte) | ja für Workflow-Läufe; für andere Missionen fehlen Artefakte im Objekt |
| Artefakte | Artifact | **kein** Objekttyp `artifact` im Desk; nur als Feld `artifacts` in `workflow_run` | **nein** → Lücke M-1 |
| Nachweise | Evidence | **kein** Objekttyp; Quellen nur serverseitig (Audit, `verification`, `DevelopmentEvidenceStore`) | **nein** → Lücke M-2 |
| Captain-Gates | Approval | `GET /api/decisions` (`uix_server.py:3902`, nur lesen); Kind `decision` (`desk/builtin_kinds.py:157`); Antworten bleibt in der Shell (Posteingang) | ja zum Anzeigen. Das Studio **beantwortet keine** Entscheidung selbst |
| Aktualisierung | – | Ereignisse `task.changed`, `decision.answered` (wie `uix/tools/workflow/tool.yaml`) | ja |

## 3. Manifest-Anforderungen (nur beschrieben, keine Datei)

| Feld | Wert für den Mock | Regel / Fundstelle |
|---|---|---|
| `id` | z. B. `factory-studio` | `desk/registry.py` `MODULE_ID` `^[a-z0-9-]{2,40}$` |
| `kind` | `object` | `desk/gateway.py` `TOOL_KINDS` |
| `handles` | **Variante 3:** nur vorhandene Typen, z. B. `[workflow]`. **Variante 1:** `[factory]` | Paket-Werkzeuge nur mit Typen aus `OBJECT_TYPES` (`desk/gateway.py:23–30`, `:164`); `factory` braucht Z2 |
| `api` | `POST /api/objects`, `POST /api/actions` | Allowlist; **nicht** `POST /api/harness/sitzungen*` (K3 offen, `docs/ABSTIMMUNG_K3_SITZUNGSROUTEN.md`) |
| `events.listens` | `task.changed`, `decision.answered` | wie `workflow` |
| `gruppe` | `arbeit` | `desk/gateway.py:46` `GRUPPEN` |
| `zweck` | `pruefung`, solange es ein Mock ist | `desk/gateway.py` `ZWECK`: ein Prüfwerkzeug lädt nur mit dem Schalter `entwicklung` (SPEC_UIX_STUFE6 §2.2). Damit erscheint der Mock nicht im normalen Betrieb |
| `trust` | `CORE` (im Paket) | `desk/gateway.py:52` |
| Dateien | `tool.js` ≤ 400 Zeilen, kein eigenes `fetch`, kein `localStorage`, CSS unter `.t-<id>` | `uix/tools/_template/tool.js` |

## 4. Serverseite und gemeinsame Zeilen (Verweis auf IF-MOD-01)

| Bedarf | Stelle | IF-MOD-01 | Variante 3 (Mock ohne Server-Teil) | Variante 1 (mit Kind) |
|---|---|---|---|---|
| eigener Objekttyp `factory` (Liste und Einzelansicht der SDK-Objekte) | `desk/extensions.py:3` `MODULES` | **Z1** | nicht nötig | eine Zeile, vom Updater reserviert |
| Typ im Manifest erlaubt | `desk/gateway.py:23–30` `OBJECT_TYPES` | **Z2** | nicht nötig | eine Zeile; Name ohne `_` und `-` (Namensregel IF-MOD-01) |
| Verben mit Freigabe (z. B. „Lauf zur Freigabe vorlegen“) | `desk/freigabeklasse.py` `ARTEN` | **Z3** | nicht nötig: ein Mock legt nichts zur Freigabe vor | je Antragsart eine Zeile, **eigener Captain-Auftrag** |
| Simulation | – | – | Simulation nur im Browser aus festen Beispieldaten, z. B. `docs/factory_sdk/beispiele/*.gueltig.json` als Vorlage. Kein Server-Aufruf mit Wirkung | Simulation serverseitig im Kind, ohne Mission, ohne Gate |

**Empfehlung:** MOD-04 als **Variante 3** beginnen, als reines Klick-Mock. Es braucht weder Z1, Z2 noch Z3 und berührt keine gesperrte Datei. Lesen über vorhandene Typen (`project`, `workflow`, `workflow_run`, `task`, `decision`). Was dort fehlt (M-1, M-2), zeigt der Mock aus Beispieldaten und kennzeichnet es als „Simulation“. Variante 1 erst mit dem Adapter (MOD-03 L-X1).

## 5. Lücken für MOD-04

| Nr. | Lücke | Wirkung | Weg |
|---|---|---|---|
| M-1 | kein Desk-Objekttyp für Artefakte | Run-Monitor sieht Artefakte nur bei `workflow_run` | Variante 3: Simulation; später Kind über Z1/Z2 |
| M-2 | kein Desk-Objekttyp für Nachweise | Nachweis-Ansicht nur simuliert | wie M-1; Quelle `DevelopmentEvidenceStore` erst nach G2 (Gegenprobe W-1) |
| M-3 | Projektbegriff offen (L-P1) | Projektbrowser zeigt eventuell zwei Arten | G2-Entscheidung abwarten; Mock zeigt nur `ProjectRegistry`-Projekte |
| M-4 | K3-Antwort offen | Studio darf keine Harness-Sitzung starten | keine Sitzungsrouten im Manifest |
| M-5 | höchstens 8 Apps zugleich (`uix/shells/harness/arbeitsplatz.yaml`) | Studio plus n8n plus Szenario Studio belegen 3 | nur beobachten |

## 6. Vorbedingungen, bevor MOD-04 beginnen darf

1. IF-MOD-01 umgesetzt (Register: Variante 1 bestätigt; Z1/Z2 reserviert der Updater erst für MOD-04). Für Variante 3 reicht die Bestätigung, dass Z1/Z2 **nicht** gebraucht werden.
2. Antwort von One Sedra K3 zu den Sitzungsrouten.
3. Eigene Freigabe G1 für MOD-04 mit Dateireservierung für `runtime/src/guppi_runtime/uix/tools/factory-studio/` (neu). Den Ort und die Gruppe `uix/tools/` reserviert der Updater.
4. Abstimmung des Bedienflusses mit dem One-Sedra-Chat (C2-3).
