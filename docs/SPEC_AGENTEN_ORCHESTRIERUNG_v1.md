# SEDRA Agenten-Orchestrierung – Spezifikation v1

Stand 20.10.2026 · Entscheidungen des Captains eingearbeitet · Fach-Spec für den spec-getriebenen Ablauf

## Zweck und Arbeitsweise

Dieses Dokument ist die Arbeitsgrundlage für den Vorarbeiter: Es legt fest, was gebaut wird, bevor eine Zeile Code entsteht. Gearbeitet wird spec-getrieben. Jede Spec durchläuft drei Stufen, und jede Stufe endet mit einer Freigabe durch den Captain.

| Stufe | Ergebnis | Inhalt | Freigabe-Tor |
| --- | --- | --- | --- |
| 1 Anforderungen | Kapitel „Anforderungen“ der Fach-Spec | Was das System können muss, als prüfbare Aussagen | G1 – Captain gibt Anforderungen frei |
| 2 Design | Kapitel „Design“ der Fach-Spec | Wie es gebaut wird: Module, Schnittstellen, Datenmodell, Fehlerfälle | G2 – Captain gibt Design frei |
| 3 Aufgaben | Kapitel „Aufgaben“ + Bau-Specs | Kleine Bauschritte; je Schritt, den SEDRA baut, eine Bau-Spec mit versteckten Tests und grüner Referenz | G3 – Captain gibt Aufgaben frei |
| 4 Umsetzung | Kandidat + Tests + Logbuch | Bau durch SEDRA lokal (oder Harness durch Claude), Review Zeile für Zeile | G4 – Captain: Übernahme ja/nein |

Regeln für alle Specs:

- Anforderungen im EARS-Format: „WENN \<Auslöser\>, DANN SOLL \<System\> \<Reaktion\>.“ Jede Anforderung hat eine ID (z. B. ORC-03) und mindestens ein Abnahmekriterium.
- Keine Aufgabe ohne Anforderung, keine Anforderung ohne Abnahmekriterium.
- Wird beim Bauen eine Lücke in der Spec gefunden, wird zuerst die Spec geändert und neu freigegeben, dann weitergebaut.
- Ablage nach SEDRA-Konvention: Fach-Specs als `docs/SPEC_<THEMA>_v1.md` (wie `SPEC_EIN_SICHERER_WEG_v1.md`), Bau-Specs für SEDRA als `runtime/benchmarks/devvm_specs/<n>.py` mit Referenz in `devvm_refs/<n>/`, geprüft mit `spec_check.py` (Zeile `result ok`).
- Arbeitsteilung wie in `docs/ENTWICKLUNG.md`: KI-Sitzungen schreiben Specs, versteckte Tests, Referenzen und den Harness (Guard, Bridge, Suite-Mechanik); SEDRA schreibt den Produktionscode neuer Module lokal auf dem Rechner, unter Anleitung von Claude (Captain, 20.10.2026).
- Reihenfolge: Spec 0 (Kern) zuerst bis G2, weil alle anderen Specs auf der Kern-API aufsetzen. Danach können Spec 1 bis 4 parallel bis G1 laufen; gebaut wird Spec 1 vor Spec 2 (Captain, 20.10.2026).

![Reihenfolge der Specs: Spec 0 zuerst, dann Spec 1 bis 4 parallel bis G1, Spec 5 am Ende](SPEC_AGENTEN_ORCHESTRIERUNG_v1_reihenfolge.svg)

Spec 0 kommt allein zuerst, weil alle anderen auf der Kern-API aufsetzen; Spec 5 prüft am Ende alles zusammen.

## Steering: Ziel, Grundsätze, Begriffe

Ziel: SEDRA führt mehrere KI-Agenten gleichzeitig wie ein kleines Team – nach dem Vorbild von Paperclip – und der Captain steuert sie über die Paperclip-Shell (Shell D) im Desk. Der Kern bleibt Python und bekommt keine neuen Rechte.

### Zielbild in fünf Punkten

1. Ein Kern für viele Anwendungsfälle: Alles läuft über das Objektmodell und die Verben des Desk (`desk/objects.py`, `desk/actions.py`), nicht über Spezialrouten.
2. Orchestrierung nach Paperclip-Vorbild: Agenten mit Rolle und Vorgesetztem, Aufgaben mit atomarem Checkout, Herzschlag-Wecken, Budgets, Routinen.
3. Parallele Agenten: Die GPU-Lease wird vom „ein Prozess lädt“ zu „ein Modellserver, mehrere Slots, ein Scheduler verteilt“ weiterentwickelt.
4. Local First, Cloud Second: lokal ist Standard, Cloud nur über Router, Inhaltsschutz und GateWay, sichtbar und budgetiert.
5. Die Paperclip-Shell (D) ist die Arbeitsfläche dafür und hält den Shell-Werkzeug-Vertrag ein.
6. Eine Social- und Nachrichten-Zentrale verwaltet LinkedIn- und Facebook-Konten, plant und postet Beiträge und ist erweiterbar für Instagram, WhatsApp und den E-Mail-Eingang, immer mit Freigabe des Captains (Spec 6).

### Grundsätze (aus SEDRA, ergänzt)

| Grundsatz | Bedeutung für dieses Vorhaben |
| --- | --- |
| Captain First | Jedes Gate einzeln per ID; eine Freigabe gilt nicht für den nächsten Zusammenhang |
| Local First, Cloud Second (neu) | Cloud nur als zweite Stufe, nie still; ersetzt das bisherige „kein Wechsel auf Cloud“ erst nach Freigabe und Doku-Änderung |
| Plan Before Code | Keine Zeile Code vor G2 der jeweiligen Spec |
| Candidate Before Stable | Neues entsteht als Kandidat unter `runtime_data/devvm_candidates/` |
| Verify Before Accept | Richter ist der versteckte Test, nicht das Modell |
| Least Privilege | Selbstentwicklung erzeugt keine neuen Rechte; Werkzeuge nur mit API-Allowlist |
| Reversible Change | Jede Übernahme rücknehmbar; Konfiguration nur mit `*.bak-<datum>-<grund>` |
| Kern geschützt | `guppi_runtime/core/` (Stufe E3) nur mit ausdrücklicher Freigabe je Änderung; `test_core_boundary_src` bleibt grün |

### Begriffe

| Begriff | Bedeutung |
| --- | --- |
| Captain | Der Mensch, der jedes Gate entscheidet |
| Vorarbeiter | KI-Sitzung (Claude), die Specs schreibt, Arbeit verteilt, SEDRA beim Bauen anleitet und dem Captain berichtet |
| Agent | Instanz einer Vorlage aus dem Agent Manager, mit Rolle, Rezept und Vorgesetztem |
| Aufgabe (`task`) | Arbeitseinheit; bei SEDRA heute eine Mission mit Zustandsautomat |
| Herzschlag | Wecken eines Agenten, wenn Arbeit für ihn ansteht (Paperclip: Heartbeat; SEDRA: `job_supervisor`) |
| Slot | Ein paralleler Platz auf dem laufenden llama-server; heute ist 1 Slot Standard |
| Rezept | Eintrag in `role_routing.yaml`: Modell, Rollen, Servereinstellungen, Kontextgrenzen |
| Gate | Freigabepunkt des Guard (ALLOW, BLOCK, CAPTAIN_REQUIRED) |
| Shell D | Die Paperclip-Shell unter `uix/shells/paperclip/`, laut Vertrag §9 nach Cockpit (C) und Minimal (E) geplant |

Namensregel (Captain, 20.10.2026): Der Bauagent heißt jetzt SEDRA statt GUPPI. Im Code bleiben die technischen Namen unverändert, etwa `guppi_runtime`, `trust: GUPPI_BUILT` und der Ordner `workspace/GUPPI_OS/`.

