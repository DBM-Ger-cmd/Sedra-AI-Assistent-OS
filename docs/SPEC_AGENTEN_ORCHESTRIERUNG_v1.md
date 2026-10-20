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

#### Bauschritte K0.7 bis K0.25 (Stufe 3, Vorlage für G3)

Stand 20.10.2026, geschnitten aus D1 bis D6 (G2 erteilt). Wer baut: **SEDRA** heißt neues Modul mit klarer Schnittstelle; Bau-Spec und versteckte Tests liegen in `runtime/benchmarks/devvm_specs/<name>.py`, die grüne Referenz (nur Prüfmittel, kein Produktionscode) in `runtime/benchmarks/devvm_refs/<name>/`. SEDRA baut lokal mit `devvm_build.py` einen Kandidaten, Richter ist der versteckte Test; nach Review Zeile für Zeile entscheidet der Captain über die Übernahme (G4, OP-10). **Harness** heißt Eingriff in vorhandene Dateien oder in Guard, Token und Vertrag; das bauen KI-Sitzungen. Ein Harness-Schritt, der ein SEDRA-Modul übernimmt, kopiert den Kandidaten unverändert in das Paket (nur relative Importe angepasst).

| Schritt | Inhalt | Dateien | G2-Gate | hängt ab von | baut |
| --- | --- | --- | --- | --- | --- |
| K0.7 | Golden-Test vor jedem Umbau: für die neun heutigen Typen `objects_view({type})` und `object_view(type, id)` auf dem Fake-Host mit Testdaten aufzeichnen, dazu die Fehler (`unknown_object_type`, Objekt „nicht gefunden“, `agent` → `unknown_object_type`, Liste `agent` leer). Aufzeichnung mit dem alten Code, eingecheckt; dazu einmal die Liste der heute grünen Tests aus D1 festhalten | `tests/test_desk_kinds.py` (Klasse `Golden`), `tests/fixtures/desk_golden/` | G2-S0-01 | – (zuerst) | Harness |
| K0.8 | Register `kinds.py`: `Kind`, `Registry` (`register`, `freeze`, `mark`/`reset`, `refuse`, `view`, `listing`, `request`, `offered`, `table`, `type_verb`), `SHAPE`, `CHAT_TOOLS`, `client_for`, `refuse_client_field` | Bau-Spec `k0_kinds` → `desk/kinds.py` | G2-S0-01, G2-S0-04 | – | SEDRA |
| K0.9 | Andocken `extensions.py`: `MODULES`, `load(registry, hub, …)` mit Rücknahme einer halben Registrierung und Audit `DESK_KIND_REFUSED`, `start(hub, loaded)` | Bau-Spec `k0_extensions` → `desk/extensions.py` | G2-S0-01 | – (Schnittstelle von K0.8 nur als Vertrag) | SEDRA |
| K0.10 | Desk an das Register: Übernahme K0.8 und K0.9 (nach G4); `desk/builtin_kinds.py` mit den neun Typen, Leser wörtlich aus `object_view`/`objects_view` verschoben (`decision` mit `own_actions=True`, `agent` als Platzhalter); `desk/gated.py` (Antrag/Anwenden nach dem Muster `boundaries_request`/`boundaries_apply`); `objects.TYPES` und `actions.VERBS`/`table()`/`offered()`/`run()` aus dem Register, dazu `run_type()`; Tests Beispieltyp `echo`, doppelter Typ, `freeze()` | `desk/kinds.py`, `desk/extensions.py`, `desk/builtin_kinds.py`, `desk/gated.py`, `desk/objects.py`, `desk/actions.py`, `tests/test_desk_kinds.py` | G2-S0-01 | K0.7, K0.8, K0.9 | Harness |
| K0.11 | Einmalige Änderung `uix_server.py`: `object_view` → `registry.view`, `objects_view` → `registry.request`; `act` erlaubt Verben ohne `id`, wenn der Typ ein `type_verb` dieses Namens hat; beim Start `builtin_kinds.register()`, `extensions.load()`, `extensions.start()`, `freeze()`; `ast`-Prüfung: keine Typnamen in `object_view`/`objects_view`; Golden-Test unverändert grün | `uix_server.py`, `tests/test_desk_kinds.py` | G2-S0-02 | K0.10 | Harness |
| K0.12 | `chat_tools.VERB_TYPES` aus dem Register statt fest | `chat_tools.py`, `tests/test_uix_guppi_moves.py` (nur laufen lassen) | G2-S0-03 | K0.10 | Harness |
| K0.13 | Feld `client`: `_authorized()` liefert die Token-Klasse, `client_for` setzt den Wert; `client` im Körper → `400 client_is_set_by_server` und Audit `UIX_CLIENT_REFUSED`; `UIX_ACTION` mit `payload.client`; Client-Token für `cli` und `mcp` in `runtime_data/uix/clients/<client>.json` (atomar, DPAPI unter Windows, sonst 0600; beim Beenden gelöscht) | `uix_server.py`, `tests/test_desk_client.py` (neu) | G2-S0-04, G2-S0-05 | K0.11 | Harness |
| K0.14 | CLI `guppi objects <typ> [<id>]`, `guppi act <typ> <id\|-> <verb> [--args JSON]` über Loopback mit `clients/cli.json`; ohne Oberfläche `uix_not_running` | `cli.py`, Test in `tests/test_desk_client.py` | G2-S0-06 | K0.13 | Harness |
| K0.15 | MCP-Server `desk_mcp.py` mit Werkzeugen `objects` und `act`, Prüfung mit `mcp_shield`, Aufruf über `clients/mcp.json`; `state_mcp.py` bleibt lesend | `desk_mcp.py` (neu), `tests/test_desk_mcp.py` (neu) | G2-S0-07 | K0.13 | Harness |
| K0.16 | Konfiguration `config.py`: `OrchestraConfig.from_dict`/`load`/`database_path`/`as_dict`, Fehler `orchestra_config_missing` und `orchestra_config_invalid:<feld>` | Bau-Spec `k0_orchestra_config` → `orchestra/config.py` | G2-S0-08, G2-S0-10 | – | SEDRA |
| K0.17 | Speicher `store.py`: Schema 1 wie D3.3, `migrate`, `schema_version`, `immediate`, `open_db` (WAL, `busy_timeout`, `foreign_keys`), Fehler `orchestra_db_error:<grund>`, `orchestra_busy` | Bau-Spec `k0_orchestra_store` → `orchestra/store.py` | G2-S0-09 | – | SEDRA |
| K0.18 | Fassade `service.py`: `Orchestra` mit übergebenen Teilen und Lesern (`agents`, `issues`, `routines`, `spent` …), `build` nach der Tabelle D3.5 mit Audit `ORCHESTRA_OFF`, `boot_entry` | Bau-Spec `k0_orchestra_service` → `orchestra/service.py` | G2-S0-08, G2-S0-11 | – (Lader und Öffner werden übergeben) | SEDRA |
| K0.19 | Paket anlegen: `orchestra/__init__.py` (nur `__all__`), Übernahme K0.16 bis K0.18 (nach G4); `runtime/config/orchestra.yaml` wie D3.4; `local_switches.ALLOWED["orchestra"] = {"enabled"}`; Importgrenze | `orchestra/`, `runtime/config/orchestra.yaml`, `local_switches.py`, `tests/test_orchestra_boundary.py` (neu), `tests/test_orchestra_config.py` (neu), `tests/test_local_switches.py` | G2-S0-08, G2-S0-10 | K0.16, K0.17, K0.18 | Harness |
| K0.20 | Verdrahtung `runtime.py`: `_configure_orchestra` über `_optional("orchestra", …)` mit `service.build(…, OrchestraConfig.load, store.open_db, …)`, `rt.orchestra`/`rt.orchestra_error`, `boot()["orchestra"]` aus `boot_entry`; `READY` unabhängig; `test_core_boundary_src` grün | `runtime.py`, `tests/test_orchestra_config.py` | G2-S0-11 | K0.19 | Harness |
| K0.21 | Desk-Adapter `orchestra_kinds.py`: Objekte für `agent`, `issue`, `routine`, `budget` aus Zeilen; `register(registry, hub)` nur bei vorhandener `hub.runtime.orchestra`, `agent` ersetzt den Platzhalter; in Spec 0 ohne Verben (siehe OP-12) | Bau-Spec `k0_orchestra_kinds` → `desk/orchestra_kinds.py` | G2-S0-12 | – (Register und Fassade nur als Vertrag) | SEDRA |
| K0.22 | Übernahme K0.21 (nach G4); Abnahme KERN-01 mit Fixture-Datenbank aus `store.open_db`: alle vier Typen über `POST /api/objects` mit genau den Schlüsseln `SHAPE`, `task` unverändert (Golden); Schalter aus → `issue` ist `unknown_object_type` | `desk/orchestra_kinds.py`, `tests/test_orchestra_desk.py` (neu), `tests/fixtures/` | G2-S0-12 | K0.11, K0.20, K0.21 | Harness |
| K0.23 | Guard-Regeln GR-029 bis GR-038 wie D4 und Stufen in `permission_levels.yaml`; `tests/test_permission_levels.py` grün; Architekturversion von `test_desk_objects` klären (OP-11) | `architecture/…/core/guard/guard_rules.yaml`, `runtime/config/permission_levels.yaml` | G2-S0-GA-01 bis GA-10, G2-S0-14 | – (vor den Verben in Spec 1) | Harness |
| K0.24 | Nachtrag `SHELL_WERKZEUG_VERTRAG_v1.md` §10: Registrierung, Verben ohne Objekt, neue Typen, Feld `client`, Client-Token | `docs/SHELL_WERKZEUG_VERTRAG_v1.md` | G2-S0-13 | K0.11, K0.13 | Harness |
| K0.25 | Abnahme Spec 0: Tests aus D5 und D1 grün, `benchmarks/uix_check.py` `result ok`, `git diff --stat main -- runtime/src/guppi_runtime/core` leer, Review-Mängel und Eingriffe ins Logbuch | – | KERN-01 bis KERN-06 | alle | Harness |

Reihenfolge: K0.7 kommt vor K0.10. Die sechs SEDRA-Bauten (K0.8, K0.9, K0.16, K0.17, K0.18, K0.21) hängen von keinem Harness-Schritt ab und können nach G3 nacheinander auf der GPU laufen (eine Lease, ein Bau zur Zeit); K0.7 und K0.23 laufen parallel dazu. Danach zwei Stränge: Desk K0.10 → K0.11 → K0.12, K0.13 → K0.14, K0.15, K0.24; Paket K0.19 → K0.20; beide treffen sich in K0.22, zuletzt K0.25.

Bau-Specs (alle mit `benchmarks/spec_check.py <name>` geprüft: Lint ok, Referenz besteht jede Stufe, die erste Stufe scheitert auf leerer Saat):

| Bau-Spec | Ziel im Paket | Stufen | Referenz | `spec_check` |
| --- | --- | --- | --- | --- |
| `k0_kinds` | `desk/kinds.py` | register, view, client | `devvm_refs/k0_kinds/kinds.py` | result ok |
| `k0_extensions` | `desk/extensions.py` | load, start | `devvm_refs/k0_extensions/extensions.py` | result ok |
| `k0_orchestra_config` | `orchestra/config.py` | top, fields, load | `devvm_refs/k0_orchestra_config/config.py` | result ok |
| `k0_orchestra_store` | `orchestra/store.py` | tx, schema, open | `devvm_refs/k0_orchestra_store/store.py` | result ok |
| `k0_orchestra_service` | `orchestra/service.py` | build, read | `devvm_refs/k0_orchestra_service/service.py` | result ok |
| `k0_orchestra_kinds` | `desk/orchestra_kinds.py` | objects, register | `devvm_refs/k0_orchestra_kinds/orchestra_kinds.py` | result ok |

Schnittstellen, die die Bau-Specs festlegen und der Harness einhält:

- Kein SEDRA-Modul importiert Desk, Runtime oder ein anderes neues Modul. Register, Hub, Fassade, Konfig-Lader, Datenbank-Öffner und Audit werden übergeben; `audit(event, payload)` ist eine Funktion, die der Harness auf `runtime.audit.append(event, component=…, payload=payload)` abbildet.
- `Registry.Kind` ist die Klasse `Kind`; eine Erweiterung baut ihre Typen mit `registry.Kind(…)` und braucht keinen Import.
- `view` füllt `actions` aus den Verben des Typs, außer bei `own_actions=True` (heute nur `decision`); `listing` füllt `actions` immer. Das bildet das heutige Verhalten nach (OP-13). Der Formcheck verlangt die sieben Schlüssel, weitere sind erlaubt (`model` trägt `roles`).
- `table()` enthält nur Typen mit mindestens einem Verb, damit `actions.run()` für Typen ohne Verben wie heute `unknown_object_type` meldet.
- `build(switch_on, …)` schaltet nur bei `switch_on is True` ein; die Fehlertexte sind die aus D3.5.

Offene Punkte (K0.7 ff.):

| Nr | Lücke oder Widerspruch | Vorschlag |
| --- | --- | --- |
| OP-12 | G2-S0-12 nennt „Typen mit Verben wie D3.2“. Die Verben (`zuweisen_an`, `wecken`, `einstellen` …) brauchen `org`, `board` und `budget` aus Spec 1 und die Gates GA-01 bis GA-10. | In Spec 0 die vier Typen nur lesend registrieren (K0.21, K0.22); die Verben mit `desk/gated.py` baut Spec 1 auf derselben Registrierung. Captain bestätigt die Abgrenzung mit G3-S0-15. |
| OP-13 | Heute verliert die Liste der Entscheidungen ihre Wege: `objects_view` setzt `actions` für jeden Eintrag aus `offered()`, und `decision` hat dort keine Verben; die Einzelansicht behält sie. | Verhalten im Golden-Test festhalten und im Register mit `own_actions` nachbilden; eine Korrektur ist eine eigene Verhaltensänderung mit eigenem Gate nach Spec 0. |
| OP-14 | D3.4: `enabled` steht in `orchestra.yaml` und im Schalter. Ob eingeschaltet ist, muss vor dem Laden der Datei feststehen (Zeile „Schalter an, Datei fehlt“). | `runtime.py` nimmt `switch_on = switches.apply("orchestra", "enabled", False)`; `enabled` in der Datei bleibt die dokumentierte Vorgabe `false` und schaltet allein nicht ein. |
| OP-15 | `desk/gated.py` gehört zu G2-S0-01, wird in Spec 0 aber von keinem Verb benutzt. | in K0.10 als Harness mit Test über ein Test-Verb bauen (wie G2 sagt); Alternative: nach Spec 1 verschieben |
| OP-16 | Die Leser der Fassade (`agents`, `issues`, …) sind Spec-0-Hilfen; Spec 1 bekommt `org.py` und `board.py`. | Spec 1 entscheidet, ob die Leser in `org`/`board` wandern; die Schnittstelle zu `orchestra_kinds` bleibt gleich. |
| OP-17 | Zustand „Budget“ im Desk (`Warnung`, `gestoppt`) ist nur Anzeige aus `spend`; der Stopp selbst ist ORC-09 in Spec 1. | so lassen; Spec 1 nutzt dieselben Schwellen aus `OrchestraConfig`. |

#### Gate-Vorschläge für G3

| Gate | Gegenstand | baut |
| --- | --- | --- |
| G3-S0-01 | K0.7 Golden-Test mit Aufzeichnung auf dem alten Code | Harness |
| G3-S0-02 | K0.8 Bau-Spec `k0_kinds` und SEDRA-Bau `desk/kinds.py` | SEDRA |
| G3-S0-03 | K0.9 Bau-Spec `k0_extensions` und SEDRA-Bau `desk/extensions.py` | SEDRA |
| G3-S0-04 | K0.10 Desk an das Register (`builtin_kinds`, `gated`, `objects`, `actions`) | Harness |
| G3-S0-05 | K0.11 einmalige Änderung `uix_server.py` | Harness |
| G3-S0-06 | K0.12 `chat_tools.VERB_TYPES` aus dem Register | Harness |
| G3-S0-07 | K0.13 Feld `client` und Client-Token | Harness |
| G3-S0-08 | K0.14 CLI `guppi objects`, `guppi act` | Harness |
| G3-S0-09 | K0.15 MCP-Server `desk_mcp.py` | Harness |
| G3-S0-10 | K0.16 Bau-Spec `k0_orchestra_config` und SEDRA-Bau `orchestra/config.py` | SEDRA |
| G3-S0-11 | K0.17 Bau-Spec `k0_orchestra_store` und SEDRA-Bau `orchestra/store.py` | SEDRA |
| G3-S0-12 | K0.18 Bau-Spec `k0_orchestra_service` und SEDRA-Bau `orchestra/service.py` | SEDRA |
| G3-S0-13 | K0.19 Paket `orchestra/`, `orchestra.yaml`, Schalter, Importgrenze | Harness |
| G3-S0-14 | K0.20 Verdrahtung `runtime.py` und `boot()` | Harness |
| G3-S0-15 | K0.21 Bau-Spec `k0_orchestra_kinds` und SEDRA-Bau `desk/orchestra_kinds.py`, Typen in Spec 0 nur lesend (OP-12) | SEDRA |
| G3-S0-16 | K0.22 Übernahme `orchestra_kinds` und Abnahme KERN-01 | Harness |
| G3-S0-17 | K0.23 Guard-Regeln GR-029 bis GR-038 und `permission_levels.yaml` | Harness |
| G3-S0-18 | K0.24 Nachtrag Shell-Werkzeug-Vertrag §10 | Harness |
| G3-S0-19 | K0.25 Abnahme Spec 0 | Harness |

