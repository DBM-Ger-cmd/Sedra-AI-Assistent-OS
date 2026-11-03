# Entwurf: Werkzeuge und Erweiterungen als Apps (03.11.2026)

Stand: `main` c364081. Nur Entwurf, nichts davon ist gebaut. Pfade unten sind relativ zu `runtime/src/guppi_runtime/` (`uix/…`, `desk/…`),
sofern nichts anderes steht. Zeilennummern gelten für c364081.

Idee des Captains: Werkzeuge und Erweiterungen sind einheitlich **Apps**, die über ein **Manifest** mit Kern und Shell reden. Vorbild ist **Android**: ein Kern, darauf aufsetzende Apps, Berechtigungen in Schutzstufen (§2.0).

## 0. Kurzfassung

1. Der Ansatz steht zu etwa drei Vierteln. `tool.yaml` gibt es, es wird geprüft, die API-Allowlist wird erzwungen, und **alles, was nicht
   `trust: CORE` ist, läuft schon heute in einem iframe mit `sandbox="allow-scripts"` hinter einer Nachrichtenbrücke**
   (`uix/ui/loader.js:151`, `uix/ui/bruecke.js`). Die Frage „iframe oder Worker?“ ist damit großenteils beantwortet: iframe gibt es.
2. Fest verdrahtet ist die **Oberfläche der Harness-Shell**: die Zellen der Taskleiste (`taskleiste.js:15`), die Orte (`places.js:14`,
   `chat_tools.py:108`) und die Start-Gruppen (`start_gruppen.json`). Diese Listen leben neben dem Manifest, nicht aus ihm.
3. Es fehlen im Manifest: Beitrag zur Leiste, Ort mit Wörtern, Rechte als benannte Fähigkeiten, Abhängigkeiten, Update-Weg.
4. Beim Lesen sind **fünf Lücken** aufgefallen, die vor jeder Öffnung für Fremde zu schließen sind (§3.5). Zwei davon sind klein und billig:
   die Rahmenseite hat dieselbe CSP wie die Shell (`connect-src 'self'`), und `uix/**` steht nicht unter den harten Vorbehalten
   der Harness (ein Modell mit Schreibbereich `runtime/**` könnte ein Werkzeug als „Paket“ ablegen, das dann `CORE` ist).
5. Reihenfolge: Stufe 0 (Lücken + Tests, kein Funktionsgewinn), 1 (Zellen aus `kind: instrument`), 2 (Ort/Gebiet aus dem Manifest),
   3 (serverseitige Erweiterungen wie MCP, nur außerhalb des Prozesses).

---

## 1. Ist-Stand

### 1.1 Was das Manifest heute leistet

`desk/gateway.py` prüft `tool.yaml` (`check_tool`) und `shell.yaml` (`check_shell`). Erlaubte Schlüssel eines Werkzeugs
(`desk/gateway.py:63`): `id name version handles kind entry api events trust tests needs description order slot instanzen gedaechtnis zweck gruppe`.
Unbekannte Schlüssel werden abgewiesen (`unknown_field`).

| Feld | Wirkung heute | Durchgesetzt wo |
|---|---|---|
| `id`, `version`, `needs.ui` | Kennung = Ordnername, SemVer, Vertragsversion `>=1.0 <2` | `gateway.py:_common`, `needs_ok` |
| `kind` (object/instrument/panel) | Art der Einbindung | Manifest; die Harness-Shell wertet `instrument` **nicht** aus (§1.2) |
| `handles` | welche Objekttypen das Werkzeug zeichnet (auch `typ:*`, `typ:<id>`, N1) | `ui/loader.js` `handlesMatch` |
| `api` | Allowlist `METHOD /pfad` (Präfix nur mit `/*` am Ende) | Server: `uix_server.py:3561` `_module_allowed` → 403 `tool_route_not_allowed`, Audit `UIX_TOOL_DENIED`; im Rahmen zusätzlich `ui/bruecke.js:29` `routeErlaubt` |
| `events.emits/listens` | Namen, Syntax geprüft; Strom-Ereignisse in `emits` verboten (`events_emits_reserved`) | `gateway.py` `EVENTS_NUR_STROM`; Bus; Brücke leitet nur `listens` weiter (`bruecke.js:91`) |
| `trust` | CORE / CAPTAIN / GUPPI_BUILT / COMMUNITY. CORE nur aus dem Paket (`local_module_cannot_be_core`, `gateway.py:115`); COMMUNITY verliert alle Nicht-GET-Routen (`gateway.py:137`) | `gateway.py`; Lader: `t.trust !== 'CORE'` → Rahmen (`loader.js:164`) |
| `gruppe` | Gruppe im Start-Menü (arbeit/modelle/wissen/system/pruefung), Vertrag Nachtrag N2 | `gateway.py:44`; Harness `startliste.js` |
| `zweck` | `betrieb` oder `pruefung` (Prüfwerkzeuge nur mit Schalter `entwicklung`) | `gateway.py` `manifest()` |
| `gedaechtnis` | `sitzung`/`ablage`: eigene Ablage je Werkzeug, getrennt nach Kopf `X-SEDRA-Tool` | `uix_server.py` `ablage_lesen/schreiben` |
| `slot`, `order`, `instanzen` | Platz (Fläche/Nachweis), Reihenfolge, Mehrfachinstanzen | Lader/Shell |
| `tests` | Browserabnahme | `benchmarks/uix_check.py` |

Lebenszyklus heute:
- **Entdecken:** `Registry.module_dirs` liest `uix/tools`, `uix/shells` und `local_config/{tools,shells}`; `GET /uix/manifest` liefert die geprüften Manifeste
  plus `rejected` mit Gründen. Abgewiesene Module verschwinden nicht still.
- **Laden:** CORE-Werkzeuge laden ihr Skript in die Seite; alle anderen bekommen einen Stellvertreter, der beim Öffnen einen iframe
  `/uix/frame/<id>` einhängt (`loader.js:145–160`). Die Rahmenseite wird ohne Token und ohne Daten ausgeliefert (`uix_server.py:3734`, `gateway.frame_page`).
- **Einbauen:** `install_request` → Gate `install_module` mit Datei-Hashes, Durchsicht-Funden (`desk/install.py:26` FLAGS: eval, fetch, innerHTML, window.parent …)
  und Routen → `install_apply` kopiert in `local_config/…`, prüft den Hash erneut, **setzt immer `trust: COMMUNITY`** (`uix_server.py:396`, `:462`).
- **Rechte erhöhen:** `trust_request` / `trust_apply` (`uix_server.py:1265ff`): Gate `grant_module_write_routes`, gebunden an den SHA-256 des Manifests; ändert sich das
  Manifest nach der Freigabe, wird nicht angewendet.
- **Entladen:** `disabled` in `uix.yaml`; `tools.refresh` im Ereignisstrom. Entfernen ist kein Gate, nur Audit (Vertrag §6).
- **Brücke:** Nachrichten `api` und `shell` (`open`, `notify`); `decide` wirft immer (`ui/rahmen.js:59`). Der Absender wird über `event.source` bestimmt, nicht über ein Feld
  der Nachricht (`bruecke.js:46`). `open({type:'shell'})` ist gesperrt (`bruecke.js:78`).
