# SPEC Apps v1 – AM1 Leistenzellen und Verfügbarkeit je Shell – G2 Design (03.11.2026)

Grundlage: `docs/SPEC_APPS_v1_AM1_ZELLEN_UND_SHELLS.md` (G1), freigegeben vom Captain am 03.11.2026 mit allen Entscheidungen wie vorgeschlagen (AM1-E1 Vorgabe-Leiste unverändert, AM1-E2 Auswahl in `leiste.json`, AM1-E3 kein Einklappen in AM1).
Nichts gebaut; diese Datei ist G2. Pfade relativ zu `runtime/src/sedra_runtime/`, Zeilen für c364081.

## 0. Was G2 im Code geklärt hat

| Punkt | Ergebnis | Beleg |
|---|---|---|
| Wo die Allowlist geprüft wird | `Gateway.allowed` lädt die Module über `_load`, **nicht** über `manifest()`. Ein Filter nach Shell in `manifest()` ändert die Allowlist also nicht – so wie G1 es verlangt (Sichtbarkeit, keine Sicherheitsgrenze). | `desk/gateway.py:408–418` |
| Öffentliche Felder des Manifests | `manifest()` gibt jedes Feld des geprüften Manifests weiter außer `api`, `js`, `css` (die werden neu gesetzt). Neue Felder `shells`, `zelle` kommen ohne weitere Änderung bei den Shells an, sobald `check_tool` sie zurückgibt. | `desk/gateway.py:343–351` |
| Rahmenseite | `frame_page` sucht das Werkzeug in `manifest()['tools']`; ein in der aktiven Shell nicht verfügbares Werkzeug bekommt damit 404 für seine Rahmenseite. Gewollt. | `desk/gateway.py:365–371` |
| Feld der Instrumente im Code | sieben Instrumente haben `field: '<name>'`; `gauge-slots` und `gauge-wissen` lesen `reading.slots` bzw. `reading.wissen` ohne dieses Feld. | `uix/tools/gauge-*/tool.js` |
| Beschriftungen | Cockpit und Harness beschriften zwei Werte **verschieden**: `decisions` heißt im Cockpit „Entscheidungen“, in der Harness „Freigaben“; `state` heißt „SEDRA“ bzw. „Zustand“. | `gauge-decisions/tool.js:29`, `gauge-state/tool.js:33`, `taskleiste.js:15–16` |
| Klick der Online-KI-Zelle | `gauge-cloud` öffnet keinen Ort, sondern schaltet das Gespräch zwischen lokal und Cloud um. | `gauge-cloud/tool.js:1–2, 19` |
| Tests, die an der Leiste hängen | Browser-Test und Abnahme suchen Zellen über `data-zelle="decisions"` bzw. `"state"` – der Wert ist der **Feldname** aus `/api/strip`. | `runtime/tests/test_uix_harness_browser.py:150`; `runtime/benchmarks/harness_abnahme_stufe5.py:52` |
| Einstellungsseiten | `einstellungen.oeffnen(S, punkt)` nimmt `<gruppe>` oder `<gruppe>/<punkt>`; Gruppen: `allgemein`, `agent`, `sprache`, `integrationen`, `modelle`, `system`. | `shells/harness/einstellungen.js:20–26, 40–46` |
| Wie die Harness Dateien ihres Ordners liest | `startmenue.js` lädt `start_gruppen.json` mit `fetch` direkt (statische Datei unter `/uix/`, kein Token nötig). | `shells/harness/startmenue.js:12, 22` |
| Vertragsversion | `UI_VERSION = (1, 0)`. | `desk/gateway.py:22` |
| Schema | `ui/schema/tool.schema.json` mit `additionalProperties: false`. | `ui/schema/tool.schema.json:10` |

Folgerung für den Entwurf: `zelle.label` ist die Beschriftung für **Datenzellen** (Shells, die die Zelle selbst zeichnen – heute nur die Harness). Das Cockpit zeichnet weiter mit dem Code des Instruments und behält seine Wörter. AM1 vereinheitlicht die Wörter nicht (§9, AM1-G2-E1).

## 1. Teil A – Manifest (AM1-01 bis AM1-06)

**`desk/gateway.py`:**
- `UI_VERSION = (1, 1)`. Bestehende Manifeste mit `needs.ui: ">=1.0 <2"` bleiben gültig.
- `TOOL_KEYS` um `shells`, `zelle` erweitern.
- Prüfung `shells`: Liste mit 1–20 Einträgen, jeder nach `MODULE_ID`, keine Dopplung → sonst `shells_invalid`. Unbekannte Shell-IDs sind kein Fehler; `manifest()` liefert sie unter `warnungen: [{id, grund: 'shells_unbekannt:<shell>'}]`.
- Prüfung `zelle` (nur `kind: instrument`, sonst `zelle_nur_fuer_instrument`):

