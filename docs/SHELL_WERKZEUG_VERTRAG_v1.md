# Shell- und Werkzeug-Vertrag v1 – Grundlage für Desktop-Module (14.10.2026, 18:43)

Captain: eine Grundlage erarbeiten, wie solche Module gebaut und sinnvoll angebunden werden, damit SEDRA künftig **eigene
Desktop-Module** erstellen kann; Start mit Richtung C (Cockpit), danach die anderen Shells (E Minimal, D Paperclip).
Dieses Papier ist der Vertrag. Alles, was eine Shell oder ein Werkzeug darf und muss, steht hier; `COCKPIT_MODUL_v1.md` beschreibt
die erste Shell, `UIX_2_RICHTUNG_C.md` die Herleitung.

## 1. Begriffe

- **Kern**: Runtime, Guard, Audit, HTTP-API (`uix_server.py`). Keine Oberfläche. Kennt weder Shell noch Werkzeug – nur Manifeste.
- **UI-Vertrag** (`uix/ui/`): das Wenige, das Shells und Werkzeuge gemeinsam nutzen: `api.js` (Token, Fehler auf Deutsch), `bus.js`
  (Ereignisse), `tokens.css` (Farben, Abstände, Schrift), `lifecycle.js` (Registrierung), Schemata für `tool.yaml` und `shell.yaml`.
- **Shell**: ein Modul, das den Bildschirm besitzt – Leiste, Navigation, Fensterung/Dock, Gespräch, Palette. Genau **eine** Shell
  ist aktiv. Sie lädt Werkzeuge und gibt ihnen Container.
- **Werkzeug**: ein Modul für einen Objekttyp oder eine Anzeige. Es zeichnet in einen Container, den die Shell gibt, und spricht
  nur über `api()` und den Bus. Es kennt keine Shell.
- **Objekt**: das, worum es geht – `project`, `intent` (Vorhaben), `task` (Aufgabe), `candidate`, `file`, `model`, `skill`, `agent`,
  `decision`, `routine`. Objekte haben `{type, id, title}`; mehr liefert die API.

## 2. Ordner und Dateien

```
runtime/src/guppi_runtime/uix/
  ui/
    api.js  bus.js  lifecycle.js  tokens.css  schema/tool.schema.json  schema/shell.schema.json
  shells/
    cockpit/   shell.yaml  shell.js  shell.css  (dock.js, tree.js, talk.js, palette.js, strip.js)
    minimal/   shell.yaml  shell.js  shell.css        ← nach Build 9
    paperclip/ …                                      ← danach
  tools/
    task/      tool.yaml  tool.js  tool.css  (+ README.md, test.spec.js)
    candidate/ decisions/ tests/ live/ costs/ files/ workshop/ library/ crew/ meter/ logbook/ talk/ …
local_config/
  tools/<id>/      ← vom Captain installierte Werkzeuge (Git-Klon oder Kopie; Commit-ID + Hashes im Gate)
  shells/<id>/     ← dito für Shells
  uix.yaml         ← aktive Shell, Reihenfolge der Werkzeuge, gespeichertes Layout
```

Regeln: klassische Skripte (kein Build-Schritt, kein Bundler), **≤ 400 Zeilen je Datei**, Top-Level-Code nur in `shell.js` bzw.
`tool.js` innerhalb der Registrierung, keine Querimporte zwischen Werkzeugen oder zwischen Werkzeug und Shell – nur `ui/`.

## 3. Manifeste

### 3.1 `tool.yaml`
```yaml
tool:
  id: candidate                 # [a-z0-9-]{2,40}, eindeutig
  name: Kandidat
  version: 1.0.0
  handles: [candidate, task]    # Objekttypen, für die das Werkzeug einen Container bekommt
  kind: object                  # object | instrument | panel  (Instrument: eine Zelle in der Leiste; Panel: Gespräch, Palette)
  entry: {js: tool.js, css: tool.css}
  api:                          # Allowlist – der Server lehnt alles andere mit 403 ab
    - GET /api/candidate/*
    - POST /api/mission/approve
  events: {emits: [decision.answered], listens: [object.open, task.changed]}
  trust: CORE                   # CORE | CAPTAIN | GUPPI_BUILT | COMMUNITY
  tests: [test.spec.js]         # Browserabnahme (uix_check läuft sie je Werkzeug)
  needs: {ui: ">=1.0 <2"}       # Vertragsversion
```

