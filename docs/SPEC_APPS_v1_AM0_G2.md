# SPEC Apps v1 – AM0 Härtung – G2 Design (03.11.2026)

Grundlage: `docs/SPEC_APPS_v1_AM0_HAERTUNG.md` (G1), freigegeben vom Captain am 03.11.2026 mit den Entscheidungen AM0-E2 (eigene `CAPTAIN`-Shells behalten Code), AM0-E3 (Abweichung der Herkunft abweisen), AM0-E4 (Sperrliste übernehmen und je Route prüfen). **AM0-E1 ist wieder offen** (Teil A).
Nichts gebaut; diese Datei ist G2. Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 0. Was G2 im Code geklärt hat

| Punkt aus G1 | Ergebnis | Beleg |
|---|---|---|
| B8 `Origin: null` | **Geklärt: wird abgelehnt.** `_same_origin_ok` lässt nur einen leeren `Origin` oder `http://127.0.0.1:<port>` durch und steht vor jeder Verarbeitung von GET, POST, PATCH und DELETE. AM0-09 bleibt als Test, der das festhält. | `uix_server.py:3535–3540, 3653, 3708, 3818` |
| B9 Sandbox-Wert getestet? | **Zum Teil.** Der Browser-Test prüft `sandbox == 'allow-scripts'`; ohne Playwright wird er übersprungen. AM0-05 ergänzt einen Node-Test, der immer läuft. | `runtime/tests/test_stufe_c_rahmen.py:15–20, 42` |
| Vorbehalt und Aufgaben/Vorarbeiter/Sitzung | Ein Vorbehalt schließt Aufgaben-Deckung, Vorarbeiter-Freigabe und „für diese Sitzung erlauben“ aus; es bleibt nur die Karte an den Captain. | `harness/freigabe.py:230, 235, 250`; `harness/erlaubnis.py:68` |
| Guard-Regeln für den Einbau | `create_gate` legt das Gate an, **ohne** eine Regel auszuwerten. Eine Regel für `install_module` hat heute deshalb keine Wirkung, sie wäre nur Erklärung. | `core/guard.py:76–77` |
| Abgleich Guard ↔ Permission-Stufen | Der Test verlangt genau 38 Regeln, jede Aktion mit Stufe, Stufe ≥ 5 nur mit `CAPTAIN_REQUIRED`. Neue Regeln müssen an drei Stellen nachgezogen werden. | `runtime/tests/test_permission_levels.py:67–90`; `runtime/config/permission_levels.yaml:16–58` |
| Leserouten für die Sperrliste | Inhalt je Route aus den Docstrings der Handler bestimmt (Tabelle in Teil C). | `uix_server.py:3755–3830` und die genannten Methoden |
| Einbau-Ablauf | Hashprüfung der Quelle, Kopie in `….im-bau`, zweite Hashprüfung, **danach** Umschreiben des Manifests auf `COMMUNITY`, dann Umbenennen. | `uix_server.py:423–482` |

**Neue Befunde aus G2** (in G1 noch nicht enthalten):

| Nr | Befund | Beleg | Umgang |
|---|---|---|---|
| N1 | Eine fremde **Vorgabe-Shell darf `shell.css` mitbringen**. CSS in der Seite der Shell kann Knöpfe umgestalten, verdecken oder vertauscht wirken lassen (z. B. „Ablehnen“ wie „Freigeben“). Nach außen kann es nichts senden (`img-src`/`connect-src` der Shell nur `self`). | `desk/gateway.py:272` (`_check_frame_shell`) | Teil F: verboten für `COMMUNITY` (neu, **zur Bestätigung**) |
| N2 | Die Angriffs-Probe aus AM0-10 kann **nicht ins Paket**: Der Vertragstest verbietet `fetch(` in jedem Paket-Werkzeug. | `runtime/tests/test_uix_contract.py:91–99` | Teil J: Probe als Prüf-Modul im Testordner |
| N3 | Ein **Git-Klon mit `.git`-Ordner lässt sich nicht einbauen**: Die Durchsicht weist jeden Pfad ab, dessen Teil mit `.` beginnt. Eine Commit-ID kann die Herkunft deshalb heute nicht festhalten. | `desk/install.py:130–131` | Herkunft trägt `commit: null`; eigener Punkt außerhalb von AM0 (§8) |
| N4 | Die Allowlist-Prüfung `Gateway.allowed` ruft bei **jeder** Anfrage mit `X-SEDRA-Tool` `_load` auf und liest alle Manifeste neu. Eine Hashprüfung in `_load` liefe damit bei jeder Anfrage. | `desk/gateway.py:408–418` | Teil B: Zwischenspeicher nach Dateistand |

