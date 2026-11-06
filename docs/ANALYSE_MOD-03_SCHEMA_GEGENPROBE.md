# Analyse MOD-03 – Schema-Gegenprobe (Stand `87ce2a6`)

| Feld | Wert |
|---|---|
| Auftrag | SEDRA-MOD-03, Auftrag v4 Punkt 1 (nur lesen, nur `docs/`) |
| Basis | `87ce2a65f4a8476976dfafa86f835cce5b68319a` (`origin/main`) |
| Geprüft | `docs/FACTORY_SDK_SPEC.md`, `docs/factory_sdk/schemas/*.schema.json` (7), `docs/factory_sdk/beispiele/*.json` (12), wie mit `87ce2a6` integriert |
| Coder | Coder 2 |
| Herkunft | `NEW_AI_GENERATED`; Fundstellen `EXISTING_REUSE` (Datei:Zeile auf `87ce2a6`) |
| Spec geändert? | **nein**. Widersprüche und Schwächen sind unten beschrieben, nicht behoben |

## 1. Umgebung und Befehl

- Validator: `jsonschema` **4.26.0** mit `referencing` **0.37.0**, Python 3.13.18, Draft 2020-12.
- Umgebung: außerhalb des Repos. `jsonschema` war in der Arbeitsumgebung **vorinstalliert**. Eine Neuinstallation war nicht möglich, weil Paket-Downloads in dieser Umgebung gesperrt sind. Im Repo wurde nichts installiert und nichts angelegt.
- `$ref` werden nur über die sieben `$id` (`urn:sedra:factory-sdk:1:…`) aufgelöst. Es gibt keinen Abrufweg, also wird nichts nachgeladen.
- Prüfwerkzeug: ein eigenes Skript außerhalb des Repos (Wortlaut in der Abgabe, `ABGABE.md`). Es ist **unabhängig** vom Prüfskript der MOD-03-Abgabe: Es sammelt alle Fehler je Beispiel, nicht nur den ersten, und hat zwei zusätzliche Teile B und C.

```
python3 -I gegenprobe.py <repo-wurzel>        → Exit 0
git status --porcelain -uall                  → leer (vorher und nachher)
```

## 2. Teil A – Beispiele gegen ihr Schema

Erwarteter Grund je ungültigem Beispiel aus `FACTORY_SDK_SPEC.md` §6.

| Beispiel | erwartet | Grund laut Spec §6 | gefundene Fehler (alle) | Ergebnis |
|---|---|---|---|---|
| `project.gueltig.json` | gültig | – | 0 | OK |
| `project.ungueltig.json` | ungültig | `status: ARCHIVED` (FC-3) | `status` [enum] | OK, genau dieser Grund |
| `workflow.gueltig.json` | gültig | – | 0 | OK |
| `workflow.ungueltig.json` | ungültig | Prozessmodell als ausführbar | `execution/executable` [const] | OK, genau dieser Grund |
| `task_run.gueltig.json` | gültig | – | 0 | OK |
| `task_run.ungueltig.json` | ungültig | `RUNNING` ohne `outcome` (FC-6) | `steps/0` [required] | OK, genau dieser Grund |
| `artifact.gueltig.json` | gültig | – | 0 | OK |
| `artifact.ungueltig.json` | ungültig | Pfad mit `..` (FC-9) | `path` [pattern] | OK, genau dieser Grund |
| `evidence.gueltig.json` | gültig | – | 0 (Digest nachgerechnet, stimmt) | OK |
| `evidence.ungueltig.json` | ungültig | `NOT_RUN` ohne Begründung (FC-8) | `(wurzel)` [required] `reason` | OK, genau dieser Grund |
| `approval.gueltig.json` | gültig | – | 0 | OK |
| `approval.ungueltig.json` | ungültig | `token_id` im Objekt (FC-10) | `(wurzel)` [additionalProperties] **und** `(wurzel)` [not] | OK im Ergebnis, siehe S-3 |

**Ergebnis Teil A:** 12 von 12 wie erwartet. Jedes ungültige Beispiel scheitert aus dem Grund, den die Spec nennt.

