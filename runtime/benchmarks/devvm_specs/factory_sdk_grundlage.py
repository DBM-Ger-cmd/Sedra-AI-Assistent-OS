"""Bau-Spec factory_sdk_grundlage v3: 4 Stufen mit Regeln aus den Schemata. Format: STAGES wie in devvm_build.py."""

NOTES = '''# Notizen factory_sdk
Nur Python-Standardbibliothek. Kein Dateizugriff, kein Netz, keine Ausführung von Inhalten.
Fehler sind ValueError mit Feld `code` (nicht leer) und `field` (Feldname oder "").
Keine übergebenen Objekte verändern (kopieren, wenn nötig).
Regeln: docs/FACTORY_SDK_SPEC.md Abschnitt 6 (fail-closed FC-1 bis FC-10).
Unbekannte Statuswerte werden abgelehnt, nicht ignoriert.
'''

TASK_S1 = '''Lege das Paket factory_sdk an. common.py: Fehlerklasse FabrikFehler(ValueError) mit code und field, Hilfsfunktionen für Pflichtfelder, Aufzählungen und Muster, abgeleitet aus docs/factory_sdk/schemas/common.schema.json.
projekt.py: pruefe_project(daten) nach project.schema.json. workflow.py: pruefe_workflow(daten) nach workflow.schema.json; ein Prozessmodell mit execution.executable=true wird abgelehnt.
Nur diese Dateien anlegen. Keine Tests.

Regeln (verbindlich, aus den Schemata; nichts davon weglassen oder erweitern):
# Regeln project (aus project.schema.json)
Pflichtfelder: ['backing', 'display_name', 'kind', 'schema_version', 'status']
Zusätzliche Felder erlaubt: False
  - PFLICHT schema_version: genau: "1.0.0"; Typ: string; SemVer des Vertrags. Diese Fassung kennt nur 1.0.0; ein anderer Wert wird abgewiesen (fail-closed).
  - PFLICHT kind: genau: "factory.project"
  - PFLICHT backing
    eine von diesen Formen (jede ist ein eigenes Objekt):
      Form 1:
        Pflichtfelder: ['created_at', 'project_id', 'qualification', 'store', 'workspace_path']
        Zusätzliche Felder erlaubt: False
          - PFLICHT store: genau: "project_registry"
          - PFLICHT project_id: Typ: string; Muster: ^PRJ-[0-9a-f]{12}$
          - PFLICHT workspace_path: Typ: string; Muster: ^projects/PRJ-[0-9a-f]{12}$
          - PFLICHT qualification: genau: "MANAGED_WORKSPACE_NOT_VM"
          - PFLICHT created_at: Typ: string; Muster: ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?\\+00:00$; UTC-Zeit wie core/util.py utcnow() (datetime.isoformat mit +00:00).
      Form 2:
        Pflichtfelder: ['project_id', 'store']
        Zusätzliche Felder erlaubt: False
          - PFLICHT store: genau: "harness_projekt"
          - PFLICHT project_id: Typ: string; Muster: ^[a-z0-9][a-z0-9-]{0,39}$
  - PFLICHT display_name: Typ: string; maximal 80 Zeichen
  - PFLICHT status: erlaubt: "ACTIVE"; Nur der Wert, den ProjectRegistry.create heute schreibt. Weitere Zustaende (Archiv) gibt es im Bestand nicht (Luecke L-P2).

# Regeln workflow (aus workflow.schema.json)
Pflichtfelder: ['digest', 'execution', 'kind', 'name', 'process_model', 'record_digest', 'revision', 'schema_version', 'workflow_id']
Zusätzliche Felder erlaubt: False
  - PFLICHT schema_version: genau: "1.0.0"; Typ: string; SemVer des Vertrags. Diese Fassung kennt nur 1.0.0; ein anderer Wert wird abgewiesen (fail-closed).
  - PFLICHT kind: genau: "factory.workflow"
  - PFLICHT workflow_id: Typ: string; Muster: ^WF-[a-f0-9]{24}$
  - PFLICHT revision: Typ: integer
  - PFLICHT digest: Typ: string; Muster: ^[0-9a-f]{64}$; SHA-256 als Hex in Kleinbuchstaben (core/util.py sha256_file, core/request_binding.py digest).
  - PFLICHT record_digest: Typ: string; Muster: ^[0-9a-f]{64}$; SHA-256 als Hex in Kleinbuchstaben (core/util.py sha256_file, core/request_binding.py digest).
  - optional previous_revision: Typ: integer oder null
  - PFLICHT name: Typ: string; maximal 200 Zeichen
  - optional change_note: Typ: string; maximal 500 Zeichen
  - PFLICHT process_model: Typ: boolean; true, wenn ein Knoten Prozess-Metadaten SEDRA_PROCESS_V1 traegt (workflows/process.py has_process). Ein Prozessmodell ist nie ausfuehrbar.
  - PFLICHT execution: Typ: object
    verschachtelt:
      Pflichtfelder: ['executable', 'profile', 'reason']
      Zusätzliche Felder erlaubt: False
        - PFLICHT executable: Typ: boolean
        - PFLICHT profile: genau: "n8n-local-data-v1"
        - PFLICHT reason: Typ: string oder null; maximal 200 Zeichen
'''

