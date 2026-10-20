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

SEDRA hat für die meisten Paperclip-Systeme schon ein Gegenstück; die echten Lücken sind parallele Agenten, Agenten-Zuweisung mit Herzschlag, Budgets je Agent und die Gates der Cloud-Stufe. Die Tabelle wurde am 20.10.2026 vom Vorarbeiter Zeile für Zeile gegen den lokalen Stand geprüft (Branch `release-vorbereitung`, Commit `6e4b0c3`, Build 25; GitHub `main` steht auf dem Stand vom 16.10.2026) und mit G1-S0-a vom Captain freigegeben.

Wichtig: Im Konzept `UIX_KOMMANDODECK_v1.md` hat der Captain schon entschieden, Paperclip „als Vorbild, nicht Einbau“ zu nutzen. Spec 0 baut darauf auf. Geprüfte Paperclip-Kopie: Pakete `cli`, `server`, `ui`, `shared`, `db` in Version 0.3.1 (die Wurzel-`package.json` hat keine Version), neueste Release-Notiz `v2026.916.1`, lokale Kopie vom 20.10.2026.

| Paperclip-System | Gegenstück in SEDRA | Stand (geprüft 20.10.2026) | Spec |
| --- | --- | --- | --- |
| Org-Chart & Agenten | `agent_manager/`: Vorlagen, Instanzen, Crews, `hire`, `promote` | teilweise – es gibt weder `reports_to` noch einen Vorgesetzten | 1 |
| Aufgaben mit atomarem Checkout | `core/mission.py` (12 Zustände), `core/mission_lock.py` (Dateisperre des Betriebssystems), Desk-Objekt `task` | teilweise – keine Zuweisung an einen Agenten, keine Blocker, keine Kommentare | 1 |
| Heartbeat-Ausführung | `jobs/job_supervisor.py` (Warteschlange, Claim, Lease, Herzschlag, Stillstand) | teilweise – weckt Jobs, nicht Agenten bei Zuweisung | 1 |
| Parallele Ausführung | `jobs/testlab.py` GPU-Lease (ein Prozess) und Tabelle `reservations` mit Priorität; `llama_server_runtime.py` startet schon mit `-np 1..8`; `resource_scheduler.py` | teilweise – Grundlage da, kein Rezept setzt `parallel`, ein Slot-Scheduler fehlt | 2 |
| Adapter | lokal: `models/router.py`, `llamacpp.py`, `openai_local.py`, `lmstudio.py`; Cloud: `models/cloud_api.py` (OpenAI-kompatibel und Anthropic, seit 16.10.2026), `cloud_settings.py`, `config/cloud_providers.yaml` (Standard aus), Inhaltsschutz `core/content_guard.py` | vorhanden – Cloud ist echt, nicht simuliert; die README („keine Cloud-Modelle“) ist veraltet | 3 |
| Governance & Freigaben | `core/guard.py` (28 Aktionen in `architecture/…/core/guard/guard_rules.yaml`), `permission_levels.py`, `desk/decisions.py` | vorhanden, strenger als Paperclip; noch keine Aktionen für die Orchestrierung | – |
| Budget & Kosten | `jobs/token_policy.py` (Ausgabegrenzen je Aufruf), Grenzen in `desk/boundaries.py`, Werkzeug `costs` | teilweise – kein Budget je Agent oder Aufgabe mit Hard-Stop | 1, 3 |
| Routinen & Zeitpläne | Objekttyp `routine` im Vertrag; Ketten wie `benchmarks/day_queue_*.py` | fehlt – Eintrag in Build 24 entfernt, weil kein Werkzeug dahinter war | 1 |
| Activity & Events | `core/audit.py` (hash-verkettet), `desk/events.py` (SSE: `task.changed`, `decision.pending`, `decision.answered`, `live.line`, `model.changed`, `system.state`) | vorhanden | – |
| Plugins | Shell-Werkzeug-Vertrag, Gate `install_module`, E1-Integration | vorhanden (Oberfläche), Backend nur E1 | – |
| Workspaces & Sandbox | `devenv/devvm.py`, microVM über microsandbox | vorhanden für Bauten | – |
| Secrets | Secret-Speicher: Umgebungsvariable `GUPPI_SECRET_*` oder `local_config/cloud_keys.json`, verschlüsselt mit Windows-DPAPI (`cloud_settings.py`); Verweise als `secret://anbieter/id`; Schwärzung im Audit | vorhanden für Cloud-Schlüssel (G1-S0-f); ein Speicher je Agent fehlt | 3 |
| KI-Labor | Werkzeug `labor` (CORE) mit `labor.py`, `labor_runs.py`, 8 eigenen Routen (`/api/cloud/*`, `/api/labor/*`), Instrument `gauge-cloud` | vorhanden – Speichern, Schlüssel und Tests nur mit Audit (`CLOUD_SETTINGS_SAVED`, `CLOUD_KEY_CHANGED`, `LABOR_CONNECTION_TEST`), ohne Guard-Gate; Spezialrouten statt `POST /api/actions` | 3, 4 |
| Oberfläche im Paperclip-Stil | Shell D `uix/shells/paperclip/` v1.1.0 (4 Skripte, 494 Zeilen), Start `START_SEDRA.bat paperclip` | teilweise – Navigation: Dashboard, Posteingang, Issues, Ziele, Agenten, Kosten, Planungstisch, Rekorder, Werkstatt, Bibliothek; es fehlen Organigramm, Routinen, Slots und KI-Labor | 4 |
| Mehrere Organisationen, Export/Import | – | bewusst weggelassen | – |

Desk-Stand (K0.3): Objekttypen `task`, `intent`, `candidate`, `model`, `skill`, `decision`, `project`, `agent`, `boundary` (`routine` fehlt; `agent` ist eingetragen, liefert aber weder Liste noch Einzelansicht). Verben nur für fünf Typen – `task`: ausfuehren; `candidate`: testen, nachpruefen, uebernehmen, zuruecknehmen; `intent`: aufgabe_machen; `boundary`: bestaetigen, aendern; `model`: laden, entladen, testen. Zugang: `POST /api/objects {type, id}` und `POST /api/actions`, Anmeldung über den Kopf `X-GUPPI-Token`; das Audit `UIX_ACTION` nennt keinen Client. Typen und Verben sind fest verdrahtet (`uix_server.objects_view`, `desk/actions.table()`). Der MCP-Server `state_mcp.py` liest nur.

## Spec 0 – Kern-Architektur und Kern-API

Empfehlung: Variante A. SEDRA bleibt Python, das Desk ist die Kern-API für alle Anwendungsfälle, und die Orchestrierung entsteht als neues Paket außerhalb von `core/`. Der Captain hat am 20.10.2026 entschieden: Variante A mit der Paperclip-Shell D als Arbeitsfläche, die KI-Zentrale bleibt nur eine Option (unten).

### Varianten

| Variante | Was passiert | Aufwand | Risiko | Passung zu SEDRA |
| --- | --- | --- | --- | --- |
| A – Python, Desk als API (gewählt) | Paperclip-Funktionen als Paket `guppi_runtime/orchestra/`, angeboten über Desk-Objekte und Verben | mittel | gering – Kern, Guard und 187 Testdateien bleiben | hoch; entspricht „Vorbild, nicht Einbau“ |
| B – Paperclip daneben | Paperclip-Server (Node 24, pnpm, Postgres) läuft neben SEDRA, spricht SEDRA über einen Adapter an | mittel bis hoch | mittel – zwei Stacks, zwei Rechtesysteme, Guard muss jeden Paperclip-Aufruf decken | gering; widerspricht der früheren Entscheidung |
| C – Neubau in TypeScript | Kern nach Paperclip-Vorbild neu | sehr hoch | hoch – abgenommene SEDRA-Module und Testbasis gehen verloren | gering |

Selbstbau und Option „KI-Zentrale“ (Captain, 20.10.2026): Shell D und die Orchestrierung werden in SEDRA gebaut, auch wenn Teile von Grund auf neu entstehen müssen und der Aufwand groß ist. Eine Shell „KI-Zentrale“ mit Paperclip als Orchestrator daneben bleibt eine Option, die nur der Captain zieht; Voraussetzung ist KERN-07. Ist KERN-07 nicht erfüllbar, scheidet Paperclip als Orchestrator aus, und es wird eine andere Lösung gesucht.

Dafür kommt KERN-07 hinzu: WENN Paperclip als Orchestrator angebunden wird, DANN SOLL es SEDRA-Agenten nur über die Kern-API wecken und nie am Guard vorbei arbeiten. Abnahme: Ein Paperclip-Herzschlag an einen SEDRA-Agenten (HTTP-Adapter von Paperclip) erzeugt eine SEDRA-Mission mit Gate und Audit, und Kosten erscheinen in beiden Systemen.

### Anforderungen

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| KERN-01 | Das System SOLL Agenten, Aufgaben, Routinen und Budgets als Desk-Objekte in der Form `{type, id, title, state, summary, actions, links}` anbieten. | `POST /api/objects {type: "agent", id}` und `POST /api/objects {type: "issue"}` liefern diese Form (G1-S0-b: keine neue GET-Route; Aufgabe des Bretts ist Typ `issue`, `task` bleibt die Mission – OP-1, G2) |
| KERN-02 | WENN ein Verb auf einem Objekt ausgeführt wird, DANN SOLL es über `POST /api/actions` und das Gate dieses Verbs laufen. | Gleiches Verb aus Shell, Gespräch und CLI erzeugt denselben Audit-Eintrag `UIX_ACTION`; er unterscheidet sich nur im Feld `client` (`shell`, `chat`, `cli`, `mcp`; G1-S0-c) |
| KERN-03 | Das Paket `core/` SOLL nur über einzeln freigegebene Gates geändert werden (Grundsatzfreigabe des Captains vom 20.10.2026). | Diff in `core/` nur mit Gate-ID im Logbuch; `tests.test_core_boundary_src` grün |
| KERN-04 | WENN ein neuer Anwendungsfall dazukommt, DANN SOLL er als Objekttyp, Verben und Werkzeug ergänzt werden können, ohne `uix_server.py` zu ändern. | Ein Beispiel-Objekttyp wird nur über Registrierung eingebunden. Die Registrierung selbst ändert `uix_server.py` und `desk/` einmal (G1-S0-d); danach gilt die Anforderung ohne Ausnahme |
| KERN-05 | Externe Clients (CLI, MCP, später ein Paperclip-Adapter) SOLLEN dieselbe API mit Token (`X-GUPPI-Token`) nutzen. | Ein Aufruf über MCP legt eine Aufgabe an, `UIX_ACTION` trägt `client: "mcp"` |
| KERN-06 | WENN eine Konfiguration des Pakets fehlt oder ungültig ist, DANN SOLL das Paket abschalten und `boot()` den Grund melden. | `guppi doctor` zeigt `orchestra_error` mit Grund |
| KERN-07 | WENN Paperclip als Orchestrator angebunden wird, DANN SOLL es SEDRA-Agenten nur über die Kern-API wecken und nie am Guard vorbei arbeiten. | Paperclip-Herzschlag erzeugt SEDRA-Mission mit Gate und Audit; Kosten in beiden Systemen |

### Design

Stand 20.10.2026, ausgearbeitet in K0.5 gegen den Code auf Branch `spec/agenten-orchestrierung` (Commit `4dcae78`). Vorlage für G2; jede Zeile der Gate-Liste (D6) wird einzeln entschieden. Spec 0 baut nur die Andockstelle und das leere Paket mit Datenmodell, Konfiguration und Schalter; die Fachlogik von `org`, `board`, `heartbeat`, `budget` und `routines` baut Spec 1 auf dieser Grundlage.

Schichten von unten, jede Schicht importiert nur nach unten:

