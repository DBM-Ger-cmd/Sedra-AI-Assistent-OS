# Baubericht Harness-Shell Stufe 5 – Einstellungen und Katalog-Editor (30.10.2026), mit Gesamtstand Stufe 4 + 5 für G4

Spec: `SPEC_HARNESS_SHELL_v1.md` (G1 HS-42), `SPEC_HARNESS_SHELL_v1_G2_STUFE5.md` (G2, freigegeben 07:53, D-U1 bis D-U8),
`SPEC_HARNESS_SHELL_v1_G3_STUFE5.md` (G3, N1 bis N8). Branch `harness/stufe-5` auf `harness/stufe-4` (lokal, kein Push – Lieferung als
Fork-ZIP). Baut: **Claude allein** (Captain 07:53 „weiter an Stufe 5 arbeiten und im Anschluss nochmal alles prüfen“; 08:55 „ja fang an“).
Gebaut 08:55 bis 09:20 in der Cloud-Sitzung (Linux, kein Modell, keine GPU). Danach die **Gesamtprüfung** (§3).

## 1. Was gebaut ist (N1 bis N8)

| Nr | Ergebnis | Dateien |
|---|---|---|
| N1 | **Katalog schreiben nur über Antrag mit Gate** (D-U2). `katalog.py`: `pruefe_entwurf`, `hash_von`, `befunde` (weite Muster nur in eigenen Regeln, Lockerung gegen die Vorlage, fehlende `verboten`-Regel, Diff-Zahlen), `sichern` (`.bak-<zeit>`), `schreiben` (atomar, Kopfkommentar), `entfernen`. Neu `harness/antraege.py`: `katalog_antrag` → `gated.request(kind='harness_katalog', action='HARNESS_KATALOG_WRITE', target='local_config/freigabe_katalog.yaml', binding={entwurf_hash, stand_hash, regeln}, exact=True, risks=Befunde)`; `katalog_entfernen_antrag` (`HARNESS_KATALOG_REMOVE`); Applier prüft den Stand-Hash (`binding_stale`), schreibt, Audit `HARNESS_KATALOG_WRITTEN`/`_REMOVED`, Ereignis `harness.katalog`; registriert in `uix_server` **vor** `kinds.freeze()`. Wege `POST katalog/antrag`, `katalog/entfernen` in `GESCHUETZT` (Herkunft S7 → 403 aus einem Harness-Prozess). Unveränderter Entwurf → `entwurf_unveraendert` (400); ungültig → `entwurf_ungueltig: <Satz>`. `GET katalog` liefert jetzt die Regeln der Vorlage mit (für Lockerung/gesperrt im Editor). | `harness/katalog.py`, `harness/antraege.py`, `harness/api.py`, `uix_server.py`, `tests/test_harness_katalog_editor.py` (12 Tests) |
| N2 | **Grenzen der Schleife** (D-U4): `vorlagen.grenzen_schreiben` kopiert die Vorlage (`.yaml` + `.md`) nach `local_config/harness_vorlagen/`, nur `max_zuege` geändert, Sicherung bei vorhandener Kopie; `POST vorlagen/grenzen {vorlage, max_zuege}` → Antrag `harness_vorlage` (`HARNESS_VORLAGE_WRITE`, Bindung mit Vorlagen-Hash → stale bei Änderung); 4–40 geprüft; Repo-Datei bleibt. | `harness/vorlagen.py`, `harness/antraege.py`, `harness/api.py` |
| N3 | `GET /api/uix/clients`: je Client (`cli`, `mcp`) `vorhanden`, `port`, `pid`, `schutz`, `zeit`, `datei` – **nie der Token** (Test prüft, dass der Token nirgends in der Antwort steht). | `uix_clients.py` (`status`), `uix_server.py` (`clients_view`), `tests/test_desk_client.py` (+1) |
| N4 | `katalog_editor_pruefung.js` (rein, 102 Zeilen): `fehler` (dieselben Regeln wie `katalog.pruefen`: ID-Form, doppelt, Werkzeug, Muster, `..`/absolut, Stufe, Begründung), `diff`, `befunde` (weit, Lockerung, gesperrt), `pruefen` (`antragMoeglich`, `rot`), `alsYamlVorschau` (der Server liest die Vorschau als gültigen Katalog). 8 node-Prüfungen. | `shells/harness/katalog_editor_pruefung.js`, `tests/test_uix_harness_einstellungen.py` |
| N5 | `einstellungen.js` (263 Zeilen): Reiter `einstellungen:[gruppe/punkt]`, Navigation links (6 Gruppen, **20 Punkte** – G2 zählte 21, die Tabelle in G2 §3.1 hat 20 Zeilen), Fläche rechts. Werkzeuge über `app.flaeche(S, objekt, nur)` – der aus `app.js` ausgelagerte Einhänge-Code (forObject → makeContext → mountTool, Werkbank-Zeile), auf das genannte Werkzeug beschränkt (D-U1, kein Nachbau): Rekorder, KI GateWay (+ Schutz als Nachweis), Cloud (`labor`), Bibliothek, Werkstatt, Slots, Guard/Inhaltsschutz, Modus und Grenzen, Module, Audit. Eigene Flächen: Darstellung (dieselben Funktionen wie im Start-Menü), **Benachrichtigungen** (K9/D-U7: Browser-Hinweis „SEDRA: eine Freigabe wartet“ bei `decision.pending`, wenn das Fenster nicht vorn ist; `Notification.requestPermission` nur nach Klick; nie der Karteninhalt; Blinken in der Taskleiste an/aus), Sprache (nur „Deutsch“), Vorlagen (Liste mit Quelle, Werkzeuge, Rechte, Modell, `max_zuege`), Freigabe-Modus (→ N6), Grenzen (→ N2; `max_tokens`/`temperature` nur Anzeige), Quelle (`/api/sprache/status`, nur Anzeige, K8), MCP (N3, Aufruf-Weg), Laufzeit (`/api/models`: Server, Kontext, Slots, Engine-Build und `engine_check`, geladene Rezepte, Lease), Schalter (`/api/switches`, Antrag über `switch_request`, Hinweis Neustart, K5). Öffnen: Seitenleiste (`data-marke="hs-einstellungen"`), Start-Menü (fester Eintrag System → Einstellungen, auch in der Suche), `/einstellungen [gruppe/punkt]`, Zelle **Zustand** (D-U6). Offene Anträge stehen als Satz auf der Seite (§3.2). Gewählter Punkt im Browser (`sedra.harness.einstellungen`). | `shells/harness/einstellungen.js`, `app.js` (`flaeche`), `reiter.js`, `verlauf.js`, `seite.js`, `eingabe.js`, `startmenue.js`, `taskleiste.js`, `shell.js`, `shell.yaml` (1.5.0, Routen `clients`, `switches`, `switch/request`, `sprache/status`), `shell.css` (+37) |
| N6 | `katalog_editor.js` (138 Zeilen): Kopf (Quelle, Datei, Regeln je Stufe), Tabelle aller Regeln mit Herkunft (Vorlage/Datei/neu), **alle Felder** bearbeitbar (D-U3), Vorlage-`verboten` gesperrt (Felder aus, kein ×), Zeile hinzufügen/entfernen, Befunde live (Fehler rot/`bad`, Lockerung und weites Muster `rot`, Zeile markiert), Diff-Zahlen, YAML-Vorschau, „Antrag stellen“ (nur ohne Fehler, ohne gesperrte Änderung, mit Änderung), „Verwerfen“, „Zurück zur Vorlage“ (nur bei Datei des Captains → Antrag `entfernen`); lädt neu bei `decision.answered`/`decision.pending`/`harness.katalog`. | `shells/harness/katalog_editor.js`, `shell.css` |
| N7 | `arbeitsplatz.yaml` (Zone Einstellungen; Begriffe einstellungen, katalog-editor, schalter, grenzen der schleife, benachrichtigung), `README.md` Stufe 5, Spec §6 Zeile 5 („gebaut“), Pi/Herdr-Plan A4 → „in Stufe 5 gebaut“. `desk/decisions.py`: Titel und Hinweis der neuen Arten; **Risiken eines gated-Antrags erscheinen jetzt im Posteingang** (bisher immer leer – auch für Wissen/Orchestrierung ein Gewinn). | `arbeitsplatz.yaml`, `README.md`, `docs/SPEC_HARNESS_SHELL_v1.md`, `desk/decisions.py`, Projekt `PLAN_PI_HERDR_ABGLEICH_v1` |
| N8 | `harness_abnahme.py --stufe5` (Teil 5 in `harness_abnahme_stufe5.py`, damit die Datei ≤ 400 bleibt): S5-A bis S5-D ohne Modell im temporären Prüfprojekt; `uix_check` Profil Harness: Prüfung `einstellungen` (alle 20 Punkte öffnen, Marken, Katalog-Zeilen, Konsolenfehler). Gesamtprüfung §3, dieser Bericht, Logbuch, ZIP. | `benchmarks/harness_abnahme.py`, `benchmarks/harness_abnahme_stufe5.py`, `benchmarks/uix_check.py`, `docs/shots/harness_stufe5/` |

