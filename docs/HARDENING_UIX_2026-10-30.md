# Härtungsrunde UIX 2026-10-30 – alle Shells, alle Werkzeuge, die Anbindung

Captain 30.10. 09:57: „gezielt die UIX auf allen Shells, Werkzeuge und die Anbindung nochmal überarbeiten, eine Hardening-Runde durchführen“.
Branch `uix/hardening-2026-10-30`, zuerst auf `harness/stufe-5` (`f66ae1a`) gebaut, dann auf `origin/main` `f9afd1e` umgesetzt (Captain 13:36: „es liegen
neue Daten im Git“ – Stufe 4/5 übernommen, Stufe 6, Review-Befunde, Spec Dynamische Rezepte; ein Konflikt in `harness/shell.yaml`). Kein Push – Lieferung als Fork-ZIP. Die Runden vom 14.10.
(`HARDENING_2026-10-14.md`, `…_BUILD9.md`) bleiben gültig; H1–H14 wurden nachgeprüft und gelten.

**Vorgehen:** vier getrennte Durchsichten (Laufzeit `ui/*.js`, Server `uix_server.py`/`desk/*`, zehn Shells, 44 Werkzeuge) gegen den
Vertrag (`SHELL_WERKZEUG_VERTRAG_v1`), je mit Zeilenbeleg. **68 Befunde** (4 hoch, 31 mittel, 33 niedrig). 60 wurden in der Runde gebaut, jede Härtung mit Test
oder Abnahme (§3); die 4 Verhaltensänderungen E1–E4 hat der Captain um 15:46 übernommen und sie sind ebenfalls gebaut (§4); 4 sind bewusst notiert (§5).

## 1. Was geprüft wurde und in Ordnung ist

| Bereich | Befund |
|---|---|
| Markup in `ui/`, allen Shells, allen Werkzeugen | kein `innerHTML`, `insertAdjacentHTML`, `outerHTML`, `document.write`, `eval`, `new Function`, `javascript:`; Server-Text nur über `textContent`/`el()`; der einzige `srcdoc` (Entwurf) liegt in `sandbox="allow-scripts"` ohne `allow-same-origin`. Der archivierte Desktop (`uix/js`, `/retro`) nutzt `innerHTML` nur mit `escapeHtml` – unverändert, Archiv. |
| Token | `hmac.compare_digest` an beiden Stellen; kein Token in Log, Audit, DOM, `console`, Antworten (`/api/uix/clients` liefert nie den Token); Query-Token nur für `/api/events` auf Loopback; Nicht-CORE-Werkzeuge im Rahmen ohne Token. |
| Statische Auslieferung | nur registrierte Ordner, Dateityp aus `SERVE_TYPES`, kein `..`, Symlink-Sperre für Datei und Elternordner (H8), `nosniff`, `no-store`, CSP mit `frame-ancestors 'none'`. |
| Nutzlast | ≤ 1 MiB, nur JSON-Objekte, 10 s Lesezeit, Leerlauf 30 s (H3). |
| Allowlist | COMMUNITY nur GET (`_common`); `install_request`/`install_apply` erzwingen COMMUNITY; `trust_apply` nur bei unverändertem Hash; Routen außerhalb der Tabellen: nur Seite, Statik, Rahmen, Harness-Präfix. Die Shell-Allowlist gilt serverseitig (`X-SEDRA-Shell`). |
| Gates | jedes `*_apply` und `gated.apply/decide` prüfen Einmal-Token + Bindung (`guard.authorize`) unter `execution_lock`; Datei-Hash in der Bindung bei Schaltern/Routing/Install/Trust; `binding_stale`/`guard_refused` mit Audit; `install_apply` kopiert nach `*.im-bau` und hasht erneut (H10). |
| Lebenszyklus | Bus-Abos nur über `ctx.bus.on` (→ `_offs`); `unmountTool` sichert Scroll, schreibt die Ablage, löst alle Abos, leert den Container; `JSON.parse`/`localStorage` in `ui/` und allen Shells in `try/catch`; jedes `refresh()` der Werkzeuge mit Satz im Container. |
| Form | alle Dateien ≤ 400 Zeilen (knapp: `cockpit/dock.js` 399, `talk/tool.js` 400, `frame.js` 399); CSS nur Token (ein `#2b2b2b` in `costs`/`meter` → Token, HU-T21). |
| Grenzen | Ereignis-Ring 256, `open_crossings` ≤ 50 (H12), Einmal-Erlaubnis verfällt (H11), Vorhaben ≤ 500 (H13), Listen in den Werkzeugen gekappt (`labor` 12/Seite, `board` 8, `agentfenster` 50/10, `routines` 20, `system` 40, `files` 20 000 Zeichen, `candidate` 2 000 Zeilen, `/api/audit` 40). |

