# BESTAND_MOD_02_WORKFLOW.md

## n8n-Workflow-Adapter: Bestandsaufnahme & Gap-Analyse

**Datum:** 13.11.2026  
**Status:** IN_DEVELOPMENT / CODER_HANDOFF  
**Basis-Commit:** 74bf792 (SEDRA Main Branch)  
**Captain-Entscheidung:** 06.11.2026, bestätigt 13.11.2026  
**Updater-Reservierung:** Z4/Z5 (n8n-Workflow-Adapter Schnittstellen)

---

## 1. Kontext & Ziel

### 1.1 Ausgangslage
- F2-04: Native/n8n/Hybrid Adapters implementiert (Phase 1-5 complete)
- n8n Adapter (`src/sedra_runtime/adapters/n8n/n8n_adapter.py`) funktionsfähig
- Evidence Store Integration in allen 3 Adaptern aktiv
- MOD-02: Gap-Analyse für n8n-Workflow-Adapter mit Policy Integration

### 1.2 Ziel
- Bestandsaufnahme des aktuellen n8n Adapters
- Identifikation von Gaps gegenüber Requirements
- Policy Integration (Captain Gates) für n8n Workflows
- Reservierte Schnittstellen Z4/Z5 implementieren

---

## 2. Bestandsaufnahme (Ist-Zustand)

### 2.1 Implementierte Features (n8n Adapter)

| Feature | Status | Details |
|---------|--------|---------|
| **Parsing** | ✅ | n8n JSON → WorkflowSpec (Nodes, Connections, Credentials) |
| **Validation** | ✅ | Schema + Credentials Referenzen + Missing Name |
| **Dry Run** | ✅ | Duration-Schätzung pro Node-Type |
| **Execution** | ✅ | n8n CLI Subprocess (`n8n execute --workflow`) |
| **Export** | ✅ | n8n.json, JSON, YAML |
| **Evidence Store** | ✅ | Auto-Recording Runs (Start/End, Metrics) |
| **CLI Integration** | ✅ | `factory adapter parse|validate|dry-run|execute|export --adapter n8n` |

### 2.2 Unterstützte n8n Node Types (Duration Estimates)

| Node Type Pattern | Estimated Duration |
|-------------------|-------------------|
| `http*`, `webhook*` | 2000ms |
| `database*`, `sql*` | 1500ms |
| `transform*`, `function*` | 500ms |
| `if*`, `switch*` | 100ms |
| Default | 500ms |

### 2.3 Aktuelle CLI Commands (n8n)

```bash
# Adapter registrieren
sedra factory adapter register n8n

# Workflow parsen
sedra factory adapter parse workflow.json --adapter n8n

# Validieren
sedra factory adapter validate workflow.json --adapter n8n

# Dry Run
sedra factory adapter dry-run workflow.json --adapter n8n

# Ausführen
sedra factory adapter execute workflow.json --adapter n8n --timeout-ms 300000

# Export
sedra factory adapter export workflow.json --adapter n8n --format n8n.json
```

---

## 3. Requirements (Soll-Zustand)

### 3.1 Policy Integration (Captain Gates)

Basierend auf `docs/ADAPTERS.md` und MOD-02 Requirements:

| Policy Feature | Beschreibung | Priorität |
|----------------|--------------|-----------|
| **Step-Level Policies** | `policies: ["policy-id"]` pro n8n Node | HIGH |
| **Gate Callback** | Async Callback an Captain für Approval | HIGH |
| **Policy Registry** | Zentrale Policy-Definitionen | MEDIUM |
| **Audit Trail** | Policy Decisions im Evidence Store | MEDIUM |

### 3.2 Reservierte Schnittstellen (Z4/Z5)

| Interface | Beschreibung | Status |
|-----------|--------------|--------|
| **Z4: Policy Evaluation** | `evaluate_policy(policy_id, context)` → `approved|rejected|pending` | TO IMPLEMENT |
| **Z5: Policy Registry** | `register_policy(policy_def)`, `get_policy(policy_id)` | TO IMPLEMENT |

### 3.3 Advanced n8n Features (Gaps)

| Feature | Gap Beschreibung | Priorität |
|---------|------------------|-----------|
| **n8n API Execution** | REST API Alternative zu CLI | MEDIUM |
| **Credential Resolution** | Echte Credential Values aus n8n Credentials Store | HIGH |
| **Workflow Activation** | `active: true` Support für Production | MEDIUM |
| **Partial Execution** | Einzelne Nodes ausführen (Debug) | LOW |
| **Webhook Testing** | Mock Webhook Endpoints für Tests | MEDIUM |
| **Execution Streaming** | Real-time Logs/Progress via Callback | LOW |

---

## 4. Gap-Analyse Matrix