## 3. Teil B – Enum-Listen gegen den Quellcode

| Liste im Schema | Quelle (`87ce2a6`) | Ergebnis |
|---|---|---|
| `task_run.phase` (12) | `core/mission.py:9` `ALLOWED` (Schlüssel) | gleich |
| `task_run.steps[].status` (7) | `core/step_journal.py:41` (PENDING), `:79 ff.` (RUNNING), `:88 ff.` `finish` (COMPLETED, GATE, WAITING, BLOCKED, FAILED) | gleich |
| `task_run.result.qualification` (4) | `core/mission.py:44` (PENDING), `core/brain.py:222` | gleich |
| `task_run.status` (3) | `core/mission.py` (`active`, `closed`), `uix_server.py:2306` (`archived`) | gleich |

## 4. Teil C – echte Datensätze aus dem Bestand

Der vorhandene Code wurde in einem Temp-Ordner **außerhalb** des Repos aufgerufen. Seine Datensätze wurden nach der Abbildung aus Spec §3 umgesetzt und gegen die Schemata geprüft. Das Repo blieb unverändert.

| Datensatz erzeugt von | SDK-Objekt | Ergebnis |
|---|---|---|
| `core/mission.py` `new_mission()` | Task/Run | gültig |
| `core/audit.py` `AuditLog.append()` | Evidence (`audit_event`) | gültig |
| `artifacts.py` `ArtifactStore.register()`, Pfad relativ umgerechnet | Artifact | gültig |
| dasselbe, Pfad **unverändert** aus dem Store (absolut) | Artifact | ungültig (`path`), bestätigt Lücke L-A2 |
| `workflows/store.py` `WorkflowStore.save()`, Revision 1 und 2, mit `policy.assessment`, `process.has_process` | Workflow | beide gültig |
| `core/guard.py` `create_gate()` (pending), `approve()` (APPROVE_ONCE), `reject()` (DENY, Aktion `HARNESS_PROZESS_ENTWURF`), Gate ohne Ziel und ohne Bindung | Approval | alle gültig |
| Approval mit `token_id` aus `approve()` | Approval | ungültig, wie gewollt |
| `projects.py` `ProjectRegistry.create()` (Dateiwerkzeug durch einen Ersatz im Temp-Ordner) | Project | gültig |

## 5. Befunde

### S-1 Workflow: `previous_revision` ist im Schema schwächer als im Store

- **Bestand:** `WorkflowStore.save` schreibt immer `previous_revision = revision − 1` (`workflows/store.py:74 ff.`, `latest`).
- **Schema:** Nur Revision 1 erzwingt `previous_revision: null`. Revision 2 mit `null` oder mit `5` ist gültig (Teil C, beide angenommen).
- **Spec:** §3.2 nennt nur die Regel für Revision 1. Das ist kein Widerspruch zur Spec, aber das Schema prüft weniger, als der Bestand garantiert.
- **Folge:** Ein falsch abgebildetes Objekt fällt nicht auf. Der Bezug `= revision − 1` ist in JSON Schema nicht ausdrückbar. Erzwingen lässt sich nur „ab Revision 2 nicht `null`“.
- **Vorschlag (nicht umgesetzt):** in Version 1.0.1 oder 1.1.0 `revision ≥ 2 ⇒ previous_revision` Pflicht und ganzzahlig. Die Gleichheit mit `revision − 1` prüft der Leser (wie FC-5).

### S-2 Approval: `APPROVE_ONCE` mit leerer Zielliste

- **Bestand:** `Guard._approve` weist eine leere Zielliste ab (`core/guard.py:89 ff.`, `approval_requires_explicit_gate_scope`; in Teil C bestätigt).
- **Schema:** `status: resolved`, `decision: APPROVE_ONCE`, `targets: []` ist gültig.
- **Folge:** Das Schema lässt einen Zustand zu, den es im Bestand nicht gibt. Gefährlich ist das nicht, weil das SDK-Objekt nichts freigibt (FC-7). Es ist aber ungenau.
- **Vorschlag (nicht umgesetzt):** `decision: APPROVE_ONCE ⇒ targets` mit `minItems: 1`.