## 1. Teil A – Vorbehalte (AM0-01)

> **Ersetzt.** AM0-E1 ist entschieden (03.11.2026): **O3+**. Statt der Liste unten gilt `SPEC_APPS_v1_AM0_E1_OBERFLAECHENCODE.md` §6 (hart/weich/frei) mit G1, G2, G3, G6, G7; deren G2-Entwurf folgt in einem eigenen Dokument. Die Prüfstellen-Einträge dieser Tabelle (gateway, install, registry, herkunft, uix_server, uix_clients, cloud) bleiben als harte Vorbehalte Teil von §6. Die übrigen Teile von AM0 hängen nicht daran.

`harness/vorbehalte.py` `PFADE` (`:10–31`) bekommt nach dem Eintrag `runtime/benchmarks/devvm_*` diese Zeilen:

| Muster | Text der Karte („Captain-Vorbehalt: …“) |
|---|---|
| `runtime/src/guppi_runtime/uix/**` | Oberfläche: Lader, Brücke, Rahmen, Shells und Paket-Werkzeuge (ein Werkzeug im Paket läuft mit Seitenzugriff) |
| `runtime/src/guppi_runtime/desk/gateway.py` | Prüfung der Manifeste und Allowlist |
| `runtime/src/guppi_runtime/desk/install.py` | Durchsicht beim Einbau von Modulen |
| `runtime/src/guppi_runtime/desk/registry.py` | Register der Module und der Oberfläche |
| `runtime/src/guppi_runtime/desk/herkunft.py` | Herkunft eingebauter Module (neu, Teil B) |
| `runtime/src/guppi_runtime/uix_server.py` | Server der Oberfläche: Token, Einbau, Rechte |
| `runtime/src/guppi_runtime/uix_clients.py` | Zugänge der externen Clients |
| `runtime/src/guppi_runtime/cloud_settings.py` | Cloud-Zugang: Anbieter und Schlüssel |
| `runtime/src/guppi_runtime/models/cloud_api.py` | Cloud-Zugang: Adapter |
| `runtime/config/cloud_providers.yaml` | Cloud-Anbieter des Pakets |

- Die Muster gelten relativ zur Wurzel des Harness-Projekts, wie die bestehenden Einträge (`pruefen` → `pfad_normal`, `passt`).
- Wirkung (aus §0): Jede Schreib- oder Änderungsaktion des Modells an diesen Pfaden erzeugt eine Karte an den Captain; Aufgaben, Vorarbeiter und Sitzungs-Erlaubnis greifen nicht.
- Grenze: Ist ein Projekt so eingerichtet, dass seine Wurzel **innerhalb** von `runtime/` liegt, passen die Muster nicht. Das gilt heute für alle Einträge gleich (z. B. `runtime/src/guppi_runtime/core/**`); G2 ändert daran nichts, der Test nennt es.

## 2. Teil B – Herkunft (AM0-02)

**Neue Datei `desk/herkunft.py`** (≤ 400 Zeilen, ohne Netz, ohne Modell):

```python
ORDNER = 'uix_herkunft'                     # unter local_config/
def pfad(project_root, area, mid) -> Path   # local_config/uix_herkunft/<tools|shells>/<id>.json
def erfassen(folder, area) -> dict          # {relpfad: sha256} – dieselben Formregeln wie install.read_module, ohne Durchsicht
def schreiben(project_root, area, mid, folder, *, quelle, mission_id, vertrauen) -> dict
def lesen(project_root, area, mid) -> dict | None
def pruefen(folder, area, eintrag) -> list[str]   # leere Liste = in Ordnung
def entfernen(project_root, area, mid) -> None
```