### 3.2 `shell.yaml`
```yaml
shell:
  id: cockpit
  name: Cockpit
  version: 1.0.0
  entry: {js: shell.js, css: shell.css}
  provides: [strip, tree, dock, talk, palette]   # welche Slots die Shell anbietet
  layout: {persist: browser}                     # Layout je Browser (localStorage), Format frei
  trust: CORE
  needs: {ui: ">=1.0 <2"}
```

## 4. Lebenszyklus (JavaScript)

```js
// tool.js – ein Werkzeug registriert sich; nichts anderes passiert beim Laden
sedra.registerTool({
  id: 'candidate',
  mount(el, ctx){            // el: leerer Container der Shell; ctx: {object, api, bus, tokens, shell:{open, notify}}
    this.el = el; this.ctx = ctx;
    this.off = ctx.bus.on('task.changed', e => { if(e.id === ctx.object.id) this.refresh(); });
    return this.refresh();
  },
  async refresh(){ const c = await this.ctx.api('/api/candidate/'+this.ctx.object.id); render(this.el, c); },
  actions(){ return [{label:'Erneut testen', run:()=>this.ctx.api('/api/task/retest',{method:'POST',body:{id:this.ctx.object.id}})}]; },  // zustandsabhängig
  unmount(){ this.off(); this.el.replaceChildren(); }
});
```

- `mount/unmount` sind Pflicht, `actions()` liefert die Handlungen des Objekts im aktuellen Zustand (Regel 3 des Cockpits), `refresh()` ist Konvention.
- Ein Werkzeug **zeichnet nur in `el`**, nie in `document`; keine globalen Stile außer in seiner `tool.css` mit Präfix `.t-<id>`.
- Ein Instrument (`kind: instrument`) implementiert `mount(el, ctx)` genauso, nur in eine Zelle; `summary()` liefert `{label, value, tone, hint}`.

```js
// shell.js – die Shell besitzt den Bildschirm
sedra.registerShell({
  id: 'cockpit',
  async start(ctx){          // ctx: {api, bus, tokens, tools: Registry, layout}
    buildStrip(ctx.tools.byKind('instrument')); buildTree(); buildDock(); buildTalk(ctx.tools.get('talk'));
    ctx.bus.on('object.open', o => this.open(o));
    ctx.bus.on('decision.pending', d => this.badge(d));
  },
  open(object){              // fragt die Registrierung: wer handles object.type? → Container je Werkzeug
    for(const t of this.ctx.tools.for(object.type)) this.dock.add(object, t);
  }
});
```

## 5. Ereignisbus (`ui/bus.js`)

Benannte Ereignisse, flache Objekte, keine Funktionen darin. Die Shell darf alle senden; Werkzeuge nur die in `events.emits`.

| Ereignis | Nutzlast | Sender |
| --- | --- | --- |
| `object.open` | `{type, id, title}` | Shell, Werkzeuge (Verweise), Gespräch (Router) |
| `task.changed` | `{id, phase, step, steps, pending}` | Werkzeug `talk`/Poller aus `/api/missions` |
| `decision.pending` / `decision.answered` | `{id, kind, mission_id, gate_id, describe}` | Poller / Werkzeug `decisions`, `talk` („einmal ja“) |
| `model.changed` | `{recipe_id, loaded, context}` | Werkzeug `workshop` |
| `live.line` | `{task_id, line, kind}` | SSE-Client (`/api/task/<id>/live`) |
| `talk.context` | `{object}` | Shell (Gespräch folgt dem Objekt) |

## 6. Server-Anbindung

- `GET /uix/manifest` → aktive Shell, Werkzeuge (id, name, handles, kind, entry-URLs, trust, version); aus `uix/shells`, `uix/tools`
  und `local_config/{shells,tools}` zusammengesetzt. Nur Manifeste, die das Schema bestehen und deren Dateien existieren.