TASK_S2 = '''Ergänze factory_sdk/task_run.py: pruefe_task_run(daten) nach task_run.schema.json. Ein Lauf im Status RUNNING ohne outcome wird abgelehnt (FC-6). Nur diese Datei.

Regeln (verbindlich, aus dem Schema):
# Regeln task_run (aus task_run.schema.json)
Pflichtfelder: ['kind', 'mission_id', 'phase', 'project_refs', 'result', 'schema_version', 'status', 'steps']
Zusätzliche Felder erlaubt: False
  - PFLICHT schema_version: genau: "1.0.0"; Typ: string; SemVer des Vertrags. Diese Fassung kennt nur 1.0.0; ein anderer Wert wird abgewiesen (fail-closed).
  - PFLICHT kind: genau: "factory.task_run"
  - PFLICHT mission_id: Typ: string; Muster: ^M-[A-Za-z0-9_-]{1,64}$
  - PFLICHT phase: erlaubt: "NEW", "UNDERSTAND", "PLAN", "READY", "EXECUTE", "VERIFY", "CANDIDATE_REVIEW", "REWORK", "CAPTAIN_REVIEW", "PAUSED", "COMPLETE", "FAILED"; Schluessel von core/mission.py ALLOWED.
  - PFLICHT status: erlaubt: "active", "closed", "archived"
  - PFLICHT project_refs: Typ: array; Aus mission.context.refs (uix_server.py setzt {project_id, workspace_path}). Leer, wenn die Mission an kein Projekt gebunden ist.
  - optional workflow_ref: Typ: object; Aus mission.context.n8n_workflow; fehlt bei Missionen ohne Workflow.
    verschachtelt:
      Pflichtfelder: ['digest', 'revision', 'workflow_id']
      Zusätzliche Felder erlaubt: False
        - PFLICHT workflow_id: Typ: string; Muster: ^WF-[a-f0-9]{24}$
        - PFLICHT revision: Typ: integer
        - PFLICHT digest: Typ: string; Muster: ^[0-9a-f]{64}$; SHA-256 als Hex in Kleinbuchstaben (core/util.py sha256_file, core/request_binding.py digest).
  - PFLICHT steps: Typ: array; Aus mission.execution.step_journal.steps; 0 Eintraege, solange das Journal fehlt. Hoechstens 32 (step_journal.py plan_steps).
  - PFLICHT result: Typ: object; Aus mission.result (core/mission.py new_mission, core/brain.py Phase VERIFY).
    verschachtelt:
      Pflichtfelder: ['accepted', 'qualification']
      Zusätzliche Felder erlaubt: False
        - PFLICHT qualification: erlaubt: "PENDING", "ARTIFACT_ONLY", "PREPARED_NOT_TESTED", "VERIFIED_INVENTORY"
        - PFLICHT accepted: Typ: boolean
        - optional tests_executed: Typ: boolean
'''

