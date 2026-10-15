# UIX-Analyse und Weiterentwicklung (Stand 2026-10-13, 22:00)

Grundlage: das Entwickler-Archiv `GUPPI_UIX_Developer_2026-10-13`. Gelesen wurden `uix/retro_desktop.html`, `uix/css/desktop.css`, alle 15 Dateien in `uix/js/`, `uix_server.py`, `uix_start.py`, `uix_diag.py`, die UIX-Tests und `docs/UIX_ROADMAP.md`. Anders als bei der Roadmap vom 04.10. wurde die UIX diesmal **gestartet**: `uix_server` auf einem Testprojekt (mit `host_isolation`, ohne echte GPU) und Headless-Chromium (Playwright), das jedes Fenster öffnet, Konsole und fehlgeschlagene Anfragen mitschreibt und Screenshots macht. Die Befunde unten stammen aus diesem Lauf, nicht aus Vermutungen.

## 1. Zustand der Oberfläche

Die Aufteilung in `css/` und `js/` (Phase 4) trägt: 15 kleine Skripte, keine über 353 Zeilen, Ladereihenfolge in der HTML-Datei, Server liefert Dateien aus einer Whitelist. Alle Fenster sind an echte Endpunkte gebunden, Attrappen gibt es nicht mehr. Der Chat ist die Arbeitsfläche (Plan-Karte, Freigaben, Diagnose-Leiste, Befehle). Die Leitplanken (UIX liest nur, Runtime entscheidet, Gates einzeln per ID) sind im Code durchgehalten: kein Knopf umgeht ein Gate, Freigaben sind an `gate_id` gebunden, Schalter- und Routing-Änderungen laufen über Mission + Gate + Prüfung des Laders.

Was fehlte, waren nicht Funktionen, sondern **Bedienbarkeit im Detail**: Fenster, deren Inhalt nicht in den Rahmen passte, eine Taskleiste, die bei mehreren Fenstern überlief, und ein paar Anzeigen, die im frischen Paket (ohne Modell) falsche Werte zeigten. Der schwerste Fehler war unsichtbar, solange man nur den Code las.

## 2. Gefundene und behobene Fehler