- Dateien: `/uix/tools/<id>/<datei>`, `/uix/shells/<id>/<datei>` – nur aus registrierten Ordnern, keine `..`, CSP bleibt `self`,
  kein Inline-Code.
- **API-Allowlist**: jeder Aufruf aus einem Werkzeug trägt `X-SEDRA-Tool: <id>`; der Server prüft Methode+Pfad gegen `api:` des
  Manifests (Platzhalter `*` nur am Ende). Treffer fehlt → 403 `tool_route_not_allowed`, Audit `UIX_TOOL_DENIED`. `api.js` setzt den
  Header automatisch aus dem `ctx`.
- **Installation** (Build 9+): `POST /api/uix/install {kind, source}` → Gate `install_module` mit Manifest, Dateiliste, SHA-256 je Datei,
  Commit-ID; Flag-Prüfung wie bei Skills (`scan`), zusätzlich: kein `eval`, kein `fetch` auf fremde Hosts, keine `import()` von außerhalb.
  Nach Freigabe liegt das Modul unter `local_config/…`; `uix.yaml` führt es. Entfernen ist kein Gate (nur Audit).
- Vertrauensränge: `CORE` (im Paket), `CAPTAIN` (vom Captain geschrieben), `GUPPI_BUILT` (aus einer Spec mit verstecktem Test, Nachweiskette),
  `COMMUNITY` (fremd; nie ohne Durchsicht, bekommt standardmäßig nur `GET`-Routen).

## 7. Wie SEDRA selbst ein Modul baut (GUPPI-Weg)

1. **Spec** in `benchmarks/devvm_specs/tool_<id>.py` wie heute (NOTES/STAGES): Zielobjekt, Handlungen, API-Routen, Ereignisse; die
   reinen Teile (Zustandsmodell, Formatierung) als `host_hidden`-Node-Tests, der Browser-Teil als `uix_check`-Abnahme (`test.spec.js`:
   mount in leeren Container, Ereignis senden, DOM prüfen).
2. **Bauen** in der DevVM nach `tool.yaml`-Schema; `spec_check.py` muss `result ok` sagen; der Kandidat trägt `trust: GUPPI_BUILT`.
3. **Einbau** über denselben Install-Gate wie fremde Module (Manifest, Hashes, Spec-Nachweis im Gate sichtbar).
4. **Vorlagen** für GUPPI: `tools/_template/` (Werkzeug) und `shells/_template/` (Shell) mit funktionierendem Minimum und Kommentaren;
   ein neues Modul beginnt immer als Kopie der Vorlage.

## 8. Abnahme

- `benchmarks/uix_check.py --tool <id>`: lädt die aktive Shell, öffnet ein Objekt des Typs, prüft: Container gefüllt, keine Konsolen-
  fehler, Handlungen vorhanden, `unmount` räumt auf, kein Zugriff außerhalb des Containers, nur erlaubte Routen gerufen (Proxy zählt).
- `tests/test_uix_contract.py`: Schemaprüfung aller Manifeste, Allowlist-Durchsetzung, Manifest-Endpunkt, Dateigrenzen, 400-Zeilen-Regel.
- Jedes Modul hat eine `README.md` mit Zweck, Objekttypen, Routen und einem Screenshot.

## 9. Reihenfolge

1. **Build 7**: `ui/` (Vertrag, Bus, Schemata, Lader, Manifest-Endpunkt, Allowlist), Cockpit-Shell (Leiste, Baum, Dock ~300 Zeilen,
   Gespräch, Palette), Werkzeuge aus den heutigen Fenstern: `talk`, `decisions`, `workshop`, `library`, `crew`, `meter`, `logbook`,
   Instrumente. Retro ins Archiv. `uix_check` auf Werkzeuge umgestellt.
2. **Build 8**: Werkzeuge `task`, `candidate` (diff2html lokal), `tests`, `live` (SSE), `files`, `costs` (Münzloch).
3. **Build 9**: Modus und Grenzen, `decisions` an der Grenze, Vorhaben und „＋ Neu“, Installation mit Gate, Vorlagen für GUPPI.
4. Danach: Shell `minimal` (E), dann `paperclip` (D); erste GUPPI-Spec für ein eigenes Werkzeug (z. B. „Routinen“).

