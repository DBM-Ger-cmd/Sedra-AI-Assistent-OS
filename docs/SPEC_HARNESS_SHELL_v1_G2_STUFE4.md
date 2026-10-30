# SPEC Harness-Shell v1 – G2 Design für Stufe 4 (29.10.2026)

Grundlage: `SPEC_HARNESS_SHELL_v1.md` (G1, §3.4 HS-32, §3.5 HS-40/41/43, §6 Stufe 4), `SPEC_HARNESS_SHELL_v1_G2.md` (Design Stufe 1/2),
`SPEC_HARNESS_SHELL_v1_G2_STUFE3.md` und `…_G3_STUFE3.md` (Stufe 3). Stand des Codes: `main` `ce433c0` (29.10.2026 15:46, Stufe 3 gemerged).
**Captain 29.10.2026 15:53:** G4 Stufe 3 **übernommen**; Stufe 4 und 5 baut **Claude allein** (D-H1 aus Stufe 3 damit beantwortet: kein
SEDRA-Anteil in Stufe 4/5, die Quote wird in Stufe 5 oder später nachgeholt); Lieferung als eigene Fork-Version, am Ende als ZIP.

Dieses Dokument legt fest, **wie** Stufe 4 gebaut wird: das Start-Menü (HS-40), die anderen Oberflächen darin (HS-41), der
Statusbereich statt Instrumentenleiste (HS-32 Rest, HS-43). Nicht hier: Einstellungen und Katalog-Editor (HS-42, Stufe 5).

## 1. Was vorhanden ist und genutzt wird

| Baustein | Stand auf `main` | Nutzung in Stufe 4 |
|---|---|---|
| Taskleiste `taskleiste.js` (Stufe 3, Shell 1.3.0) | links Knopf „Start“ (öffnet heute den Alt+S-Umschalter `.sx-umschalter`), Mitte Sitzungen/Aufgaben/Diff/Läufe, rechts Status aus `/api/strip` (Zellen `decisions`, `model`, `gpu`, `state`), Uhr | Knopf „Start“ öffnet das Start-Menü (HS-30); Status um `ram`, Modellserver und Scheduler-Zustand erweitert (HS-32) |
| Reiter `reiter.js` | Reiter-IDs nach Art: Sitzung `S-…`, `diff:…`, `aufgaben:…`, `lauf:…`; `oeffnen`, `neu`, `schliessen`, `umbenennen`; Arbeitsfläche je Reiter | neue Art `app:<typ>:<id>` – ein Werkzeug des Vertrags in einem Reiter (HS-40 „eine App öffnet als Reiter“) |
| UI-Vertrag `ui/loader.js`, `ui/lifecycle.js` | `ctx.tools.forObject(objekt)`, `ctx.makeContext(manifest, objekt, shellApi)`, `sedraLifecycle.mountTool(mod, el, ctx, onProblem)` / `unmountTool` – so hängen Cockpit (`dock.js`) und Minimal Werkzeuge ein | **dieselben drei Aufrufe**, kein neuer Weg (SHELL_WERKZEUG_VERTRAG_v1) |
| Orte `ui/places.js` | die Liste der Orte mit `object: {type, id, title, view}` und Suchwörtern (Strg+K) | Grundlage der App-Liste: jeder Ort ist eine App; Gruppen kommen aus einer Zuordnung (§3.2) |
| `GET /api/uix/modules` (`modules_view`) | Shells und Werkzeuge mit `id`, `name`, `description`, `kind`, `slot`, `handles`, `enabled`, `preview`; Shell-Standard | Liste der anderen Oberflächen (HS-41) mit Bild; Werkzeuge vom Typ `object`/`panel`, die keinem Ort entsprechen, als weitere Apps |
| Umschalter `ui/wechsel.js` (Alt+S, Vertrag 1.1) | Liste der Shells aus `/api/uix/modules`, Wechsel über `POST /api/uix/shell` (Seite lädt neu), Darstellung Klar/Nacht, Schrift; meldet den Arbeitsstand vorher (`sedraStand`) | der Wechsel läuft weiter über `sedraWechsel` (derselbe Code, derselbe Audit-Eintrag); das Start-Menü ruft ihn, zeigt den Chip aber nicht mehr (§4) |
| Arbeitsstand `ui/stand.js` | offene Objekte je Shell, Übernahme beim Wechsel (höchstens 24) | App-Reiter melden ihr Objekt wie Cockpit-Panes; beim Wechsel in eine andere Oberfläche sind sie dort offen |
| Ablage `GET/POST /api/uix/shelf` | je Shell eine Liste (`uix.shelf.<shell>` in `local_config/uix.yaml`), Audit, kein Gate | „zuletzt benutzte oben“ (HS-40) liegt hier, nicht im Browser – gilt auf jedem Rechner, auch vom Stick |
| Schalter `entwicklung` (`local_switches.py`, S6-E4) | `desk/gateway.py` lädt Prüfwerkzeuge (`zweck: pruefung`) nur mit dem Schalter; ohne ihn stehen sie unter `rejected.pruefung` | Gruppe „Prüfung“ erscheint nur, wenn mindestens ein geladenes Werkzeug `zweck: pruefung` hat – die Shell prüft den Schalter nicht selbst |
| Instrumente `kind: instrument` (9 Stück, `gauge-*`) | Zellen der Cockpit-Leiste, Daten aus `/api/strip` | in der Harness **nie** als Leiste (HS-43); ihre Daten stehen im Statusbereich; die Werkzeuge selbst werden in der Harness nicht eingehängt |
| Hardware-Manager `hardware_manager/manager.py`, `collector.py` | `get_state()` liefert alle ≥ 2 s eine zwischengespeicherte Probe: GPUs aus `nvidia-smi` (**`temperature_core`**, `vram_used`/`vram_total`, Auslastung, Leistung, Lüfter), **Board-Sensoren über LibreHardwareMonitor (WMI `root/LibreHardwareMonitor`: Temperatur, Lüfter, Leistung, Takt)**, RAM `available` (Windows), Platten; Gigabyte-Software wird nur **erkannt** (Inventar, `write_supported: false`), nicht gelesen; thermischer Zustand `NORMAL/WARM/HOT/…` aus den Grenzwerten des Profils | **GPU-Temperatur, VRAM belegt und freier RAM kommen aus genau dieser Probe** – keine neue Messung (HS-32): `strip_view` liest `hardware_manager.get_state()` (§5) |