| Kategorie | Ist | Soll | Gap | Aufwand |
|-----------|-----|------|-----|---------|
| **Policy: Step-Level** | ❌ Nicht implementiert | `policies` Array pro Step | Neu | M |
| **Policy: Gate Callback** | ❌ Nicht implementiert | Async Captain Callback | Neu | M |
| **Policy: Registry (Z5)** | ❌ Nicht implementiert | Policy CRUD + Evaluation | Neu | L |
| **Policy: Evaluation (Z4)** | ❌ Nicht implementiert | Policy Decision Engine | Neu | L |
| **n8n API Execution** | ❌ Nur CLI | REST API Client | Neu | M |
| **Credential Resolution** | ⚠️ Nur Referenzen | Echte Values aus Store | Neu | M |
| **Evidence: Policy Metrics** | ⚠️ Basis Metrics | Policy Decision Tracking | Neu | S |
| **Webhook Testing** | ❌ Nicht implementiert | Mock Server | Neu | M |

**Legende:** S=Small (<1d), M=Medium (1-3d), L=Large (>3d)

---

## 5. Implementierungsplan

### Phase 1: Policy Core (Z4/Z5) — Week 1
1. **Policy Registry** (`src/sedra_runtime/policy/registry.py`)
   - `register_policy(policy_def: PolicyDefinition)`
   - `get_policy(policy_id: str) -> PolicyDefinition`
   - `list_policies() -> List[PolicyDefinition]`
   - Persistenz: `local_config/policies.json`

2. **Policy Evaluator** (`src/sedra_runtime/policy/evaluator.py`)
   - `evaluate_policy(policy_id: str, context: PolicyContext) -> PolicyDecision`
   - Captain Gate Callback Integration
   - Evidence Store Integration

3. **Policy Definition Schema**
   ```python
   @dataclass
   class PolicyDefinition:
       id: str
       name: str
       description: str
       severity: PolicySeverity  # low, medium, high, critical
       requires: List[str]  # roles, approvals
       evaluator: str  # "captain_gate" | "auto" | "script"
   ```

### Phase 2: n8n Adapter Policy Integration — Week 1-2
1. **Step-Level Policies** in n8n Adapter
   - `WorkflowStep.policies` Array unterstützen
   - Gate Check vor Node Execution

2. **Credential Resolution**
   - n8n Credentials Store Integration
   - Secure Credential Injection

3. **n8n API Client** (Alternative zu CLI)
   - REST API Wrapper
   - Async Execution Support

### Phase 3: Advanced Features — Week 2-3
1. **Webhook Mock Server** für Tests
2. **Execution Streaming** (Progress Callback)
3. **Partial Execution** (Debug Mode)

---

## 6. Dateireservierungen (Koordinator/Updater)

| Pfad | Reserviert für | Status |
|------|----------------|--------|
| `src/sedra_runtime/policy/` | Z4/Z5 - Policy Core | RESERVIERT (Updater bestätigt) |
| `src/sedra_runtime/adapters/n8n/n8n_adapter.py` | n8n Policy Integration | RESERVIERT |
| `local_config/policies.json` | Policy Persistenz | RESERVIERT |
| `docs/ADAPTERS.md` | Dokumentation | FREI |

---

## 7. Tests (Target Coverage)

| Test | Beschreibung |
|------|--------------|
| `test_policy_registry.py` | CRUD, Persistenz, Validation |
| `test_policy_evaluator.py` | Captain Gate, Auto-Policies, Evidence |
| `test_n8n_policy_integration.py` | Step Policies, Gate Callback, Credentials |
| `test_n8n_api_client.py` | REST API Execution, Auth |

---

## 8. Risiken & Mitigations

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| n8n CLI nicht verfügbar | Mittel | Hoch | Fallback: REST API, klarer Error |
| Captain Gate Timeout | Niedrig | Mittel | Default: Reject nach 5min |
| Credential Leak | Niedrig | Kritisch | Nur Referenzen, Resolution at Runtime |
| Policy Registry Performance | Niedrig | Mittel | Caching, Lazy Loading |

---

## 9. Nächste Schritte

1. ✅ F2-05 Task erstellt (Policy Integration & Production Hardening)
2. 🔄 **Policy Registry implementieren** (Z5)
3. 🔄 **Policy Evaluator implementieren** (Z4)
4. 🔄 **n8n Adapter Policy Integration**
5. 🔄 **Tests schreiben**
6. 🔄 **Dokumentation aktualisieren** (ADAPTERS.md)

---

## 10. Sign-off

| Rolle | Name | Datum | Status |
|-------|------|-------|--------|
| Captain | - | 06.11.2026 | ✅ Genehmigt |
| Koordinator | - | 13.11.2026 | ✅ Einordnung |
| Updater | - | 13.11.2026 | ✅ Reservierung Z4/Z5 |
| Coder 2 | - | 13.11.2026 | 🔄 CODER_HANDOFF |