TASK_S3 = '''Ergänze factory_sdk/artifact.py: pruefe_artifact(daten) nach artifact.schema.json; ein Pfad mit ".." wird abgelehnt (FC-9). factory_sdk/evidence.py: pruefe_evidence(daten) nach evidence.schema.json; NOT_RUN ohne Begründung wird abgelehnt (FC-8). Nur diese Dateien.

Regeln (verbindlich, aus den Schemata):
# Regeln artifact (aus artifact.schema.json)
Pflichtfelder: ['artifact_id', 'artifact_type', 'integrity', 'kind', 'mission_id', 'path', 'provenance', 'schema_version', 'status']
Zusätzliche Felder erlaubt: False
  - PFLICHT schema_version: genau: "1.0.0"; Typ: string; SemVer des Vertrags. Diese Fassung kennt nur 1.0.0; ein anderer Wert wird abgewiesen (fail-closed).
  - PFLICHT kind: genau: "factory.artifact"
  - PFLICHT artifact_id: Typ: string; Muster: ^ART-[0-9A-F]{8}$
  - PFLICHT mission_id: Typ: string; Muster: ^M-[A-Za-z0-9_-]{1,64}$
  - PFLICHT path: Typ: string; Muster: ^(?![A-Za-z]:)(?!/)(?!.*\\\\)(?!(.*/)?\\.\\.(/|$)).+$; maximal 400 Zeichen; Pfad relativ zum Arbeitsbereich: kein fuehrender Schraegstrich, kein Laufwerksbuchstabe, kein Backslash, kein '..'-Segment.
  - PFLICHT artifact_type: genau: "file"
  - PFLICHT integrity: Typ: object
    verschachtelt:
      Pflichtfelder: ['algorithm', 'hash']
      Zusätzliche Felder erlaubt: False
        - PFLICHT algorithm: genau: "sha256"
        - PFLICHT hash: Typ: string; Muster: ^[0-9a-f]{64}$; SHA-256 als Hex in Kleinbuchstaben (core/util.py sha256_file, core/request_binding.py digest).
  - PFLICHT provenance: Typ: object
    verschachtelt:
      Pflichtfelder: ['created_at', 'created_by', 'source_component']
      Zusätzliche Felder erlaubt: False
        - PFLICHT created_by: genau: "system"
        - PFLICHT source_component: Typ: string; Muster: ^[a-z][a-z0-9_.:-]{0,63}$
        - PFLICHT created_at: Typ: string; Muster: ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?\\+00:00$; UTC-Zeit wie core/util.py utcnow() (datetime.isoformat mit +00:00).
  - PFLICHT status: genau: "active"
  - optional job_id: Typ: string; maximal 80 Zeichen; Wie im Store auf oberster Ebene; nur bei Artefakten aus dem Job-System vorhanden.

# Regeln evidence (aus evidence.schema.json)
Pflichtfelder: ['claim', 'evidence_digest', 'kind', 'outcome', 'recorded_at', 'schema_version', 'source', 'subject']
Zusätzliche Felder erlaubt: False
  - PFLICHT schema_version: genau: "1.0.0"; Typ: string; SemVer des Vertrags. Diese Fassung kennt nur 1.0.0; ein anderer Wert wird abgewiesen (fail-closed).
  - PFLICHT kind: genau: "factory.evidence"
  - PFLICHT evidence_digest: Typ: string; Muster: ^[0-9a-f]{64}$; digest() ueber das Objekt ohne dieses Feld. Wer liest, rechnet nach; Abweichung = ungueltig.
  - PFLICHT subject: Typ: object
    verschachtelt:
      Pflichtfelder: ['id', 'kind']
      Zusätzliche Felder erlaubt: False
        - PFLICHT kind: erlaubt: "factory.task_run", "factory.artifact", "factory.workflow"
        - PFLICHT id: Typ: string; maximal 80 Zeichen
        - optional revision: Typ: integer
  - PFLICHT source
    eine von diesen Formen (jede ist ein eigenes Objekt):
      Form 1:
        Pflichtfelder: ['event_hash', 'event_id', 'type']
        Zusätzliche Felder erlaubt: False
          - PFLICHT type: genau: "audit_event"
          - PFLICHT event_id: Typ: string; Muster: ^EVT-[0-9]{6,}$
          - PFLICHT event_hash: Typ: string; Muster: ^[0-9a-f]{64}$; SHA-256 als Hex in Kleinbuchstaben (core/util.py sha256_file, core/request_binding.py digest).
      Form 2:
        Pflichtfelder: ['index', 'mission_id', 'type']
        Zusätzliche Felder erlaubt: False
          - PFLICHT type: genau: "verification"
          - PFLICHT mission_id: Typ: string; Muster: ^M-[A-Za-z0-9_-]{1,64}$
          - PFLICHT index: Typ: integer
      Form 3:
        Pflichtfelder: ['artifact_id', 'hash', 'type']
        Zusätzliche Felder erlaubt: False
          - PFLICHT type: genau: "test_report"
          - PFLICHT artifact_id: Typ: string; Muster: ^ART-[0-9A-F]{8}$
          - PFLICHT hash: Typ: string; Muster: ^[0-9a-f]{64}$; SHA-256 als Hex in Kleinbuchstaben (core/util.py sha256_file, core/request_binding.py digest).
  - PFLICHT claim: Typ: string; maximal 500 Zeichen
  - PFLICHT outcome: erlaubt: "PASS", "FAIL", "SKIPPED", "NOT_RUN", "BLOCKED"; Ergebnisbegriffe aus 03_PROZESS/TESTS_UND_ABNAHMEGATES.md. Nur PASS ist ein bestandener Nachweis; SKIPPED und NOT_RUN sind es nie.
  - optional reason: Typ: string; maximal 500 Zeichen
  - PFLICHT recorded_at: Typ: string; Muster: ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?\\+00:00$; UTC-Zeit wie core/util.py utcnow() (datetime.isoformat mit +00:00).
'''

