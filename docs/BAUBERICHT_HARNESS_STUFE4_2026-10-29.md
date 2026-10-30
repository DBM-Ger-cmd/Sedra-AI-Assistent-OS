# Baubericht Harness-Shell Stufe 4 – Start-Menü, Apps, Statusbereich (29.10.2026)

Spec: `SPEC_HARNESS_SHELL_v1.md` (G1 §3.4, §3.5), `SPEC_HARNESS_SHELL_v1_G2_STUFE4.md` (G2, freigegeben 16:31), `SPEC_HARNESS_SHELL_v1_G3_STUFE4.md`
(G3, freigegeben 16:40). Grundlage `main` `ce433c0`; Branch `harness/stufe-4` (lokal, kein Push – Lieferung als Fork-ZIP, Captain 15:53).
Baut: **Claude allein** (Captain 15:53). Gebaut 16:40 bis 17:30 in der Cloud-Sitzung (Linux, kein Modell, keine GPU, kein LibreHardwareMonitor).

## 1. Was gebaut ist (N1 bis N9)

| Nr | Ergebnis | Dateien |
|---|---|---|
| N1 | Vertrags-Nachträge **N2** (`gruppe` in `tool.yaml`) und **N3** (`umschalter: chip\|menue` in `shell.yaml`); Gateway prüft beide (`gruppe_invalid`, `umschalter_invalid`); `modules_view` gibt `gruppe`, `zweck`, `umschalter` mit aus. `ui/wechsel.js`: `modus()`, `menueHaken()`, `wechseln()`, `uebersicht()`, `leeren()` exportiert; bei `menue` kein Chip, kein Mini-Hub, Alt+S ruft den Haken. Schemas nachgezogen. | `desk/gateway.py`, `uix_server.py`, `ui/wechsel.js`, `ui/schema/*.json`, `docs/SHELL_WERKZEUG_VERTRAG_v1.md`, `tests/test_desk_gateway.py`, `tests/test_uix_harness_start.py` |
| N2 | `/api/strip`: Zellen `ram`, `server`, `scheduler`; `gpu` mit `temperatur`, `quelle` (`LHM` / `nvidia-smi`), `vram_belegt`, `thermisch`. Quelle allein die zwischengespeicherte Probe des Hardware-Managers (`get_state()`, von der Leiste höchstens alle 10 s angefragt); `strip_view` ruft nie `nvidia-smi` oder PowerShell. Fehlt LHM, steht der Satz dabei, wie man es bekommt (D-S3, auch neben einer nvidia-smi-Temperatur). | `uix_server.py` (`_hardware_probe`, `gpu_temperatur`, `_gpu_zelle`, `_ram_zelle`, `_server_zelle`, `_scheduler_zelle`), `tests/test_uix_strip.py` (12 Tests) |
| N3 | `startliste.js` (rein, 112 Zeilen): Orte mit Werkzeug, Werkzeuge ohne Ort (`id: alle`), nie `talk`/Instrumente, Gruppe aus Manifest > Datei (Ort-ID, Objekttyp) > `arbeit`, „Prüfung“ nur für reine Prüf-Orte, Suche (Wortanfang), zuletzt, Ablage-Einträge. `start_gruppen.json`. 12 node-Prüfungen. | `shells/harness/startliste.js`, `start_gruppen.json`, `tests/test_uix_harness_start.py` |
| N4 | `startmenue.js`: Knopf Start, Alt+S, `/start`; Suche mit Fokus, Pfeile/Enter/Esc; „Zuletzt benutzt“ aus `uix.shelf.harness` (`GET/POST /api/uix/shelf`, gebündelt ≤ 1 je 2 s); Gruppen; Oberflächen mit Vorschaubild (Wechsel über `sedraWechsel.wechseln`); Darstellung · Schrift; „Gedächtnis leeren“ (zweimal klicken). `shell.yaml` 1.4.0 mit `umschalter: menue` und den drei `/api/uix/*`-Routen. | `shells/harness/startmenue.js`, `shell.yaml`, `shell.css`, `shell.js`, `eingabe.js` |
| N5 | `app.js`: Reiter `app:<typ>:<id>[:<ansicht>]`; Einhängen über `ctx.tools.forObject` → `ctx.makeContext` → `sedraLifecycle.mountTool`, Aushängen beim Schließen; `inhalt` in der Fläche, `nachweis` rechts zum Aufklappen (Zustand je Reiter im Browser); **Werkbank-Zeile** aus `sedraLifecycle.actionsOf` (`data-verbs`); `shellApi.open` und `object.open` → App; Grenze 8 mit Satz; Arbeitsstand über `sedraStand.makeMelder` gemeldet und beim Start übernommen. | `shells/harness/app.js`, `reiter.js`, `verlauf.js`, `shell.js` |
| N6 | `taskleiste.js`: Start → Menü; Zellen Freigaben, Modell, GPU, RAM, Modellserver, Scheduler, Zustand, Uhr; Zellen mit „–“/`off` ausgeblendet; Klick je Zelle öffnet die App (Werkstatt, Hardware, Slots, Maschinenraum); Freigaben-Klick öffnet Aufgaben, Sitzung oder den Posteingang als App. App-Reiter als Knöpfe mit Gruppensymbol. | `shells/harness/taskleiste.js` |
| N7 | `arbeitsplatz.yaml` (Start-Menü, App, Hardware, Werkstatt, Nachweise, Oberfläche wechseln), `README.md` Stufe 4, Spec §6. Hinweise „Werkstatt im Cockpit“ zeigen jetzt auf das Start-Menü; `shellApi.decide` öffnet den Posteingang als App. | `arbeitsplatz.yaml`, `README.md`, `docs/SPEC_HARNESS_SHELL_v1.md`, `tests/test_arbeitsplatz.py` |
| N8 | `harness_abnahme.py --stufe4` (S4-A bis S4-D, ohne Modell, eigener Server oder `--url`); `uix_check` Profil `harness`: `opens: True`, Nachweis-Knopf, `leftovers`, `after_tool`, Start-Menü als `menu` mit `open_key` Alt+S, `talk.before`. Bilder unter `docs/shots/harness_stufe4/`. | `benchmarks/harness_abnahme.py`, `benchmarks/uix_check.py`, `docs/shots/harness_stufe4/` |
| N9 | Tests, dieser Bericht, Logbuch, ZIP. | – |

