# SPEC Apps v1 – AM0 Härtung + AM1 Manifest v1.1 – G3 Bauaufteilung (05.11.2026)

Unterchat U12 (Roadmap `ROADMAP_ONE_SEDRA_APPS_KERN_SHELL_2026-11-05.md`, Stufen A0 und A1). Basis `main` d51083a.
**Status: Entwurf der Bauaufteilung. Nichts gebaut.** Grund: G2 von AM0 und AM1 ist nicht freigegeben (§0). Diese Datei ist die Vorlage für G3; gebaut wird erst nach der Freigabe von G2 durch den Captain (Fragen in §7).
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für d51083a.

## 0. Gate-Stand (geprüft)

| Spec | G1 | G2 | Beleg |
|---|---|---|---|
| AM0 Härtung | **freigegeben** 03.11. (AM0-E2, E3, E4 wie vorgeschlagen; E1 → O3+) | **geschrieben, nicht freigegeben** | `SPEC_APPS_v1_AM0_HAERTUNG.md:3`, `SPEC_APPS_v1_AM0_G2.md:383` („→ Freigabe durch den Captain → G3“) |
| AM1 Zellen und Shells | **freigegeben** 03.11. (AM1-E1 bis E3) | **geschrieben, nicht freigegeben** | `SPEC_APPS_v1_AM1_ZELLEN_UND_SHELLS.md:3`, `SPEC_APPS_v1_AM1_G2.md` §11 |
| AM0-E1 Oberflächencode (O3+, G9–G11) | entschieden 03.11. | **freigegeben** 03.11. (eigenes Dokument) | `SPEC_APPS_v1_O3PLUS_G9_G2.md:4`; Konzept §13 Zeile 384 |