- **Desk:** Objekttypen und Verben werden in `desk/kinds.py` registriert, beim Start eingefroren; Verben laufen über `POST /api/actions` mit Gate (`desk/gated.py`); der Server setzt
  `client` aus dem Token (R4), externe Clients (`cli`, `mcp`) haben eigene Tokens, die **nur** `/api/objects` und `/api/actions` öffnen (R5).

### 1.2 Wo die Shell trotzdem fest verdrahtet ist

| Stelle | Was fest ist | Folge |
|---|---|---|
| `uix/shells/harness/taskleiste.js:15–16` `ZELLEN` | die sieben Zellen (Freigaben, Modell, GPU, RAM, Modellserver, Scheduler, Zustand) mit Beschriftung und Klick-Ziel | Eine neue Anzeige braucht eine Code-Änderung in der Shell. |
| `taskleiste.js:176–178` | Die Leiste liest `/api/strip` und filtert `ZELLEN` gegen die Antwort. Zusätzliche Schlüssel der Antwort (`tasks`, `cloud`, `mode`, `slots`, `wissen`) werden **ignoriert**. | Die Instrument-Manifeste (`uix/tools/gauge-*/tool.yaml`, `kind: instrument`) sind für die Harness-Shell tot. Wem sie dienen (vermutlich dem Cockpit), habe ich nicht geprüft. |
| `taskleiste.js:~185–195` | Sonderfälle je Schlüssel: `decisions` (Freigabe-Zelle), `model`/`server` (Modell-Menü), `state` (Einstellungen), dazu die Token-Zelle (`tokenZelle`, per `splice` an Position 2) | Verhalten hängt am Schlüsselnamen, nicht am Manifest. |
| `uix_server.py:1747` `strip_view` | Die Zellen kommen aus einem festen Dict, jede aus einer eigenen Servermethode (`_gpu_zelle`, `_ram_zelle` …) | Auch serverseitig ist die Liste Code. |
| `uix/tools/gauge-*/tool.js` | `summary()` liefert nur einen Platzhalter (`value: null`), z. B. `gauge-gpu/tool.js:36` | Das Instrumentenvertrags-`summary()` aus Vertrag §4 ist nicht angeschlossen. |
| `uix/ui/places.js:14` `PLACES` | Orte mit Wörtern und Objekt – von Shells, Palette und Gespräch benutzt | Ein Werkzeug kann keinen Ort mitbringen. |
| `chat_tools.py:108` `PLACES` | Zweite Liste (Chat, `app_oeffnen`), ein Test vergleicht beide | Zwei Wahrheiten, ein Test hält sie zusammen. |
| `harness/werkzeuge.py:49–54` `ORTE` | liest `chat_tools.PLACES`; `app_oeffnen` (Zeile 420) öffnet nur diese | Das Modell kann nur feste Orte öffnen (das ist als Sicherung gut, §2.4). |
| `uix/shells/harness/start_gruppen.json` | Ort-ID → Gruppe | `gruppe` im Manifest gewinnt zwar, aber nur für Werkzeuge, die schon einen Ort haben. |
| `uix/shells/harness/einstellungen.js:24` | Seite „Integrationen“: MCP, GateWay, Cloud als feste Punkte | Eine neue Erweiterung hat dort keinen Platz. |
| `desk/gateway.py:68` `FRAME_API` | die Routen der „Shell aus Vorgabe“ | bewusst Vertragscode, kein Befund |
| `uix/shells/harness/app.js` `S._apps` | Zustand der offenen Apps (max. 8) wohnt in der Shell | in Ordnung, ist Shell-Zustand |

Zwischenbefund: **Das Manifest beschreibt, was ein Werkzeug *darf*, aber nicht, was es der Oberfläche *beiträgt*.** Der Beitrag steht in drei Shell-Dateien.

---

## 2. Zielbild

### 2.0 Vorbild Android: ein Kern, darauf aufsetzende Apps

Leitbild (Captain, 03.11.2026): SEDRA verhält sich wie Android. Es gibt einen kleinen, geschützten **Kern**; alles andere sind **Apps**, die nur über definierte Schnittstellen und
mit **gewährten Berechtigungen** auf den Kern zugreifen. Die Abbildung zeigt, was SEDRA schon hat und was fehlt:

| Android | SEDRA | Stand |
|---|---|---|
| Linux-Kernel + Systemdienste (nicht austauschbar) | Kern: Guard, Audit, Missionen, Inhaltsschutz, Desk (§2.6) | vorhanden |
| App-Sandbox (eigene UID je App) | iframe `sandbox="allow-scripts"`, Opaque Origin, kein Token (`loader.js:151`) | vorhanden, nur für Nicht-CORE |
| `AndroidManifest.xml` | `tool.yaml` | vorhanden, Schlüssel fehlen (§2.2) |
| Systemapps (in der Firmware) | `trust: CORE`, nur aus dem Paket | vorhanden; läuft aber **in** der Seite, nicht abgeschottet (L1) |
| Nutzer-Apps aus dem Store | `COMMUNITY` / `CAPTAIN` / `GUPPI_BUILT` in `local_config/` | vorhanden |
| `<uses-permission>` im Manifest | `rechte:` (§2.3, §5) | fehlt, heute nur Routenlisten |
| Schutzstufen `normal` / `dangerous` / `signature` | Stufen A / B / C (unten) | fehlt |
| Laufzeit-Dialog „App möchte …“ | Antrag mit Gate im Posteingang | Muster vorhanden (`trust_request`) |
| Intents / Binder (App ruft Dienst über den Kern) | Desk: `POST /api/objects`, `POST /api/actions` (Verben mit Gate) | vorhanden |
| ContentProvider (Daten einer App für andere) | eigene Objekttypen (`handles`) mit Lese-Fähigkeit | teilweise |
| Broadcasts mit Berechtigung | Ereignisbus, `listens` nach Klassen (B4) | Klassen fehlen |
| Hintergrunddienste | Dienst-Apps außerhalb des Prozesses (B5, Stufe 3) | fehlt |
| Paketsignatur, Installer-Prüfung (Play Protect) | Hashes im Gate, `herkunft` | Hashes ja, Signatur und Ladeprüfung fehlen (L1) |
| Einstellungen → Apps → Berechtigungen | Karte „Berechtigung“ im Modul-Werkzeug | fehlt |
| Nur der Kern ist root | nur der Kern gibt Tokens und Freigaben aus | vorhanden |

**Schutzstufen der Berechtigungen** (wie bei Android; die Stufe legt der Kern fest, nicht die App):