Zeilen je Shell-Datei (Vertrag ≤ 400): `verlauf.js` 356, `shell.js` 206, `taskleiste.js` 201, `startmenue.js` 184, `aufgabe.js` 181, `eingabe.js` 176, `app.js` 171, `seite.js` 136, `reiter.js` 124, `startliste.js` 112, `markdown.js` 110, `karte.js` 103, `lauf.js` 86; `shell.css` 349, nur Token, kein Hex. Gesamt: 71 Dateien, +1 886 / −94 Zeilen gegen `ce433c0` (einschließlich Specs und Bilder).

## 2. Abnahme (ohne Modell)

| Prüfung | Ergebnis |
|---|---|
| `run_tests.py scheduler desk orchestra uix harness` | **1 335 Tests, 9 übersprungen, 0 rot**, 589 s (Browser-Bahn ausgelassen: 5 Dateien) |
| `run_tests.py uix harness --slow` (Browser-Bahn) | **553 Tests, 0 neu rot** (1 bekannt rot), siehe §2a |
| `harness_abnahme.py --stufe4` | **S4-A** vollständig (34 Apps, 0 fehlt, 0 zu viel, kein Chip, kein Hub, 8 Oberflächen) · **S4-B** App-Leben (Suche „wissen“ → Enter → `app:wissen:speicher` mit `wissen` + `fundstelle`, Nachweise auf, 10 × öffnen → 8 offen mit 3 Sätzen, schließen → 0 Mounts, 7 offen) · **S4-B** Alt+S öffnet, Esc schließt · **S4-C** Cockpit und zurück: 7 Apps vorher, 7 nachher (Stand übernommen) · **S4-D** drei Hardware-Fälle (LHM 58 °C mit Quelle `LHM`; nur nvidia-smi 61 °C mit LHM-Satz; keine GPU: keine Temperatur, keine RAM-Zelle), höchstens 2 Proben je Fall · Konsole ohne Fehler |
| `uix_check.py --shell harness` | **42 von 42**, 1 nicht geprüft (`agentfenster`: kein Objekt im Prüfprojekt). Neu geprüft: 32 Werkzeuge als App-Reiter (Container, Text, Nachweisspalte, Absender), `unmount`, Start-Menü als Palette (Alt+S → „werkstatt“ → Werkstatt: Modelle, Esc schließt), `breite`, `layout` |
| `uix_check.py --shell cockpit / minimal / paperclip` | **41/41, 42/42, 45/45** – unverändert grün (der Chip bleibt dort) |
| Bilder | `docs/shots/harness_stufe4/01_start_menue.png` … `06_status_*.png`, `uix_check/` (je Werkzeug ein Bild) |

### 2a Browser-Bahn