## 2. Konflikte mit dem vorhandenen Code

| Nr | Konflikt | Entscheidung |
|---|---|---|
| K1 | **Zwei Wege zu anderen Oberflächen:** der Alt+S-Chip (`sedraWechsel`, Vertrag) und das Start-Menü (HS-41 „ersetzt den Mini-Hub“). | Ein Weg für den Nutzer, ein Code für den Wechsel: das Start-Menü zeigt die Oberflächen und ruft `sedraWechsel.wechseln(id)`; der Chip wird in der Harness **nicht gezeichnet** (`shell.yaml`: `umschalter: menue`), **Alt+S öffnet das Start-Menü**. Die anderen Shells bleiben beim Chip. → D-S1 |
| K2 | **Gruppen** (Arbeit, Modelle, Wissen, System, Prüfung) stehen in keinem Manifest (`tool.yaml` hat kein `gruppe`-Feld) und nicht in `places.js`. | Zuordnung in der Shell (`start_gruppen.yaml` im Shell-Ordner, §3.2); ein optionales Manifest-Feld `gruppe` gewinnt, wenn es da ist (Vertrags-Nachtrag N2, rückwärtskompatibel). Nicht zugeordnet → „Arbeit“. → D-S2 |
| K3 | **Was ist eine App?** HS-40 sagt „alle Werkzeuge vom Typ `object`/`panel`“; die Orte in `places.js` sind aber Objekte (ein Werkzeug zeichnet mehrere Orte: `wissen` hat sieben). | Eine App ist ein **Ort** (`places.js`), nicht ein Werkzeug. Werkzeuge `object`/`panel`, zu denen kein Ort führt, bekommen einen Ort aus ihrem ersten `handles`-Typ mit `id: alle` (§3.1), damit nichts fehlt (UIX-10). `talk` (panel) ist in der Harness das Gespräch selbst und keine App. |
| K4 | **Ein Werkzeug im Reiter** braucht den Slot-Begriff des Vertrags (`inhalt` links, `nachweis` rechts). Die Harness hat keine zwei Spalten. | Der App-Reiter zeichnet `inhalt`-Werkzeuge in der Fläche und `nachweis`-Werkzeuge in einer **zuklappbaren rechten Spalte** (Vorgabe zu, Knopf „Nachweise“), wie Minimal „Nachweise zum Umschalten“. Keine Dock-Logik, kein Teilen. |
| K5 | **Shell-Allowlist** (`shell.yaml api:`) kennt `/api/uix/*` nicht; ein eingehängtes Werkzeug ruft seine eigenen Routen über seinen Kontext (eigene Allowlist). | Die Shell nimmt `GET /api/uix/modules`, `GET/POST /api/uix/shelf`, `POST /api/uix/shell` in ihre Liste; die Werkzeuge behalten ihre. |
| K6 | **GPU-Temperatur** (HS-32): `/api/strip` kennt sie nicht, der Hardware-Manager **misst sie schon** (`nvidia-smi temperature.gpu`, Probe alle ≥ 2 s; dazu Board-Sensoren über LibreHardwareMonitor). Die Board-Software von Gigabyte (Control Center/AORUS) hat keine lesbare Schnittstelle – sie wird nur erkannt. | `strip_view` nimmt die Probe des Hardware-Managers (`get_state()`, zwischengespeichert, keine neue Messung). **Reihenfolge der Quelle (Captain 16:28: „über die Board-Software, wenn möglich“):** (1) Board-Sensor über LibreHardwareMonitor, wenn ein Sensor `Temperature` zur GPU gehört (Name enthält `GPU`), (2) sonst `nvidia-smi temperature_core`, (3) sonst keine Temperatur (Zelle zeigt nur VRAM). Hinweis in der Zelle nennt die Quelle (`LHM` / `nvidia-smi`). Läuft LibreHardwareMonitor nicht, sagt der Hinweis das („Board-Sensoren: LibreHardwareMonitor nicht gestartet“) – SEDRA startet nichts. → D-S3 |
| K7 | **Scheduler-Zustand** (D-G7 aus Stufe 3: „Stufe 4 im Statusbereich“). `/api/strip` hat `tasks` (Missionen), aber keinen Scheduler-Eintrag. | Neue Zelle `scheduler` in `/api/strip`: `aus` / `bereit` / `n in Arbeit`, Daten aus dem vorhandenen `model_scheduler`-Zustand (lesend). Ohne Schalter: `aus`, Ton `off`. |
| K8 | **Dateigrenze 400 Zeilen** (Vertrag): `taskleiste.js` 180, `shell.js` nah an der Grenze. | Neue Dateien `startmenue.js` und `app.js`; `taskleiste.js` bekommt nur den Aufruf und die neuen Zellen. |