## Ist-Stand: Paperclip gegen SEDRA

SEDRA hat für die meisten Paperclip-Systeme schon ein Gegenstück; die echten Lücken sind parallele Agenten, Agenten-Zuweisung mit Herzschlag, Budgets je Agent und die Cloud-Stufe. Die Tabelle beruht auf der GitHub-Doku von SEDRA (Stand 12.–15.10.2026, öffentlich bis Build 24; der lokale Stand ist neuer, etwa mit dem KI-Labor im Cockpit); der Vorarbeiter prüft jede Zeile gegen den lokalen Main Branch, bevor G1 erteilt wird.

Wichtig: Im Konzept `UIX_KOMMANDODECK_v1.md` hat der Captain schon entschieden, Paperclip „als Vorbild, nicht Einbau“ zu nutzen. Spec 0 baut darauf auf.

| Paperclip-System | Gegenstück in SEDRA | Stand (vermutet) | Spec |
| --- | --- | --- | --- |
| Org-Chart & Agenten | `agent_manager/`: Vorlagen, Instanzen, Crews, `hire`, `promote` | teilweise – Berichtslinien und Vorgesetzte prüfen | 1 |
| Aufgaben mit atomarem Checkout | `core/mission.py`, `mission_lock.py`, Desk-Objekt `task` | teilweise – Zuweisung an Agent, Blocker, Kommentare fehlen vermutlich | 1 |
| Heartbeat-Ausführung | `jobs/job_supervisor.py` (Warteschlange, Leases, Herzschlag, Stillstand) | teilweise – weckt Jobs, nicht Agenten bei Zuweisung | 1 |
| Parallele Ausführung | `jobs/testlab.py` GPU-Lease (ein Prozess), 1 Slot je Rezept, `resource_scheduler.py` | fehlt | 2 |
| Adapter | `models/router.py`, `llamacpp.py`, `openai_local.py`, `lmstudio.py` | lokal vorhanden; Cloud im GateWay nur simuliert | 3 |
| Governance & Freigaben | `core/guard.py`, `permission_levels.py`, `desk/decisions.py` | vorhanden, strenger als Paperclip | – |
| Budget & Kosten | `jobs/token_policy.py`, Werkzeug `costs` | teilweise – kein Budget je Agent oder Aufgabe mit Hard-Stop | 1, 3 |
| Routinen & Zeitpläne | Objekttyp `routine` im Vertrag; Ketten wie `night_queue_*.py` | fehlt – Eintrag in Build 24 entfernt, weil kein Werkzeug dahinter war | 1 |
| Activity & Events | `core/audit.py` (hash-verkettet), `desk/events.py` (SSE) | vorhanden | – |
| Plugins | Shell-Werkzeug-Vertrag, Gate `install_module`, E1-Integration | vorhanden (Oberfläche), Backend nur E1 | – |
| Workspaces & Sandbox | `devenv/devvm.py`, microVM über microsandbox | vorhanden für Bauten | – |
| Secrets | Geheimnis-Sperre (Hardening 14.10.), Schwärzung im Audit | vorhanden, je Agent prüfen | 3 |
| Oberfläche im Paperclip-Stil | Shell D `uix/shells/paperclip/`, Start `START_SEDRA.bat paperclip` | seit Build 13 vorhanden (Navigation, Seiten, Gespräch als Schublade); laut Captain noch nicht weit (20.10.) | 4 |
| Mehrere Organisationen, Export/Import | – | bewusst weggelassen | – |

## Spec 0 – Kern-Architektur und Kern-API

Empfehlung: Variante A. SEDRA bleibt Python, das Desk ist die Kern-API für alle Anwendungsfälle, und die Orchestrierung entsteht als neues Paket außerhalb von `core/`. Der Captain hat am 20.10.2026 entschieden: Variante A mit der Paperclip-Shell D als Arbeitsfläche, die KI-Zentrale bleibt nur eine Option (unten).

### Varianten

| Variante | Was passiert | Aufwand | Risiko | Passung zu SEDRA |
| --- | --- | --- | --- | --- |
| A – Python, Desk als API (gewählt) | Paperclip-Funktionen als Paket `guppi_runtime/orchestra/`, angeboten über Desk-Objekte und Verben | mittel | gering – Kern, Guard und 117 Testdateien bleiben | hoch; entspricht „Vorbild, nicht Einbau“ |
| B – Paperclip daneben | Paperclip-Server (Node 24, pnpm, Postgres) läuft neben SEDRA, spricht SEDRA über einen Adapter an | mittel bis hoch | mittel – zwei Stacks, zwei Rechtesysteme, Guard muss jeden Paperclip-Aufruf decken | gering; widerspricht der früheren Entscheidung |
| C – Neubau in TypeScript | Kern nach Paperclip-Vorbild neu | sehr hoch | hoch – abgenommene SEDRA-Module und Testbasis gehen verloren | gering |

Selbstbau und Option „KI-Zentrale“ (Captain, 20.10.2026): Shell D und die Orchestrierung werden in SEDRA gebaut, auch wenn Teile von Grund auf neu entstehen müssen und der Aufwand groß ist. Eine Shell „KI-Zentrale“ mit Paperclip als Orchestrator daneben bleibt eine Option, die nur der Captain zieht; Voraussetzung ist KERN-07. Ist KERN-07 nicht erfüllbar, scheidet Paperclip als Orchestrator aus, und es wird eine andere Lösung gesucht.

Dafür kommt KERN-07 hinzu: WENN Paperclip als Orchestrator angebunden wird, DANN SOLL es SEDRA-Agenten nur über die Kern-API wecken und nie am Guard vorbei arbeiten. Abnahme: Ein Paperclip-Herzschlag an einen SEDRA-Agenten (HTTP-Adapter von Paperclip) erzeugt eine SEDRA-Mission mit Gate und Audit, und Kosten erscheinen in beiden Systemen.

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| KERN-01 | Das System SOLL Agenten, Aufgaben, Routinen und Budgets als Desk-Objekte in der Form `{type, id, title, state, summary, actions, links}` anbieten. | `GET /api/objects/agent/<id>` und `GET /api/objects/task?filter` liefern diese Form |
| KERN-02 | WENN ein Verb auf einem Objekt ausgeführt wird, DANN SOLL es über `POST /api/actions` und das Gate dieses Verbs laufen. | Gleiches Verb aus Shell, Gespräch und CLI erzeugt denselben Audit-Eintrag |
| KERN-03 | Das Paket `core/` SOLL nur über einzeln freigegebene Gates geändert werden (Grundsatzfreigabe des Captains vom 20.10.2026). | Diff in `core/` nur mit Gate-ID im Logbuch; `tests.test_core_boundary_src` grün |
| KERN-04 | WENN ein neuer Anwendungsfall dazukommt, DANN SOLL er als Objekttyp, Verben und Werkzeug ergänzt werden können, ohne `uix_server.py` zu ändern. | Ein Beispiel-Objekttyp wird nur über Registrierung eingebunden |
| KERN-05 | Externe Clients (CLI, MCP, später ein Paperclip-Adapter) SOLLEN dieselbe API mit Token nutzen. | Ein Aufruf über MCP legt eine Aufgabe an, Audit nennt den Client |
| KERN-06 | WENN eine Konfiguration des Pakets fehlt oder ungültig ist, DANN SOLL das Paket abschalten und `boot()` den Grund melden. | `guppi doctor` zeigt `orchestra_error` mit Grund |
| KERN-07 | WENN Paperclip als Orchestrator angebunden wird, DANN SOLL es SEDRA-Agenten nur über die Kern-API wecken und nie am Guard vorbei arbeiten. | Paperclip-Herzschlag erzeugt SEDRA-Mission mit Gate und Audit; Kosten in beiden Systemen |