Zeilen je Shell-Datei (Vertrag ≤ 400): `shell.css` 386, `verlauf.js` 357, `einstellungen.js` 263, `shell.js` 207, `taskleiste.js` 206, `startmenue.js` 188, `aufgabe.js` 181,
`app.js` 180, `eingabe.js` 177, `katalog_editor.js` 138, `seite.js` 136, `reiter.js` 125, `startliste.js` 112, `markdown.js` 110, `karte.js` 103, `katalog_editor_pruefung.js` 102,
`lauf.js` 86 – nur Token, kein Hex. Gegen `harness/stufe-4`: 39 Dateien, +1 562 / −64 Zeilen (ohne Bilder, vor Bericht und Fotos). `harness/api.py` ist mit 632 Zeilen weiter über 400 (war 612 vor Stufe 5 – Altlast, nicht hier gewachsen).

## 2. Abnahme Stufe 5 (ohne Modell)

| Prüfung | Ergebnis |
|---|---|
| `tests/test_harness_katalog_editor.py` | 12 Tests: Antrag schreibt nichts; Freigeben schreibt, Sicherung, Audit; Stand von Hand geändert → `binding_stale` + `DESK_GATED_STALE`, nichts überschrieben; ungültig/unverändert → 400 mit Satz; Lockerung und weites Muster als Risiko am Gate; Herkunft → 403 auf allen drei Wegen, Lesen bleibt frei; entfernen → Vorlage; Grenzen 4–40, Kopie in `local_config`, Repo-Datei unverändert, `HARNESS_VORLAGE_WRITTEN`; Applier registriert |
| `tests/test_uix_harness_einstellungen.py` | 8 node-Prüfungen (unverändert kein Antrag; Diff; Lockerung rot aber möglich; Verschärfung kein Befund; `verboten` gesperrt bei Lockern und Entfernen; weit + alle Fehlersätze; `befehl`-Muster dürfen absolut sein; YAML-Vorschau vom Server gelesen) |
| `tests/test_desk_client.py::ClientsView` | ohne Token, fehlende Datei = `vorhanden: false` |
| `harness_abnahme.py --stufe5` | **S5-A** vier Wege (Seitenleiste, Start-Menü-Suche „einstell“ + Enter, `/einstellungen system/schalter` → Punkt gewählt, Zelle Zustand) landen in `einstellungen:`; 20 Punkte, keiner leer · **S5-B** `schreiben-docs` captain → frei: 1 roter Befund, Zeile markiert, Antrag mit Risiko „Lockerung: Regel „schreiben-docs“ der Vorlage von captain auf frei“, Datei nicht angelegt, Satz „1 Antrag offen“; Ablehnen → Datei unverändert, kein Antrag mehr; Freigeben → Datei mit Kopfkommentar, Kopf „Datei des Captains“; zweite Änderung → Sicherung `freigabe_katalog.yaml.bak-20261030-091823`, Audit `HARNESS_KATALOG_WRITTEN` · **S5-C** `entwicklung.enabled` → Antrag `request:switch` → Freigeben → „wirkt erst nach Neustart der SEDRA-Oberfläche“, `LOCAL_SWITCH_CHANGED` · **S5-D** `bauagent` 24 → 12: Kopie erst nach Freigabe, `GET vorlagen` Quelle `local_config`, `max_zuege` 12, Repo bleibt 24 · Konsole ohne Fehler |
| `uix_check.py --shell harness` | **43 von 43**, 1 nicht geprüft (`agentfenster`); neu `einstellungen ok 20 Punkte; Katalog 12 Regeln` |
| Bilder | `docs/shots/harness_stufe5/01_einstellungen.png` … `07_grenzen.png` |