**Format** (JSON, atomar über `core.util.atomic_write_json`):
```json
{"schema": 1, "art": "tools", "id": "rechnung", "vertrauen_beim_einbau": "COMMUNITY",
 "quelle": "D:\\Module\\rechnung", "commit": null, "mission_id": "M-…", "eingebaut_am": "2026-11-…",
 "dateien": {"tool.yaml": "<sha256>", "tool.js": "<sha256>", "README.md": "<sha256>"}}
```
- `commit` bleibt `null` (N3).
- `desk/install.py` bekommt `dateien(folder, area)`: der Teil von `read_module` ohne `scan_text`, damit Formregeln (Verknüpfungen, Punkt-Pfade, Dateitypen, Größe) an einer Stelle bleiben.

**Schreiben**:
- `install_apply` ruft `herkunft.schreiben(…)` **nach** `staging.replace(target)` (`uix_server.py:467`), also über die Dateien, wie sie danach liegen – mit dem umgeschriebenen `tool.yaml`/`shell.yaml`. Der Audit-Eintrag `UIX_MODULE_INSTALLED` bekommt zusätzlich `herkunft_sha256` (Hash der JSON-Datei).
- `trust_apply` schreibt nach dem Umschreiben des Manifests (`uix_server.py:1324–1327`) den Hash von `tool.yaml`/`shell.yaml` in der Herkunftsdatei neu (Rest unverändert).
- `install_remove` (`uix_server.py:1338ff`) löscht die Herkunftsdatei mit.

**Prüfen** in `Gateway._load` (`desk/gateway.py`), nach erfolgreichem `check_tool`/`check_shell`, nur für `origin == 'local'`:

| Lage | Ergebnis |
|---|---|
| Herkunftsdatei vorhanden | `pruefen` vergleicht; Gründe `herkunft_abweichung:<pfad>`, `herkunft_datei_fehlt:<pfad>`, `herkunft_datei_neu:<pfad>`, `herkunft_unlesbar` → Modul in `rejected` |
| keine Datei, `trust: COMMUNITY` | `herkunft_fehlt` → `rejected` |
| keine Datei, anderes Vertrauen | wie heute geladen (eigenes Modul des Captains, auch aus der Vorlage) |

- **Zwischenspeicher** (N4): je Modul der Stand `[(relpfad, size, mtime_ns)]` und das Prüfergebnis; neu gehasht wird nur, wenn sich dieser Stand oder die Herkunftsdatei ändert.
- **Meldung**: `Gateway` erhält ein Attribut `melden` (Standard `None`). Der Hub setzt es auf eine Funktion, die `UIX_MODULE_TAMPERED {kind, id, gruende}` ins Audit schreibt, je Prozess und `(id, gruende)` einmal.

**Was die Herkunftsdatei schützt – ehrlich:** Sie macht Änderungen sichtbar, die nach dem Einbau ohne Gate entstehen (versehentlich, durch Sync- oder Hilfsprogramme, durch Werkzeuge ohne Vorsatz). Gegen einen Prozess, der mit den Rechten des Captains absichtlich **beide** Ordner ändert (`local_config/tools/…` und `local_config/uix_herkunft/…`), schützt sie nicht. Eine stärkere Stufe wäre der Abgleich mit dem Audit (`herkunft_sha256` im Eintrag, Prüfung beim Start); sie ist vorbereitet, aber **nicht** Teil von AM0.

**Bestand**: Module, die vor AM0 mit `COMMUNITY` eingebaut wurden, haben keine Herkunftsdatei und werden abgewiesen. Das Werkzeug „Module“ zeigt dazu den Satz „Vor der Herkunftsprüfung eingebaut – entfernen und erneut einbauen“. Ob es auf dem PC des Captains solche Module gibt, ist nicht bekannt.

## 3. Teil C – Routen (AM0-03)

Korrektur gegenüber G1: Die Regel zur Weite lautet **mindestens ein fester Abschnitt** nach `/api` bzw. `/uix` (G1 schrieb „zwei“, nannte aber `GET /api/gateway/*` als gültig – das hat einen Abschnitt). Die Sperrliste deckt den Rest ab.

**In `desk/gateway.py`, `_common`, für `origin == 'local'`:**
- `route_zu_breit(route)`: wahr bei `… /api/*` und `… /uix/*` → Fehler `api_route_too_broad:<route>`.
- Nur bei `trust == 'COMMUNITY'`: `route_sensibel(route)` gegen `SENSIBEL_COMMUNITY`; ein Treffer liegt vor, wenn der Pfad der Route (ohne `/*`) mit einem Eintrag beginnt **oder** ein Eintrag mit dem Präfix der Route beginnt (damit `GET /api/fisch/*` den Eintrag `/api/fisch/transkripte` trifft) → Fehler `api_route_sensitive:<route>`.
- `install_request` nutzt dieselbe Prüfung (die Ablehnung kommt vor dem Gate).

