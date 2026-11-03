# SPEC Apps v1 – AM1: Leistenzellen aus dem Manifest, Verfügbarkeit je Shell (03.11.2026)

Status: **G1 freigegeben** (03.11.2026, Entscheidungen wie vorgeschlagen); **G2** in `docs/SPEC_APPS_v1_AM1_G2.md`. Nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11.
Ziel: Die Taskleiste der Harness-Shell entsteht aus den Manifesten der Instrumente, wie es Cockpit und Rahmen-Shells schon tun. Dazu das Manifestfeld `shells`, damit ein Instrument (und später jede App) nur in bestimmten Shells erscheint. Nur Paket-Instrumente (CORE).
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Befund

| Nr | Befund | Beleg |
|---|---|---|
| B1 | Cockpit und Rahmen-Shells bauen ihre Leiste aus allen Werkzeugen mit `kind: instrument`, hängen jedes Instrument in eine Zelle (`mountTool`) und reichen ihm die Antwort von `/api/strip` über `update(reading, problem)`. | `shells/cockpit/strip.js:16–24, 37–47`; `ui/frame.js:146, 167` |
| B2 | Die Harness-Shell nutzt das nicht. Sie hat eine feste Liste `ZELLEN` (Schlüssel, Beschriftung, Ort), liest `/api/strip` selbst und zeichnet die Zellen selbst. | `shells/harness/taskleiste.js:15–16, 168–198` |
| B3 | Welches Feld von `/api/strip` ein Instrument zeigt, steht nur in seinem Code (`field: 'gpu'`), nicht im Manifest. | `tools/gauge-gpu/tool.js` (`field`) |
| B4 | Es gibt neun Instrumente (`gauge-state` 10, `-model` 11, `-gpu` 12, `-cloud` 12, `-decisions` 13, `-tasks` 14, `-mode` 15, `-wissen` 16, `-slots` 60; Zahl = `order`) und das Prüfwerkzeug `rahmen-probe` (990, `zweck: pruefung`, `trust: CAPTAIN`). | `uix/tools/gauge-*/tool.yaml`, `rahmen-probe/tool.yaml` |
| B5 | Drei Zellen der Harness-Leiste haben **kein** Instrument: `ram`, `server`, `scheduler`. Ihre Werte liefert `/api/strip` nur, wenn es die Quelle gibt. | `uix_server.py:1747–1777` (`_ram_zelle`, `_server_zelle`, `_scheduler_zelle`) |
| B6 | Fünf Instrumente erscheinen in der Harness-Leiste **nicht**, obwohl `/api/strip` ihre Werte liefert: `tasks`, `cloud`, `mode`, `slots`, `wissen`. | `taskleiste.js:178` filtert gegen `ZELLEN` |
| B7 | Die Harness-Leiste hat **Sonderfälle**: `decisions` (Zähler „· beim Vorarbeiter m“, Markierung neuer Freigaben), `model` (Modell-Menü), `server` (Router-Menü), `state` (öffnet Einstellungen → System), dazu die **Token-Zelle** aus Sitzungsdaten des Browsers, eingefügt an Position 2. | `taskleiste.js:183–197, 160–165, 196` |
| B8 | Die Reihenfolge der Harness-Leiste folgt der Liste, nicht `order` (Freigaben zuerst, `order` 13). | `taskleiste.js:15`, `gauge-decisions/tool.yaml` |
| B9 | Ein Manifest kann nicht sagen, in welchen Shells es erscheint. Neue Instrumente für RAM usw. würden sofort auch im Cockpit erscheinen. | `desk/gateway.py:63` (`TOOL_KEYS` ohne `shells`) |
| B10 | Instrumente im Rahmen (Nicht-CORE) bekommen im Cockpit eine Zelle mit iframe, aber kein `update(reading)`: die Brücke kennt dafür keine Nachricht. | `ui/lifecycle.js:39–41`, `ui/bruecke.js:11` |

## 2. Anforderungen

### 2.1 Feld `shells` (Verfügbarkeit)

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM1-01 | `tool.yaml` darf `shells: [<shell-id>, …]` tragen (Muster `^[a-z0-9-]{2,40}$`, 1–20 Einträge, keine Dopplung). Fehlt das Feld, ist das Werkzeug in allen Shells verfügbar (heutiges Verhalten). | Schema-Test |
| AM1-02 | Eine unbekannte Shell-ID ist **kein** Fehler (auf dem USB-Stick fehlen Shells, `docs/ENTSCHEIDUNGEN_USB_STICK.md:8`), aber eine Warnung im Werkzeug „Module“ (`shells_unbekannt:<id>`). | Test |
| AM1-03 | `GET /uix/manifest` liefert in `tools` nur Werkzeuge, die in der aktiven Shell verfügbar sind; die übrigen stehen in einer neuen Liste `nicht_in_dieser_shell` (nur `id`, `name`). Die Routen-Allowlist des Servers bleibt davon unberührt (Sichtbarkeit, keine Sicherheitsgrenze; Konzept §5.1). | Test mit zwei Shells |
| AM1-04 | Öffnet eine Shell ein Objekt, dessen Werkzeug hier nicht verfügbar ist, zeigt sie ihren Leerzustand mit dem Satz „In dieser Oberfläche nicht verfügbar – verfügbar in: <Shells>.“ | uix_check |