## 2. Was geändert wurde (60 Härtungen)

### 2.1 Hoch

| Nr | Härtung | Datei |
|---|---|---|
| **HU-1** | **Kein Shell-Wechsel über die Brücke.** Ein abgeschottetes (Nicht-CORE) Werkzeug konnte per `postMessage {op:'shell', name:'open', args:[{type:'shell', id:'x'}]}` die aktive Shell umschreiben und die Seite neu laden – ohne jede Route. Die Brücke prüft `open` jetzt: Typ nach Muster, nie `shell`, ID Text/Zahl (`open_objekt_ungueltig`). | `ui/bruecke.js`, `tests/test_stufe_c_bruecke.py` |
| **HU-2** | **Der Entwurf führt nichts ohne Klick aus.** Ein ```` ```vorarbeiter ````-Block in der Modellantwort wurde sofort als `POST /api/vorarbeiter/aktion` ausgeführt (Lauf starten, anlegen, rendern). Jetzt ein Knopf „Aktion ausführen: …“ mit dem JSON davor – wie `talk.offer`. | `tools/entwurf/tool.js` |
| **HU-S1** | **Der Knopf „Zum Standard machen“ war tot:** `POST /api/uix/standard` fehlte in der `api`-Liste der Shell `start` → 403 und `UIX_TOOL_DENIED`. Eingetragen; dazu der **Vertragstest HU-T12**: jede Route, die eine Shell oder ein Werkzeug ruft, steht in der `api`-Liste – und die Liste nennt nichts, was der Code nicht ruft (Helfer aus `ui/` zählen mit). Dabei fiel auf: `tools/_template` rief `POST /api/actions` ohne Eintrag – die **Vorlage für jedes neue Werkzeug** hätte 403 bekommen. | `shells/start/shell.yaml`, `tools/_template/tool.yaml`, 20 weitere Manifeste (zu weite Listen gekürzt: `gateway`, `library` (4 nie gebaute Routen), `planung`, `rekorder` (3 Reste der Browser-Aufnahme), `schutz`, `boundaries`, `tests`, 9 Instrumente, `_template`, `harness`, `minimal`), `tests/test_uix_hardening_2026_10_30.py::RoutenImManifest` |
| **HU-T1** | **`schutz` lief doppelt mit einer Instanz.** Das GateWay bettet `schutz` in sein Menü ein (`gateway/nav.js`), die Harness hängt für `gateway:alle` beide Werkzeuge ein – das zweite `mount` überschrieb `this.host/this.offs`, das erste `unmount` leerte den falschen Container, Abos gingen verloren. Jetzt eine Instanz je Container (Nachtrag N2, `instanzen: viele`), die Einbettung baut über den Container ab. Der Querzugriff selbst (`root.sedra.tools.get('schutz')`) bleibt → Entscheidung E4. | `tools/schutz/tool.js`, `tool.yaml`, `tools/gateway/nav.js` |
| **HU-S16** | **In der Harness beantwortete `shellApi.decide(id, way)` keine Entscheidung** – es öffnete nur den Posteingang und ließ Kennung und Weg fallen; eine Antwort aus der Entscheidungen-App lief ins Leere (Stufe 5 hatte über `hub.decide` geprüft, nicht über die App). Jetzt `sedraStand.entscheiden` + `freigabenLaden`; ohne Kennung weiter der Posteingang als App. *Neu gefunden beim Vertragstest.* | `shells/harness/shell.js` |

### 2.2 Server (`uix_server.py`, `desk/*`)

| Nr | Härtung | Datei |
|---|---|---|
| HU-B2 | `chat_attach` weist jetzt auch `runtime_data/uix/clients/*.json` (Client-Token, unter POSIX Klartext) und `cloud_keys.json` ab – beide kamen nach H1 dazu. | `uix_server.py` (`SECRET_NAMES`, `SECRET_DIRS`) |
| HU-B3 | **Herkunftsprüfung S7 auf jedem Gate-Weg:** bisher nur `/api/decisions/answer` und die Harness-Pfade; `mission/approve|reject`, jedes `*/apply` und `/api/actions` beantworteten Gates ohne Prüfung – ein Harness-Prozess mit abgelesenem Token hätte jedes Missions-Gate freigeben können. `HERKUNFT_WEGE` deckt alle. | `uix_server.py` |
| HU-B5 | Abgebrochene Verbindung (Browser lädt neu, `BrokenPipeError`) löste in `_send` ein zweites `_send(503)` und einen Traceback auf stderr aus (im Minimal-Lauf der Gesamtprüfung sichtbar). `_send` fängt, `Server.handle_error` schweigt bei Verbindungsabbrüchen. | `uix_server.py` |
| HU-B6 | `hmac.compare_digest(str, str)` warf `TypeError` bei Nicht-ASCII im Token-Kopf (Verbindung ohne Antwort). Vergleich als Bytes. | `uix_server.py` |
| HU-B7 | `gated.decide`: scheiterte der Applier mit einer fremden Ausnahme oder die Token-Prüfung, blieb die Mission offen ohne `pending` mit unverbrauchten Tokens – nicht beantwortbar, kein Audit. Jetzt geschlossen mit `result.error` und `DESK_GATED_FAILED`. | `desk/gated.py` |
| HU-B8 | `switch_apply`, `routing_apply`, `model_add_apply` schrieben mit `write_text` (nicht atomar), Sicherung `.bak-<Tag>-uix` – die zweite Änderung am Tag überschrieb die Sicherung der ersten. Jetzt Temp + `replace` (Zeilenenden bleiben, CRLF-Test), Sicherung mit Sekunde. | `uix_server.py` (`_write_raw`, `_sicherung`) |
| HU-B9 | `uix.yaml` (Shell-Wahl, Ablage, Werkzeug an/aus): Lesen-Ändern-Schreiben ohne Sperre, fester Temp-Name – zwei Tabs konnten sich überschreiben. Modul-Sperre + `mkstemp`. | `desk/registry.py` |
| HU-B10 | Die Durchsicht beim Einbau prüfte nur `.js`/`.html`; ein `.svg` mit `<script>`/`onload` wurde kopiert und same-origin ausgeliefert. Jetzt auch `.svg`, mit den Flags `<script in SVG/HTML` und `on…= in Markup`. | `desk/install.py` |
| HU-B11 | `install_remove` prüfte „Shell ist aktiv“ nur gegen den Start-Override; die in `uix.yaml` gewählte Shell konnte entfernt werden (nächster Start: `active_shell_not_available`). | `uix_server.py` |
| HU-B12 | `code` steht jetzt in **jeder** 400 (vorher nur bei zwei Codes); `FRIENDLY_400` kennt `request_too_large`, `bad_content_length`, `captain_approval_required/invalid`, `unknown_shell`, `module_changed_since_the_request`, `binding_stale`; kaputter `Content-Length` → `bad_content_length` statt Traceback. | `uix_server.py` |
| HU-B14 | Rahmenseite (`/uix/frame/…`) lief außerhalb des `try`: kaputte `uix.yaml` → toter Thread statt 503. | `uix_server.py` |
| HU-L11 | **Ereignisse des Stroms sendet kein Werkzeug** (Nachtrag N3 war nirgends durchgesetzt): `bus.js` lehnt `task.changed`, `model.changed`, `system.state`, `desk.*`, `tools.refresh`, `agent/issue.changed`, `budget.warning`, `slot.changed`, `harness.*` von einem Werkzeug ab; das Gateway weist ein Manifest mit solchen `emits` ab (`events_emits_reserved`). | `ui/bus.js`, `desk/gateway.py`, `tests/test_desk_gateway.py` |

### 2.3 Laufzeit (`ui/*.js`)

| Nr | Härtung | Datei |
|---|---|---|
| HU-L4 | `ablage.set()` vor dem ersten `get()` schickte nur den eigenen Schlüssel; der Server **ersetzt** – alle anderen Werte des Werkzeugs am Objekt waren weg. Schreiben läuft jetzt über `holen()`. | `ui/lifecycle.js`, `tests/test_uix_vertrag11.py` |
| HU-L5 | Verlauf aus `localStorage` (Shells aus Vorgabe): ein `null`/String darin brach den Start bei **jedem** Laden (Fatal-Seite). Einträge werden gefiltert, ein kaputtes `current` gelöscht. | `ui/frame.js` |
| HU-L6 | `refreshKarte`: zwei überlappende Aufrufe hängten das Entscheidungs-Werkzeug doppelt ein (ohne `unmount`, Abos blieben). Marker + Nachlauf. | `ui/frame.js` |
| HU-L7 | `routeErlaubt` der Brücke kannte keine Präfix-Routen (`GET /api/x/*`, Vertrag §6) – ein Nicht-CORE-Werkzeug mit solcher Allowlist bekam für alles `tool_route_not_allowed`. Jetzt wie `gateway.route_allowed`. | `ui/bruecke.js` |
| HU-L9 | Rekorder: `getUserMedia` **vor** `aufnahme/beginnen`; lehnte der Kern ab, blieb das Mikrofon offen. Reihenfolge getauscht, `MediaRecorder`-Fehler stoppt die Spuren. | `ui/sprache.js` |
| HU-L10 | Wirft `mount()`, nachdem das Werkzeug schon `ctx.bus.on` gerufen hat, blieben die Abos bis zum Neuladen. Im `catch` gelöst, Container geleert. | `ui/lifecycle.js` |
| HU-L13 | `closeEvents()` ließ einen geplanten Neuaufbau-Timer leben – danach eine Verbindung, die niemand schloss. | `ui/loader.js` |
| HU-L14 | `manifest.tools`/`r.reasons`/`t.css`/`t.js` ungeprüft → englischer `TypeError` als Fatal-Text. Deutsche Sätze. | `ui/loader.js` |
| HU-L15 | Brücke im Rahmen ohne Frist (15 s jetzt), `mount`-Promise ohne `catch`. | `ui/rahmen.js` |
| HU-L16 | `shellFuer` (Shell ohne `decide` für Nicht-CORE) wurde gebaut, aber nicht übergeben – toter Code, der Schutz vortäuschte. | `ui/loader.js` |
| HU-L17 | `memos` wuchsen ohne Grenze (Rahmen rief nie `memoVergessen`); verdrängte Objekte des Verlaufs nehmen ihr Memo mit. | `ui/frame.js` |
| HU-T8 | Eine Handlung aus `actions()`, die scheitert, sagt es dem Captain über `shell.notify` – zentral in `actionsOf` (vorher verschluckten Harness und Rahmen die Ablehnung; sechs Werkzeuge und die Vorlage hatten kein Fehlerbild). | `ui/lifecycle.js` |

### 2.4 Shells

| Nr | Härtung | Datei |
|---|---|---|
| HU-S2 | Die **Vorlage** (`_template`, Ausgang jeder neuen Shell) leerte den Körper vor dem `unmount` und kehrte bei „kein Werkzeug“ früh zurück – alte Werkzeuge blieben mit Abos eingehängt. | `shells/_template/shell.js` |
| HU-S3 | Fisch nahm `tools.for(type)` statt `forObject(object)` – Nachtrag N1 (`typ:alle`, `typ:<id>`) ignoriert. | `shells/fisch/shell.js` |
| HU-S4 | Minimal und Start hatten einen **eigenen** Shell-Wechsel (`POST /api/uix/shell` + `reload`) neben `sedraWechsel` (Vertrag N3: „die einzigen Wege“). Jetzt `wechseln()`/`uebersicht()`; `POST /api/uix/shell` aus beiden Manifesten. | `shells/minimal/menubar.js`, `shells/start/shell.js`, beide `shell.yaml` |
| HU-S5 | Minimal stellte das Fenster-Layout aus `localStorage` ungeprüft wieder her (`NaN`-Boxen, Fremdfelder). `sanitizeWindows` wie `dock.sanitizeLayout`. | `shells/minimal/windows.js` |
| HU-S6 | Paperclip: Seitenverlauf nur auf „Array“ geprüft. `sanitizeHistory`. | `shells/paperclip/pages.js` |
| HU-S7 | `decide` in Fisch, GateWay-KMU und der Vorlage sendete kein `decision.answered` (Werkzeuge blieben beim alten Stand). Ein gemeinsamer Helfer `sedraStand.entscheiden(api, bus, id, way)` – statt sieben Umsetzungen. | `ui/stand.js`, drei Shells |
| HU-S8 / S10 | Minimal: „Klick daneben“-Hörer blieb am `document`, wenn ein Menüeintrag schloss (und schloss dann das nächste Menü beim ersten Klick); dasselbe im Ablage-Feld. | `shells/minimal/menubar.js`, `shelfedit.js` |
| HU-S9 | Harness: `JSON.parse` außerhalb des `try` – ein kaputter `sedra.harness.gesehen` warf beim Zeichnen der Taskleiste. | `shells/harness/taskleiste.js` |
| HU-S11 | Start: `view.shells`/`view.rejected` ungeschützt, Bus-Aufruf ohne `catch`. | `shells/start/shell.js` |
| HU-S12 | GateWay-KMU: `shellApi.notify` schrieb nur `console.info` – der Captain sah Hinweise der Werkzeuge nie. Jetzt ins Gespräch. | `shells/gateway-kmu/shell.js` |
| HU-S13 / S14 | Harness: `GET /api/events` überflüssig (der Strom gehört dem Loader); Guppi-XP: `provides: [windows]` versprach Objekte, die Shell leitet nur auf `/retro` um → `chooser`. | `shell.yaml` beider |
| HU-S15 | Minimal: nach dem Schließen bekam das zuletzt **eingefügte** Fenster den Fokus, nicht das oberste. | `shells/minimal/windows.js` |

### 2.5 Werkzeuge

| Nr | Härtung | Datei |
|---|---|---|
| HU-T3 | Rekorder: `setInterval(…, 700)` dauerhaft, auch ohne Aufnahme. Jetzt 700 ms nur, solange der Kern aufnimmt, sonst alle 4 s. | `tools/rekorder/tool.js` |
| HU-T4 | Labor: 5-s-Intervall nur im Reiter „Läufe“ und im sichtbaren Fenster. | `tools/labor/tool.js` |
| HU-T5 | Live/Kosten: jede `live.line` löste sofort einen API-Aufruf (und ein Neuzeichnen) aus – gebündelt (`buendeln`, 300/500 ms). | `tools/live/tool.js`, `tools/costs/tool.js` |
| HU-T6 | Protokolle von Gespräch, Entwurf, Live wachsen nicht mehr ohne Ende (600 Zeilen); die History geht nur noch mit `MAX_HISTORY` (8) ans Modell – vorher der ganze Verlauf je Frage. | `tools/talk/*.js`, `tools/entwurf/tool.js`, `tools/live/tool.js` |
| HU-T7 | Schutz: `answer()` ohne `catch` – eine abgelehnte Antwort war nirgends zu sehen. | `tools/schutz/tool.js` |
| HU-T9 | Labor: die Suche baute bei jeder Taste den Container neu und verlor den Fokus. | `tools/labor/tool.js` |
| HU-T10 | GateWay-Upload: keine Größenprüfung (Base64 in den JSON-Body), Fehler per `alert()`. Grenze 700 KB (Server 1 MiB), Satz im Container. | `tools/gateway/tool.js` |
| HU-T13 | Felder der Serverantwort ohne Schutz in `labor`, `gateway`, `schutz`, `rekorder` (eine halbe Antwort ließ die Fläche halb leer). | vier Werkzeuge |
| HU-T14 | Rekorder: `URL.createObjectURL` nie freigegeben. | `tools/rekorder/tool.js` |
| HU-T15 | Transkript: `suchen()`/`fassung()` ohne `catch` (über Enter am Knopf vorbei). | `tools/transkript/tool.js` |
| HU-T16 | Gespräch: Fokus-Timer und Griff-Hörer am Fenster werden in `unmount` geräumt. | `tools/talk/tool.js` |
| HU-T17 | Labor: globale ID `laborMaster` → Klasse (zwei Instanzen träfen sich). | `tools/labor/tool.js` |
| HU-T18 | Instrumente: `unmount` entfernt jetzt `onclick`/`onkeydown`/`tabindex`/`title` vom Container der Shell. | 9 × `tools/gauge-*/tool.js` |
| HU-T20 | `emits: [object.open]` in 33 Manifesten, obwohl kein Werkzeug es sendet (alle öffnen über `shell.open`) – gestrichen; `emits` ist jetzt wahr. | 33 × `tool.yaml` |
| HU-T21 | `#2b2b2b` → `var(--line)`. | `tools/costs/tool.css`, `tools/meter/tool.css` |