### Design (Vorschlag)

- Schichten von unten: `core/` (nur mit Gate je Änderung) → `jobs/`, `models/` → neu `orchestra/` → `desk/` (API) → `uix_server.py` (nur HTTP) → Shell D.
- `orchestra/` mit `org.py` (Agenten, Rollen, Vorgesetzte), `board.py` (Aufgaben, Checkout, Blocker, Kommentare), `heartbeat.py` (Wecken), `budget.py`, `routines.py`.
- Ablage in SQLite unter `workspace/GUPPI_OS/runtime_data/orchestra/orchestra.db`, wie `testlab.db`; atomares Schreiben über `core/util.py`.
- Konfiguration `runtime/config/orchestra.yaml`, Schalter `orchestra` in `local_config/switches.yaml` (Standard aus).
- Stufe: E2 (Erweiterung) – braucht laut `self_development.py` immer den Captain.
- Neue Guard-Aktionen (z. B. `assign_task`, `wake_agent`, `set_budget`) werden in `guard_rules.yaml` eingetragen; das ist Harness-Arbeit der KI-Sitzung und ein eigenes Gate.

### Aufgaben

- [ ] K0.1 Lokalen Stand gegen GitHub abgleichen: `BUILD.txt`, `docs/CHANGELOG.md`, `git log`
- [ ] K0.2 Ist-Tabelle oben Zeile für Zeile gegen den Code prüfen und korrigieren
- [ ] K0.3 Desk-Stand prüfen: Welche Objekttypen und Verben gibt es in `desk/objects.py` und `desk/actions.py`?
- [ ] K0.4 Variante A mit Befunden aus K0.1–K0.3 gegen den Code bestätigen → G1
- [ ] K0.5 Design `orchestra/` mit Datenmodell und neuen Guard-Aktionen ausarbeiten → G2
- [ ] K0.6 Nach Freigabe: Logbuch-Eintrag, Doku (README, `ENTWICKLUNG.md`) auf Local First, Cloud Second anpassen

## Spec 1 – Orchestrierung: Agenten, Aufgaben, Herzschlag

Spec 1 macht aus den einzelnen Agenten des Agent Managers ein Team: Organigramm, zugewiesene Aufgaben mit atomarem Checkout, Wecken bei Arbeit, Budgets und Routinen. Ausgeführt wird jede Agentenarbeit weiterhin als Mission durch Brain und Guard.

Erstes Team (Captain, 20.10.2026): Planer, Coder, Reviewer, Recherche. Der Planer steht oben im Organigramm und delegiert an die drei anderen. Die Rezepte kommen aus den vorhandenen Rollen `planner`, `coder` und `reviewer` in `role_routing.yaml`; für Recherche wird eine Rolle mit dem lesenden Web-Werkzeug angelegt (Hosts aus `config/web_access.yaml`). Der Reviewer gibt Hinweise, entscheidet aber keine Abnahme: Laut `ENTWICKLUNG.md` sind Modell-Reviewer unzuverlässig, Richter bleibt der versteckte Test.

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| ORC-01 | WENN der Captain einen Agenten einstellt, DANN SOLL das System ihn mit Rolle, Rezept, Vorgesetztem und Budget registrieren. | Objekt `agent` mit `reports_to`; Einstellen läuft über ein Gate |
| ORC-02 | Jeder Agent außer dem obersten SOLL genau einen Vorgesetzten haben. | Ein Zyklus im Organigramm wird abgelehnt |
| ORC-03 | WENN eine Aufgabe zugewiesen wird, DANN SOLL sie genau einen Bearbeiter haben. | Zweite Zuweisung ersetzt die erste und schreibt Audit |
| ORC-04 | WENN zwei Agenten dieselbe Aufgabe gleichzeitig übernehmen wollen, DANN SOLL genau einer Erfolg haben. | Paralleltest mit 2 Prozessen, 100 Durchläufe, nie zwei Halter |
| ORC-05 | WENN eine Aufgabe einen offenen Blocker hat, DANN SOLL sie nicht ausgeführt werden. | Wecken einer blockierten Aufgabe führt zu keinem Lauf |
| ORC-06 | WENN einem Agenten Arbeit zugewiesen wird oder eine Antwort auf seine Rückfrage eingeht, DANN SOLL der Herzschlag ihn wecken; mehrere Weckrufe kurz nacheinander werden zusammengefasst. | 3 Zuweisungen in 1 s ergeben 1 Lauf |
| ORC-07 | WENN ein Agent geweckt wird, DANN SOLL seine Arbeit als Mission mit Guard-Prüfung und Audit laufen. | Jeder Lauf hat eine Mission-ID und Audit-Einträge |
| ORC-08 | WENN ein Agent eine Teilaufgabe erstellt, DANN SOLL sie nur an Agenten unter ihm im Organigramm gehen, mit höchstens seinen Rechten. | Delegation nach oben oder zur Seite wird abgelehnt |
| ORC-09 | WENN ein Agent 80 % seines Budgets erreicht, DANN SOLL das System warnen; bei 100 % SOLL es den Agenten pausieren und eine Entscheidung an den Captain stellen. | Budget in Token (lokal) und Euro (Cloud); Pause wird ausgelöst |
| ORC-10 | WENN der Zeitpunkt einer Routine erreicht ist, DANN SOLL eine Aufgabe für den zuständigen Agenten entstehen; verpasste Läufe werden nach Regel nachgeholt oder ausgelassen. | Routine mit Cron erzeugt Aufgabe; Nachhol-Regel getestet |
| ORC-11 | WENN ein Lauf länger als die eingestellte Zeit keinen Fortschritt meldet, DANN SOLL das System Stillstand melden und die Aufgabe freigeben. | Mechanik aus `job_supervisor` wiederverwendet |
| ORC-12 | Der Captain SOLL jeden Agenten pausieren, fortsetzen und beenden können; eine laufende Aufgabe wird dabei sauber freigegeben. | Nach Beenden hat die Aufgabe keinen Halter mehr |
| ORC-13 | Jede Aufgabe SOLL ihre Zielkette (Ziel → Projekt → Aufgabe) an den Agenten mitgeben. | Die Mission enthält die Zielkette im Kontext |

### Design (Vorschlag)

Datenmodell in `orchestra.db`:

| Tabelle | Wichtige Felder |
| --- | --- |
| `agents` | `id`, `template_id`, `role`, `recipe_id`, `reports_to`, `status` (aktiv, pausiert, beendet), `budget_tokens`, `budget_eur` |
| `tasks` | `id`, `title`, `goal_id`, `parent_id`, `assignee`, `state`, `checkout_by`, `checkout_at`, `mission_id` |
| `blockers` | `task_id`, `blocked_by_task_id` |
| `comments` | `task_id`, `author` (Agent oder Captain), `text`, `ts` |
| `wakeups` | `id`, `agent_id`, `reason`, `due_at`, `coalesced_into` |
| `routines` | `id`, `agent_id`, `cron`, `catch_up` (nachholen, auslassen), `last_run` |
| `spend` | `agent_id`, `task_id`, `provider` (lokal, cloud), `tokens`, `eur`, `ts` |

- Checkout: `BEGIN IMMEDIATE` und `UPDATE tasks SET checkout_by=? WHERE id=? AND checkout_by IS NULL`; Erfolg nur bei genau einer geänderten Zeile.
- Herzschlag: `heartbeat.py` liest fällige `wakeups`, fasst sie je Agent zusammen und übergibt einen Job an `job_supervisor`; das Modell holt sich der Job beim Scheduler (Spec 2).
- Ein Agentenlauf: Aufgabe auschecken → Mission mit `captain_intent` aus Aufgabe und Zielkette → Brain → Ergebnis als Kommentar und Arbeitsprodukt → Aufgabe freigeben.
- Rechte: Agent erbt die `permission_levels` seiner Vorlage; Delegation kann sie nur senken.

