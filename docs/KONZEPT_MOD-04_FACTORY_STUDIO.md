# Konzept SEDRA-MOD-04 – Factory Studio (Mock)

| Feld | Wert |
|---|---|
| Auftrag | Auftrag v5 Coder 2, 06.11.2026: Konzept, **nur Dokument** |
| Basis | `e83d0af16bb92976edede808274db62b1717f8a2` (`origin/main`, enthält den Namenswechsel `7b6d560` und F0-05B `e83d0af`, Paket `sedra_runtime`) |
| Status MOD-04 | für Code und UI **gesperrt**; Vorbedingungen: IF-MOD-01 umgesetzt, Antwort von One Sedra K3 |
| Grundlagen | `docs/FACTORY_SDK_SPEC.md` (Spec), `docs/ENTWURF_MOD-04_SCHNITTSTELLEN.md`, `docs/IR_MOD-01_ENTWURF.md`, `docs/ABSTIMMUNG_K3_SITZUNGSROUTEN.md`, `docs/ANALYSE_MOD-03_SCHEMA_GEGENPROBE.md` |
| Herkunft | `NEW_AI_GENERATED`; Fundstellen `EXISTING_REUSE`, Pfade relativ zu `runtime/src/sedra_runtime/` auf `e83d0af` |

## 1. Zweck

Das Factory Studio zeigt dem Captain an einem durchgespielten Beispiel, wie ein Factory-Vorgang in One Sedra aussehen wird: vom Projekt über den Workflow und den Lauf bis zum Artefakt, zum Nachweis und zur Freigabe. Es ist ein **Mock**: Er führt nichts aus und erteilt nichts, damit Bedienfluss und Begriffe geprüft werden können, bevor ein Factory-Backend existiert.

Für wen: den Captain (Bedienfluss beurteilen, G2 für Factory vorbereiten), den Koordinator und den One-Sedra-Chat (Einbettung in die Shell). Die Factory-Coder nutzen ihn später als Abbild der SDK-Verträge.

Der Bedienfluss in einem Satz: **Projekt wählen → Workflow-Revision wählen → Lauf vorlegen → Freigabe abwarten → Schritte verfolgen → Ergebnis mit Artefakt und Nachweis ansehen.**

## 2. Bedienfluss

Jeder Schritt benennt das SDK-Objekt (Spec §3) und den Zustand, den der Mock zeigt. „Simulation“ heißt: Der Wert kommt aus festen Beispieldaten im Mock, nicht vom Server.

| # | Schritt | SDK-Objekt | Was der Mock zeigt | Quelle im Mock |
|---|---|---|---|---|
| 1 | Projekt wählen | **Project** (Spec §3.1) | Name, `status: ACTIVE`, Art der Quelle (`project_registry` oder `harness_projekt`) | Simulation (Standard); wahlweise vorhandene Projekte lesen (Frage F-1) |
| 2 | Workflow-Revision wählen | **Workflow** (Spec §3.2) | Name, Revision, `process_model`, `execution.executable` mit `reason`; ein Prozessmodell ist als „nicht ausführbar“ gekennzeichnet | Simulation; wahlweise vorhandene Workflows lesen |
| 3 | Lauf vorlegen | **Task/Run** (Spec §3.3) | neue Mission, Phase `READY` → `CAPTAIN_REVIEW`, ein Schritt `PENDING`; Hinweis: „Im Betrieb entstünde jetzt ein Gate, das du im Posteingang beantwortest.“ | nur Simulation |
| 4 | Freigabe | **Approval** (Spec §3.6) | Gate `status: pending`, Aktion `run_n8n_workflow`, Ziel, Risiken, `rollback_available`; danach wahlweise `resolved` mit `APPROVE_ONCE` oder `DENY` | nur Simulation; zwei Knöpfe „Simulation: angenommen / abgelehnt“, die **keine** Route rufen |
| 5 | Schritte verfolgen | **Task/Run** | Phase `EXECUTE`, Schritt `RUNNING` → `COMPLETED`; zusätzlich ein Vorführfall `RUNNING` mit `outcome: unknown` („Ausgang unbekannt, wird nicht wiederholt“, FC-6) | nur Simulation |
| 6 | Prüfen und Ergebnis | **Task/Run** | Phase `VERIFY` → `COMPLETE`, `result.qualification: ARTIFACT_ONLY`, `accepted: false`; Satz: „Artefakt vorhanden, keine fachliche Abnahme“ | nur Simulation |
| 7 | Artefakt ansehen | **Artifact** (Spec §3.4) | `artifact_id`, Pfad relativ zum Arbeitsbereich, `artifact_type: file`, SHA-256 | nur Simulation |
| 8 | Nachweis ansehen | **Evidence** (Spec §3.5) | Gegenstand (der Lauf), Quelle (`audit_event`), Aussage, `outcome`; zum Vergleich ein Nachweis `NOT_RUN` mit Begründung („zählt nicht als bestanden“, FC-8) | nur Simulation |
| 9 | Abgelehnt-Pfad | **Approval**, **Task/Run** | `DENY` → keine Ausführung; Lauf bleibt stehen oder wird beendet (`FAILED`, `status: closed`) | nur Simulation |