### S-3 Approval: ein ungültiges Beispiel, zwei Schema-Fehler

- `approval.ungueltig.json` bricht inhaltlich genau eine Regel (FC-10). Im Schema schlagen aber zwei Schlüsselwörter an: `additionalProperties: false` (FC-2) und das ausdrückliche Verbot `not` / `required: token_id` (FC-10).
- Spec §6 sagt „bricht genau eine Regel“. Das stimmt für die Regel, nicht für die Zahl der Schema-Fehler. Die Doppelung ist gewollt: Das Token-Verbot bleibt bestehen, auch wenn eine spätere Fassung `additionalProperties` lockern sollte.
- **Vorschlag:** In Spec §6 einen Satz ergänzen, dass FC-10 doppelt abgesichert ist. Keine Schemaänderung.

### W-1 Widerspruch: Es gibt einen Nachweis-Speicher (Lücke L-E1 ist falsch formuliert)

- **Spec §3.5 und L-E1:** „Baustein: keiner als eigener Speicher“ und „Kein Nachweis-Speicher“.
- **Bestand:** `DevelopmentEvidenceStore` (`selfdev/development_evidence.py:9`) ist eine Hash-Kette mit Einträgen `EVD-…`. Ein Eintrag hat die Felder `evidence_type`, `job_id`, `candidate_id`, `source_ref`, `artifact_sha256`, `trust_level` (`observed`, `deterministic`, `model_assessment`, `human_review`, `external_unverified`), `payload`, `previous_evidence_hash`, `evidence_hash` (`:20–51`), dazu `verify_chain` (`:53`). Angelegt wird er in `runtime.py:182` unter `self_development/evidence.jsonl`. Genutzt wird er von `jobs/verification_gate.py` und `jobs/context_manager.py`.
- **Einordnung:** Der Speicher ist an **Jobs und Kandidaten der Selbstentwicklung** gebunden. Er hat kein `mission_id`. Für Factory-Nachweise zu einer Mission ist er heute nicht vorgesehen, aber er ist der naheliegende Baustein. Seine Vertrauensstufen trennen genau das, was die Factory braucht: deterministischen Beleg und Modellmeinung (`jobs/verification_gate.py`, Kopf: „A model's opinion is never deterministic evidence“).
- **Folge für v1:** Die drei Quellen (`audit_event`, `verification`, `test_report`) bleiben gültig. Es fehlt eine vierte Quelle `development_evidence` (`EVD-…` + `evidence_hash`) und ein Feld für die Vertrauensstufe.
- **Vorschlag (nicht umgesetzt):** L-E1 umformulieren in „Nachweis-Speicher vorhanden (Selbstentwicklung, job-/kandidatengebunden); Bindung an Missionen fehlt“. In Version 1.1.0 eine Quelle `development_evidence` und das optionale Feld `trust_level` mit den fünf Werten aus dem Bestand. Entscheidung bei G2.
- **Herkunft des Fehlers:** In der MOD-03-Arbeit habe ich nach einem Nachweis-Speicher nur unter `modules/` und `core/` gesucht, nicht unter `selfdev/` und `jobs/`. Die Gegenprobe hat das aufgedeckt.

## 6. Zusammenfassung

| Prüfung | Ergebnis |
|---|---|
| 7 Schemata gegen Metaschema | gültig |
| 12 Beispiele, Grund wie Spec §6 | 12/12 |
| 4 Enum-Listen gegen den Code | 4/4 gleich |
| Teil C: 15 Prüfungen mit echten Datensätzen | 12 wie erwartet, 3 als Befund (S-1 zweimal, S-2) |
| Befunde | S-1, S-2 (Schema schwächer als Bestand), S-3 (Doppelabsicherung, nur Text) |
| Widerspruch Spec ↔ Bestand | W-1 (Nachweis-Speicher vorhanden) |

Keine Datei der Spec oder der Schemata wurde geändert. Die Vorschläge zu S-1, S-2, S-3 und W-1 brauchen eine G2-Entscheidung und einen Auftrag.