**`SENSIBEL_COMMUNITY`** (Inhalt aus den Handlern; alle GET):

| Eintrag | Was die Route liefert | Beleg |
|---|---|---|
| `/api/chat/` | was der Captain im Gespräch gefragt und gesehen hat | `chat_verlauf`, `uix_server.py:2821` |
| `/api/harness/` | Sitzungen, Antworten, Projekte der Harness | Präfix-Routen `:3752` |
| `/api/arbeitsstand` | offene Objekte | `arbeitsstand_view`, `:2795` |
| `/api/audit` | Zustand der Kette und neueste Ereignisse (ohne Nutzlast) | `audit_view`, `:2995` |
| `/api/missions` | Missionen mit Titeln (Titel stammen aus Anträgen) | `missions`, `:193` |
| `/api/decisions` | offene Entscheidungen mit Titeln | `decisions_view`, `:197` |
| `/api/uix/` | Module, Ablagen der Shells, externe Clients (Port, PID) | `modules_view`, `shelf_view`, `clients_view` |
| `/api/cloud` | Zustand der Cloud-Anbieter | `cloud_view`, `:2655` |
| `/api/switches` | Schalter dieses Rechners | `switches_view`, `:2254` |
| `/api/processes` | laufende Prozesse | `processes_view`, `:3326` |
| `/api/gateway/` | Gateway-Vorgänge, Vorgaben, Dateinamen des Projekts | `gateway_list`, `:878` |
| `/api/fisch/` | Rollen, Profil, Transkripte | `fisch/hub.py:99` |
| `/api/sprache/` | Aufnahmen und Stand der Spracherkennung | `sprache/hub.py:34` |
| `/api/projects` | Projekte mit Pfaden | Routentabelle `:3774` |
| `/api/diagnose`, `/api/context`, `/api/permissions`, `/api/supervisor` | Diagnose und innerer Zustand der Laufzeit | Routentabelle |

Nicht auf der Liste (für `COMMUNITY` lesbar, wenn im Manifest): `/api/strip`, `/api/status`, `/api/boundaries`, `/api/guard/status`, `/api/models`, `/api/library`, `/api/topics`, `/api/tools`, `/api/meter`, `/api/inventory`, `/api/profiles`, `/api/capabilities`, `/api/resources`, `/api/routing`, `/api/agents`, `/api/rework`, `/api/intent/vorlagen`, `/api/uix/vorgaben` (unter `/api/uix/` doch gesperrt – wegen des Präfixes; AM3 öffnet Gezieltes). Diese Liste ist **nicht** als unbedenklich geprüft, sondern nur nicht als sensibel erkannt.

## 4. Teil D – CSP der Rahmenseite (AM0-04)

- `uix_server.py`: Konstante `RAHMEN_CSP = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'none'; form-action 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; frame-ancestors 'self'"`.
- `_send(…, csp=None)`: Ist `csp` gesetzt, wird genau diese Kopfzeile gesendet; sonst die heutige Zusammensetzung (`:3686–3687`).
- Die Rahmenseite (`:3742`) sendet `csp=RAHMEN_CSP`. **`/hardware`** (`:3727`, ebenfalls `frame_self`) bleibt unverändert.
- `img-src 'self'` bleibt, damit Werkzeuge Bilder aus ihrem Ordner zeigen können; ohne Token liefert der Server darüber keine API-Daten.

## 5. Teil E – Sandbox-Wert (AM0-05)

`ui/loader.js`: `const RAHMEN_SANDBOX = 'allow-scripts';` an der Stelle von `:151`, ausgeführt in `module.exports` und `root.sedraLoader`. Node-Test (über `run_js` aus `test_uix_contract`): Wert genau `'allow-scripts'`, und `loader.js` enthält nirgends `allow-same-origin`, `allow-top-navigation`, `allow-popups`, `allow-forms`, `allow-modals`.

## 6. Teil F – Fremde Shells (AM0-06, N1)