| Stufe | Wie bei Android | Beispiele | Vergabe |
|---|---|---|---|
| **A normal** | `normal` | lesen eigener Typen, eigene Ablage, Ereignisse der Klasse `öffentlich`, Ort im Start-Menü | mit dem Einbau gewährt; im Gate sichtbar, kein eigener Klick |
| **B gefährlich** | `dangerous` | Zelle in der Leiste, Ereignisse der Klasse `inhalt`, Verben mit Gate, Netz über den Server, Lesen fremder Typen | nur auf Antrag: eigenes Gate, im Klartext, jederzeit entziehbar |
| **C Kern** | `signature` | Guard, Audit, Freigabe, Tokenvergabe, Einbau-Gate, Schreiben in `uix/**` | nie an Apps; nur Paket-Code (CORE) im Kern |

Folgerungen für den Plan:
- **Systemapps sollten ebenfalls abgeschottet laufen**, soweit möglich (Android lässt Systemapps trotzdem in eigenen Prozessen laufen). Heute laufen CORE-Werkzeuge in der Seite; ein
  Ziel für später: auch sie hinter der Brücke, damit „CORE“ nicht „hat den Token“ heißt. Das ist teuer (Zeichnen, `ctx.einbetten`, Tests) und kein Teil von Stufe 0 bis 3.
- **Kein App-Store** (kein Katalog, keine Bewertungen). Die Quelle ist ein Ordner oder Git-Klon mit Commit-ID; „Signatur“ ist vorerst der Hash im Gate.
- **Kein „alles erlauben“** (Android kennt das Muster „Berechtigung einmal pauschal“ nicht; hier auch nicht): jede Fähigkeit einzeln.

### 2.1 Begriff

Eine **App** ist ein Werkzeug (`uix/tools/<id>`) oder eine Erweiterung mit einem Manifest. Sie hat bis zu drei Beiträge, alle im Manifest deklariert:
**Fläche** (ein Fenster im Reiter), **Zelle** (ein Eintrag der Taskleiste), **Ort** (Name, Wörter und Gebiet im Start-Menü/Palette/Chat). Eine App kann
auch nur eine Zelle haben oder nur einen Dienst (ohne Oberfläche, §2.4).

Das Manifest bleibt `tool.yaml`. Es wird nicht umbenannt (viele Tests und Dokumente hängen daran); `kind: app` ist unnötig, `kind` bleibt object/instrument/panel.

### 2.2 Fehlende Felder (Vorschlag, alle optional, Version `needs.ui >=1.1`)

```yaml
tool:
  id: rechnung
  name: "Rechnungen"
  version: 1.2.0
  kind: object
  # --- neu ---------------------------------------------------------------
  gebiet: arbeit                     # = bestehendes Feld `gruppe`; Name bleibt `gruppe` (kein zweites Feld!)
  ort:                               # Beitrag zu Start-Menü, Palette, Chat (ersetzt den Eintrag in places.js / chat_tools.PLACES)
    id: rechnung                     # [a-z0-9-]{2,40}, global eindeutig, Kernorte haben Vorrang
    label: "Rechnungen"
    hint: "Rechnungen prüfen und ablegen"
    symbol: "▤"                      # ein Zeichen aus fester Menge, kein Bild von außen
    words: [rechnung, rechnungen]    # Kernwörter sind gesperrt (Kollision → Modul abgewiesen)
    object: {type: rechnung, id: alle}
  zelle:                             # Beitrag zur Taskleiste; nur bei kind: instrument oder zusätzlich zu einer Fläche
    key: rechnungen-offen
    label: "Rechnungen"
    ort: rechnung                    # Klickziel: ein Ort (nie ein Skript der App)
    quelle: {api: "GET /api/rechnung/zelle"}   # liefert {value, hint, tone}; tone ∈ ok|warn|off, value ≤ 24 Zeichen
    order: 40
  rechte:                            # benannte Fähigkeiten statt freier Routen (§2.3)
    - lesen:rechnung
    - ereignis:system.state
  needs:
    ui: ">=1.1 <2"
    apps: {gateway: ">=1.0 <2"}      # Abhängigkeiten von anderen Apps; fehlt eine, wird die App nicht geladen, mit Grund
  herkunft:                          # Lieferkette (§3.6), vom Gate gesetzt, nicht vom Autor
    quelle: "git+https://…@<commit>"
    sha256: {tool.js: "…", tool.css: "…"}
```

Regeln dazu:
- **`gruppe` existiert schon** (Nachtrag N2). Es wird nur nicht „Gebiet“ genannt. Kein Synonym einführen; im Start-Menü steht weiter „Gruppe“.
- **`ort`** ersetzt die Parallelwahrheit: Kernorte bleiben in `places.js`, die Liste der Shell ist `Kernorte + Orte aus Manifesten`. `chat_tools.PLACES` und
  `harness/werkzeuge.py:ORTE` lesen dieselbe Zusammensetzung (aus dem Desk), der heutige Gleichheitstest wird ein Test gegen das Manifest.
- **`zelle`** zeigt **Daten, nie Code**: Die Shell zeichnet `label`, `value`, `tone` selbst. Die App liefert Zahlen/Kurztext über eine Leseroute (oder die Brücke, §3.4),
  Länge begrenzt, Steuerzeichen entfernt. Eine fremde Zelle trägt ein festes Kennzeichen („fremd“), damit sie nicht wie eine Kernzelle aussieht.
- **`needs.apps`** und **`version`** sind schon im Schlüsselsatz angelegt (`version`, `needs`), aber nur `needs.ui` wird ausgewertet.
- **`herkunft`** schreibt der Einbau, nicht der Autor (der Autor kann sie nicht fälschen, weil das Gate sie erzeugt).

### 2.2a Apps je Shell (Captain, 03.11.2026)

Shells dürfen **eigene Apps** mitbringen. Eine App muss nicht in jeder Shell verfügbar sein. Android-Vergleich: Hersteller-Oberfläche mit eigenen Apps neben den gemeinsamen.

Heute gibt es dafür keinen Platz: `TOOL_KEYS` (`desk/gateway.py:63`) kennt kein Feld für die Shell, Orte gelten „in jeder Shell“ (Vertrag, Nachtrag Orte G2-S4-21), und `uix/tools/` ist ein gemeinsamer Ordner. Werkzeuge mit `handles` zeigt jede Shell, die `dock` oder `windows` anbietet (`OPENS_OBJECTS`).

Vorschlag, zwei Wege, ein Mechanismus:

```yaml
tool:
  id: rechnung
  shells: [harness, cockpit]     # Verfügbarkeit; fehlt das Feld = alle Shells (heutiges Verhalten, keine Migration)
```
- **Gemeinsame Apps** bleiben in `uix/tools/<id>/`. `shells:` begrenzt, in welchen Shells sie erscheinen (Start-Menü, Palette, Chat-Ort, Leiste).
- **Shell-eigene Apps** liegen in `uix/shells/<shell>/apps/<id>/tool.yaml`. Sie gelten **nur** in dieser Shell; `shells:` ist dort implizit `[<shell>]` und darf nicht erweitert werden.
  Wird die Shell gewechselt, verschwinden Zellen, Orte und Reiter dieser Apps; offene Reiter gehen im Arbeitsstand mit der Shell zurück in den Zustand „App nicht verfügbar“ (kein stiller Verlust, ein Hinweis).