## 10. Andockstelle im Backend: das Desk (Captain 18:47)

Der Captain: im Backend braucht es einen Teil, der an das Desktop-Modul andockt und alles verbindet und bereitstellt – auch wenn die
Architektur dafür neu gedacht wird. Heute macht `uix_server.py` (≈ 1.300 Zeilen) alles zugleich: HTTP, Fachlogik, Gates, Prozessliste.
Das wird getrennt:

```
guppi_runtime/
  desk/                     ← die Andockstelle (neu, Build 7)
    gateway.py              Manifeste (Shell, Werkzeuge), Dateien aus registrierten Ordnern, Allowlist je Werkzeug, CSP, Token
    objects.py              EIN Objektmodell für alles: project, intent, task, candidate, file, model, skill, agent, decision, routine
    actions.py              Verben je Objekttyp (task: retest/pause/undo; model: load/unload/test; skill: write; …) – jedes Verb kennt sein Gate
    decisions.py            eine Quelle für alle Entscheidungen: Mission-Gates + Änderungsanträge (switch, routing, model_add, skill) + Grenzen
    events.py               ein Strom: `/api/events` (SSE) aus Audit, Missions-Store, Modell-Loader, Live-Ausgaben; Werkzeuge pollen nicht mehr
    live.py                 Live-Zeilen je Aufgabe (run_log, step_journal, Modell-Stream des runaway_guard) → `live.line`
    boundaries.py           Modus und vier Grenzen je Projekt (Build 9), Deckungsprüfung vor `guard.create_gate`
    registry.py             welche Shell aktiv ist, welche Werkzeuge installiert sind (`local_config/uix.yaml`)
  uix_server.py             nur noch HTTP: Routen → desk; Härtung (Secrets, Timeout, Host/Origin) bleibt
```

**Grundsätze der Andockstelle**

1. **Ein Objektmodell, eine Form.** Jedes Objekt kommt als `{type, id, title, state, summary, actions:[…], links:[…]}` –
   `GET /api/objects/<type>/<id>` und `GET /api/objects/<type>?filter`. Werkzeuge brauchen keine zehn Spezialrouten mehr; die alten
   Routen bleiben ein Jahr als Hülle.
2. **Verben statt Routen.** `POST /api/actions {type, id, verb, args}` → `actions.py` prüft Modus/Grenzen, erzeugt bei Bedarf *eine*
   Entscheidung, führt sonst aus, schreibt Audit. Dasselbe Verb aus Gespräch, Werkzeug oder Palette läuft über denselben Weg.
3. **Entscheidungen haben eine Quelle.** `decisions.py` vereint Mission-Gates, `open_requests` und Grenzüberschreitungen zu
   `{id, kind, describe, ways:[einmal|aendern|ablehnen|freigeben], binding}`; `POST /api/decisions/<id> {way}` ruft approve/apply oder
   reject – Einmal-Token und Inhaltsbindung des Guard bleiben unverändert darunter.
4. **Ein Ereignisstrom.** `/api/events` (SSE, Token-gesichert) liefert alle Bus-Ereignisse aus §5 serverseitig; die Shell verteilt sie.
   Polling (heute 3–8 s je Fenster) entfällt; Wiederverbindung mit `Last-Event-ID`.
5. **Der Kern bleibt unberührt.** Desk ruft Brain, Guard, Missions, Router, Skill-Bibliothek – es ersetzt nichts davon. Alles, was Desk
   schreibt, läuft über die bestehenden Gates. Konzeptprüfung P0 (Inhaltsbindung) ist Voraussetzung, nicht Folge.
6. **Testbar ohne Browser.** Jede Desk-Datei ist mit dem Fake-Host (`host_isolation`) prüfbar; `test_desk_*.py` deckt Objektmodell,
   Verben, Entscheidungen, Strom, Allowlist. Die Browserabnahme (§8) kommt obendrauf.

**Umbau in Schritten (im Bauplan §9 enthalten):** Build 7 legt `desk/gateway.py`, `registry.py`, `events.py`, `decisions.py` an und
verlegt die heutigen Views dorthin (keine Verhaltensänderung, alte Routen bleiben); Build 8 `objects.py`, `actions.py`, `live.py`;
Build 9 `boundaries.py`. Danach ist `uix_server.py` nur noch die HTTP-Hülle.