Die Beispieldaten folgen den gültigen Beispielen der Spec (`docs/factory_sdk/beispiele/*.gueltig.json`) und werden gegen die Schemata geprüft, bevor sie in den Mock kommen.

## 3. Objekte und Zustände

Nur Zustände aus der Spec. Was die Spec nicht kennt, zeigt der Mock nicht.

| Objekt | Zustände im Mock | Spec-Fundstelle | bewusst nicht gezeigt |
|---|---|---|---|
| Project | `ACTIVE` | §3.1, `project.schema.json` `status` | Archiv, Ende (L-P2: gibt es im Bestand nicht) |
| Workflow | `process_model` ja/nein; `execution.executable` ja/nein mit `reason`; Profil `n8n-local-data-v1` | §3.2 | Bearbeiten der Definition (bleibt in der App „n8n Workflows“) |
| Task/Run – Phase | `READY`, `CAPTAIN_REVIEW`, `EXECUTE`, `VERIFY`, `COMPLETE`, `FAILED` (Auswahl aus den 12 Phasen) | §3.3, `task_run.schema.json` `phase` | `CANDIDATE_REVIEW`, `REWORK` (gehören zur Selbstentwicklung bzw. Nacharbeit, nicht zum Factory-Grundfluss) |
| Task/Run – Status | `active`, `closed` | §3.3 `status` | `archived` (Archivieren ist eine Aufräumhandlung der Aufgaben-App) |
| Task/Run – Schritt | `PENDING`, `GATE`, `RUNNING`, `COMPLETED`, `FAILED`; `outcome` `known`/`unknown` | §3.3 `steps[].status`, FC-6 | `WAITING`, `BLOCKED` (Frage F-4) |
| Task/Run – Ergebnis | `qualification` `PENDING` → `ARTIFACT_ONLY`; `accepted: false` | §3.3 `result` | `PREPARED_NOT_TESTED`, `VERIFIED_INVENTORY` (andere Workflows) |
| Artifact | `active`, `artifact_type: file` | §3.4 | typisierte Artefakte (L-A1) |
| Evidence | `outcome` `PASS`, `NOT_RUN` (mit `reason`); Quelle `audit_event` | §3.5 | Quelle `development_evidence`, `trust_level` (Gegenprobe W-1, erst mit Spec 1.1.0) |
| Approval | `pending`; `resolved` mit `APPROVE_ONCE` oder `DENY`; `single_use: true` | §3.6 | der Einmal-Token (nie im Objekt, FC-10); Dauerfreigaben (L-G2) |

## 4. Schnittstellen

Ausführlich in `docs/ENTWURF_MOD-04_SCHNITTSTELLEN.md` §2–§4. Hier nur, was der Mock in der empfohlenen **Variante 3** (Klick-Mock ohne Server-Teil) braucht und was dafür heute fehlt.

