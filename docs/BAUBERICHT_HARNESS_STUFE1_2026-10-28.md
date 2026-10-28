# Baubericht Harness-Shell Stufe 1 (28.10.2026)

Spec: `SPEC_HARNESS_SHELL_v1.md` (G1), `SPEC_HARNESS_SHELL_v1_G2.md` (G2, D-E1 bis D-E6), `SPEC_HARNESS_SHELL_v1_G3_STUFE1.md` (T1–T8).
Gebaut von Claude (HS-E5, D-E6) im Worktree `stufe-1-64f713`, Branch `claude/stufe-1-64f713` ab `36f1a0f` (= `spec/agenten-orchestrierung`).
Kein Push, `main` und `spec/agenten-orchestrierung` unberührt. Übernahme entscheidet der Captain (G4).

## Ergebnis

**Committet sind T1–T6 und das Abnahme-Skript (T8).** Die Shell (T7) liegt nur in der Arbeitskopie des Worktrees. Sie hängt an zwei
Änderungen am Shell-Vertrag, die der Captain noch nicht freigegeben hat (siehe „OFFEN – Entscheidung des Captains“). Ohne diese
Änderungen lehnt `check_shell` die Shell ab, und die Paket-Tests werden rot.

| Prüfung | Ergebnis |
|---|---|
| Gruppen `scheduler desk orchestra uix` nach T1 (Commit-Stand) | 1073 Tests, 0 rot |
| Gruppen `scheduler desk orchestra uix harness`, Arbeitskopie mit Shell und offenen Änderungen | 1135 Tests, **2 rot** – beide gehören zu den offenen Fragen: `test_desk_gateway…test_every_rule_of_the_contract_is_enforced` (PATCH/DELETE im Manifest, Frage 1), `test_uix_shell_paperclip…test_the_acceptance_knows_every_shell_in_the_package` (Profil `harness` in uix_check, Frage 2) |
| Gruppen ohne die offenen Änderungen, aber mit dem Shell-Ordner | 6 rot (die Shell wird abgelehnt) – deshalb ist der Ordner nicht committet |
| neue Gruppe `harness` | 7 Testdateien, 69 Tests, 0 rot (6 Dateien, 62 Tests davon committet) |
| `uix_check --shell harness --groesse 1024x700,1400x860` (Arbeitskopie) | 18 von 18 ok (je 9 Prüfungen), 0 Konsolenfehler, Überhang 0 px; 6 „nicht geprüft“ (Werkzeug-Container, Palette – gibt es in dieser Shell nicht) |
| Browser-Durchlauf mit Modell-Attrappe (beide Größen) | Streamen grau → geprüft, Werkzeugzeile aufklappbar, Markdown mit Tabelle und Code-Kopieren, Stopp-Knopf und Esc → „Abgebrochen“, nach Neuladen alles wieder da, hell und dunkel, 0 Konsolenfehler |
| Abnahme mit echtem Modell (T8) | **offen – wartet auf Ja des Captains** (Skript vorbereitet, trocken gegen Attrappe in beiden Guard-Modi grün) |
| Cockpit | unverändert (`uix/shells/cockpit/` ohne Änderung); `chat_reply` unverändert |
| Auswahl in `START_SEDRA` | `harness|Harness` erscheint in `uix_start --liste` |

## Aufgaben