## 3. Prüfung (auf `origin/main` `f9afd1e` + Härtung)

| Prüfung | Ergebnis |
|---|---|
| `tests/test_uix_hardening_2026_10_30.py` (neu) | 11 Tests, 56 Teilprüfungen: HU-B2/B3/B5/B6/B7/B9/B10/B12, HU-L11/L13 (node), Vertragstest Routen für alle 10 Shells und 44 Werkzeuge |
| erweiterte Tests | `test_stufe_c_bruecke` (+1: HU-1; Präfix-Routen), `test_uix_vertrag11` (+1: HU-L4), `test_desk_gateway` (+1 Fall `events_emits_reserved`), `test_uix_shell_start`/`test_uix_guppi_moves`/`test_uix_shell_paperclip` (an HU-S4/S14 angepasst) |
| `uix_check.py --shell harness / cockpit / minimal / paperclip` | **43/43, 41/41, 42/42, 45/45** – alle Oberflächen grün nach der Härtung |
| `harness_abnahme.py --stufe4`, `--stufe5` | **S4-A bis S4-D ok**, **S5-A bis S5-D ok** (mit HU-S16 beantwortet die Entscheidungen-App jetzt wirklich) |
| `run_tests.py scheduler desk orchestra uix harness` | **1 395 Tests, 9 übersprungen, 0 rot**, 634 s |
| `run_tests.py uix harness --slow` (Browser-Bahn) | **612 Tests, 9 übersprungen, 0 rot**, 920 s (`known_red.txt` leer) |