### Aufgaben

- [ ] O1.1 Agent Manager auf Berichtslinien und Instanz-Status prüfen; Erweiterung oder neues `org.py` festlegen
- [ ] O1.2 Datenmodell final, Migration für bestehende Agenten → G2
- [ ] O1.3 Bau-Specs schreiben: `orc_org`, `orc_board`, `orc_heartbeat`, `orc_budget`, `orc_routines` in `devvm_specs/`, je mit Referenz und `spec_check.py` = ok → G3
- [ ] O1.4 Neue Guard-Aktionen und Desk-Registrierung (Harness, KI-Sitzung)
- [ ] O1.5 Bau durch SEDRA, Review, Übernahme → G4

## Spec 2 – Modell-Scheduler: parallele Agenten

Die GPU-Lease bleibt, bekommt aber eine zweite Ebene: Ein Prozess besitzt den Modellserver (Lade-Lease), und ein Scheduler verteilt dessen parallele Slots an Agentenläufe (Slot-Lease). Heute lädt nur ein Prozess Modelle und jedes Rezept hat 1 Slot; das ändert eine Regel aus `ENTWICKLUNG.md` und braucht deshalb eine Captain-Freigabe und eine Doku-Änderung.

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| SCH-01 | WENN ein Rezept `slots: N` angibt, DANN SOLL der llama-server mit N parallelen Slots starten. | N gleichzeitige Anfragen werden parallel beantwortet; Messung des Gesamtdurchsatzes |
| SCH-02 | Die Lade-Lease SOLL genau einen Besitzer haben; der Scheduler SOLL Slot-Leases an Läufe vergeben. | 2 Ladeversuche: einer wartet. N+1 Läufe: einer wartet in der Schlange |
| SCH-03 | WENN ein Server mit N Slots starten soll, DANN SOLL `resource_scheduler` VRAM inklusive KV-Cache für N Slots vorab reservieren und den Start ablehnen, wenn die Grenze von 11,5 GB überschritten würde. | Ablehnung nennt gemessenen und benötigten Wert |
| SCH-04 | Der Scheduler SOLL Captain-Anfragen vor Agentenläufen und diese vor Routinen bedienen; wartende Läufe steigen mit der Wartezeit in der Priorität. | Kein Lauf wartet länger als die eingestellte Obergrenze |
| SCH-05 | Die Kontextgrenze je Slot SOLL gemessen und im Rezept je Slot-Zahl geführt werden. | `context_ladder.py` liefert Werte für 1 bis N Slots; Rezept enthält sie |
| SCH-06 | WENN ein Lauf ein anderes Rezept braucht als das geladene, DANN SOLL der Scheduler nur nach einer vom Captain freigegebenen Regel umladen oder auf ein freigegebenes kleines Modell ausweichen. | Ohne Regel: Lauf wartet und meldet den Grund |
| SCH-07 | WENN alle Slots belegt sind und die Schlange länger als die Grenze ist, DANN SOLL der Scheduler die Cloud-Stufe vorschlagen (Spec 3), aber nie selbst umschalten. | Vorschlag erscheint als Entscheidung im Desk |
| SCH-08 | WENN der Server abstürzt oder Müll liefert, DANN SOLL das System den Canary laufen lassen, neu starten, offene Slot-Leases zurück in die Schlange geben und Läufe über `step_journal` fortsetzen, ohne Schritte still zu wiederholen. | Absturz-Test: kein Schritt doppelt ausgeführt |
| SCH-09 | Die Oberfläche SOLL Slots, Belegung und Warteschlange live zeigen. | Ereignis `slot.changed` auf `/api/events` |
| SCH-10 | Bau- und Messläufe (`devvm_build.py`, Benchmarks) SOLLEN die GPU weiterhin exklusiv nehmen können. | Modus `exklusiv` blockiert neue Slot-Leases, bis der Lauf endet |

### Design (Vorschlag)

- Neues Modul `jobs/model_scheduler.py`; `jobs/testlab.py` behält die Lade-Lease, eine neue Tabelle `slot_leases` in `testlab.db` hält die Slot-Leases mit Herzschlag wie bisher.
- Rezept-Erweiterung in `role_routing.yaml`: `server.slots: N` und `context.per_slots: {1: …, 2: …, 4: …}` aus Messungen.
- llama-server-Start mit `--parallel N`; der Gesamtkontext `-c` wird auf die Slots verteilt. Ob Build b11160 einen gemeinsamen KV-Puffer für alle Slots nutzt, wird gemessen, nicht angenommen.
- Jeder Agentenlauf fragt `model_scheduler.acquire(recipe, priority)` und bekommt einen Slot oder einen Platz in der Schlange.

### Messplan (vor G2)

1. Hauptmodell Qwen3.6-35B-A3B mit 1, 2, 3 und 4 Slots: VRAM, Kontext je Slot (`context_ladder.py --probes 2`), Token/s gesamt und je Slot.
2. Gleiche Messung für ein kleines Hilfsmodell, auch mit `n_cpu_moe` bzw. auf CPU.
3. Verbindungsprüfung S0 (`connection_check.py`) je Einstellung.
4. Ergebnis als Tabelle in `MODELLE.md`; Vorschlag für Standard-Slotzahl an den Captain.

### Aufgaben

- [ ] S2.1 Messplan ausführen (unter GPU-Lease, Rezepte nur mit Sicherung) → Messbericht
- [ ] S2.2 Regeländerung zur GPU-Lease in `ENTWICKLUNG.md` als Entwurf → Captain-Gate
- [ ] S2.3 Design `model_scheduler.py` und Tabelle `slot_leases` → G2
- [ ] S2.4 Bau-Specs `sch_queue` (Priorität, Altern), `sch_slots` (Vergabe, Rückgabe, Absturz) → G3
- [ ] S2.5 Integration in `llama_server_runtime.py` und `resource_scheduler.py` (Harness) → G4

## Spec 3 – Local First, Cloud Second

Cloud wird eine zweite Stufe hinter dem bestehenden Schutz: Jeder Cloud-Aufruf geht durch den Router, den Inhaltsschutz (Build 16) und die Einstufung des KI-GateWays (Build 19) und braucht eine Entscheidung oder eine vom Captain freigegebene Regel. Heute ist Cloud im GateWay nur simuliert, und die README sagt „keine Cloud-Modelle“; beides ändert sich erst nach Freigabe dieser Spec.

Anbieter (Captain, 20.10.2026): der NVIDIA API Catalog (Schlüssel vorhanden) und Mammouth (Schlüssel geplant). Beide bieten eine OpenAI-kompatible Schnittstelle, NVIDIA unter `https://integrate.api.nvidia.com/v1`, Mammouth mit eigener Basis-URL laut Mammouth-Doku. Ein Adapter `models/cloud.py` reicht deshalb für beide, mit je einem Cloud-Rezept. Mammouth leitet an Modelle verschiedener Hersteller weiter; welche Schutzklassen dorthin dürfen, legt die GateWay-Matrix je Anbieter fest. Beide Hosts sind neue Ziele im Netz, also externe Aktionen mit eigener Guard-Regel. Das Budget der Startphase steht im nächsten Abschnitt.

### Budget der Startphase (Captain, 20.10.2026)

In der Startphase kostet die Cloud nichts extra: NVIDIA wird kostenlos genutzt, Mammouth nur mit dem im Abo enthaltenen API-Guthaben. Gebremst wird über drei Ebenen.