### 2.2 Feld `zelle`

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM1-05 | Ein Werkzeug mit `kind: instrument` darf `zelle: {feld, label, ort?, aktion?}` tragen. `feld`: Schlüssel in der Antwort von `/api/strip` (`^[a-z][a-z0-9_]{1,30}$`). `label`: 1–20 Zeichen. `ort`: ID eines Ortes (`ui/places.js`). `aktion`: eine von `freigaben`, `modellmenue`, `routermenue`, `einstellungen:<seite>` (`<seite>` aus der Liste der Einstellungsseiten der Harness). `zelle` an einem anderen `kind` → `zelle_nur_fuer_instrument`. | Schema-Test |
| AM1-06 | Bei Paket-Instrumenten muss `zelle.feld` mit dem `field` im Code übereinstimmen. | Test liest `tool.js` je Instrument |
| AM1-07 | Alle neun `gauge-*` bekommen `zelle`. Neu im Paket: `gauge-ram`, `gauge-server`, `gauge-scheduler` (CORE, `kind: instrument`, `api: []`, `shells: [harness]`, `tool.js` mit `update` wie die übrigen). | Schema-Test; Test „jede Zelle der alten `ZELLEN` hat ein Instrument“ |

### 2.3 Harness-Leiste aus Manifesten

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM1-08 | Die Harness-Shell bekommt eine Datei `shells/harness/leiste.json` `{zellen: [<instrument-id>, …]}`: **Auswahl und Reihenfolge**. Vorgabe = heutige Leiste: `gauge-decisions`, `gauge-model`, `gauge-gpu`, `gauge-ram`, `gauge-server`, `gauge-scheduler`, `gauge-state`. JSON, weil die Seite nur js/css/json/svg/png/html ausliefert (wie `start_gruppen.json`). | Test |
| AM1-09 | Die reine Funktion `zellenAusManifest(instrumente, auswahl)` (neue Datei `shells/harness/zellen.js`, ≤ 400 Zeilen) liefert `[{id, feld, label, ort, aktion}]` in der Reihenfolge der Auswahl; Instrumente, die nicht verfügbar oder nicht ausgewählt sind, fehlen; ein ausgewähltes, aber fehlendes Instrument wird übersprungen und einmal gemeldet. | Node-Test |
| AM1-10 | `taskleiste.js` zeichnet aus dieser Liste. Die Zelle bleibt **Datenzelle**: die Shell zeichnet Beschriftung, Wert und Ton selbst; der Code des Instruments wird in der Harness nicht eingehängt. Begründung: einheitliches Aussehen der Leiste, und dieselbe Regel gilt später für fremde Zellen (AM3). | Test der Shell |
| AM1-11 | Klick: `aktion` vor `ort`. `freigaben` = heutiges Verhalten der Freigabe-Zelle, `modellmenue`/`routermenue` = heutige Menüs, `einstellungen:<seite>` öffnet die Seite. Ohne `aktion` öffnet `ort` die App (`app.oeffnen`). | Test je Aktion |
| AM1-12 | HS-32 bleibt: Eine Zelle ohne Wert (`–` und Ton `off`) wird ausgeblendet. | bestehender Test |
| AM1-13 | Die **Token-Zelle** bleibt eine Zelle der Shell (Daten aus der Sitzung im Browser, nicht aus `/api/strip`), an derselben Stelle wie heute. Sie ist eine benannte Ausnahme, kein Instrument. | Test |
| AM1-14 | **Rückfall**: Liefert das Manifest keine Instrumente oder scheitert `zellenAusManifest`, nutzt die Leiste die eingebaute Liste `ZELLEN_RUECKFALL` (= heutige `ZELLEN`) und meldet es über `onProblem`. | Test |
| AM1-15 | **Gleichheit**: Mit der Vorgabe-Auswahl ist die gezeichnete Leiste in Schlüssel, Beschriftung, Klickziel und Reihenfolge **identisch** zu heute. | Gold-Test gegen eine aufgezeichnete Fassung von heute |
| AM1-16 | Cockpit und Rahmen-Shells ändern sich nur durch `shells`: `gauge-ram`/`-server`/`-scheduler` erscheinen dort nicht; alle übrigen Zellen bleiben. | Test: Zellenliste Cockpit vorher = nachher |
| AM1-17 | Nicht-CORE-Instrumente erscheinen in der Harness-Leiste in AM1 **nicht** (fremde Zellen: AM3). | Test |