| Schicht | Inhalt | darf importieren |
| --- | --- | --- |
| 1 `core/` | Guard, Audit, Mission, Util | nur `core/` (`test_core_boundary_src`) |
| 2 `jobs/`, `models/` | Supervisor, Lease, Scheduler, Router | `core/` |
| 3 `orchestra/` (neu) | Organigramm, Aufgabenbrett, Herzschlag, Budget, Routinen | `core/`, `jobs/` (nur über übergebene Objekte, siehe D3) |
| 4 `desk/` | Objekttypen, Verben, Entscheidungen, Ereignisse | alles darunter, `orchestra/` nur im Adapter `desk/orchestra_kinds.py` |
| 5 `uix_server.py` | nur HTTP, Anmeldung, Herkunft (`client`) | `desk/` |
| 6 Shell D, Werkzeuge | Oberfläche | nur `ctx.api()` und `ctx.bus` |

`runtime.py` ist Kompositionswurzel: Es baut `orchestra` zusammen und meldet dessen Fehler in `boot()` (D3.5). Weil `test_core_boundary_src` `runtime.py` mit dem Kern prüft, darf nichts, was `runtime.py` aus `orchestra/` importiert, über Umwege `agent_manager`, `devenv`, `devvm*` oder `coder_ext` erreichen.

#### D1 Desk-Registrierung (KERN-04, G1-S0-d)

Befund: Typen und Verben stehen an vier Stellen fest im Code – `desk/objects.TYPES`, die if-elif-Ketten in `UIXHub.object_view` und `UIXHub.objects_view` (`uix_server.py`), `desk/actions.table()` und zusätzlich `chat_tools.VERB_TYPES`. Typ `agent` steht in `TYPES`, `object_view` wirft für ihn `unknown_object_type`, `objects_view` liefert `items: []`.

Neuer Baustein `desk/kinds.py` (der Name `desk/registry.py` ist schon für Shells und Werkzeuge vergeben):

```
Kind(name, title, read, listing, verbs=(), type_verbs=(), source='desk')
    read(hub, oid)          -> dict | None      ein Objekt in der einen Form, None = nicht gefunden
    listing(hub, payload)   -> list[dict]       die Liste des Typs (payload kann filtern)
    verbs                   -> [actions.Verb]   Verben am Objekt (unverändert: verb, label, run, needs_gate, when, confirm)
    type_verbs              -> [actions.Verb]   Verben ohne Objekt, z. B. „anlegen“ (run(hub, None, args))

register(kind)      einmal je Name; Name nach ^[a-z][a-z0-9_]{1,31}$; doppelter Name → ValueError('kind_already_registered')
freeze()            nach dem Start der Oberfläche keine Registrierung mehr (kein Andocken über eine Anfrage)
names(), get(name), view(hub, kind, oid), listing(hub, kind, payload), problems
```

`view` und `listing` setzen `actions` aus `actions.offered(obj)` und prüfen die Form (`type, id, title, state, summary, actions, links`); fehlt ein Schlüssel, antwortet die Route mit `object_shape_invalid` statt mit einem halben Objekt.

Was sich einmal ändert:

| Datei | Änderung | Gate |
| --- | --- | --- |
| `desk/kinds.py` | neu, wie oben | G2-S0-01 |
| `desk/builtin_kinds.py` | neu: die heutigen Typen `task`, `candidate`, `model`, `intent`, `boundary`, `decision`, `skill`, `project`, `agent` als `Kind`; die Leser sind die heutigen Zweige aus `object_view`/`objects_view`, wörtlich verschoben, sie rufen weiter die Hub-Methoden (`missions()`, `models_view()`, `_intent_object`, `_candidate_report` …) | G2-S0-01 |
| `desk/extensions.py` | neu: Liste der Module, die beim Start `register(kinds, hub)` aufrufen (zuerst `desk.orchestra_kinds`); ein neuer Anwendungsfall ist ein Modul plus eine Zeile hier, `uix_server.py` bleibt unberührt | G2-S0-01 |
| `desk/objects.py` | `TYPES` wird aus dem Register gelesen (Kompatibilität für bestehende Importe); Bauer der Objekte bleiben | G2-S0-01 |
| `desk/actions.py` | `VERBS`/`table()` lesen die Verben aus dem Register; `run()` wie heute, dazu `run_type()` für Verben ohne Objekt | G2-S0-01 |
| `uix_server.py` | `object_view`/`objects_view` werden zwei Zeilen (`kinds.view`/`kinds.listing`); `act` nimmt `client` (D2) und erlaubt Verben ohne `id`, wenn der Typ ein `type_verb` dieses Namens hat; beim Start `builtin_kinds.register()`, `extensions.load(hub)`, `kinds.freeze()` | G2-S0-02 (deckt G1-S0-d und D2 zusammen) |
| `chat_tools.py` | `VERB_TYPES` aus dem Register statt fest | G2-S0-03 (von G1-S0-d nicht gedeckt, siehe Offene Punkte) |

Migration ohne Verhaltensänderung:

1. Vor dem Umbau einen Golden-Test schreiben (`tests/test_desk_kinds.py::Golden`): Für jeden heutigen Typ werden `objects_view({type})` und `object_view(type, id)` auf dem Fake-Host mit Testdaten aus `tests/fixtures/` aufgezeichnet, ebenso die Fehler (`unknown_object_type`, `not_found`). Die Aufzeichnung entsteht mit dem alten Code und wird eingecheckt.
2. Umbau. `agent` wird als Platzhalter registriert, der genau das heutige Verhalten nachbildet (Einzelansicht `unknown_object_type`, Liste leer). Ist `orchestra` eingeschaltet, ersetzt `desk/orchestra_kinds.py` den Platzhalter (einziger erlaubter Ersatz, `register(kind, replace_placeholder=True)`).
3. Der Golden-Test muss unverändert grün sein, dazu die vorhandenen Tests:

| Vorhandener Test | sichert |
| --- | --- |
| `tests/test_desk_objects.py` | Form jedes Objekts, Verben nur im passenden Zustand, nicht angebotene Verben laufen nicht, unbekannte Typen und Verben abgewiesen, `UIX_ACTION` geschrieben, Listen gleicher Form |
| `tests/test_desk_intent_stufen.py`, `tests/test_desk_boundaries.py` | Verben `aufgabe_machen`, `bestaetigen`, `aendern` mit Gates |
| `tests/test_uix_guppi_moves.py` | Gespräch: `list_actions`, `propose_action` lesen dieselben Verben |
| `tests/test_uix_server.py`, `tests/test_uix_flows.py` | Routen `/api/objects`, `/api/actions` über HTTP |
| `tests/test_uix_contract.py`, `benchmarks/uix_check.py` | Werkzeuge im Browser unverändert (`result ok` für alle Shells) |
| `tests/test_core_boundary_src.py` | Kern unberührt |

Neu in `tests/test_desk_kinds.py`: Beispieltyp `echo` (nur im Test) wird über `extensions` registriert, ist über `POST /api/objects` und `POST /api/actions` erreichbar, und `uix_server.py` enthält keinen Typnamen mehr (Prüfung per `ast`: keine Vergleiche `kind == '<typ>'` in `object_view`/`objects_view`).

#### D2 Feld `client` im Audit `UIX_ACTION` (KERN-02, KERN-05, G1-S0-c)

Heute gibt es genau einen Token je Serverstart (`secrets.token_urlsafe(32)` in `make_server`), er lebt nur im Speicher und erreicht die Seite über das URL-Fragment. CLI und MCP haben deshalb heute gar keinen Weg zur API (`state_mcp.py` liest Dateien direkt, `guppi doctor` ruft die Runtime im Prozess).

Grundsatz: Der Server setzt `client`, nie der Aufrufer. Ein Feld `client` im Körper einer Anfrage wird mit `400 client_is_set_by_server` abgewiesen und als `UIX_CLIENT_REFUSED` protokolliert, damit ein Fälschungsversuch sichtbar wird.

| Wert | Ermittlung im Server | fälschbar durch |
| --- | --- | --- |
| `shell` | Browser-Token (wie heute), kein oder ein anderer `X-SEDRA-Tool`-Kopf | – |
| `chat` | Browser-Token und `X-SEDRA-Tool` ∈ {`talk`, `planung`} (die Gesprächswerkzeuge; Liste in `desk/kinds.py`), der Kopf hat die Allowlist-Prüfung (§6) bestanden | Code in derselben Seite (siehe Vertrauensgrenze) |
| `cli` | eigener CLI-Token | wer die CLI-Tokendatei lesen kann |
| `mcp` | eigener MCP-Token | wer die MCP-Tokendatei lesen kann |

Client-Token: Beim Start erzeugt der Server je externem Client (`cli`, `mcp`) einen eigenen Zufallstoken und schreibt ihn mit Port und PID nach `workspace/GUPPI_OS/runtime_data/uix/clients/<client>.json` (atomar; der Token unter Windows mit DPAPI wie `cloud_keys.json`, sonst Datei mit Rechten 0600). Die Zuordnung Token → Client steht nur im Speicher des Servers. Beim Beenden werden die Dateien gelöscht, beim nächsten Start neu erzeugt. Anmeldung bleibt der Kopf `X-GUPPI-Token`; `_authorized()` liefert statt `True` den Client-Namen. Das ändert die Token-Semantik (Regel 6) und ist deshalb ein eigenes Gate (G2-S0-05).

Vertrauensgrenze: Alle Token-Halter sind dasselbe Windows-Konto auf Loopback; `client` ist eine Herkunftsangabe für Audit und Abnahme, keine Berechtigung. Kein Verb und kein Gate hängt von `client` ab. Zwischen den Token-Klassen (Browser, CLI, MCP) ist die Angabe nicht fälschbar, ohne die Tokendatei der anderen Klasse zu lesen. Innerhalb der Browserseite (`shell` gegen `chat`) ist sie eine Selbstauskunft: Werkzeug-Code in der Seite könnte den Kopf eines anderen Werkzeugs setzen. Das ist hinnehmbar, weil Werkzeuge mit Rang `COMMUNITY` nur `GET`-Routen bekommen und `POST /api/actions` damit für sie gesperrt ist.

Audit: `UIX_ACTION` bekommt `payload = {type, id, verb, client}`; sonst bleibt der Eintrag gleich. `core/audit.py` bleibt unverändert (die Nutzlast ist frei).

Externe Clients:

- CLI: neue Befehle `guppi objects <typ> [<id>]` und `guppi act <typ> <id|-> <verb> [--args JSON]`; sie lesen `clients/cli.json` und rufen `POST /api/objects` bzw. `POST /api/actions` über Loopback. Läuft keine Oberfläche: Fehler `uix_not_running`, kein Weg am Desk vorbei (G2-S0-06).
- MCP: neuer Server `desk_mcp.py` mit den Werkzeugen `objects` und `act`, Prüfung der Anfragen mit `mcp_shield` wie `state_mcp.py`, Aufruf über `clients/mcp.json`. `state_mcp.py` bleibt rein lesend (G2-S0-07).

#### D3 Paket `orchestra/`

##### D3.1 Module

| Modul | Aufgabe | importiert innerhalb des Pakets |
| --- | --- | --- |
| `__init__.py` | leer bis auf `__all__`; importiert nichts, damit `runtime.py` nur `config` und `store` lädt | – |
| `config.py` | `OrchestraConfig.load(path)`: liest und prüft `orchestra.yaml`, wirft `ValueError('orchestra_config_…')` | – |
| `store.py` | SQLite-Verbindung (WAL, `busy_timeout=30000`, `foreign_keys=ON`), Schema, Migrationen über `meta.schema_version`, Helfer `immediate()` für `BEGIN IMMEDIATE` | `config` |
| `org.py` | Agenten, Rollen, Vorgesetzte, Zyklusprüfung, Rechte nur senken (ORC-01, 02, 08, 12) | `store` |
| `board.py` | Aufgaben, Zuweisung, atomarer Checkout, Blocker, Kommentare, Zielkette (ORC-03, 04, 05, 13) | `store`, `org` |
| `budget.py` | Verbrauch buchen (`spend`), Schwellen 80/100 % (ORC-09) | `store` |
| `heartbeat.py` | fällige Weckrufe lesen, je Agent zusammenfassen, Lauf übergeben, Stillstand (ORC-06, 07, 11) | `store`, `board`, `org`, `budget` |
| `routines.py` | Cron-Auswertung, Nachhol-Regel, `routine_runs` (ORC-10) | `store`, `board` |
| `service.py` | Fassade `Orchestra` für Desk und Runtime: hält die Teile, nimmt Audit, Guard, `job_supervisor` und einen Vorlagen-Leser als übergebene Objekte | alle |