## 3. Gesamtprüfung (Stufe 4 + 5, „im Anschluss nochmal alles prüfen“)

| Prüfung | Ergebnis |
|---|---|
| `run_tests.py scheduler desk orchestra uix harness` | **1 358 Tests, 9 übersprungen, 0 rot**, 620 s (99 Testdateien, Browser-Bahn ausgelassen: 5) – Stufe 4 hatte 1 335 |
| `run_tests.py uix harness --slow` (Browser-Bahn) | **575 Tests, 9 übersprungen, 0 rot**, 919 s (57 Testdateien) – Stufe 4 hatte 553 mit 1 bekannt rotem; `known_red.txt` ist leer |
| `uix_check.py --shell harness / cockpit / minimal / paperclip` | **43/43** (1 nicht geprüft), **41/41** (2), **42/42** (1), **45/45** (2) – alle Oberflächen grün; im Minimal-Lauf stehen `BrokenPipeError`-Zeilen des Servers im Protokoll (der Browser schließt den Ereignisstrom beim Neuladen – kein Fehler der Prüfung, Ergebnis ok) |
| `harness_abnahme.py --stufe4` | **S4-A bis S4-D ok** – im ersten Lauf S4-A „zu viel: einstellungen“: der feste Eintrag der Stufe 5 ist kein Ort; die Prüfung kennt ihn jetzt und verlangt ihn (`einstellungen: true`); zweiter Lauf ok, 35 Apps, 8 Oberflächen |
| `harness_abnahme.py --stufe5` | S5-A bis S5-D ok (§2) |