| Schlüssel | Regel | Fehler |
|---|---|---|
| `feld` | Pflicht, `^[a-z][a-z0-9_]{1,30}$` | `zelle_feld_invalid` |
| `label` | Pflicht, Text 1–20 Zeichen | `zelle_label_invalid` |
| `ort` | optional, ID aus `chat_tools.PLACES` (dieselben IDs wie `ui/places.js`) | `zelle_ort_unbekannt` |
| `aktion` | optional: `freigaben`, `modellmenue`, `routermenue` oder `einstellungen:<gruppe>[/<punkt>]` (`^einstellungen:[a-z]+(/[a-z]+)?$`) | `zelle_aktion_invalid` |
| andere | – | `zelle_unbekannt:<schlüssel>` |

- Rückgabe von `check_tool`: zusätzlich `'shells': list | None`, `'zelle': dict | None`.
- `manifest()`: nach dem Filter für `disabled` und `pruefung` (`:336–339`) zusätzlich `verfuegbar = t.shells is None or active in t.shells`; nicht verfügbare stehen in `nicht_in_dieser_shell: [{id, name, shells}]`.
- `modules_view` (`uix_server.py:487ff`) gibt `shells` und `zelle` je Werkzeug mit aus.
- `aktion` ist ein **Hinweis an Shells, die Datenzellen zeichnen**; eine Shell, die eine Aktion nicht kennt, nutzt `ort`. Das steht so im Vertrag (Nachtrag, §6).

**`ui/schema/tool.schema.json`:** dieselben zwei Eigenschaften mit denselben Regeln.

**Gleichheit Code ↔ Manifest (AM1-06):** `gauge-slots` und `gauge-wissen` bekommen die Eigenschaft `field` (`'slots'`, `'wissen'`) und lesen darüber; danach haben alle Instrumente des Pakets `field`. Ein Test liest `field` aus jeder `tool.js` (Muster `field: '<name>'`) und vergleicht mit `zelle.feld`.

## 2. Teil B – Instrumente (AM1-07)

| Instrument | `zelle` (neu) | `shells` |
|---|---|---|
| `gauge-decisions` | `{feld: decisions, label: "Freigaben", aktion: freigaben}` | – |
| `gauge-model` | `{feld: model, label: "Modell", ort: models, aktion: modellmenue}` | – |
| `gauge-gpu` | `{feld: gpu, label: "GPU", ort: hardware}` | – |
| `gauge-state` | `{feld: state, label: "Zustand", ort: machine, aktion: "einstellungen:system"}` | – |
| `gauge-tasks` | `{feld: tasks, label: "Aufgaben", ort: tasks}` | – |
| `gauge-cloud` | `{feld: cloud, label: "Online-KI"}` (kein Ort: der Klick schaltet im Cockpit das Gespräch um) | – |
| `gauge-mode` | `{feld: mode, label: "Modus", ort: boundary}` | – |
| `gauge-slots` | `{feld: slots, label: "Slots", ort: slots}` | – |
| `gauge-wissen` | `{feld: wissen, label: "Wissen", ort: wissen}` | – |
| **neu** `gauge-ram` | `{feld: ram, label: "RAM", ort: hardware}` | `[harness]` |
| **neu** `gauge-server` | `{feld: server, label: "Modellserver", ort: models, aktion: routermenue}` | `[harness]` |
| **neu** `gauge-scheduler` | `{feld: scheduler, label: "Scheduler", ort: slots}` | `[harness]` |

Die Labels für die Harness sind die heutigen Wörter aus `ZELLEN` (`taskleiste.js:15–16`); für die vier Instrumente, die die Harness heute nicht zeigt, das Wort aus ihrem Code.

**Die drei neuen Instrumente** (`uix/tools/gauge-ram|server|scheduler/`): `tool.yaml` (`kind: instrument`, `handles: []`, `order` 17/18/19, `api: []`, `events.listens: [system.state]`, `trust: CORE`, `needs.ui: ">=1.1 <2"`, `shells: [harness]`, `zelle` wie oben), `tool.js` nach dem Muster von `gauge-gpu` (`mount`, `update(reading, problem)`, `unmount`, `summary`, `field`), `README.md` (Vertrag: eine README je Modul). Die Harness hängt ihren Code nicht ein (Datenzelle); der Lader lädt ihr Skript trotzdem, weil sie CORE sind (`ui/loader.js:164–170`). Kosten: drei kleine Skripte.

## 3. Teil C – Harness-Leiste (AM1-08 bis AM1-15)