- `check_shell` (`desk/gateway.py:210ff`): `trust == 'COMMUNITY'` und kein `vorgabe` → `community_shell_needs_vorgabe`.
- `_check_frame_shell`: `trust == 'COMMUNITY'` und `shell.css` im Ordner → `community_shell_no_css` (**neu aus N1, zur Bestätigung durch den Captain**; ohne Bestätigung entfällt nur diese Zeile).
- `ui/loader.js` vor `:173`: Ist `manifest.shell.trust === 'COMMUNITY'` und nicht `manifest.shell.frame`, wird nichts geladen und ein Satz gezeigt („Eine fremde Shell ohne Vorgabe wird nicht geladen.“). Zweite Sicherung, falls die Serverprüfung umgangen würde.
- Eigene `CAPTAIN`-Shells mit Code bleiben (AM0-E2).
- Restrisiko: Eine fremde Vorgabe kann Texte setzen (Titel, Beschriftungen). Wie `ui/frame.js` sie zeichnet (als Text oder als Markup), wurde nicht gelesen; G3 prüft, dass es nur Text ist.

## 7. Teil G – Gate-Texte (AM0-07)

`install_request` (`uix_server.py:407–416`), Liste `risks`:

| Art | Neuer Text |
|---|---|
| Werkzeug | „läuft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite“ · „nicht begrenzt: Rechenzeit und Speicher im Browser“ · „Leserouten: <Liste> (oder: keine)“ · Funde der Durchsicht wie bisher |
| Shell (Vorgabe) | „ohne eigenen Code und ohne eigenes CSS – die Oberfläche baut der Rahmen des Vertrags (ui/frame.js)“ · „Routen: nur die festen Routen des Rahmens“ |

`describe` bleibt in der Form, ersetzt aber „nur Leserouten (n)“ durch „Leserouten: n“. Die Texte setzen Teil D voraus („ohne Netz“); Reihenfolge in §10.

## 8. Teil H – Guard-Regeln (AM0-08)

- `guard_rules.yaml`: `GR-039 install_module`, `GR-040 grant_module_write_routes`, `GR-041 grant_app_rights` (für AM3), alle `CAPTAIN_REQUIRED`, mit Kommentar „2026-11-03 Apps v1 AM0“.
- `permission_levels.yaml`: dieselben drei Aktionen mit `{level: 5, path_scoped: false}` und Kommentar.
- `test_permission_levels.py:71`: `38` → `41`, Kommentar ergänzt.
- **Damit die Regeln wirken** (§0: `create_gate` wertet nicht aus): `install_request` und `trust_request` rufen vor `create_gate` die Auswertung des Guard für ihre Aktion auf und brechen bei `BLOCK` mit Satz ab. Name und Form der Auswertung (im Test als `evaluate(action, mission_id=…, target=…)` nachgebildet, `test_permission_levels.py:38–42`) werden in G3 an `core/guard.py` bestätigt. Verhalten heute: unverändert (`CAPTAIN_REQUIRED` = Gate wie bisher).

## 9. Teil I und J – Nachweise (AM0-09, AM0-10)

- **AM0-09** Server-Test: `GET /api/strip` und `POST /api/objects` mit gültigem Browser-Token und `Origin: null` → 403.
- **AM0-10** Angriffs-Probe als **Prüf-Modul im Testordner** `runtime/tests/fixtures/rahmen_angriff/` (`tool.yaml` mit `trust: CAPTAIN`, `zweck: pruefung`, `kind: instrument`), das der Browser-Test in `local_config/tools/` des Prüfprojekts legt (N2). Versuche, jeder als Knopf mit Ergebnis im Rahmen: `fetch('/api/strip')`, `fetch('https://example.org')`, Bild von `https://example.org`, `window.open(…)`, Zugriff auf `window.parent.document`. Erwartet: jeder scheitert. Ob `start_server` (`benchmarks/uix_check.py`) Module in `local_config` des Prüfprojekts ablegen lässt, klärt G3; sonst legt der Test sie selbst vor dem Start ab.

## 10. Reihenfolge für G3 (Bauaufgaben)