Importregeln (neuer Test `tests/test_orchestra_boundary.py` mit `core_boundary.violations`/`chains`): `orchestra/` darf `guppi_runtime.core` und `guppi_runtime.jobs` importieren, sonst nur Standardbibliothek und `yaml`. Verboten: `desk`, `uix_server`, `uix`, `chat_tools`, `agent_manager`, `devenv`, `devvm*`, `coder_ext`, `models.cloud_api`. Vorlagen und Instanzen des Agent Managers kommen über eine übergebene Funktion (`templates(ref) -> dict`), die der Desk-Adapter aus `agent_manager` baut; nur so bleibt `runtime.py` unter `test_core_boundary_src` grün.

##### D3.2 Schnittstelle zum Desk

`desk/orchestra_kinds.py` (eingetragen in `desk/extensions.py`) registriert die Typen nur, wenn `hub.runtime.orchestra` existiert. Mit Schalter aus bleibt alles wie heute.

| Typ | Leser | Verben am Objekt (Gate) | Verben ohne Objekt |
| --- | --- | --- | --- |
| `agent` (ersetzt den Platzhalter) | `org` | `zuweisen_an` (`assign_task`), `wecken` (`wake_agent`), `pausieren` (`pause_agent`), `fortsetzen` (`resume_agent`), `beenden` (`terminate_agent`), `einordnen` (`set_org`) | `einstellen` (`agent.instantiate` + `set_org`) |
| `issue` (Aufgabe des Bretts, Vorschlag; siehe Offene Punkte) | `board` | `zuweisen` (`assign_task`), `blocker_setzen`, `kommentieren` (`create_new_artifact`), `abbrechen` | `anlegen` (`create_new_artifact`) |
| `routine` | `routines` | `aendern`, `ausschalten` (`set_routine`) | `anlegen` (`set_routine`) |
| `budget` (id = Agent-ID) | `budget` | `festlegen` (`set_budget`) | – |

Jedes Verb mit `needs_gate` folgt dem vorhandenen Muster von `boundaries_request`/`boundaries_apply`: Antrag erzeugt eine Mission mit Gate und Bindung, die Entscheidung läuft über `desk/decisions.py`, das Ausführen prüft den Einmal-Token mit `guard.authorize`. Damit dafür kein Code in `uix_server.py` nötig ist, kommt der Ablauf als Helfer `desk/gated.py` (Antrag, Anwenden) in die Registrierung (Teil von G2-S0-01). Ergebnisse schreibt `orchestra` als Audit-Ereignisse (`ORC_AGENT_HIRED`, `ORC_TASK_ASSIGNED`, `ORC_TASK_CHECKED_OUT`, `ORC_WAKE`, `ORC_BUDGET_WARNING`, `ORC_BUDGET_STOP`, `ORC_ROUTINE_FIRED`), ohne Inhalt von Kommentaren. `desk/events.py` übersetzt sie in Spec 4 zu `agent.changed`, `budget.warning`.

Der Herzschlag braucht einen Takt. `desk/extensions.py` darf je Modul ein `start(hub)` anbieten; `orchestra_kinds.start` startet einen Daemon-Thread, der `heartbeat.tick()` und `routines.tick()` im eingestellten Abstand ruft, nur bei eingeschaltetem Schalter. Wer außer der Oberfläche taktet (z. B. ohne laufende UIX), entscheidet Spec 1 (Offene Punkte).

##### D3.3 Datenmodell `orchestra.db`

Ablage `workspace/GUPPI_OS/runtime_data/orchestra/orchestra.db`, WAL wie `testlab.db`. Geschrieben wird nur in Transaktionen; `core/util.atomic_write_*` gilt für Dateien, nicht für SQLite (siehe Offene Punkte). Zeiten als UTC-Text (ISO 8601, wie Audit), Geld als ganze Cent. Abgestimmt mit dem Datenmodell von Spec 1; Abweichungen stehen in der letzten Spalte.

| Tabelle | Spalten (Typ, Pflicht) | Schlüssel und Indizes | gegenüber Spec 1 |
| --- | --- | --- | --- |
| `meta` | `key TEXT`, `value TEXT NOT NULL` | PK `key`; enthält `schema_version` | neu |
| `agents` | `id TEXT`, `instance_id TEXT NOT NULL`, `template_id TEXT NOT NULL`, `name TEXT NOT NULL`, `role TEXT NOT NULL`, `recipe_id TEXT`, `reports_to TEXT`, `status TEXT NOT NULL` CHECK (`aktiv`,`pausiert`,`beendet`), `permission_level INTEGER NOT NULL` CHECK 0–6, `budget_tokens INTEGER`, `budget_eur_cent INTEGER`, `budget_period TEXT NOT NULL DEFAULT 'gesamt'` CHECK (`gesamt`,`monat`), `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`, `revision INTEGER NOT NULL DEFAULT 1` | PK `id`; UNIQUE `instance_id`; FK `reports_to` → `agents(id)`; Index `(reports_to)`, `(status)` | `instance_id`, `name`, `permission_level`, `budget_period`, `revision` neu; `budget_eur` als Cent |
| `tasks` | `id TEXT`, `title TEXT NOT NULL`, `description TEXT`, `goal_ref TEXT`, `project_id TEXT`, `parent_id TEXT`, `assignee TEXT`, `state TEXT NOT NULL` CHECK (`offen`,`zugewiesen`,`in_arbeit`,`wartet`,`erledigt`,`abgebrochen`), `priority INTEGER NOT NULL DEFAULT 0`, `checkout_by TEXT`, `checkout_at TEXT`, `checkout_run TEXT`, `mission_id TEXT`, `created_by TEXT NOT NULL`, `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`, `revision INTEGER NOT NULL DEFAULT 1` | PK `id`; FK `parent_id` → `tasks(id)`, `assignee` → `agents(id)`; Index `(assignee, state)`, `(parent_id)`, `(mission_id)`, Teilindex `(checkout_by) WHERE checkout_by IS NOT NULL` | `goal_id` heißt `goal_ref` (verweist auf ein Vorhaben `intent`); `project_id`, `priority`, `checkout_run`, `created_by`, `revision` neu |
| `blockers` | `task_id TEXT NOT NULL`, `blocked_by_task_id TEXT NOT NULL`, `created_at TEXT NOT NULL` | PK `(task_id, blocked_by_task_id)`; CHECK `task_id <> blocked_by_task_id`; FK beide → `tasks(id)`; Index `(blocked_by_task_id)`; Zyklen prüft `board.py` | – |
| `comments` | `id INTEGER`, `task_id TEXT NOT NULL`, `author_kind TEXT NOT NULL` CHECK (`captain`,`agent`,`system`), `author_id TEXT`, `text TEXT NOT NULL`, `ts TEXT NOT NULL` | PK `id` AUTOINCREMENT; FK `task_id`; Index `(task_id, ts)` | `author` aufgeteilt in Art und ID |
| `wakeups` | `id INTEGER`, `agent_id TEXT NOT NULL`, `task_id TEXT`, `reason TEXT NOT NULL` CHECK (`zugewiesen`,`antwort`,`routine`,`captain`,`wiederholung`), `due_at TEXT NOT NULL`, `created_at TEXT NOT NULL`, `coalesced_into INTEGER`, `job_id TEXT`, `done_at TEXT` | PK `id`; FK `agent_id`, `coalesced_into` → `wakeups(id)`; Teilindex `(agent_id, due_at) WHERE done_at IS NULL AND coalesced_into IS NULL` | `task_id`, `job_id`, `done_at` neu |
| `routines` | `id TEXT`, `agent_id TEXT NOT NULL`, `title TEXT NOT NULL`, `cron TEXT NOT NULL`, `timezone TEXT NOT NULL DEFAULT 'Europe/Berlin'`, `catch_up TEXT NOT NULL` CHECK (`nachholen`,`auslassen`), `enabled INTEGER NOT NULL DEFAULT 1`, `task_template TEXT NOT NULL` (JSON), `last_run TEXT`, `next_run TEXT` | PK `id`; FK `agent_id`; Teilindex `(next_run) WHERE enabled = 1` | `title`, `timezone`, `enabled`, `task_template`, `next_run` neu |
| `routine_runs` | `routine_id TEXT NOT NULL`, `due_at TEXT NOT NULL`, `task_id TEXT`, `outcome TEXT NOT NULL` CHECK (`erzeugt`,`ausgelassen`,`nachgeholt`) | PK `(routine_id, due_at)` – derselbe Termin erzeugt nie zwei Aufgaben | neu |
| `spend` | `id INTEGER`, `agent_id TEXT NOT NULL`, `task_id TEXT`, `mission_id TEXT`, `provider TEXT NOT NULL` CHECK (`lokal`,`cloud`), `provider_id TEXT`, `model TEXT`, `tokens_in INTEGER NOT NULL DEFAULT 0`, `tokens_out INTEGER NOT NULL DEFAULT 0`, `requests INTEGER NOT NULL DEFAULT 1`, `eur_cent INTEGER NOT NULL DEFAULT 0`, `ts TEXT NOT NULL` | PK `id` AUTOINCREMENT; Index `(agent_id, ts)`, `(provider_id, ts)`, `(task_id)` | `tokens` aufgeteilt; `provider_id`, `model`, `requests`, `mission_id` neu (Spec 3 braucht Anfragen je Minute/Tag) |

Checkout wie in Spec 1: `BEGIN IMMEDIATE`, `UPDATE tasks SET checkout_by=?, checkout_at=?, checkout_run=?, revision=revision+1 WHERE id=? AND checkout_by IS NULL AND state IN ('zugewiesen','offen')` und Erfolg nur bei genau einer Zeile; vor dem Update prüft dieselbe Transaktion, dass kein offener Blocker besteht. Fremdschlüssel auf Agenten des Agent Managers (`instance_id`) liegen in einer anderen Datenbank und werden nur beim Einstellen geprüft.

##### D3.4 Konfiguration und Schalter

`runtime/config/orchestra.yaml` (Paket-Vorgabe, im Git):

```yaml
orchestra:
  schema: 1
  enabled: false                 # der Schalter in local_config/switches.yaml schaltet ein
  database: orchestra/orchestra.db    # relativ zu runtime_data, kein absoluter Pfad, kein ..
  heartbeat: {tick_s: 5, coalesce_s: 2, max_runs_per_tick: 1}
  checkout: {stall_s: 900}       # ORC-11; Grenzen wie job_supervisor (2..86400)
  budget: {warn_percent: 80, stop_percent: 100}
  routines: {max_catch_up: 3}
  org: {max_depth: 6}
```

Prüfung in `config.py`: unbekannte Schlüssel abgewiesen, Zahlen mit Grenzen wie `SupervisorConfig._int`, `warn_percent < stop_percent`, `coalesce_s < tick_s`, `database` relativ und ohne `..`.

Schalter: `local_switches.ALLOWED` bekommt `"orchestra": {"enabled"}`; Standard aus, weil die Paket-Vorgabe `enabled: false` sagt (G2-S0-10).

##### D3.5 Verhalten bei fehlender oder ungültiger Konfiguration (KERN-06)

`runtime.py` bekommt `_configure_orchestra(data)` über das vorhandene Muster `_optional("orchestra", build)` (G2-S0-11):