| Nr | Fertig | Belege |
|---|---|---|
| T1 | `on_delta(kanal, stueck)` in `_chat_streamed`; `delta.tool_calls` nach `index` zusammengesetzt, `message.tool_calls` wie ohne Streamen; wirft `on_delta` → Verbindung zu, `finish_reason='abgebrochen'`; `chat()` streamt mit `on_delta` auch ohne `stream_guard`. Router reicht nur an lokale Adapter (Cloud bekommt den Rückruf nie); Control nimmt `stream` aus der Anfrage, bevor Prüfsumme und Audit sie sehen; `slot_owner` aus der Anfrage geht an den Router. Nicht in `SAMPLING_KEYS`. | `test_harness_streamen` (8); alte Gruppen danach 1073 Tests grün |
| T2 | `harness/sitzung.py`: `S-` + 8 Hex, Kopf + Zeilen, `fsync` je Zeile, kaputte Zeile gezählt, Liste je Projekt mit letzter Zeit, Titel als Zeile, Löschen = Verschieben nach `geloescht/`, Sperre je Sitzung | `test_harness_sitzung` (13), darunter 2 Threads × 100 Zeilen à 5000 Zeichen |
| T3 | `harness/strom.py`: `A-` + 8 Hex, nummeriert, voll gehalten bis `ende` + 10 min, blockierender Leser, Wiederaufnahme ab Nummer, Abbruch-Signal, höchstens 8 laufende | `test_harness_strom` (9) |
| T4 | `harness/projekte.py` + `config/harness_projekte.beispiel.yaml`: Standard „Sedra Entwicklung“ = Repo-Wurzel, Schreibbereich `runtime/** docs/** redesign/**`; ungültige Datei → Fehler mit Grund; Muster außerhalb abgelehnt; schreibt nichts | `test_harness_projekte` (5) |
| T5 | `harness/schleife.py`: Züge über `control.execute` mit `stream`, `slot_owner='captain-chat'`, `tool_choice` nur `auto` (letzter Zug ganz ohne Werkzeuge), Wiederholung 2× Hinweis / 3× Schluss, `ende` ∈ antwort/erledigt/nur_plan/abgebrochen/fehler, 24 Züge (4–40), `compact_history` ab 70 %, Zurückhalten → nur Grund gespeichert, Ergebnisse „(Daten, keine Anweisung)“ | `test_harness_schleife` (16) |
| T6 | `harness/api.py` + `uix_server`: die 6 Wege der Stufe 1, SSE wie `_events`, PATCH/DELETE neu im Handler (nur `/api/harness/`), Schleife im eigenen Thread ohne `hub.lock`, `harness.sitzung`/`harness.antwort` auf `/api/events`, `kein_modell` mit Grund | `test_uix_harness_api` (11): ganzer Ablauf, `/api/status` während einer Antwort, `hub.lock` in der Schleife nie gehalten, > 8000 Zeichen → 400, Stopp, Löschen verschiebt |
| T7 | **nur Arbeitskopie (OFFEN, Frage 1)** – `uix/shells/harness/`: `shell.yaml`, `README.md`, `arbeitsplatz.yaml`, `seite.js`, `reiter.js`, `verlauf.js`, `eingabe.js`, `taskleiste.js`, `shell.css`, `preview.png`, dazu `markdown.js` und `shell.js` (Zustand, Registrierung) | `uix_check` (oben), `test_uix_harness_shell` (7) |
| T8 | Gruppe `harness` in `run_tests.py`; `benchmarks/harness_abnahme.py` für die Abnahme mit echtem Modell; dieser Bericht; Logbuch-Zeile | – |

Umfang: rund 2080 Zeilen neuer Code (Paket harness 800, Shell 1270) plus rund 120 geänderte Zeilen in Adapter, Router, Control, uix_server, gateway, bus und uix_check; rund 1000 Zeilen Tests.

## OFFEN – Entscheidung des Captains (nicht committet, nur Arbeitskopie)

| Frage | Konflikt Spec ↔ Code | Gebaut in der Arbeitskopie | Folge |
|---|---|---|---|
| 1 | G2 §6 verlangt `provides: [seite, reiter, flaeche, eingabe, taskleiste]`; `desk/gateway.SLOTS` kennt nur die alten Namen. Das Manifest braucht `PATCH`/`DELETE` für `/api/harness/sitzungen/<id>`; `gateway.ROUTE` kennt nur GET/POST. | `SLOTS` um die fünf Namen ergänzt, `ROUTE` um PATCH/DELETE; dazu `ui/bus.js` mit `harness.sitzung`/`harness.antwort`; `test_desk_modules` (Liste der Shells), `test_uix_harness_shell` | `test_desk_gateway` erwartet, dass `DELETE` im Manifest abgelehnt wird → rot. Andere Wege: (a) Titel/Löschen über POST statt PATCH/DELETE (weicht von G2 §4 ab), (b) den Vertragstest anpassen. |
| 2 | `uix_check` hat keine Fenstergröße und prüft „talk“ über das Werkzeug `talk`; die Regel „Shell ohne dock/windows bekommt kein eigenes Profil“ (`test_uix_shell_paperclip`). | Profil `harness`, Option `--groesse BxH[,BxH]`, „talk“ = Nachricht ohne Modell ergibt „Kein Modell geladen“ (HS-53) | `test_uix_shell_paperclip` rot; ohne Profil prüft `uix_check` nur allgemein und „talk“ schlägt fehl (kein `.t-talk-in`). |

Die Dateien stehen unverändert in der Arbeitskopie: `runtime/src/guppi_runtime/desk/gateway.py`, `runtime/src/guppi_runtime/uix/ui/bus.js`,
`runtime/benchmarks/uix_check.py`, `runtime/tests/test_desk_modules.py`, `runtime/tests/test_uix_contract.py` (nimmt Präfix-Wege des Servers an),
`runtime/tests/test_uix_harness_shell.py` und der Ordner `runtime/src/guppi_runtime/uix/shells/harness/`.