## 3. Start-Menü (HS-40)

### 3.1 Die App-Liste

Quelle ist `places.js` (`sedraPlaces.alle()`), gefiltert auf Orte, zu denen **mindestens ein geladenes Werkzeug** zeichnet
(`ctx.tools.forObject(ort.object).length > 0`, UIX-10: was kein Werkzeug hat, steht nicht im Menü – aber in „Module“ als
„ohne Werkzeug“). Dazu:

- Werkzeuge `kind: object|panel` aus `/api/uix/modules` (enabled), zu deren `handles`-Typen kein Ort führt: synthetischer Ort
  `{type: <erster handles-Typ>, id: 'alle', title: <name>}`, Gruppe aus §3.2, Hinweis aus `description`.
- Werkzeuge mit `zweck: pruefung` kommen vom Gateway nur mit Schalter `entwicklung`; sind sie da, gibt es die Gruppe „Prüfung“.
- Nie im Menü: `kind: instrument`, `talk`, die Werkzeuge der Harness selbst (Aufgaben, Läufe, Diff sind Reiter, keine Apps).
- Jede App: Symbol (ein Zeichen aus `start_gruppen.yaml`, sonst das der Gruppe), Name, ein Hinweis-Satz, Gruppe.

### 3.2 Gruppen und Reihenfolge (`uix/shells/harness/start_gruppen.yaml`)