| Bedarf | Weg | Fundstelle (`e83d0af`) | heute vorhanden? |
|---|---|---|---|
| Werkzeug im Start-Menü | Manifest `tool.yaml`: `kind: object`, `gruppe: arbeit`, `zweck: pruefung` (lädt nur mit Schalter `entwicklung`), `trust: CORE` | `desk/gateway.py:43` `ZWECK`, `:46` `GRUPPEN` | ja (Vertrag), Datei **nicht** angelegt |
| Objekttyp im Manifest | `handles` nur mit vorhandenen Typen, z. B. `[workflow]` | `desk/gateway.py:23–30` `OBJECT_TYPES`, `:164` | ja, für Variante 3 |
| eigener Objekttyp `factory` | Erweiterung in `MODULES` + Typ in `OBJECT_TYPES` | `desk/extensions.py:3`; `desk/gateway.py:23–30` | **fehlt: Z1 und Z2** (IF-MOD-01); nur für Variante 1 nötig |
| Projekte lesen (optional) | `POST /api/objects {type: project}` | `desk/builtin_kinds.py:158`, `desk/objects.py:162` | ja |
| Workflows und Läufe lesen (optional) | `POST /api/objects {type: workflow \| workflow_run}` | `workflows/desk.py:135`, `:149` | ja |
| Aufgaben lesen (optional) | `POST /api/objects {type: task}` | `desk/builtin_kinds.py:152`, `desk/objects.py:41` | ja (ohne Artefakte) |
| Entscheidungen lesen (optional) | `POST /api/objects {type: decision}` | `desk/builtin_kinds.py:157` | ja; **antworten nicht** |
| Aktualisierung | Ereignisse `task.changed`, `decision.answered` | wie `uix/tools/workflow/tool.yaml` | ja |
| Artefakte und Nachweise als Objekt | eigener Typ | – | **fehlt** (M-1, M-2 im Schnittstellenentwurf); im Mock nur simuliert |
| Verben mit Freigabe | Antragsart in `ARTEN` | `desk/freigabeklasse.py:20` | **fehlt: Z3** (IF-MOD-01); Variante 3 braucht keines |

**Nicht im Manifest:** `POST /api/harness/sitzungen` und `…/sitzungen/*` (K3 offen), `POST /api/decisions/answer`, `POST /api/actions` mit Wirkung. In Variante 3 ruft der Mock keine Route mit Wirkung.

## 5. Freigaben

### 5.1 Im Mock

**Keine.** Der Mock legt keine Mission an, erzeugt kein Gate und beantwortet keine Entscheidung. Die Knöpfe „Simulation: angenommen / abgelehnt“ ändern nur den Zustand im Browser und sind als Simulation beschriftet.

### 5.2 Im späteren Betrieb (Abbild für G2)

Welche Stellen des Bedienflusses heute schon eine Captain-Freigabe haben und wo eine neue Antragsart nötig wäre:

| Schritt im Fluss | Weg im Bestand | Antragsart / Route | Klasse | Fundstelle | Stand |
|---|---|---|---|---|---|
| 1 Projekt anlegen (Registry) | `ProjectRegistry.create` | Route `/api/project/create` | `N` (Handlung, kein Gate) | `desk/freigabeklasse.py:178` | vorhanden |
| 1 Ordner als Projekt aufnehmen (Harness) | Antrag | `request:harness_projekt` | **`H`** | `desk/freigabeklasse.py:31` (Zeile mit `request:harness_projekt`) | vorhanden |
| 2 Workflow speichern | `WorkflowStore.save`, Verb `speichern` | – | keine Freigabe (nur Audit `WORKFLOW_REVISION_SAVED`) | `workflows/desk.py:45` | vorhanden; ob das für Factory reicht: Frage F-3 |
| 2 Prozess-Entwurf durch SEDRA | Antrag | `request:harness_prozess` | **`H`** | `desk/freigabeklasse.py:25`, `harness/antraege.py:23` | vorhanden |
| 3–4 Lauf starten | Verb `starten` (`needs_gate=True`) → Missions-Gate `run_n8n_workflow` | Art `gate` | **`H`** | `workflows/desk.py:137`, `workflows/execution.py:30/35`, `desk/freigabeklasse.py:21` | vorhanden |
| 5 Ausführung | Einmal-Token über `guard.authorize` | – | (Folge von 3–4) | `core/guard.py:89 ff.`, `:119` | vorhanden; kein Wiederholen bei unbekanntem Ausgang (`core/step_journal.py:81`) |
| 6–8 Ergebnis, Artefakt, Nachweis | – | – | keine Freigabe | – | lesen genügt |
| 9 Artefakt übernehmen, veröffentlichen oder weitergeben | – | **neue Factory-Antragsart** | wäre **`H`** (Daten nach außen / in den Betrieb, vgl. `GRUND_H` `desk/freigabeklasse.py:101`) | – | **fehlt: Z3**; eigener Captain-Auftrag |

