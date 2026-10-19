# Plan: Stufe C der Modulisolation (iframe und Brücke)

**Stand:** 19.10.2026, nach Commit `dd73aed` (Auto-Update Teil 2) und Stufe A/B.
**Art:** reine Planung. Noch nichts umgesetzt. Grundlage: `docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md`, Abschnitt 3.1.

---

## 1. Ausgangslage (im Code geprüft)

- 28 Werkzeuge sind `trust: CORE`, eines `trust: CAPTAIN`. Fremdmodule (COMMUNITY) gibt es noch keine im Alltag.
- Kein Werkzeug ruft `fetch` selbst auf. Alle gehen über `ctx.api()`, das der Kern der Shell reicht (`ui/api.js`).
- Werkzeuge rendern direkt in die Seite der Shell (`mount(el, ctx)`), nutzen `window.sedraDom` und hören auf den Ereignisstrom der Shell (`ui/bus.js`).
- Stufe A hat den Token aus dem Modulzugriff genommen. Eine Grenze gegen Code auf derselben Seite gibt es aber weiterhin: Dieser Code kann die Adresse lesen oder Shell-Objekte anfassen. `ui/api.js` nennt das selbst als ehrliche Grenze.

## 2. Ziel

Ein Modul, das nicht vertraut wird, kann nur:
- die Routen aufrufen, die sein Manifest nennt,
- auf Ereignisse antworten, die für sein Fenster bestimmt sind,
- nichts vom Token, vom Kern-Objekt oder von anderen Modulen sehen.

## 3. Technischer Entwurf

### 3.1 Trennung

- Jedes Modul mit `trust` außer CORE läuft in einem `<iframe sandbox="allow-scripts">`. **Ohne** `allow-same-origin`. Dadurch hat der Frame eine undurchsichtige Herkunft: kein Zugriff auf Token, Cookies, `localStorage` oder das Elternfenster.
- CORE-Werkzeuge bleiben in der Seite (Empfehlung aus Abschnitt 3.1). Sie sind geprüfter Kern; ihre Grenze ist die Herkunft des Pakets, nicht die Sandbox.

### 3.2 Brücke (postMessage)

- Der Kern (Shell/Loader) hält den Token und allein `fetch`.
- Ein Modul schickt Nachrichten der Form `{id, op, path, method, body}`. Ops: `api`, `events:subscribe`, `ready`, `resize`.
- Der Kern ordnet jede Nachricht über `event.source` dem Modul zu, **nicht** über ein Feld in der Nachricht. Ein Modul kann also keine fremde Kennung vortäuschen.
- Jede `api`-Nachricht wird gegen die Routenliste des Manifests geprüft. Nicht gelistet → Fehler `tool_route_not_allowed`, wie heute.
- Antworten gehen an `event.source` zurück, mit `id`. Der Zielursprung ist `'*'` nur für den Frame, dessen Herkunft undurchsichtig ist; der Kern prüft, dass `event.source === frame.contentWindow`.
- Ereignisse: der Kern abonniert den Strom und leitet nur Ereignisse weiter, die das Modul laut Manifest `events.listens` nennt.

### 3.3 Oberfläche

- Der Frame bekommt eine eigene Kopie des nötigen CSS (`shell.css`, Werkzeug-CSS) und eine kleine Laufzeit mit `sedraDom`-Teilen. Keine Skripte aus der Shell.
- Dock, Fenster, Verschieben und Tastatur bleiben in der Shell. Nur der Inhalt wandert in den Frame.
- Die Größe des Frames folgt dem Fenster per Nachricht `resize`.

### 3.4 Was sich für Werkzeuge ändert

- Der Vertrag `ctx.api` bleibt gleich. Im Frame ist `ctx.api` ein Stellvertreter, der über die Brücke geht. Werkzeug-Code muss dafür nicht umgeschrieben werden, solange er nur `ctx.api` und `el` nutzt.
- Werkzeuge, die `window.sedraDom`, Shell-Objekte oder fremde DOM-Knoten anfassen, müssen angepasst werden. Das wird vorher durch eine Bestandsaufnahme gefunden (siehe Schritt C1).

## 4. Schritte