| Ebene | Grenze | Verhalten |
| --- | --- | --- |
| Euro | 0 € zusätzlich; Mammouth nur Abo-Guthaben | Warnung bei 80 % des Guthabens, Stopp bei 100 % |
| Anfragen NVIDIA | 30 pro Minute systemweit, 500 pro Tag | Puffer zum Limit des kostenlosen Zugangs (meist bis zu 40 pro Minute); bei Erreichen wartet der Lauf oder bleibt lokal |
| Je Agent | Planer und Recherche: Cloud erlaubt; Reviewer: optional für eine zweite Meinung; Coder: nur lokal | Ein Coder-Lauf erzeugt nie einen Cloud-Aufruf |

- Vor dem regelmäßigen Einsatz prüft der Vorarbeiter die Nutzungsbedingungen beider Anbieter; der kostenlose NVIDIA-Zugang ist für Prototypen, Forschung und Tests gedacht.
- Nach etwa vier Wochen Betrieb wertet der Vorarbeiter die Tabelle `spend` aus: wie oft lokal überlastet war, welche Agenten die Cloud brauchten, was es gekostet hätte. Daraus legt der Captain ein festes Monatsbudget fest.
- Alle Grenzen liegen in `local_config/cloud_rules.yaml` und werden nur über ein Gate geändert.

### KI-Labor ausbauen (Captain, 20.10.2026)

Im Cockpit gibt es schon das Werkzeug „KI-Labor“ mit den API-Anbindungen. Es wird zur Steuerstelle der Cloud-Stufe ausgebaut und in Shell D eingebunden, statt ein neues Werkzeug zu bauen. Weil es nur im lokalen Stand existiert, erfasst der Vorarbeiter es zuerst vor Ort.

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| LAB-01 | Das KI-Labor SOLL als Werkzeug nach dem Shell-Werkzeug-Vertrag in jeder Shell laufen, auch in Shell D, ohne Shell-eigenen Code. | `uix_check --tool <id>` meldet `result ok` in Cockpit und Paperclip |
| LAB-02 | WENN der Captain einen Anbieter anlegt (Name, Basis-URL, Modelle), DANN SOLL das über ein Gate laufen und der Schlüssel nur im Secret-Speicher landen. | Schlüssel steht in keiner Datei, keinem Log, keinem Audit-Eintrag |
| LAB-03 | Der Captain SOLL je Anbieter einen Kurztest starten können (eine Frage, Antwortzeit, Token); der Test ist eine externe Aktion mit Gate und läuft durch das GateWay. | Testergebnis wie beim Kurztest der Werkstatt, Audit `CLOUD_CALL` |
| LAB-04 | Das KI-Labor SOLL die Grenzen der Startphase zeigen; jede Änderung ist ein Gate. | Anfragen pro Minute und Tag, Abo-Guthaben, Freigaben je Agent sichtbar |
| LAB-05 | Das KI-Labor SOLL den Verbrauch je Anbieter und Agent live zeigen und bei 80 % warnen. | Werte aus `spend`, Ereignis `budget.warning` |
| LAB-06 | Das KI-Labor SOLL je Anbieter zeigen, welche Schutzklassen dorthin dürfen; geändert wird das nur im GateWay. | Anzeige nur lesend, Verweis auf das GateWay |
| LAB-07 | Das KI-Labor SOLL den Schalter `cloud` zeigen; Umschalten ist ein Gate. | Bei aus zeigt das Labor „Cloud-Stufe aus“ |

- [ ] L3.1 KI-Labor lokal erfassen: Werkzeug-ID, Manifest, Routen, Vertrauensrang und wo heute Schlüssel liegen (gegen CLD-08 prüfen)
- [ ] L3.2 Prüfen, ob es vertragskonform ist; wenn ja, in Shell D einhängen, sonst Nacharbeit planen
- [ ] L3.3 Design der Erweiterung nach LAB-02 bis LAB-07 → G2
- [ ] L3.4 Bau-Spec für die reinen Teile (Budgetrechnung, Warnschwellen) mit versteckten Tests; Oberfläche mit `uix_check` → G3

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| CLD-01 | Jeder Modellaufruf SOLL lokal laufen, solange keine Cloud-Regel greift. | Ohne Regel: 0 Cloud-Aufrufe im Audit |
| CLD-02 | WENN ein Cloud-Aufruf in Frage kommt, DANN SOLL das GateWay die Anfrage nach Schutzklasse einstufen; gesperrte Schutzklassen (z. B. personenbezogene Daten) gehen nie in die Cloud. | Testfälle je Schutzklasse; gesperrte Klasse bleibt lokal |
| CLD-03 | WENN ein Cloud-Aufruf erfolgen soll, DANN SOLL er eine Entscheidung des Captains brauchen, außer eine freigegebene Regel deckt Agent, Schutzklasse, Anbieter und Budget. | Regel ist im Audit gebunden; ohne Deckung entsteht eine Entscheidung |
| CLD-04 | Jeder Cloud-Aufruf SOLL im Audit mit Anbieter, Modell, Token, Kosten und Schutzklasse stehen, ohne Inhalt. | Audit-Eintrag `CLOUD_CALL` vorhanden, kein Text darin |
| CLD-05 | WENN ein Cloud-Budget erreicht ist – in Euro, in Anfragen pro Minute oder in Anfragen pro Tag, je Agent, je Anbieter oder gesamt –, DANN SOLL das System keine weiteren Cloud-Aufrufe zulassen; bei 80 % SOLL es warnen. | Hard-Stop greift; Lauf fällt auf lokal oder wartet |
| CLD-06 | Die Oberfläche SOLL jede Antwort aus der Cloud sichtbar kennzeichnen. | Kennzeichen in Gespräch und Aufgabe |
| CLD-07 | WENN die Cloud nicht erreichbar ist, DANN SOLL das System lokal weiterarbeiten oder warten; es wechselt nie still die Stufe. | Ausfall-Test ohne stillen Wechsel |
| CLD-08 | API-Schlüssel SOLLEN nur im Secret-Speicher liegen, nie in Rezepten, Logs oder Audit. | Geheimnis-Sperre findet keinen Schlüssel in Dateien |
| CLD-09 | WENN Cloud-Agenten wie Claude Code oder Codex eingebunden werden, DANN SOLLEN sie als Adapter hinter derselben Prüfung laufen und nur in der DevVM arbeiten. | Adapter-Lauf zeigt Gate, Einstufung und microVM |
| CLD-10 | Ein Schalter `cloud` in `switches.yaml` SOLL die Stufe ganz abschalten; Standard ist aus. | Bei aus: Router kennt keine Cloud-Ziele |

### Design (Vorschlag)

- Adapter `models/cloud.py` für OpenAI-kompatible Anbieter, nach Vorbild von `openai_local.py`.
- Rezepte bekommen ein optionales Feld `fallback: <cloud-rezept>`; der Router entscheidet die Stufe, nie das Modell selbst.
- Ablauf eines Aufrufs: lokal möglich? → ja: lokal. Nein oder überlastet (SCH-07) → Schalter `cloud` an? → GateWay stuft ein → Klasse erlaubt? → Regel deckt den Fall? → sonst Entscheidung an den Captain → Budget prüfen → Aufruf → Audit und `spend`.
- Cloud-Regeln liegen in `local_config/cloud_rules.yaml` (nicht im Git) und werden nur über ein Gate geändert.

### Aufgaben

- [ ] C3.1 `SPEC_EIN_SICHERER_WEG_v1.md` und `SPEC_GATEWAY_VORGANG_v1.md` lesen: Schutzklassen und Matrix übernehmen, nicht neu erfinden
- [ ] C3.2 Entwurf der Grundsatzänderung für README und `ENTWICKLUNG.md` → Captain-Gate
- [ ] C3.3 Design Adapter, Regeln, Budget → G2
- [ ] C3.4 Bau-Spec `cld_rules` (Regelprüfung, Budget) mit versteckten Tests; Adapter und Router-Stufe als Harness → G3
- [ ] C3.5 Test mit einem Anbieter und kleinem Budget, danach Abnahme → G4