| Nr | Aufgabe | Dateien | Tests |
|---|---|---|---|
| T1 | Vorbehalte | `harness/vorbehalte.py` | `tests/test_harness_vorbehalte.py` erweitert: je neuer Eintrag eine Karte mit `vorbehalt: True` |
| T2 | Routenregeln und Sperrliste | `desk/gateway.py`, `uix_server.py` (`install_request`) | neu `tests/test_apps_am0_routen.py`; alle Paket-Manifeste bleiben gültig |
| T3 | CSP der Rahmenseite | `uix_server.py` | neu `tests/test_apps_am0_csp.py` (Kopfzeile Rahmen, `/hardware` unverändert) |
| T4 | Sandbox-Konstante | `ui/loader.js` | Node-Test in `tests/test_apps_am0_rahmen.py` |
| T5 | Fremde Shells | `desk/gateway.py`, `ui/loader.js` | `tests/test_apps_am0_shells.py`; `tests/test_uix_frame.py` bleibt grün |
| T6 | Herkunft | neu `desk/herkunft.py`, `desk/install.py`, `desk/gateway.py`, `uix_server.py` | neu `tests/test_apps_am0_herkunft.py` (ändern, hinzufügen, fehlend, CAPTAIN ohne Datei, `trust_apply`, Entfernen, Zwischenspeicher) |
| T7 | Gate-Texte | `uix_server.py` | Textprüfung in T6-Datei |
| T8 | Guard-Regeln | `guard_rules.yaml`, `permission_levels.yaml`, `test_permission_levels.py`, `uix_server.py` | bestehender Abgleich; neuer Test: Auswertung vor `create_gate` |
| T9 | Nachweise | `tests/fixtures/rahmen_angriff/`, `tests/test_stufe_c_rahmen.py`, neuer Server-Test für `Origin: null` | Browser (mit Playwright), Server |

T3 vor T7 (Text „ohne Netz“). T8 berührt den Guard: eigener Commit, eigene Freigabe.
Bestehende Suiten, die grün bleiben müssen: `test_uix_contract.py`, `test_uix_hardening_2026_10_30.py`, `test_stufe_c_bruecke.py`, `test_stufe_c_rahmen.py`, `test_uix_frame.py`, `test_desk_install*` (Name in G3), `test_permission_levels.py`, `test_harness_vorbehalte.py`.

## 11. Rückfall

| Teil | Rückfall |
|---|---|
| A | Einträge entfernen (durch Claude/Captain; die Datei ist selbst Vorbehalt) |
| B | Schalter `herkunft_pruefen` in `local_switches` (Standard an); aus = keine Prüfung, Schreiben der Datei läuft weiter |
| C | – (betrifft nur fremde Module) |
| D | `csp=None` an der Rahmenseite |
| F | Prüfungen entfernen |
| H | Regeln und Stufen entfernen, Zähler zurück |

## 12. Risiken

- T6 berührt jeden Aufruf mit `X-SEDRA-Tool` (über `_load`); der Zwischenspeicher muss das abfangen. Messen in G3: Antwortzeit von `POST /api/objects` mit Kopf vor und nach.
- T1 kann laufende Bauarbeiten an der Oberfläche über die Harness verlangsamen (jede Datei eine Karte). Gewollt.
- T5/N1 kann eine eingebaute fremde Vorgabe-Shell mit CSS ausschließen. Unbekannt, ob es eine gibt.

## 13. Offen

| Nr | Frage | Vorschlag |
|---|---|---|
| AM0-G2-E1 | Fremde Vorgabe-Shells ohne `shell.css` (N1)? | ja |
| – | N3 (Git-Klone mit `.git` nicht einbaubar) als eigenen Punkt aufnehmen? | ja, außerhalb von AM0: beim Einbau `.git` gezielt auslassen und die Commit-ID lesen |

## 14. Berechtigungen vorab (für G3)

Wie G1 §9: `harness/vorbehalte.py`, `desk/{gateway.py, install.py, herkunft.py}`, `uix_server.py`, `ui/loader.js`, Testdateien und `tests/fixtures/rahmen_angriff/`; **Guard** (`architecture/…/guard_rules.yaml`) und `runtime/config/permission_levels.yaml` nur in eigenem Commit nach ausdrücklicher Freigabe. Nicht: `local_config/` auf dem PC, Push auf `main`.

## 15. Nächste Gates

G2 (diese Datei) → Freigabe durch den Captain → G3 Bauaufgaben T1–T9 → G4 Abnahme am PC (Einbau eines Test-Moduls, Änderung danach, Anzeige der Abweisung; Angriffs-Probe im Browser).