| Schritt | Inhalt | Prüfung |
|---|---|---|
| **C1** Bestandsaufnahme | Alle Werkzeuge und Shells nach Zugriffen auf `window`, `document` außerhalb von `el`, `sedraDom`, `sedraApi` durchsuchen. Liste je Werkzeug. Read-only. | Liste im Dokument, keine Änderung |
| **C2** Brücke ohne Frame | Kern-Seite: Nachrichtenprotokoll, Zuordnung über `event.source`, Routenprüfung, Ereignisfilter. Im Test mit zwei Frames ohne echte Oberfläche. | Tests: fremde Kennung wird abgelehnt; Modul ohne Route bekommt `tool_route_not_allowed`; Modul ohne `events.listens` bekommt kein Ereignis; Token steht nie im Frame |
| **C3** Ein Werkzeug im Frame | Pilot: ein kleines, unkritisches Werkzeug (z. B. Uhr oder System-Anzeige). Browser-Test. | Browser-Suite grün; Werkzeug zeigt dieselben Daten |
| **C4** Alle Fremdwerkzeuge | Alle Nicht-CORE-Werkzeuge in den Frame. CORE bleibt in der Seite. | Browser-Suite (18 Tests) grün; Vertragsprüfung grün |
| **C5** Gegenprüfung | Versuch aus einem Test-Modul: Token lesen, `parent.sedraApi`, fremde Route, fremde Kennung. Jeder Versuch muss scheitern und im Protokoll stehen. | Testdatei mit diesen Versuchen |

Geschätzter Umfang: C1 klein, C2 mittel, C3 klein, C4 mittel, C5 klein. C2 und C5 sind die sicherheitskritischen Teile und bekommen die meisten Tests.

## 5. Risiken

- **Layout und Fokus:** Frames verschlucken Tastatur- und Mausereignisse, Drag & Drop funktioniert nicht über die Grenze. Gegenmittel: Browser-Tests je Schritt, Tastatur-Test im Frame.
- **Synchrone Aufrufe:** Werkzeuge, die heute synchron Shell-Objekte lesen, brechen. Gegenmittel: C1 findet sie vorher.
- **Performance:** Viele Frames kosten Speicher. Mit wenigen Fremdmodulen unkritisch.
- **Scheinsicherheit bei CORE:** Solange CORE in der Seite bleibt, schützt die Sandbox nur Fremdmodule. Das ist gewollt, muss aber in der Dokumentation stehen.

## 6. Entscheidungen, die du treffen musst

1. **CORE-Werkzeuge in der Seite lassen?** *Empfehlung:* ja. Alles umzubauen wäre groß und bringt wenig, weil CORE aus dem Paket kommt und geprüft ist.
2. **Vor oder nach Auto-Update für Dritte?** Updates können Modulrechte ändern (Teil 2 ist fertig). *Empfehlung:* C vor einer Freigabe für fremde Module. Für den eigenen Gebrauch reicht Stufe A/B.
3. **Umfang von C4:** nur COMMUNITY-Module, oder auch CAPTAIN-Werkzeuge? *Empfehlung:* alle Nicht-CORE.

## 7. Nicht in diesem Plan

- Signierte Releases (Frage 3 aus dem Isolationsplan).
- Eine Isolation der Shells selbst. Shells bleiben Kern.

## 8. Ergebnis C1 (Bestandsaufnahme, 19.10.2026)

- **Stand der Werkzeuge:** 28 CORE, 1 CAPTAIN (nur `tools/_template`, die Vorlage). Es gibt heute **kein** echtes Nicht-CORE-Werkzeug. Der Rahmen (C4) hat deshalb im Alltag noch keinen Gegenstand; er schützt künftige Module. Der Pilot (C3) braucht ein Test-Modul, kein bestehendes Werkzeug.
- **Shell-Aktionen:** Werkzeuge rufen `ctx.shell.open`, `ctx.shell.notify` und `ctx.shell.decide` auf (`ui/loader.js`, `SHELL_API`). Die Brücke muss genau diese drei Aufrufe als Nachrichten tragen. `decide` ist für Nicht-CORE schon heute gesperrt und wirft einen Fehler; das bleibt so.
- **Gemeinsame Hilfsobjekte:** `root.sedraGatewayArbeit`, `root.sedraGatewayRegeln`, `root.sedraTalkKombi`, `root.sedraVorgabe` werden von CORE-Werkzeugen genutzt. Sie bleiben in der Seite, weil diese Werkzeuge in der Seite bleiben. Kein Konflikt.
- **Direkter DOM:** `document.createElement`/`createTextNode` nur in CORE-Werkzeugen (`schutz`, `gateway`); im Rahmen wären sie innerhalb des eigenen Dokuments unproblematisch.
- **Token und Kern-Objekte:** Kein Werkzeug liest `sedraApi`, `location` oder den Token. Die einzigen Zugriffe auf `top`/`parent` sind Variablen `top` in `gateway/regeln.js` (lokale Variable, kein Fensterzugriff).