| Lage | `rt.orchestra` | `rt.orchestra_error` | Desk |
| --- | --- | --- | --- |
| Schalter aus (Standard) | `None` | `None` | Typen wie heute, `agent` Platzhalter |
| Schalter an, Datei fehlt | `None` | `orchestra_config_missing` | wie Schalter aus |
| Schalter an, Datei ungültig | `None` | `orchestra_config_invalid:<feld>` | wie Schalter aus |
| Datenbank nicht zu öffnen oder Schema neuer als der Code | `None` | `orchestra_db_error:<grund>` | wie Schalter aus |
| alles gültig | `Orchestra` | `None` | Typen `agent`, `issue`, `routine`, `budget` registriert |

`boot()` bekommt `"orchestra": {"enabled": bool, "error": str|None, "schema_version": int|None}`. Der Zustand `READY` hängt davon nicht ab (wie bei `job_supervisor`). `guppi doctor` gibt `boot()` aus und zeigt den Eintrag damit ohne Änderung an `cli.py`. Ein Fehler wird zusätzlich einmal als `ORCHESTRA_OFF` mit Grund ins Audit geschrieben.

#### D4 Neue Guard-Aktionen

Neue Regeln kommen in `architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT/core/guard/guard_rules.yaml` (GR-029 ff.) und je ein Eintrag in `runtime/config/permission_levels.yaml`, weil eine dort fehlende Aktion als `missing_permission` gesperrt würde. Jede Zeile ist ein eigenes Gate (Regel 6). Hinweis: Der Guard behandelt eine unbekannte Aktion als `CAPTAIN_REQUIRED`; heute laufen so schon `install_module`, `set_project_boundaries`, `change_switch`, `agent.instantiate` ohne eigene Regel. Für die Orchestrierung wird jede Aktion ausdrücklich eingetragen, damit die Entscheidung im Regelwerk steht und nicht im Standard. Die Spalte „Stufe“ ist die Obergrenze aus `permission_levels.yaml` (0 READ_ONLY … 6 EXTERNAL_ACTION): Sie sagt, ab welcher Rechte-Stufe ein Agenten-Job die Aktion überhaupt anfragen darf. Verwaltungsaktionen des Captains stehen auf 5 (SYSTEM_CHANGE), damit ein Agent sie nie selbst anfragt; `tests/test_permission_levels.py` hält Regeln und Stufen gleich.

| Gate | Aktion | Bedeutung | Vorschlag | Stufe | Begründung |
| --- | --- | --- | --- | --- | --- |
| G2-S0-GA-01 | `set_org` | Agent ins Organigramm aufnehmen, Vorgesetzten, Rolle oder Rezept ändern | CAPTAIN_REQUIRED | 5 | ändert, wer wem Arbeit und Rechte geben darf (ORC-01, 02, 08) |
| G2-S0-GA-02 | `assign_task` | Aufgabe einem Agenten zuweisen oder umhängen | ALLOW | 2 | legt nur einen Datensatz an, startet nichts; der Lauf hat sein eigenes Gate (`wake_agent`); Audit `ORC_TASK_ASSIGNED` |
| G2-S0-GA-03 | `delegate_task` | Agent legt Teilaufgabe für einen Agenten unter sich an | ALLOW | 2 | `org.py` prüft vorher Richtung und Rechte (ORC-08); eine Verletzung wird im Code abgewiesen und protokolliert, der Guard sieht nur gültige Delegationen |
| G2-S0-GA-04 | `wake_agent` | Agentenlauf starten (Mission mit Modell) | CAPTAIN_REQUIRED | 4 | „Jeder Lauf, der Modelle startet, ist ein Gate“ (ARCHITEKTUR §5); für automatisches Wecken siehe Offene Punkte (Dauerfreigabe) |
| G2-S0-GA-05 | `pause_agent` | Agent anhalten, laufende Aufgabe freigeben | ALLOW | 2 | macht das System nur sicherer (ORC-12) |
| G2-S0-GA-06 | `resume_agent` | angehaltenen Agenten fortsetzen | CAPTAIN_REQUIRED | 5 | hebt eine Pause auf, auch die Pause nach Budget-Stopp |
| G2-S0-GA-07 | `terminate_agent` | Agent beenden (Status `beendet`, endgültig) | CAPTAIN_REQUIRED | 5 | nicht rücknehmbar im Organigramm |
| G2-S0-GA-08 | `set_budget` | Budget eines Agenten festlegen oder erhöhen (auch nach 100 %) | CAPTAIN_REQUIRED | 5 | Budget ist eine Grenze des Captains (ORC-09) |
| G2-S0-GA-09 | `set_routine` | Routine anlegen, ändern, ausschalten | CAPTAIN_REQUIRED | 5 | erzeugt künftig Arbeit ohne weiteren Klick (ORC-10) |
| G2-S0-GA-10 | `fire_routine` | fällige Routine legt eine Aufgabe an | ALLOW | 2 | legt nur eine Aufgabe an; der Lauf braucht `wake_agent` |

Wiederverwendet statt neu:

| Vorhandene Aktion | wofür | Entscheidung |
| --- | --- | --- |
| `create_new_artifact` (GR-002) | Aufgabe anlegen, Kommentar schreiben | ALLOW |
| `agent.instantiate` (`agent_manager/instances.py`, ohne Regel → CAPTAIN_REQUIRED) | Agent einstellen (Instanz anlegen); danach `set_org` | unverändert |
| `external_write`, `paid_action` | Cloud-Aufrufe eines Agenten (Spec 3) | unverändert |
| – (kein Guard) | Checkout einer Aufgabe | interne Sperre wie `mission_lock`, keine Handlung nach außen |

#### D5 Fehlerfälle und Abnahme

Fehlerfälle:

| Fall | Verhalten |
| --- | --- |
| Typ doppelt registriert | `ValueError('kind_already_registered')` beim Start; Erweiterung wird ausgelassen, Grund in `kinds.problems` und Audit `DESK_KIND_REFUSED`; die eingebauten Typen laufen weiter |
| Erweiterung wirft beim Import oder `register` | wie oben; die Oberfläche startet trotzdem |
| Leser liefert unvollständige Form | `object_shape_invalid` |
| Registrierung nach `freeze()` | `ValueError('kinds_frozen')` |
| Verb ohne `id`, aber kein `type_verb` | `id_required` (wie heute) |
| `client` im Körper | `400 client_is_set_by_server`, Audit `UIX_CLIENT_REFUSED` |
| Token keiner Klasse | `403` wie heute |
| CLI/MCP ohne laufende Oberfläche | `uix_not_running` |
| `orchestra` aus, Typ `issue` angefragt | `unknown_object_type` |
| Datenbank gesperrt | `busy_timeout` 30 s, danach `orchestra_busy`; kein halber Schreibvorgang |
| Checkout von zwei Agenten | genau einer gewinnt (ORC-04), der andere bekommt `task_already_checked_out` |

Abnahme je Anforderung:

| ID | Testdatei | Prüfung |
| --- | --- | --- |
| KERN-01 | `tests/test_orchestra_desk.py` (neu) | Schalter an, Fixture-Datenbank: `POST /api/objects {type:"agent", id}` und `{type:"issue"}`, `{type:"routine"}`, `{type:"budget", id}` liefern genau die Schlüssel `SHAPE`; `{type:"task"}` liefert die Missionsliste unverändert (Golden) |
| KERN-02 | `tests/test_desk_client.py` (neu) | dasselbe Verb (`model/laden` auf Fake-Host) mit Browser-Token, Browser-Token + `X-SEDRA-Tool: talk`, CLI-Token, MCP-Token: vier `UIX_ACTION`, Nutzlasten gleich bis auf `client` = `shell`, `chat`, `cli`, `mcp`; `client` im Körper → 400; fremder Token → 403 |
| KERN-03 | `tests/test_core_boundary_src.py`, Durchsicht | Test grün; `git diff --stat main -- runtime/src/guppi_runtime/core` leer für Spec 0, sonst je Datei eine Gate-ID im Logbuch |
| KERN-04 | `tests/test_desk_kinds.py` (neu) | Golden-Test der neun heutigen Typen; Typ `echo` nur über `extensions` erreichbar über beide Routen; `ast`-Prüfung: keine Typnamen in `object_view`/`objects_view`; doppelter Typ abgewiesen; `freeze()` wirkt |
| KERN-05 | `tests/test_desk_mcp.py` (neu) | MCP-Werkzeug `act` mit `{type:"intent", id, verb:"aufgabe_machen"}` legt eine Aufgabe an; letzter `UIX_ACTION` trägt `client:"mcp"`; Anfrage ohne gültigen MCP-Token scheitert |
| KERN-06 | `tests/test_orchestra_config.py` (neu), `tests/test_local_switches.py` | Schalter aus → `orchestra` `None`, Fehler `None`; Schalter an + Datei fehlt → `boot()["orchestra"]["error"] == "orchestra_config_missing"`; ungültige Werte je Feld → `orchestra_config_invalid:<feld>`; `state` bleibt `READY`; `cli.main(['doctor'])` druckt den Eintrag; Schalter `orchestra` wird angenommen |
| Grenze | `tests/test_orchestra_boundary.py` (neu) | `orchestra/` importiert keine verbotenen Pakete, auch nicht über Umwege |

KERN-07 (nur Bedingung): Ein Paperclip-Adapter ist ein weiterer externer Client mit eigenem Token nach D2 und eigenem Wert für `client`; er ruft nur `POST /api/objects` und `POST /api/actions` (Verb `wecken` am Typ `agent`), bekommt dadurch dieselbe Mission mit Gate (`wake_agent`) und denselben Audit-Eintrag. Kosten meldet SEDRA aus `spend`; der Rückweg der Kosten zu Paperclip ist eigene Arbeit der Option „KI-Zentrale“. Ein neuer Client-Wert ist eine Änderung der Liste aus G1-S0-c und damit ein eigenes Gate.

#### D6 Gate-Vorschläge für G2

Änderungen an `core/`: keine. Spec 0 kommt ohne Eingriff in `guppi_runtime/core/` aus; `core/audit.py` nimmt `client` in der freien Nutzlast auf. Eine spätere Kern-Änderung ist nur vorgemerkt (Dauerfreigabe, Offene Punkte) und nicht Teil von G2.

| Gate | Gegenstand | Art |
| --- | --- | --- |
| G2-S0-01 | Desk-Registrierung: `desk/kinds.py`, `builtin_kinds.py`, `extensions.py`, `gated.py`; `objects.TYPES` und `actions.table()` aus dem Register; Golden-Test | Design |
| G2-S0-02 | einmalige Änderung `uix_server.py`: `object_view`/`objects_view` an das Register, `act` mit `client` und Verben ohne `id`, Start der Erweiterungen (deckt G1-S0-d) | Design |
| G2-S0-03 | einmalige Änderung `chat_tools.py`: `VERB_TYPES` aus dem Register | Design |
| G2-S0-04 | Feld `client` in `UIX_ACTION`, Ermittlung im Server, Abweisung im Körper, Vertrauensgrenze wie D2 | Design |
| G2-S0-05 | Client-Token für `cli` und `mcp` mit Dateien unter `runtime_data/uix/clients/` (Token-Semantik, Regel 6) | Regel 6 |
| G2-S0-06 | CLI-Befehle `guppi objects`, `guppi act` über die API | Design |
| G2-S0-07 | neuer MCP-Server `desk_mcp.py` (schreibend über `/api/actions`); `state_mcp.py` bleibt lesend | Design |
| G2-S0-08 | Paket `orchestra/`: Module, Schichtung, Importregeln, `test_orchestra_boundary.py` | Design |
| G2-S0-09 | Datenmodell `orchestra.db` wie D3.3, inkl. Abweichungen zu Spec 1 (Spec 1 übernimmt es in O1.2) | Design |
| G2-S0-10 | `runtime/config/orchestra.yaml` und Schalter `orchestra` in `local_switches.ALLOWED` | Konfiguration |
| G2-S0-11 | Verdrahtung in `runtime.py` (`_configure_orchestra`, Eintrag in `boot()`); `runtime.py` steht unter `test_core_boundary_src` | Kompositionswurzel |
| G2-S0-12 | Desk-Typen `agent`, `issue`, `routine`, `budget` mit Verben wie D3.2; `task` bleibt die Mission | Design |
| G2-S0-13 | Nachtrag `SHELL_WERKZEUG_VERTRAG_v1.md` §10: Registrierung der Objekttypen, Verben ohne Objekt, neue Typen, Feld `client`, Client-Token | Vertrag |
| G2-S0-14 | Einträge der neuen Aktionen in `runtime/config/permission_levels.yaml` (Stufen wie D4) | Konfiguration |
| G2-S0-GA-01 bis GA-10 | je eine neue Guard-Regel wie D4 (GR-029 bis GR-038) | Guard, Regel 6 |