```yaml
start:
  gruppen: [arbeit, modelle, wissen, system, pruefung]
  zuordnung:                         # Ort-ID oder Objekttyp -> Gruppe; fehlt beides -> arbeit
    tasks: arbeit      intents: arbeit     decisions: arbeit    project: arbeit    planung: arbeit
    routines: arbeit   org: arbeit         crew: arbeit         gateway: arbeit    labor: arbeit
    models: modelle    slots: modelle      library: modelle     hardware: modelle
    wissen: wissen     wissen-suche: wissen  wissen-quellen: wissen  wissen-vorschlaege: wissen  wissen-eigenes: wissen
    logbook: system    machine: system     modules: system      boundary: system   meter: system
    uebersetzung: arbeit  transkript: arbeit  aufnahme: arbeit
  symbole: {arbeit: '▤', modelle: '◆', wissen: '▣', system: '⚙', pruefung: '✓'}
  zuletzt_max: 6
```

Ein Manifest-Feld `gruppe: modelle` in `tool.yaml` (Vertrags-Nachtrag N2, optional) gewinnt über die Zuordnung. Die Datei liest die
Shell beim Start (`GET` auf die eigene Datei wie `arbeitsplatz.yaml`); eine kaputte Datei ist ein Satz im Menü, kein leeres Menü.

### 3.3 Aufbau und Bedienung

- Öffnet über den Knopf „Start“ (HS-30), **Alt+S** (K1) und das Kommando `start` in der Eingabe (`/start`); schließt mit Esc, Klick außerhalb, Auswahl.
- Oben das **Suchfeld** (Fokus beim Öffnen): trifft Name, Hinweis und die Suchwörter aus `places.js` (dieselben wie Strg+K); Treffer in
  Menü-Reihenfolge, Pfeile/Enter wie die Palette.
- Darunter **„Zuletzt benutzt“** (bis `zuletzt_max`, aus `uix.shelf.harness` → `start.zuletzt`, neueste zuerst), dann die Gruppen in
  der Reihenfolge aus der Datei; leere Gruppen fehlen.
- Unten die Zeile **„Oberflächen“** (§4) und die Zeile **„Darstellung · Schrift“** (ruft die vorhandenen Funktionen aus `sedraWechsel`).
- Ein Klick öffnet die App als Reiter (§3.4) und schreibt sie nach „Zuletzt benutzt“ (`POST /api/uix/shelf {shell: harness, items: …}` –
  gebündelt, höchstens einmal je 2 s, kein Gate, Audit wie bisher).

### 3.4 App-Reiter (`app.js`)

- Reiter-ID `app:<type>:<id>[:<view>]`, Titel = Ort-Titel; ein Ort ist höchstens einmal offen (zweiter Klick aktiviert).
- Beim Aktivieren: `ctx.tools.forObject(objekt)` → `inhalt`-Werkzeuge in die Fläche, `nachweis`-Werkzeuge in die rechte Spalte (K4);
  je Werkzeug `ctx.makeContext(manifest, objekt, shellApi)` und `sedraLifecycle.mountTool(...)`. Beim Schließen `unmountTool` für alle.
- `shellApi.open(objekt)` aus einem Werkzeug (z. B. „Aufgabe öffnen“ aus der Liste) öffnet oder aktiviert den passenden App-Reiter – so,
  wie es der Vertrag verlangt (`ctx.shell.open`), kein zweiter Mechanismus.
- Der Reiter meldet sein Objekt an `sedraStand` (offen/vorn/zu), damit Cockpit, Minimal und Paperclip ihn beim Wechsel übernehmen.
- Fehler eines Werkzeugs (Mount wirft) werden im Reiter als Satz gezeigt („Das Werkzeug ‚…‘ ließ sich nicht öffnen: …“), die Shell läuft weiter (`onProblem`).
- Mehr als **8 App-Reiter** gleichzeitig: der älteste nicht aktive wird geschlossen und das gesagt (Speicher, Vertrag „keine stillen Zustände“).

## 4. Andere Oberflächen (HS-41)

- Zeile „Oberflächen“ im Start-Menü: alle Shells aus `/api/uix/modules` außer `start` und der laufenden, mit Name, Bild (`preview`),
  Markierung „Standard“; Klick → `sedraWechsel.wechseln(id)` (meldet den Stand, `POST /api/uix/shell`, Seite lädt neu).