`tests/known_red.txt` ist leer (seit 715a159); jeder rote Test wäre neu.

## 4. Abweichungen von G2/G3 und Befunde

1. **20 statt 21 Punkte:** G2 §3.1 nennt „21 Punkte“, die Tabelle hat 20 Zeilen (3+3+2+3+4+5). Gebaut sind die 20 der Tabelle.
2. **Weite Muster nur in eigenen Regeln:** die Vorlage selbst enthält `**` (`lesen-alles`) und `*` (`lauf-stopp`); würde der Editor jede weite Vorlage-Regel rot zeigen, stünde jeder Entwurf von Anfang an mit zwei Befunden da. Rot (und Risiko am Gate) ist ein weites Muster nur in einer Regel, die **nicht genau so** in der Vorlage steht (Python `katalog.befunde` und JS gleich).
3. **Risiken im Posteingang** (`desk/decisions.request_decision`): bisher `risks: []` für jeden gated-Antrag; jetzt die am Gate gebundenen Risiken. Betrifft auch `wissen_quelle`, `wissen_vorschlag`, `orchestra` – nur Anzeige, kein Verhalten.
4. **Vorlagen-Text (`.md`) nicht lesbar** (G2 §3.1 „Text der `.md` lesbar“): es gibt keinen Lese-Weg für den Systemtext und `GET vorlagen` lässt ihn bewusst weg; ein neuer Weg wäre über G3 hinaus. Die Seite sagt, wo die Datei liegt. Wenn gewünscht: `GET vorlagen/<id>` als Nachtrag.
5. **Schalter-Fläche zeigt den Stand aus `/api/switches`** (Wert aus `local_config/switches.yaml`), die Anträge aus `/api/decisions` (`request:switch`). Der Hinweis „Neustart“ kommt aus `restart_needed` des Servers – nicht aus der Seite.
6. **Grenzen:** die Kopie der Vorlage in `local_config/harness_vorlagen/` ist dieselbe Vorrang-Mechanik wie bisher; „Zurück zum Repo“ = Datei löschen (nicht gebaut, da D-U4 nur das Setzen nennt; der Captain löscht die Kopie von Hand – das Löschen über die Oberfläche wäre ein weiterer Gate-Antrag).
7. **Zelle Zustand** öffnet `einstellungen:system` (erster Punkt der Gruppe System = Guard/Inhaltsschutz); der Maschinenraum bleibt als App über das Start-Menü erreichbar.
8. **Benachrichtigung** ist nur im echten Browser mit Erlaubnis prüfbar (Playwright headless gibt keine); gebaut nach K9, im Browser des Captains zu prüfen (G4).
9. **D-U5:** Cloud (`labor`) unverändert – Speichern mit Audit, ohne Gate (Build 5); hier nur eingehängt.
10. **Nicht hier prüfbar** (wie Stufe 4): echte GPU-Temperatur mit LHM, Browser-Benachrichtigung, Katalog-Editor gegen den echten `local_config/freigabe_katalog.yaml` des Captains (die Tests schreiben nur in temporäre Prüfprojekte, P5-3).