## Nachtrag 15.10.2026 (Build 17): eine Shell aus einer Vorgabe, strukturierte Antworten

- **Shell aus Vorgabe.** `shell.yaml` darf statt `entry` den Schlüssel `vorgabe: shell.vorgabe.yaml` tragen; `entry`, `api` und
  `provides` sind dann verboten – Code, Routen und Slots gehören dem Rahmen `ui/frame.js` (Vertragscode, `FRAME_API` im Vermittler).
  Die Vorgabe wird gegen `ui/schema/vorgabe.schema.json` geprüft (flache Teilmenge: `models/structured.py`), unbekannte Schlüssel
  mit Satz abgewiesen. Der Rahmen setzt die Vertragsmarken selbst; `uix_check` leitet das Profil aus der Vorgabe ab und prüft ganz.
- **Der Creator** ist Vertrag: `ui/vorgabe.js` (Block, Skizze) wird von `desk.html` geladen und von Einstieg und Werkzeug „Module“
  genutzt; die Routen `GET /api/uix/vorgaben`, `POST /api/uix/vorgabe` (nur vorschlagen) und `POST /api/uix/scaffold` mit `vorgabe`.
- **Strukturierte Antworten.** `ModelRouter.chat(…, schema=…)` erzwingt ein JSON-Schema beim Modell (`response_format`), prüft die
  Antwort und erbittet sie bei Fehlern mit Satz erneut (≤ 3 Runden). Jede Runde geht durch den Inhaltsschutz. Für jedes Modul, das
  vom Modell Daten statt Text will.

## Nachtrag 15.10.2026 (Build 19): Objekttyp `gateway`, Zonen am Rand

- `gateway` ist ein Objekttyp des Vertrags (Werkzeug `gateway` als Werkstück, `schutz` als Nachweis daneben), ein Ort der Ortskunde
  und ein Starttyp für Vorgaben. Routen `/api/gateway/*` und `/api/guard/probe`.
- Eine Vorgabe darf `orte: {einblenden: rand}` und `leiste: {einblenden: rand}` sagen: die Zone steht nicht im Raster, liegt verborgen
  am Rand und fährt beim Anfahren (Zeiger oder Tastatur) heraus. `uix_check` misst solche Zonen nicht als Zonen.

## Nachtrag 21.10.2026 (Spec 4, Shell D): N1 bis N8

Freigegeben mit G2-S4-03 (N1), G2-S4-04 (N2), G2-S4-05 (N3, N4) und G2-S4-21 (Orte); Wortlaut aus `SPEC_AGENTEN_ORCHESTRIERUNG_v1.md`, D4.4.

- **N1 – `handles` mit Zusatz (§3.1, §4).** Ein Eintrag in `handles` darf neben dem Typ (wie bisher: alle Objekte dieses Typs) eine
  der Formen `typ:alle` (nur das Objekt mit der ID `alle`, die Sammlung), `typ:*` (jedes Einzelobjekt des Typs, also weder die ID
  `alle` noch ein Objekt mit `collection: true`) oder `typ:<id>` (genau dieses Objekt, z. B. `agent:rollen`, ein festes Objekt mit
  `collection: true` im Deskriptor) tragen. Das Schema erlaubt das Muster `^[a-z0-9-]{2,40}(:(\*|[a-z0-9-]{1,40}))?$`. Der Lader
  bekommt `registry.forObject(object)`; `registry.for(type)` bleibt für Aufrufe ohne Objekt und nennt jedes Werkzeug, das den Typ in
  irgendeiner Form handelt. Welche Werkzeuge ein Objekt zeichnen, entscheidet die reine Funktion `handlesMatch(eintrag, objekt)`
  (`ui/loader.js`). Alle bestehenden Manifeste behalten ihre Bedeutung. Die Serverprüfung der Manifeste (`desk/gateway.py`) lässt
  die Formen mit Zusatz zu, sobald das erste Werkzeug eine trägt.