#### Offene Punkte (K0.5)

| Nr | Lücke oder Widerspruch | Vorschlag |
| --- | --- | --- |
| OP-1 | Desk-Typ `task` ist heute die Mission; KERN-01 und Spec 1 nennen die Aufgabe des Bretts ebenfalls `task`. Beides unter einem Typ hieße zwei Datenquellen und andere Verben – eine Verhaltensänderung bestehender Werkzeuge. | `task` bleibt die Mission; die Aufgabe des Bretts wird Typ `issue` (Paperclip-Begriff, Shell D nennt den Eintrag schon „Issues“) und verweist über `mission_id` auf ihre Missionen. KERN-01 im Abnahmekriterium auf `{type:"issue"}` anpassen. |
| OP-2 | G1-S0-d erlaubt die einmalige Änderung von `uix_server.py` und `desk/`; `chat_tools.VERB_TYPES` ist eine fünfte feste Stelle außerhalb davon. | eigenes Gate G2-S0-03 |
| OP-3 | KERN-05 setzt voraus, dass CLI und MCP den Token haben; heute gibt es nur den flüchtigen Browser-Token. | Client-Token wie D2 (G2-S0-05) |
| OP-4 | `wake_agent` = CAPTAIN_REQUIRED widerspricht dem automatischen Wecken von ORC-06: Guard-Freigaben sind Einmal-Token mit 24 h. Eine Dauerfreigabe (wie SOC-07 für Beiträge) fehlt. | In Spec 1 eine Freigabeart „Dauerfreigabe je Agent“ entwerfen, gebunden an Agent, Rechte-Stufe, Budget und Ablaufdatum; das ist eine Änderung an `core/guard.py` und braucht ein eigenes Kern-Gate. Bis dahin weckt jeder Lauf eine Entscheidung. |
| OP-5 | Spec 0 sagt „atomares Schreiben über `core/util.py`“ für `orchestra.db`; `util` schreibt Dateien atomar, SQLite sichert sich über Transaktionen. | Satz ersetzt durch D3.3 (Transaktionen, WAL); `util` nur für Dateien |
| OP-6 | ORC-02 „außer dem obersten“: ein oberster Agent oder mehrere Wurzeln? | entschieden (Captain, 20.10.2026): genau ein aktiver Agent ohne Vorgesetzten, der **Unterarbeiter**; geprüft in `org.py` |
| OP-7 | Budget-Zeitraum ist offen (gesamt oder je Monat); Spec 3 will ein Monatsbudget. | Spalte `budget_period` (`gesamt`, `monat`); Standard `gesamt` bis zur Auswertung nach vier Wochen |
| OP-8 | Zielkette (ORC-13): Eine Tabelle für Ziele fehlt. | Ziel = Vorhaben (`intent`), Projekt = `project`; `tasks.goal_ref` und `tasks.project_id` verweisen darauf, keine eigene Ziel-Tabelle |
| OP-9 | Herzschlag-Takt läuft nach D3.2 nur, solange die Oberfläche läuft; E2E-6 (Routine fällig, während SEDRA aus war) braucht nur die Nachhol-Regel, aber ein Betrieb ohne UIX hätte keinen Takt. | in Spec 1 entscheiden: Takt in der Oberfläche (Vorschlag) oder eigener Dienst |
| OP-10 | Die Stufe „E2 (Erweiterung)“ aus dem früheren Vorschlag passt nicht zum Weg: `self_integration` übernimmt nur E1-Module nach `capabilities/`. `orchestra/` und die Desk-Teile sind Harness- bzw. Bau-Übernahmen nach Review (G4), keine Selbst-Integration. | in G2 so festhalten; `self_integration` wird nicht geweitet |
| OP-11 | `tests/test_desk_objects.py` liest die Architektur `v1.17_RUNTIME_SYNC`, die Runtime lädt `v1.20_SELF_DEVELOPMENT`. Neue Guard-Regeln kämen nur in v1.20. | prüfen, ob der Test mit v1.20 laufen soll; nicht in Spec 0 ändern |

### Aufgaben

- [x] K0.1 Lokalen Stand gegen GitHub abgleichen: `BUILD.txt`, `docs/CHANGELOG.md`, `git log`
- [x] K0.2 Ist-Tabelle oben Zeile für Zeile gegen den Code prüfen und korrigieren
- [x] K0.3 Desk-Stand prüfen: Welche Objekttypen und Verben gibt es in `desk/objects.py` und `desk/actions.py`?
- [x] K0.4 Variante A mit Befunden aus K0.1–K0.3 gegen den Code bestätigen → G1 (erteilt 20.10.2026, G1-S0-a bis f)
- [x] K0.5 Design `orchestra/` mit Datenmodell und neuen Guard-Aktionen ausarbeiten → G2 (ausgearbeitet 20.10.2026, Abschnitt „Design“ D1 bis D6; G2 erteilt 20.10.2026)
- [ ] K0.6 Nach Freigabe: Logbuch-Eintrag, Doku (README, `ENTWICKLUNG.md`) auf Local First, Cloud Second anpassen

## Spec 1 – Orchestrierung: Agenten, Aufgaben, Herzschlag

Spec 1 macht aus den einzelnen Agenten des Agent Managers ein Team: Organigramm, zugewiesene Aufgaben mit atomarem Checkout, Wecken bei Arbeit, Budgets und Routinen. Ausgeführt wird jede Agentenarbeit weiterhin als Mission durch Brain und Guard.

Erstes Team (Captain, 20.10.2026): Unterarbeiter, Planer, Coder, Reviewer, Recherche. Der **Unterarbeiter** steht oben im Organigramm: Er ist die Instanz direkt unter dem Inhaber (Captain) und beaufsichtigt Planer, Coder, Reviewer und Recherche (OP-6, Captain 20.10.2026; ersetzt „Planer oben“). Anweisungen des Captains an das Team gehen an den Unterarbeiter; er zerlegt, verteilt und berichtet, der Planer hilft beim Zerlegen, delegiert aber nicht (ORC-14). Offen für Spec 1: welches Rezept der Unterarbeiter bekommt. Die Rezepte kommen aus den vorhandenen Rollen `planner`, `coder` und `reviewer` in `role_routing.yaml`; für Recherche wird eine Rolle mit dem lesenden Web-Werkzeug angelegt (Hosts aus `config/web_access.yaml`). Der Reviewer gibt Hinweise, entscheidet aber keine Abnahme: Laut `ENTWICKLUNG.md` sind Modell-Reviewer unzuverlässig, Richter bleibt der versteckte Test.

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
| ORC-14 | WENN der Captain dem Team eine Anweisung gibt, DANN SOLL sie beim Unterarbeiter ankommen; er zerlegt sie in Aufgaben, weist sie den Agenten unter ihm zu und meldet dem Captain das Ergebnis. Nur der Unterarbeiter delegiert (Captain, 20.10.2026). | Eine Anweisung im Gespräch mit dem Unterarbeiter (Shell D, UIX-04) erzeugt Aufgaben bei den Agenten unter ihm, am Ende einen Bericht an den Captain; der Planer kann nicht zuweisen; jeder Lauf braucht `wake_agent` |

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

Cloud wird eine zweite Stufe hinter dem bestehenden Schutz: Jeder Cloud-Aufruf geht durch den Router, den Inhaltsschutz (Build 16) und die Einstufung des KI-GateWays (Build 19) und braucht eine Entscheidung oder eine vom Captain freigegebene Regel. Seit 16.10.2026 gibt es einen echten Cloud-Zugang hinter Schalter und Inhaltsschutz (`models/cloud_api.py`, `cloud_settings.py`, KI-Labor); er läuft aber noch ohne Guard-Gate, ohne Budget und ohne GateWay-Einstufung. Die README sagt weiterhin „keine Cloud-Modelle“. Spec 3 baut den vorhandenen Zugang aus, statt einen neuen zu bauen (G1-S0-e); die README ändert sich erst nach Freigabe dieser Spec.

Anbieter (Captain, 20.10.2026): der NVIDIA API Catalog (Schlüssel vorhanden) und Mammouth (Schlüssel geplant). Beide bieten eine OpenAI-kompatible Schnittstelle, NVIDIA unter `https://integrate.api.nvidia.com/v1`, Mammouth mit eigener Basis-URL laut Mammouth-Doku. Der vorhandene Adapter `models/cloud_api.py` (OpenAI-kompatibel) reicht deshalb für beide, mit je einem Cloud-Rezept. Mammouth leitet an Modelle verschiedener Hersteller weiter; welche Schutzklassen dorthin dürfen, legt die GateWay-Matrix je Anbieter fest. Beide Hosts sind neue Ziele im Netz, also externe Aktionen mit eigener Guard-Regel. Das Budget der Startphase steht im nächsten Abschnitt.

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

Im Cockpit gibt es schon das Werkzeug „KI-Labor“ mit den API-Anbindungen. Es wird zur Steuerstelle der Cloud-Stufe ausgebaut und in Shell D eingebunden, statt ein neues Werkzeug zu bauen. Stand 20.10.2026: Werkzeug `labor` (CORE) mit 8 eigenen Routen (`/api/cloud/*`, `/api/labor/*`); Speichern, Schlüssel und Tests werden protokolliert, laufen aber durch kein Guard-Gate. Die Gates werden nachgerüstet (G1-S0-e).

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| LAB-01 | Das KI-Labor SOLL als Werkzeug nach dem Shell-Werkzeug-Vertrag in jeder Shell laufen, auch in Shell D, ohne Shell-eigenen Code. | `uix_check --tool <id>` meldet `result ok` in Cockpit und Paperclip |
| LAB-02 | WENN der Captain einen Anbieter anlegt (Name, Basis-URL, Modelle), DANN SOLL das über ein Gate laufen und der Schlüssel nur im Secret-Speicher landen. | Schlüssel steht nur im Secret-Speicher (CLD-08), in keinem Log und keinem Audit-Eintrag |
| LAB-03 | Der Captain SOLL je Anbieter einen Kurztest starten können (eine Frage, Antwortzeit, Token); der Test ist eine externe Aktion mit Gate und läuft durch das GateWay. | Testergebnis wie beim Kurztest der Werkstatt, Audit `CLOUD_CALL` |
| LAB-04 | Das KI-Labor SOLL die Grenzen der Startphase zeigen; jede Änderung ist ein Gate. | Anfragen pro Minute und Tag, Abo-Guthaben, Freigaben je Agent sichtbar |
| LAB-05 | Das KI-Labor SOLL den Verbrauch je Anbieter und Agent live zeigen und bei 80 % warnen. | Werte aus `spend`, Ereignis `budget.warning` |
| LAB-06 | Das KI-Labor SOLL je Anbieter zeigen, welche Schutzklassen dorthin dürfen; geändert wird das nur im GateWay. | Anzeige nur lesend, Verweis auf das GateWay |
| LAB-07 | Das KI-Labor SOLL den Schalter `cloud` zeigen; Umschalten ist ein Gate. | Bei aus zeigt das Labor „Cloud-Stufe aus“ |

