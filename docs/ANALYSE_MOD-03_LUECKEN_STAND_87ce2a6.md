# Analyse MOD-03 – Stand der Lücken auf `87ce2a6`

| Feld | Wert |
|---|---|
| Auftrag | SEDRA-MOD-03, Auftrag v4 Punkt 2 (nur `docs/`) |
| Basis | `87ce2a65f4a8476976dfafa86f835cce5b68319a` (`origin/main`) |
| Grundlage | Lückenliste `docs/FACTORY_SDK_SPEC.md` §5 (L-P1 bis L-X1), geschrieben auf `2b13daa` / `c6960fa` |
| Herkunft | `NEW_AI_GENERATED`; Fundstellen `EXISTING_REUSE` |
| Spec geändert? | nein |

## 1. Was sich seit der Spec auf `main` geändert hat

```
git log --oneline 2b13daa..87ce2a6
  87ce2a6 MOD-03: Factory-SDK-Spezifikation (Coder 2, Basis c6960fa)
  c6960fa Harness: Lauf-Typ selbsttest (Testbatterie mit Ergebnisdatei)
  4a3d401 MOD-01/02: Bestandsbefund und Entwuerfe (Coder 2, Basis 2b13daa)
  468d346 F0-05B: Spezifikation v2 und Race-Testentwurf (Coder 1, Basis 2b13daa)
git diff --stat 2b13daa 87ce2a6 -- runtime/src      → leer
```

Unter `runtime/src/` hat sich nichts geändert. **Keine Lücke ist durch neuen Code geschlossen.** Was sich verschoben hat, sind Entscheidungen und Aufträge (IF-MOD-01 gestellt, F0-05B mit G3), dazu ein Fehler in der Lückenliste selbst (L-E1, siehe Gegenprobe W-1).

## 2. Lücke für Lücke

| Nr. | Lücke (Spec §5) | Befund auf `87ce2a6` | Schließbar heute? | Was es bräuchte |
|---|---|---|---|---|
| L-P1 | Zwei Projektbegriffe | unverändert: `ProjectRegistry` (`projects.py:5`) und Harness-Projekte (`harness/projekte.py:22`). Das Desk-Objekt `project` nimmt `project_id` **oder** `name` als ID (`desk/objects.py:162`) | **nein, Entscheidung offen** | Captain-/G2-Entscheidung; danach Spec 1.1.0 mit nur einem `backing` |
| L-P2 | Projekt nur `ACTIVE` | unverändert (`projects.py:19`) | nein | eigener Auftrag an den Owner der Registry, nur falls die Factory ein Projektende braucht |
| L-W1 | Workflow ohne Projektbezug | unverändert: der Store hängt am SEDRA-Projekt (`workflows/store.py:15–16`) | **ja, ohne Code**, als Abbildungsregel | Spec-Satz: Projektbezug eines Workflows nur über die Mission (`context.refs`), nie im Store. Braucht G2 |
| L-T1 | `accepted` fehlt vor VERIFY | unverändert (`core/mission.py:44`) | **ja, ist bereits geschlossen** durch die Abbildungsregel in Spec §3.3 (`false`); in der Gegenprobe Teil C bestätigt | nichts; kann aus §5 gestrichen werden |
| L-T2 | Workflow-Lauf = ein Schritt `N8N-1` | unverändert (`workflows/desk.py:104`) | nein | F2-02 (Pipeline als Missionsplan) |
| L-A1 | Artefakte nur `file` | unverändert (`artifacts.py:14`) | nein | F2, Minor-Version |
| L-A2 | Store-Pfad absolut | unverändert (`artifacts.py:14`, `str(path)`); in der Gegenprobe Teil C bestätigt | nein im Store; **Abbildungsregel ist belegt** (relativ zu `control.workspace`) | Adapter (L-X1) |
| L-E1 | „Kein Nachweis-Speicher“ | **falsch formuliert**: `DevelopmentEvidenceStore` existiert (`selfdev/development_evidence.py:9`, `runtime.py:182`), aber nur für Jobs und Kandidaten | **teilweise**: Baustein vorhanden, Mission-Bindung fehlt | Spec-Korrektur (Text) + 1.1.0 mit Quelle `development_evidence` und `trust_level`; G2 |
| L-G1 | Keine Factory-Antragsarten | unverändert: kein `factory` in `desk/freigabeklasse.py` | nein | Captain-Auftrag Z3 aus IF-MOD-01, erst wenn MOD-04/F2 die Liste der Arten festlegt |
| L-G2 | `standing` nicht abgebildet | unverändert (`desk/gated.py:30`) | bewusst nicht | – |
| L-R1 | Kein Factory-Modul-Register | unverändert. Einziger Bezug: Platzhalter `"factory": {"state": "NOT_EVALUATED", "reason": "factory_acceptance_required"}` in `runtime.py:146` (`_readiness_from_boot`) | nein | F2-01 |
| L-X1 | Kein Adapter Bestand → SDK | unverändert; IF-MOD-01 ist gestellt (Variante 1), Z1/Z2 reserviert der Updater erst für MOD-04 | nein | G3-Auftrag für den Adapter; Ort `docs/` reicht nicht, braucht `runtime/` (Reservierung) |