## 3. Entwurf

```yaml
# uix/tools/gauge-gpu/tool.yaml (Ausschnitt, neu)
  zelle: {feld: gpu, label: "GPU", ort: hardware}
# uix/tools/gauge-decisions/tool.yaml
  zelle: {feld: decisions, label: "Freigaben", aktion: freigaben}
# uix/tools/gauge-model/tool.yaml
  zelle: {feld: model, label: "Modell", ort: models, aktion: modellmenue}
# uix/tools/gauge-server/tool.yaml (neu)
  shells: [harness]
  zelle: {feld: server, label: "Modellserver", ort: models, aktion: routermenue}
# uix/tools/gauge-state/tool.yaml
  zelle: {feld: state, label: "Zustand", ort: machine, aktion: "einstellungen:system"}
```
- `desk/gateway.py`: `TOOL_KEYS` um `shells`, `zelle` erweitern; Prüfungen; `manifest()` filtert nach `cfg['shell']`; öffentliche Felder enthalten `zelle` und `shells`.
- `ui/schema/tool.schema.json`: dieselben Felder.
- Version: `needs.ui` bleibt `>=1.0 <2` für bestehende Werkzeuge; der Vertrag wird 1.1 (`UI_VERSION`), neue Felder setzen `>=1.1` voraus.
- Harness: `zellen.js` (rein), `leiste.json`, `taskleiste.js` nutzt beides; `ZELLEN` wird `ZELLEN_RUECKFALL`.
- Die Leiste wird nicht gemessen und eingeklappt wie im Cockpit (`ui/leiste.js`, „+n ▾“); das bleibt eine eigene Entscheidung (AM1-E3).

## 4. Tests und Abnahme

`tests/test_apps_am1_manifest.py` (Schema, Filter, Gleichheit `field`/`feld`), Node-Test `zellen.test.js`, Gold-Test der Harness-Leiste, Vergleich der Cockpit-Leiste vorher/nachher, `uix_check` Harness bei 1024×700 und 1400×860. Abnahme am PC: Leiste sieht aus wie vorher; eine geänderte `leiste.json` (z. B. `gauge-tasks` dazu) zeigt die Zelle ohne Codeänderung.

## 5. Rückfall

`ZELLEN_RUECKFALL` in der Shell (AM1-14). `shells` ohne Angabe = alle Shells. Die neuen Instrumente sind mit `shells: [harness]` außerhalb der Harness unsichtbar.

## 6. Abgrenzung

Keine fremden Zellen (AM3). Keine Änderung an `/api/strip` außer dass die drei Harness-Felder dort schon heute stehen. Kein Einklappen „+n“ in der Harness. Keine Orte aus Manifesten (AM2).

## 7. Risiken

- Kleine Abweichungen im Aussehen (Reihenfolge, Abstand, Tooltip) – durch den Gold-Test abgefangen.
- `shells` verführt dazu, Werkzeuge zu verstecken, die eine Grundfunktion sind. Schutz kommt mit AM2 (Grundfunktionen ignorieren `shells`).

## 8. Entscheidungen des Captains

**Entschieden vom Captain am 03.11.2026: alle Vorschläge dieser Tabelle übernommen.**

| Nr | Frage | Vorschlag |
|---|---|---|
| AM1-E1 | Soll die Harness-Leiste mehr Zellen zeigen (Aufgaben, Online-KI, Modus, Slots, Wissen)? | Vorgabe unverändert; der Captain ergänzt in `leiste.json` |
| AM1-E2 | Auswahl in `leiste.json` (Datei der Shell) oder als Feld in `shell.yaml`? | `leiste.json` (wie `start_gruppen.json`); `shell.yaml` bleibt Vertrag |
| AM1-E3 | Einklappen „+n ▾“ auch in der Harness? | später, eigener Punkt |

## 9. Berechtigungen vorab

Schreiben in `desk/gateway.py`, `ui/schema/tool.schema.json`, `uix/tools/gauge-*` (neu: drei Ordner), `uix/shells/harness/{taskleiste.js, zellen.js, leiste.json}`; Tests. Nicht: andere Shells außer Testvergleich, `/api/strip`.

## 10. Nächste Gates

G1 → G2 (genaue Darstellung der Sonderzellen, Liste der Einstellungsseiten) → G3 → G4 am PC.