G3 gibt die Bauschritte frei, nicht die Übernahme: Jeder SEDRA-Kandidat kommt nach dem Review einzeln zur Übernahme (G4), jede Harness-Änderung wird gegen ihr G2-Gate geprüft.

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

### Abgleich gegen den Code (G1)

Stand 20.10.2026, geprüft gegen Branch `spec1/orchestrierung` (Commit `3abb023`), Paperclip-Kopie Version 0.3.1. Gelesen, nicht ausgeführt: es lief kein Test, keine Oberfläche, kein Modell. Die Anforderungen oben bleiben unverändert stehen; Korrekturen stehen weiter unten als Vorschlag (alt neben neu) und werden erst mit G1 gültig.

#### O1.1 Agent Manager und Rollen

Befund `agent_manager/`:

| Baustein | Stand | Folge für Spec 1 |
| --- | --- | --- |
| Vorlagen (`service.py`, `agent_import.py`) | `template.yaml` mit Rolle (Freitext), SOUL, Werkzeugen, `permissions`, `capabilities`; der Import erzwingt `network_mode: deny`, `external_write: false`, `privileged: false` und lässt nur die Effekte `read_only` bis `reversible_write` zu; Vertrauen immer `UNVERIFIED`. Es gibt sieben Vorlagen aus `devvm_templates.py` (coder, reviewer, tester, planner, explorer, solo, step_planner), alle für die DevVM. | Es gibt keine Vorlage für Unterarbeiter und Recherche. Eine Vorlage kann kein Netz erlauben (siehe Recherche unten). |
| Instanzen (`instances.py`) | Einstellen = Gate `agent.instantiate` (CLI `hire`, dann `create`); Instanz startet `UNVERIFIED`, Lebenszyklus `ACTIVE`/`QUARANTINED`, Zulassung (`admission`) erst nach `promote` (Gate `agent.promote`, verlangt Suite-Lauf, Review eines anderen Modells und Entscheidung). `revoke` ohne Gate. Kein Desk-Verb, nur CLI. | Kein `reports_to`, kein Budget, kein Rezept, kein Pausieren oder Beenden. Eine Vorlage ohne Suite (Unterarbeiter, Recherche) kann nie `VERIFIED` werden (`no_suite_declared`). |
| Crews (`crews.py`) | Slots mit Pin auf Vorlage und Digest, Workflow-Graph, Unabhängigkeitsregeln; `assemble` empfiehlt nur. | Vorbild für Teamzusammenstellung, aber kein Organigramm: ein Crew-Workflow ist ein Ablauf, keine Berichtslinie. |
| Läufe (`bridge.py`, `run_worker.py`) | Gate `agent.assign` bindet die **Vorlagen-Referenz**, Mission und Eingabe; der Lauf ist ein DevVM-Bau von ein bis zwei Stunden (`benchmarks/devvm_build.py`), Verbrauch nur nachträglich aus Build-Logs (`token_records.py`). | Das ist kein Lauf „Aufgabe des Bretts“ im Sinne von ORC-07; ein Agentenlauf des Teams ist eine Brain-Mission (siehe ORC-07). |
| Rechte der Vorlage | Keine Stufenzahl. Die Stufen 0 bis 6 stehen in `permission_levels.yaml` (Obergrenze je Job) und `max_level` je Rezept in `role_routing.yaml` (Rezept `coder.local_primary`: 2). | `agents.permission_level` (D3.3) hat keine Quelle; Abbildung nötig (Vorschlag unten). |

Befund Rollen und Rezepte:

| Rolle | `role_routing.yaml` | `job_supervisor.yaml` | `token_policy.yaml` | Befund |
| --- | --- | --- | --- | --- |
| planner, coder, reviewer | Rezept `coder.local_primary` listet sie (und tester, researcher u. a.); `enabled: false`, `max_level: 2`, kein Netz, `weights_id: null` | `planner`, `reviewer`, `coder` (coder `mutates: true`) | je ein Eintrag | vorhanden. Nur ein lokales Rezept: Unabhängigkeit Coder/Reviewer ist nicht beweisbar. Das stört nicht, solange der Reviewer nur Hinweise gibt. |
| researcher | im selben Rezept gelistet | `researcher` (Fähigkeit `research`) | Eintrag | Rolle vorhanden, aber ohne Werkzeug dahinter: `tools/web.py` hängt an `runtime.web_tool`, nicht an einer Vorlage. |
| Unterarbeiter | – | – | – | fehlt in allen drei Dateien |

Web-Zugang: `config/web_access.yaml` erlaubt `youtube.com`, `youtu.be`, `github.com`, `raw.githubusercontent.com`, `huggingface.co`; nur `https` und `GET`, 2 MB, 30 s; Guard-Aktion `external_read` (GR-027, ALLOW); Treffer liegen als `untrusted_external` unter `runtime_data/external/`. Für Recherche ist das schmal (keine Suchmaschine, keine Dokumentationsseiten).

Empfehlung zur Frage „Agent Manager erweitern oder `orchestra/org.py`“: **`orchestra/org.py`, der Agent Manager bleibt unverändert.** Begründung:

1. Der Agent Manager beschreibt Zulassung und Qualifikation (`VERIFIED`, Suite, Review). Das Organigramm beschreibt Führung (Vorgesetzter, Budget, Weckrecht). Das sind zwei Fragen mit zwei Gates; in einer Registry vermischt, hinge ein Wechsel der Berichtslinie an der `registry.sqlite` des Agent Managers, die mit Gate-Dateien, Outbox und DevVM verwoben ist (3424 Zeilen).
2. D3.1 verbietet `orchestra/` den Import von `agent_manager` (wegen `test_core_boundary_src` über `runtime.py`); eine Erweiterung dort wäre aus `orchestra/` nur über den Desk-Adapter erreichbar, `org.py` müsste also ohnehin getrennt bleiben.
3. `agents.instance_id` (D3.3) verbindet beides ohne Änderung am Agent Manager: Einstellen = `agent.instantiate` (vorhanden) plus `set_org` (GA-01).
4. Das Wiederverwenden von `hire`/`create` bringt die vorhandene Prüfung des Vorlagen-Digests gratis mit.

Offen dabei: Die AM-Zulassung (`VERIFIED`) verlangt eine Suite je Vorlage. Vorschlag: Orchestra-Läufe (Brain-Missionen) verlangen **keine** AM-Zulassung, weil sie über `wake_agent` und die Guard-Prüfung der Mission laufen; die AM-Zulassung bleibt Voraussetzung nur für DevVM-Bauaufträge (`agent.assign`). Das ist Gate G1-S1-02.

#### ORC-01 bis ORC-14 gegen den Code

Maßstab „prüfbar“: Lässt sich das Abnahmekriterium als automatischer Test mit Fixture oder Fake-Uhr schreiben, ohne Modell und ohne Oberfläche?

| ID | Was existiert | Was fehlt | Prüfbar? |
| --- | --- | --- | --- |
| ORC-01 | `agent.instantiate` mit Gate (CLI `hire`); der Desk-Typ `agent` ist nur ein Platzhalter. | `reports_to`, Rolle als feste Kennung, Rezept, Rechte-Stufe, Budget, Desk-Verb `einstellen`. Zwei Gates (instantiate + `set_org`) statt „ein Gate“. | ja, nach Korrektur (Gates benennen) |
| ORC-02 | nichts (Crews kennen nur Workflow-Abhängigkeiten, mit Zyklusprüfung `_has_cycle`). | Organigramm, Zyklus- und Wurzelprüfung, Tiefe (`max_depth: 6`), Verhalten beim Beenden eines Vorgesetzten. „außer dem obersten“ ist durch OP-6 entschieden (genau ein Unterarbeiter). | ja; Wurzel und Beenden fehlen im Kriterium |
| ORC-03 | Missionen haben keinen Bearbeiter (`created_by` ist fest `captain`). | Typ `issue` mit `assignee` (D3.3); Umhängen während des Checkouts ist ungeregelt. | ja |
| ORC-04 | Muster: `core/mission_lock.py` (nicht blockierende Betriebssystem-Sperre, `mission_execution_busy`) und der Lease des `job_supervisor`. Für Aufgaben des Bretts: nichts. | `BEGIN IMMEDIATE`-Checkout in `board.py`; Freigabe bei Prozessende. | ja: `multiprocessing` mit temporärer Datenbank, 100 Durchläufe |
| ORC-05 | `job_supervisor` kennt `depends_on` und `dependency_satisfied_states` für **Jobs**; `step_journal` kennt `depends_on` nur innerhalb einer Mission. | Blocker zwischen Aufgaben des Bretts, Zyklusprüfung der Blocker. Das Kriterium „Wecken einer blockierten Aufgabe“ ist zweideutig (Agent wecken oder Aufgabe übernehmen). | nein, erst nach Klärung |
| ORC-06 | Das Wort „Herzschlag“ gibt es nur als **Lease-Herzschlag** eines Workers (`job_supervisor.heartbeat`, `reap` alle 30 s im `job_worker`); er weckt keinen Agenten. Keine Zusammenfassung von Weckrufen. | Tabelle `wakeups`, Zusammenfassen (`coalesce_s`), Auslöser „Antwort auf Rückfrage“ (eine Rückfrage-Mechanik ist nirgends definiert). | ja mit Fake-Uhr; Rückfrage unklar |
| ORC-07 | `Brain.create_mission` (Mission, Zustandsautomat, Guard, Audit) und `job_supervisor.create_job`. | Der Adapter „Aufgabe → Mission“. Wecken ohne Gate geht nicht: `wake_agent` ist `CAPTAIN_REQUIRED`. Die Mission trägt keinen Agenten (`created_by` fest `captain`). | ja (Mission-ID, Audit); Gate-Folge offen (OP-4) |
| ORC-08 | `create_job` prüft `permission_level <= contract.permission_level`; Stufen aus `permission_levels.yaml`. | Richtungsprüfung im Organigramm. Widerspruch zu ORC-14: „nur der Unterarbeiter delegiert“ macht ORC-08 für alle anderen leer. „höchstens seinen Rechten“ ist missverständlich (siehe Vorschlag). | ja, nach Korrektur |
| ORC-09 | `token_policy.py` begrenzt nur die Ausgabe **je Aufruf**; `desk/boundaries.py` kennt die Grenze `kosten` (Token je Aufgabe, je Projekt; `fragt`/`zu`/Zahl); `agent_manager/usage_meter.py` summiert nachträglich Build-Logs. | Buchung des Verbrauchs (`spend`), Summe je Agent, 80-%-Warnung, Pause, Entscheidung an den Captain (`decisions.collect` kennt keine Art „Budget“). Die Quelle der Tokenzahl je Lauf ist offen (nicht geprüft, ob `llamacpp.py` sie liefert). Der Euro-Teil hängt an Spec 3. | teilweise (Token ja, Euro erst mit Spec 3) |
| ORC-10 | nichts. `routine` stand im Vertrag, der Eintrag wurde in Build 24 entfernt; `benchmarks/day_queue_*.py` sind feste Ketten ohne Cron. | Cron-Auswertung, Nachhol-Regel, `routine_runs`. Abhängigkeiten: nur `PyYAML`, kein `croniter`; `zoneinfo` kommt im Code nirgends vor (unter Windows braucht es das Paket `tzdata`). | ja mit Fake-Uhr |
| ORC-11 | `job_supervisor.reap`: Lease abgelaufen **und** Herzschlag still, dann `JOB_LEASE_*`/`JOB_ABANDONED`; Stillstand = Herzschläge ohne Fortschritt über `stall_after_s` (300 s), dann `JOB_STALLED`; Fortschritt zählt nur bei geändertem Schrittmarker. | Freigabe des **Checkouts** bei diesen Ereignissen; `reap` läuft nur, solange ein Worker läuft und der Supervisor an ist (Standard aus). `checkout.stall_s: 900` (D3.4) und `stall_after_s: 300` sind zwei Zahlen für dasselbe. Nach einem Absturz von SEDRA bleibt ein Checkout stehen. | ja, nach Korrektur |
| ORC-12 | AM `revoke` (Quarantäne, ohne Gate), `job_supervisor.cancel` (Abbruch mit Quittung des Workers), Mission `PAUSED` (aus den meisten Zuständen erlaubt). | Verben `pausieren`/`fortsetzen`/`beenden` (GA-05 bis GA-07), saubere Freigabe der Aufgabe, Behandlung der Untergebenen. | ja |
| ORC-13 | Missionen tragen `captain_intent` (unveränderlich), `objective`, `context.refs`; Ziel = Vorhaben (`intent`), Projekt = `project` (OP-8). | Auflösung der Kette beim Wecken, Form im Kontext, Umgang mit einem gelöschten Glied. Ob und wie der Kontext-Zusammenbau (`context_assembly`) `context.refs` liest, ist nicht geprüft. | nein, „im Kontext“ ist nicht messbar formuliert |
| ORC-14 | `chat_tools` (Gespräch liest `list_actions`/`propose_action`), Verb `intent.aufgabe_machen`. UIX-04 (Agentenfenster) ist eine Anforderung von Spec 4, noch nicht gebaut. | Verb zum Anweisen, Zerlegung, Zuweisungsrecht nur für den Unterarbeiter, Bericht. Das Kriterium hängt an der Oberfläche (Spec 4) und ist ohne sie nicht prüfbar. Viele Gates: Jeder Lauf braucht `wake_agent` (OP-4). | nein, erst nach Korrektur (Weg über die Kern-API) |

#### Korrekturvorschläge (alte und neue Fassung)

Alle Fassungen gelten für Typ `issue` (OP-1) und das Datenmodell D3.3. Die alte Fassung steht oben in der Anforderungstabelle.

