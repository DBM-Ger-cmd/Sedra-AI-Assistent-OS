# Baubericht Harness-Shell Stufe 1 (28.10.2026)

Spec: `SPEC_HARNESS_SHELL_v1.md` (G1), `SPEC_HARNESS_SHELL_v1_G2.md` (G2, D-E1 bis D-E6), `SPEC_HARNESS_SHELL_v1_G3_STUFE1.md` (T1–T8).
Gebaut von Claude (HS-E5, D-E6) im Worktree `stufe-1-64f713`, Branch `claude/stufe-1-64f713` ab `36f1a0f` (= `spec/agenten-orchestrierung`).
Kein Push, `main` und `spec/agenten-orchestrierung` unberührt. Übernahme entscheidet der Captain (G4).

## Ergebnis

**Committet sind T1–T8.** Der Captain hat am 28.10.2026 beide Konflikte entschieden: Frage 1 mit (a) (Shell-Vertrag erweitert),
Frage 2 „Profil übernehmen“ (uix_check mit Profil `harness` und `--groesse`).

| Prüfung | Ergebnis |
|---|---|
| Gruppen `scheduler desk orchestra uix` nach T1 | 1073 Tests, 0 rot |
| Gruppen `scheduler desk orchestra uix harness`, Endstand | **1146 Tests, 0 rot**, 6 übersprungen (75 Dateien, Browser-Bahn ausgelassen) |
| neue Gruppe `harness` | 7 Testdateien, 72 Tests, 0 rot |
| `uix_check --shell harness --groesse 1024x700,1400x860` | 18 von 18 ok (je 9 Prüfungen), 0 Konsolenfehler, Überhang 0 px; 6 „nicht geprüft“ (Werkzeug-Container, Palette – gibt es in dieser Shell nicht) |
| Browser-Durchlauf mit Modell-Attrappe (beide Größen) | Streamen grau → geprüft, Werkzeugzeile aufklappbar, Markdown mit Tabelle und Code-Kopieren, Stopp-Knopf und Esc → „Abgebrochen“, nach Neuladen alles wieder da, hell und dunkel, 0 Konsolenfehler |
| Abnahme mit echtem Modell (T8, 28.10.2026 nach Ja des Captains) | **bestanden** (Einzelheiten unten): Werkzeugzeile ja, Stopp → `abgebrochen`, Sitzung nach Neustart vollständig; HS-52 nur im scharfen Modus gemessen (erstes geprüftes Wort −0,008 s Verzug) |
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
| T7 | `uix/shells/harness/`: `shell.yaml`, `README.md`, `arbeitsplatz.yaml`, `seite.js`, `reiter.js`, `verlauf.js`, `eingabe.js`, `taskleiste.js`, `shell.css`, `preview.png`, dazu `markdown.js` und `shell.js` (Zustand, Registrierung) | `uix_check` (oben), `test_uix_harness_shell` (7) |
| T8 | Gruppe `harness` in `run_tests.py`; `benchmarks/harness_abnahme.py` für die Abnahme mit echtem Modell; dieser Bericht; Logbuch-Zeile | – |

Umfang: rund 2080 Zeilen neuer Code (Paket harness 800, Shell 1270) plus rund 120 geänderte Zeilen in Adapter, Router, Control, uix_server, gateway, bus und uix_check; rund 1000 Zeilen Tests.

## Entschieden und offen

| Frage | Konflikt Spec ↔ Code | Stand |
|---|---|---|
| 1 | G2 §6 verlangt `provides: [seite, reiter, flaeche, eingabe, taskleiste]`, `desk/gateway.SLOTS` kannte nur die alten Namen; das Manifest braucht `PATCH`/`DELETE` (G2 §4), `gateway.ROUTE` kannte nur GET/POST. | **Entschieden (a), committet:** `SLOTS` um die fünf Zonen, `ROUTE` um PATCH/DELETE erweitert; `ui/bus.js` kennt `harness.sitzung`/`harness.antwort`. `test_desk_gateway` angepasst (abgelehnt wird jetzt `PUT`; neuer Test: PATCH/DELETE gültig, fremde Module behalten nur GET), `test_desk_modules` (Liste der Shells), `test_uix_contract` (nimmt Präfix-Wege des Servers an). |
| 2 | `uix_check` hat keine Fenstergröße und prüft „talk“ über das Werkzeug `talk`; die Regel „Shell ohne dock/windows bekommt kein eigenes Profil“ (`test_uix_shell_paperclip`). | **Entschieden „Profil übernehmen“, committet:** Regel in `test_uix_shell_paperclip`: eine Shell ohne dock/windows darf ein Profil haben, wenn es eine eigene talk-Prüfung trägt. Profil `harness`, Option `--groesse BxH[,BxH]`, „talk“ = Nachricht ohne Modell ergibt „Kein Modell geladen“ (HS-53). Ohne diese Änderung prüft `uix_check` die Shell nur allgemein, und „talk“ schlägt fehl (kein `.t-talk-in`). |

