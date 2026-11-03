# SPEC Apps v1 – AM0: Härtung des Bestehenden (03.11.2026)

Status: **G1 freigegeben** (03.11.2026, Entscheidungen wie vorgeschlagen); **G2** in `docs/SPEC_APPS_v1_AM0_G2.md`. Nichts gebaut. Teil von `docs/KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11.
Ziel: die Lücken schließen, die beim Lesen des App-Wegs gefunden wurden, **bevor** irgendetwas für fremden Code geöffnet wird. Kein neuer Funktionsumfang.
Pfade relativ zu `runtime/src/guppi_runtime/`, Zeilen für c364081.

## 1. Befund

| Nr | Befund | Beleg | Folge heute |
|---|---|---|---|
| B1 | Die harten Vorbehalte der Harness schützen `core/**`, `harness/freigabe.py`, `vorbehalte.py`, `befehl.py`, Aufgaben-/Lauf-Code, `local_config/**`, Guard-Regeln, `.git` – **nicht** `uix/ui/**`, `uix/tools/**`, `uix/shells/**`, `desk/gateway.py`, `desk/install.py`, `desk/registry.py`, `uix_server.py`, `uix_clients.py`, `cloud_settings.py`, `models/cloud_api.py`, `runtime/config/cloud_providers.yaml`. | `harness/vorbehalte.py:10–31` | Ein Modell mit Schreibbereich `runtime/**` (Beispiel `runtime/config/harness_projekte.beispiel.yaml:12`) kann nach einer gewöhnlichen Karte ein Werkzeug in den Paketordner legen. Es ist dann `CORE` und läuft mit Seitenzugriff (`ui/loader.js:164`). Es kann ebenso Lader, Brücke oder Manifestprüfung ändern. |
| B2 | Nach dem Einbau werden Hashes nicht mehr geprüft. Der Einbau prüft sie beim Kopieren (`uix_server.py:459–461`); danach liest der Lader die Dateien ungeprüft. | `desk/gateway.py` `_load`, `uix_server.py:459` | Eine spätere Änderung an `local_config/tools/<id>/` fällt nicht auf. |
| B3 | `GET /api/*` ist als Route gültig (`ROUTE`, `gateway.py:59`). Für `COMMUNITY` werden nur Nicht-GET-Routen entfernt (`gateway.py:137`). | `gateway.py:59, 137` | Ein fremdes Modul kann im Gate „nur Leserouten (1)“ zeigen und damit jede Leseroute der Seite meinen, z. B. `GET /api/chat/verlauf`, `GET /api/audit`, `GET /api/harness/…` (Namen aus der Routentabelle `uix_server.py:3755–3830`; Inhalt der einzelnen Routen nicht geprüft). |
| B4 | Die Rahmenseite eines abgeschotteten Werkzeugs bekommt die CSP der Shell; nur `frame-ancestors` unterscheidet sich. | `uix_server.py:3686–3687`, Aufruf mit `frame_self=True` `:3743` | `connect-src 'self'`: Der Rahmen darf den Server ohne Brücke anfragen. Ohne Token antworten API-Routen nicht (`_authorized`, `:3542ff`); Dateien unter `/uix/…` und die Rahmenseiten werden vor der Token-Prüfung ausgeliefert (`:3730–3743`). Last und Erkundung bleiben möglich. |
| B5 | Fremde Shells laufen mit Code in der Seite. Der Einbau nimmt `kind: shell` an (`uix_server.py:391`), der Lader lädt `manifest.shell.js` ohne Blick auf `trust` (`ui/loader.js:174`). `PLAN_STUFE_C` §7: „Eine Isolation der Shells selbst“ ist nicht im Plan, „Shells bleiben Kern“. | wie genannt | Die Abschottung der Werkzeuge ist für Shells wirkungslos. Eine eingebaute Shell hat dieselben Möglichkeiten wie CORE-Code in der Seite. |
| B6 | Der Gate-Text beim Einbau nennt als Risiko „fremder Code läuft danach in derselben Seite wie die Shell“. | `uix_server.py:415` | Für Werkzeuge seit Stufe C falsch, für Shells richtig (B5). Der Captain bekommt eine ungenaue Auskunft. |
| B7 | `install_module` und `grant_module_write_routes` haben keine eigene Guard-Regel; sie greifen über `unknown_action: CAPTAIN_REQUIRED`. | `architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT/core/guard/guard_rules.yaml:4` | Ergebnis richtig, aber nicht ausdrücklich; eine spätere Änderung der Vorgabe für unbekannte Aktionen würde den Einbau mitändern. |
| B8 | Ob der Server Anfragen mit `Origin: null` (so sendet ein Rahmen ohne `allow-same-origin`) ablehnt, ergibt sich aus `_same_origin_ok` (`uix_server.py:3535–3540`: nur leer oder `http://127.0.0.1:<port>`). Wo genau diese Prüfung greift, wurde nicht nachverfolgt. | `uix_server.py:3535–3540` | wahrscheinlich abgelehnt, nicht belegt |
| B9 | Das Sandbox-Attribut steht als Zeichenkette im Lader (`fenster.setAttribute('sandbox', 'allow-scripts')`, `ui/loader.js:151`). Ob ein Test genau diesen Wert festschreibt, wurde nicht geprüft (die Stufe-C-Tests wurden nicht gelesen). | `ui/loader.js:151` | Eine Änderung zu `allow-scripts allow-same-origin` würde die Abschottung aufheben. |

## 2. Anforderungen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| AM0-01 | **Vorbehalte erweitern.** In `harness/vorbehalte.py` `PFADE` kommen hinzu: `runtime/src/guppi_runtime/uix/ui/**`, `…/uix/tools/**`, `…/uix/shells/**`, `…/desk/gateway.py`, `…/desk/install.py`, `…/desk/registry.py`, `…/uix_server.py`, `…/uix_clients.py`, `…/cloud_settings.py`, `…/models/cloud_api.py`, `runtime/config/cloud_providers.yaml`. Begründungstext je Eintrag („Oberflächen-Vertrag: Lader, Brücke, Rahmen“ usw.). | Test: `datei_schreiben` auf je einen Pfad ergibt Stufe `captain` mit `vorbehalt: True`; „für diese Sitzung erlauben“ ist für diese Pfade nicht möglich (wie bei bestehenden Vorbehalten, `uix/shells/harness/arbeitsplatz.yaml:42`). |
| AM0-02 | **Herkunft beim Laden prüfen.** `install_apply` schreibt nach dem Kopieren eine Herkunftsdatei `local_config/uix_herkunft/<tools|shells>/<id>.json` mit `{quelle, commit (falls Git), dateien: {pfad: sha256}, mission_id, eingebaut_am}`. Die Datei liegt **außerhalb** des Modulordners. `Gateway._load` vergleicht bei jedem Modul mit `trust: COMMUNITY` alle Dateien; Abweichung, fehlende oder zusätzliche Datei → Modul abgewiesen mit `herkunft_abweichung:<pfad>` und Audit `UIX_MODULE_TAMPERED` (einmal je Start und Modul). Ein `COMMUNITY`-Modul ohne Herkunftsdatei wird abgewiesen (`herkunft_fehlt`). Module mit `CAPTAIN`, die der Captain selbst ablegt oder aus der Vorlage anlegt (`module_scaffold`, `uix_server.py:598`), haben keine Herkunftsdatei und werden wie heute geladen. **Achtung:** Der Einbau schreibt das Manifest nach der Hashprüfung um (`trust: COMMUNITY`, `uix_server.py:462–466`); die Herkunftsdatei muss die Hashes **nach** dem Umschreiben enthalten. `trust_apply` schreibt ebenfalls ins Manifest (`:1324–1327`); bis AM3 die Rechte aus dem Manifest nimmt, muss `trust_apply` die Herkunftsdatei im selben Schritt neu schreiben. | Test: Datei nach Einbau ändern → abgewiesen + Audit; Datei hinzufügen → abgewiesen; Herkunftsdatei löschen → abgewiesen; CAPTAIN-Modul ohne Datei → geladen. |
| AM0-03 | **Routenweite begrenzen.** Für Module außerhalb des Pakets (`origin == 'local'`) gilt: Ein Platzhalter `/*` braucht mindestens **zwei** feste Abschnitte nach `/api` (`GET /api/gateway/*` gültig, `GET /api/*` und `GET /api/harness/*` nicht, wenn `harness` auf der Sperrliste steht). Verstoß → `api_route_too_broad`. Zusätzlich eine **Sperrliste** `SENSIBEL` für `COMMUNITY` (Vorschlag, Inhalt je Route in G2 prüfen): `/api/chat/*`, `/api/audit`, `/api/harness/*`, `/api/arbeitsstand`, `/api/uix/clients`, `/api/cloud`, `/api/switches`, `/api/permissions`, `/api/context`, `/api/processes`, `/api/sprache/aufnahmen`, `/api/fisch/transkripte`, `/api/gateway/vorgaenge`. Treffer → `api_route_sensitive:<route>`. | Test je Fall; bestehende Paket-Manifeste bleiben gültig (Test über alle `uix/tools/*/tool.yaml`). |
| AM0-04 | **Eigene CSP für die Rahmenseite.** `/uix/frame/<id>` antwortet mit `default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src data: blob:; font-src 'self'; connect-src 'none'; form-action 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; frame-ancestors 'self'`. Die Shell-Seiten behalten ihre CSP. | Test: Kopfzeile der Rahmenseite; Browser-Test: `fetch('/api/strip')` und `fetch('/uix/manifest')` im Rahmen scheitern an der CSP. |
| AM0-05 | **Sandbox-Wert festschreiben.** Der Wert des Attributs ist eine Konstante (`RAHMEN_SANDBOX = 'allow-scripts'`) in `ui/loader.js`; ein Node-Test prüft, dass sie genau diesen Wert hat und nie `allow-same-origin`, `allow-top-navigation`, `allow-popups`, `allow-forms` enthält. | Node-Test |
| AM0-06 | **Fremde Shells nur als Vorgabe.** `check_shell`: Eine Shell mit `trust: COMMUNITY` darf kein `entry` haben (`community_shell_needs_vorgabe`). `install_request` mit `kind: shell` nimmt nur Ordner mit `vorgabe:` an. Der Lader lädt `manifest.shell.js` nur, wenn `trust` nicht `COMMUNITY` ist (doppelte Sicherung). Shells mit `trust: CAPTAIN`, die der Captain selbst ablegt, bleiben erlaubt (siehe AM0-E2). | Test: Einbau einer Code-Shell → abgewiesen; Vorgabe-Shell → angenommen; Lader-Test mit COMMUNITY-Code-Shell → nicht geladen. |
| AM0-07 | **Gate-Texte richtig.** Einbau eines Werkzeugs: „läuft abgeschottet im Rahmen, ohne Token und ohne Netz; Rechte: <Liste>; nicht begrenzt: Rechenzeit und Speicher im Browser“. Einbau einer Vorgabe-Shell: „ohne eigenen Code; die Oberfläche baut der Rahmen des Vertrags“. | Test der Texte |
| AM0-08 | **Ausdrückliche Guard-Regeln** für `install_module`, `grant_module_write_routes` und (für AM3 vorbereitet) `grant_app_rights` → `CAPTAIN_REQUIRED`. Die Aktivierung einer App (AM3-08) ist bewusst **kein** Gate und bekommt keine Guard-Regel. Permission-Stufen in `runtime/config/permission_levels.yaml` ergänzen, damit `tests/test_permission_levels.py` keine Abweichung meldet (laut Kopf der Datei, `:4`). | bestehender Abgleich-Test, neuer Test je Aktion |
| AM0-09 | **Origin `null` belegt abgelehnt.** Test: eine API-Anfrage mit gültigem Token und `Origin: null` → abgelehnt. Wenn der Test zeigt, dass sie angenommen wird, ist das ein eigener Befund mit Korrektur in diesem Baustein. | Server-Test |
| AM0-10 | **Angriffs-Probe erweitern.** Das Prüfwerkzeug `rahmen-probe` (`zweck: pruefung`) versucht zusätzlich: `fetch` ohne Brücke, `fetch` an eine fremde Adresse, Bild von fremder Adresse, `window.open`, Formular absenden, Fokus der Seite stehlen. Jeder Versuch muss scheitern; der Browser-Test zählt. | Browser-Test (`test_stufe_c_rahmen.py` erweitert) |

## 3. Entwurf

- **Vorbehalte (AM0-01)**: reine Liste; `pruefen` und `einstufung` bleiben unverändert. Wirkung: Jeder Schreibzugriff des Modells auf diese Pfade braucht eine eigene Karte; Aufgaben-Freigaben decken ihn nicht (wie heute bei `core/**`; die Deckung von Vorbehalten nicht im Code geprüft – G2 klärt das an `harness/aufgabe_deckung.py`).
- **Herkunft (AM0-02)**: Format JSON, atomar geschrieben (`core/util.atomic_write_json` wie `uix_clients.py`). Prüfung in `Gateway._load` nach `check_tool`/`check_shell`. Kosten: ein Lesen und Hashen aller Dateien fremder Module je Manifest-Abruf. `GET /uix/manifest` wird bei jedem Seitenaufbau gerufen; bei wenigen kleinen Modulen vernachlässigbar, sonst Zwischenspeicher mit Änderungszeit (G2).
- **CSP (AM0-04)**: `_send` erhält statt `frame_self` einen Parameter `csp`; die Rahmenseite übergibt die strenge Fassung. `style-src 'unsafe-inline'` bleibt, weil Werkzeuge `style=` setzen (Vertrag, Nachtrag 30.10. „CSP ohne Inline-Script“).
- **Fremde Shells (AM0-06)**: Vorgabe-Shells sind schon vollständig (Schema `ui/schema/vorgabe.schema.json`, Rahmen `ui/frame.js`, `FRAME_API`). Es entsteht kein neuer Weg, ein vorhandener wird der einzige für Fremde.

## 4. Tests und Abnahme

Neue Tests: `tests/test_apps_am0_vorbehalte.py`, `test_apps_am0_herkunft.py`, `test_apps_am0_routen.py`, `test_apps_am0_csp.py` (Server), Node-Test für AM0-05, Erweiterung von `test_stufe_c_rahmen.py` (Browser). Bestehende Suiten: Vertrag, Stufe C, Einbau, `test_uix_hardening_2026_10_30.py` müssen grün bleiben.
Abnahme durch den Captain: Einbau eines Test-Moduls am PC, Änderung einer Datei danach, Anzeige der Abweisung im Werkzeug „Module“.

## 5. Rückfall

| Teil | Rückfall |
|---|---|
| AM0-01 | Einträge aus der Liste nehmen (Vorbehalt-Datei ist selbst Vorbehalt; Änderung nur durch Claude/Captain) |
| AM0-02 | Schalter `herkunft_pruefen` (Standard an); aus = heutiges Verhalten |
| AM0-03 | keine Rücknahme vorgesehen; Paket-Manifeste sind ausgenommen |
| AM0-04 | CSP-Parameter auf die alte Fassung |
| AM0-06 | Prüfung in `check_shell` entfernen |

## 6. Abgrenzung

Keine Signatur (offen, Konzept §12). Keine Abschottung von CORE. Keine neue Berechtigungslogik (AM3). Keine Änderung am Guard außer zwei ausdrücklichen Regeln.

## 7. Risiken

- AM0-01 macht Bauaufträge an SEDRA, die Oberflächen-Code ändern, mühsamer: jede Datei eine Karte. Das ist Absicht, kann aber zu „Freigabe-Müdigkeit“ führen. Gegenmittel: Oberflächen-Bau über die DevVM und `adopt_plan`/Handkopie (Vertrag §7, Linie L5), nicht im Paketordner.
- AM0-03 kann eigene `CAPTAIN`-Module brechen, die breite Muster nutzen. Heute gibt es außer `rahmen-probe` und der Vorlage kein Nicht-CORE-Werkzeug im Paket (`PLAN_STUFE_C` §8); was unter `local_config/` auf dem PC des Captains liegt, ist nicht bekannt.
- AM0-06 bricht eine eingebaute fremde Code-Shell, falls es eine gibt. Unbekannt.

## 8. Entscheidungen des Captains

**Entschieden vom Captain am 03.11.2026: alle Vorschläge dieser Tabelle übernommen – außer AM0-E1:** zur Ausarbeitung zurückgegeben und danach entschieden (03.11.2026): **O3+** statt „ganz `uix/**` hart“, dazu G4 sofort und AM9 mit G5; siehe `docs/SPEC_APPS_v1_AM0_E1_OBERFLAECHENCODE.md`.

| Nr | Frage | Vorschlag |
|---|---|---|
| AM0-E1 | Vorbehalt für den ganzen Oberflächen-Code (`uix/**`) oder nur für den Vertragscode (`uix/ui/**`) und die Prüfstellen? | ganz `uix/**`: ein Werkzeug im Paket ist CORE, also Kern |
| AM0-E2 | Dürfen selbst abgelegte `CAPTAIN`-Shells weiter Code haben? | ja; nur `COMMUNITY` muss Vorgabe sein |
| AM0-E3 | Abweichung der Herkunft: abweisen oder nur warnen? | abweisen, mit Satz im Werkzeug „Module“ |
| AM0-E4 | Sperrliste der Leserouten (AM0-03): so übernehmen und in G2 je Route prüfen? | ja |

## 9. Berechtigungen vorab

| Nr | Berechtigung |
|---|---|
| P0-1 | Schreiben `harness/vorbehalte.py` (selbst Vorbehalt: nur durch Claude/Captain) |
| P0-2 | Schreiben `desk/gateway.py`, `desk/install.py`, `uix_server.py` (Einbau, CSP, Prüfungen) |
| P0-3 | Schreiben `ui/loader.js`, `uix/tools/rahmen-probe/*` |
| P0-4 | Schreiben `architecture/…/guard/guard_rules.yaml`, `runtime/config/permission_levels.yaml` (Guard: Captain-Entscheidung) |
| P0-5 | Tests anlegen; Browser-Tests mit dem vorhandenen Chromium |
| nicht | `local_config/` auf dem PC, Push auf `main`, Modelle |

## 10. Nächste Gates

G1 (diese Datei) → G2 Entwurf im Detail (Sperrliste je Route geprüft, Format Herkunftsdatei, Zwischenspeicher) → G3 Bauaufgaben → G4 Abnahme am PC.