| ID | Alte Fassung | Neue Fassung (Vorschlag) | Grund |
| --- | --- | --- | --- |
| ORC-01 | WENN der Captain einen Agenten einstellt, DANN SOLL das System ihn mit Rolle, Rezept, Vorgesetztem und Budget registrieren. Abnahme: Objekt `agent` mit `reports_to`; Einstellen läuft über ein Gate. | WENN der Captain einen Agenten einstellt (Verb `einstellen` am Typ `agent`), DANN SOLL das System aus einer Vorlage eine Instanz anlegen (Gate `agent.instantiate`), sie mit Rolle, Rezept, Vorgesetztem, Rechte-Stufe und Budget ins Organigramm eintragen (Gate `set_org`) und beides in **einem** Antrag zur Entscheidung stellen. Abnahme: `POST /api/actions` (`agent`, `einstellen`) erzeugt eine Mission mit beiden gebundenen Gates; nach der Freigabe liefert `POST /api/objects {type:"agent", id}` `reports_to`, Rolle, Stufe, Budget; ohne Freigabe entsteht keine Zeile in `agents`. | Zwei Gates sind im Code Tatsache; „ein Gate“ war nicht prüfbar. |
| ORC-02 | Jeder Agent außer dem obersten SOLL genau einen Vorgesetzten haben. Abnahme: Ein Zyklus wird abgelehnt. | Jeder aktive Agent außer dem Unterarbeiter SOLL genau einen Vorgesetzten haben; es gibt genau einen aktiven Agenten ohne Vorgesetzten (OP-6). `org.py` lehnt ab: Zyklus, zweite Wurzel, Tiefe über `max_depth`, Beenden eines Agenten mit aktiven Untergebenen. Abnahme: je ein Test für diese vier Fälle mit Fehlercode. | OP-6 ist entschieden, der Wortlaut „außer dem obersten“ ist offen geblieben; das Beenden eines Vorgesetzten fehlte. |
| ORC-03 | WENN eine Aufgabe zugewiesen wird, DANN SOLL sie genau einen Bearbeiter haben. Abnahme: Zweite Zuweisung ersetzt die erste und schreibt Audit. | WENN eine Aufgabe (`issue`) zugewiesen wird, DANN SOLL sie genau einen aktiven Bearbeiter haben. Eine zweite Zuweisung ersetzt die erste und schreibt `ORC_TASK_ASSIGNED` mit altem und neuem Bearbeiter, außer die Aufgabe ist ausgecheckt (dann `task_checked_out`; umhängen erst nach der Freigabe). Zuweisung an pausierte oder beendete Agenten wird abgelehnt. | Umhängen während eines Laufs hätte zwei Läufe erzeugt. |
| ORC-04 | WENN zwei Agenten dieselbe Aufgabe gleichzeitig übernehmen wollen, DANN SOLL genau einer Erfolg haben. Abnahme: Paralleltest mit 2 Prozessen, 100 Durchläufe, nie zwei Halter. | Anforderung unverändert; Abnahme geschärft: In 100 Durchläufen mit je einer neuen Aufgabe und zwei Prozessen gewinnt genau einer, der andere bekommt `task_already_checked_out`, danach steht `checkout_by` auf dem Sieger. Test auf einer temporären Datenbank. | schon prüfbar; nur der Fehlercode (D5) fehlte im Kriterium. |
| ORC-05 | WENN eine Aufgabe einen offenen Blocker hat, DANN SOLL sie nicht ausgeführt werden. Abnahme: Wecken einer blockierten Aufgabe führt zu keinem Lauf. | WENN eine Aufgabe einen offenen Blocker hat, DANN SOLL ihr Checkout mit `task_blocked` abgelehnt werden; ein Weckruf, der nur blockierte Aufgaben betrifft, endet ohne Mission und ohne Modellstart. WENN der letzte Blocker erledigt ist, DANN SOLL ein Weckruf (Grund `antwort`) für den Bearbeiter entstehen. Blocker-Zyklen werden abgelehnt. | „Wecken“ meinte zwei Dinge; der zweite Satz schließt die Lücke, dass eine erledigte Blockade niemanden weckt. |
| ORC-06 | WENN einem Agenten Arbeit zugewiesen wird oder eine Antwort auf seine Rückfrage eingeht, DANN SOLL der Herzschlag ihn wecken; mehrere Weckrufe kurz nacheinander werden zusammengefasst. Abnahme: 3 Zuweisungen in 1 s ergeben 1 Lauf. | WENN einem Agenten Arbeit zugewiesen wird, der Captain ihm eine Anweisung gibt oder ein Kommentar an einer seiner Aufgaben eingeht, DANN SOLL der Herzschlag einen Weckruf eintragen; Weckrufe desselben Agenten innerhalb von `coalesce_s` werden zu einem zusammengefasst. Ein Weckruf wird nur mit gültiger Freigabe zum Lauf (`wake_agent`: einzeln oder Dauerfreigabe, ORC-15). Abnahme (Fake-Uhr, ohne Modell): 3 Zuweisungen in 1 s ergeben 1 Weckruf; ohne Freigabe entsteht 1 Entscheidung und kein Lauf. „Rückfrage“ entfällt als eigener Begriff: Antwort = Kommentar. | Der Herzschlag des Supervisors ist ein Lease-Takt, kein Wecken; ohne den Freigabe-Satz würde das Kriterium „1 Lauf“ am Gate scheitern. |
| ORC-07 | WENN ein Agent geweckt wird, DANN SOLL seine Arbeit als Mission mit Guard-Prüfung und Audit laufen. Abnahme: Jeder Lauf hat eine Mission-ID und Audit-Einträge. | WENN ein Agent mit gültiger Freigabe geweckt wird, DANN SOLL seine Arbeit als Brain-Mission laufen, deren `captain_intent` aus der Aufgabe gebildet wird (nie aus Modellausgabe), mit Guard-Prüfung der Mission und Audit `ORC_WAKE` (Agent, Aufgabe, Mission-ID). Abnahme: Jeder Lauf hat eine Mission-ID in `tasks.mission_id` und `ORC_WAKE`; die Mission nennt den Agenten in `context.refs`. DevVM-Bauaufträge für Coder laufen weiter über `agent.assign` (zweites Gate). | Der Agent Manager startet DevVM-Builds, keine Brain-Missionen; die Mission kennt keinen Agenten (`created_by` fest `captain`; `core/` bleibt unberührt). |
| ORC-08 | WENN ein Agent eine Teilaufgabe erstellt, DANN SOLL sie nur an Agenten unter ihm im Organigramm gehen, mit höchstens seinen Rechten. Abnahme: Delegation nach oben oder zur Seite wird abgelehnt. | WENN ein Agent eine Teilaufgabe erstellt (`delegate_task`), DANN SOLL das nur gehen, wenn er delegieren darf (Rolle Unterarbeiter, ORC-14) und der Empfänger unter ihm im Organigramm steht. Die Teilaufgabe erhält die Obergrenze `min(Obergrenze der Elternaufgabe, Stufe des Empfängers)`. Abnahme: Unterarbeiter → Coder erlaubt; Coder → Unterarbeiter (oben), Coder → Reviewer (Seite), Planer → Coder (`delegation_not_allowed`) abgelehnt; die Obergrenze der Teilaufgabe ist nie höher als die der Elternaufgabe. | „höchstens seine Rechte“ würde Coder-Aufgaben vom Unterarbeiter mit Stufe 1 ausschließen. Die Obergrenze wird deshalb von der Aufgabe geerbt (neue Spalte, G1-S1-24). |
| ORC-09 | WENN ein Agent 80 % seines Budgets erreicht, DANN SOLL das System warnen; bei 100 % SOLL es den Agenten pausieren und eine Entscheidung an den Captain stellen. Abnahme: Budget in Token (lokal) und Euro (Cloud); Pause wird ausgelöst. | (a) Nach jedem Lauf bucht das System den Verbrauch in `spend`. (b) Vor jedem Lauf prüft es: Restbudget ≥ Ausgabegrenze des Laufs (`token_policy`), sonst kein Lauf. (c) Bei 80 % `ORC_BUDGET_WARNING` und Hinweis im Posteingang; bei 100 % Agent `pausiert`, `ORC_BUDGET_STOP`, eine Entscheidung „Budget erhöhen und fortsetzen?“ (ein Antrag mit `set_budget` und `resume_agent`). (d) Die Projekt-Grenze `kosten` aus `desk/boundaries.py` gilt zusätzlich; die strengere gewinnt. Abnahme: Fixture-Verbräuche lösen Warnung, Pause und Entscheidung aus; ein Lauf mit zu wenig Restbudget startet nicht. Euro-Budget erst mit Spec 3 (Startphase 0 €). | Ohne Vorabprüfung überschreitet ein Lauf das Budget um bis zu `output_cap`; Pause allein löst die Entscheidung nicht aus. |
| ORC-10 | WENN der Zeitpunkt einer Routine erreicht ist, DANN SOLL eine Aufgabe für den zuständigen Agenten entstehen; verpasste Läufe werden nach Regel nachgeholt oder ausgelassen. | Anforderung unverändert. Ergänzt: Pro Termin entsteht höchstens eine Aufgabe (`routine_runs`); ist die Aufgabe der vorigen Auslösung noch offen, entsteht keine neue (Vorbild Paperclip `coalesce_if_active`); `max_catch_up` begrenzt das Nachholen; Cron und Zeitzone ohne neue Abhängigkeit (Eigenbau über die Standardbibliothek, `tzdata` nur wenn die Zeitzone gebraucht wird). Abnahme: Fake-Uhr mit Termin, Nachholfall, Sommerzeitwechsel, doppeltem Takt. | Ohne Überlappungsregel häuft eine langsame Routine Aufgaben an. |
| ORC-11 | WENN ein Lauf länger als die eingestellte Zeit keinen Fortschritt meldet, DANN SOLL das System Stillstand melden und die Aufgabe freigeben. Abnahme: Mechanik aus `job_supervisor` wiederverwendet. | Zwei Fälle. (a) Läuft der Lauf als Supervisor-Job, gibt `orchestra` den Checkout frei, sobald `JOB_STALLED` oder `JOB_ABANDONED` kommt. (b) Beim Start der Orchestrierung gibt sie jeden Checkout frei, dessen Lauf nicht mehr lebt. Eine Zahl für „Stillstand“: `stall_after_s` des Supervisors; `checkout.stall_s` entfällt. Abnahme: Test mit Fake-Uhr für (a) und mit künstlich verwaistem Checkout für (b). | `reap` läuft nur mit Worker; ein Absturz ohne Neustart-Abgleich hinterließe Aufgaben, die niemand mehr anfasst. |
| ORC-12 | Der Captain SOLL jeden Agenten pausieren, fortsetzen und beenden können; eine laufende Aufgabe wird dabei sauber freigegeben. Abnahme: Nach Beenden hat die Aufgabe keinen Halter mehr. | Anforderung unverändert; ergänzt: Pausieren und Beenden brechen einen laufenden Lauf ab (`job_supervisor.cancel`, Mission `PAUSED`), die Aufgabe geht auf `offen` ohne Bearbeiter mit Systemkommentar; ein pausierter Agent bekommt keine Weckrufe; der Unterarbeiter ist nicht beendbar, solange aktive Untergebene da sind. Quarantäne im Agent Manager (`revoke`) pausiert den Agenten auch im Organigramm. Abnahme: Halter leer, Lauf abgebrochen, Audit, kein neuer Weckruf. | Der Abbruch des Laufs fehlte im Kriterium. |
| ORC-13 | Jede Aufgabe SOLL ihre Zielkette (Ziel → Projekt → Aufgabe) an den Agenten mitgeben. Abnahme: Die Mission enthält die Zielkette im Kontext. | WENN ein Lauf beginnt, DANN SOLL das System die Kette Vorhaben (`goal_ref`) → Projekt (`project_id`) → Elternaufgaben → Aufgabe zum Zeitpunkt des Weckens auflösen und dem Lauf als abgegrenzten, in der Länge begrenzten Textblock mitgeben. Fehlt ein Glied, läuft der Lauf mit dem Hinweis „Glied nicht gefunden“, ohne Absturz. Abnahme: Der Kontext des Laufs enthält die Glieder in dieser Reihenfolge; ein gelöschtes Vorhaben erzeugt den Hinweis. | „im Kontext“ ist nicht messbar; Reihenfolge, Grenze und Fehlerfall fehlten. |
| ORC-14 | WENN der Captain dem Team eine Anweisung gibt, DANN SOLL sie beim Unterarbeiter ankommen; er zerlegt sie in Aufgaben, weist sie den Agenten unter ihm zu und meldet dem Captain das Ergebnis. Nur der Unterarbeiter delegiert. Abnahme über Shell D (UIX-04). | WENN der Captain dem Team eine Anweisung gibt (Verb `anweisen` am Typ `agent`, Ziel Unterarbeiter, Gate `create_new_artifact`), DANN SOLL eine Aufgabe für den Unterarbeiter mit Kommentar des Captains und ein Weckruf (Grund `captain`) entstehen. Der Unterarbeiter zerlegt, weist den Agenten unter ihm zu und meldet dem Captain das Ergebnis (ORC-18). Nur der Unterarbeiter delegiert. Abnahme über die Kern-API, ohne Oberfläche: `anweisen` erzeugt Aufgabe und Weckruf; ein Fixture-Lauf des Unterarbeiters legt Teilaufgaben bei Planer, Coder und Reviewer an; `delegate_task` des Planers wird abgelehnt; jeder Lauf trägt `ORC_WAKE`. UIX-04 prüft Spec 4 getrennt. | Die Abnahme darf nicht an einer Oberfläche hängen, die erst Spec 4 baut. |

#### Neue Anforderungen (Vorschlag)

| ID | Anforderung (EARS) | Abnahmekriterium |
| --- | --- | --- |
| ORC-15 | WENN der Captain für einen Agenten eine Dauerfreigabe für `wake_agent` erteilt, DANN SOLL der Guard Weckrufe dieses Agenten ohne weitere Rückfrage zulassen, solange Agent, Rechte-Stufe, Rezept, Vorgesetzter und Budget-Obergrenze unverändert sind, das Budget nicht aufgebraucht ist, das Ablaufdatum nicht erreicht ist und die Zahl erlaubter Läufe nicht überschritten ist. | Tests am Guard: Lauf mit Dauerfreigabe erlaubt und gezählt; nach Ablauf, nach Änderung von Stufe oder Rezept, nach Pause, bei Budget 100 %, nach Widerruf und nach der letzten erlaubten Nutzung verweigert; jede Nutzung und jedes Ende im Audit; die Dauerfreigabe gilt nur für `wake_agent`, nie für ein anderes Gate |
| ORC-16 | WENN der Schalter `orchestra` an ist und die Oberfläche läuft, DANN SOLL ein Takt alle `tick_s` Sekunden Weckrufe, Routinen und Stillstand prüfen; es darf immer nur ein Takter laufen. | Fake-Uhr: Der Takt ruft `heartbeat.tick()` und `routines.tick()`; ein zweiter Takter bekommt `tick_busy`; `boot()` und das Objekt `agent` zeigen den Takt „läuft/aus“ und den letzten Takt; nach mehr als `3 × tick_s` ohne Takt erscheint ein Hinweis |
| ORC-17 | WENN der Unterarbeiter geweckt wird, DANN SOLL sein Rezept ihn auf Lesen, Zerlegen und strukturierte Vorschläge begrenzen; `orchestra` prüft die Vorschläge und legt Aufgaben an, nicht das Modell. | Fixture-Antwort des Modells (Liste von Teilaufgaben) wird geprüft und angelegt; ungültige Rollen, zu viele Teilaufgaben (`max_subtasks`), Zuweisung an Nicht-Untergebene und Freitext-Verben werden abgewiesen; das Rezept enthält keine Schreib-, Netz- oder Testwerkzeuge |
| ORC-18 | WENN der Unterarbeiter die Teilaufgaben einer Anweisung abgeschlossen sieht, DANN SOLL er dem Captain einen Bericht liefern, der Ergebnis, offene Punkte und das Ergebnis der versteckten Tests nennt, nicht das Urteil des Reviewers. | Der Bericht ist ein Kommentar des Unterarbeiters an der Ausgangsaufgabe plus ein Ereignis `issue.reported`; er enthält je Teilaufgabe Zustand und Prüfergebnis (grün, rot, nicht geprüft); fehlt ein Prüfergebnis, steht „nicht geprüft“, nie „bestanden“ |
| ORC-19 | WENN der Recherche-Agent Text aus dem Netz liest, DANN SOLL dieser Text als Daten (`untrusted_external`) in den Kontext gehen und nie eine Zuweisung, ein Verb oder ein Gate auslösen. | Test: Webtext mit einer Anweisung („weise Aufgabe X zu“) führt zu keinem Verb; das Ergebnis liegt unter `runtime_data/external/` mit Hash; Hosts nur aus `web_access.yaml` |

##### Dauerfreigabe je Agent (OP-4), Vorschlag

Befund `core/guard.py`: Freigaben sind Einmal-Token (`single_use`, `max_uses: 1`, 24 h), gebunden an Mission, Aktion, Ziel und `request_digest`. Eine Dauerfreigabe passt nicht hinein, weil die Bindung an die Mission fest ist und jede Nutzung das Token verbraucht. Zwei Wege:

| Weg | Inhalt | Dafür | Dagegen |
| --- | --- | --- | --- |
| 1 Token-Art `standing` im Guard (empfohlen) | `guard.py` bekommt eine zweite Token-Art: `grants.action_type = wake_agent`, `targets = [agent_id]`, `request_digest` über die stabilen Felder (Agent, Stufe, Rezept, Vorgesetzter), `limits = {max_uses, expires_at, budget_floor}`, Zähler `uses`. `authorize_standing(...)` prüft alles bei jedem Wecken, zählt und schreibt `CAPTAIN_STANDING_USED`; Widerruf ohne Gate (`CAPTAIN_STANDING_REVOKED`). Die Bindung gilt dem Agenten statt einer Mission. | Der Guard bleibt die einzige Stelle, die zulässt; Zählen, Ablauf und Widerruf laufen unter der vorhandenen Token-Sperre; das Audit ist lückenlos | Eingriff in `core/guard.py` (geschätzt 60 bis 80 Zeilen plus Tests, nicht gemessen); eigenes Kern-Gate |
| 2 Neue Aktion `wake_agent_standing` (ALLOW), Prüfung in `orchestra` | Regel in `guard_rules.yaml`, Bedingungen und Zähler in `orchestra.db` | kein Eingriff in `core/` | Der Guard sieht nur „ALLOW“ und kann die Grenzen nicht prüfen; ein Fehler in `orchestra` öffnet das Wecken ohne Gegenkontrolle des Guards; das widerspricht „strenger als Paperclip“ |