Erster Lauf nach der Umsetzung auf `main`: 3 rot – zwei Tests erwarteten den alten eigenen Shell-Wechsel von Minimal (HU-S4), und die
node-Spec von `costs` lief ohne Laufzeit (`buendeln` fehlt dort) → `costs`/`live` fallen ohne `sedraLifecycle` auf den sofortigen Aufruf
zurück. Zweiter Lauf: 1 rot (`test_desk_kinds` verglich die 400 als ganzes Dict – HU-B12 fügt `code` hinzu; Test angepasst). Dritter Lauf: **0 rot**.

## 4. Entscheidungen des Captains – übernommen und gebaut (Captain 15:46: „so übernehmen und weiter“)

| Nr | Gebaut | Dateien / Tests |
|---|---|---|
| **E1** | Update-Übernahme ist ein Gate: die Vorschau legt den Antrag an (`update_apply`, Ziel `update:<tag>`, Bindung Tag + Manifest-Hash + Rechteliste, Risiken = Rechteänderungen); `POST /api/update/uebernehmen {mission_id}` ist das Apply (Einmal-Token, `_spend_approval`, geändertes Manifest → `file_changed_repeat_request`). Werkzeug System: „Freigeben und übernehmen“ über `shell.decide`; der alte Weg (`tag` + `rechte_schluessel`) geht nicht mehr. Herkunft S7 gilt auch hier. | `uix_server.py`, `desk/decisions.py`, `tools/system/*`; `UpdateGate` (2 Tests) |
| **E2** | `cloud/save` schreibt atomar mit Sicherung `.bak-<Zeit>`; eine geänderte `base_url` wird nicht geschrieben, sondern als Antrag `cloud_base_url_change` vorgelegt (Risiko: der Schlüssel geht an den neuen Host); Schalter/Modellwahl gelten sofort; `POST /api/cloud/base-url/apply` nach der Freigabe. Labor sagt es im Hinweis. | `cloud_settings.py`, `uix_server.py`, `desk/decisions.py`, `tools/labor/tool.js`; `CloudAdresseGate` (2 Tests) |
| **E3** | CSP `script-src 'self'` für Desk-, Rahmen- und Hardware-Seite: die Rahmenseite trägt das Manifest als `data-manifest` (`rahmen.js` startet bei `DOMContentLoaded`), die Hardware-Seite lädt `uix/js/hardware_dashboard.js`. Nur `/retro` (Archiv, `onclick`-Attribute) behält `'unsafe-inline'`; `style-src` bleibt vorerst mit `'unsafe-inline'`. | `uix_server.py`, `desk/gateway.py`, `ui/rahmen.js`, `hardware_manager/dashboard.html`, `uix/js/hardware_dashboard.js`; `test_e3_*`, `test_stufe_c_rahmen` (Browser), `test_uix_stufe6` 21/21 |
| **E4** | Vertrag §2 scharf: **N9 `ctx.einbetten(id, el, objekt)`** – ein Werkzeug bettet ein anderes nur über die Laufzeit ein (eigene Kennung, eigenes Gedächtnis, Abbau mit dem Einbettenden); GateWay→Schutz nutzt es, die Guard-Routen verschwinden aus dem GateWay-Manifest. `zitate.js` liegt in `ui/` (Gespräch, Fundstelle und Wissen nutzen es). **Prüfzugang:** `sedraBoot.ctx` und `sedra.tools/.shells` gibt es nur mit Schalter `entwicklung` oder `SEDRA_PRUEFZUGANG=1` (uix_check, host_isolation); im Betrieb fehlen sie, `sedraBoot.manifest` bleibt. Statischer Test: kein Werkzeug/keine Shell greift auf `sedra.tools/.shells`, `sedraBoot.ctx`, `sedraWechsel` (Werkzeuge), `sedraApi` zu. | `ui/loader.js`, `ui/lifecycle.js`, `ui/start.js`, `ui/zitate.js`, `desk/gateway.py`, `tools/gateway/nav.js`, `tools/gateway/tool.yaml`, `desk.html`, `benchmarks/uix_check.py`, `tests/host_isolation.py`; `VertragParagraf2` (3 Tests, darunter N9 mit node); Vertrags-Nachtrag 30.10. |