TASK_S4 = '''Ergänze factory_sdk/approval.py: pruefe_approval(daten) nach approval.schema.json; token_id im Objekt wird abgelehnt (FC-10). Ergänze factory_sdk/__init__.py: exportiere alle sechs pruefe_* Funktionen und FabrikFehler.

Regeln (verbindlich, aus dem Schema):
# Regeln approval (aus approval.schema.json)
Pflichtfelder: ['action', 'decision', 'gate_id', 'kind', 'mission_id', 'request_digest', 'risks', 'rollback_available', 'schema_version', 'single_use', 'status', 'targets']
Zusätzliche Felder erlaubt: False
  - PFLICHT schema_version: genau: "1.0.0"; Typ: string; SemVer des Vertrags. Diese Fassung kennt nur 1.0.0; ein anderer Wert wird abgewiesen (fail-closed).
  - PFLICHT kind: genau: "factory.approval"
  - PFLICHT gate_id: Typ: string; Muster: ^HG-[0-9A-F]{8}$
  - PFLICHT mission_id: Typ: string; Muster: ^M-[A-Za-z0-9_-]{1,64}$
  - optional request_kind: Typ: string; Muster: ^[a-z][a-z0-9_]{1,39}$
  - PFLICHT action: Typ: string; Muster: ^[A-Za-z][A-Za-z0-9_]{1,63}$; gate.request.exact_action. Im Bestand klein (run_n8n_workflow, change_objective) und gross (HARNESS_PROZESS_ENTWURF).
  - PFLICHT targets: Typ: array
  - PFLICHT request_digest
    eine von diesen Formen (jede ist ein eigenes Objekt):
      Form 1:
        Pflichtfelder: []
        Zusätzliche Felder erlaubt: True
      Form 2:
        Pflichtfelder: []
        Zusätzliche Felder erlaubt: True
  - PFLICHT risks: Typ: array
  - PFLICHT rollback_available: Typ: boolean
  - PFLICHT status: erlaubt: "pending", "resolved"
  - PFLICHT decision: erlaubt: null, "APPROVE_ONCE", "DENY"
  - optional decided_at
    eine von diesen Formen (jede ist ein eigenes Objekt):
      Form 1:
        Pflichtfelder: []
        Zusätzliche Felder erlaubt: True
      Form 2:
        Pflichtfelder: []
        Zusätzliche Felder erlaubt: True
  - PFLICHT single_use: genau: true
'''