- **N2 – Mehrere Instanzen eines Werkzeugs (§4).** `unmount(el)` und `actions(el)` bekommen den Container, den `mount` bekommen hat.
  Ein Werkzeug darf mehrere Instanzen zugleich führen (eine je Container) und muss sie dann je `el` verwalten; ein Werkzeug mit einer
  Instanz darf das Argument ignorieren. `lifecycle.unmountTool` und `actionsOf` reichen `state.el` weiter. Der Zustand eines Werkzeugs
  darf nicht in `this` liegen, wenn es mehrere Instanzen führt.
- **N3 – Ereignisse (§5).** Neue Zeilen der Tabelle (Nutzlast flach, Pflichtfelder fett): `agent.changed` {**id**}; `issue.changed`
  {**id**}; `budget.warning` {**agent_id**, prozent, stufe}; `slot.changed` {slot, state, run_id, priority, queue_len}. Sender: der
  Ereignisstrom (`desk/events.py`). Werkzeuge dürfen sie in `events.listens` nennen, aber nicht senden. Jedes Werkzeug, das Daten
  zeigt, hört außerdem `desk.resync` und liest dann neu.
- **N4 – Entscheidungen mit Agent (§5, §10.3).** `decision.pending` und die Form der Entscheidung tragen das optionale Feld `agent_id`
  (leer, wenn kein Agent betroffen ist).
- **N5 – Darstellungshinweise im Objekt (§4).** Der Deskriptor eines Objekts darf `view` (z. B. `liste`, `board`) und `kompakt`
  tragen. Beides sind Hinweise der Shell an das Werkzeug, keine Identität; Werkzeuge ändern die Ansicht, indem sie `object.open` mit
  demselben Typ und derselben ID und anderem `view` senden. Der Verlaufsschlüssel einer Shell darf `view` enthalten.
- **N6 – Routen neuer Werkzeuge (§6).** Ein Werkzeug, das nach dem Datum dieses Nachtrags entsteht, nennt in `api` nur
  `POST /api/objects` (lesen) und `POST /api/actions` (handeln); ein Instrument zusätzlich `GET /api/strip`. Bestehende Werkzeuge
  sind ausgenommen, bis ihre Spec sie umstellt.
- **N7 – Ergebnisfelder des Desk (§10).** Die Listen der Typen `agent`, `issue`, `routine`, `budget` und `gespraech` tragen `quelle` =
  {`zustand`: `aus`, `bereit` oder `fehler`, `grund`, `takt`}; Werkzeuge unterscheiden damit „ausgeschaltet“, „ausgefallen“ und
  „leer“. Der Desk-Typ `gespraech` ist nur lesend, die ID ist die Agenten-ID, der Filter heißt `agent`.
- **N8 – Einbau (§7.3).** Werkzeuge, die im Paket liegen (`uix/tools/`), kommen nach Review per `adopt_plan` oder Handkopie hinein
  (Linie L5) und tragen `trust: CORE`; `install_module` gilt für Werkzeuge unter `local_config/`.
- **Orte (G2-S4-21).** `ui/places.js` nennt zusätzlich `org` (`agent:alle`), `routines` (`routine:alle`), `slots` (`model:alle`) und
  `labor` (`labor:labor`); der Ort `crew` zeigt auf `agent:rollen`. Die Orte gelten in jeder Shell; ohne Werkzeug zeigt die Shell
  ihren Leerzustand.

## Nachtrag 21.10.2026 (Spec 0, Kern-API): §10 Registrierung, Verben ohne Objekt, neue Typen, Feld `client`, Client-Token

Freigegeben mit G2-S0-13; Wortlaut aus `SPEC_AGENTEN_ORCHESTRIERUNG_v1.md`, D1 bis D3. Gebaut in K0.10 bis K0.15, K0.19 bis K0.22.