Prüfung nach E1–E4: `uix_check` Harness 43/43, Cockpit 41/41, Minimal 42/42, Paperclip 45/45; `--stufe4`/`--stufe5` ok; erster Gesamtlauf
2 rot (Spec-Dateien luden `zitate.js` noch aus dem Werkzeug; der Retro-Test zählte `hardware_dashboard.js` zur Archivseite) → angepasst; danach **1 407 Tests, 0 rot** (629 s) und Browser-Bahn **624 Tests, 0 rot** (887 s).

### 4.1 Die vier Punkte, wie sie vorgelegt wurden

| Nr | Befund | Vorschlag |
|---|---|---|
| **E1** | **`POST /api/update/uebernehmen` tauscht Programmdateien ohne Gate und ohne Einmal-Token** (`uix_server.py:816`, `update_anwenden.py`): `rechte_schluessel` ist ein deterministischer Hash über die Rechteliste (aus der Vorschau ablesbar) und bei einem Update ohne Rechteänderung leer – zwei POSTs mit dem Browser-Token reichen für einen Programmtausch. | Wie `install_request`/`install_apply`: die Vorschau legt ein Gate mit Bindung (Tag, Manifest-Hash, Rechte) an, `uebernehmen` prüft `guard.authorize` mit Einmal-Token. Betrifft den Update-Weg der Oberfläche (Build 20) – eigener kleiner Bau mit Test. **Empfehlung: ja.** |
| **E2** | **`cloud/save` schreibt `base_url` je Anbieter ohne Gate** (nur `https` geprüft) – der API-Schlüssel geht beim nächsten Start an diesen Host; `write_text` nicht atomar. D-U5 (Stufe 5) sagte „Cloud bleibt wie gebaut“. | Mindestens atomar + `.bak` (ohne Verhaltensänderung, baue ich bei Ja sofort); die Änderung von `base_url` zusätzlich als Antrag mit Gate wie Schalter. **Empfehlung: atomar ja; Gate für `base_url` ja.** |
| **E3** | **CSP mit `script-src 'unsafe-inline'`**: die Rahmenseite startet mit einem Inline-`<script>`, Desk-Seite ebenso; Vertrag §6 sagt „CSP bleibt self, kein Inline-Code“. Ein eingeschleuster String würde als Script laufen (heute durch HU-1/Markup-Regeln keiner bekannt). | Manifest als `data-manifest` auf `#werk`, `rahmen.js` liest es; Inline-Start der Desk-Seite in eine Datei; dann `'unsafe-inline'` aus `script-src` (Styles bleiben, bis die Shells keine `style=`-Attribute mehr brauchen). Eigener Bau mit `uix_check` aller Shells. **Empfehlung: ja, als nächste Runde.** |
| **E4** | **Querzugriffe am Vertrag vorbei:** (a) `window.sedra.tools/.shells` sind die lebenden Registrierungen – `gateway/nav.js` holt sich `schutz` darüber und mountet es selbst (mit HU-T1 jetzt sauber, aber Vertrag §2 verbietet Querimporte); (b) `window.sedraBoot.ctx` legt den ganzen Loader-Kontext (Seiten-API, Bus, `makeContext`) global ab – nur Tests lesen es; (c) `root.sedraWechsel.leeren/wechseln` stehen jedem CORE-Werkzeug offen; (d) `talk` nutzt `sedraWissenZitate` aus dem Werkzeug `wissen`. | (a) Einbettung über die Shell (eigener Container, `makeContext` von `schutz`) oder streichen; (b) nur `manifest` veröffentlichen, Tests auf die Shell-API umstellen; (c) Wechsel nur über `shell.open` bzw. ctx der Shell; (d) `zitate.js` nach `ui/`. Zusammen ein Bau „Vertrag §2 scharf“ mit Test „keine `root.sedra.tools.get` außerhalb `ui/`“. **Empfehlung: ja, nach E3.** |

## 5. Bewusst nicht geändert, aber notiert

- **Manifest-Zwischenspeicher** (`gateway._load`): jede Anfrage mit `X-SEDRA-*`, jede Moduldatei parst alle Manifeste neu – Leistung, kein Sicherheitsproblem; ein mtime-Cache wäre ein eigener kleiner Bau mit `tools.refresh`.
- **`desk.resync`** hören nur 8 Werkzeuge (N3 nimmt bestehende aus); die Vorlage `_template` macht es nicht vor – Kandidat für die nächste Vertrags-Nachtragsrunde.
- **Doppelungen zwischen Shells** (Klick-daneben-Menü in Cockpit/Minimal/Paperclip, Instrumente-Lesen in vier Shells) – Kandidaten für `ui/`, kein Fehler.
- **Gateway tauscht `ctx.object` intern** (neuer Vorgang, Übersicht) statt `shell.open` – die Shell weiß nichts vom Wechsel; funktioniert, aber am N5-Muster vorbei.
- Aus den Runden vom 14.10. unverändert: `/rebind ja` ohne Gate, 503-Texte mit Pfaden, kein `fsync` bei `boundaries.yaml`/`intents.yaml`.