HIDDEN_S1 = '''import json
EXAMPLES = json.loads('{"project.gueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ACTIVE"}, "project.ungueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ARCHIVED"}, "workflow.gueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": false, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "workflow.ungueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": true, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "task_run.gueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "GATE", "attempts": 1, "outcome": "known"}], "result": {"qualification": "PENDING", "accepted": false}}, "task_run.ungueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "RUNNING", "attempts": 1}], "result": {"qualification": "PENDING", "accepted": false}}, "artifact.gueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "M-1A2B3C4D/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "artifact.ungueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "../M-9F9F9F9F/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "evidence.gueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "n8n-Lauf nach Freigabe genau einmal ausgelöst", "outcome": "PASS", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "8705ae7fba307117d0c18a765a24f6caf3d9a935544249381822608cf62988cd"}, "evidence.ungueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "Live-Lauf gegen echte n8n-Instanz", "outcome": "NOT_RUN", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "da7b2aafbbafb191244748003e38ca1aaa5d9ed07391de936855fa41ce84e2e4"}, "approval.gueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "pending", "decision": null, "decided_at": null, "single_use": true}, "approval.ungueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "resolved", "decision": "APPROVE_ONCE", "decided_at": "2026-11-06T11:40:12.345678+00:00", "single_use": true, "token_id": "APR-0BADF00D"}}')

# Abnahme S1 (versteckt). Gueltige Beispiele: keine Ausnahme. Ungueltige: ValueError mit code und field.
from factory_sdk import pruefe_project, pruefe_workflow, FabrikFehler
import copy
for name, fn in [("project", pruefe_project), ("workflow", pruefe_workflow)]:
    ok = EXAMPLES[name + ".gueltig"]
    fn(copy.deepcopy(ok))
    bad = EXAMPLES[name + ".ungueltig"]
    try:
        fn(copy.deepcopy(bad))
    except FabrikFehler as exc:
        assert exc.code and isinstance(exc.field, str), (name, exc.code)
    else:
        raise AssertionError(name + " ungueltig wurde angenommen")
print("ok S1")
'''

HIDDEN_S2 = '''import json
EXAMPLES = json.loads('{"project.gueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ACTIVE"}, "project.ungueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ARCHIVED"}, "workflow.gueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": false, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "workflow.ungueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": true, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "task_run.gueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "GATE", "attempts": 1, "outcome": "known"}], "result": {"qualification": "PENDING", "accepted": false}}, "task_run.ungueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "RUNNING", "attempts": 1}], "result": {"qualification": "PENDING", "accepted": false}}, "artifact.gueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "M-1A2B3C4D/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "artifact.ungueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "../M-9F9F9F9F/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "evidence.gueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "n8n-Lauf nach Freigabe genau einmal ausgelöst", "outcome": "PASS", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "8705ae7fba307117d0c18a765a24f6caf3d9a935544249381822608cf62988cd"}, "evidence.ungueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "Live-Lauf gegen echte n8n-Instanz", "outcome": "NOT_RUN", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "da7b2aafbbafb191244748003e38ca1aaa5d9ed07391de936855fa41ce84e2e4"}, "approval.gueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "pending", "decision": null, "decided_at": null, "single_use": true}, "approval.ungueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "resolved", "decision": "APPROVE_ONCE", "decided_at": "2026-11-06T11:40:12.345678+00:00", "single_use": true, "token_id": "APR-0BADF00D"}}')

from factory_sdk import pruefe_task_run, FabrikFehler
import copy
pruefe_task_run(copy.deepcopy(EXAMPLES["task_run.gueltig"]))
try:
    pruefe_task_run(copy.deepcopy(EXAMPLES["task_run.ungueltig"]))
except FabrikFehler as exc:
    assert exc.code
else:
    raise AssertionError("task_run ungueltig wurde angenommen")
print("ok S2")
'''