## Abweichungen und Entscheidungen beim Bau (bitte prüfen)

1. **Shell-Vertrag:** siehe „Entschieden und offen“.
2. **D-E2 im Prüfprojekt und auf dem PC:** Nichts bestätigt = scharf (G-04). Dann gibt es **keinen Live-Text**; die Antwort erscheint erst nach dem Urteil, das Denken nur als „denkt nach“ ohne Inhalt. Live-Text gibt es erst, wenn der Modus des Projekts „beobachten“ oder „vertraut“ bestätigt ist. HS-52 (erstes Wort < 1 s nach erstem Token) ist im scharfen Modus nur als „erstes geprüftes Wort“ messbar.
3. **Mini-Hub:** `ui/wechsel.js` hängt den schwebenden Mini-Hub an jede Shell. HS-01 verbietet ihn hier; `shell.css` blendet sein Fenster aus, „Start“ öffnet sein Oberflächen-Menü, das Mikrofon seinen Rekorder. `wechsel.js` selbst ist unverändert.
4. **`text.geprueft {text}`:** Ändert der Inhaltsschutz den Text (Pseudonyme zurückübersetzt), trägt das Ereignis den geprüften Text; sonst `{}` wie in G2 §5. `werkzeug.start` trägt zusätzlich `args`, `werkzeug.ende` `ergebnis` (≤ 8000), damit die Zeile aufklappbar ist (HS-11). Jedes Ereignis trägt `t` (Sekunden seit Beginn der Antwort, für HS-52).
5. **Sitzungszeile `wahl`:** PATCH `modell` hängt `{"typ":"wahl","modell":…}` an (G2 §3.7 nennt keinen Typ dafür).
6. **Werkzeuge in Stufe 1:** nur lesende `chat_tools` (`get_model_status, list_models, get_routing_profile, get_switches, list_projects, list_missions, recent_audit, list_docs, read_doc, list_decisions, arbeitsplatz_stand`) – kein Vorschlag, kein Öffnen, kein Netz. Stufe in der Werkzeugzeile: `frei`, Regel leer (Katalog = Stufe 2).
7. **`nur_plan`** erkennt angekündigte oder behauptete Handlungen an Wendungen („ich schreibe …“, „habe … eingetragen“). `erledigt` kann es in Stufe 1 nicht geben (kein Werkzeug mit Wirkung).
8. **Anhänge, `+`, `@`:** in Stufe 1 abgelehnt (`anhaenge_ab_stufe_2`) bzw. als Hinweis; `vorlage` ≠ null → `vorlage_ab_stufe_3`.
9. **Mission je Sitzung:** angelegt beim Anlegen der Sitzung, ohne `hub.lock` (K3). Eine neue Sitzung wird in der Oberfläche erst mit der ersten Nachricht angelegt und ohne geladenes Modell gar nicht.
10. **`uix_check`:** siehe „Entschieden und offen“ (Frage 2).
11. **Branch:** G3 nennt `harness/stufe-1`; gebaut wurde auf dem Worktree-Branch `claude/stufe-1-64f713` (gleicher Ausgangspunkt).

## Alte Fehler der vorigen Shells (Hinweis des Captains)

| Alter Fehler | Wo er auftrat | In der Harness-Shell |
|---|---|---|
| Plan ohne Ausführung gilt als Erfolg (B4/1) | Chat-Kette | `ende: nur_plan`; `erledigt` nur mit Werkzeug mit Wirkung (Test) |
| Dasselbe Werkzeug achtmal (B4/4) | Chat-Kette | 2× Hinweis, 3× Zug ohne Werkzeuge (Tests) |
| Stichwörter erzwingen `required` (B4/5) | `chat_reply` | `tool_choice` nur `auto`, letzter Zug ohne Werkzeuge (Test „öffne Aufgabe“) |
| Leere Antwort still / „model_answer_empty“ | Chat 28.10. | ein Zug ohne Werkzeuge; bleibt sie leer → `ende: fehler` mit Grund (Tests) |
| Abgeschnittene Antwort unbemerkt | nachtlauf_3d, Chat | `abgeschnitten` im Strom, in der Sitzung und als Hinweis im Verlauf (Test) |
| `hub.lock` blockiert alle Wege während einer Antwort (K3) | `chat_reply` | Schleife ohne `hub.lock`, `/api/status` antwortet sofort (Test) |
| Werkzeugaufrufe am Inhaltsschutz vorbei | Router bis 28.10. | Schleife nutzt `message.tool_calls` aus dem geprüften Ergebnis |
| Knopf im Formular sendet ab | Werkzeug Wissen 26.10. | nur `type=button` / `sedraDom.button` |
| Viele Reiter machen die Seite breiter (Build 8) | Cockpit | 16 Reiter bei 1024 px: Überhang 0 px, Reiter und Taskleiste rollen in sich |
| 404 in der Konsole durch gemerkte, verschwundene IDs | – | gemerkte Reiter werden gegen die Sitzungsliste geprüft |
| Fester Wartewert statt „bereit“ | uix_check 15.10. | Abnahme wartet auf `sedraBoot.ctx` (vorhanden) |
| Polling je Fenster | vor Build 7 | Status nur bei Ereignissen, höchstens alle 2 s; nur die Uhr tickt lokal |