- Eine Shell darf Apps nur **anbieten und anordnen** (Zeichnen von Zellen, Gruppen, Orte). Sie darf einer App keine Rechte geben, die diese nicht hat (§2.3, §5). Eine Shell-eigene App steht in der Berechtigung wie jede andere.

Regeln und Sicherheit:
1. **Vertrauen folgt dem Ursprung, nicht der Shell.** Liegt eine App im Paket (`uix/shells/<shell>/apps/`), ist sie `CORE`/Paket; kommt sie über das Einbau-Gate, ist sie `COMMUNITY`, auch wenn sie für eine Shell gebaut wurde. Eine Shell-Datei aus `local_config/shells/<id>/` kann kein CORE bringen (`local_module_cannot_be_core`).
2. **Die Verfügbarkeit ist eine Sichtbarkeit, keine Sperre.** Der Server beantwortet die Routen einer App unabhängig von der aktiven Shell; die Allowlist (`api`) bleibt die einzige Grenze. Eine App, die in keiner aktiven Shell erscheint, ist trotzdem „eingebaut“ und kann nicht still starten (B1 Aktivierung).
3. **Kein Umweg über die Shell.** Eine Shell kann keine fremde App an der Aktivierung vorbei starten, und `app_oeffnen` (Modell) öffnet nur Apps, die in der **aktiven** Shell verfügbar **und** aktiviert sind. Sonst könnte eine Shell als Hintertür für COMMUNITY-Apps dienen.
4. **Zusammensetzung statt Kopie.** Orte, Zellen und Gruppen einer Shell = Kernorte + gemeinsame Apps mit passender `shells:` + eigene Apps der Shell (Stufe 2). Kollisionsprüfung gilt je Shell; ein Ort darf in zwei Shells verschieden belegt sein.
5. **Shells ohne Slot** (z. B. Minimal ohne `dock`) zeigen keine Flächen-Apps; Prüfung bleibt `OPENS_OBJECTS`. Das Manifest einer App kann `shells:` nennen, die den Slot nicht haben: Warnung im Modul-Werkzeug, kein Fehler.
6. **Wechsel der Shell bleibt Vertragscode** (`sedraWechsel`, Nachtrag N3): eine Shell baut keinen eigenen Wechsel; offene Apps gehen mit, soweit sie in der Ziel-Shell verfügbar sind.

Auswirkung auf den Plan: Stufe 2 bekommt `shells:` und den Ordner `apps/` (Lader liest beide Orte; ohne Feld = alle). Stufe 1 (Zellen) gilt zunächst nur für die Harness-Shell. Die Tests (`handles`-Zuordnung, `start_gruppen`) prüfen je Shell.

### 2.3 Rechte statt Routen

Heute sind „Rechte“ eine Liste von Routen. Das ist für Menschen schwer zu lesen („`POST /api/actions` darf *alles*“, Verben stehen im Body, die Allowlist sieht sie nicht).
Ziel: das Manifest nennt **Fähigkeiten**, das Gate zeigt sie im Klartext, der Server leitet die Routen daraus ab.

| Fähigkeit | Wirkung | Standard |
|---|---|---|
| `lesen:<typ>` | `POST /api/objects` nur für diesen Typ | nur eigene Typen |
| `verb:<typ>.<verb>` | `POST /api/actions` nur für dieses Verb; das Verb behält sein eigenes Gate | nie vorab |
| `ereignis:<name>` | darf dieses Ereignis hören (nicht senden) | nur „öffentliche“ Ereignisse (§3.4) |
| `zelle`, `ort` | Beitrag zu Leiste / Start-Menü | ja, aber sichtbar „fremd“ |
| `ablage` | eigene Ablage (`gedaechtnis`) | ja, Größe begrenzt |
| `netz:<host>` | Server-Seite holt für die App von diesem Host (nie die App selbst) | nein |

Antrag: **jede** Erweiterung der Rechte (auch bei einem Update) ist ein neues Gate im Posteingang, gebunden an den Hash des Manifests (Muster `trust_request`,
`uix_server.py:1265`: Änderung nach der Freigabe → „manifest_changed_since_the_request“). Entzug braucht kein Gate.

### 2.4 Lebenszyklus

| Phase | Heute | Ziel |
|---|---|---|
| Entdecken | Ordner scannen, Manifest prüfen | gleich; zusätzlich Kollisionen (`ort.id`, `ort.words`, `zelle.key`) prüfen und mit Grund in `rejected` zeigen |
| Anzeigen | Modul-Werkzeug „Module“ | zeigt je App: Herkunft, Vertrauensstufe, Rechte, Beiträge, Zustand (aktiv/aus/abgewiesen) |
| Aktivieren | mit dem Einbau ist es geladen | **Einbauen ≠ Aktivieren.** COMMUNITY-Apps sind nach dem Gate „eingebaut, aus“; Aktivieren ist ein Klick des Captains (Audit). So kann ein Gate-Klick nicht gleichzeitig fremden Code starten. |
| Laden | Rahmen beim Öffnen | gleich; Zellen-Apps laden erst, wenn die Leiste sichtbar ist und die App aktiv ist |
| Aktualisieren | nicht vorgesehen (`id` schon vergeben → Fehler, `uix_server.py:406`) | `install_request` mit gleicher `id` = Update: Gate zeigt Diff der Dateien und der Rechte; neues Recht = zusätzliche Zeile im Gate; App bleibt bis zur Freigabe in der alten Fassung |
| Entladen | `disabled` + `tools.refresh` | zusätzlich: Brücke meldet den Rahmen ab (`bruecke.abmelden`), Zelle verschwindet, offene Reiter schließen mit Hinweis |
| Entfernen | ohne Gate, Audit | bleibt ohne Gate (Entzug ist sicher); Ablage der App wird beim Entfernen gefragt |

### 2.5 Kommunikation

- **Ereignisse:** Apps *hören* nach `events.listens`; *senden* dürfen nur Apps im Paket (`emits`), und nur nicht-reservierte Namen. Für Rahmen ist `emit` heute ein
  No-op (`rahmen.js:49`): das Feld `emits` ist bei Nicht-CORE-Apps wirkungslos. Entweder aus dem Manifest für sie streichen (ehrlich) oder über die Brücke mit
  eigenem Namensraum `app.<id>.*` und Nutzlast-Schema ermöglichen (nur auf Antrag).
- **Verben:** Eine App löst Handlungen **nur** über Desk-Verben aus (`POST /api/actions`), nie über eigene Schreibrouten am Kern vorbei. Jedes Verb hat sein Gate und
  sein Audit; die App ist dabei nur Antragsteller.
- **Objekte:** Eine App bringt eigene Objekttypen mit (`handles`, schon möglich für lokale Module, `gateway.py:122`) – lesend. Schreiben wieder nur über Verben.
- **Bridge-Verben** (Vorschlag, klein): `zelle.setze({value, hint, tone})` für Apps ohne Leseroute; `ort.oeffne` bleibt `shell.open` (heute `open`/`notify`, `bruecke.js:12`).

### 2.6 Was **niemals** eine App sein darf