## 5. Gesamtstand für G4 (Stufe 4 + 5)

- **Stufe 4** (Bericht `BAUBERICHT_HARNESS_STUFE4_2026-10-29.md`): Start-Menü, Apps, Statusbereich – unverändert, `--stufe4` in §3 erneut gelaufen.
- **Stufe 5** (dieser Bericht): Einstellungen, Katalog-Editor, Grenzen, Schalter, MCP-Anzeige, Benachrichtigung.
- **Offene Punkte vor G4:** keine neuen. Aus Stufe 3/4 unverändert: Prüfung auf dem PC des Captains (Windows, RTX, LHM, echter Browser), S3-C mit Modell, Vergleich des zweiten N8-Kandidaten.
- **Vorschlag G4:** auf dem PC des Captains: (1) Einstellungen öffnen (Seitenleiste, Start, `/einstellungen`, Zelle Zustand); (2) Katalog: eine Regel ändern → Antrag im Posteingang → Freigeben → `local_config/freigabe_katalog.yaml` mit `.bak`; (3) Benachrichtigung einschalten, Fenster in den Hintergrund, eine Freigabe auslösen; (4) Stufe-4-Punkte (GPU-Zelle mit Temperatur und Quelle, Wechsel Cockpit und zurück). Dann „Übernehmen“ für beide Stufen oder Befunde nennen.

## 6. Quote (L4)

Stufe 5 ganz von Claude (Captain 07:53): kein SEDRA-Bau. Zeilen Claude ≈ 1 150 Code (JS, Python, CSS) plus Tests, Abnahme und Doku; Zeilen SEDRA 0.

## Nachtrag Abnahme durch SEDRA (30.10.2026, am PC, nach Ja des Captains)

Cockpit aus `main` (`0509a94`), Qwen3.6-35B-A3B geladen (`coder.local_primary`), Vorarbeiter-Sitzung `S-7C674D6B`, Aufgabe `T-12F035D3` (nur `lauf_starten run_tests`, 10 Aufrufe, 2 Stunden). Der Vorarbeiter startete beide Läufe ohne Karte und fasste die Ergebnisse zusammen.

| Lauf | Gruppen | Ergebnis |
|---|---|---|
| `L-517E05ED` | `harness` | 270 Tests, 1 übersprungen, 0 rot, 20 s |
| `L-9916EACE` | `scheduler desk orchestra uix` | 1146 Tests, 14 übersprungen, 0 rot, 102 s |

Der Vorarbeiter nannte „1416 Tests“ (Summe der beiden Läufe; die Gruppen überlappen, der Gesamtlauf der Gruppen zusammen zählt 1338, 0 rot).

**Nicht abgenommen:** `harness_abnahme.py --stufe4` und `--stufe5` (Paket `playwright` fehlt in der `.venv`), Benachrichtigung, GPU-Zelle mit Temperatur und Quelle (RTX, LibreHardwareMonitor), Cockpit-Wechsel, `test_k5` unter Windows. Diese Prüfungen macht der Captain im Browser (Checkliste im Vorschlag G4 oben).