**Zusammenfassung:**

| Stand | Lücken |
|---|---|
| bereits geschlossen (Abbildungsregel) | L-T1 |
| ohne Code schließbar (Spec-Satz, braucht G2) | L-W1 |
| Text der Spec falsch, korrigieren | L-E1 |
| offen, Entscheidung nötig | L-P1 |
| offen, eigener Auftrag oder späterer Meilenstein | L-P2, L-T2, L-A1, L-A2, L-G1, L-R1, L-X1 |
| bewusst ausgelassen | L-G2 |

## 3. Neue Punkte seit der Spec

| Nr. | Punkt | Beleg | Wirkung auf das SDK |
|---|---|---|---|
| N-1 | **Namenswechsel `guppi_runtime` → `sedra_runtime`** (SEDRA-NAME-01, `AWAITING_CAPTAIN`, Register) | Branch `guppi-raus` laut Register; auf GitHub **nicht** vorhanden (`git ls-remote`), auf `main` gilt `guppi_runtime` | Die Spec nennt Fundstellen relativ zum Paket (`projects.py`, `core/guard.py` …). Sie bleibt nach dem Umbenennen lesbar, wenn das Paket nur den Namen wechselt. Den vollen Pfad `runtime/src/guppi_runtime/…` nennen: die `description` von `artifact.schema.json`, `project.schema.json` und `workflow.schema.json` (je eine Stelle, keine Formregel) sowie `docs/BESTAND_MOD_01_APPS.md`, `docs/BESTAND_MOD_02_WORKFLOW.md` und `docs/IR_MOD-01_ENTWURF.md` (Kennung in `desk/extensions.py` `MODULES`: `"guppi_runtime.workflows.desk"`). Diese Analysen nennen den Pfad nur hier. Vorschlag: nach NAME-01 ein kleiner Auftrag zum Nachführen dieser Stellen; Zeilennummern erneut prüfen, falls NAME-01 Zeilen verschiebt |
| N-2 | Gegenprobe-Befunde S-1, S-2 | `docs/ANALYSE_MOD-03_SCHEMA_GEGENPROBE.md` §5 | Schema schwächer als Bestand; Vorschlag Version 1.0.1/1.1.0 |
| N-3 | F0-05B in Entwicklung (Coder 1, `desk/orchestra_runner.py`, `jobs/`, `orchestra/service.py`) | Register, G3 vom 06.11. | keine: das SDK liest Missionen, nicht das Job-System. Ändert F0-05B Schrittstatus oder Phasen, muss Teil B der Gegenprobe erneut laufen |

## 4. Empfohlene Reihenfolge (keine Umsetzung)

1. G2-Entscheidung L-P1 (Projektbegriff).
2. Ein kleiner Text-Auftrag für Spec 1.0.1: L-E1 umformulieren, L-T1 streichen, L-W1 als Regel aufnehmen, Hinweis zu S-3. Ohne Formänderung, Schemata bleiben 1.0.0.
3. Spec 1.1.0 mit Formänderung erst zusammen mit dem Adapter (L-X1): S-1, S-2, Quelle `development_evidence`, `trust_level`.
4. Nach NAME-01: Pfade in den Coder-2-Dokumenten nachführen (N-1).