HIDDEN_S3 = '''import json
EXAMPLES = json.loads('{"project.gueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ACTIVE"}, "project.ungueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ARCHIVED"}, "workflow.gueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": false, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "workflow.ungueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": true, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "task_run.gueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "GATE", "attempts": 1, "outcome": "known"}], "result": {"qualification": "PENDING", "accepted": false}}, "task_run.ungueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "RUNNING", "attempts": 1}], "result": {"qualification": "PENDING", "accepted": false}}, "artifact.gueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "M-1A2B3C4D/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "artifact.ungueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "../M-9F9F9F9F/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "evidence.gueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "n8n-Lauf nach Freigabe genau einmal ausgelöst", "outcome": "PASS", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "8705ae7fba307117d0c18a765a24f6caf3d9a935544249381822608cf62988cd"}, "evidence.ungueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "Live-Lauf gegen echte n8n-Instanz", "outcome": "NOT_RUN", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "da7b2aafbbafb191244748003e38ca1aaa5d9ed07391de936855fa41ce84e2e4"}, "approval.gueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "pending", "decision": null, "decided_at": null, "single_use": true}, "approval.ungueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "resolved", "decision": "APPROVE_ONCE", "decided_at": "2026-11-06T11:40:12.345678+00:00", "single_use": true, "token_id": "APR-0BADF00D"}}')

from factory_sdk import pruefe_artifact, pruefe_evidence, FabrikFehler
import copy
for name, fn in [("artifact", pruefe_artifact), ("evidence", pruefe_evidence)]:
    fn(copy.deepcopy(EXAMPLES[name + ".gueltig"]))
    try:
        fn(copy.deepcopy(EXAMPLES[name + ".ungueltig"]))
    except FabrikFehler as exc:
        assert exc.code
    else:
        raise AssertionError(name + " ungueltig wurde angenommen")
print("ok S3")
'''