**`shells/harness/leiste.json`:**
```json
{"_hinweis": "Taskleiste der Harness-Shell (SPEC_APPS_v1_AM1): welche Instrumente als Zelle erscheinen und in welcher Reihenfolge. Die Token-Zelle gehört der Shell und steht immer an zweiter Stelle.",
 "zellen": ["gauge-decisions", "gauge-model", "gauge-gpu", "gauge-ram", "gauge-server", "gauge-scheduler", "gauge-state"]}
```

**Neue Datei `shells/harness/zellen.js`** (rein, ≤ 400 Zeilen, Node-tauglich):
```js
// zellenAusManifest(instrumente, auswahl) → {zellen: [{id, feld, label, ort, aktion}], fehlend: [id], ohneZelle: [id]}
//   instrumente: die Manifeste mit kind 'instrument' (aus S.ctx.tools.byKind('instrument')), nur trust 'CORE' (AM1-17)
//   auswahl: leiste.json; Reihenfolge = auswahl.zellen
// pruefeAuswahl(roh) → {zellen: [...]} oder wirft mit Satz (wie startliste.zuordnungPruefen)
// ZELLEN_RUECKFALL: die heutige Liste aus taskleiste.js als [{feld, label, ort, aktion}]
```

**`shells/harness/taskleiste.js`:**
- `mount`: lädt `leiste.json` einmal (`fetch`, wie `startmenue.js`), baut `S._leiste.zellen` mit `zellenAusManifest`. Bei Fehler (Datei fehlt, unlesbar, Ergebnis leer) → `ZELLEN_RUECKFALL` und **eine** Meldung über `S.ctx.onProblem('Taskleiste', …)` mit Satz „Leiste aus der eingebauten Liste: <Grund>“.
- `status`: statt `ZELLEN.filter(([k]) => …)` über `S._leiste.zellen` mit `z.feld`; `zelle.dataset.zelle = z.feld` (unverändert für Tests und Abnahme).
- Klick: `aktion` vor `ort`. `freigaben` → `freigabenZelle` (heute an `k === 'decisions'`), `modellmenue` → `modell.menue(S)`, `routermenue` → `modell.routerMenue(S)`, `einstellungen:<x>` → `einstellungen.oeffnen(S, x)`, sonst `ort` → `app.oeffnen(S, PLACES.find(…))`. Die Tooltip-Zusätze für Modell und Modellserver (`taskleiste.js:188`) hängen an der Aktion statt am Schlüssel.
- Token-Zelle: unverändert an Position 2 (`:200`).
- Das Datei-Limit von 400 Zeilen bleibt eingehalten (heute 235 Zeilen).

**`shells/harness/shell.yaml`:** `zellen.js` in `entry.js` vor `taskleiste.js`; `version` 1.9.0 → 1.10.0.

**Leerzustand (AM1-04):** In AM1 nur in der Harness: `app.oeffnen` (`shells/harness/app.js:77`) findet keinen Zeichner → Hinweis „In dieser Oberfläche nicht verfügbar – verfügbar in: <Shells>“ aus `nicht_in_dieser_shell`. Die anderen Shells behalten ihren Leerzustand; das ist eine Einschränkung gegenüber G1 (AM1-04 sprach von „einer Shell“ allgemein) und wird mit AM2 nachgezogen.

## 4. Teil D – Cockpit und Rahmen unverändert (AM1-16)

Keine Code-Änderung in `shells/cockpit/strip.js` und `ui/frame.js`. Durch `shells: [harness]` bekommen sie die drei neuen Instrumente nicht. Nachweis: Test über `Gateway.manifest()` mit aktiver Shell `cockpit` – die Liste der Instrumente ist vorher und nachher gleich (die neun `gauge-*`; `rahmen-probe` nur mit Schalter `entwicklung`).

## 5. Tests