## Spec 4 – Oberfläche: die Paperclip-Shell (D)

Shell D ist die Arbeitsfläche für das Agenten-Team: Navigation wie bei Paperclip, jeder Agent als eigenes Gesprächsfenster, Aufgaben, Entscheidungen und Slots live. Sie hält den Shell-Werkzeug-Vertrag v1 ein und nutzt vorhandene Werkzeuge, bevor neue entstehen.

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| UIX-01 | Shell D SOLL den Vertrag `SHELL_WERKZEUG_VERTRAG_v1.md` einhalten: Manifest, nur `ctx.api()` und `ctx.bus`, eigener Container, höchstens 400 Zeilen je Datei, README. | `tests/test_uix_contract.py` grün; `uix_check.py` meldet `result ok` |
| UIX-02 | Die Shell SOLL eine Navigation bieten: Übersicht, Eingang (Entscheidungen), Aufgaben, Ziele, Organigramm, Agenten, Routinen, Kosten, Modelle und Slots sowie KI-Labor. | Jeder Eintrag öffnet ein Objekt oder eine Liste |
| UIX-03 | Die Shell SOLL vorhandene Werkzeuge (`task`, `decisions`, `crew`, `costs`, `live`, `workshop`, `talk`) wiederverwenden; neu entstehen nur `org`, `board`, `routines` und das Instrument `slots`. | Manifest-Liste zeigt die Wiederverwendung |
| UIX-04 | WENN der Captain einen Agenten öffnet, DANN SOLL ein eigenes Gesprächsfenster mit diesem Agenten erscheinen, mit seinen Aufgaben und Läufen daneben. | Mehrere Agentenfenster gleichzeitig offen; jedes hält seinen Verlauf |
| UIX-05 | Die Shell SOLL Änderungen über den Ereignisstrom `/api/events` erhalten, nicht durch Polling. | Keine periodischen Abfragen im Netzwerkprotokoll |
| UIX-06 | Jede Handlung SOLL über `POST /api/actions` laufen. | Allowlist der neuen Werkzeuge enthält keine Spezialrouten |
| UIX-07 | WENN eine Entscheidung offen ist, DANN SOLL die Shell sie sichtbar markieren und die Wege des Desk anbieten (einmal, ändern, ablehnen, freigeben). | Badge an Eingang und am betroffenen Agenten |
| UIX-08 | Die Shell SOLL Cloud-Antworten kennzeichnen und den Budgetstand je Agent zeigen. | Kennzeichen und Balken sichtbar |
| UIX-09 | `START_SEDRA.bat paperclip` SOLL direkt in Shell D starten. | Start ohne Zwischenschritt |

### Design (Vorschlag)

- Prüfen, ob Shell D als Vorgabe (`shell.vorgabe.yaml`, Rahmen `ui/frame.js`, Build 17) gebaut werden kann; das spart Shell-Code. Sonst klassisch mit `shell.yaml` und `shell.js`.
- Aufbau: linke Navigation, Mitte Liste oder Board, rechts Detail beziehungsweise Agentengespräch; Slots als Instrument in der Leiste.
- Neue Ereignisse: `agent.changed`, `slot.changed`, `budget.warning`; Eintrag in Vertrag §5 als Nachtrag.
- Neue Werkzeuge entstehen als Kopie von `tools/_template/` mit `trust: GUPPI_BUILT`, wenn SEDRA sie baut.

Keine Grenze nach Umfang (Captain, 20.10.2026): Shell D wird auch gebaut, wenn viele neue Werkzeuge oder eine Änderung am Shell-Werkzeug-Vertrag nötig sind. Vertragsänderungen sind grundsätzlich freigegeben; jede einzelne bleibt ein Gate und kommt als Nachtrag in `SHELL_WERKZEUG_VERTRAG_v1.md`. Stand laut Captain: `uix/shells/paperclip/` ist vorhanden, der Bau steht am Anfang.

KI-Labor (Captain, 20.10.2026): Das vorhandene Werkzeug aus dem Cockpit kommt als eigener Navigationseintrag in Shell D, neben Modelle und Slots, und wird nach Spec 3 (LAB-01 bis LAB-07) ausgebaut. Es zählt nicht als neues Werkzeug.

### Aufgaben

- [ ] U4.1 Stand von `uix/shells/paperclip/` prüfen und Paperclip-UI (Vorlage `ui/`) auf Ansichten und Abläufe durchsehen
- [ ] U4.2 Skizze der Shell und Liste der Werkzeuge → G1/G2
- [ ] U4.3 Bau-Specs `tool_org`, `tool_board`, `tool_routines`, `tool_slots` (Node-Tests für reine Teile, `uix_check` für den Browser) → G3
- [ ] U4.4 Bau durch SEDRA, Einbau über Gate `install_module` → G4

## Spec 5 – Inbetriebnahme und Abnahme

Das Vorhaben gilt als fertig, wenn sechs Durchläufe von Anfang bis Ende grün sind und die Standardprüfungen von SEDRA bestehen. Jeder Durchlauf ist ein Test, der auch später wiederholt werden kann.

| ID | Durchlauf | Erwartetes Ergebnis |
| --- | --- | --- |
| E2E-1 | Captain stellt einen Agenten ein und weist ihm eine Aufgabe zu | Herzschlag weckt ihn, Mission läuft lokal, Guard entscheidet, Ergebnis als Kommentar, Audit vollständig |
| E2E-2 | Ein Planer-Agent delegiert zwei Teilaufgaben an zwei Agenten unter ihm | Beide laufen gleichzeitig auf zwei Slots; das Instrument `slots` zeigt die Belegung |
| E2E-3 | Ein Agent erreicht sein Budget | Warnung bei 80 %, Pause bei 100 %, Entscheidung im Eingang |
| E2E-4 | Alle Slots belegt, Schlange über der Grenze | Cloud-Vorschlag als Entscheidung; bei Freigabe gekennzeichnete Antwort, Audit `CLOUD_CALL`, Kosten in `spend` |
| E2E-5 | Der llama-server stürzt während eines Laufs ab | Canary, Neustart, Lauf setzt fort, kein Schritt doppelt |
| E2E-6 | Eine Routine mit Cron wird fällig, während SEDRA aus war | Nachhol-Regel greift wie eingestellt |

Standardprüfungen vor jeder Übernahme:

- `guppi doctor` meldet READY.
- Betroffene Tests grün, dazu immer `tests.test_core_boundary_src`.
- Oberfläche: `benchmarks/uix_check.py` mit `result ok`.
- Logbuch-Eintrag über `benchmarks/logbook.py add`, Build über `benchmarks/make_build.py`, Eintrag in `docs/CHANGELOG.md`.
- Keine lokalen Pfade in eingecheckten Dateien; kein Push ohne Auftrag des Captains.

## Spec 6 – Social- und Nachrichten-Zentrale

SEDRA bekommt eine Zentrale für Social-Konten (Captain, 20.10.2026): Konten verbinden und angemeldet bleiben, Beiträge entwerfen, planen und posten. „Angemeldet bleiben“ heißt hier: SEDRA hält die Zugangstoken der offiziellen Schnittstellen im Secret-Speicher und erneuert sie, soweit die Plattform es erlaubt; Passwörter sieht und speichert SEDRA nie. Die Zentrale ist von Anfang an für weitere Kanäle gebaut: Instagram, WhatsApp und der E-Mail-Eingang docken später über denselben Kanal-Vertrag an (Captain, 20.10.2026).

### Was die Plattformen erlauben