Für Factory-Schritte, die es heute nicht gibt (Übernahme eines Artefakts, Weitergabe an eine andere Factory, Veröffentlichung), braucht jede Art einen Eintrag in `desk/freigabeklasse.py`. Sonst schlägt `tests/test_freigabe_vollstaendig.py` fehl. Dieses Konzept legt **keine** Art fest, es nennt nur die Stellen.

## 6. Abgrenzung – was der Mock nicht tut

- **Keine echte Ausführung:** keine Mission, kein Schritt, kein Aufruf von n8n, kein Modell, kein Job.
- **Keine Freigabe:** kein Gate, kein Token, keine Antwort im Posteingang, keine neue Antragsart.
- **Keine Live-Publikation:** nichts wird veröffentlicht, hochgeladen, gepusht oder geteilt.
- **Keine Bestellung, keine Zahlung, keine Fremdaktion:** auch nicht als Platzhalter-Knopf mit Wirkung.
- **Keine Schreibzugriffe:** kein Speichern von Projekten, Workflows, Artefakten oder Nachweisen. Optional nur lesen über `POST /api/objects`.
- **Keine Harness-Sitzung:** keine Sitzungsrouten, kein Gespräch aus dem Mock (K3 offen).
- **Kein neues System:** keine eigene Shell, keine eigene Engine, kein eigener Speicher. Das Studio ist ein Werkzeug in One Sedra.
- **Keine Privatsprache:** keine Zustände außerhalb der Spec (§3).
- **Sichtbar als Mock:** ständige Kennzeichnung „Simulation – nichts wird ausgeführt“; Werkzeug nur mit Schalter `entwicklung` (`zweck: pruefung`).

## 7. Offene Fragen

**An den Koordinator / Captain:**

| Nr. | Frage | Vorschlag |
|---|---|---|
| F-1 | Darf der Mock vorhandene Projekte, Workflows und Läufe **lesen** (nur `POST /api/objects`), oder nur Simulation zeigen? | Standard nur Simulation; Lesemodus als Schalter im Mock, klar getrennt beschriftet |
| F-2 | L-P1: Welcher Projektbegriff gilt? Zeigt der Projektbrowser `ProjectRegistry`, Harness-Projekte oder beide? | bis zur Entscheidung nur Registry-Projekte, im Mock beide Arten als Beispiel |
| F-3 | Reicht „Workflow speichern ohne Freigabe“ für Factory-Workflows, oder soll eine Factory-Revision eine Freigabe brauchen? | heute keine; Entscheidung bei G2 |
| F-4 | Sollen `WAITING` und `BLOCKED` im Mock vorkommen (z. B. „n8n nicht eingerichtet“)? | ja, als zusätzlicher Vorführfall, wenn gewünscht |
| F-5 | G1 für MOD-04 als Variante 3 (Klick-Mock, nur Simulation, `zweck: pruefung`), mit Reservierung für einen neuen Ordner unter `uix/tools/`? | ja, nach K3-Antwort |
| F-6 | Welche Factory-Antragsarten (Schritt 9) sollen in den Captain-Auftrag Z3? | erst nach Spec 1.1.0 und F2-Planung |
| F-7 | Zwei integrierte Coder-2-Dokumente nennen noch den alten Paketnamen (`docs/ENTWURF_MOD-04_SCHNITTSTELLEN.md`, `docs/ANALYSE_MOD-03_LUECKEN_STAND_87ce2a6.md`, je eine Stelle). Nachführen als kleiner Auftrag? | ja, zusammen mit dem Text-Auftrag Spec 1.0.1 |

**An One Sedra K3 (über den Koordinator):**

| Nr. | Frage |
|---|---|
| K-1 | Gibt es Einwände gegen ein weiteres Werkzeug in der Gruppe `arbeit`, das nur mit dem Schalter `entwicklung` erscheint? |
| K-2 | Höchstens 8 Apps zugleich (`uix/shells/harness/arbeitsplatz.yaml`): Soll das Studio als App-Reiter öffnen oder in einer anderen Zone? |
| K-3 | Soll das Studio später eine Harness-Sitzung starten dürfen (wie „Von SEDRA entwerfen lassen“), oder gilt dafür der Weg aus der Antwort zu `docs/ABSTIMMUNG_K3_SITZUNGSROUTEN.md`? |
| K-4 | Darf das Studio die vorhandenen Zeichenbausteine `uix/ui/workflow-canvas.js` und `workflow-model.js` nur lesend nutzen, ohne sie zu ändern? |