Vorschlag für die Grenzen (Startwerte ohne Messung): nur Agenten mit Stufe ≤ 3 (die Stufen 4 bis 6 behalten Einmal-Freigaben); Ablauf Standard 7 Tage, höchstens 30; höchstens 50 Läufe je Dauerfreigabe; Erteilen ist `CAPTAIN_REQUIRED` mit Anzeige von Agent, Stufe, Rezept, Budget, Ablauf und Lauf-Zahl; ein Antrag darf mehrere Agenten enthalten, entschieden wird je Agent (Regel 6); die Dauerfreigabe deckt **nur** das Wecken: Folge-Gates im Lauf (`agent.assign`, `paid_action`, `external_write`, `install_module`) bleiben einzeln. Sie erlischt bei Ablauf, Verbrauch, Budget 100 %, Pause, Beenden, Quarantäne, Änderung von Stufe, Rezept, Vorgesetztem oder Budget-Obergrenze und auf Widerruf.

##### Takt des Herzschlags (OP-9), Vorschlag

Befund: Einen Takt für Agenten gibt es nicht. `job_worker.Worker` reapt alle `reap_every` (30 s), aber nur, solange ein Worker-Thread läuft und der Supervisor an ist. `uix_server.py` startet Daemon-Threads für Einzelaufgaben, keinen Dauertakt für die Orchestrierung (nicht im Detail geprüft). Empfehlung: **Takt in der Oberfläche** (wie in D3.2), `tick()` idempotent und durch eine Betriebssystem-Sperre (Muster `mission_lock.exclusive`, Datei `orchestra/tick.lock`) auf einen Takter begrenzt. Damit lässt sich später ein eigener Dienst (`guppi orchestra run`) hinzufügen, ohne zwei Takter zu riskieren. Ein eigener Dienst ist erst nötig, wenn Routinen nachts ohne Oberfläche laufen sollen; bis dahin trägt die Nachhol-Regel (E2E-6).

##### Rezept und Vorlage des Unterarbeiters, Vorschlag

- Vorlage `guppi.orchestra.foreman` (Anzeigename Unterarbeiter), Effekt `proposal_only`, `workspace_mode: read_only`, `network_mode: deny`; gebaut im Harness (Vorlagen entstehen durch KI-Sitzungen, Datei mit Prüfsumme), Vertrauen `UNVERIFIED`.
- Rolle `foreman` in `job_supervisor.yaml` (`mutates: false`, Fähigkeit `orchestration`), in `role_routing.yaml` im Rezept `coder.local_primary` gelistet (`max_level` 2), in `token_policy.yaml` zunächst wie `planner` (Denken an, 4096 Ausgabe). Die Zahlen sind Startwerte, gemessen ist nichts.
- Das Modell bekommt die Anweisung, die Zielkette, die Liste der Agenten unter ihm (Rolle, Stufe, offene Aufgaben) und das Budget; es liefert **nur eine strukturierte Liste** (Titel, Rolle, Blocker, Akzeptanz). `orchestra` prüft und legt an (ORC-17). So bleibt das Modell ohne Verb, und Webtext aus der Recherche kann kein Verb erreichen (ORC-19).
- Schleifenschutz: Obergrenze für Teilaufgaben je Anweisung, ein Zerlegungslauf je Elternaufgabe; `jobs/loop_guard.py` und `jobs/runaway_guard.py` sind Kandidaten (nicht auf Eignung geprüft).
- Der Planer hilft: Der Unterarbeiter kann dem Planer eine Aufgabe „Zerlegung vorschlagen“ zuweisen; der Vorschlag kommt als Kommentar zurück, entschieden und angelegt wird beim Unterarbeiter.

##### Recherche, Vorschlag

Vorlage `guppi.orchestra.researcher`, Effekt `read_only`. Das Web-Werkzeug bleibt ein **Host-Werkzeug** (`tools/web.py`, Guard `external_read`), weil Vorlagen `network_mode: deny` erzwingen und der Import nichts anderes zulässt. Der Recherche-Lauf ist deshalb eine Brain-Mission, kein DevVM-Lauf. Die Hostliste (fünf Domains) wird für Spec 1 nicht geändert; eine Erweiterung ist eine eigene Captain-Entscheidung (G1-S1-23).

##### Abbildung Vorlage → Rechte-Stufe, Vorschlag

`agents.permission_level` = `min(Stufe aus dem Effekt der Vorlage, max_level des Rezepts)`; Effekt `read_only` → 1, `proposal_only` → 1, `reversible_write` (Sandbox-Arbeitsbereich) → 2, `preview` → 3. Stufe 4 und höher bekommt kein Teammitglied. Die Delegation kann die Stufe nur senken.

#### Vergleich mit Paperclip (Kopie 0.3.1), nur Lehrreiches

| Thema | Paperclip | Lehre für SEDRA |
| --- | --- | --- |
| Organigramm | `agents.reportsTo` (Selbstverweis), Kette per Aufstieg über `reportsTo` (`server/src/services/agents.ts`) | Selbstverweis genügt; Zyklus durch Aufstieg prüfen. SEDRA ergänzt Wurzelregel und Beenden-Regel. |
| Aufgaben und Checkout | `issues.assigneeAgentId`, `checkoutRunId`, `executionRunId`, `executionLockedAt`; Checkout und Freigabe binden an einen **Lauf**; PostgreSQL | Checkout an den Lauf binden (D3.3 hat `checkout_run`); beim Lauf-Ende wird freigegeben. SQLite mit `BEGIN IMMEDIATE` genügt. |
| Weckrufe | Tabelle `agent_wakeup_requests` mit `source` (timer, assignment, on_demand, automation), `status`, `coalescedCount`, `idempotencyKey`, `runId`; die Zuweisung löst den Weckruf aus (`issue-assignment-wakeup.ts`) | Idempotenzschlüssel ergänzen: derselbe Auslöser (z. B. Kommentar-ID) erzeugt nie zwei Weckrufe (G1-S1-24). `wakeups.reason` deckt die Quelle, `done_at` den Status. |
| Takt | `setInterval` im Serverprozess (`server/src/index.ts`, `heartbeat.tickTimers`) | Takt im Hauptprozess ist dort Standard; bestätigt OP-9. |
| Budget | `budget_policies`: Bereich (Agent, Projekt, Firma), Fenster, `warnPercent` 80, `hardStopEnabled`, Reservierung (`reservationCents`), Vorfälle (`budget_incidents`); `agents.pauseReason` | Die Reservierung vor dem Lauf entspricht der Vorabprüfung in ORC-09. Ein Vorfallsdatensatz je Überschreitung wäre für die Entscheidung des Captains nützlich (G1-S1-25). |
| Routinen | `routines` mit `concurrencyPolicy` (Vorgabe `coalesce_if_active`), `catchUpPolicy` (Vorgabe `skip_missed`), Revisionen | Überlappungsregel übernommen (ORC-10); die Vorgabe „auslassen“ statt „nachholen“ ist die vorsichtigere Voreinstellung. Revisionen einer Routine bleiben weggelassen. |
| Freigaben | `approvals`, `issue_approvals` | SEDRA bleibt strenger; ein Gegenstück zu Einmal-Token mit Bindung hat Paperclip nicht gezeigt (nicht vertieft geprüft), die Dauerfreigabe ist SEDRA-eigen. |

Bewusst nicht übernommen: mehrere Firmen, Export/Import, Plugins, Identitätsschlüssel je Agent, Chat-Kanäle (siehe Ist-Stand-Tabelle).

#### Offene Fragen für den Captain

1. Sollen Orchestra-Läufe ohne AM-Zulassung (`VERIFIED`) erlaubt sein (G1-S1-02)?
2. Rollenkennung `foreman` oder `unterarbeiter` in Konfigurationsdateien (G1-S1-20)?
3. Dauerfreigabe: Weg 1 (Kern) oder Weg 2 (kein Kern)? Zahlen 7 Tage, 30 Tage, 50 Läufe, Stufe ≤ 3 (G1-S1-16 bis 18)?
4. Welche Hosts braucht die Recherche zusätzlich (G1-S1-23)?

Nicht geprüft: Ausführen von Tests oder Oberfläche; ob lokale Modellantworten Tokenzahlen liefern (Quelle für `spend`); `context_assembly` und `context.refs`; ob `loop_guard`/`runaway_guard` für den Unterarbeiter taugen; Tiefe von Shell D (`uix/shells/paperclip/`); die Hintergrundthreads in `uix_server.py` im Detail; Paperclip nur an den genannten Dateien gelesen.

#### Gate-Liste G1 Spec 1

Jede Zeile wird einzeln entschieden (Vorschlag: alle wie empfohlen).

| Gate | Gegenstand | Vorschlag |
| --- | --- | --- |
| G1-S1-01 | Ort des Organigramms: `orchestra/org.py`, Agent Manager unverändert | ja |
| G1-S1-02 | ORC-01 neu: Einstellen in einem Antrag (`agent.instantiate` + `set_org`); Orchestra-Läufe brauchen keine AM-Zulassung, DevVM-Bauaufträge schon | ja |
| G1-S1-03 | ORC-02 neu (Wurzel, Zyklus, Tiefe, Beenden mit Untergebenen) | ja |
| G1-S1-04 | ORC-03 neu (kein Umhängen während des Checkouts) | ja |
| G1-S1-05 | ORC-04 geschärft (Fehlercode, 100 Durchläufe) | ja |
| G1-S1-06 | ORC-05 neu (`task_blocked`, Weckruf bei erledigtem Blocker) | ja |
| G1-S1-07 | ORC-06 neu (Weckruf statt Lauf, Freigabe-Satz, „Rückfrage“ entfällt) | ja |
| G1-S1-08 | ORC-07 neu: Agentenlauf = Brain-Mission; Coder-Bauaufträge zusätzlich über `agent.assign` | ja |
| G1-S1-09 | ORC-08 neu (Delegationsrecht, vererbte Obergrenze) | ja |
| G1-S1-10 | ORC-09 neu (Buchung, Vorabprüfung, Pause mit Entscheidung, Zusammenspiel mit der Grenze `kosten`) | ja |
| G1-S1-11 | ORC-10 ergänzt (keine Überlappung, Cron im Eigenbau, `tzdata` nur bei Bedarf) | ja |
| G1-S1-12 | ORC-11 neu (Freigabe bei Supervisor-Ereignis, Neustart-Abgleich, eine Zahl) | ja |
| G1-S1-13 | ORC-12 ergänzt (Lauf abbrechen, Quarantäne pausiert) | ja |
| G1-S1-14 | ORC-13 neu (Kette zum Weckzeitpunkt, begrenzt, Fehlerfall) | ja |
| G1-S1-15 | ORC-14 neu (Verb `anweisen`, Abnahme über die Kern-API) | ja |
| G1-S1-16 | ORC-15 Dauerfreigabe: Weg 1 (Token-Art `standing` im Guard) statt Weg 2 | ja (Weg 1) |
| G1-S1-17 | Kern-Gate (Grundsatz): Änderung an `core/guard.py` für G1-S1-16; Diff und Tests folgen in Stufe 2 zur Einzelfreigabe | ja, nur Grundsatz |
| G1-S1-18 | Grenzen der Dauerfreigabe: Stufe ≤ 3, Standard 7 Tage, höchstens 30, höchstens 50 Läufe, deckt nur das Wecken | ja |
| G1-S1-19 | ORC-16 Takt in der Oberfläche mit Takt-Sperre; eigener Dienst später | ja |
| G1-S1-20 | ORC-17 Rezept des Unterarbeiters (Vorlage `proposal_only`, Rolle `foreman` oder `unterarbeiter`, Modell liefert nur eine strukturierte Liste) | ja, Kennung `foreman` |
| G1-S1-21 | ORC-18 Bericht des Unterarbeiters (Kommentar plus Ereignis, Prüfergebnis statt Reviewer-Urteil) | ja |
| G1-S1-22 | ORC-19 Recherche: Web-Werkzeug bleibt Host-Werkzeug, Text ist Daten, nie Verb | ja |
| G1-S1-23 | Hostliste `web_access.yaml` für die Recherche: unverändert lassen | ja (unverändert) |
| G1-S1-24 | Datenmodell-Nachträge für O1.2: `tasks.max_level`, `agents.can_delegate`, Tabelle `standing_approvals` (Spiegel der Guard-Token), `wakeups.idempotency_key` | ja |
| G1-S1-25 | Paperclip-Lehren: Vorfallsdatensatz je Budget-Überschreitung; Voreinstellung „auslassen“ bei Routinen | ja, Voreinstellung `auslassen` |

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

- [x] O1.1 Agent Manager auf Berichtslinien und Instanz-Status prüfen; Erweiterung oder neues `org.py` festlegen → Empfehlung `org.py` (G1-S1-01, 20.10.2026)
- [ ] O1.2 Datenmodell final, Migration für bestehende Agenten → G2
- [ ] O1.3 Bau-Specs schreiben: `orc_org`, `orc_board`, `orc_heartbeat`, `orc_budget`, `orc_routines` in `devvm_specs/`, je mit Referenz und `spec_check.py` = ok → G3
- [ ] O1.4 Neue Guard-Aktionen und Desk-Registrierung (Harness, KI-Sitzung)
- [ ] O1.5 Bau durch SEDRA, Review, Übernahme → G4

## Spec 2 – Modell-Scheduler: parallele Agenten

Die GPU-Lease bleibt, bekommt aber eine zweite Ebene: Ein Prozess besitzt den Modellserver (Lade-Lease), und ein Scheduler verteilt dessen parallele Slots an Agentenläufe (Slot-Lease). Heute lädt nur ein Prozess Modelle und jedes Rezept hat 1 Slot; das ändert eine Regel aus `ENTWICKLUNG.md` und braucht deshalb eine Captain-Freigabe und eine Doku-Änderung.

Stand Stufe 1: 20.10.2026, Branch `spec2/modelle-scheduler`, gegen den Code von Commit `3abb023` geprüft. Vorlage für G1; jede Zeile der Gate-Liste (G1-S2-a bis G1-S2-m) wird einzeln entschieden. Es wurde nichts ausgeführt, kein Modell geladen und nichts gemessen; alle Zahlen unten stammen aus dem Code, aus `MODELLE.md` oder sind als „zu messen“ markiert.

### Anforderungen

Die Tabelle bleibt unverändert; die Korrekturvorschläge stehen unter „Abgleich gegen den Code (G1)“ und werden erst mit G1 eingearbeitet.

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

### Abgleich gegen den Code (G1)

Geprüft wurden `models/llama_server_runtime.py`, `models/model_loader.py`, `models/role_routing.py`, `jobs/testlab.py`, `jobs/resource_scheduler.py`, `jobs/job_supervisor.py`, `core/step_journal.py`, `desk/events.py`, `models/gpu_canary.py`, `models/gpu_preflight.py`, `uix_server.py` (Lease), die Konfigurationen `llama_server.yaml`, `resource_scheduler.yaml`, `model_loader.yaml`, `role_routing.yaml` sowie `benchmarks/context_ladder.py`, `connection_check.py`, `devvm_build.py`, `testlab_cli.py`.

Befunde, die mehrere Anforderungen betreffen:

- **B-1 Zwei Lease-Wege.** Die Lease `gpu` (`TestLab.try_acquire`, `BEGIN IMMEDIATE`, Herzschlag, Übernahme bei Stillstand oder totem Prozess) nehmen heute die Benchmarks (`lab.lease(...)`) und der Desk beim manuellen Laden (`uix_server.py`, hält die Lease, solange das Modell geladen ist). Der Produktpfad der Jobs (`job_supervisor` → `ModelLoader.ensure` → `LlamaServerRuntime.load_model`) nimmt sie **nicht**. Er schützt sich nur durch `server_already_running` und `port_in_use`.
- **B-2 Ein Server, eine Instanz.** `LlamaServerRuntime` führt genau eine Instanz (`_info`, ein Port 8089); ein zweites `load_model` wird mit `server_already_running` abgelehnt. Mehrere Modelle gleichzeitig sind nicht vorgesehen (passt zum Zielbild: ein Modellserver, mehrere Slots).
- **B-3 `parallel` kommt aus der globalen Loader-Konfiguration, nicht aus dem Rezept.** `ModelLoader` reicht `config.parallel` (`model_loader.yaml`, Standard 1, erlaubt 1 bis 8) an `load_model` durch. `build_command` setzt `-np` und lässt 1 bis 8 zu. Die Prüfung der Rezepte (`role_routing.py`, `profile.server`) kennt weder `slots` noch `parallel`: Ein Rezept mit diesen Feldern würde mit `profile.server` abgelehnt.
- **B-4 Gesamtkontext gegen Kontext je Slot.** `-c` ist die Summe über alle Slots; `load_model` meldet den vom Server angewendeten Wert aus `/props` (`n_ctx`) als `contextLength`. Der Loader vergleicht diesen Wert mit dem vom Router gewünschten Fenster (`want`) und lädt bei Abweichung um oder lehnt ab (`loaded_with_other_context`). Mit N Slots stimmt der Vergleich nicht mehr, wenn nicht klar festgelegt ist, ob das Rezept das Fenster je Slot oder insgesamt meint. Ob Build b11160 die Summe fest auf die Slots teilt oder einen gemeinsamen KV-Puffer nutzt, ist ungemessen (Spec nennt es schon im Design).
- **B-5 Messwerkzeuge laden fest mit 1 Slot.** `context_ladder.py` (Zeilen 124, 208) und `connection_check.py` (Zeile 73) rufen `load_model(..., parallel=1, ...)`; `--set` ändert nur Felder aus `profile.server`, nicht den Slot-Wert. Die Messung nach Messplan Schritt 1 und 3 braucht deshalb eine Erweiterung der Werkzeuge (`--parallel`), also Harness-Code, den es noch nicht gibt. `devvm_build.py` hat `--parallel` (und `agent_manager/run_worker.py` begrenzt es auf 1 bis 2); darüber ist 2 Slots im Bau schon möglich (`parallel_check`).
- **B-6 Sicherheitshinweis zu `gpu_preflight`.** `clear_leftovers` beendet Prozesse nach der GUPPI-Startsignatur der Kommandozeile (`--no-webui`, `--spec-type`), nicht nach eigener PID. Das ist enger als ein Namensmuster, aber nicht dasselbe wie Regel 2 („nur eigene Prozesse über ihre PID“). Mit einem dauerhaft laufenden Scheduler-Server muss die Regel eindeutig sein, sonst räumt ein Benchmark den Server des Schedulers ab. Vorschlag: Der Scheduler schreibt seine PID in die Lease; `clear_leftovers` fasst nur Prozesse an, die keiner lebenden Lease gehören.