Diese Teile bleiben Kern oder Vertragscode. Eine App darf sie weder ersetzen noch ergänzen noch ihre Entscheidung abnehmen. Ein Manifest, das das behauptet, wird abgewiesen.

| Bereich | Warum | Wo |
|---|---|---|
| **Guard** (Regeln, Einmal-Token, Bindung an Auftrags-Digest) | einzige Stelle, die Freigaben ausgibt | `core/guard.py`, `architecture/…/guard_rules.yaml` |
| **Audit** (Hash-Kette, `.head`-Anker) | eine App darf nicht schreiben, was ihr Wirken belegt | `core/audit.py` |
| **Freigabe/Entscheiden** | `decide` über die Brücke gibt es nie (`rahmen.js:59`); auch keine Karten-Oberfläche in einer App, die wie eine Freigabe aussieht | `harness/freigabe.py`, `harness/vorbehalte.py`, `desk/decisions.py` |
| **Inhaltsschutz** (Eingang/Ausgang zu Modellen) | wäre eine App der Schutz, könnte sie ihn auslassen | `core/content_guard.py`, `content_policy.py` |
| **Permission-Stufen, Vorbehalte, Freigabe-Katalog** | nur „öfter Nein sagen“ ist erlaubt | `core/permission_levels.py`, `harness/vorbehalte.py` |
| **Vertrauensvergabe und Einbau-Gate** | sonst stuft sich eine App selbst hoch | `uix_server.py` `install_*`, `trust_*` |
| **Manifestprüfung, Lader, Brücke, Rahmen** | Vertragscode (`desk/gateway.py`, `uix/ui/*`) | Paket |
| **Client-Tokens** (cli/mcp) | wer Tokens ausgibt, ist der Kern | `uix_clients.py` |
| **`local_config/`, Schalter, Schreibrechte des Projekts** | Captain-Hoheit | Vorbehalt `**/local_config/**` |

Folgerung: Apps sind **Antragsteller und Anzeiger**. Sie dürfen lesen, anzeigen, vorschlagen und Verben beantragen; entscheiden, schützen und protokollieren tut der Kern.

---

## 3. Sicherheit

### 3.1 Wer ist der Angreifer?

`trust: COMMUNITY` – ein Modul von außen (Download, Git-Klon, vom Modell vorgeschlagen). Zusätzlich zwei Fälle, die gern vergessen werden:
(a) ein Modell, das über seinen Schreibbereich Dateien ablegt (Prompt-Injektion), (b) ein Modul, das nach dem Gate nachträglich verändert wird.

### 3.2 Was die Sandbox schon leistet (und was nicht)

`<iframe sandbox="allow-scripts">` ohne `allow-same-origin` gibt dem Dokument einen **undurchsichtigen Ursprung**: kein Zugriff auf DOM, `localStorage`, Cookies der Shell; kein
`window.top`-Zugriff; keine Formulare, Pop-ups, Top-Navigation. Der Rahmen bekommt **keinen Token** (`frame_page` liefert ihn nicht), spricht nur per `postMessage`; der Kern ordnet
über `event.source` zu und prüft Allowlist und Nachrichtenform. Das ist echte Isolation durch den Browser, nicht nur ein Etikett.

Für **CORE-Apps** gilt dagegen: sie laufen *in* der Seite mit Token. Dort ist das Manifest tatsächlich nur ein Etikett; die Allowlist (Header `X-SEDRA-Tool`) setzt der eigene
Code der Seite (`api.js:21`) – ein CORE-Werkzeug könnte den Header weglassen. Geschützt ist das nur durch Review, `uix_check` (kein `fetch`, kein `localStorage`) und die Regel, dass
CORE nur aus dem Paket kommt. **Wer CORE schreiben kann, hat den Token.** (→ Lücke L1.)

Was der Rahmen **nicht** leistet: kein CPU-/Speicherlimit (eine Endlosschleife im Rahmen belastet den Browser), keine Garantie gegen Seitenkanäle zwischen Prozessen im Browser,
kein Schutz davor, dass die App dem Captain etwas **vorspielt** (§3.3 Nr. 6).

### 3.3 Bedrohungsmodell