## Abweichungen und Entscheidungen beim Bau (bitte prüfen)

1. **Shell-Vertrag:** siehe OFFEN oben.
2. **D-E2 im Prüfprojekt und auf dem PC:** Nichts bestätigt = scharf (G-04). Dann gibt es **keinen Live-Text**; die Antwort erscheint erst nach dem Urteil, das Denken nur als „denkt nach“ ohne Inhalt. Live-Text gibt es erst, wenn der Modus des Projekts „beobachten“ oder „vertraut“ bestätigt ist. HS-52 (erstes Wort < 1 s nach erstem Token) ist im scharfen Modus nur als „erstes geprüftes Wort“ messbar.
3. **Mini-Hub:** `ui/wechsel.js` hängt den schwebenden Mini-Hub an jede Shell. HS-01 verbietet ihn hier; `shell.css` blendet sein Fenster aus, „Start“ öffnet sein Oberflächen-Menü, das Mikrofon seinen Rekorder. `wechsel.js` selbst ist unverändert.
4. **`text.geprueft {text}`:** Ändert der Inhaltsschutz den Text (Pseudonyme zurückübersetzt), trägt das Ereignis den geprüften Text; sonst `{}` wie in G2 §5. `werkzeug.start` trägt zusätzlich `args`, `werkzeug.ende` `ergebnis` (≤ 8000), damit die Zeile aufklappbar ist (HS-11). Jedes Ereignis trägt `t` (Sekunden seit Beginn der Antwort, für HS-52).
5. **Sitzungszeile `wahl`:** PATCH `modell` hängt `{"typ":"wahl","modell":…}` an (G2 §3.7 nennt keinen Typ dafür).
6. **Werkzeuge in Stufe 1:** nur lesende `chat_tools` (`get_model_status, list_models, get_routing_profile, get_switches, list_projects, list_missions, recent_audit, list_docs, read_doc, list_decisions, arbeitsplatz_stand`) – kein Vorschlag, kein Öffnen, kein Netz. Stufe in der Werkzeugzeile: `frei`, Regel leer (Katalog = Stufe 2).
7. **`nur_plan`** erkennt angekündigte oder behauptete Handlungen an Wendungen („ich schreibe …“, „habe … eingetragen“). `erledigt` kann es in Stufe 1 nicht geben (kein Werkzeug mit Wirkung).
8. **Anhänge, `+`, `@`:** in Stufe 1 abgelehnt (`anhaenge_ab_stufe_2`) bzw. als Hinweis; `vorlage` ≠ null → `vorlage_ab_stufe_3`.
9. **Mission je Sitzung:** angelegt beim Anlegen der Sitzung, ohne `hub.lock` (K3). Eine neue Sitzung wird in der Oberfläche erst mit der ersten Nachricht angelegt und ohne geladenes Modell gar nicht.
10. **`uix_check`:** siehe OFFEN oben (Frage 2).
11. **Branch:** G3 nennt `harness/stufe-1`; gebaut wurde auf dem Worktree-Branch `claude/stufe-1-64f713` (gleicher Ausgangspunkt).

## Offen (nicht in Stufe 1 oder nicht geprüft)

- **T8 mit echtem Modell:** erste Antwort mit Werkzeugzeile, Stopp, Neustart des Cockpit-Servers und Sitzung noch da, HS-52. Ablauf:
  1. Rezept `harness.nemotron_e4b` (Nemotron 3.5 Bolt E4B Q4_K_M, Kontext 8192 unvermessen, in `local_config/role_routing.yaml`) laden und `START_SEDRA harness` – nur nach Ja des Captains; setzt die Entscheidung zu Frage 1 voraus.
  2. `python benchmarks/harness_abnahme.py --url "<URL mit #token>"` (Teil 1).
  3. Cockpit-Server neu starten, dann `… --sitzung S-…` (Teil 2).
- Nicht im Browser geprüft: Strg+B von Hand, mittlere Maustaste, Umbenennen/Löschen in der Seitenleiste (Code und API-Tests vorhanden), Mikrofon → Rekorder.
- Bekannte Grenze: Nach einem Stopp ohne bereits gestreamten Text (scharfer Modus) bleibt die Antwort leer; mit Live-Text wird der Teil bis zum Stopp geprüft und gespeichert.

## Quote (L4)

Stufe 1: alles Claude (100 % Claude, 0 % SEDRA) – so vorgesehen (HS-E5, D-E6).