| Plattform | Wohin posten | Anmeldung und Laufzeit | Planen |
| --- | --- | --- | --- |
| LinkedIn | Eigenes Profil (`w_member_social`) und Unternehmensseite (`w_organization_social`); beide Rechte brauchen eine Prüfung durch LinkedIn, die Wochen dauern kann | OAuth; Zugangstoken 60 Tage; Refresh-Token (365 Tage) nur für freigegebene Marketing-Partner, sonst Neuanmeldung alle 60 Tage; ein Refresh verlängert die 365 Tage nicht | Kein Planen in der Schnittstelle: SEDRA hält den Beitrag und postet zur Zeit |
| Facebook | Nur Seiten, kein persönliches Profil (seit 2018 abgeschaltet) | Seiten-Token aus einem langlebigen Nutzer-Token läuft nicht ab, wird aber ungültig bei Passwortwechsel, Entzug der App oder Verlust der Admin-Rechte | Planen in der Schnittstelle mit `scheduled_publish_time`, 10 Minuten bis 30 Tage im Voraus |

Für beide braucht es eine eigene Entwickler-App mit Datenschutzerklärung. Bei Meta braucht jede Berechtigung über `public_profile` hinaus eine App-Prüfung (`pages_manage_posts` mit `pages_read_engagement` und `pages_show_list`); Seiten, die man nicht selbst verwaltet, zusätzlich eine Business-Verifizierung.

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| SOC-01 | WENN der Captain ein Konto verbindet, DANN SOLL das über den offiziellen OAuth-Weg der Plattform im Browser laufen; SEDRA sieht und speichert kein Passwort. | Kein Passwortfeld in SEDRA; Verbinden ist ein Gate |
| SOC-02 | Zugangs- und Refresh-Token SOLLEN nur im Secret-Speicher liegen; SEDRA erneuert sie selbst, wo die Plattform es erlaubt. | Erneuerung ohne Zutun, Audit `SOCIAL_TOKEN_REFRESHED` ohne Token |
| SOC-03 | WENN ein Token in 7 Tagen abläuft oder ungültig wird, DANN SOLL eine Entscheidung „neu anmelden“ im Eingang erscheinen; geplante Beiträge dieses Kontos werden angehalten, nicht verworfen. | Abgelaufenes Testtoken hält die Planung an |
| SOC-04 | Agenten SOLLEN Entwürfe schreiben dürfen; jeder Entwurf geht durch das GateWay (Personenbezug, KI-Kennzeichnung nach R-14). | Entwurf trägt den GateWay-Befund |
| SOC-05 | WENN ein Beitrag veröffentlicht werden soll, DANN SOLL er eine Freigabe des Captains brauchen, gebunden an Inhalt (Hash), Konto und Zeitpunkt; jede Änderung danach macht die Freigabe ungültig. | Geänderter Text verlangt eine neue Freigabe |
| SOC-06 | Geplante Beiträge SOLLEN in einem Kalender stehen; Facebook plant in der Schnittstelle (bis 30 Tage), sonst hält SEDRA den Beitrag und postet ihn über eine Routine (ORC-10). | Beitrag erscheint zur geplanten Zeit (± 2 Minuten), Audit vorhanden |
| SOC-07 | Für geplante Beiträge SOLL es eine Freigabeart geben, die bis zur Veröffentlichung gilt; Guard-Freigaben gelten heute 24 Stunden. | Beitrag in 10 Tagen mit einer einzigen Freigabe |
| SOC-08 | WENN SEDRA zum geplanten Zeitpunkt aus war, DANN SOLL es nicht still nachposten, sondern fragen: jetzt posten, neu planen oder verwerfen. | Verpasster Termin erzeugt diese Entscheidung |
| SOC-09 | Posten SOLL eine externe Schreibaktion sein: Die Netz-Grenze des Projekts (Build 9) muss sie decken, erlaubt sind nur die Hosts der Plattformen. | Fremder Host wird abgewiesen |
| SOC-10 | Nach dem Veröffentlichen SOLL SEDRA Link und Plattform-ID am Beitrag speichern; Bearbeiten und Löschen auf der Plattform laufen ebenfalls über ein Gate. | Beitrag zeigt den Link; Löschen fragt |
| SOC-11 | SEDRA SOLL nur die offiziellen Schnittstellen nutzen: kein Posten über Browser-Steuerung, keine automatischen Likes, Kommentare oder Kontakte. | Keine Browser-Automatisierung im Paket `social/` |

### Design (Vorschlag)

- Paket `guppi_runtime/social/`: `accounts.py` (Konten, Verweise auf Token im Secret-Speicher), `oauth.py` (Autorisierungscode-Weg mit Rückruf an den lokalen `uix_server`), `posts.py` (Zustände: Entwurf → geprüft → freigegeben → geplant → veröffentlicht oder fehlgeschlagen), Adapter `linkedin.py` und `facebook.py`.
- Desk-Objekte `social_account` und `social_post`; Verben `connect`, `reconnect`, `draft`, `approve`, `schedule`, `publish_now`, `cancel`.
- Werkzeug `social` in Shell D: Konten mit Status (verbunden, läuft ab in n Tagen, getrennt), Kalender, Entwürfe, offene Freigaben; im Cockpit über den Vertrag ebenfalls nutzbar.
- Vorhaben-Vorlage „Beitragsreihe“ auf den Vorhaben mit Stufen (Build 20): Thema → Entwürfe → Prüfen → Planen → Auswerten.
- Entwürfe schreiben Planer und Recherche; ob sie dazu die Cloud nutzen dürfen, regelt Spec 3.

### Erweiterbar: der Kanal-Vertrag

Jeder Kanal ist ein Adapter mit derselben Schnittstelle; ein neuer Kanal ändert weder die Zentrale noch das Werkzeug, die Freigaben oder das Audit. Ein Kanal beschreibt sich in einem Manifest: `id`, `art` (Beitrag, Nachricht, Mail), `richtung` (aus, ein, beides), `anmeldung` (OAuth, Token, IMAP), was er kann (selbst planen, bearbeiten, löschen, Anhänge), seine Grenzen (z. B. Beiträge je 24 Stunden, Antwortfenster) und seine Hosts für die Netz-Grenze.

| Kanal | Art | Was offiziell geht | Besonderheit |
| --- | --- | --- | --- |
| LinkedIn (jetzt) | Beiträge | Profil und Unternehmensseite | Neuanmeldung alle 60 Tage ohne Partnerstatus |
| Facebook (jetzt) | Beiträge | Seiten | Planen bis 30 Tage in der Schnittstelle |
| Instagram (später) | Beiträge | Nur professionelle Konten, über Instagram- oder Facebook-Login | 100 API-Beiträge je 24 Stunden; kein Planen in der Schnittstelle, SEDRA hält den Beitrag |
| WhatsApp (später) | Nachrichten | Nur über die WhatsApp Business Platform mit registrierter Geschäftsnummer | Freie Antworten nur 24 Stunden nach der letzten Nachricht des Kunden, danach nur von Meta genehmigte Vorlagen |
| E-Mail-Eingang (später) | Mails ein und aus | IMAP/SMTP oder Postfach-Schnittstelle mit OAuth (z. B. Gmail, Microsoft 365) | Antworten laufen über den GateWay-Weg „Kundenanfrage beantworten“ (Build 20) |

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| SOC-12 | WENN ein neuer Kanal dazukommt, DANN SOLL er nur als Adapter mit Manifest nach dem Kanal-Vertrag eingebunden werden; Zentrale, Werkzeug, Freigabe und Audit bleiben unverändert. | Ein Testkanal „echo“ läuft nur über Registrierung |
| SOC-13 | WENN eine Nachricht eingeht (Mail, WhatsApp, Kommentar), DANN SOLL sie im gemeinsamen Posteingang der Zentrale landen und durch den Inhaltsschutz gehen; nichts wird automatisch beantwortet. | Eingehende Testmail erscheint, kein Versand |
| SOC-14 | Antworten an Personen SOLLEN wie Beiträge eine Freigabe brauchen, gebunden an Inhalt, Empfänger und Kanal; Kanalregeln (etwa das 24-Stunden-Fenster und Vorlagen bei WhatsApp) prüft der Adapter vorher. | WhatsApp-Antwort nach 25 Stunden ohne Vorlage wird mit Grund abgewiesen |
| SOC-15 | Eingehende Nachrichten sind personenbezogene Daten: Sie bleiben lokal (R-01) und gehen höchstens pseudonymisiert nach GateWay-Prüfung in die Cloud. | GateWay-Befund an jeder eingehenden Nachricht |