- [x] L3.1 KI-Labor lokal erfassen: Werkzeug-ID, Manifest, Routen, Vertrauensrang und wo heute Schlüssel liegen (gegen CLD-08 prüfen) – erledigt in K0.2, siehe Ist-Tabelle
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
| CLD-08 | API-Schlüssel SOLLEN nur im Secret-Speicher liegen, nie in Rezepten, Logs oder Audit. Secret-Speicher heißt: Umgebungsvariable `GUPPI_SECRET_*` oder `local_config/cloud_keys.json`, verschlüsselt mit Windows-DPAPI (G1-S0-f). | Geheimnis-Sperre findet keinen Schlüssel im Klartext in Dateien; Konfiguration nennt nur `secret://anbieter/id` |
| CLD-09 | WENN Cloud-Agenten wie Claude Code oder Codex eingebunden werden, DANN SOLLEN sie als Adapter hinter derselben Prüfung laufen und nur in der DevVM arbeiten. | Adapter-Lauf zeigt Gate, Einstufung und microVM |
| CLD-10 | Ein Schalter `cloud` in `switches.yaml` SOLL die Stufe ganz abschalten; Standard ist aus. | Bei aus: Router kennt keine Cloud-Ziele |

### Design (Vorschlag)

- Adapter: der vorhandene `models/cloud_api.py` (OpenAI-kompatibel und Anthropic) wird ausgebaut; neu sind Router-Stufe, Regeln, Budget und Guard-Gates.
- Rezepte bekommen ein optionales Feld `fallback: <cloud-rezept>`; der Router entscheidet die Stufe, nie das Modell selbst.
- Ablauf eines Aufrufs: lokal möglich? → ja: lokal. Nein oder überlastet (SCH-07) → Schalter `cloud` an? → GateWay stuft ein → Klasse erlaubt? → Regel deckt den Fall? → sonst Entscheidung an den Captain → Budget prüfen → Aufruf → Audit und `spend`.
- Cloud-Regeln liegen in `local_config/cloud_rules.yaml` (nicht im Git) und werden nur über ein Gate geändert.

### Aufgaben

- [x] C3.1 `SPEC_EIN_SICHERER_WEG_v1.md` und `SPEC_GATEWAY_VORGANG_v1.md` lesen: Schutzklassen und Matrix übernehmen, nicht neu erfinden
- [x] C3.2 Entwurf der Grundsatzänderung für README und `ENTWICKLUNG.md` (siehe „Abgleich gegen den Code (G1)“) → Captain-Gate G1-S3-10
- [ ] C3.3 Design Adapter, Regeln, Budget → G2
- [ ] C3.4 Bau-Spec `cld_rules` (Regelprüfung, Budget) mit versteckten Tests; Adapter und Router-Stufe als Harness → G3
- [ ] C3.5 Test mit einem Anbieter und kleinem Budget, danach Abnahme → G4

### Abgleich gegen den Code (G1)

Stufe 1 der Spec 3, Stand 20.10.2026, Branch `spec3/cloud-gateway` (Basis Commit `3abb023`). Nur gelesen: kein Cloud-Aufruf, kein Schlüssel gelesen, kein Test ausgeführt. „Geprüft“ heißt: Code gelesen, nicht gelaufen.

#### Schutzklassen und Matrix (C3.1, übernommen)

Quellen: `SPEC_EIN_SICHERER_WEG_v1.md` (S1 bis S7), `SPEC_GATEWAY_VORGANG_v1.md` (13 Merkmale, Matrix), `REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1` (R-01 bis R-16) und der Code `gateway/klassen.py` (`POLICY_VERSION = b6-datenregeln-0.1`, `RECHTSGRUNDLAGE_CLOUD = False`). Spec 3 erfindet nichts Neues; die Matrix bleibt Sache des GateWay.

| Klasse | Beispiele (Merkmal) | Wohin darf sie heute | Review |
| --- | --- | --- | --- |
| Hard Block | Zugangsdaten (S01), Karte mit Prüfwert (F03), Anweisungen an die KI im Dokument (S02) | nirgends, auch nicht lokal | nicht übersteuerbar |
| UNCLASSIFIED | Scan unvollständig, Datei unlesbar | nirgends, bis der Captain prüft | ja |
| SK3 streng vertraulich | besondere Kategorien (P02), Strafsachen (P03), amtliche Kennungen (P04), Geschäftsgeheimnis (G01), Minderjährige (V01), Hochrisiko-Kontext (A01, von Hand) | nur lokal, nach Review | ja |
| SK2 vertraulich | Bankverbindung (F01), Kartendaten (F02), NDA (G02), Rechtsstreit (R01, von Hand) | nur lokal | nein |
| SK1 intern | Personenbezug (P01) | nur lokal; `CLOUD_AFTER_PSEUDONYMIZATION` erst mit Rechtsgrundlage und AVV (R-01) | nein |
| SK0 öffentlich | kein Merkmal, Scan vollständig | lokal oder Cloud | nein |

Heute darf also **nur SK0** in die Cloud. Zusätzlich sperrt der Inhaltsschutz (`core/content_policy.py`, `judge`) auf der Route `cloud` jeden Scanner-Treffer für Personenbezug, sensible Daten, Platzhalter und Schlüssel (`SG_PERSONAL_CLOUD`, `SG_SENSITIVE_CLOUD`, `SG_SECRET_CLOUD`, `SG_PLACEHOLDER_CLOUD`, `SG_KEY_FORMAT`). Der Modus (Sandbox, Beobachten, Vertraut) ändert daran nichts: was den Rechner verlässt, ist immer scharf (S5, `enforced`). Zwei Ebenen also: **Scanner-Ebene** (`content_policy`, bei jedem Aufruf) und **Klassen-Ebene** (`klassen.einstufen`, nur im GateWay-Vorgang). Die Klassen-Ebene sieht auch das, was kein Scanner findet (R01, A01 von Hand).

#### Abgleich CLD-01 bis CLD-10

| ID | Befund | Stand | Beleg |
| --- | --- | --- | --- |
| CLD-01 | `ModelRouter.choose` wählt Cloud nie von selbst; nur ein Aufruf mit Anbieter-Name erreicht sie. Aber es gibt keine „Cloud-Regel“. Auch `labor.cloud_chat`, `redesign_*`, `spec_lab`, Standardläufe und `paperclip_pipeline` rufen `provider_adapter` direkt auf und umgehen den Router. Nach Klick oder Lauf-Start geht der Aufruf hinaus. | teilweise | `models/router.py` `choose`; `labor.py`, `redesign_agent.py` |
| CLD-02 | Der Inhaltsschutz prüft jeden Cloudaufruf (Scanner-Ebene). Die Schutzklassen von `klassen.einstufen` sind **nicht** auf dem Cloudweg: Gespräch, Kurztest und Läufe stufen nicht ein; R01 und A01 greifen dort nie. Die Matrix kennt keinen Anbieter, nur „Cloud“. Zudem baut `labor.py` ein eigenes `ContentGuard(cloud_enabled=True)` statt `runtime.content_guard`: Zähler, Modus und Anzeige von `schutz` sehen diese Aufrufe nicht. Außerdem gibt es in `labor.cloud_chat` einen Konfigurationswert `modus: test`, der Personenbezug pseudonymisiert und sendet, statt zu sperren; das widerspricht R-01 und gehört entfernt oder hinter ein Gate. | teilweise | `labor.py` Z. 39, 98 ff.; `gateway/vorgang.py` ist der einzige Aufrufer von `einstufen` |
| CLD-03 | Fehlt. Kein Guard-Gate, keine Regeldatei `cloud_rules.yaml`, keine Regelbindung im Audit. Der Klick des Captains im Labor oder im Gespräch ist heute die einzige „Entscheidung“, ohne Bindung an Agent, Klasse, Anbieter, Budget. | fehlt | `uix_server.py` `labor_connection`, `chat_cloud` ohne `_gate_request` |
| CLD-04 | Das Audit kennt `SG_MODEL_CALL` (Route, Modell, Policy, Bindungs-Hash, ohne Text) und `TOOL_CALLED` (Router). Es fehlen: Anbieter im `SG_MODEL_CALL`, Token, Kosten, Schutzklasse. `CLOUD_CALL` gibt es nicht. Token stehen in `result["usage"]`, werden aber nirgends ins Audit geschrieben. | teilweise | `core/content_guard.py` `info`; `labor.py` |
| CLD-05 | Fehlt. Kein Zähler, kein `spend`, keine Grenze pro Minute oder Tag, kein Euro-Stand, keine 80-%-Warnung. **Risiko:** `model_test` sendet bis zu 120 Anfragen hintereinander (`MAX_MODELS_PER_RUN`), `connection_test` bis zu 4 Testnachrichten; beides läge über 30 pro Minute. Läufe starten als eigene Prozesse (`vorarbeiter.lauf_starten`), ein Zähler im Speicher reicht deshalb nicht. | fehlt | `labor.py` `model_test`, `vorarbeiter.py` |
| CLD-06 | Im Kombi-Pfad steht „Cloud · Anbieter / Modell“ vor der Antwort. Das Ergebnis von `cloud_chat` trägt `provider`, `model`, aber kein einheitliches Kennzeichen; für Aufgaben und Issues gibt es nichts, weil Cloud-Läufe keine Aufgabe tragen. Der normale Cloud-Pfad im Gespräch wurde nicht im Browser geprüft. | teilweise | `uix/tools/talk/kombi.js`, `uix_server.py` `chat_cloud` |
| CLD-07 | Kein stiller Wechsel: Der Router fällt nie auf Cloud zurück; bei Cloud-Fehler bleibt in `chat_kombi` der lokale Entwurf, und die Antwort sagt warum. Es gibt aber kein „warten“ (kein Wiederholen, kein Rezept-Feld `fallback`); die Gegenrichtung (lokal überlastet → Cloud, SCH-07) hängt an Spec 2. Ein Cloud-Ausfall im Lauf bricht den Lauf ab. | teilweise | `models/router.py`, `uix_server.py` `chat_kombi` |
| CLD-08 | Weitgehend erfüllt: Verweis `secret://anbieter/id`, Umgebungsvariable `GUPPI_SECRET_*`, DPAPI-Datei `local_config/cloud_keys.json` (nur Windows), Audit ohne Wert, Fehlertexte geschwärzt, Weiterleitungen mit Schlüssel abgelehnt. Lücken: (1) Der Speicher ist nach Anbieter geschlüsselt, nicht nach Verweis; `_key_state` nimmt fest `_API_KEY`, ein Verweis mit anderer ID wird dort nicht aufgelöst. (2) Mammouth: Schlüsselformat unbekannt; `_error_detail` kennt nur `nvapi-` und `sk-`. (3) DPAPI ohne zusätzliche Entropie: jeder Prozess desselben Benutzers kann entschlüsseln, auch ein Lauf-Prozess. (4) Ein Test „kein Schlüssel im Klartext in Dateien“ wurde nicht gefunden (nicht gezielt gesucht). | erfüllt mit Lücken | `cloud_settings.py`, `models/cloud_api.py` |
| CLD-09 | Fehlt. Der Anthropic-Adapter ist eine API, kein Agent-Adapter (Claude Code, Codex), und es gibt keinen DevVM-Anschluss. | fehlt | – |
| CLD-10 | Abweichung vom Spec-Text: Der Schalter steht **nicht** in `switches.yaml` (`local_switches.ALLOWED` kennt keinen Abschnitt `cloud`), sondern als Hauptschalter `enabled` in `cloud_providers.yaml` (Standard aus). Bei aus baut `runtime._configure_cloud_providers` keinen Adapter, der Router kennt keine Cloud-Ziele: dieses Kriterium ist erfüllt. Aber Labor-Tests und Läufe lesen den Schalter zur Laufzeit aus der Datei (`labor._enabled`) und sind nicht an den Router-Stand beim Start gebunden. Zwei Wahrheiten. | abweichend | `runtime.py` `_configure_cloud_providers`, `labor.py` `_enabled` |