| Nr | Bedrohung | Stand | Gegenmaßnahme |
|---|---|---|---|
| 1 | **Umweg am Guard vorbei** (direkter Schreibweg am Kern) | Nicht-CORE: nur Brücke → Allowlist → Server; COMMUNITY nur GET. Aber: `POST /api/actions` als eine einzige Route gibt dem Server die Verben nicht zu sehen; Schutz liegt im Verb-Gate. | Rechte als `verb:`-Fähigkeiten (§2.3); der Server prüft Verb gegen die Fähigkeiten der App, nicht nur die Route. Jedes Verb behält sein Gate; kein Verb ohne Gate für App-Herkunft. |
| 2 | **Gleiche Browser-Origin wie die Shell** | Nicht-CORE: gelöst durch Opaque Origin. CORE: gleiche Origin, gewollt. | Nie `allow-same-origin` für Rahmen (Test, der das Attribut fest vorschreibt). Im Betrieb keine CORE-Apps aus `local_config`. |
| 3 | **Manifest als bloßes Etikett** | Bei CORE ja (§3.2); bei Rahmen durch die Brücke durchgesetzt. Ausnahmen: `emits` wirkungslos; `needs.apps` fehlt; die Install-Durchsicht (FLAGS) ist nur ein Hinweis für den Captain, kein Schutz (Regex umgehbar). | Schutz nie auf FLAGS stützen (dort steht es schon „Hinweis“). Neue Felder nur mit Durchsetzung oder gar nicht ins Schema aufnehmen. |
| 4 | **API-Allowlist zu weit** | `ROUTE` erlaubt `GET /api/*` (`gateway.py:59`: `(/(api|uix)(/…)*(/\*)?)`). Ein COMMUNITY-Manifest mit `GET /api/*` darf **jede** Leseroute rufen, die der Browser-Token öffnet (Sitzungen, Karten, Audit). Das Gate zeigt „nur Leserouten (N)“ und listet die Routen, aber eine Warnung vor Weite fehlt. | L2: Für nicht-CORE nur Pfade mit mindestens `/api/<bereich>/<name>`; `*` nur unterhalb eines Bereichs der App; breite Muster = rotes Gate; Liste der **sensiblen Leseroutes** (Sitzungsinhalt, Karten, Audit, Dateien) als „nie für Fremde“. |
| 5 | **Ereignisse als Seitenkanal** | Die Brücke reicht `listens`-Ereignisse mit **voller Nutzlast** weiter (`bruecke.js:93`). Inhaltstragend: `decision.pending` (`describe` kann Pfade und Befehle enthalten), `live.line` (Zeilen der Ausgabe), `talk.context`, `object.open`. `gateway.py` prüft nur die Syntax der Namen, nicht, wer was hören darf. Der Inhaltsschutz sitzt am Modell-Ein-/Ausgang, **nicht am Bus**. | L3: Ereignisse in zwei Klassen. **Öffentlich:** `system.state`, `model.changed`, `desk.resync`, `tools.refresh`, `slot.changed`. **Inhaltstragend:** alle anderen. COMMUNITY darf nur öffentliche hören; inhaltstragende nur mit Fähigkeit und mit **Nutzlast-Filter** (Schlüssel-Whitelist je Ereignis, `describe`/`line` nie). Filter in der Brücke, nicht in der App. |
| 6 | **Vortäuschen** (UI-Spoofing) | Eine App zeichnet in ihrem Rahmen beliebig, etwa eine Karte, die wie eine Freigabe aussieht; `shell.notify(text, ton)` setzt Text in die Hinweiszeile der Shell (`shell.js:58`, `hinweis`). Freigeben geht zwar nur im Kern, aber der Captain muss das erkennen. | L4: Rahmen mit festem sichtbaren Rand/Beschriftung „fremde App · <id>“, den die Shell außerhalb des Rahmens zeichnet. `notify` für Fremde mit Präfix „<id>:“, Länge begrenzt, Ton nur `note`, keine Blink-/Benachrichtigung. Nie Freigabe-Elemente in einem Rahmen. |
| 7 | **Rahmenseite hat Netz** | Die Rahmenseite bekommt die CSP der Shell: `connect-src 'self'` (`uix_server.py:3686–3687`, nur `frame-ancestors` ist anders, `:3743`). Sie braucht das nicht (alles läuft per `postMessage`). Mit `'self'` kann der Rahmen den Server **ohne Token** abfragen (alle Routen, die vor der Token-Prüfung antworten, etwa Dateien unter `/uix/`) und erzeugt Last. | L5: Rahmenseite mit eigener CSP: `default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data: blob:; connect-src 'none'; form-action 'none'; frame-src 'none'; base-uri 'none'`. Beweis per Test: `fetch('/api/strip')` im Rahmen scheitert. |
| 8 | **Lieferkette** | Gate zeigt Hashes, `install_apply` prüft sie erneut beim Kopieren (`uix_server.py:459`). **Offen:** (a) kein Prüfen beim *Laden* (wer `local_config/tools/<id>/tool.js` später ändert, wird nicht bemerkt); (b) kein Update-Weg, also kein Diff; (c) keine Signatur, keine Pin-Pflicht für Bibliotheken (`fremde Adresse` wird als Fund gemeldet, nicht verboten); (d) **das Modell kann Pakete schreiben:** `vorbehalte.py` sperrt `core/**`, `harness/*.py`, `local_config/**`, aber **nicht** `uix/tools/**`, `uix/ui/**`, `uix/shells/**`, `desk/gateway.py`, `uix_server.py`. Mit Schreibbereich `runtime/**` kann ein Modell (nach einer normalen Karte, deren Diff harmlos aussieht) ein Werkzeug mit `trust: CORE` ablegen. | L1: Vorbehalt auf `uix/ui/**`, `uix/tools/**`, `uix/shells/**`, `desk/gateway.py`, `desk/install.py`, `uix_server.py` (harte Karte, wie Guard). Hashliste beim Laden prüfen (`herkunft.sha256`, Abweichung → App aus, Audit). Updates über das Gate mit Datei-Diff. Pin-Pflicht: Bibliotheken mitliefern mit Hash; Netz-Fund in Dateien = Ablehnung statt Hinweis. |
| 9 | **Gate-Text sagt Falsches** | `uix_server.py:415`: „fremder Code läuft danach in derselben Seite wie die Shell“ – seit Stufe C falsch (Rahmen). Ein zu großes Risiko im Gate stumpft ab, ein falsches verwirrt. | Text auf den Stand bringen: „läuft abgeschottet im Rahmen, ohne Token; Rechte: …“. Ehrlich bleiben: was *nicht* geschützt ist (CPU). |
| 10 | **Selbstaktivierung** | Nach dem Gate ist ein Modul sofort geladen. | „Eingebaut, aus“ + Aktivieren durch den Captain (§2.4). |
| 11 | **Namenskollision/Kapern** | Ein Ort mit Wörtern des Kerns („freigabe“, „logbuch“) würde Navigation umlenken, und `app_oeffnen` des Modells könnte fremde Orte öffnen. | Kernwörter reserviert; Kollision = Abweisung; `app_oeffnen` nur für Kernorte **oder** aktivierte Apps, und Öffnen ist nie ein Start im Hintergrund. |

### 3.4 iframe-sandbox oder Worker mit Nachrichtenbrücke?

| | iframe `sandbox="allow-scripts"` + Brücke | Web Worker + Brücke |
|---|---|---|
| Isolation vom Token/DOM der Shell | ja (Opaque Origin) | Worker aus der Shell-Origin laufen **same-origin**; ohne DOM, aber mit `fetch` auf dieselbe Origin. Der Token liegt nicht im Worker, aber Isolation hängt dann an CSP/Disziplin statt an der Origin. Ein Worker aus `blob:`/`data:` erbt die Origin der Seite. |
| Oberfläche zeichnen | ja | nein (nur Daten) |
| Beitrag zur Zelle ohne Fläche | ja (unsichtbarer Rahmen) | ja, kleiner |
| UI-Spoofing | möglich (Fläche), eindämmbar durch Rand | nicht möglich |
| Aufwand | **vorhanden** (`loader.js`, `bruecke.js`, `rahmen.js`, 4 Testdateien) | neu: zweiter Mechanismus, zweite Brücke, zweite Testreihe |
| CPU-Schutz | keiner | `terminate()` möglich, aber kein Limit vorab |

**Empfehlung:** Beim iframe bleiben, **einen** Mechanismus. Für Apps, die nur eine Zelle liefern, genügt ein unsichtbarer Rahmen (oder, besser, die Leseroute aus §2.2: kein Code im Browser).
Ein Worker lohnt sich nur, wenn später ein Fall auftaucht, der *ohne* Fläche und *mit* mehr Rechenaufwand läuft; dann als zweiter Typ `kind: dienst`, nicht jetzt.
Kosten der Härtung des vorhandenen Wegs sind gering: CSP der Rahmenseite (L5), Rand (L4), Ereignisfilter (L3), Test für das Sandbox-Attribut.

Einschränkungen, die ehrlich im Dokument stehen sollen: Sandbox begrenzt weder CPU noch Speicher; sie ersetzt keine Durchsicht; und sie hilft nur, solange der Captain
einer App keine Schreibfähigkeit gibt, die selbst gefährlich ist (die App muss den Kern nicht umgehen, wenn er ihr das Schreiben erlaubt).

### 3.5 Lücken, die vor jeder Öffnung für Fremde zu schließen sind

| Nr | Lücke | Aufwand | Wirkung |
|---|---|---|---|
| L1 | `uix/**`, `desk/gateway.py`, `desk/install.py`, `uix_server.py` nicht unter den harten Vorbehalten; Hashes nicht beim Laden geprüft | klein (Liste in `vorbehalte.py` + Ladeprüfung) | verhindert „Modell schreibt CORE-Werkzeug“ und stille Änderung nach dem Gate |
| L2 | Allowlist-Muster `GET /api/*` für COMMUNITY möglich; Liste sensibler Leseroutes fehlt | klein (Prüfung in `check_tool` + Test) | begrenzt, was ein Fremder lesen darf |
| L3 | Ereignisse: volle Nutzlast an jeden Hörer | mittel (Klassen + Filter in `bruecke.js`) | schließt den Seitenkanal |
| L4 | Kein sichtbares Fremd-Kennzeichen am Rahmen; `notify` ungefiltert | klein | gegen Vortäuschen |
| L5 | CSP der Rahmenseite gleich der Shell (`connect-src 'self'`) | klein (`frame_self` bekommt eigene Kopfzeile) | Rahmen kann den Server nicht ohne Brücke anfragen |