Zeile für Zeile:

| ID | Was existiert | Was fehlt | Abnahme prüfbar? | Befund |
| --- | --- | --- | --- | --- |
| SCH-01 | `build_command(parallel=1..8)` setzt `-np`; `LlamaServerConfig`/`load_model(parallel=…)` reichen es durch; `devvm_build --parallel` nutzt es | Rezept-Feld `server.slots` (wird von der Rezeptprüfung abgelehnt, B-3); Messwerkzeug für gleichzeitige Anfragen; Regel, was `-c` bei N Slots bedeutet (B-4) | nein – „parallel beantwortet“ und „Messung“ ohne Schwelle | teilweise vorhanden |
| SCH-02 | Lade-Lease `gpu` mit genau einem Besitzer, Test `test_testlab`; Spalte `name` erlaubt weitere Leases; `reservations` mit Priorität | Tabelle `slot_leases`; Warteschlange der Wartenden: `acquire` fragt alle `poll_s` (5 s) erneut, die Reihenfolge ist ein Wettlauf, nicht FIFO; die vorhandene Tabelle `queue` meint geplante Messrunden, nicht Wartende; Besitz über `pid` taugt für Slot-Leases nicht, weil alle Läufe im selben Prozess laufen (B-1) | ja für „2 Ladeversuche: einer wartet“; „N+1: einer wartet in der Schlange“ braucht die Reihenfolge-Aussage (FIFO je Priorität) | teilweise; Produktpfad ohne Lease (B-1) |
| SCH-03 | `resource_scheduler`: Hauptbuch plus Messung, `need_of` rechnet KV-Cache mit, `kv_cache_placement`, Ablehnung mit `need_gb` und `best_free_gb`/`available_gb` im Ergebnis, Audit `RESOURCE_DENIED` mit Grund; `vram_reserve_gb` 0,7 | Der Schalter ist aus (`enabled: false`). Eine Reservierung gehört einem `job_id`; N Läufe würden die Modellgewichte N-fach buchen und sich selbst ablehnen (`resident_vram_gb` gutschreibt nur auf der Messseite, nicht im Hauptbuch). `max_jobs` des Hardwareprofils (1 bis 4) deckelt die Parallelität zusätzlich. „Grenze 11,5 GB“ ist nirgends konfiguriert: die Grenze ist Gesamt-VRAM minus 0,7 (bei 12 GB etwa 11,3 GiB). Das Audit trägt nur den Grund, nicht die Werte | ja, wenn „gemessen“ und „benötigt“ als Felder der Ablehnung festgelegt sind | zu ändern (siehe unten); Zahl 11,5 klären |
| SCH-04 | Priorität nur als ganze Zahl der `reservations`: eine lebende Reservierung höherer Priorität schiebt niedrigere auf (`deferred`) | Zuordnung Captain/Agent/Routine zu Zahlen; Altern (keine Prioritätserhöhung durch Wartezeit); Obergrenze der Wartezeit in keiner Konfiguration; Verdrängung eines laufenden Laufs gibt es nicht (ein Slot wird erst frei, wenn der Lauf endet) | nein – „Kein Lauf wartet länger als die Obergrenze“ ist bei Überlast nicht erfüllbar, nur „meldet“ | zu ändern |
| SCH-05 | Rezept hat `context.recommended/maximum/tiers/measured_maximum`; `context_ladder.py` misst die sichere Grenze (Nadel-im-Heuhaufen, 85 % Füllung, VRAM-Reserve 1 GiB, Treiberereignisse) | `--parallel` am Werkzeug (B-5); Rezeptfeld `per_slots`; Auflösung `role_routing._evaluate` kennt es nicht; Ladder prüft eine Anfrage nach der anderen, nicht N gleichzeitig gefüllte Slots | ja, wenn „1 bis N“ auf die gemessenen Zahlen (1 bis 4) festgelegt wird | fehlt |
| SCH-06 | Der Router wählt je Rolle ein Rezept; `ModelLoader` entlädt und lädt bei falschem Fenster (nur dieses Modell); `captain_cloud_approved` je Auflösung | Keine Aussage „andere Rezeptfamilie → umladen“; keine Ablage für eine „vom Captain freigegebene Regel“ (kein Guard-Eintrag, kein Konfig-Feld); kein Wartegrund-Code für den Lauf | ja: „Ohne Regel wartet der Lauf und meldet den Grund“ | fehlt |
| SCH-07 | `desk/decisions.py` (Entscheidungen), Cloud aus (`cloud_allowed: false`), Cloud nur mit Freigabe je Auflösung | Schlangengrenze nicht definiert; Spec 3 baut die Cloud-Stufe erst; die Art der Entscheidung (`kind`) existiert nicht | ja, sobald Grenze und Entscheidungsart festliegen | abhängig von Spec 3 |
| SCH-08 | Absturz wird erkannt (`_reap`, Audit `LLAMA_SERVER_EXITED`, `gpu_canary.invalidate`), der Canary läuft vor dem nächsten Laden (`_check_gpu`), das Journal (`step_journal.start`) verweigert den Neustart eines Schritts im Zustand RUNNING mit `UNKNOWN_EXECUTION_OUTCOME` und höchstens 3 Versuche | Neustart des Servers passiert nur beim nächsten Laden, nicht von selbst; „Müll liefern“ wird live nicht erkannt (`gpu_canary.garbage` und `degenerate_reason` laufen nur in Canary und Messungen); Slot-Leases gibt es nicht; „Läufe fortsetzen“ widerspricht dem Journal: ein Schritt im Zustand RUNNING gilt als unbekannter Ausgang, die Mission pausiert (`brain.py`), er wird nie still wiederholt | ja, wenn „fortsetzen“ als „ab dem letzten abgeschlossenen Schritt, der unterbrochene wartet auf Entscheidung oder ist lesend und darf wiederholt werden“ gefasst wird (`readonly_step`) | zu ändern |
| SCH-09 | `desk/events.py`: `diff` ist rein und deterministisch, Ereignisse `task.changed`, `decision.pending`, `decision.answered`, `live.line`, `model.changed`, `system.state`; Poller alle 3 s | Ereignis `slot.changed`, Schnappschuss-Feld `slots`; Datenquelle (Lease-Tabelle oder `/slots` des Servers; ob Build b11160 den Endpunkt liefert, ist ungeprüft) | ja; „live“ braucht eine Latenzgrenze (Poller 3 s) | fehlt, gut anschließbar |
| SCH-10 | Benchmarks und `devvm_build` nehmen `lab.lease(...)` mit Wartezeit bis 10 h; `resource_scheduler.reserve(exclusive=True)` kennt `exclusive_conflict`/`exclusive_held`; `reservations` mit Priorität | Modus `exklusiv` im Scheduler. Kippt die Lade-Lease dauerhaft zum Scheduler (B-1), warten Benchmarks bis zu ihrem `wait_s` und scheitern; es braucht eine Übergabe: Scheduler sperrt neue Slot-Leases, wartet auf laufende, stoppt seinen Server und gibt `gpu` frei | ja | fehlt; wichtigste Folgeänderung |

Korrekturvorschläge (alt / neu):

| ID | Alt | Neu (Vorschlag) |
| --- | --- | --- |
| SCH-01 | WENN ein Rezept `slots: N` angibt, DANN SOLL der llama-server mit N parallelen Slots starten. | WENN ein Rezept `server.slots: N` (1 bis 8) angibt, DANN SOLL der Scheduler den llama-server mit `-np N` starten; das Rezept nennt das Fenster **je Slot**, der Gesamtkontext ist `N × Fenster`. Abnahme: N gleichzeitige Anfragen laufen zeitlich überlappend (jede beginnt, bevor die erste endet); Summe der Token/s bei N=2 mindestens `<schwelle>` × Einzelwert (Schwelle aus der Messung, G1-S2-a) |
| SCH-02 | Die Lade-Lease SOLL genau einen Besitzer haben; der Scheduler SOLL Slot-Leases an Läufe vergeben. | Die Lade-Lease (`gpu`) SOLL genau einen Besitzer haben, den Scheduler-Prozess, der den Modellserver hält. Slot-Leases SOLLEN je Lauf (nicht je Prozess) vergeben werden, mit Herzschlag, in Reihenfolge Priorität, dann Eingang. Abnahme: 2 Ladeversuche, einer wartet; N+1 Läufe, der letzte bekommt den Slot erst, wenn einer frei wird, in Eingangsreihenfolge je Priorität |
| SCH-03 | … VRAM inklusive KV-Cache für N Slots vorab reservieren und den Start ablehnen, wenn die Grenze von 11,5 GB überschritten würde. | … Gewichte **einmal** und KV-Cache **je Slot** vorab buchen und den Start ablehnen, wenn Gesamtbedarf plus Reserve die konfigurierte VRAM-Grenze überschreitet (`<grenze>`: 11,5 GB, G1-S2-c). Abnahme: Die Ablehnung enthält `need_gb` und `measured_free_gb` im Ergebnis und im Audit `RESOURCE_DENIED` |
| SCH-04 | … Kein Lauf wartet länger als die eingestellte Obergrenze. | Stufen Captain (3) > Agent (2) > Routine (1); je `<alter_s>` Wartezeit steigt ein wartender Lauf um eine Stufe, höchstens bis Agent. Abnahme: Ein Lauf, der länger als `<warte_max_s>` wartet, wird gemeldet (Ereignis `slot.changed`, Vorschlag nach SCH-07); Captain-Anfragen überholen immer, laufende Läufe werden nicht verdrängt |
| SCH-05 | … `context_ladder.py` liefert Werte für 1 bis N Slots; Rezept enthält sie | … Der Messlauf mit `--parallel N` füllt alle N Slots gleichzeitig zu 85 % und liefert die sichere Grenze je Slot für N = 1 bis 4; das Rezept führt sie unter `context.per_slots` (Schlüssel N, Wert Fenster je Slot) |
| SCH-06 | … nur nach einer vom Captain freigegebenen Regel umladen … | … Regel = Eintrag im Overlay `local_config/role_routing.yaml` (Feld `scheduler.swap`, Standard `none`), mit Gate bei Änderung. Ohne Regel wartet der Lauf mit Grund `model_swap_not_allowed` |
| SCH-07 | … die Schlange länger als die Grenze ist … | … länger als `<schlange_max>` Läufe oder älter als `<warte_max_s>` … Vorschlag als Entscheidung `kind: cloud_offload`; Annahme gilt nur für diese Entscheidung |
| SCH-08 | … Läufe über `step_journal` fortsetzen, ohne Schritte still zu wiederholen. | … Läufe ab dem letzten abgeschlossenen Schritt fortsetzen; ein unterbrochener Schritt wird nur wiederholt, wenn er lesend ist (`readonly_step`), sonst pausiert die Mission mit `UNKNOWN_EXECUTION_OUTCOME` und wartet auf den Captain. „Müll“ = Antwort, die `degenerate_reason` auslöst. Abnahme: Absturz-Test mit unechtem Server: je Schritt höchstens ein Versuch im Journal, kein doppeltes Audit der Wirkung |
| SCH-09 | … Ereignis `slot.changed` auf `/api/events` | … Ereignis `slot.changed` mit `{slot, state, run_id, priority, queue_len}` innerhalb von 3 s nach der Änderung (Poller-Takt) |
| SCH-10 | … Modus `exklusiv` blockiert neue Slot-Leases, bis der Lauf endet | … Anfrage `exklusiv` sperrt neue Slot-Leases, wartet höchstens `<drain_s>` auf laufende, stoppt den eigenen Server über die eigene PID, gibt `gpu` frei; danach startet der Scheduler den Server erst wieder, wenn der Lauf `gpu` zurückgegeben hat |

### Design (Vorschlag)

- Neues Modul `jobs/model_scheduler.py`; `jobs/testlab.py` behält die Lade-Lease, eine neue Tabelle `slot_leases` in `testlab.db` hält die Slot-Leases mit Herzschlag wie bisher.
- Rezept-Erweiterung in `role_routing.yaml`: `server.slots: N` und `context.per_slots: {1: …, 2: …, 4: …}` aus Messungen.
- llama-server-Start mit `--parallel N`; der Gesamtkontext `-c` wird auf die Slots verteilt. Ob Build b11160 einen gemeinsamen KV-Puffer für alle Slots nutzt, wird gemessen, nicht angenommen.
- Jeder Agentenlauf fragt `model_scheduler.acquire(recipe, priority)` und bekommt einen Slot oder einen Platz in der Schlange.

Die Ausarbeitung (Tabelle `slot_leases`, Reihenfolge, Übergabe an Benchmarks, Prüfung der Rezeptfelder) folgt in S2.3 nach G1.

### Messplan-Entwurf S2.1 (nicht ausgeführt)

Zweck: die Zahlen für SCH-01, SCH-03, SCH-05 und die Standard-Slotzahl liefern. Der Plan ändert **kein** Rezept: Einstellungen kommen nur über `--set` (nur für diese Messung); die Rezeptdatei wird erst nach dem Bericht und nach Gate geändert (Schritt 9). Platzhalter: `<guppi>` Projektordner, `<modelle>` Modellordner, `<datum>` aus `date`, `<owner>` Name der Sitzung, `<rezept>` Rezept-ID des Hauptmodells (`coder.local_primary` im Overlay, laut `MODELLE.md`), `<klein>` Rezept-ID des Hilfsmodells (etwa `coder.llama_qwen35`).

Voraussetzungen (alle vor Schritt 1):

1. G1-S2-k erteilt; kein anderer Lauf aktiv.
2. Messwerkzeug-Erweiterung `--parallel N` für `context_ladder.py` und `connection_check.py` sowie ein neues Werkzeug `slot_throughput.py` (sendet N gleichzeitige Anfragen, misst Token/s je Slot und gesamt, VRAM, Treiberereignisse) sind gebaut und ohne GPU getestet (unechter Server). Das ist Harness-Code der KI-Sitzung und ein eigener Schritt (M0), nicht Teil der Messung.
3. Engine unverändert (`engine_build` laut `llama_server.yaml`, bei den stabilen Läufen b11160); `GUPPI_ENGINE_BUILD` nur setzen, wenn der Captain es für diese Messung festlegt.

Ablauf:

| Schritt | Aktion | Befehl (Platzhalter) | Erwartung / Abbruch |
| --- | --- | --- | --- |
| 0 | Zustand lesen | `python benchmarks/testlab_cli.py --project <guppi> status` | Lease frei, keine Reservierung. Sonst **Abbruch**: warten, nichts anfassen |
| 1 | Lauf in die Warteschlange eintragen | `python benchmarks/testlab_cli.py --project <guppi> plan --owner <owner> --kind slot-messung --what "Qwen3.6 Slots 1-4" --models <rezept>` | Eintrag mit Nummer |
| 2 | Sicherung der Konfigurationen (nur Lesekopie, es wird nichts geändert) | `copy <guppi>\local_config\role_routing.yaml <guppi>\local_config\role_routing.yaml.bak-<datum>-slotmessung` | Datei vorhanden. Wird auch Schritt 9 später nötig, gilt Regel 3 erneut mit frischem Datum |
| 3 | Lease halten, Reste räumen | Die Werkzeuge nehmen sie selbst: `lab.lease(owner, purpose, ttl_s=1800, preflight=clear_leftovers)`; bei langen Läufen Wartezeit setzen (`wait_s`). Kein manuelles Beenden von Prozessen; nur eigene PID | `preflight` meldet `GpuNotClean`: **Abbruch** mit Ausgabe (andere Last auf der Karte) |
| 4 | Verbindungsprüfung S0 je Slot-Zahl | `python benchmarks/connection_check.py <guppi> <rezept> --context 32768 --parallel N` für N = 1, 2, 3, 4 | Nur zur Einordnung: S0 war am 12.10. bei allen Modellen nicht bestanden (`MODELLE.md`, Prüfung selbst verdächtig). Erst N=1 gegen die bekannte Lage vergleichen; kippt N=1 anders als am 12.10., **Abbruch** |
| 5 | Kontextleiter je Slot-Zahl | `python benchmarks/context_ladder.py <guppi> <rezept> --probes 2 --parallel N --tag slots<N>` für N = 1, 2, 3, 4 (Stufen 8k bis 128k je Slot) | Ergebnis `runtime_data/measurements/context_ladder_<rezept>_slots<N>_<datum>.json`. Leiter stoppt an der ersten Stufe, die scheitert; freier VRAM unter 1 GiB zählt als Fehlschlag |
| 6 | Durchsatz je Slot-Zahl | `python benchmarks/slot_throughput.py <guppi> <rezept> --parallel N --context <je_slot_aus_5> --requests N --runs 3` | Token/s gesamt und je Slot, Überlappung der Anfragen, VRAM-Spitze, `driver_events` |
| 7 | Hilfsmodell, gleiche Schritte 4 bis 6 | wie oben mit `<klein>`, zusätzlich mit `--set n_cpu_moe=<k>` und `--set n_gpu_layers=0` als CPU-Variante | wie oben |
| 8 | Aufräumen und Eintrag | Lease endet mit dem Block; `plan` auf `done` setzen: `python benchmarks/testlab_cli.py --project <guppi> setstatus <nr> done` | Kein Server übrig (`status`), VRAM wieder unter der Ausgangslage |
| 9 | Erst nach Bericht und Gate: Rezept ändern | Sicherung `…bak-<datum>-per-slots`, dann `context.per_slots` und `server.slots` im Overlay eintragen, danach Ladeprüfung: Datei wird vom Lader noch angenommen (Regel 3) | nicht Teil der Messung |

Abbruchkriterien (jedes einzeln, danach Lease freigeben, Server über eigene PID stoppen, Befund melden):

- `preflight` findet Last Dritter auf der GPU, oder die Lease ist belegt.
- Ein Server stürzt ab oder liefert Müll (`garbage`/`degenerate_reason`), bevor die Stufe beendet ist: Stufe als Fehlschlag, Leiter für diese Slot-Zahl beenden.
- Neue NVIDIA-Treiberfehler (`nvlddmkm`) im Systemprotokoll während einer Stufe: Gesamtabbruch, kein weiterer Start ohne Captain.
- Freier VRAM unter 1 GiB nach einer Antwort (Maß des Werkzeugs) oder Überschreitung der VRAM-Grenze von 11,5 GB.
- Temperatur-/Thermalzustand HOT oder CRITICAL im Hardware-Manager.
- Gesamtlaufzeit über `<limit_h>` (Vorschlag 3 h für das Hauptmodell, 1 h für das Hilfsmodell); die Lease-Laufzeit wird nur über den Herzschlag verlängert.
- Mehr als 3 Fehlschläge in Folge bei gleicher Einstellung.

Erwartete Tabelle für `MODELLE.md` (neuer Abschnitt „Parallele Slots“, Werte erst nach der Messung):

| Modell | Slots | Fenster je Slot (sicher) | Gesamtkontext | VRAM-Spitze (GiB) | Token/s gesamt | Token/s je Slot | S0 | Hinweis |
|---|---|---|---|---|---|---|---|---|
| Qwen3.6-35B-A3B UD-IQ4_XS | 1 | ? | ? | ? | ? | ? | ? | Vergleichswert: 44–47 Token/s, 131k (MODELLE.md) |
| (gleich) | 2 | ? | ? | ? | ? | ? | ? | |
| (gleich) | 3 | ? | ? | ? | ? | ? | ? | |
| (gleich) | 4 | ? | ? | ? | ? | ? | ? | |
| Hilfsmodell `<klein>` | 1 bis 4 | ? | ? | ? | ? | ? | ? | auch CPU-Variante |

Danach: Vorschlag der Standard-Slotzahl an den Captain (G1-S2-a bis G1-S2-c fließen ein). Ungelöst im Messplan: ob MTP-Spekulation (`spec-type draft-mtp`) mit mehreren Slots stabil und schneller bleibt, ist eine eigene Zeile in Schritt 6 (`--set mtp=true/false`).

### Regel-Entwurf S2.2: GPU-Lease in `ENTWICKLUNG.md` (Entwurf, Datei nicht geändert)

Heutiger Wortlaut, Regel 2: „**GPU:** Vor dem Laden von Modellen die Lease holen. Rezepte, Engine und Schalter nie ändern, solange ein Lauf die GPU nutzt. Nur eigene Prozesse über ihre PID beenden, nie per Namensmuster; andere Sitzungen teilen sich GPU und Skripte.“

Vorschlag (gilt erst nach Captain-Gate G1-S2-l und nach Bau des Schedulers; bis dahin bleibt der heutige Text):

> 2. **GPU:** Es gibt zwei Ebenen. Die **Lade-Lease** (`gpu`) hat genau einen Besitzer; nur er startet und stoppt Modellserver. Vor dem Laden eines Modells die Lade-Lease holen. Läuft der Modell-Scheduler, ist er der Besitzer, und Sitzungen laden nicht selbst. Die **Slot-Lease** gibt der Scheduler an einen Lauf, der den laufenden Server nutzt; sie erlaubt Anfragen, aber kein Laden, Stoppen oder Ändern. Mess- und Bauläufe (Benchmarks, `devvm_build`) fordern den Modus **exklusiv** an: Der Scheduler sperrt neue Slot-Leases, wartet auf laufende, stoppt seinen Server und übergibt die Lade-Lease. Rezepte, Engine und Schalter nie ändern, solange ein Lauf die GPU nutzt, auch nicht über eine Slot-Lease. Prozesse nur über die eigene PID beenden, nie per Namensmuster; der Scheduler beendet nur seinen eigenen Server, und Aufräumen (`gpu_preflight`) fasst keinen Server an, der zu einer lebenden Lease gehört.

Dazu zwei Folgeänderungen, jede ein eigenes Gate: die Beschreibung der Lease im Kopf von `testlab.py` und im Abschnitt Betrieb (`BETRIEB.md`), und die Zeile „Slot“ in den Begriffen dieser Spec („heute ist 1 Slot Standard“ entfällt erst nach Freigabe der Standard-Slotzahl).

### Paperclip: wie parallele Agenten laufen (nur Lehrreiches)

Quelle: lokale Kopie `paperclip-master`, `server/src/services/heartbeat/queue.ts` und `packages/shared/src/constants.ts`.

- Parallelität ist eine **Grenze je Agent**: `maxConcurrentRuns` im Herzschlag-Eintrag jedes Agenten (Standard 20, `AGENT_DEFAULT_MAX_CONCURRENT_RUNS`). `startNextQueuedRunForAgent` zählt laufende Läufe des Agenten, rechnet `maxConcurrentRuns − laufende` als freie Plätze und holt genau so viele Läufe aus der Schlange (Zeilen 1896 bis 2012). Für Adapter mit nur einer externen Sitzung ist die Grenze fest 1.
- Es gibt **keinen** gemeinsamen Verteiler für ein Betriebsmittel wie GPU oder Modellserver. Jeder Adapter startet seinen eigenen Prozess oder ruft eine Cloud-Schnittstelle; Engpässe regelt dort der Anbieter. Zusätzliche Bremsen sind Tageslimits je Agent (`maxDailyRuns`, `maxDailyCostCents`).
- Beanspruchen und Abbrechen laufen über Zeilensperren in Postgres; ein Gewinner wird durch den Zustand der Zeile bestimmt (ähnlich dem atomaren Checkout aus Spec 1).
- Lehre für SEDRA: Paperclip löst „wie viele Läufe je Agent“, nicht „wie verteilen sich die Läufe auf eine knappe lokale GPU“. Die Slot-Lease ist deshalb eine eigene Schicht unter dem Herzschlag aus Spec 1 und braucht zusätzlich eine Grenze **je Agent** (`max_parallel` im Agenten, Spec 1), damit ein Agent nicht alle Slots belegt.

### Gate-Liste G1-S2

Jede Zeile wird einzeln entschieden. Die Empfehlung der Spec-Sitzung steht in der letzten Spalte.

| Gate | Frage an den Captain | Empfehlung |
| --- | --- | --- |
| G1-S2-a | SCH-01: Neue Fassung mit Fenster je Slot und messbarer Schwelle für den Durchsatz (Zahl `<schwelle>` wird nach der Messung vorgeschlagen) | ja |
| G1-S2-b | SCH-02: Lade-Lease und Slot-Leases getrennt, Slot-Leases je Lauf, Reihenfolge Priorität dann Eingang; Produktpfad der Jobs nimmt künftig eine Lease (B-1) | ja |
| G1-S2-c | SCH-03: Welche VRAM-Grenze gilt: 11,5 GB absolut oder Gesamt-VRAM minus `vram_reserve_gb` 0,7 (rund 11,3 GiB)? Gewichte einmal, KV je Slot buchen | 11,5 GB als Obergrenze, Reserve bleibt 0,7; dann nur beide Zahlen in einem Feld festhalten |
| G1-S2-d | SCH-04: Stufen Captain/Agent/Routine, Altern, Obergrenze meldet statt garantiert, keine Verdrängung laufender Läufe | ja |
| G1-S2-e | SCH-05: `context_ladder` und `connection_check` bekommen `--parallel`; Rezeptfeld `context.per_slots`; neues Werkzeug `slot_throughput.py` (Harness, KI-Sitzung, ohne GPU gebaut) | ja |
| G1-S2-f | SCH-06: Umladen nur nach Regel im Overlay (`scheduler.swap`), Standard keine; Wartegrund `model_swap_not_allowed` | ja |
| G1-S2-g | SCH-07: Schlangengrenze und Entscheidungsart `cloud_offload`; Abhängigkeit zu Spec 3 | ja, Grenze in Spec 3 festlegen |
| G1-S2-h | SCH-08: „Fortsetzen“ als „ab letztem abgeschlossenen Schritt; unterbrochener nur wiederholen, wenn lesend, sonst Pause“ (kein Eingriff in `core/step_journal.py`); Server-Neustart und Müll-Erkennung im Scheduler | ja |
| G1-S2-i | SCH-09: `slot.changed` über Schnappschuss und `diff` in `desk/events.py` (Takt 3 s), Datenquelle klären in S2.3 | ja |
| G1-S2-j | SCH-10: Übergabe-Verfahren „exklusiv“; `gpu_preflight` beendet keinen Server mit lebender Lease (B-6) | ja |
| G1-S2-k | Messplan-Entwurf S2.1 und seine Abbruchkriterien als Rahmen für die spätere Messung freigeben (Ausführung braucht trotzdem eigene Freigabe samt GPU-Zeit) | ja |
| G1-S2-l | Regel-Entwurf S2.2 als Grundlage für die spätere Änderung von `ENTWICKLUNG.md` freigeben (die Datei bleibt bis zum Bau unverändert) | ja |
| G1-S2-m | Korrekturvorschläge SCH-01 bis SCH-10 (alt/neu) in die Tabelle „Anforderungen“ übernehmen | ja, nach Entscheidung a bis j |

### Aufgaben

- [ ] S2.0 Messwerkzeuge erweitern (`--parallel`, `slot_throughput.py`), ohne GPU testen → G1-S2-e
- [ ] S2.1 Messplan ausführen (unter GPU-Lease, Rezepte nur mit Sicherung) → Messbericht
- [ ] S2.2 Regeländerung zur GPU-Lease in `ENTWICKLUNG.md` als Entwurf → Captain-Gate (Entwurf steht oben)
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

Abnahmekriterien: LAB-02 bis LAB-07 sind prüfbar (Audit, `spend`, Anzeige). LAB-01 braucht für Shell D den Spec-4-Eintrag. LAB-03: „Kurztest der Werkstatt“ meint das „Testen“ lokaler Modelle (Antwort des Captains); das Ergebnisformat ist damit festgelegt.

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
| LAB-03 | … eine Frage, Antwortzeit, Token; externe Aktion mit Gate und durch das GateWay. | Der Kurztest sendet **genau eine** feste Testnachricht an das Standardmodell, kein `GET /models`. Er zählt gegen das Budget und schreibt `CLOUD_CALL`. Modellliste und Test aller Modelle sind eigene Aktionen; der Test aller Modelle ist in der Startphase aus. Das Ergebnis zeigt wie das „Testen“ der Werkstatt Antwortzeit und Token. |
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

#### Antworten des Captains auf die offenen Fragen (20.10.2026)

1. Mammouth (URL, Modelle, Schlüsselformat, Guthaben-Abfrage): wird später eingetragen; der Schlüssel ist noch nicht beantragt. (URL und Guthaben-Abfrage stehen inzwischen in der API-Doku, siehe unten.) Bis dahin steht Mammouth nicht im Startbestand der Anbieter (LAB-02), und das Muster für sein Schlüsselformat (CLD-08) bleibt offen.
2. NVIDIA: ob die Grenze in Anfragen als einzige Bremse genügt, wird erst im Betrieb geklärt (C3.5).
3. „Kurztest der Werkstatt“ (LAB-03): gemeint ist das „Testen“ lokaler Modelle in der Werkstatt (eine kurze Frage mit Zeit und Token/s, `workshop/arbeitsplatz.yaml`). Der Verweis bleibt; der Cloud-Kurztest zeigt dasselbe Ergebnisformat (Antwortzeit, Token). Die Korrektur in der Tabelle „alt / neu“ (Streichung des Verweises) entfällt.
4. Lauf-Prozesse dürfen den vorhandenen Schlüssel lesen, weil er für Testzwecke angelegt ist. Das gilt nur für diesen Testschlüssel; für den produktiven Schlüssel entscheidet G2 neu (CLD-08, Punkt 3).
5. SK0-only genügt für Planer und Recherche.
6. Nutzungsbedingungen beider Anbieter: geprüft am 20.10.2026, Ergebnis im nächsten Abschnitt. Für Mammouth fehlt noch der Primärtext.


#### Prüfung der Nutzungsbedingungen (20.10.2026)

Gelesen wurden öffentliche Seiten; es gab keinen Aufruf der Anbieter-APIs. Rechtsprüfung ist das nicht.

**NVIDIA API Catalog.** Primärtext: „NVIDIA API Trial Terms of Service“ (PDF von NVIDIA, Stand Oktober 2025), gelesen. Befunde:

| Punkt | Inhalt der Bedingungen | Folge für Spec 3 |
| --- | --- | --- |
| Zweck | Zugang „for limited trial purposes only“, ohne Einsatz des Dienstes oder der erzeugten Inhalte in Produktion (1.2); ohne Subskription nur interner Test und Evaluation (1.4) | Der Dauerbetrieb von Planer und Recherche mit der kostenlosen Stufe ist **nicht** gedeckt, sobald er „Produktion“ ist. Die Grenze „Startphase“ muss als Test und Evaluation geführt werden (G1-S3-11) |
| Umfang | Nutzung begrenzt nach Zahl der Zugriffe oder Dauer; Credits (laut Forum 1000 beim Start, bis 5000); danach braucht es eine Subskription (1.4) | Die Grenze 500 pro Tag ist **unsere** Vorsicht, keine Zusage von NVIDIA. Das Tageslimit kann früher enden (Credits) und der Zugang ganz (Trial endet). Die Zahl „bis zu 40 pro Minute“ steht nicht in den Bedingungen (nur in Foren); CLD-05 muss mit Ablehnung durch den Anbieter (HTTP 429) rechnen |
| Eingaben | Keine vertraulichen oder sensiblen Daten, keine Personendaten, keine Zahlungsdaten (2.6, 4.3) | deckt sich mit „nur SK0“; auch SK1 bleibt draußen |
| Verwendung der Eingaben | NVIDIA darf Eingaben und Ergebnisse zur Verbesserung seiner Produkte „einschließlich KI-Modelle“ verwenden und protokolliert Nutzung für Sicherheit (3.3) | SK0 muss wirklich **öffentlich** sein. Ein Entwurf, der später nicht für Dritte gedacht ist, ist kein SK0. Das gehört in die GateWay-Beschreibung von SK0 (G1-S3-12) |
| Weiteres | Vorabversionen ohne Gewähr (1.3); Schiedsklausel (14) | Verfügbarkeit nicht zugesichert; CLD-07 gilt auch für den Ausfall |