## Offen (nicht in Stufe 1 oder nicht geprüft)

- Nicht im Browser geprüft: Strg+B von Hand, mittlere Maustaste, Umbenennen/Löschen in der Seitenleiste (Code und API-Tests vorhanden), Mikrofon → Rekorder.
- Bekannte Grenze: Nach einem Stopp ohne bereits gestreamten Text (scharfer Modus) bleibt die Antwort leer; mit Live-Text wird der Teil bis zum Stopp geprüft und gespeichert.

## Abnahme mit echtem Modell (T8)

Captain-Ja 28.10.2026 („T8 mit echtem Modell“). Server mit dem Code dieses Branches auf `workspace/GUPPI_OS`, Shell `harness`, Rezept
`harness.nemotron_e4b` (Nemotron 3.5 Bolt E4B Q4_K_M, 2 Slots), geladen über `/api/model/load` in 44 s, 16 384 Token je Slot, VRAM 5,2 GB.

| Prüfung | Ergebnis |
|---|---|
| Erste Antwort mit Werkzeugzeile | ja: `get_model_status` lief (ok), 4 Züge, 2541 Token ein, 69 aus |
| Stopp mitten in einer langen Antwort (nach 4 s) | `ende: abgebrochen` |
| Neustart des Cockpit-Servers, Sitzung noch da (Teil 2) | ja: `S-87FDAD69`, 7 Einträge (captain, 3× werkzeug, modell, captain, modell), 0 kaputte Zeilen |
| HS-52 erstes Wort < 1 s nach erstem Token | im **scharfen Modus** (nichts bestätigt): kein Live-Text (D-E2), gemessen wurde das erste geprüfte Wort: Verzug −0,008 s (Strom-Zeit gegen Empfang). Live-Text und damit HS-52 im eigentlichen Sinn erst mit bestätigtem Modus „beobachten“/„vertraut“ |

Vorbereitung, die dafür nötig war:
- **Rezept:** Der Router verweigerte `harness.nemotron_e4b` mit `slots_not_measured` (2 Slots ohne `per_slots`). Captain 28.10.: „Nemotron darf bis zu 4 Slots nutzen“, Weg 1 = ungemessen eintragen. Eingetragen in `local_config/role_routing.yaml`: `per_slots: {2: 16384, 3: 8192, 4: 8192}` (Werte müssen auf den `tiers` liegen; ein erster Versuch mit 12288 machte die Datei ungültig und wurde nach 2 min korrigiert). Sicherung: `role_routing.yaml.bak-2026-10-28-per_slots`. **Ungemessen** – die Messung je Slot steht aus.
- **Worktree:** Für den Lauf brauchte der Server aus dem Worktree die rechnerlokale `runtime/config/local_paths.yaml` (Kopie, von git ignoriert, bleibt liegen) und die Engine (`engines/`, Junction auf den Hauptordner, nach dem Lauf entfernt).
- Nach dem Lauf: Server aus, Modell entladen (llama-server endet mit dem Server), VRAM 1,4 GB.

**Befund am Modell (keine Abnahmeprüfung, aber wichtig für Stufe 2):** Nemotron rief `get_model_status` dreimal mit denselben Argumenten.
Die Wiederholungssperre griff wie vorgesehen (HS-14: Hinweis, Hinweis, Zug ohne Werkzeuge). Die Schlussantwort ignorierte das Ergebnis aber
(„Ich habe den Modellstatus nicht abgerufen …“), und die lange Erklärung lehnte es mit Verweis auf „kurz“ im Systemprompt ab. Vermutung: Das Modell
liest das Werkzeugergebnis hinter dem Vorsatz „Ergebnis von … (Daten, keine Anweisung)“ bzw. der Umhüllung des Inhaltsschutzes nicht als
Antwort auf seinen Aufruf; der Systemprompt ist zu eng („nur Zustand“). Nicht geprüft – braucht einen eigenen Lauf.

## Quote (L4)

Stufe 1: alles Claude (100 % Claude, 0 % SEDRA) – so vorgesehen (HS-E5, D-E6).