Zusätzlich offen und nur zu prüfen (ich habe es beim Lesen nicht festgestellt): ob der Server `Origin: null` aus dem Rahmen ausdrücklich ablehnt und ob es einen Test gibt, der
beweist, dass ein Rahmen-Skript `fetch` ohne Token nicht durchbringt. Die vorhandenen Tests (`test_stufe_c_rahmen.py`, `test_stufe_c_bruecke.py`, `test_uix_frame.py`) wurden hier nicht gelesen.

### 3.6 Rechte nur über Antrag mit Gate

Der Weg existiert schon in Teilen und wird nur verallgemeinert:

1. Einbau: Gate `install_module` (Hashes, Routen, Funde). Ergebnis: **eingebaut, aus, ohne Rechte außer „lesen eigene Typen“**.
2. Aktivieren: Klick des Captains, Audit `UIX_MODULE_ACTIVATED`.
3. Mehr Rechte (Verb, Ereignis, Schreiben): `trust_request`-Muster – Gate zeigt **genau** die neuen Fähigkeiten im Klartext, gebunden an den Manifest-Hash; geändertes Manifest → Ablehnung beim Anwenden.
4. Update: Gate mit Datei-Diff; neue Rechte nur mit eigener Zeile; bei Ablehnung bleibt die alte Fassung.
5. Entzug und Entfernen: ohne Gate, mit Audit.
6. Das Modell darf **beantragen** (Posteingang), aber weder freigeben noch aktivieren. `app_oeffnen` öffnet nur Kernorte und aktivierte Apps.

Das Gate selbst bleibt Kern (§2.6). Die Karte im Posteingang wird vom Kern gezeichnet, nie von einer App.

---

## 4. Umsetzungsplan

Jede Stufe ist einzeln freigebbar, hat einen Rückfall und lässt die vorherige unverändert. Keine Stufe ändert Guard, Audit, Freigabe oder Inhaltsschutz.

### Stufe 0 – Lücken schließen, ohne neue Funktion (Voraussetzung für 3)

- **Inhalt:** L1 (Vorbehalte `uix/**` u. a.; Hash-Prüfung beim Laden), L2 (Weite der Allowlist), L5 (CSP des Rahmens), Gate-Text (Nr. 9), Test für `sandbox="allow-scripts"` ohne `allow-same-origin`.
- **Risiko:** gering. L5 kann Rahmen-Werkzeuge brechen, die heimlich `fetch` nutzen (laut Regeln verboten); L1 stellt Handarbeit des Captains an `uix/**` nicht in Frage, nur dem Modell ist es gesperrt.
- **Tests:** vorhandene Stufe-C-Tests; neu: Rahmen-`fetch` scheitert; `GET /api/*` bei COMMUNITY wird abgewiesen; `datei_schreiben uix/tools/x/tool.yaml` ergibt eine harte Karte; Hash-Abweichung beim Laden → App aus + Audit.
- **Rückfall:** CSP-Kopfzeile zurück; Vorbehalte sind reine Liste; Hash-Prüfung per Schalter.

### Stufe 1 – Zellen der Taskleiste aus `tool.yaml` (`kind: instrument`) ableiten

- **Inhalt:** `ZELLEN` in `taskleiste.js:15` wird aus dem Manifest gebaut: alle `kind: instrument`-Werkzeuge nach `order`, mit `zelle.{key,label,ort}`. Die neun `gauge-*`-Manifeste bekommen
  `zelle` passend zur heutigen Liste (inklusive der bisher ignorierten Zellen nur, wenn der Captain sie will, sonst `zelle` weglassen). Werte kommen weiter aus `/api/strip`; `strip_view` bleibt zunächst
  fest (nur die Reihenfolge und Beschriftung wandern ins Manifest). Sonderzellen (`decisions`, `token`, `model`/`server`, `state`) bleiben Code der Shell mit `sonder: <name>` im Manifest.
- **Noch nicht:** Fremde Zellen. Erst Stufe 3.
- **Risiko:** mittel für die Anzeige (Reihenfolge, Position der Token-Zelle, Blinken der Freigaben), null für Sicherheit, weil nur CORE-Instrumente betroffen sind.
- **Tests:** Gold-Test: aus den Manifesten abgeleitete Liste ist **identisch** zur heutigen `ZELLEN` (Schlüssel, Beschriftung, Ziel, Reihenfolge); node-Test für die reine Funktion `zellenAusManifest`; `uix_check` bei 1024×700.
- **Rückfall:** Konstante `ZELLEN` bleibt als Rückfallliste, wenn das Manifest keine Zellen liefert oder die Ableitung scheitert; Schalter in den Einstellungen nicht nötig.

### Stufe 2 – Ort und Gebiet im Manifest, Start-Menü daraus

- **Inhalt:** Feld `ort` (und `gruppe`, das es schon gibt). `places.js` bleibt Quelle der Kernorte; der Desk liefert `Kernorte + Orte aus Manifesten` an Shells und Chat. `chat_tools.PLACES` und
  `werkzeuge.py:ORTE` lesen diese Zusammensetzung. Kollisionsprüfung in `check_tool`. `start_gruppen.json` schrumpft auf die Gruppennamen und die Zuordnung der Kernorte.
- **Aktivieren statt sofort:** Orte aus COMMUNITY-Apps erscheinen erst nach „Aktivieren“ (Nr. 10, 11).
- **Risiko:** mittel. Doppelte Wahrheit entsteht kurz (Liste und Manifest); Palette und Chat müssen dasselbe sehen. Wörter-Kollisionen verändern Navigation – deshalb reserviert.
- **Tests:** der heutige Vergleichstest (places.js ↔ chat_tools) wird zum Test „Zusammensetzung = Kernorte + Manifeste“; Kollision → abgewiesen mit Grund in `rejected`; `app_oeffnen` einer nicht aktiven Fremd-App → Fehler; node-Test für Startliste mit Fremd-Ort.
- **Rückfall:** Kernorte bleiben im Code; schaltet man das Lesen aus Manifesten ab, ist der Zustand wie heute.

### Stufe 3 – Erweiterungen (MCP, GateWay) als Apps mit Isolation

Zwei Arten, die man trennen muss:

**3a. Oberflächen-Apps** (GateWay-artig: Werkzeug + Objekttyp): sind schon Apps. GateWay ist ein CORE-Werkzeug (`uix/tools/gateway`) mit Backend `gateway/`; als Paketteil bleibt es CORE. Für Fremde gelten Stufe 0 bis 2.
Was neu zu klären ist: eine Fremd-App mit eigenem Objekttyp braucht einen **Leser** auf der Serverseite. Heute ist `desk/kinds.py` Python im Prozess, beim Start eingefroren, nur über `desk/extensions.MODULES` (Paket) erweiterbar.
**Fremder Python-Code im Server-Prozess kommt nicht in Frage.**

**3b. Dienste (MCP-Server und Ähnliches):** laufen **außerhalb** des Prozesses und sprechen mit dem Kern wie die vorhandenen Clients: eigenes Token pro App, Scope nur `/api/objects` und `/api/actions`
(R5, `uix_clients.py`), Fähigkeiten aus dem Manifest bestimmen, welche Typen und Verben das Token berühren darf. Das ist **die** Brücke für Erweiterungen: Pull statt Push, der Kern bleibt der Server.
Für fremden Code, der selbst ausgeführt werden soll, gibt es `sandbox/` (microVM); ein Dienst-Prozess auf dem Host nur nach Gate, mit Port- und Pfadgrenzen, und ausdrücklich nicht aus einer COMMUNITY-Lieferung.

- **Risiko:** hoch. Berührt Token-Vergabe (Kern), Prozessstart (Gate) und den Server-Bau. Deshalb zuletzt, mit eigener Spec.
- **Tests:** Token-Scope (Verb ohne Fähigkeit → 403 + Audit), Dienst ohne Aktivierung startet nicht, Entzug beendet den Prozess, Client-Feld `mcp` bleibt vom Server gesetzt, Audit-Kette intakt, Fake-Host für `test_desk_*`.
- **Rückfall:** Dienst-Apps sind ein Schalter (`apps_dienste`, Standard aus); aus = heutiger Zustand der MCP-Clients.

---

## 5. App-Berechtigung: die fünf Fragen als Schalter je App

Die fünf Fragen der ersten Fassung sind keine einmalige Grundsatzentscheidung. Sie werden **je App** in der Berechtigung festgelegt (Karte „Berechtigung“ im Modul-Werkzeug,
Änderungen als Antrag mit Gate im Posteingang, §3.6). Der Kern liefert nur die **Obergrenze je Vertrauensstufe**; innerhalb der Grenze entscheidet der Captain pro App.

| Nr | Schalter in der Berechtigung (gilt je App; Verfügbarkeit je Shell siehe §2.2a) | Werte | Standard COMMUNITY | Obergrenze (Kern, nicht änderbar) |
|---|---|---|---|---|
| B1 | **Aktivierung** | `aus` · `an` | `aus` nach dem Einbau; „An“ ist ein eigener Klick mit Audit | – |
| B2 | **Zelle in der Leiste** | `nein` · `text` (Wert + Ton, gekennzeichnet „fremd“) | `nein` | nie Code in der Leiste, nie Klickziel außerhalb eines Orts |
| B3 | **Schreiben im Projekt** (`uix/**` u. a.) | gehört nicht zur App-Berechtigung, sondern zu den Vorbehalten des Kerns | – | `uix/**`, `desk/gateway.py`, `desk/install.py`, `uix_server.py` bleiben harte Karte für das Modell, für jede App und jede Sitzung |
| B4 | **Ereignisse hören** | je Name an/aus; Klassen: `öffentlich` (system.state, model.changed, desk.resync, tools.refresh, slot.changed) · `inhalt` (decision.*, live.line, talk.context, object.open, task.changed) | nur `öffentlich`, ohne Haken nichts | `inhalt` nur mit ausdrücklichem Haken, Nutzlast gefiltert (nie `describe`, `line`) |
| B5 | **Dienst-Prozess** (MCP u. ä.) | `nein` · `ja, Host (nur eigene)` · `ja, microVM` | `nein` | Dienst auf dem Host nur für `CAPTAIN`/`GUPPI_BUILT`; fremde nur in der microVM |

Einordnung nach Schutzstufe: B1 und die Kennzeichnung der Zelle sind Stufe A/B (Aktivierung ist ein Klick, Zelle ist `dangerous`), B4 `öffentlich` = A, `inhalt` = B, B5 = B (fremd nur microVM), B3 = C. Dazu die Schalter aus §2.3 (`lesen:<typ>`, `verb:<typ>.<verb>`, `ablage`, `netz:<host>`) in derselben Karte. Vorlage der Karte im Manifest:

```yaml
rechte:
  aktivierung: aus            # B1: der Captain schaltet an
  zelle: nein                 # B2: nein | text
  ereignisse: [system.state]  # B4: Namen; Klasse `inhalt` nur mit Haken des Captains
  dienst: nein                # B5: nein | host | microvm
  lesen: [rechnung]
  verben: []
```

Regeln:
1. **Das Manifest bittet, der Captain gewährt.** Was in `rechte:` steht, ist der Antrag; die gewährte Fassung liegt als Datei des Captains unter `local_config/` (vom Modell nicht beschreibbar, Vorbehalt) und gilt nur, solange der Manifest-Hash passt.
2. **Mehr verlangt als gewährt = nicht geladen** (mit Grund in `rejected`), nie stillschweigend gekürzt.
3. **Die Obergrenze ist Code des Kerns** (§2.6) und steht nicht im Manifest. Eine App kann sie nicht mitbringen.
4. **Jede Änderung nach oben** (B1 an, B2 text, B4 Haken, B5 ja) ist ein Gate; nach unten braucht keines.
5. **Das Modell darf beantragen**, nie gewähren und nie aktivieren; `app_oeffnen` öffnet nur Kernorte und aktivierte Apps.
6. B3 steht hier nur der Vollständigkeit halber: es ist kein Schalter. Der Schutz von `uix/**` hängt nicht an der App, sondern am Projekt.

Offen bleibt an den Captain nur noch die **Werkseinstellung** der Tabelle (Spalte „Standard COMMUNITY“). Die Empfehlung steht in der Tabelle.

---

## 6. Quellen (gelesen)

`uix/tools/_template/{tool.yaml,README.md}`, `docs/SHELL_WERKZEUG_VERTRAG_v1.md`, `docs/SPEC_HARNESS_SHELL_v1_STUFE6_G1.md`, `docs/ARCHITEKTUR.md`, `docs/ARBEITSWEG_WUNSCH_UMSETZEN.md`,
`uix/shells/harness/{taskleiste.js,startmenue.js,start_gruppen.json,arbeitsplatz.yaml,einstellungen.js}`, `uix/ui/{loader.js,bruecke.js,rahmen.js,places.js}`,
`desk/{gateway.py,install.py}`, `uix_server.py` (Allowlist, Einbau, Vertrauen, Strip, Rahmenseite, CSP), `harness/{werkzeuge.py,freigabe.py,vorbehalte.py}`, `chat_tools.py:108`,
`uix/tools/gauge-gpu/`. Nicht gelesen: `uix/shells/_template/` (liegt im Paket unter `runtime/src/guppi_runtime/uix/shells/_template`, nicht im Wurzelverzeichnis), die Stufe-C-Tests, `uix_clients.py`, `core/content_guard.py` im Einzelnen.