- „Zum Standard machen“ bleibt im Werkzeug Module (kein Doppel).
- Der Alt+S-Chip wird in der Harness nicht gezeichnet (`shell.yaml`: `umschalter: menue`; `wechsel.js` prüft das Feld, Vorgabe `chip`
  für alle anderen Shells – Vertrags-Nachtrag N3, rückwärtskompatibel). Alt+S ruft `startmenue.oeffnen()`.
- Die Shell `start` (Übersicht) bleibt im Paket, wie sie ist; die Harness verweist nicht auf sie.

## 5. Statusbereich (HS-32 Rest, HS-43)

Zellen rechts in der Taskleiste, Daten **nur** aus `/api/strip` (höchstens alle 2 s, wie heute) und `/api/events`:

| Zelle | Wert | Hinweis (`title`) | Ton | Klick |
|---|---|---|---|---|
| Freigaben | `n` (+ „beim Vorarbeiter m“, wie Stufe 3) | erste wartende Karte | `warn` wenn n > 0 | Posteingang (Reiter Aufgaben/Freigaben) |
| Modell | Rezept-ID oder „keins“ | Kontext | `ok`/`off` | App „Werkstatt: Modelle“ |
| GPU | **Temperatur °C** (Quelle nach K6) · VRAM belegt/gesamt GiB | GPU-Name · Quelle der Temperatur · Sperre · thermischer Zustand des Hardware-Managers | `warn` ab Zustand `WARM` oder fremder Sperre, `bad` ab `HOT` | App „Hardware“ |
| RAM | frei/gesamt GB (**neu** `strip.ram`, aus derselben Probe; sonst „–“) | – | `warn` unter 2 GB frei | App „Hardware“ |
| Modellserver | „bereit“ / „aus“ (**neu** `strip.server`, aus `llama_server`-Zustand, lesend) | Port, Engine-Build | `ok`/`off` | App „Werkstatt: Modelle“ |
| Scheduler | „aus“ / „bereit“ / „n in Arbeit“ (**neu** `strip.scheduler`, K7) | – | `off`/`ok`/`warn` | App „Modelle und Slots“ |
| Zustand | `READY`/`SAFE_MODE` (wie heute) | Fähigkeiten · Audit | `ok`/`warn` | App „Maschinenraum“ |
| Uhr | HH:MM | Datum | – | – |

Regeln: Zellen mit Wert „–“ und Ton `off` werden **ausgeblendet**, nicht leer gezeigt (kleine Bildschirme, Stick an fremdem PC). Blinken
(HS-33) wie in Stufe 3. Keine Instrumente werden eingehängt (HS-43): `gauge-*` bleiben Cockpit-Werkzeuge; ihre Daten sind dieselben
Zellen von `/api/strip`.

## 6. Endpunkte und Ereignisse

| Weg | Methode | Neu/geändert | Zweck |
|---|---|---|---|
| `/api/strip` | GET | **geändert**: Zellen `ram`, `server`, `scheduler` dazu; Zelle `gpu` um Temperatur, VRAM belegt und thermischen Zustand aus `hardware_manager.get_state()` erweitert (zwischengespeicherte Probe, keine neue Messung; fehlt eine Quelle, fehlt der Wert) | Statusbereich |
| `/api/uix/modules` | GET | unverändert | Apps ohne Ort, Oberflächen |
| `/api/uix/shelf` | GET/POST | unverändert; Inhalt `uix.shelf.harness = {start: {zuletzt: [ort-id…]}}` | zuletzt benutzt |
| `/api/uix/shell` | POST | unverändert | Wechsel |

Ereignisse: keine neuen. `tool.*`/`object.open` aus eingehängten Werkzeugen laufen über den vorhandenen Bus; `shellApi.open` → App-Reiter.

## 7. Dateien der Shell (`uix/shells/harness/`, Version 1.4.0)