| Datei | Prüft |
|---|---|
| neu `tests/test_apps_am1_manifest.py` | Schema `shells`/`zelle` (gültig, jede Fehlermeldung), `shells_unbekannt` als Warnung, Filter in `manifest()` mit zwei Shells, `nicht_in_dieser_shell`, Allowlist unverändert (`allowed` für ein nicht verfügbares Werkzeug wie vorher), `field` = `zelle.feld` für alle Instrumente, Cockpit-Instrumente vorher = nachher |
| neu `tests/test_apps_am1_leiste.py` (Node über `run_js`) | `zellenAusManifest` mit den echten Manifesten und der echten `leiste.json` ergibt **genau** die heutige Liste: `decisions/Freigaben/–/freigaben`, `model/Modell/models/modellmenue`, `gpu/GPU/hardware`, `ram/RAM/hardware`, `server/Modellserver/models/routermenue`, `scheduler/Scheduler/slots`, `state/Zustand/machine/einstellungen:system`; fehlendes Instrument → `fehlend`; Nicht-CORE wird übergangen; `pruefeAuswahl` mit kaputter Datei wirft mit Satz; `ZELLEN_RUECKFALL` = heutige `ZELLEN` |
| bestehend `tests/test_uix_harness_shell.py` | Dateiliste der Shell um `zellen.js`, `leiste.json` ergänzen (`:28`) |
| bestehend `tests/test_uix_harness_browser.py` | `data-zelle="decisions"` mit `.neu` (`:150`) bleibt grün |
| bestehend `benchmarks/harness_abnahme_stufe5.py` | Klick auf `data-zelle="state"` öffnet Einstellungen → System (`:52–53`) |
| `benchmarks/uix_check.py --shell harness` | bei 1024×700 und 1400×860 ohne Konsolenfehler, Leiste vorhanden |
| `test_uix_contract.py` | alle Manifeste gültig, README je Modul, ≤ 400 Zeilen |

## 6. Reihenfolge für G3

| Nr | Aufgabe | Dateien |
|---|---|---|
| T1 | Schema und Prüfung `shells`, `zelle`; `UI_VERSION` 1.1; Filter in `manifest()`; `modules_view` | `desk/gateway.py`, `ui/schema/tool.schema.json`, `uix_server.py` |
| T2 | `field` für `gauge-slots`, `gauge-wissen`; `zelle` in neun Manifesten | `uix/tools/gauge-*` |
| T3 | drei neue Instrumente | `uix/tools/gauge-ram|server|scheduler/` |
| T4 | `zellen.js`, `leiste.json`, Umbau `taskleiste.js`, `shell.yaml` | `uix/shells/harness/` |
| T5 | Leerzustand Harness | `uix/shells/harness/app.js` |
| T6 | Vertrag: Nachtrag „Felder `shells` und `zelle` (Vertrag 1.1)“ | `docs/SHELL_WERKZEUG_VERTRAG_v1.md` |

Jede Aufgabe mit ihren Tests aus §5; T4 erst nach T1–T3.

**Berührung mit AM0:** AM0-01 setzt `uix/**` unter einen harten Vorbehalt. Wird AM1 **über die Harness** gebaut, braucht jede Datei eine Karte. Wird es von Claude direkt im Repo gebaut (wie bisherige Stufen), betrifft der Vorbehalt den Bau nicht. Reihenfolge AM0/AM1 deshalb frei.

## 7. Rückfall

`ZELLEN_RUECKFALL` in der Harness (automatisch bei Fehlern). `shells` fehlt = alle Shells. Ganz zurück: `leiste.json` löschen → Rückfall-Liste = heutige Leiste.

## 8. Risiken

- Die Harness lädt eine weitere Datei beim Start (`leiste.json`); schlägt das fehl, greift der Rückfall – sichtbar über `onProblem`.
- Wer `leiste.json` ändert, kann die Freigaben-Zelle herausnehmen. AM2 macht sie zur Grundfunktion (immer da); bis dahin ist das möglich und dokumentiert.
- `UI_VERSION` 1.1: Ein Modul, das `needs.ui: "==1.0"` sagt, würde nicht mehr laden. Im Paket gibt es keins (alle `">=1.0 <2"`; Test über alle Manifeste); unter `local_config/` auf dem PC nicht bekannt.

## 9. Offen

| Nr | Frage | Vorschlag |
|---|---|---|
| AM1-G2-E1 | Beschriftungen von Cockpit und Harness vereinheitlichen („Entscheidungen“/„Freigaben“, „SEDRA“/„Zustand“)? | nicht in AM1; eigener kleiner Punkt nach AM2 |

## 10. Berechtigungen vorab (für G3)

Schreiben in `desk/gateway.py`, `uix_server.py` (nur `modules_view`), `ui/schema/tool.schema.json`, `uix/tools/gauge-*` und drei neue Ordner, `uix/shells/harness/{zellen.js, leiste.json, taskleiste.js, app.js, shell.yaml}`, `docs/SHELL_WERKZEUG_VERTRAG_v1.md`, Tests. Nicht: andere Shells, `/api/strip`, `local_config/`.

## 11. Nächste Gates

G2 (diese Datei) → Freigabe durch den Captain → G3 T1–T6 → G4 Abnahme am PC: Leiste sieht aus wie vorher; eine geänderte `leiste.json` (z. B. `gauge-tasks` dazu) zeigt die Zelle ohne Codeänderung; im Cockpit keine neuen Zellen.