Gesucht in `LOGBUCH_AGENT_MANAGER.md` (Zeilen 674–687), `KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §13 (Zeilen 369–384), `UEBERSICHT_NEBENSITZUNGEN_2026-11-04.md`, `WISSEN_SEDRA_GESAMT.md` §10: Es gibt nur „AM0 und AM1 in G2 bringen“ (Konzept :370 – der Auftrag, G2 zu **schreiben**) und die Freigabe von G2 für **O3+/G9–G11** (:384). Eine Freigabe von `SPEC_APPS_v1_AM0_G2.md` oder `SPEC_APPS_v1_AM1_G2.md` steht nirgends. `BESTANDSAUFNAHME_v1.22.0_2026-11-03.md:58` sagt es ausdrücklich: „Für die G2-Entwürfe AM0 und AM1 fehlen noch die Freigaben, u. a. AM0-G2-E1 … und AM1-G2-E1“.

## 1. Was schon gebaut ist – wird nicht doppelt aufgenommen

Die Git-Geschichte im Worktree hat nur einen Commit (d51083a); die Belege kommen aus dem Code und aus `SPEC_APPS_v1_O3PLUS_G9_G2.md` §13.

| Teil | Stand im Code | Beleg | Folge für AM0/AM1 |
|---|---|---|---|
| G11 Vollständigkeit der Freigabe-Wege | gebaut | `desk/freigabeklasse.py`; `tests/test_freigabe_vollstaendig.py` | AM0/AM1 legen **keine neue POST-Route und keinen neuen Harness-Weg** an (§6); die Bestandslisten bleiben gleich |
| G9/G10 Tür für Klasse H, Kanal im Audit | gebaut | `uix_server.py` `freigabe_tuer`; `desk/bestaetigung.py`, `systemdialog.py`, `freigabe_konsole.py` | Einbau (`/api/uix/install`) und Vertrauen (`trust`) laufen schon durch die Tür; AM0-T8 (Guard-Regeln) ist dadurch nur noch Erklärung, kein Schutz (§3 S9) |
| O3-06 Lese-Sperre Client-Token | gebaut | `harness/vorbehalte.py:47–60` | – |
| E9 `dashboard.html` hart, Hardware-Server ohne Inline-Skript | gebaut | `harness/vorbehalte.py:28` | – |
| harte Vorbehalte für die G9-Prüfstellen | gebaut | `harness/vorbehalte.py:29–33` | – |
| G4 Ausführung nur nach Sicht | gebaut | `harness/code_stand.py`, `vorbehalte.pruefen` (`ungesehen`) | – |
| **O3-01/O3-02 harte Muster für `uix/**`-Manifeste, `uix/ui/**`, Prüfstellen `desk/gateway.py` usw.** | **nicht gebaut** | `harness/vorbehalte.py:10–41` enthält sie nicht | ersetzt AM0-T1; Bau in U12 möglich (nur `vorbehalte.py`), §3 S8 |
| O3-03/O3-04 weich + „weich vor Katalog“, G1 Feld `oberflaeche` | nicht gebaut | `vorbehalte.pruefen_weich:62` kennt nur Modelle | braucht `harness/freigabe.py`, `aufgabe.py` – **nicht U12** (paralleler Chat), §5 |
| G2/G3/G6/G7 (Abnahme vor Wirkung, Sammelkarte, Startbericht, Rückweg) | nicht gebaut | O3PLUS §13.3 letzte Zeile | nicht Teil von AM0/AM1 |
| **Desktop Builder mit Profilen** (05.11.) | gebaut | `harness/desktop.py` (Wahl `desktop.json`, Profile `profile/<id>.json`, `GRUND_ZELLEN = ('decisions',)`), `uix/shells/harness/desktop.js` (`zellenAnwenden`, eigene Liste `ZELLEN`) | überdeckt einen Teil von AM1-08 (Auswahl/Reihenfolge der Zellen); `profile:` im Manifest muss an diese Profile anschließen (§2, §4) |
| Taskleiste: Temp, VRAM, RAM als drei Zellen (05.11.) | gebaut | `uix/shells/harness/taskleiste.js:15–30` (`trennen`) | AM1-G2 §2 (eine Zelle `gpu`) passt nicht mehr (§2 D1) |

Von AM0 (T1–T9) und AM1 (T1–T6) ist im Code **nichts** gebaut: `UI_VERSION = (1, 0)` (`desk/gateway.py:22`), `TOOL_KEYS` ohne `shells`/`zelle`/`profile` (`:63`), keine Routen-Weite und keine Sperrliste (`_common`, `:132–137`), keine Herkunftsdatei (`desk/herkunft.py` fehlt), Sandbox als Zeichenkette (`ui/loader.js:151`), Lader prüft `trust` der Shell nicht (`:174`), Rahmenseite mit Shell-CSP (`uix_server.py:3811–3812, 3867`), alter Gate-Text (`:515, 522`), 38 Guard-Regeln (`test_permission_levels.py:72`), kein `gauge-ram|server|scheduler`, keine `zellen.js`/`leiste.json`, kein Test `Origin: null`.

## 2. Abweichungen seit G2 (Code-Stand 05.11.)

| Nr | Abweichung | Beleg | Umgang in G3 |
|---|---|---|---|
| D1 | Die Harness-Leiste hat **acht** Datenzellen statt sieben: `decisions, model, temp, vram, ram, server, scheduler, state`. `temp` und `vram` entstehen in der Shell aus dem einen Wert `gpu` von `/api/strip`. Beschriftungen jetzt „Temp“, „VRAM belegt“, „RAM frei“. | `taskleiste.js:15–30` | zwei weitere Instrumente `gauge-temp`, `gauge-vram` (Frage E5); `trennen` bleibt in der Shell |
| D2 | Der **Desktop Builder** speichert schon eine Wahl der Zellen (`zellen: {ausblenden, reihenfolge}`) und benannte **Profile**; „leer heißt Vorgabe der Shell“. `Freigaben` ist Grundfunktion (Server prüft). | `harness/desktop.py:1–10, 19–22, 157`; `desktop.js:30–37` | `leiste.json` wird die **Vorgabe der Shell**, die Wahl des Builders liegt unverändert darüber (Frage E6) |
| D3 | `desktop.js` hat eine eigene feste Liste `ZELLEN` (Namen für den Builder) mit `token`. | `desktop.js:17–18` | soll aus `S._leiste.zellen` kommen – Datei gehört dem parallelen Chat, Änderung nur beschrieben (§5) |
| D4 | Roadmap §5 skizziert `zelle: {gruppe: werkzeuge, ort: start}` (Platz im Start-Menü); AM1-G2 definiert `zelle` als **Taskleisten-Zelle** `{feld, label, ort, aktion}`. Für den Platz im Start-Menü gibt es schon das Feld `gruppe` (`arbeit, modelle, wissen, system, pruefung`, `desk/gateway.py:44, 198`; gelesen von `startliste.js:7`). | wie genannt | AM1-Bedeutung behalten; Roadmap-Skizze korrigieren (Frage E3) |
| D5 | AM0-T1 (Vorbehalte) ist durch O3+ ersetzt (`SPEC_APPS_v1_AM0_G2.md` §1 „Ersetzt“). Der harte Teil ist eine reine Liste in `vorbehalte.py`; der weiche Teil braucht `freigabe.py`/`aufgabe.py`. | O3PLUS §3.1 | S8 baut nur den harten Teil (Frage E7) |
| D6 | Zeilen verschoben: `install_request` :494, `install_apply` :530 (Umschreiben auf COMMUNITY :569–574), `trust_apply` :1408 (schreibt :1431–1433), `install_remove` :1445, `_same_origin_ok` :3660, `_send` :3799, `/hardware` :3852, Rahmenseite :3867, `_ram_zelle`/`_server_zelle`/`_scheduler_zelle` in `/api/strip` :1880–1882. | `uix_server.py` | G3 nutzt diese Zeilen |
| D7 | Fremde Apps: Voreinstellung 05.11. „nur eigene Pakete, keine Dritten, bis A0 und A4 stehen“. Es gibt also heute keinen Einbau fremder Module im Betrieb; AM0 schützt den Weg, bevor er geöffnet wird. | Roadmap §7 Nr. 3 | keine Änderung am Plan; Abnahme mit einem **eigenen** Test-Modul |

## 3. Bauaufteilung AM0 (A0)

Reihenfolge so gewählt, dass kleine, unabhängige Schritte zuerst kommen und jeder Schritt allein grün ist.

| Schritt | AM0-G2 | Inhalt | Dateien (U12 darf) | Tests |
|---|---|---|---|---|
| **S1** | T4 | `const RAHMEN_SANDBOX = 'allow-scripts'` an `ui/loader.js:151`, ausgeführt in `module.exports`/`sedraLoader` | `uix/ui/loader.js` | neu `tests/test_apps_am0_rahmen.py`: Node (`run_js` aus `test_uix_contract`) Wert genau `'allow-scripts'`; Text von `loader.js` ohne `allow-same-origin`, `allow-top-navigation`, `allow-popups`, `allow-forms`, `allow-modals` |
| **S2** | T3 | `RAHMEN_CSP` (G2 §4) als Konstante; `_send(…, csp=None)`; Rahmenseite (:3867) sendet `csp=RAHMEN_CSP`; `/hardware` (:3852) unverändert | `uix_server.py` | neu `tests/test_apps_am0_csp.py`: Kopfzeile `/uix/frame/<id>` genau `RAHMEN_CSP` (mit einem CAPTAIN-Prüfwerkzeug im Prüfprojekt), `/hardware` und `/` wie vorher; `test_stufe_c_rahmen.py` bleibt grün |
| **S3** | T9 (Server) | Nachweis `Origin: null` | – | in `test_apps_am0_csp.py`: `GET /api/strip` und `POST /api/objects` mit Browser-Token und `Origin: null` → 403 |
| **S4** | T2 | `route_zu_breit` (`/api/*`, `/uix/*` → `api_route_too_broad:<r>`) für `origin == 'local'`; `SENSIBEL_COMMUNITY` (G2 §3, 18 Präfixe) mit Treffer in beide Richtungen → `api_route_sensitive:<r>`; Prüfung in `_common` **vor** dem Filter auf GET (:136), damit die Ablehnung schon in `install_request` (:508) greift | `desk/gateway.py` | neu `tests/test_apps_am0_routen.py`: je Fall; Präfix-Treffer `GET /api/fisch/*`; alle 44 `uix/tools/*/tool.yaml` und alle Shells des Pakets bleiben gültig |
| **S5** | T5 | `check_shell`: COMMUNITY ohne `vorgabe` → `community_shell_needs_vorgabe`; `_check_frame_shell` (:251): COMMUNITY mit `shell.css` → `community_shell_no_css` (nur nach Ja zu E1b); `ui/loader.js` vor :174: COMMUNITY-Shell ohne `frame` wird nicht geladen, Satz „Eine fremde Shell ohne Vorgabe wird nicht geladen.“; offene Frage aus AM0-G2 §6 vorab geprüft: `ui/frame.js` enthält kein `innerHTML` (0 Treffer); G3 bestätigt im Test, dass Texte der Vorgabe nur als Text gesetzt werden | `desk/gateway.py`, `uix/ui/loader.js` | neu `tests/test_apps_am0_shells.py`; `test_uix_frame.py`, `test_desk_install.py` grün |
| **S6** | T6 | neu `desk/herkunft.py` (G2 §2: `pfad, erfassen, schreiben, lesen, pruefen, entfernen`); `desk/install.py` bekommt `dateien(folder, area)` (Formregeln ohne `scan_text`); `install_apply` schreibt nach `staging.replace(target)` (:574) – also mit dem umgeschriebenen Manifest –, Audit `UIX_MODULE_INSTALLED` + `herkunft_sha256`; `trust_apply` (:1431–1433) schreibt den Manifest-Hash neu; `install_remove` (:1445) löscht die Datei; `Gateway._load` (:316–319) prüft für `origin == 'local'` (COMMUNITY ohne Datei → `herkunft_fehlt`), Zwischenspeicher nach `(relpfad, size, mtime_ns)` (N4), `Gateway.melden` → `UIX_MODULE_TAMPERED` einmal je `(id, gruende)`; Schalter `herkunft_pruefen` in `local_switches.py` (nur Datei, Standard an, wie `code_sicht` :36) | `desk/herkunft.py` (neu), `desk/install.py`, `desk/gateway.py`, `uix_server.py`, `local_switches.py` | neu `tests/test_apps_am0_herkunft.py`: ändern / hinzufügen / fehlend / Datei gelöscht → abgewiesen + Audit einmal; CAPTAIN ohne Datei → geladen; `trust_apply`; Entfernen; Zwischenspeicher (zweiter `_load` ohne Hashen, gezählt über einen Zähler in `herkunft`); Messung `POST /api/objects` mit `X-SEDRA-Tool` vorher/nachher (Zahl in den Baubericht) |
| **S7** | T7 | Gate-Texte (G2 §7): Werkzeug „läuft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite“ · „nicht begrenzt: Rechenzeit und Speicher im Browser“ · „Leserouten: <Liste> (oder: keine)“; Vorgabe-Shell „ohne eigenen Code und ohne eigenes CSS …“; `describe` „Leserouten: n“ statt „nur Leserouten (n)“ (:515, :522). **Nach S2** („ohne Netz“ stimmt erst mit der CSP) | `uix_server.py` | Textprüfung in `test_apps_am0_herkunft.py` |
| **S8** | T1 → O3-01/O3-02 (harter Teil) | `PFADE` um: `runtime/src/guppi_runtime/uix/ui/**`; `…/uix/**/tool.yaml`, `…/uix/**/shell.yaml`, `…/uix/**/shell.vorgabe.yaml`, `…/uix/**/arbeitsplatz.yaml`; `…/uix/desk.html`, `…/uix/retro_desktop.html`, `…/uix/js/**`; `desk/gateway.py`, `desk/install.py`, `desk/registry.py`, `desk/herkunft.py`, `uix_server.py`, `uix_clients.py`, `cloud_settings.py`, `models/cloud_api.py`, `runtime/config/cloud_providers.yaml`; dazu `runtime/tests/test_freigabe_*.py` (E14, 03.11. übernommen) und `harness/oberflaeche.py` (O3-02, Datei kommt später) | `harness/vorbehalte.py` | `tests/test_harness_vorbehalte.py` erweitert: je Muster `datei_schreiben` → Grund; `…/uix/**/README.md` frei; `…/uix/shells/harness/x.js` **kein** harter Treffer (bleibt bis zum weichen Teil wie heute) |
| **S9** | T8 | `guard_rules.yaml` GR-039 `install_module`, GR-040 `grant_module_write_routes`, GR-041 `grant_app_rights` → `CAPTAIN_REQUIRED`; `permission_levels.yaml` je `{level: 5, path_scoped: false}`; `test_permission_levels.py:72` 38 → 41; `install_request`/`trust_request` rufen vor `create_gate` `guard.evaluate(action, mission_id=…, target=…)` (`core/guard.py:63`) und brechen bei `BLOCK` ab. **Eigener Commit, eigene Freigabe** (Guard) | `architecture/…/guard/guard_rules.yaml`, `runtime/config/permission_levels.yaml`, `uix_server.py`, Test | `test_permission_levels.py`; neu: `evaluate` vor `create_gate` (Fake-Guard) |
| **S10** | T9 (Browser) | Prüf-Modul `runtime/tests/fixtures/rahmen_angriff/` (`trust: CAPTAIN`, `zweck: pruefung`, `kind: instrument`; nicht im Paket, weil der Vertragstest `fetch(` verbietet, N2); Versuche `fetch('/api/strip')`, `fetch('https://example.org')`, Bild von außen, `window.open`, `window.parent.document`; der Test legt das Modul vor dem Start in `local_config/tools/` des **Prüfprojekts** | `runtime/tests/fixtures/…`, `tests/test_stufe_c_rahmen.py` | Browser (Playwright, sonst übersprungen); kein Netz nötig – erwartet wird das Scheitern an der CSP |

Hinweis S8: Danach braucht jede Änderung an `tool.yaml`/`shell.yaml` über die **Harness** eine Karte – auch für S11–S13 unten, wenn sie über die Harness gebaut würden. U12 baut direkt im Repo (Claude), der Vorbehalt betrifft den Bau nicht. Den „Im Chat anpassen“-Weg des Desktop Builders (Modell ändert Shell-Dateien) trifft S8 nur bei Manifesten und `uix/ui/**`; JS/CSS der Shells bleiben bis zum weichen Teil frei wie heute.

## 4. Bauaufteilung AM1 (A1) – Manifest v1.1

### 4.1 Felder

```yaml
tool:
  id: gauge-ram
  kind: instrument
  trust: CORE                          # CORE nur Paket (gilt schon: local_module_cannot_be_core)
  needs: {ui: ">=1.1 <2"}
  gruppe: system                       # besteht: Platz im Start-Menü (D4)
  shells: [harness]                    # AM1-01: Verfügbarkeit je Shell; fehlt = alle Shells (bleibt, Beschluss 05.11.)
  profile: [standard, kmu, stick]      # NEU daneben: Verfügbarkeit je Profil von One Sedra; fehlt = alle Profile
  zelle: {feld: ram, label: "RAM frei", ort: hardware}   # AM1-05: Taskleisten-Zelle, nur kind: instrument
```

| Feld | Regel | Fehler / Warnung | Wirkung |
|---|---|---|---|
| `shells` | wie AM1-G2 §1: Liste 1–20, je `MODULE_ID`, ohne Dopplung | `shells_invalid`; unbekannte Shell → Warnung `shells_unbekannt:<id>` | `manifest()` zeigt nur Werkzeuge der aktiven Shell; Rest in `nicht_in_dieser_shell` |
| **`profile`** (neu) | Liste 1–40 (`MAX_PROFILE` aus `harness/desktop.py:25`), je `PROFIL_ID` (`^[a-z0-9][a-z0-9-]{1,39}$`, `desktop.py:22`), ohne Dopplung. Reserviert: `standard` = **kein Profil gewählt** (Vorgabe der Shell, `desktop.json` `profil: null`) | `profile_invalid`; unbekanntes Profil → Warnung `profil_unbekannt:<id>` (Profile liegen beim Captain, im Paket nicht bekannt; wie `shells_unbekannt`) | nur in **One Sedra** (`harness`) ausgewertet: verfügbar, wenn `profile` fehlt oder das aktive Profil (`desktop.laden(project_root)['profil'] or 'standard'`) darin steht. Andere Shells ignorieren das Feld |
| `zelle` | wie AM1-G2 §1 (`feld`, `label`, `ort` aus `chat_tools.PLACES`, `aktion` ∈ `freigaben, modellmenue, routermenue, einstellungen:<gruppe>[/<punkt>]`); neu optional `quelle` (Feld in `/api/strip`, aus dem die Shell den Wert ableitet, nur für `temp`/`vram` aus `gpu`) | wie AM1-G2; `zelle_quelle_invalid` | Datenzelle der Harness |

Gemeinsame Regeln für `shells` und `profile`:
- **Sichtbarkeit, kein Recht.** `Gateway.allowed` (:408) lädt über `_load`, nicht über `manifest()`; die Allowlist ändert sich nicht (AM1-G2 §0). Das gilt auch für `profile` – ein Profil schützt nichts (`ENTWURF_AUFTRAGGEBER_PROFILE` §1).
- **Grundfunktionen ignorieren beide Felder.** Ein Werkzeug, das eine Grundfunktion trägt (heute `decisions`, `tasks`, Zelle `decisions` – `harness/desktop.py:19–20`), bleibt in jedem Profil sichtbar; `profile` an einem solchen Werkzeug → Warnung `grundfunktion_ignoriert_profil`. Die Liste der Grundfunktionen kommt mit AM2 aus einer Stelle; bis dahin aus `harness/desktop.GRUND_START/GRUND_ZELLEN` gelesen (nur lesen, Datei nicht ändern).
- **Reihenfolge der Filter:** `disabled` → `pruefung` → `shells` → `profile`. Nicht sichtbare stehen in `nicht_in_dieser_shell` bzw. `nicht_in_diesem_profil` (`{id, name, shells | profile}`).
- `UI_VERSION = (1, 1)`; bestehende `needs.ui: ">=1.0 <2"` bleiben gültig (Test über alle Manifeste).

### 4.2 Schritte

| Schritt | AM1-G2 | Inhalt | Dateien (U12 darf) | Tests |
|---|---|---|---|---|
| **S11** | T1 + `profile` | `TOOL_KEYS` + `shells`, `profile`, `zelle`; Prüfungen §4.1; `check_tool` gibt die drei Felder zurück; `manifest()` filtert (aktives Profil über `harness.desktop.laden(self.registry`-Wurzel`)`, Fehler beim Lesen → `standard` + Warnung); `warnungen` in der Antwort; `UI_VERSION` 1.1; `ui/schema/tool.schema.json` mit denselben Feldern; `modules_view` gibt `shells`, `profile`, `zelle` aus | `desk/gateway.py`, `uix/ui/schema/tool.schema.json`, `uix_server.py` (nur `modules_view`) | neu `tests/test_apps_am1_manifest.py`: jede Regel und Meldung; zwei Shells; zwei Profile (Profil-Datei im Prüfprojekt); Allowlist unverändert für ein unsichtbares Werkzeug; Cockpit-Instrumente vorher = nachher; alle 44 Paket-Manifeste gültig |
| **S12** | T2 | `field: 'slots'`/`'wissen'` in `gauge-slots`, `gauge-wissen`; `zelle` in den neun `gauge-*` (Tabelle AM1-G2 §2; Label der Harness aus `taskleiste.js:15–16`) | `uix/tools/gauge-*/tool.yaml`, zwei `tool.js` | Gleichheit `field` (Code) = `zelle.feld` für alle Instrumente |
| **S13** | T3 + D1 | neue Instrumente, je `tool.yaml`, `tool.js` (Muster `gauge-gpu`), `README.md`; `shells: [harness]`, `order` 17–21, `api: []`, `needs.ui: ">=1.1 <2"`: `gauge-temp` `{feld: temp, label: "Temp", ort: hardware, quelle: gpu}`, `gauge-vram` `{feld: vram, label: "VRAM belegt", ort: hardware, quelle: gpu}`, `gauge-ram` `{feld: ram, label: "RAM frei", ort: hardware}`, `gauge-server` `{feld: server, label: "Modellserver", ort: models, aktion: modellmenue}` (heute öffnet auch `server` das Modell-Menü, `taskleiste.js:192–195`; nicht `routermenue` wie in G2), `gauge-scheduler` `{feld: scheduler, label: "Scheduler", ort: slots}` | `uix/tools/gauge-{temp,vram,ram,server,scheduler}/` | Vertragstest (README, ≤ 400 Zeilen, Manifest); Cockpit sieht sie nicht |
| **S14** | T4 | `uix/shells/harness/leiste.json` = **Vorgabe der Shell**: `["gauge-decisions", "gauge-model", "gauge-temp", "gauge-vram", "gauge-ram", "gauge-server", "gauge-scheduler", "gauge-state"]`; neu `zellen.js` (rein, Node-tauglich: `zellenAusManifest(instrumente, auswahl)`, `pruefeAuswahl(roh)`, `ZELLEN_RUECKFALL` = heutige `ZELLEN`); `taskleiste.js`: lädt `leiste.json` einmal, zeichnet aus `S._leiste.zellen` (`z.feld` als `data-zelle`, unverändert für Tests, Builder und `desktop.json`), Klick `aktion` vor `ort`, `trennen` bleibt (liefert `temp`/`vram`), Token-Zelle an Position 2, danach wie heute `desktop.zellenAnwenden` (Wahl des Captains über der Vorgabe); `shell.yaml` `zellen.js` vor `taskleiste.js`, Version +1 | `uix/shells/harness/{leiste.json, zellen.js, taskleiste.js, shell.yaml}` | neu `tests/test_apps_am1_leiste.py` (Node): echte Manifeste + echte `leiste.json` = **genau** die heutige Liste (8 Zellen, Schlüssel, Label, Ort, Klickziel); Nicht-CORE übergangen (AM1-17); fehlendes Instrument → `fehlend`; kaputte Datei → Rückfall + eine Meldung; `test_uix_harness_shell.py` Dateiliste (+2); `test_uix_harness_browser.py` (`data-zelle="decisions"`) grün |
| **S15** | T5 | Leerzustand in `app.oeffnen` (`uix/shells/harness/app.js:46`): „In dieser Oberfläche nicht verfügbar – verfügbar in: <Shells>“ bzw. „In diesem Profil nicht verfügbar“ | `uix/shells/harness/app.js` (nicht auf der Sperrliste des parallelen Chats; vor dem Bau mit ihm abstimmen) | Node/uix_check |
| **S16** | T6 | Nachtrag „Felder `shells`, `profile`, `zelle` (Vertrag 1.1)“ in `docs/SHELL_WERKZEUG_VERTRAG_v1.md`; Roadmap §5 Skizze korrigieren (`zelle` = Taskleiste, `gruppe` = Start-Menü) | Doku | – |

Reihenfolge: S11 → S12 → S13 → S14 → S15 → S16. S14 erst nach S11–S13.

## 5. Änderungen an Dateien des parallelen Chats – nur beschrieben, nicht gemacht

| Datei | Änderung | Wann |
|---|---|---|
| `uix/shells/harness/desktop.js` | `ZELLEN` (:17–18, Namen für den Builder) nicht mehr fest: `zellenListe(S)` liefert `[['token','Token']]` + `S._leiste.zellen.map(z => [z.feld, z.label])` in der Vorgabe-Reihenfolge; Rückfall die heutige Liste. Ohne diese Änderung zeigt der Builder eine **neu** in `leiste.json` aufgenommene Zelle nicht zum Ausblenden an (sie erscheint trotzdem in der Leiste). | nach S14 |
| `harness/desktop.py` | keine Pflichtänderung. Optional (AM2): `GRUND_START`/`GRUND_ZELLEN` an eine gemeinsame Stelle der Grundfunktionen verlegen, die `desk/gateway.py` mitliest; Prüfung, dass eine `zellen.reihenfolge` nur bekannte Zellen nennt, aus den Manifesten | AM2 |
| `harness/freigabe.py`, `harness/aufgabe.py` | O3-03/O3-04 (weich für `uix/shells/**`, `uix/tools/**`, `uix/css/**`, „weich vor Katalog“) und G1 (Feld `oberflaeche`, eng, eine je Projekt, nicht im Vorschlag des Vorarbeiters) nach `SPEC_APPS_v1_O3PLUS_G9_G2.md` §2.1–2.2; dazu `vorbehalte.pruefen_weich` (U12 darf diese Datei, aber ohne `freigabe.py` hat der weiche Grund keine Wirkung → zusammen bauen) | O3-G3 Schritt 4, nach dem parallelen Chat |
| `harness/api.py` | keine. AM0/AM1 legen keinen Harness-Weg an; `WEG`/`GESCHUETZT` bleiben, `desk/freigabeklasse.py` ebenso | – |
| `runtime.py`, `harness/werkzeuge.py`, `katalog.py`, `schleife.py`, `verlauf.js`, `zeilen.js`, `eingabe.js`, `wissen/**` | keine | – |

Abstimmung mit U13 (A2, Orte und App-Rahmen): berührt `taskleiste.js` und das Start-Menü; U13 nach S14 starten (Roadmap §6).

## 6. Tests und Abnahme

Je Schritt die neue Testdatei plus die Gruppen im Ordner `runtime`: `PYTHONIOENCODING=utf-8 python3 benchmarks/run_tests.py harness uix desk`, dazu im Ordner `runtime/tests` `PYTHONPATH=../src python3 -m unittest test_freigabe_vollstaendig` (muss ohne Änderung an `freigabeklasse.py` grün bleiben – Nachweis, dass kein Freigabe-Weg dazukam). Grün bleiben müssen außerdem: `test_uix_contract`, `test_uix_hardening_2026_10_30`, `test_stufe_c_bruecke`, `test_stufe_c_rahmen`, `test_uix_frame`, `test_desk_install`, `test_permission_levels`, `test_harness_vorbehalte`, `test_uix_harness_shell`, `test_uix_harness_browser`.
Stand vor dem Bau (d51083a, Container): siehe §8.

**Abnahme am PC (G4):** (1) Einbau eines eigenen Test-Moduls als COMMUNITY, Datei danach ändern → im Werkzeug „Module“ abgewiesen mit `herkunft_abweichung:<pfad>`; (2) Angriffs-Probe im Browser scheitert fünfmal; (3) Taskleiste von One Sedra sieht aus wie vorher (8 Zellen + Token); `gauge-tasks` in `leiste.json` → Zelle „Aufgaben“ erscheint ohne Codeänderung; (4) Profil „stick“ anlegen, ein Instrument mit `profile: [standard]` verschwindet im Profil „stick“, Freigaben bleibt; (5) Cockpit ohne neue Zellen.

## 7. Entscheidungsfragen an den Captain

| Nr | Frage | Vorschlag |
|---|---|---|
| **E1** | `SPEC_APPS_v1_AM0_G2.md` freigeben (mit den Korrekturen dieses Dokuments: Teil A durch O3 hart ersetzt, Zeilen nach D6)? | ja |
| E1b | AM0-G2-E1: fremde Vorgabe-Shells ohne `shell.css`? | ja (Voreinstellung „nur eigene Pakete“ macht es heute folgenlos) |
| E1c | N3 (Git-Klone mit `.git` nicht einbaubar) als eigenen Punkt außerhalb AM0? | ja, später |
| **E2** | `SPEC_APPS_v1_AM1_G2.md` freigeben, mit D1 (Temp/VRAM), D2 (Builder) und `profile:`? AM1-G2-E1 (Beschriftungen vereinheitlichen) nicht in AM1? | ja; Beschriftungen später |
| **E3** | `zelle` heißt Taskleisten-Zelle (AM1); der Platz im Start-Menü bleibt das bestehende Feld `gruppe` (AM2 bringt `orte`). Roadmap-Skizze §5 entsprechend korrigieren? | ja |
| **E4** | Bedeutung von `profile:`: Liste von Profil-Kennungen des Desktop Builders, `standard` = ohne Profil, fehlt = alle; nur Sichtbarkeit; nur in One Sedra ausgewertet; Grundfunktionen ignorieren es; unbekannte Kennung = Warnung | ja |
| **E5** | Temp und VRAM: zwei neue Instrumente `gauge-temp`, `gauge-vram` (nur Harness, Wert von der Shell aus `gpu` abgeleitet, Feld `zelle.quelle`) – statt `/api/strip` zu ändern? | ja (kein Eingriff in `/api/strip`, G1 §6) |
| **E6** | `leiste.json` ist die Vorgabe der Shell; die Wahl im Desktop Builder (ausblenden, Reihenfolge, Profile) liegt unverändert darüber. Neue Zellen kommen über `leiste.json`, nicht über den Builder (Builder-Erweiterung „Zelle hinzufügen“ später) | ja |
| **E7** | AM0-T1 = nur der **harte** Teil von O3 (S8, `vorbehalte.py`); der weiche Teil und G1 bleiben bei O3-G3 Schritt 4 (braucht `freigabe.py`/`aufgabe.py`) | ja |
| **E8** | S9 (Guard-Regeln GR-039–041): eigener Commit mit eigener Freigabe. Seit G9 ist der Einbau schon Klasse H hinter der Tür; die Regeln sind Erklärung. Trotzdem bauen? | ja, als eigener Commit, zuletzt |
| E9 | Reihenfolge: S1–S3 (klein) → S11–S14 (A1, sichtbarer Nutzen, unabhängig von AM0) → S4–S8 → S10 → S9 → S15–S16 | ja |
| E10 | S15 berührt `uix/shells/harness/app.js` (nicht auf der Sperrliste, aber Kern der Shell): erst nach Abstimmung mit dem parallelen Chat | ja |

## 8. Stand der Tests vor dem Bau

Gelaufen im Worktree (Container, d51083a, ohne Änderung am Code, 05.11.2026):
- `run_tests.py harness uix desk`: 110 Testdateien, **1.205 Tests, 0 rot**, 9 übersprungen, Browser-Bahn ausgelassen (5), 788 s.
- `test_freigabe_vollstaendig`: **17 Tests, OK**.

## 9. Berechtigungen vorab (für den Bau)

Wie AM0-G2 §14 und AM1-G2 §10, eingeschränkt durch die Sperrliste des parallelen Chats (§5). Guard (`architecture/…/guard_rules.yaml`) und `runtime/config/permission_levels.yaml` nur in eigenem Commit nach ausdrücklicher Freigabe (E8). Nicht: `local_config/` auf dem PC, Push, Modelle, GPU, Downloads.

## 10. Nächste Gates

G2 AM0 und G2 AM1 → **Freigabe durch den Captain (E1–E10)** → G3 Bau S1–S16 (dieses Dokument) → G4 Abnahme am PC (§6).