### Aufgaben

- [ ] S6.1 Entwickler-Apps bei LinkedIn und Meta anlegen und Berechtigungen beantragen (Captain; früh starten, die Prüfung dauert)
- [ ] S6.2 Klären, welche Konten: LinkedIn-Profil, Unternehmensseite oder beides; welche Facebook-Seiten
- [ ] S6.3 Freigabeart für geplante Beiträge (SOC-07) entwerfen → Captain-Gate (Guard, Kern)
- [ ] S6.4 Design `social/` und Werkzeug `social` → G2
- [ ] S6.5 Bau-Specs `soc_posts` (Zustandsautomat, Freigabe-Bindung) und `soc_schedule` (Planung, verpasste Termine) → G3
- [ ] S6.6 OAuth und Adapter als Harness; Test mit einer eigenen Testseite → G4
- [ ] S6.7 Kanal-Vertrag v1 mit Testkanal festlegen; Instagram, WhatsApp und E-Mail-Eingang danach als eigene kleine Specs (6a, 6b, 6c)

Offen für den Captain:

- [ ] Welche Konten genau (LinkedIn-Profil, Unternehmensseite, welche Facebook-Seiten)?
- [ ] Gibt der Captain jeden Beitrag einzeln frei, oder eine ganze Beitragsreihe auf einmal?
- [ ] Wie weit im Voraus soll geplant werden?
- [ ] Dürfen Entwürfe mit Cloud-Modellen entstehen, oder nur lokal?
- [ ] Welcher Kanal kommt nach LinkedIn und Facebook zuerst: Instagram, WhatsApp oder E-Mail-Eingang?
- [ ] Welches Postfach für den E-Mail-Eingang (Gmail, Microsoft 365 oder ein anderer Anbieter)?

## Entscheidungen des Captains (20.10.2026)

Alle acht Fragen sind beantwortet; neu offen sind nur die Fragen zur Social-Zentrale (Spec 6).

| Frage | Entscheidung | Folge im Dokument |
| --- | --- | --- |
| Variante | A mit Shell D, Selbstbau auch bei großem Aufwand; KI-Zentrale mit Paperclip nur als Option des Captains und nur, wenn KERN-07 erfüllbar ist | Spec 0: Option und KERN-07; Spec 4: keine Grenze nach Umfang |
| Shell D | Ordner `uix/shells/paperclip/` vorhanden, Bau am Anfang | Ist-Tabelle, Spec 4 |
| Cloud-Anbieter | NVIDIA API Catalog (vorhanden), Mammouth (geplant) | Spec 3: ein OpenAI-kompatibler Adapter für beide |
| Erstes Team | Planer, Coder, Reviewer, Recherche | Spec 1 |
| Reihenfolge | erst Spec 1, dann Spec 2 | Ablauf, Grafik, Prompt |
| Wer baut | GUPPI heißt jetzt SEDRA; SEDRA baut lokal unter Anleitung von Claude | Begriffe, Arbeitsteilung, Prompt |
| Ablage | als `docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md` ins Repo | diese Datei |
| Paperclip-Stand | lokale Kopie der verlinkten Vorlage | Vorarbeiter notiert Version und Datum |

Weitere Entscheidungen:

- [x] Cloud-Budget: Startphase mit 0 € zusätzlich, NVIDIA höchstens 30 Anfragen pro Minute und 500 pro Tag, Mammouth nur Abo-Guthaben, Coder nur lokal (Spec 3, Budget der Startphase). Festes Monatsbudget nach vier Wochen Auswertung.
- [x] Stand der Paperclip-Kopie: die verlinkte Vorlage `paperclipai/paperclip` (Branch `master`). Der Vorarbeiter notiert Version aus `package.json` und Datum der lokalen Kopie, weil `master` sich schnell ändert.
- [x] Grenze für die Rückfallebene: entfällt. Fehlende Grundlagen werden neu gebaut, Aufwand ist kein Kriterium; Paperclip als Orchestrator nur mit erfüllter KERN-07.
- [x] Änderungen an `core/` und am Shell-Werkzeug-Vertrag: grundsätzlich genehmigt. Jede einzelne Änderung bleibt ein eigenes Gate per ID (Regel 1 in `ENTWICKLUNG.md`); automatisch wird der Kern nie geändert.
- [x] KI-Labor: Das vorhandene Werkzeug im Cockpit wird zur Steuerstelle der Cloud-Stufe ausgebaut und in Shell D eingebunden (Spec 3, LAB-01 bis LAB-07).

## Vorarbeiter-Prompt

Der Prompt für den Vorarbeiter liegt bewusst nicht in dieser Datei, weil er Laufwerkspfade dieses PCs enthält (Regel 10 in `ENTWICKLUNG.md`). Er wird außerhalb des Repos aufbewahrt und als erste Nachricht an die Vorarbeiter-Sitzung gegeben.

## Quellen

- [SEDRA README](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS)
- [docs/README.md – Dokumentenübersicht](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS/blob/main/docs/README.md)
- [docs/ARCHITEKTUR.md](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS/blob/main/docs/ARCHITEKTUR.md)
- [docs/ENTWICKLUNG.md](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS/blob/main/docs/ENTWICKLUNG.md)
- [docs/BETRIEB.md](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS/blob/main/docs/BETRIEB.md)
- [docs/SHELL_WERKZEUG_VERTRAG_v1.md](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS/blob/main/docs/SHELL_WERKZEUG_VERTRAG_v1.md)
- [docs/CHANGELOG.md](https://github.com/DBM-Ger-cmd/Sedra-AI-Assistent-OS/blob/main/docs/CHANGELOG.md)
- [Paperclip README](https://github.com/paperclipai/paperclip)
- [NVIDIA API Catalog – OpenAI-kompatible Endpunkte](https://docsearch.algolia.com/mcp/docs/website/build.nvidia.com)
- [Mammouth als OpenAI-kompatibler Anbieter](https://forum.devolutions.net/topics/51918/openai-compatible-ai-provider-mammouthai)
- [NVIDIA Build: Grenzen des kostenlosen Zugangs](https://medium.com/@vignarajj/beyond-the-hype-supercharging-my-local-development-workflow-with-nvidia-nim-and-opencode-free-6ff12d6f851e)
- [NVIDIA-Forum: keine Erhöhung im kostenlosen Zugang](https://forums.developer.nvidia.com/t/request-for-nvidia-build-api-rate-limit-increase-40-rpm-200-rpm/377433)
- [Mammouth: Pläne und API-Guthaben (aipicks.jp)](https://aipicks.jp/tool/mammouth-ai/pricing)
- [LinkedIn: programmatische Refresh-Token (Microsoft Learn)](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens)
- [LinkedIn Posting API Guide (Zernio)](https://zernio.com/blog/linkedin-posting-api)
- [Facebook Graph API Posting Guide (Postproxy)](https://postproxy.dev/blog/facebook-graph-api-posting-guide/)
- [Instagram Content Publishing (Meta for Developers)](https://developers.facebook.com/docs/instagram-platform/content-publishing)
- [WhatsApp Business API: Grenzen und 24-Stunden-Fenster (Zoko)](https://www.zoko.io/post/whatsapp-business-api-message-limitations)