`run_tests.py uix harness --slow`: 55 Testdateien, **553 Tests, 9 übersprungen, 1 rot** (881 s) – der eine rote ist der bekannte
`test_uix_flows.Build24.test_paperclip_new_project_and_the_workplace_answers` aus `tests/known_red.txt` (Routinen in der Paperclip-Navigation, rot seit `fa65917`); **kein neuer Fehlschlag**, Lauf-Ergebnis 0.

## 3. Abweichungen von G2/G3 und Befunde

1. **`start_gruppen.json` statt `.yaml`** (G3 N3): die Seite liefert nur js/css/json/svg/png/html aus (`SERVE_NAME`); den Server für eine Datei zu weiten wäre die größere Änderung. Im G3 vermerkt.
2. **Regel „Prüfung“ geschärft:** ein Ort landet nur dann unter „Prüfung“, wenn **alle** seine Werkzeuge `zweck: pruefung` haben – sonst würde eine Probe, die Aufgaben mitzeichnet, die Aufgaben umsortieren. (Im Paket gibt es heute kein `object`-Prüfwerkzeug; `rahmen-probe` ist ein Instrument.)
3. **LHM-Satz auch neben einer nvidia-smi-Temperatur** (N2): im ersten Bau stand er nur ohne Temperatur; S4-D hat es gefunden, jetzt steht er, sobald die Board-Sensoren fehlen (D-S3: „sagen, wie man es vielleicht lösen kann“).
4. **Werkbank-Zeile im App-Reiter** war in G2 nicht genannt, aber Vertrag (Regel 3, `data-verbs`): `uix_check` meldete beim Kandidaten „keine Handlungen, obwohl das Objekt welche hat“ – eingebaut wie in Minimal (`sedraLifecycle.actionsOf`).
5. **`object.open` → App** (Vertrag §5): ein Werkzeug, das ein Objekt öffnet (Liste → Einzelansicht), bekommt in der Harness einen App-Reiter; in G2 stand nur `shellApi.open`.
6. **Probe des Hardware-Managers:** `get_state()` nimmt bei Bedarf selbst eine Probe (nvidia-smi, WMI, je ≥ 2 s / 5 s Zwischenspeicher). Die Leiste fragt sie höchstens alle 10 s – damit ist sie nicht der Treiber der Messung, aber auf einem PC, auf dem sonst niemand den Hardware-Manager liest, läuft dadurch alle 10 s eine Probe. Das ist dieselbe Probe, die der Hardware-Manager für seine thermische Überwachung braucht; eine neue Messart ist es nicht (HS-32).
7. **GPU-Zelle ohne GPU:** auf einem PC ohne GPU ist `hw.vram_gb` leer, die Zelle zeigt „–“ mit Ton `off` und wird ausgeblendet. Im Prüfprojekt steht eine Test-GPU mit 12 GB (host_isolation), deshalb bleibt die Zelle dort auch im Fall „keine GPU“ stehen – ohne Temperatur, wie S4-D es verlangt.
8. **Nicht hier prüfbar:** die echte Temperatur mit RTX und LibreHardwareMonitor, der Klick „Oberflächen“ mit echten Vorschaubildern aller Shells (im Prüfprojekt vorhanden), die Benachrichtigung bei neuen Freigaben in Verbindung mit App-Reitern. Das ist die Prüfung des Captains auf dem PC (D-T3).
9. **Shell `start`** bleibt im Paket; die Harness zeigt sie nicht (D-S8). Die anderen Shells behalten Chip und Mini-Hub.

## 4. Offen

- **G4 Stufe 4:** Prüfung auf dem PC des Captains (Windows, RTX, LHM): Start-Menü, eine App öffnen, GPU-Zelle mit Temperatur und Quelle, Wechsel ins Cockpit und zurück; dann Übernahme.
- **Stufe 5** (HS-42 Einstellungen mit Katalog-Editor): G2 folgt nach G4.
- Aus Stufe 3 unverändert: `test_uix_stufe6` unter Last, Vergleich des zweiten N8-Kandidaten.
- Pi/Herdr-Plan und Stick-Plan setzen auf dieser Stufe auf (Start-Liste der Taskleiste = Stufe 4 ist jetzt da; `PLAN_USB_STICK_v1` A2 kann die Übersicht `start` ersetzen).

## 5. Quote (L4)

Stufe 4 ganz von Claude (Captain 15:53): kein SEDRA-Bau. Zeilen Claude ≈ 1 100 Code (JS, Python, CSS, JSON) plus Tests und Specs; Zeilen SEDRA 0.