**Konsequenz für C2 bis C5:** Die Brücke trägt `open`, `notify`, `decide` und `ctx.api`/Ereignisse. Der Pilot in C3 ist ein Test-Modul unter `tools/_template`-Kopie. Ohne echte Fremdmodule bleibt die Wirkung zunächst theoretisch; sie ist dann mit C5 belegbar.

## 9. Stand nach C2 (19.10.2026)

- **C2 erledigt:** `runtime/src/guppi_runtime/uix/ui/bruecke.js` mit den reinen Regeln (`pruefeNachricht`, `routeErlaubt`) und der Kern-Brücke (`makeBruecke`). Quelle wird über das Fenster zugeordnet, Routen über Methode und Pfad gegen das Manifest geprüft, `decide` ist über die Brücke nicht erreichbar, Ereignisse gehen nur laut `events.listens`. Test: `runtime/tests/test_stufe_c_bruecke.py` (12 Tests, node), alle grün.
- **Noch nicht verdrahtet:** Der Loader und die Shells nutzen die Brücke noch nicht. Dadurch ändert C2 das laufende Verhalten nicht.
- **Offen:** C3 (Rahmen-Client im Frame, Auslieferung der Frame-Seite über den Server, Einbau in `mountTool`, Pilot als Test-Modul, Browser-Test), C4 (Umstellung, nur für Nicht-CORE, im Alltag ohne Gegenstand), C5 (Gegenprüfung mit einem Angriffs-Testmodul im Browser).

## 10. Stand nach C3, C4 und C5 (19.10.2026)

- **C3 erledigt:** Der Rahmen läuft. Der Loader (`ui/loader.js`) lädt den Code von Nicht-CORE-Werkzeugen nicht mehr in die Seite; er hängt stattdessen ein `iframe sandbox="allow-scripts"` ein (`mountFrame`). `ui/lifecycle.js` leitet `mountTool` dorthin. Der Rahmen selbst ist `ui/rahmen.js` (läuft im iframe, nur `postMessage`) und die Seite `/uix/frame/<id>`, die der Server ohne Token ausliefert (`desk/gateway.frame_page`).
- **C4 erledigt im Code:** Die Umstellung gilt für jedes Werkzeug außerhalb des Pakets. Im Alltag ist das der Pilot `rahmen-probe`, sonst keines.
- **C5 erledigt als Browser-Test:** `runtime/tests/test_stufe_c_rahmen.py` klickt im Rahmen jeden verbotenen Versuch (fremde Route, Freigabe, Lesen der Shell-Seite, Token-Zugang) und prüft, dass er verweigert wird. Außerdem: Der Code des Pilots steht nicht in der Seite, der Token-Zugang `window.sedraApi` fehlt in der Seite, die Sandbox hat kein `allow-same-origin`.
- **Tests:** Vertrag, Server, Isolation A/B, Brücke (12), Rahmen (1, Browser), Oberflächen-Browser-Suiten: alle grün.
- **Bekannte Grenzen:**
  - Der Rahmen hat nur das Werkzeug-CSS, nicht das Design der Seite. Darstellung im Rahmen ist daher noch schlicht.
  - Ereignisse aus dem Rahmen heraus sind nicht möglich (`bus.emit` ist im Rahmen leer), nur Empfang laut Manifest.
  - Getestet ist der Rahmen nur in der Cockpit-Shell; Minimal und Paperclip sind nicht im Browser geprüft.
  - Der Pilot `rahmen-probe` ist als Instrument sichtbar. Er kann nach Abnahme ausgeblendet werden.