| Nr. | Befund | Ursache | Behebung |
|---|---|---|---|
| 1 | **Chat-Fenster ohne Titelleiste und Werkzeugleiste.** Beim Start sieht der Captain nur Verlauf, Modellzeile und Eingabe; Verschieben, Schließen, Brücke/Modelle/Diagnose sind nicht erreichbar. Projekt-, Entwicklungs-, Modelle- und Verarbeitungsfenster schneiden unten 69–76 px ab (z. B. die letzten Modellkarten). | `.content{height:calc(100% - 69px)}` wurde von `.chat-body`, `.project-layout`, `.dev-layout`, `.model-main`, `.processor` mit `height:100%` überschrieben, die auf **demselben** Element liegen. Der Inhalt ragte unter das Fenster; `focus()` auf das Eingabefeld scrollte das `overflow:hidden`-Fenster um 76 px nach unten. Außerdem ist die Werkzeugleiste 44 px hoch, nicht 37. | Fenster sind eine Flex-Spalte (`.window.active{display:flex}`), `.content{flex:1 1 0;min-height:0}`; keine festen Höhen mehr. Gemessen: `winScrollTop` 0, Titelleiste sichtbar, Inhalt = Fenster − Leisten. |
| 2 | **Taskleiste läuft über.** Feste Knöpfe und Fensterknöpfe doppelt („● GUPPI Interface" und „Interface"); ab fünf offenen Fenstern verschwinden Zustand, Skills und Uhr rechts aus dem Bild. | Feste Launcher ohne Bezug zum Fenster, `min-width:160px`, kein Schrumpfen. | Launcher tragen `data-window`; `syncTaskbar()` blendet den Launcher aus, solange sein Fenster offen ist (ein Knopf je Fenster). Knöpfe `flex:0 1 160px`, `min-width:60px`, Ellipse; `.task-right` fest. |
| 3 | **Modellauswahl zeigt „null".** Im frischen Paket (Rezept ohne `model`) steht „null" im Chat-Auswahlfeld und in Rückfragen („null laden?"). | `r.model` direkt verwendet. | `modelName(r)` = Modell oder Rezept-ID; Karte sagt „kein Modell eingetragen". |
| 4 | **Brücke und Logbuch: Knöpfe auseinandergezogen**, der Missionsknopf klebt am unteren Rand. | `.preview{display:grid;place-items:center}` zentriert jedes Kind; nur der Maschinenraum setzte `display:block` per JS. | `.preview` ist eine Spalte (`flex-direction:column;align-items:flex-start`); Bilder und Platzhalter bleiben zentriert; Karten, Schrittleiste, Rohdaten volle Breite. JS-Sonderfall entfernt. |
| 5 | Seitenspalte im Projektfenster und im Verarbeitungsfenster nicht scrollbar (Karte „VM-Idee" abgeschnitten); Werte in `info-row` ragen aus der Karte („blockiert" rechts außerhalb). | kein `overflow`, kein `min-width:0`. | `overflow:auto;min-height:0`; Werte `white-space:nowrap`, Beschriftung umbricht. |
| 6 | Entwicklungsumgebung: „BLOCKED" und „TECHNISCH BLOCKIERT" in **Grün**. | Klasse `ok` fest im Markup. | `state.className = ready ? 'ok' : 'bad'`, Badge `.bad` rot. |
| 7 | Modelle-Fenster: Überschrift „Modellkombination" ohne Inhalt; Freigabe-Karte einer Routing-Änderung erschien unter „Schalter"; „Modell-Einstellungen" leer ohne Hinweis. | fehlende Fallunterscheidung. | Überschrift nur mit Einträgen; `renderPendingChange(box, kind)` je Abschnitt; Hinweis auf fehlende `local_config/role_routing.yaml`. |
| 8 | `claude_chat.js` führte Code auf oberster Ebene aus (Event-Bindung, `ccLoad()`), entgegen der Regel aus Phase 4 („nur `main.js`"). | – | `ccInit()` in `claude_chat.js`, Aufruf in `main.js`; ein Test verlangt das jetzt für alle Dateien. |

Dazu kleinere Verbesserungen, die beim Durchklicken auffielen:
- **Mission-Fenster** (`missionWorkflow`): lesbarer Kopf (Auftrag, Phase, Klasse, Risiko, Plan-Schritte, Ergebnis, offene Fragen) über den Rohdaten; „Mission ausführen" nur, wenn kein Gate offen und die Mission nicht fertig ist (dieselbe Regel wie in der Chat-Karte); Phasen-Badge gilt jetzt überall, nicht nur im Chat.
- **Startmenü** schließt bei Klick daneben und mit Escape (vorher blieb es offen, bis man erneut auf „GUPPI" klickte). Escape schließt auch das Kontextmenü.
- **„Projekte"** in Taskleiste und Startmenü zeigte ein `alert()`; jetzt werden die Ordner kurz markiert und GUPPI sagt in der Sprechblase, wo sie liegen.
- **Tastatur:** Fenstersteuerung (—, □, ×), Startmenü-Einträge, Kontextmenü, Taskleistenknöpfe und Projektordner sind per Tab erreichbar und mit Enter/Leertaste bedienbar (`makeKeyboardButton`), mit sichtbarem Fokusrahmen. Ein erster Schritt zu Phase 5.
- „Neuer Chat" schreibt eine Begrüßung statt zwei.
- Leerer Projektordner: der Hinweis spannt über das ganze Dateiraster statt in einer Zelle zu stehen.

Tests: 5 neue in `tests/test_uix_server.py` (Fensterlayout ohne feste Höhen, ein Taskleistenknopf je Fenster, Modellname-Ersatz, kein Code auf oberster Ebene außerhalb `main.js`). `test_uix_server`, `test_uix_diag`, `test_uix_start`, `test_agent_ui`: 78 grün, 1 übersprungen (kein Lader im Testprojekt). Alle JS-Dateien bestehen `node --check` und bleiben unter 400 Zeilen. Server (`uix_server.py`) unverändert.

Nicht geändert, aber gesehen: `/api/processes` meldet unter Linux „powershell nicht gefunden" (nur im Testlauf; auf dem GUPPI-PC nicht relevant). Der Guppy-Meter zählt im Testprojekt 48.552 Zeilen „von Claude", weil er das Git des Pakets liest; das ist die bekannte Zählweise, kein UIX-Fehler.

## 3. Was die UIX heute gut macht

- **Ehrlich:** Jeder Zustand kommt aus `/api/...`; ohne Verbindung steht „OFFLINE", ohne Modell „nur planen", ohne Projekt ein klarer Satz. Nichts wird vorgetäuscht.
- **Freigaben sind sichtbar und einmalig:** Karte im Chat mit Ziel, Risiken, Rücknahme; Bestätigung zeigt die genaue Anfrage; nach jeder Aktion wird die Karte aus dem Missionsdatensatz neu gebaut.
- **Erklärte Fehler:** `/api/diagnose/explain` übersetzt Fehlercodes in Ursache und nächsten Schritt, mit Kopierknopf; die Diagnose-Leiste und `/status` zeigen GPU, Lease, Modell, Selbsttest, Profil.
- **Kein Flackern im Modelle-Fenster:** Ansicht wird abseits gebaut und nur bei Änderung getauscht; während der Captain tippt, wird nicht neu gezeichnet.
- **Kleine, lesbare Dateien**, die GUPPI selbst ändern kann (coin_hole.js und diag_panel.js hat es schon gebaut).

## 4. Vorschläge zur Weiterentwicklung

Geordnet nach Nutzen für den Captain pro Aufwand. Die ersten vier sind klein genug, dass GUPPI sie als Kandidaten bauen kann (eine `js/`-Datei + `test_uix_server.py`).

### 4.1 Nahe Schritte (je 1–2 Dateien)

1. **Mehrere Verarbeitungsfenster.** Heute gibt es **ein** `processorWindow` für Maschinenraum, Logbuch, Brücke, Datei, Mission und Kandidaten-Ergebnis. „Logbuch" aus der Brücke ersetzt die Brücke; eine Datei neben einer Mission ansehen geht nicht. Vorschlag: `showProcessor()` klont eine Vorlage pro Aufruf (Obergrenze z. B. 4, älteste wird ersetzt), Taskleiste und `syncTaskbar()` funktionieren schon generisch. Alternativ: Brücke bekommt ein eigenes Fenster, da sie die Zentrale ist.
2. **Verlauf des Chat-Fensters überlebt ein Neuladen.** Der Companion-Chat (`chat.js`) ist nach F5 oder Server-Neustart leer; der „GUPPI Chat" (`claude_chat.js`) speichert in `localStorage`, aber beide Fenster wissen nichts voneinander. Vorschlag: `chatHistory` + `chatSessionMission` im `sessionStorage` halten (Leitplanke: kein Runtime-Zustand, nur die Anzeige), und die Sitzungs-Mission beim Start per `/api/mission/details` prüfen (existiert sie noch?).
3. **Zwei Chats zusammenführen oder klar trennen.** „GUPPI Interface" (Projekt, Plan-Karten, Freigaben, Anhänge, Diagnose) und „GUPPI Chat" (Sitzungsliste, Markdown, kein Plan) überschneiden sich; die Modellauswahl ist gekoppelt, der Rest nicht. Entscheidung des Captains: entweder die Sitzungsliste in das Interface-Fenster ziehen (links einklappbar) und `claude_chat.js` auflösen, oder den Chat als reinen „Lese-/Frage-Modus" benennen und Plan-Karten dort bewusst weglassen. Der Entwurf `ABLAUF_GESPRAECH_2026-10-13.md` setzt auf dem GUPPI Chat auf; dann sollte das Interface-Fenster absehbar die Rolle „Brücke mit Chat" bekommen.
4. **Freigabe-Leiste (G7) im Chat-Fenster.** Vom Captain am 13.10. entschieden: Leiste unter dem Verlauf, rot/grün/grau, Zähler im Fenstertitel, Entscheidung nur in der Detailansicht per Gate-ID. Die Daten gibt es (`/api/missions` → `pending_gates`, `/api/mission/details` → `human_gates`). Vorschlag: `js/gate_bar.js` (GUPPI baut den Rechenteil, Spec `gate_bar` steht in der Nachtkette G), 30-Sekunden-Abfrage nur bei fokussiertem Fenster wie im Modelle-Fenster. Die bestehende Gate-Karte in der Chat-Karte bleibt als Detailansicht.
5. **Live-Zustand der Mission in der Karte.** Nach „Ausführen" wird die Karte erst nach Rückkehr des Aufrufs neu gebaut; bei langen Läufen sieht der Captain nichts. Vorschlag: während `mission/run` läuft, alle 3 s `mission/details` lesen und die Phase/Schritte aktualisieren; Knopf zeigt „läuft …".

### 4.2 Mittlere Schritte

6. **Fensterzustand merken.** Position, Größe, maximiert, offen/zu je Fenster in `localStorage` (reine Anzeige-Bequemlichkeit, von der Leitplanke erlaubt). Beim Start öffnen sich die zuletzt offenen Fenster wieder. Dazu ein Menüpunkt „Fenster anordnen" (Kaskade / nebeneinander), damit man aus der Stapelung herauskommt.
7. **Projektfenster: Dateien lesen *und* in den Chat ziehen.** Klick auf eine Datei öffnet die Vorschau; ein zweiter Knopf „An nächste Nachricht anhängen" nutzt `/api/chat/attach` mit dem absoluten Pfad des Projekts (Server kennt `workspace_path`). Damit entfällt das `prompt()` für Pfade im Normalfall.
8. **Suche und Filter in Brücke und Logbuch.** Ab 30 Missionen ist die Knopfliste unhandlich: Textfilter (Intent, ID), Filter nach Phase (READY, PAUSED, COMPLETE, FAILED) und „nur mit offenem Gate". Audit-Ereignisse nach Typ filtern.
9. **Maschinenraum mit Verlauf.** Die Karten zeigen den Moment; VRAM frei / RAM frei als kleine 10-Minuten-Linie (die Hardware-Seite hat `/api/state` mit `history`). Zusammen mit `/api/processes` ergibt das die Antwort auf „warum lädt das Modell nicht?" an einem Ort.
10. **Modell-Einstellungen: Vorschau der Wirkung.** Beim Ändern von Kontext, `n_cpu_moe` oder KV-Typ eine Schätzung „braucht ca. X GB VRAM, frei sind Y" (Daten: `size_gb`, `min_vram_gb`, `/api/resources`), bevor die Freigabe angefragt wird. Das verhindert Gates, deren Ergebnis dann an `hardware_pressure` scheitert.

### 4.3 Grundlagen (Phase 5)

11. **Echte Schaltflächen statt `div` + `onclick`.** `makeKeyboardButton` ist ein Pflaster. Langfristig `<button class="ctrl">` und `<button class="menuitem">`; dann entfallen `role`, `tabindex` und die Tastatur-Handler. Ein Test kann verlangen, dass es im Markup keine klickbaren `div`s ohne `role` mehr gibt.
12. **Fensterbausteine als Vorlage.** Jede Titelleiste wird in der HTML-Datei neun Mal fast gleich geschrieben. Eine `<template id="windowFrame">` plus `makeWindow(id, title, toolbar)` in `desktop.js` würde die HTML-Datei halbieren und ist die Voraussetzung für 4.1 Nr. 1.
13. **Prüfung mit echtem Browser als feste Abnahme.** Der heutige Fehler Nr. 1 ist statisch nicht zu finden. Vorschlag: `runtime/benchmarks/uix_check.py` (Playwright, Chromium ist auf dem PC vorhanden: Edge), das die Seite lädt, jedes Fenster öffnet, `pageerror`/Konsole/4xx-5xx sammelt und misst, dass kein Fenster intern gescrollt ist (`scrollTop === 0`) und Titelleisten im Rahmen liegen. Läuft optional in `run_tests.bat` (überspringt ohne Playwright). Das wäre „`pruefen.py` als feste Abnahme" aus Phase 4.2.
14. **Responsiv bis 1024 px.** Der `@media(max-width:850px)`-Block blendet die Seitenspalte aus und verbreitert zwei Fenster; die anderen sieben bleiben fest. Mindestens: alle Fenster `max-width:100vw`, Werkzeugleisten umbrechen (tun sie schon), Dateiraster 2 Spalten.
15. **Dunkles Thema** nur, wenn der Captain es will; die Hardware-Seite ist bereits dunkel (`#101722`), die Desktop-Seite hell. Der Bruch beim Öffnen des Hardware-Fensters fällt auf. Entweder die Hardware-Seite an das UIX-Thema anpassen (ein `.css` im UIX-Look, Struktur bleibt) oder ein Thema-Schalter in beiden.

## 5. Reihenfolge, die ich vorschlagen würde

1. Diese Korrekturen übernehmen und einmal im echten Fenster (Edge-App-Modus, 1920×1080) gegenprüfen: Chat-Fenster hat Titelleiste, Taskleiste zeigt Uhr bei sechs offenen Fenstern, Modelle-Fenster lässt sich bis zur letzten Karte scrollen.
2. `uix_check.py` (Nr. 13) als Abnahme, bevor GUPPI Oberflächen-Kandidaten baut; sonst prüft wieder nur das Lesen.
3. Freigabe-Leiste (Nr. 4) und Live-Karte (Nr. 5): das ist der Kern des beschlossenen Gesprächsablaufs.
4. Entscheidung zu den zwei Chats (Nr. 3), dann Verlauf speichern (Nr. 2).
5. Mehrere Verarbeitungsfenster (Nr. 1) auf Basis der Fenstervorlage (Nr. 12).

## 6. Dateien dieser Änderung

- `runtime/src/guppi_runtime/uix/css/desktop.css` (Fensterlayout, Taskleiste, Vorschau, Seitenspalten, Badges, Fokusrahmen)
- `runtime/src/guppi_runtime/uix/retro_desktop.html` (Launcher mit `data-window`)
- `runtime/src/guppi_runtime/uix/js/desktop.js` (`syncTaskbar`, `makeKeyboardButton`), `main.js` (Menüs schließen, Escape, Tastatur, `ccInit`), `status.js` (Zustandsfarben, kein Display-Sonderfall), `models.js` (`modelName`, Abschnitte), `missions.js` (`missionSummary`, Ausführen-Regel), `projects.js` (Projekte-Hinweis, Tastatur), `chat.js` (eine Begrüßung), `claude_chat.js` (`ccInit`)
- `runtime/tests/test_uix_server.py` (5 Tests)
- `docs/LOGBUCH_AGENT_MANAGER.md` (Eintrag 22:03), `docs/UIX_ROADMAP.md` (Stand)

## 7. Nachtrag 22:35: Umsetzung der schnellen Maßnahmen

Captain: „1 und 2 umsetzen, der Rest für GUPPI.“

**Umgesetzt (Claude)**
- **`runtime/benchmarks/uix_check.py`** – die Browser-Abnahme. `python benchmarks/uix_check.py` startet einen `uix_server` auf einem Wegwerf-Projekt (oder prüft mit `--url` eine laufende UIX), öffnet alle neun Fenster und misst, was der Captain sieht: Titelleiste im Rahmen, kein interner Scroll, Inhalt im Rahmen, Taskleistenknopf, Fokus auf das Eingabefeld, Uhr und Zustand sichtbar, keine JS-Fehler. Optionen `--shots DIR` (Screenshots je Schritt), `--browser msedge|chrome` (Browser des PCs statt Playwright-Chromium), `--headed`. Ergebnis als Zeile `result ok` / `result FAIL`. Gegenprobe: gegen den unveränderten Archivstand 9 von 13 Prüfungen rot, gegen den neuen 13/13. Als `tests/test_uix_browser.py` in der Suite; ohne Playwright übersprungen. Einrichtung auf dem PC: `.venv\Scripts\pip install playwright`, dann entweder `.venv\Scripts\python -m playwright install chromium` oder `--browser msedge`.
  → Ab jetzt die Abnahme für jeden UIX-Kandidaten von GUPPI: Spec-Tests (node) **und** `uix_check.py` müssen grün sein.
- **Live-Missionskarte** (`missions.js`, `runMissionLive`): nach „Ausführen“ wird der Missionsdatensatz alle 3 s gelesen und die Karte mit der aktuellen Phase neu gezeichnet (Badge „läuft … <status>“), kein zweiter Ausführen-Knopf; nach Rückkehr des Laufs einmal final. Geprüft mit einem künstlich auf 7 s verlangsamten Lauf. Im Mission-Fenster erscheint während des Laufs ein Hinweis, danach baut sich die Ansicht neu.

**Nebenbefund, behoben:** `benchmarks/spec_check.py` führte nur `hidden`-Tests (Python) aus. Stufen mit `host_hidden` (JS, node) galten als bestanden, ohne dass ein Test lief – drei neue Specs meldeten „ok“, obwohl ihre Tests an der Referenz scheiterten. Jetzt laufen node-Tests in der Baumkopie, fehlendes node ist FAIL. `coin_hole` und `chat_diag` bestehen weiterhin (devvm_build hatte beim Bau selbst mit node gerichtet; nur die Vorprüfung war blind).

**Für GUPPI vorbereitet** (Spec + versteckte node-Tests + Referenz, `spec_check` ok):

| Spec | Datei | Stufen | Was GUPPI baut | Anbindung danach (Claude) |
|---|---|---|---|---|
| `chat_store` | `js/chat_store.js` | pack, unpack | `packChat`, `unpackChat` (Version, Alter ≤ 7 Tage, Form, letzte 40 Züge, 4000 Zeichen), `chatSummary` | `chat.js`: nach jedem Zug in `sessionStorage` sichern, in `initChat` wiederherstellen, Sitzungs-Mission per `/api/mission/details` prüfen |
| `window_state` | `js/window_state.js` | clamp, store | `clampBox`, `cascadeBox`, `packWindows`, `unpackWindows` | `desktop.js`/`main.js`: sichern bei Bewegen/Größe/Öffnen/Schließen, beim Start wiederherstellen, Menüpunkt „Fenster anordnen“ |
| `mission_filter` | `js/mission_filter.js` | filter, groups | `filterMissions` (Wörter, Phasen, nur offene Gates), `missionGroups` (Heute/Gestern/Diese Woche/Älter), `missionLine` | `missions.js` (Brücke), `status.js` (Logbuch): Textfeld, Phasen-Chips, Schalter „nur mit offener Freigabe“ |

Baubefehl je Spec (Standard aus ENTWICKLUNG.md; `--context 32768` reicht, die Dateien bleiben unter 120 Zeilen):
```
cd runtime
.venv\Scripts\python.exe benchmarks/spec_check.py chat_store
.venv\Scripts\python.exe benchmarks/devvm_build.py <projekt> --spec chat_store --attempts 1 ^
    --coder coder.local_primary --all-models coder.local_primary --context 32768 --tidy --reasoning off --coder-ext all ^
    --server-set flash_attn=on --server-set kv_cache_type=q8_0 --server-set ubatch=512
```
Dasselbe für `window_state` und `mission_filter`. Nicht in die Nachtkette G eingetragen, weil die heute Nacht schon läuft; sie passen in die nächste Kette oder einen Tageslauf (je Spec etwa 3–6 Minuten GPU-Zeit nach den Erfahrungswerten von `chat_diag`).

**Punkt 5 (Datei aus dem Projektfenster anhängen)** ist reine Verdrahtung ohne eigene Logik – kein GUPPI-Bau, Claude macht das in einem der nächsten Schritte (`projects.js` + eine Zeile in `uix_server.chat_attach`, damit ein Projektpfad relativ zum `workspace_path` angenommen wird).

## 8. Nachtrag 14.10., 10:00: Umsetzung der Vorschläge aus dem Gespräch

Auf Wunsch des Captains selbst umgesetzt (Build 3, siehe `docs/CHANGELOG.md`): SEDRA-Benennung (GUPPI bleibt Maskottchen), Umgebungs-Skips statt roter Tests (`tests/env_skip.py`, volle Suite grün), `logbook.py` ohne Platzhalter-Art, `BUILD.txt` + `make_build.py` + `CHANGELOG.md`, Regel 12 in `ENTWICKLUNG.md` (Branches/Patches), Guppy-Status, Fensteranimationen, Denk-Puls, Seekarte, Anhängen ohne `prompt()` (Details im Style Manifest, Abschnitt 11).

Nicht umgesetzt, mit Grund: Münzloch nach Modell einfärben und Klick auf Münze → Lauf (GUPPI-gebauter Code `coin_hole.js`, braucht Laufdaten je Münze aus `/api/meter`: eigene Spec); Fischschwarm für Baustufen (braucht `build_log.events` in der Oberfläche: kommt mit dem Buildflow-Fenster); ein gemeinsamer Nachtplan für alle Ketten (Skripte der anderen Sitzung sind uncommittet und nicht im Paket).