| Datei | Neu/geändert | Inhalt | Zeilen (Ziel) |
|---|---|---|---|
| `startmenue.js` | neu | Menü: Liste bauen (§3.1), Gruppen (§3.2), Suche, zuletzt, Oberflächen-Zeile, Tastatur | ≤ 320 |
| `app.js` | neu | App-Reiter: mount/unmount, Nachweis-Spalte, `shellApi.open`, Stand melden, Grenze 8 | ≤ 220 |
| `start_gruppen.yaml` | neu | Zuordnung und Symbole (§3.2) | – |
| `taskleiste.js` | geändert | Start → Menü; Zellen RAM, Modellserver, Scheduler; Ausblenden bei „–“ | ≤ 240 |
| `reiter.js` | geändert | Art `app:` (Titel, Schließen ruft `app.schliessen`) | +25 |
| `shell.js` | geändert | Alt+S → Menü, `/start`, `umschalter: menue`, Register der neuen Module | +20 |
| `shell.yaml` | geändert | Version 1.4.0, `entry.js` + `startmenue.js`, `app.js`; `api` + `/api/uix/*` (K5); `umschalter: menue` | – |
| `shell.css` | geändert | Menü, App-Reiter, Nachweis-Spalte – nur Token (Vertrag) | +120 |
| `arbeitsplatz.yaml` | geändert | Satz zum Start-Menü und zu Apps (SEDRA antwortet „Wo finde ich …?“ daraus) | +10 |
| `README.md` | geändert | Stufe 4 | – |
| `ui/wechsel.js` | geändert | Feld `umschalter` lesen (N3); `wechseln(id)` und Darstellung/Schrift als aufrufbare Funktionen exportiert | +15 |
| `ui/places.js` | unverändert | – | – |
| `uix_server.py` | geändert | `strip_view`: `ram`, `server`, `scheduler`; `gpu` aus der Hardware-Manager-Probe (Temperatur mit Quellenreihenfolge K6) | +45 |
| `docs/SHELL_WERKZEUG_VERTRAG_v1.md` | geändert | Nachträge N2 (`gruppe`), N3 (`umschalter`) | – |

## 8. Tests und Abnahme

- `tests/test_uix_harness_start.py` (neu, Gruppe `harness`): App-Liste aus Orten + Werkzeugen (UIX-10: Ort ohne Werkzeug fehlt),
  Gruppen aus Datei und Manifest-Feld, Prüfung-Gruppe nur mit `entwicklung`, Suche trifft Suchwörter, zuletzt über `/api/uix/shelf`
  (nicht im Browser), Grenze 8 Reiter, `umschalter: menue` blendet den Chip aus, Alt+S öffnet das Menü. Reine Teile (Liste bauen,
  gruppieren, suchen) mit `node` wie `test_uix_contract`.
- `tests/test_uix_strip.py` (erweitert): Zellen `ram`, `server`, `scheduler`; ohne Quelle fehlt die Zelle; keine neue Messung
  (Attrappe zählt Aufrufe von `nvidia-smi`/Collector: null).
- `benchmarks/uix_check.py --shell harness`: Marken `hs-start-menue`, `hs-app` dazu; Harness grün; Cockpit/Minimal/Paperclip unverändert grün
  (der Chip bleibt dort).
- Browser-Durchlauf (Playwright, wie Stufe 3 Teil C): Start → Suche „wissen“ → Enter → App-Reiter Wissen → Nachweise auf → Oberfläche
  Cockpit wählen → Cockpit zeigt Wissen offen (Stand übernommen) → zurück in die Harness.
- HS-52: Taskleiste frischt höchstens alle 2 s; Messung im Durchlauf.
- Abnahme-Szenarien (ohne Modell, Attrappe reicht): S4-A Menü vollständig gegen die Liste der geladenen Werkzeuge; S4-B eine App öffnen,
  schließen, wieder öffnen; S4-C Wechsel und zurück mit Übernahme; S4-D Statusbereich an einem PC ohne GPU (Zellen ausgeblendet, kein Fehler).

## 9. Berechtigungen vorab (ENTWICKLUNG.md)