Abnahmekriterien: CLD-01, 02, 04, 05, 08, 10 sind prüfbar, sobald `CLOUD_CALL` und der Zähler existieren. Nicht prüfbar wie formuliert: **CLD-03** („Regel ist im Audit gebunden“ braucht eine definierte Regel-ID im Audit), **CLD-06** („Kennzeichen in Gespräch und Aufgabe“ braucht eine Festlegung, was das Kennzeichen ist), **CLD-07** („Ausfall-Test ohne stillen Wechsel“ braucht eine Definition von „wartet“), **CLD-09** (microVM-Anschluss hängt an Spec 0 und der DevVM).

#### Abgleich LAB-01 bis LAB-07

| ID | Befund | Stand |
| --- | --- | --- |
| LAB-01 | Das Werkzeug `labor` hat Manifest (`kind: object`, `trust: CORE`, `handles: [labor]`, 8 `api`-Einträge) und nur `tool.js`/`tool.css`. Im Cockpit hängt es in `palette.js` und `tree.js`. Shell D (`shell.yaml` v1.1.0) hat keinen Eintrag; das gehört nach Spec 4. `uix_check --tool labor` wurde nicht ausgeführt. | teilweise |
| LAB-02 | Anbieter **anlegen** geht nicht: `cloud_settings.save` lehnt unbekannte Anbieter ab; bekannt sind nur `nvidia`, `openai`, `anthropic` aus `config/cloud_providers.yaml`. **Mammouth fehlt.** Eintragen von Basis-URL und Modell geht ohne Gate; der Schlüssel (`/api/cloud/key`) landet nur in DPAPI, im Audit steht `CLOUD_KEY_CHANGED` ohne Wert. Gate fehlt. | teilweise |
| LAB-03 | Kurztest existiert (`connection_test`), aber mehr als „eine Frage“: ein `GET /models` plus bis zu 4 Testnachrichten, mit einer fest eingebauten Modellliste vom 16.10.2026. Audit nur `LABOR_CONNECTION_TEST` (ok/nicht ok), kein `CLOUD_CALL`, kein Gate, keine Einstufung (die Testnachricht ist fest und harmlos, geht aber nur durch den Scanner). Auch `fetch_models` ist ein Netzzugriff auf den Anbieter-Host ohne Guard-Regel. `model_test` (alle Modelle) sprengt die Startphasen-Grenzen. | teilweise |
| LAB-04 | Fehlt: keine Grenzen, keine Anzeige, keine `cloud_rules.yaml`. | fehlt |
| LAB-05 | Fehlt: keine Tabelle `spend`, kein Ereignis `budget.warning` (der Ereigniskatalog wurde nicht gelesen; im Spec-Ist-Stand ist es nicht aufgeführt). | fehlt |
| LAB-06 | Nicht vorhanden. Die Matrix ist global („Cloud“), nicht je Anbieter. Geändert wird sie heute nur im Code (`klassen.py`, `RECHTSGRUNDLAGE_CLOUD`). Eine Anbieter-Zeile (Obergrenze) muss neu entstehen. | fehlt |
| LAB-07 | Der Hauptschalter ist im Labor sichtbar und umschaltbar (`laborMaster`), speichert über `/api/cloud/save` **ohne Gate** und wirkt erst nach dem Neustart (`restart_needed`). Der Satz „Cloud-Stufe aus“ steht dort nicht. | teilweise |

Abnahmekriterien: LAB-02 bis LAB-07 sind prüfbar (Audit, `spend`, Anzeige). LAB-01 braucht für Shell D den Spec-4-Eintrag. LAB-03: „wie beim Kurztest der Werkstatt“ ist nicht festgelegt; einen Kurztest unter diesem Namen habe ich im Code nicht gefunden (siehe Offene Fragen).

#### Korrekturvorschläge (alt / neu)

| ID | alt | neu (Vorschlag) |
| --- | --- | --- |
| CLD-01 | Jeder Modellaufruf SOLL lokal laufen, solange keine Cloud-Regel greift. Ohne Regel: 0 Cloud-Aufrufe im Audit. | Jeder Modellaufruf SOLL lokal laufen, solange keine freigegebene Regel in `cloud_rules.yaml` (oder eine Entscheidung des Captains) den Cloudweg für genau diesen Aufruf öffnet. Alle Cloud-Zugriffe (Gespräch, Labor, Läufe, Pipelines) gehen durch **eine** Stelle, die `CLOUD_CALL` schreibt. Abnahme: Ohne Regel keine Zeile `CLOUD_CALL`; ein Test zählt jeden `provider_adapter`-Aufruf. |
| CLD-02 | … stuft das GateWay die Anfrage nach Schutzklasse ein; gesperrte Schutzklassen gehen nie in die Cloud. | … stuft `gateway/klassen.einstufen` vor jedem Cloudaufruf ein, zusätzlich zum Scanner des Inhaltsschutzes. In die Cloud darf nur SK0 mit Weg `CLOUD_ALLOWED`. Die Obergrenze je Anbieter (Tabelle in `cloud_rules.yaml`) macht den Weg enger, nie weiter als die Matrix (K-03). Abnahme: ein Testfall je Klasse und je Anbieter. |
| CLD-03 | … brauchen eine Entscheidung des Captains, außer eine freigegebene Regel deckt … | … Regel: Agent, Schutzklasse, Anbieter, Budget; Bindung im Audit mit Regel-ID und Hash der Regeldatei. Ohne Deckung entsteht eine Entscheidung (`desk/decisions`). Ein Klick des Captains im Gespräch oder Labor zählt als Entscheidung für **diesen einen** Aufruf (G1-S3-05). |
| CLD-04 | … Anbieter, Modell, Token, Kosten und Schutzklasse … | zusätzlich: Regel-ID oder Entscheidungs-ID, Agent, Aufrufer (`chat`, `labor`, `lauf`), Dauer, Ergebnis (`ok`, `blocked`, `limit`, `error`). Kosten in Euro nur mit Preisliste, sonst 0 und Anzahl. Kein Text. |
| CLD-05 | … in Euro, Anfragen pro Minute oder pro Tag … Hard-Stop. | Zähler **prozessübergreifend** (Tabelle `spend` in einer Datenbank mit Sperre, nicht im Speicher), weil Läufe eigene Prozesse sind. Pro Anbieter und gesamt, je Agent. Stopp bei 100 %, Warnung bei 80 % (`budget.warning`). Auch Kurztest und Modelltest zählen. Bei Limit bleibt der Lauf lokal oder wartet (Minutenlimit: höchstens bis zur nächsten Minute; Tageslimit: bleibt lokal). |
| CLD-06 | … sichtbar kennzeichnen. Kennzeichen in Gespräch und Aufgabe. | Jedes Ergebnis trägt `route: cloud`, `provider`, `model`. Die Oberfläche zeigt „Cloud · Anbieter / Modell“ an jeder Antwort im Gespräch und am Kommentar oder Ergebnis einer Aufgabe. Abnahme: `uix_check` und Klicktest. |
| CLD-07 | … lokal weiterarbeiten oder warten; nie still wechseln. | Bei Ausfall: Meldung mit Grund, **kein** automatischer Wechsel der Stufe, in keine Richtung. Das Rezept-Feld `fallback` führt nur zu einer sichtbaren Entscheidung oder zu einer freigegebenen Regel, nie zu einem stillen Wechsel. |
| CLD-08 | … Secret-Speicher heißt … | zusätzlich: Speicher nach Verweis geschlüsselt (`secret://anbieter/id`); Muster für Mammouth-Schlüssel in die Schlüsselerkennung; DPAPI mit Entropie je Installation (Entscheidung offen); ein Test, der `local_config`, Logs und Audit nach Schlüsseln durchsucht. |
| CLD-09 | … Adapter hinter derselben Prüfung, nur in der DevVM. | In die **Nach-Startphase** verschieben: Die Startphase hat Budget 0 und Coder nur lokal; Claude Code und Codex sind Coder-Dienste mit eigenem Abo. Eigene Spec nach G4 von Spec 3. |
| CLD-10 | Ein Schalter `cloud` in `switches.yaml` … | Ein Hauptschalter: `cloud_providers.enabled` in `local_config/cloud_providers.yaml` (Standard aus). Er gilt für **alle** Pfade, auch Labor und Läufe, und wird bei jedem Aufruf frisch gelesen. Umschalten ist ein Gate. (Alternative: `switches.yaml` um den Abschnitt `cloud` erweitern, siehe G1-S3-09.) |
| LAB-02 | WENN der Captain einen Anbieter anlegt … | Anbieter anlegen heißt: Eintrag in `local_config/cloud_providers.yaml` (Name, Basis-URL nur https, Modelle, Verweis `secret://…`). Gate `set_cloud_provider`; der Schlüssel läuft getrennt über `credential_access`. Startbestand: `nvidia`, `mammouth`. |
| LAB-03 | … eine Frage, Antwortzeit, Token; externe Aktion mit Gate und durch das GateWay. | Der Kurztest sendet **genau eine** feste Testnachricht an das Standardmodell, kein `GET /models`. Er zählt gegen das Budget und schreibt `CLOUD_CALL`. Modellliste und Test aller Modelle sind eigene Aktionen; der Test aller Modelle ist in der Startphase aus. „wie beim Kurztest der Werkstatt“ entfällt. |
| LAB-05 | … Verbrauch live zeigen und bei 80 % warnen. | Anzeige je Anbieter und Agent; Warnung als Ereignis `budget.warning` und im Posteingang. Der Ereigniskatalog wird erweitert (eigenes Gate, kein `core/`). |
| LAB-07 | … Schalter `cloud` zeigen; Umschalten ist ein Gate. | wie CLD-10; bei aus zeigt das Labor „Cloud-Stufe aus“ und sperrt alle Test-Knöpfe. |

#### Guard-Aktionen für die Cloud-Stufe

Vorhanden (`guard_rules.yaml`, `permission_levels.yaml`): `external_write` (GR-005, CAPTAIN_REQUIRED, Stufe 6), `credential_access` (GR-007, CAPTAIN_REQUIRED, Stufe 6), `paid_action` (GR-008, CAPTAIN_REQUIRED, Stufe 6), `external_read` (GR-027, ALLOW; gilt für die Hosts aus `config/web_access.yaml`). Für die Cloud-Stufe genügen sie nicht allein: Ein Gate je Aufruf wäre bei 500 Anfragen am Tag unbrauchbar, und eine unbekannte Aktion läuft ohnehin als CAPTAIN_REQUIRED.