**Mammouth.** Primärquelle ist nur die API-Dokumentation (`info.mammouth.ai/docs/api-quick-start`), gelesen. Die Nutzungsbedingungen, die Datenschutzseite und die Auftragsverarbeitung liegen hinter der Anmeldung oder waren nicht abrufbar; **nicht geprüft**. Was die API-Doku sagt:

- Basis-URL `https://api.mammouth.ai/v1`, Anmeldung mit Bearer-Schlüssel, Endpunkte `POST /v1/chat/completions` (OpenAI-kompatibel), `POST /v1/embeddings`, `GET /key/info` (verbrauchte Credits je Schlüssel).
- Abo-Credits für die API monatlich: Starter 2 $, Standard 4 $, Expert 10 $ (in Dollar, nicht Euro); zusätzliche Credits kaufbar; die Doku nennt „nie mehr als der angezeigte Preis“ als Obergrenze. Ratenlimits nennt sie nicht (nur 429 als Fehler).
- Modellliste im „Model Explorer“, nicht über eine feste Liste. Das Muster für das Schlüsselformat nennt sie nicht.
- Mammouth leitet an Modelle fremder Hersteller weiter; was diese mit Eingaben tun, steht laut Doku auf einer Seite „Privacy with model providers“, die ich nicht lesen konnte. Dritte Quellen nennen Löschung von Protokollen nach höchstens 30 Tagen und kein Training mit Eingaben; das ist **nicht bestätigt**.

Folgen für die Spec: (1) Das Guthaben ist abfragbar (`GET /key/info`); damit ist die Euro-Grenze für Mammouth ohne Schätzung prüfbar (CLD-05), ist aber ein weiterer Netzzugriff (Aktion `cloud_probe`, GA-06). (2) Die Währung ist Dollar; „0 € extra“ heißt in der Regeldatei: Credits, die das Abo enthält, kein Zukauf. (3) Vor dem ersten Mammouth-Aufruf liest der Vorarbeiter Nutzungsbedingungen und „Privacy with model providers“ nach Anmeldung (G1-S3-13).

Neue Gates aus der Prüfung:

| Gate | Entscheidung, die der Captain trifft | Empfehlung |
| --- | --- | --- |
| G1-S3-11 | NVIDIA wird in der Startphase ausdrücklich als Test und Evaluation geführt (Prototyp-Zweck); ein Dauerbetrieb im Alltag braucht vorher eine Subskription oder einen anderen Anbieter. Diese Einordnung steht in der Spec und im Labor (LAB-04) | ja |
| G1-S3-12 | SK0 bedeutet für die Cloud „öffentlich, ohne Rücksicht auf Verwendung durch den Anbieter“: Entwürfe und interne Texte gelten nicht als SK0, auch wenn kein Merkmal anschlägt (Text in `gateway/wissen.py`, Gate in Stufe 2) | ja |
| G1-S3-13 | Mammouth erst nach Lesen von Nutzungsbedingungen und Datenschutzseite (nach Anmeldung) in den Startbestand; Freigabe als eigenes Gate | ja |

#### Nicht geprüft

Kein Testlauf (`pytest`, `uix_check`), keine Browserprüfung, kein Cloud-Aufruf; `local_config/` und `cloud_keys.json` nicht geöffnet. Nicht gelesen: `desk/events.py`, `desk/decisions.py`, `provider_health`, die Tests im Einzelnen, der Wortlaut der Regeln in `docs/ENTWICKLUNG.md`, Preislisten; Mammouth-Nutzungsbedingungen und -Datenschutzseite (nicht abrufbar, siehe Prüfung der Nutzungsbedingungen).

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

### Abgleich gegen den Code (G1)

Stand 20.10.2026, K4.1 und K4.2, Branch `spec4/shell-d` (Commit `3abb023`). Nur gelesen: nichts gestartet, kein Test und kein `uix_check` ausgeführt.

#### Stand von Shell D (U4.1)

| Punkt | Befund |
| --- | --- |
| Dateien | `shell.yaml` (v1.1.0, `trust: CORE`, `provides: [tree, dock, talk, notify, palette, inbox]`), `shell.js` 155, `nav.js` 86, `pages.js` 176, `topbar.js` 77 Zeilen (zusammen 494), `shell.css` 100, `README.md`, `arbeitsplatz.yaml`, `preview.png`. Alle Skripte weit unter 400 Zeilen. |
| Aufbau | Navigation links (`NAV`, 15 Einträge), Kopfzeile mit Zurück, Verben des Werkstücks und Suchfeld (Strg+K), Seiten in der Mitte, das Gespräch (`talk`) als Schublade rechts. Drei Seitenarten: `dashboard` (Instrumente als Kacheln plus vier Karten), `collection`, `object` (Werkstück links, Nachweise als Karten rechts). Verlauf in `localStorage` (`sedra.paperclip.history`). |
| Ereignisse | Die Shell hört `object.open`, `decision.pending`, `decision.answered`, `task.changed`, `model.changed`, `desk.error` und lädt danach `GET /api/strip` und `GET /api/decisions` neu. Eigene Zeitgeber hat die Shell nicht. |
| Entscheidungen | `decide()` ruft `POST /api/decisions/answer` (steht in `shell.yaml` unter `api`). Der Badge am Posteingang kommt aus `GET /api/decisions`. |
| Heutige Namen | „Issues“ zeigt Typ `task`, also die Missionen. „Agenten“ und „Organigramm“ zeigen Typ `agent` mit dem Werkzeug `crew`, einer Liste aus `GET /api/agents` ohne Vorgesetzte. |
| Als Vorgabe baubar? | **Nein.** `shell.vorgabe.yaml` kennt nur die Zonen `leiste`, `orte`, `werkstueck`, `gespraech`, `entscheidungen`, `leer`; `orte.liste` und `start.type` sind feste Aufzählungen ohne `org`, `issue`, `routine`, `labor`. Ein Dashboard aus mehreren Sammlungen, ein Stapel von Agentenfenstern und Abschnitte in der Navigation gibt es im Rahmen `ui/frame.js` (335 Zeilen) nicht. `gateway-studio` zeigt, was die Vorgabe trägt: eine Hauptfläche mit Nachweisen. Empfehlung: Shell D bleibt klassisch (`shell.yaml` und Skripte) und teilt Dateien, wo 400 Zeilen drohen. Den Rahmen zu erweitern wäre ein eigenes Gate und lohnt nicht. |
| Tests | `tests/test_uix_shell_paperclip.py` und das Profil `paperclip` in `benchmarks/uix_check.py` (Zonen `pc-nav`, `pc-top`, `pc-page`; Kacheln `.pc-kpi`; Verlauf als „layout“) sind vorhanden. Nicht ausgeführt. |

#### Vorbild: Paperclip-UI (lokale Kopie vom 20.10.2026, `ui/src/pages` und `components`)

Geprüft wurden Dateinamen, Größen und Stichproben, nicht der ganze Code (die zwölf Seiten haben zusammen über 23.000 Zeilen).

| Paperclip-Ansicht | Inhalt (Stichprobe) | Übernehmen in Shell D |
| --- | --- | --- |
| `Dashboard` | vier Kennzahlen (Agenten aktiv, Aufgaben in Arbeit, Ausgaben im Monat, offene Freigaben), Aktivität | ja, die Kacheln gibt es; ergänzen: Slots und Ausgaben als Instrumente |
| `Inbox`, `Approvals`, `DecisionQueuePage` | Freigaben und Entscheidungen | schon da (`decisions`); Badge auch am Agenten (UIX-07) |
| `Issues` mit `IssuesList`, `KanbanBoard` | Liste oder Board (`viewMode: list` oder `board`), Spalten nach Status, Zuweisung, Blocker | ja: Liste und Board mit den Zuständen aus D3.3 (`offen`, `zugewiesen`, `in_arbeit`, `wartet`, `erledigt`, `abgebrochen`); Kommentare und Blocker im Detail |
| `Goals`, `GoalDetail` | Ziele mit Issues | schon da (`intent` mit Stufen); die Zielkette Ziel → Projekt → Issue im Issue zeigen (ORC-13) |
| `OrgChart` | Baum nach „reports to“, Karten von 200 px, Breite aus den Teilbäumen berechnet | ja, als Baum mit einer Wurzel (Unterarbeiter unter dem Captain, OP-6); Karte zeigt Rolle, Status, Budgetbalken |
| `Agents`, `AgentDetail`, `AgentChat` | Liste, Detail mit Reitern, Live-Lauf, Gespräch mit dem Agenten | ja: Detail mit Issues und Läufen neben dem Gespräch (UIX-04); Anweisungsdateien, Adapter und Zugangsdaten nicht |
| `Routines`, `RoutineDetail` | Liste, Auslöser („Triggers“), Läufe | ja, klein: Liste, Cron-Text, Nachhol-Regel, letzte und nächste Ausführung |
| `Costs` | Reiter Überblick, Budgets, Anbieter, Abrechner, Finanzen | Überblick, Budgets, Anbieter; Abrechner und Finanzen nicht |
| Firmen-Export und -Import, Zugänge, Einladungen, Auth, Workspaces, Skills, Plugins | mehrere Firmen, Pakete | nein (in der Ist-Tabelle „bewusst weggelassen“) |

Ablauf, den Shell D tragen soll: Captain gibt dem Unterarbeiter eine Anweisung → Issues entstehen → Zuweisung → Entscheidung im Posteingang (`wake_agent`) → Lauf mit Live-Zeilen → Ergebnis als Kommentar → Bericht an den Captain.

#### UIX-01 bis UIX-09 gegen den Code

**da** = erfüllt, **teils** = Grundlage da, Lücke genannt, **fehlt** = muss gebaut werden. „Prüfbar“ sagt, ob das Abnahmekriterium heute mit vorhandenen Mitteln gemessen wird.

| ID | Befund | Prüfbar? | Vorschlag |
| --- | --- | --- | --- |
| UIX-01 | **da.** Manifest, Dateigrenze (`test_no_file_of_the_contract…_longer_than_400_lines` prüft alle `*.js` unter `uix/`), README, Werkzeuge ohne `fetch`, `localStorage`, `EventSource`. Die Shell nutzt nur `ctx.api`, `ctx.bus`, `ctx.tools`, `ctx.makeContext`. `uix_check --shell paperclip` hat ein Profil. Lücke: Das Profil kennt keine Objekte für die neuen Werkzeuge; ein Werkzeug ohne Eintrag in `OBJECTS` wird über `handles[0]` und `alle` geöffnet, sinnvoll nur für Sammlungen. | ja | Wortlaut ergänzen (unten); Profil und `OBJECTS` im Prüfwerkzeug erweitern (G1-S4-08). |
| UIX-02 | **teils.** `NAV` hat Dashboard, Posteingang, Issues, Ziele, Agenten, Kosten, Planungstisch, Rekorder, Werkstatt, Bibliothek, Logbuch, Module, Dateien, Modus und Grenzen, Maschinenraum. Es fehlen **Organigramm** (nur Karte im Dashboard, öffnet `agent:alle`), **Routinen** (Build 24 entfernt), **Slots** und **KI-Labor** (`labor` handelt Typ `labor`, steht weder in `NAV` noch in `ui/places.js`, ist also auch über Strg+K nicht erreichbar). „Issues“ zeigt Missionen. „Jeder Eintrag öffnet ein Objekt oder eine Liste“ misst `uix_check` nicht je Eintrag; `test_every_place_of_the_palette_opens_an_object_a_tool_handles` prüft nur `places.js`. | nein (nur Orte der Palette) | Wortlaut ändern; neuer reiner Test (node): jeder `NAV`-Eintrag hat ein Werkzeug, das seinen Typ handelt; `uix_check` öffnet jeden Eintrag. |
| UIX-03 | **teils, Zählung unvollständig.** Vorhanden: `task` (nutzt `POST /api/objects` und `/api/actions`), `decisions`, `crew` (Typ `agent`, liest `GET /api/agents`), `costs` und `live` (Nachweise für `task`), `workshop`, `talk`, `labor`, dazu `intent`, `planung`, `meter`, `rekorder`. Das Brett braucht ein neues Werkzeug `board` für Typ `issue` (G2); `task` bleibt die Mission. Zwei Fallen: (1) Eine Sammlung mountet **alle** Werkzeuge, die den Typ handeln (`pages.js`, `collection`): `org` und `crew` auf `agent` erschienen zugleich. (2) Das Gespräch ist ein einzelnes Modul (`registerTool` legt ein Objekt je ID ab, `mount` speichert `this.el` und `this.history` darin); zweimal gemountet überschreibt es sich. Aus dem Code gelesen, im Browser nicht geprüft. | ja (Manifestliste) | Werkzeugliste unten; Wortlaut ändern. |
| UIX-04 | **fehlt.** Es gibt genau eine Gesprächsschublade (`talk`, `kind: panel`). `POST /api/chat/reply` kennt keinen Agenten (`text`, `history`, `mission_id`, `attachments`, `vorgang`); das Gespräch folgt dem Objekt nur über `talk.context`. Mehrere Fenster mit je eigenem Verlauf gehen mit `talk` nicht. Dazu ORC-14: Die Anweisung an den Unterarbeiter muss als Issues bei den Agenten unter ihm enden. | nein | Neues Werkzeug `agentfenster` (Typ `agent`, Einzelansicht) über ein Verb am Typ `agent` (Spec 1, etwa `anweisen`); Verlauf serverseitig je Agent. Entscheidung G1-S4-03. |
| UIX-05 | **teils.** `/api/events` (SSE) und die Ereignisse `task.changed`, `decision.pending`, `decision.answered`, `model.changed`, `live.line`, `system.state` gibt es; der Server fragt dafür alle 3 s den Hub ab (`desk/events.py`, `Poller`), im Browser steht nur ein Strom. `agent.changed`, `budget.warning`, `slot.changed` fehlen in `ui/bus.js` (`EVENTS`; unbekannte Namen werden abgewiesen) und in `events.diff`. Zeitgeber im Browser: `labor` alle 5 s (Läufe), `rekorder` 0,7 s und 3 s, `workshop` (Teststrecke), `ui/wechsel.js` 1 s. Das Kriterium „keine periodischen Abfragen im Netzwerkprotokoll“ gilt damit nicht für ganz Shell D. | nein (`uix_check` zählt Aufrufe ohne Absender, nicht Wiederholungen) | Wortlaut ändern: die neuen Seiten lesen bei Ereignissen, nicht im Takt; Ausnahmen nennen. Prüfung im Leerlauf (G1-S4-08). |
| UIX-06 | **teils.** `POST /api/actions` und `POST /api/objects` gibt es; `task` und `talk` nutzen sie. Alle anderen nutzen Spezialrouten: `labor` sieben (`/api/cloud/*`, `/api/labor/*`), `workshop` zehn. Die Shell selbst ruft `POST /api/decisions/answer`. Das Kriterium nennt nur die neuen Werkzeuge, so bleibt es prüfbar. | ja (Manifeste lesen) | Wortlaut präzisieren (unten). |
| UIX-07 | **teils.** Badge am Posteingang aus `GET /api/decisions` (`nav.js`, `badgeCounts`); die Wege kommen aus `decisions`. Kein Badge am Agenten; Entscheidungen tragen heute keine Agenten-ID (`describe`, `mission_id`, `gate_id`). | Posteingang ja, Agent nein | Agenten-ID in der Entscheidung ist Sache von Spec 0/1 (`binding`); die Shell liest sie. G1-S4-07. |
| UIX-08 | **fehlt.** Kein Cloud-Kennzeichen und kein Budgetbalken in Shell D (das Gespräch wählt Cloud über `GET /api/cloud` und `POST /api/chat/cloud`). Die Quelle `spend` und der Desk-Typ `budget` kommen mit Spec 0/1/3; `budget.warning` ist für Spec 4 vorgesehen. | nein, hängt an Spec 1 und 3 | Balken in `org` und `agentfenster`; Kennzeichen „Cloud · Anbieter“ aus dem Lauf. |
| UIX-09 | **da (aus dem Quelltext).** In `START_SEDRA.bat` wird ein erstes Argument, das nicht `--gewaehlt`, `--uebersicht` oder `--replace` ist, zur Shell-ID (`--shell paperclip`, `GEWAEHLT=1`); `uix_start.py --shell` startet „nur für diesen Start“, die Wahl in `uix.yaml` bleibt. Ordner `paperclip` stimmt. Nicht gestartet. | teils (Argumentaufbau als Text prüfbar; Start selbst mit `uix_check --shell paperclip` auf einem Testprojekt) | Wortlaut präzisieren. |

Korrekturvorschlag Wortlaut (alt → neu), G1-S4-01:

| ID | alt | neu |
| --- | --- | --- |
| UIX-01 | `tests/test_uix_contract.py` grün; `uix_check.py` meldet `result ok` | wie alt; dazu `uix_check.py --shell paperclip` mit Objekten für jedes neue Werkzeug im Profil; kein „nicht geprüft“ für `org`, `board`, `routines`, `slots`, `agentfenster`, `labor` |
| UIX-02 | Übersicht, Eingang (Entscheidungen), Aufgaben, Ziele, Organigramm, Agenten, Routinen, Kosten, Modelle und Slots sowie KI-Labor. Jeder Eintrag öffnet ein Objekt oder eine Liste | Dashboard, Posteingang, Issues (Typ `issue`, Liste und Board), Ziele, Organigramm, Agenten, Routinen, Kosten, Modelle und Slots, KI-Labor; Assistenten, Werkzeuge und Projekt wie heute. Abnahme: Test, dass jeder Eintrag ein Werkzeug hat, und `uix_check` öffnet jeden Eintrag |
| UIX-03 | wiederverwenden `task`, `decisions`, `crew`, `costs`, `live`, `workshop`, `talk`; neu nur `org`, `board`, `routines` und Instrument `slots` | wiederverwenden: `decisions`, `live`, `costs` (angepasst), `workshop`, `labor`, `meter`, `intent`, `planung`, `talk` (unverändert), `task` für Läufe, `crew` für die Rollenliste; neu: `org`, `board`, `routines`, `agentfenster`, Instrument `slots`. Abnahme: Manifestliste mit Begründung je Werkzeug |
| UIX-04 | Eigenes Gesprächsfenster mit dem Agenten, seine Aufgaben und Läufe daneben; mehrere Fenster, jedes hält seinen Verlauf | wie alt; die Anweisung geht als Verb über `POST /api/actions` (ORC-14); der Verlauf liegt serverseitig je Agent. Abnahme: zwei Fenster offen, zwei Verläufe, nach dem Neuladen derselbe Inhalt |
| UIX-05 | Änderungen über `/api/events`, nicht durch Polling; keine periodischen Abfragen im Netzwerkprotokoll | Die neuen Seiten lesen bei Ereignissen (`agent.changed`, `issue.changed`, `budget.warning`, `slot.changed`, `decision.*`), nicht im Takt. Abnahme: im Leerlauf 10 s lang keine wiederholte Abfrage desselben Pfads von `org`, `board`, `routines`, `slots`, `agentfenster`. Ausnahmen bis zu ihrer Spec: `workshop`, `rekorder`, `labor` |
| UIX-06 | Jede Handlung über `POST /api/actions`; Allowlist der neuen Werkzeuge ohne Spezialrouten | Jede Handlung der neuen Werkzeuge über `POST /api/actions`, Lesungen über `POST /api/objects`; ihre Manifeste nennen nur diese beiden Routen (Instrument: zusätzlich `GET /api/strip`). Vorhandene Werkzeuge sind ausgenommen |
| UIX-07 | Badge an Eingang und am betroffenen Agenten | wie alt; setzt die Agenten-ID in der Entscheidung voraus (Spec 0/1) |
| UIX-08 | Cloud-Antworten kennzeichnen, Budgetstand je Agent zeigen | wie alt, Quelle `spend` über Desk-Typ `budget`; messbar erst nach Spec 1 und 3 |
| UIX-09 | direkt in Shell D, ohne Zwischenschritt | wie alt; Abnahme: Test des Argumentaufbaus und `uix_check --shell paperclip` auf einem Testprojekt |

#### Neue Ereignisse

`ui/bus.js` weist unbekannte Ereignisse ab; jedes neue ist ein Eintrag in `EVENTS` und im Vertrag §5 (G1-S4-05). Nutzlast flach:

| Ereignis | Pflichtfeld | Quelle |
| --- | --- | --- |
| `agent.changed` | `id` | `ORC_AGENT_*`, `ORC_WAKE` (Spec 0, D3.2) |
| `issue.changed` | `id` | `ORC_TASK_*` (neu gegenüber Spec 0) |
| `budget.warning` | `agent_id` | `ORC_BUDGET_WARNING`, `ORC_BUDGET_STOP`; Cloud-Grenzen aus Spec 3 |
| `slot.changed` | – | `model_scheduler` (Spec 2, SCH-09) |

Sie entstehen in `desk/events.diff` (Spec 0/1 liefert die Audit-Ereignisse).

### Werkzeugliste

| Werkzeug | Status | Typ | Begründung |
| --- | --- | --- | --- |
| `decisions`, `live`, `intent`, `planung`, `meter`, `rekorder`, `library`, `logbook`, `modules`, `project`, `boundaries`, `gauge-*` | wiederverwendet | wie heute | laufen in Shell D; keine Änderung |
| `task` | wiederverwendet, andere Rolle | `task` | zeigt die Mission (den Lauf) hinter einem Issue; erreichbar über `mission_id` im Issue |
| `workshop` | wiederverwendet | `model` | Modelle laden, entladen, testen; Slots kommen als eigenes Instrument |
| `labor` | wiederverwendet, Ausbau in Spec 3 | `labor` | braucht nur einen `NAV`-Eintrag und einen Ort in `places.js`; zählt nicht als neues Werkzeug (Captain). Zeitgeber alle 5 s bleibt als Ausnahme bis Spec 3 |
| `crew` | angepasst | `agent` | liest heute `GET /api/agents` (Agent Manager, ohne Vorgesetzte). Empfehlung: Agentenliste und Baum zeichnet `org`; `crew` bleibt die Rollenliste und wird bei `agent:alle` nicht mitgemountet (Falle 1, G1-S4-04) |
| `costs` | angepasst | Nachweis für `task`, dazu `issue` | Budgetbalken und Cloud-Kennzeichen je Agent und Lauf (UIX-08); heute nur Münzen je Mission |
| `talk` | unverändert | Panel | bleibt das Gespräch mit SEDRA in der Schublade; Agentengespräche sind nicht `talk` (Singleton, kein Agent in `chat/reply`) |
| `org` | **neu** | `agent` (Sammlung) | Organigramm als Baum aus `reports_to`, Wurzel Unterarbeiter unter dem Captain; Karte mit Rolle, Status, Budgetbalken, Badge; Verben `einstellen`, `pausieren`, `fortsetzen`, `beenden`, `einordnen` (D3.2) |
| `agentfenster` | **neu** (fehlt in UIX-03) | `agent` (Einzelansicht) | Gesprächsfenster mit einem Agenten, daneben Issues und Läufe; mehrere zugleich; Verlauf serverseitig; beim Unterarbeiter ORC-14 |
| `board` | **neu** | `issue` | Liste und Board nach Zustand; Detail mit Zielkette, Blockern, Kommentaren und Link zur Mission; Verben `zuweisen`, `blocker_setzen`, `kommentieren`, `abbrechen`, `anlegen` |
| `routines` | **neu** | `routine` | Liste und Detail mit Cron-Text, Nachhol-Regel, letzter und nächster Ausführung; Verben `anlegen`, `aendern`, `ausschalten` (Gate `set_routine`) |
| `slots` | **neu**, Instrument | `kind: instrument` | belegte und freie Slots, Warteschlange (SCH-09); hört `slot.changed`; zeigt das geladene Modell |

Alle neuen Werkzeuge entstehen als Kopie von `tools/_template/`, mit `trust: GUPPI_BUILT` beim Bau durch SEDRA; Allowlist nur `POST /api/objects` und `POST /api/actions` (UIX-06). Vertragsnachträge: `handles` mit `agent:alle` und `agent:*` (G1-S4-04) und die vier Ereignisse (G1-S4-05). Ohne G1-S4-04 ginge es nur mit eigenen Typen für Einzelansicht und Sammlung, was den Desk-Typ `agent` zerlegt.

### Skizze der Oberfläche

```
+------------------------------------------------------------------------------------------+
| ‹ Zurück   Organigramm            [Einstellen] [Pausieren]            [ Ort suchen…  ^K ] |
+----------------+-------------------------------------------------+-----------------------+
| SEDRA          |  Agenten 5 · Issues in Arbeit 2 · Slots 2/3 ·   |  Unterarbeiter        |
|                |  Cloud heute 0 €                                |  ┌─ Gespräch ───────┐ |
| Dashboard      |                                                 |  │ Captain: Bau X   │ |
| Posteingang ②  |             [ Captain ]                         |  │ Unterarbeiter:   │ |
| Issues         |                  |                              |  │ 3 Issues angelegt│ |
| Ziele          |           [ Unterarbeiter ] ●                   |  └──────────────────┘ |
| Organigramm    |    /       |        |         \                 |  Issues: UA-1 UA-2    |
| Agenten        | [Planer] [Coder] [Reviewer] [Recherche]         |  Läufe: #12 läuft     |
| Routinen       |   ▇▇▇░     ▇▇░░      ▇░░░       ▇▇▇▇ (Budget)   |  Budget ▇▇▇░░ 62 %    |
| Kosten         |                                                 |  ┌ Coder (2. Fenster) ┐ |
| Modelle/Slots  |                                                 |  └────────────────────┘ |
| KI-Labor       |                                                 |                       |
| Assistenten …  |                                                 |  [Mit SEDRA sprechen] |
+----------------+-------------------------------------------------+-----------------------+
```

Links die Navigation wie heute, neu sind Organigramm, Routinen, Modelle und Slots, KI-Labor. Mitte: Liste, Baum oder Board. Rechts: der Stapel der Agentenfenster; die Schublade „Mit SEDRA sprechen“ bleibt das allgemeine Gespräch. Badges (②) am Posteingang und an der Agentenkarte.

### Gate-Liste G1 Spec 4

Jede Zeile entscheidet der Captain einzeln. Keine Änderung an `core/`.

| Gate | Gegenstand | Empfehlung |
| --- | --- | --- |
| G1-S4-01 | Wortlaut UIX-01 bis UIX-09 wie in der Tabelle alt/neu | freigeben |
| G1-S4-02 | Shell D bleibt klassisch (`shell.yaml` und Skripte), nicht aus einer Vorgabe; der Rahmen `ui/frame.js` wird nicht erweitert | freigeben |
| G1-S4-03 | Agentengespräche als neues Werkzeug `agentfenster` mit serverseitigem Verlauf und Verb am Typ `agent`; `talk` bleibt ein einziges Gespräch. Alternative: `talk` mehrfach mountbar machen (Vertrag §4, Fabrik statt Einzelobjekt) | freigeben (kleinerer Eingriff) |
| G1-S4-04 | Vertragsnachtrag: `handles` darf `typ:alle` (Sammlung) oder `typ:*` (Einzelobjekt) tragen | freigeben |
| G1-S4-05 | Vertragsnachtrag §5: Ereignisse `agent.changed`, `issue.changed`, `budget.warning`, `slot.changed` | freigeben |
| G1-S4-06 | Navigation: Organigramm, Routinen, Modelle und Slots, KI-Labor; „Issues“ zeigt Typ `issue` (erst nach G2-S0-12, bis dahin `task`) | freigeben |
| G1-S4-07 | Entscheidungen tragen die Agenten-ID (Badge am Agenten); Änderung bei Spec 0/1 (`decisions.py`, `binding`), nicht in der Shell | freigeben, Spec 1 führt es |
| G1-S4-08 | `benchmarks/uix_check.py`: Profil `paperclip` mit Objekten für die neuen Werkzeuge, Leerlauf-Prüfung auf wiederholte Abfragen, Prüfung jedes `NAV`-Eintrags | freigeben |
| G1-S4-09 | `ui/places.js`: Orte `labor`, `routines`, `org`, `slots` (Strg+K, auch im Cockpit sichtbar) | freigeben |
| G1-S4-10 | `shells/paperclip/arbeitsplatz.yaml` an die neuen Seiten anpassen (SEDRA antwortet daraus) | freigeben |

### Offene Fragen (Stufe 1)

| Nr | Frage | Vorschlag |
| --- | --- | --- |
| OP-S4-1 | Zugang des Agentengesprächs: Verb am Typ `agent` oder `chat_reply` mit Parameter `agent`? Hängt an Spec 1 (ORC-14) | Verb, so bleibt jede Handlung ein Gate (UIX-06) |
| OP-S4-2 | Kachel „Cloud heute“ braucht `spend` (Spec 3) | bleibt leer („noch keine Daten“), bis Spec 3 baut |
| OP-S4-3 | Brett als eigene Seite oder Umschalter Liste/Board im selben Werkzeug? | ein Werkzeug mit Umschalter, wie Paperclip (`viewMode`) |
| OP-S4-4 | `test_uix_shell_paperclip.py` und das Profil in `uix_check.py` setzen „Issues“ = `task` voraus; der Wechsel auf `issue` muss beide anpassen | im Bau, unter G1-S4-08 |
| OP-S4-5 | `labor` und `workshop` haben Zeitgeber und Spezialrouten (UIX-05, UIX-06) | Ausnahme im Wortlaut; Umbau gehört zu Spec 3 und zur Werkstatt |

### Design (Vorschlag)

- Prüfen, ob Shell D als Vorgabe (`shell.vorgabe.yaml`, Rahmen `ui/frame.js`, Build 17) gebaut werden kann; das spart Shell-Code. Sonst klassisch mit `shell.yaml` und `shell.js`.
- Aufbau: linke Navigation, Mitte Liste oder Board, rechts Detail beziehungsweise Agentengespräch; Slots als Instrument in der Leiste.
- Neue Ereignisse: `agent.changed`, `slot.changed`, `budget.warning`; Eintrag in Vertrag §5 als Nachtrag.
- Neue Werkzeuge entstehen als Kopie von `tools/_template/` mit `trust: GUPPI_BUILT`, wenn SEDRA sie baut.

Keine Grenze nach Umfang (Captain, 20.10.2026): Shell D wird auch gebaut, wenn viele neue Werkzeuge oder eine Änderung am Shell-Werkzeug-Vertrag nötig sind. Vertragsänderungen sind grundsätzlich freigegeben; jede einzelne bleibt ein Gate und kommt als Nachtrag in `SHELL_WERKZEUG_VERTRAG_v1.md`. Stand laut Captain: `uix/shells/paperclip/` ist vorhanden, der Bau steht am Anfang.

KI-Labor (Captain, 20.10.2026): Das vorhandene Werkzeug aus dem Cockpit kommt als eigener Navigationseintrag in Shell D, neben Modelle und Slots, und wird nach Spec 3 (LAB-01 bis LAB-07) ausgebaut. Es zählt nicht als neues Werkzeug.

### Aufgaben

- [x] U4.1 (20.10.2026) Stand von `uix/shells/paperclip/` prüfen und Paperclip-UI (Vorlage `ui/`) auf Ansichten und Abläufe durchsehen
- [x] U4.2 Skizze und Werkzeugliste, Anforderungsteil → G1 (Vorlage 20.10.2026, G1-S4-01 bis 10); Design danach → G2
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

G1 Spec 1 bis 4 und G3 Spec 0 (Captain, 20.10.2026), nach Prüfung durch den Vorarbeiter (Stichproben gegen den Code, `spec_check` je Bau-Spec `result ok`):

| Gate | Entscheidung |
| --- | --- |
| G1-S1-01 bis G1-S1-25 | freigegeben wie empfohlen; u. a. Organigramm in `orchestra/org.py`, ORC-01 bis ORC-14 in neuer Fassung, neue ORC-15 bis ORC-19, Dauerfreigabe als Token-Art im Guard (Weg 1; Kern-Gate nur als Grundsatz, der Diff wird einzeln freigegeben), Grenzen Stufe ≤ 3, 7 Tage (höchstens 30), höchstens 50 Läufe, Kennung `foreman`, Hostliste der Recherche unverändert |
| G1-S2-a bis G1-S2-m | freigegeben wie empfohlen; VRAM-Obergrenze 11,5 GB, Reserve 0,7 GB; Messplan nur als Rahmen, Ausführung braucht eigene Freigabe mit GPU-Zeit |
| G1-S3-01 bis G1-S3-13, G1-S3-GA-01 bis GA-07 | freigegeben wie empfohlen, mit einer Änderung an G1-S3-04: der Labor-Wert `modus: test` (Personenbezug wird ersetzt und gesendet, Captain 16.10.2026) **bleibt, aber nur hinter einem Gate und nur mit ausdrücklich gekennzeichneten Testdaten**; jeder solche Aufruf steht im Audit. Hauptschalter bleibt in `cloud_providers.yaml`; `paid_action` in der Startphase BLOCK; NVIDIA nur Test und Evaluation; Mammouth erst nach Prüfung seiner Bedingungen |
| G1-S4-01 bis G1-S4-10 | freigegeben wie empfohlen; Shell D klassisch, neues Werkzeug `agentfenster`, Vertragsnachträge `handles` und vier Ereignisse |
| G3-S0-01 bis G3-S0-19 | freigegeben wie empfohlen; die vier neuen Typen in Spec 0 nur lesend, Verben folgen in Spec 1 (OP-12); OP-13 bis OP-17 wie vorgeschlagen. G3 gibt den Bau frei, nicht die Übernahme: jeder SEDRA-Kandidat kommt einzeln zu G4 |

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