| Nr | Was | Vorschlag |
|---|---|---|
| P4-1 | Schreiben in `runtime/src/guppi_runtime/uix/shells/harness/**`, `uix/ui/wechsel.js`, `uix_server.py` (nur `strip_view`), `tests/test_uix_harness_start.py`, `tests/test_uix_strip.py`, `benchmarks/uix_check.py`, `docs/SPEC_HARNESS_SHELL_v1_G3_STUFE4.md`, `docs/BAUBERICHT_HARNESS_STUFE4_<datum>.md`, `docs/SHELL_WERKZEUG_VERTRAG_v1.md` (Nachträge), Logbuch (anhängen) | ja |
| P4-2 | Befehle: `python benchmarks/run_tests.py uix harness`, `node` für reine Tests, `python benchmarks/uix_check.py --shell <id>` (Playwright, ohne Modell) | ja |
| P4-3 | Kein Modell, kein Lauf, kein Download, kein Push; Lieferung als Fork-ZIP (Captain 15:53) | – |
| P4-4 | Keine Änderung an `local_config/`, `config/`, Katalog, `places.js` | – |

## 10. Fragen an den Captain (Vorschlag jeweils fett)

| ID | Frage | Vorschlag |
|---|---|---|
| D-S1 | **Alt+S in der Harness:** Chip ausblenden und Alt+S öffnet das Start-Menü (ein Weg), oder beides nebeneinander lassen? | **Ein Weg: Menü.** Die anderen Shells behalten den Chip (Vertrag unverändert). |
| D-S2 | **Gruppen:** Zuordnung in `start_gruppen.yaml` der Shell plus optionales Manifest-Feld `gruppe` (Vertrags-Nachtrag N2)? Oder nur die Datei? | **Beides**; das Feld, damit ein neues Werkzeug (auch eins von SEDRA) sich selbst einordnet. Zuordnung aus §3.2 so übernehmen oder ändern. |
| D-S3 | **GPU-Temperatur:** aus der Probe des Hardware-Managers; Reihenfolge Board-Sensor (LibreHardwareMonitor) → `nvidia-smi` → keine. Die Gigabyte-Software selbst ist nicht lesbar (nur erkannt). | **Entschieden (Captain 16:28): über die Board-Software, wenn möglich** – umgesetzt als Reihenfolge in K6. Offen nur: soll die Zelle sagen, wie man LibreHardwareMonitor startet, wenn es fehlt? Vorschlag **ja, ein Satz im Hinweis**. |
| D-S4 | **Apps = Orte** (K3): ein Ort je Eintrag, Werkzeuge ohne Ort bekommen einen; `talk` keine App. | **Ja, so.** |
| D-S5 | **Nachweise im App-Reiter** als zuklappbare rechte Spalte (K4), Vorgabe zu. | **Ja.** Alternative (Nachweise als eigener Reiter) macht den Zusammenhang zum Werkstück unsichtbar. |
| D-S6 | **Grenze 8 App-Reiter**, ältester nicht aktiver wird mit Satz geschlossen. | **8.** |
| D-S7 | **Zuletzt benutzt** in `uix.shelf.harness` (Rechner-weit, Audit, kein Gate) statt im Browser. | **Ja** – gilt auf jedem PC und vom Stick. |
| D-S8 | **Shell `start`** bleibt im Paket (für die anderen Shells und `START_SEDRA --uebersicht`); die Harness zeigt sie nicht. | **Ja.** Entfernen erst mit dem Stick-Plan (dort entschieden). |

Nach deinen Antworten tragen wir die Entscheidungen hier ein und schreiben G3 (Bau-Aufgaben N1 bis N8 mit Tests); erst dann beginnt der Bau.

## 11. Entscheidungen des Captains

- **D-S3** (29.10.2026 16:28): GPU-Temperatur über die Board-Software, wenn möglich → Quellenreihenfolge K6 (LibreHardwareMonitor-Sensor, sonst nvidia-smi, sonst keine).
- **D-S1, D-S2, D-S4 bis D-S8** (29.10.2026 16:31, Captain: „okay, machen wir weiter“ – gelesen als „Ja, wie vorgeschlagen“): ein Weg über das Menü, Alt+S öffnet es; Gruppen aus Datei plus Manifest-Feld `gruppe` (N2); Apps = Orte; Nachweise als zuklappbare Spalte; Grenze 8; zuletzt in `uix.shelf.harness`; Shell `start` bleibt. LHM-Hinweis: ein Satz, wie man es startet.

G2 Stufe 4 ist damit freigegeben; Bau-Aufgaben: `SPEC_HARNESS_SHELL_v1_G3_STUFE4.md`.