| Gate | Aktion | Bedeutung | Vorschlag | Stufe | Begründung |
| --- | --- | --- | --- | --- | --- |
| G1-S3-GA-01 | `credential_access` (vorhanden) | Schlüssel für einen Anbieter ablegen oder löschen (`/api/cloud/key`) | CAPTAIN_REQUIRED, unverändert | 6 | nur im Secret-Speicher; Gate nachrüsten, die Regel besteht |
| G1-S3-GA-02 | `set_cloud_provider` (neu) | Anbieter anlegen oder ändern (Name, Basis-URL, Modelle) | CAPTAIN_REQUIRED | 5 | neues Ziel im Netz (CLD-08, LAB-02) |
| G1-S3-GA-03 | `change_switch` (vorhanden) oder neu `set_cloud_switch` | Hauptschalter Cloud und Schalter je Anbieter | CAPTAIN_REQUIRED | 5 | CLD-10, LAB-07; mit `change_switch` braucht es keine neue Regel |
| G1-S3-GA-04 | `set_cloud_rules` (neu) | `cloud_rules.yaml` ändern: Grenzen, Freigaben je Agent und Anbieter, Obergrenze der Klassen | CAPTAIN_REQUIRED | 5 | Budget und Freigaben sind Grenzen des Captains (LAB-04); wie `set_budget` in Spec 0 |
| G1-S3-GA-05 | `cloud_call` (neu) | ein einzelner Cloudaufruf, ausgelöst durch einen Agenten oder Lauf | CAPTAIN_REQUIRED, außer eine freigegebene Regel deckt Agent, Klasse, Anbieter und Budget (dann ALLOW mit Regel-ID) | 6 | CLD-03. Eine Aktion statt `external_write` plus `paid_action`; das Gate entscheidet über die Regel, nicht über den Text |
| G1-S3-GA-06 | `cloud_probe` (neu) | Kurztest und Modellliste auf Klick des Captains | ALLOW nach Klick (der Klick ist die Entscheidung), nur bei Schalter an und freiem Budget | 4 | LAB-03; ein Gate pro Klick wäre doppelt |
| G1-S3-GA-07 | `paid_action` (vorhanden) | Aufruf, der Geld kostet (Mammouth über das Abo-Guthaben hinaus, Euro über 0) | BLOCK in der Startphase | 6 | Startphase: 0 € extra; nur ein Gate des Captains öffnet das |

Die neuen Aktionen brauchen je einen Eintrag in `guard_rules.yaml` (fortlaufend nach den Nummern aus Spec 0) und in `permission_levels.yaml`; `tests/test_permission_levels.py` hält beides gleich. Das Audit bekommt `CLOUD_CALL` neben `CLOUD_SETTINGS_SAVED`, `CLOUD_KEY_CHANGED`, `LABOR_CONNECTION_TEST`. Die Regeldatei liegt unter `architecture/…/core/guard/`; jede Änderung dort ist ein eigenes Gate (Regel 1).

#### Entwurf Grundsatzänderung „Local First, Cloud Second“ (C3.2)

Nur Text. `README.md` und `docs/ENTWICKLUNG.md` werden erst nach Freigabe der Spec geändert.

**README.md, Zeile „Läuft vollständig lokal“**

alt: „**Läuft vollständig lokal:** eigener llama.cpp-Server, keine Cloud-Modelle. Hauptmodell ist Qwen3.6-35B-A3B auf einer RTX 4070 Ti (12 GB).“

neu: „**Local First, Cloud Second:** Alles läuft zuerst lokal (eigener llama.cpp-Server, Hauptmodell Qwen3.6-35B-A3B auf einer RTX 4070 Ti, 12 GB). Eine Cloud-Stufe ist eine zweite Möglichkeit und standardmäßig aus. Sie ist nur über einen Schalter erreichbar, geht bei jedem Aufruf durch den Router, den Inhaltsschutz und die Einstufung des KI-GateWay, ist budgetiert und im Audit sichtbar. Personenbezogene und vertrauliche Daten (alles über SK0) verlassen den Rechner nicht. Coder-Agenten laufen nur lokal.“

**README.md, Abschnitt „Grenzen“**

alt: „Es gibt keinen stillen Wechsel auf ein Cloud-Modell.“

neu: „Es gibt keinen stillen Wechsel auf ein Cloud-Modell, in keiner Richtung: Die Cloud wird nur über eine freigegebene Regel oder eine Entscheidung des Captains erreicht, und jede Antwort aus der Cloud ist als solche gekennzeichnet.“

**README.md, GateWay-Zeile („Cloud nur simuliert“)**

Ersetzen durch „Cloud nur über das GateWay; Anbieter und Budget stehen im KI-Labor“, sobald G4 von Spec 3 bestanden ist. Bis dahin bleibt „simuliert“ stehen, weil der GateWay-Vorgang selbst den echten Cloudweg noch nicht nutzt.

**docs/ENTWICKLUNG.md, neuer Grundsatz** (neben „Captain First“ und „Kern geschützt“)

„**Local First, Cloud Second.** Jeder Modellaufruf läuft lokal, solange nichts anderes ausdrücklich erlaubt ist. Die Cloud ist eine zweite Stufe hinter dem Schalter `cloud` (Standard aus). Jeder Cloudaufruf geht durch den Router, den Inhaltsschutz und die GateWay-Einstufung, braucht eine Entscheidung des Captains oder eine von ihm freigegebene Regel, hat ein Budget, schreibt `CLOUD_CALL` ins Audit und wird in der Oberfläche gekennzeichnet. Schlüssel stehen nur im Secret-Speicher. Es gibt keinen stillen Wechsel der Stufe. Coder-Agenten arbeiten nur lokal. Vor Freigabe von Spec 3 gibt es keine Cloud-Aufrufe durch Agenten oder Tests.“

**docs/ENTWICKLUNG.md, bestehende Netz-Regel**

Zusatz: „Ausgenommen sind die Hosts der freigegebenen Cloud-Anbieter in `cloud_rules.yaml`; jeder neue Host ist ein Gate.“ Der Wortlaut der bestehenden Regel wurde nicht abgeglichen; er ist beim Einarbeiten zu prüfen.

#### Gate-Liste G1-S3

Alles ist ein Vorschlag des Vorarbeiters. Jedes Gate entscheidet der Captain einzeln.

| Gate | Entscheidung, die der Captain trifft | Empfehlung |
| --- | --- | --- |
| G1-S3-01 | Abgleich gegen den Code (CLD-01 bis CLD-10, LAB-01 bis LAB-07) als richtig freigeben | ja |
| G1-S3-02 | Korrekturen der Tabelle „alt / neu“ übernehmen (CLD-01 bis CLD-08, CLD-10, LAB-02, 03, 05, 07) | ja |
| G1-S3-03 | CLD-09 (Claude Code und Codex als Adapter) in die Nach-Startphase verschieben | ja |
| G1-S3-04 | Eine Cloud-Stelle: alle Pfade (Gespräch, Labor, Läufe, Pipelines) laufen durch einen Aufrufer mit `CLOUD_CALL`, Einstufung und Budget; die direkten `provider_adapter`-Aufrufe entfallen. Der Konfigurationswert `modus: test` (pseudonymisiert und sendet Personenbezug) entfällt | ja |
| G1-S3-05 | Klick des Captains (Gespräch, Kurztest) zählt als Entscheidung für diesen einen Aufruf, bleibt aber im Budget und in der Einstufung | ja |
| G1-S3-06 | Einstufung nach `klassen.einstufen` plus Anbieter-Obergrenze; die Anbieter-Tabelle ist nur enger als die Matrix (K-03) | ja |
| G1-S3-07 | Zähler in einer Datenbank mit Sperre (prozessübergreifend) statt im Speicher | ja |
| G1-S3-08 | Startphasen-Grenzen aus der Spec übernehmen: NVIDIA 30 pro Minute und 500 pro Tag, Mammouth nur Abo-Guthaben, Coder nur lokal; „Test aller Modelle“ in der Startphase aus | ja |
| G1-S3-09 | Ort des Hauptschalters: `cloud_providers.yaml` (ein Ort, wie heute) oder `switches.yaml` (Spec-Text; ändert `local_switches.py`) | `cloud_providers.yaml` |
| G1-S3-10 | Grundsatztext C3.2 für README und `ENTWICKLUNG.md` (Entwurf oben) freigeben; eingearbeitet wird erst nach G1 | ja |
| G1-S3-GA-01 bis GA-07 | die sieben Guard-Aktionen der Tabelle, jede einzeln | wie vorgeschlagen |

#### Offene Fragen an den Captain (nicht blockierend für G1)

1. Mammouth: Basis-URL, Modellnamen und Schlüsselformat stehen nicht im Repo. Gibt es eine Abfrage des Abo-Guthabens, oder zählt SEDRA nur Anfragen und Token?
2. NVIDIA ist kostenlos (0 €): Reicht die Grenze in Anfragen als einzige Bremse?
3. „Kurztest der Werkstatt“ (LAB-03): Gemeint ist vermutlich `connection_test`; unter diesem Namen nicht gefunden. Verweis streichen?
4. DPAPI-Datei: Darf ein Lauf-Prozess den Schlüssel lesen (heute ja, gleicher Benutzer), oder gehen Läufe über den Server?
5. Mit `RECHTSGRUNDLAGE_CLOUD = False` darf nur SK0 in die Cloud. Reicht das für Planer und Recherche, oder arbeiten sie nur mit SK0-Auszügen?
6. Die Prüfung der Nutzungsbedingungen beider Anbieter (Budget-Abschnitt) ist Vorarbeiter-Aufgabe vor dem regelmäßigen Einsatz und in Stufe 1 nicht erledigt.

#### Nicht geprüft

Kein Testlauf (`pytest`, `uix_check`), keine Browserprüfung, kein Cloud-Aufruf; `local_config/` und `cloud_keys.json` nicht geöffnet. Nicht gelesen: `desk/events.py`, `desk/decisions.py`, `provider_health`, die Tests im Einzelnen, der Wortlaut der Regeln in `docs/ENTWICKLUNG.md`, Nutzungsbedingungen von NVIDIA und Mammouth, Preislisten.

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
| Erstes Team | Unterarbeiter (oben, unter dem Captain; Nachtrag OP-6), Planer, Coder, Reviewer, Recherche | Spec 1 |
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

G1 Spec 0 (Captain, 20.10.2026), nach Prüfung K0.1 bis K0.4:

| Gate | Entscheidung |
| --- | --- |
| G1-S0-a | Ist-Tabelle korrigiert, Zeile KI-Labor ergänzt |
| G1-S0-b | KERN-01 prüft über `POST /api/objects`; keine neue GET-Route |
| G1-S0-c | Audit `UIX_ACTION` bekommt das Feld `client` |
| G1-S0-d | Die Registrierung für KERN-04 ändert `uix_server.py` einmal |
| G1-S0-e | Spec 3 baut den vorhandenen `cloud_api.py` aus und rüstet die Gates des KI-Labors nach |
| G1-S0-f | Die DPAPI-verschlüsselte Datei `local_config/cloud_keys.json` gilt als Secret-Speicher im Sinne von CLD-08 |

G2 Spec 0 (Captain, 20.10.2026): Design D1 bis D6 freigegeben, alles wie vom Vorarbeiter empfohlen.

| Gate | Entscheidung |
| --- | --- |
| G2-S0-01 bis G2-S0-14 | freigegeben wie D6 |
| G2-S0-GA-01 bis GA-10 | freigegeben wie D4: `set_org`, `wake_agent`, `resume_agent`, `terminate_agent`, `set_budget`, `set_routine` CAPTAIN_REQUIRED; `assign_task`, `delegate_task`, `pause_agent`, `fire_routine` ALLOW (GR-029 bis GR-038) |
| OP-1 | Aufgabe des Bretts ist Typ `issue`; `task` bleibt die Mission; KERN-01 angepasst |
| OP-4 | `wake_agent` bleibt CAPTAIN_REQUIRED; Dauerfreigabe je Agent wird in Spec 1 entworfen (Kern-Gate) |
| OP-5 | `orchestra.db` sichert sich über Transaktionen und WAL; `core/util.py` nur für Dateien |
| OP-6 | genau ein oberster Agent: der Unterarbeiter, direkt unter dem Captain; dazu ORC-14 |
| OP-7 | Budget-Zeitraum `gesamt` oder `monat`, Standard `gesamt` |
| OP-8 | Ziel = Vorhaben (`intent`), Projekt = `project`; keine Ziel-Tabelle |
| OP-9 | Takt des Herzschlags in der Oberfläche; eigener Dienst wird in Spec 1 entschieden |
| OP-10 | `orchestra/` und Desk-Teile werden nach Review übernommen (G4), nicht über `self_integration`; diese wird nicht geweitet |
| OP-11 | Architekturversion von `test_desk_objects` (v1.17 gegen v1.20) wird im Bau geklärt |

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