- **R1 – Registrierung der Objekttypen (§10 Grundsatz 1).** Welche Typen es gibt und was sie lesen, steht in einem Register
  (`desk/kinds.py`), nicht in `uix_server.py`. Ein Typ ist `Kind(name, title, read, listing, verbs, type_verbs)`; `read(hub, id)`
  liefert ein Objekt in der einen Form oder `None` (dann antwortet das Desk mit dem Objekt „nicht gefunden“), `listing(hub, payload)`
  die Liste, `payload` darf filtern. Die neun Typen von heute stehen in `desk/builtin_kinds.py`. Ein neuer Anwendungsfall ist ein
  Modul mit `register(registry, hub)` und eine Zeile in `desk/extensions.MODULES`; das Register wird beim Start der Oberfläche
  einmal gefüllt und dann eingefroren (`kinds_frozen`), über eine Anfrage kommt kein Typ dazu. Ein doppelter Name wird abgewiesen
  (`kind_already_registered`), die halbe Registrierung des Moduls zurückgenommen und als `DESK_KIND_REFUSED` protokolliert; die
  übrigen Typen laufen weiter. Fehlt einem Objekt einer der sieben Schlüssel, antwortet die Route mit `object_shape_invalid`
  statt mit einem halben Objekt; weitere Schlüssel sind erlaubt. `GET /api/objects/…` aus Grundsatz 1 gibt es nicht; der Weg ist
  `POST /api/objects {type, id?}` (G1-S0-b).
- **R2 – Verben ohne Objekt (§10 Grundsatz 2).** `POST /api/actions {type, verb, args}` ohne `id` läuft nur, wenn der Typ ein Verb
  ohne Objekt dieses Namens hat (z. B. `anlegen`); sonst wie bisher `id_required`. Das Ergebnis trägt `id: null`. Verben mit Gate
  folgen dem Muster `desk/gated.py` (Antrag mit Gate und Bindung, Anwenden nur mit gültigem Einmal-Token).
- **R3 – Neue Typen `agent`, `issue`, `routine`, `budget` (§10, Objektmodell).** Sie kommen aus der Orchestrierung
  (`desk/orchestra_kinds.py`) und sind nur da, wenn der Schalter `orchestra` an ist und das Paket gültig startet; sonst ist `issue`
  ein `unknown_object_type` und `agent` bleibt der heutige Platzhalter (Liste leer, Einzelansicht `unknown_object_type`). `issue` ist
  die Aufgabe des Bretts, `task` bleibt die Mission (OP-1). `budget` hat die ID des Agenten. In Spec 0 bieten die vier Typen keine
  Verben an (OP-12); die Verben baut Spec 1 mit den Guard-Regeln GR-029 bis GR-038.
- **R4 – Feld `client` (§10 Grundsatz 2, Audit).** Der Eintrag `UIX_ACTION` trägt `payload = {type, id, verb, client}`. `client` setzt
  der Server aus dem Token, nie der Aufrufer: `shell` (Browser-Token), `chat` (Browser-Token und `X-SEDRA-Tool` ∈ {`talk`,
  `planung`}, der Kopf hat die Allowlist bestanden), `cli`, `mcp`. Ein Feld `client` im Körper von `/api/objects` oder
  `/api/actions` wird mit `400 client_is_set_by_server` abgewiesen und als `UIX_CLIENT_REFUSED` protokolliert. `client` ist eine
  Herkunftsangabe, keine Berechtigung: kein Verb und kein Gate hängt davon ab. Innerhalb der Seite (`shell` gegen `chat`) ist die
  Angabe eine Selbstauskunft; Werkzeuge mit `trust: COMMUNITY` bekommen ohnehin nur `GET`-Routen.
- **R5 – Client-Token (§6, Anmeldung).** Neben dem Browser-Token schreibt der Server beim Start je externem Client (`cli`, `mcp`) einen
  eigenen Zufallstoken mit Port und PID nach `runtime_data/uix/clients/<client>.json` (atomar; unter Windows mit der DPAPI, sonst
  Datei mit Rechten 0600) und löscht die Dateien beim Beenden. Die Anmeldung bleibt der Kopf `X-GUPPI-Token`. Ein Client-Token
  öffnet nur `POST /api/objects` und `POST /api/actions`; jede andere Route antwortet ihm mit `403`. Die externen Clients sind
  `guppi objects <typ> [<id>]`, `guppi act <typ> <id|-> <verb> [--args JSON]` und der MCP-Server `desk_mcp.py` (Werkzeuge `objects`,
  `act`); ohne laufende Oberfläche melden sie `uix_not_running` – es gibt keinen Weg am Desk vorbei.