HIDDEN_S4 = '''import json
EXAMPLES = json.loads('{"project.gueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ACTIVE"}, "project.ungueltig": {"schema_version": "1.0.0", "kind": "factory.project", "backing": {"store": "project_registry", "project_id": "PRJ-3f9a1c2b7d4e", "workspace_path": "projects/PRJ-3f9a1c2b7d4e", "qualification": "MANAGED_WORKSPACE_NOT_VM", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "display_name": "Beispiel Software Factory", "status": "ARCHIVED"}, "workflow.gueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": false, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "workflow.ungueltig": {"schema_version": "1.0.0", "kind": "factory.workflow", "workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3", "record_digest": "8e4284462977901081a032495c0de1253dcd7fde585c6eeeaf82292ea4a382a5", "previous_revision": 1, "name": "Anfrage prüfen", "change_note": "IF-Bedingung ergänzt", "process_model": true, "execution": {"executable": true, "profile": "n8n-local-data-v1", "reason": null}}, "task_run.gueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "GATE", "attempts": 1, "outcome": "known"}], "result": {"qualification": "PENDING", "accepted": false}}, "task_run.ungueltig": {"schema_version": "1.0.0", "kind": "factory.task_run", "mission_id": "M-1A2B3C4D", "phase": "CAPTAIN_REVIEW", "status": "active", "project_refs": [{"project_id": "PRJ-3f9a1c2b7d4e"}], "workflow_ref": {"workflow_id": "WF-55cf1725549ddc93e4855595", "revision": 2, "digest": "068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"}, "steps": [{"step_id": "N8N-1", "status": "RUNNING", "attempts": 1}], "result": {"qualification": "PENDING", "accepted": false}}, "artifact.gueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "M-1A2B3C4D/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "artifact.ungueltig": {"schema_version": "1.0.0", "kind": "factory.artifact", "artifact_id": "ART-9C0FFEE1", "mission_id": "M-1A2B3C4D", "path": "../M-9F9F9F9F/n8n-result.json", "artifact_type": "file", "integrity": {"algorithm": "sha256", "hash": "454c30c8423b41114a22f00d2dd857b7116cee24cf0227e3b8b003b91d16bf91"}, "provenance": {"created_by": "system", "source_component": "workflows:n8n", "created_at": "2026-11-06T11:40:12.345678+00:00"}, "status": "active"}, "evidence.gueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "n8n-Lauf nach Freigabe genau einmal ausgelöst", "outcome": "PASS", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "8705ae7fba307117d0c18a765a24f6caf3d9a935544249381822608cf62988cd"}, "evidence.ungueltig": {"schema_version": "1.0.0", "kind": "factory.evidence", "subject": {"kind": "factory.task_run", "id": "M-1A2B3C4D"}, "source": {"type": "audit_event", "event_id": "EVT-004211", "event_hash": "d0844b3f61f934dab66ea59bcee18599463595abdaf4ed3608eda5dce1e51633"}, "claim": "Live-Lauf gegen echte n8n-Instanz", "outcome": "NOT_RUN", "recorded_at": "2026-11-06T11:40:12.345678+00:00", "evidence_digest": "da7b2aafbbafb191244748003e38ca1aaa5d9ed07391de936855fa41ce84e2e4"}, "approval.gueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "pending", "decision": null, "decided_at": null, "single_use": true}, "approval.ungueltig": {"schema_version": "1.0.0", "kind": "factory.approval", "gate_id": "HG-5E6F7A8B", "mission_id": "M-1A2B3C4D", "action": "run_n8n_workflow", "targets": ["http://127.0.0.1:5678/sedra-workflow/068f057d54567dadeb470598e469e7f6064d9e3ef69ccfd4c756f492098d8ad3"], "request_digest": "80f70afeef3caa57646fd20afb95be9c3f2c03d38e091906de31838813dcc22e", "risks": ["Lokale n8n-Testinstanz; nur Datenprofil v1, keine Außenaktionen."], "rollback_available": false, "status": "resolved", "decision": "APPROVE_ONCE", "decided_at": "2026-11-06T11:40:12.345678+00:00", "single_use": true, "token_id": "APR-0BADF00D"}}')

from factory_sdk import pruefe_approval, FabrikFehler
import copy, factory_sdk
for f in ["pruefe_project", "pruefe_workflow", "pruefe_task_run", "pruefe_artifact", "pruefe_evidence", "pruefe_approval", "FabrikFehler"]:
    assert hasattr(factory_sdk, f), f
pruefe_approval(copy.deepcopy(EXAMPLES["approval.gueltig"]))
try:
    pruefe_approval(copy.deepcopy(EXAMPLES["approval.ungueltig"]))
except FabrikFehler as exc:
    assert exc.code
else:
    raise AssertionError("approval ungueltig wurde angenommen")
print("ok S4")
'''

STAGES = [
    {"name": "S1", "task": TASK_S1, "hidden": {"hidden_factory_s1.py": HIDDEN_S1}},
    {"name": "S2", "task": TASK_S2, "hidden": {"hidden_factory_s2.py": HIDDEN_S2}},
    {"name": "S3", "task": TASK_S3, "hidden": {"hidden_factory_s3.py": HIDDEN_S3}},
    {"name": "S4", "task": TASK_S4, "hidden": {"hidden_factory_s4.py": HIDDEN_S4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_factory_s1.py": HIDDEN_S1}
