# Plan und Umsetzungsprompt: SEDRA als Assistent in der KI-GateWay-Shell (PROPOSED, 15.10.2026, 14:30)

**Status:** Q3. Plan auf Wunsch von Klaus (Chat 14:20: „erst einmal voll durchplanen und darauf einen umfassenden Prompt erstellen, der den Plan abdeckt und wie man ihn in der Shell und mit dem SEDRA-Kern umsetzt“). Grundlage: Entscheidungen Klaus 14:03 (P1–P6), 14:08 (Regelwerk als verbindliche Regel), 14:12 (Wissensbasis, Fragen im Chat), 14:14 („SEDRA soll die Shell wie seine Arbeitsumgebung sehen“), 14:19 (Leitfaden vom Anlegen bis zum Ablegen als Teil des Moduls).
**Prüfgegenstand:** Prototyp Build 20 + Ticket B6-G-01 (ZIP SHA-256 `07f1b30f…337f`) + Zwischenstand B6-G-03 (Git-Commit `9915aa2` in der Arbeitskopie, **nicht abgenommen**, siehe Abschnitt 2).
**Gate:** Klaus für den Plan und den Prompt; technisch Klaus (Prototyp-Linie). Übernahme in die B6-Linie: David, nach dem 20.10.

---

## 1. Ziel in einem Satz
SEDRA kennt die KI-GateWay-Shell als seine Arbeitsumgebung: das Regelbuch (R-01…R-16), den Leitfaden (sieben Schritte vom Anlegen bis zum Ablegen), den Live-Zustand jedes Vorgangs und die Fehlercodes – und beantwortet im Gespräch konkrete Fragen („Was muss ich als Nächstes machen?“, „Wo ist der Fehler in diesem Text?“, „Warum ist der Vorgang gesperrt?“, „Wo liegt der Entwurf?“) deterministisch, auch ohne geladenes Modell; ein geladenes Modell nutzt dieselbe Wissensbasis als Werkzeug. Jede Handlung bleibt ein Knopf für den Captain, jede Freigabe ein Gate.

## 2. Belegter IST-Stand (Arbeitskopie, Linux, 15.10.)

| Baustein | Stand | Beleg |
|---|---|---|
| Regelwerk v0.1 in der Matrix | **implementiert, getestet**: `gateway/klassen.py` mit `REGELN` R-01…R-16, `POLICY_VERSION = 'b6-datenregeln-0.1'`, A01 (manuell), R-01 nur lokal (`RECHTSGRUNDLAGE_CLOUD = False`), jeder Grund mit Regelnummer | `test_gateway.DasRegelwerk` 12 Tests, Matrix-Tests angepasst |
| KI-Kennzeichnung R-14 | implementiert, getestet: `Entwurf.kennzeichnung` („KI-Entwurf (modell) – menschlich geprüft: nein/ja“), in `GET /api/gateway/vorgang` | `test_the_studio_flow_example_local`, `test_the_whole_way` |
| Regelbuch in der API | implementiert: `GET /api/gateway/vorgaenge` liefert `regeln`, `policy_version`, `regelwerk` | `test_the_whole_way` |
| Wissensbasis | **implementiert, von Hand geprüft, noch ohne Unit-Tests**: `gateway/wissen.py` – SQLite `local_config/gateway/wissen.sqlite`, Tabellen `wissen` (aus Code gefüllt, Versionsstempel) und `eigene` (Einträge des Captains); Inhalte: Regeln, Merkmale, Zustände, Fehlercodes, Begriffe, **Leitfaden (7 Schritte)**, Ablauf; `antwort()` mit sechs Antwortarten (Text prüfen, nächster Schritt, Fehler am Vorgang, Leitfaden/Ablage, Stand, Regelbuch) und Knöpfen (`ui_actions`, Typ `open` auf `gateway`-Objekte) | Probelauf 14:19 (sieben Fragen, Ausgabe im Chat) |
| Chat-Anbindung | **nicht implementiert** | – |
| Shell/Werkzeug (A01, Regelnummern, Leitfaden, Kennzeichnung sichtbar) | **nicht implementiert** | – |
| Werkzeuge für das Modell (`gateway_*` in `chat_tools.py`) | nicht implementiert | – |
| Volle Suite auf dem Zwischenstand | nicht gelaufen (nur `test_gateway` 38, `test_content_guard` 27 grün) | – |

Nicht geändert: `core/content_guard.py`, `core/audit.py`, `core/guard.py`, `desk/decisions.py`, `models/router.py` – der Sicherheitskern bleibt, wie er nach B6-G-01 ist.

## 3. Architektur: wie SEDRA die Shell „sieht“

```
Captain ── Gespräch (Zone unten im Studio, Werkzeug talk) ──► POST /api/chat/reply
                                                                 │
                        ┌────────────────────────────────────────┤
                        │ zuständig? (gateway-Wörter, GW-ID,     │ nicht zuständig
                        │ aktive Shell = gateway-studio +        │
                        │ Frage nach Schritt/Fehler/Stand)       ▼
                        ▼                                   Modell (llama-server) mit ChatTools
               GatewayWissen.antwort()                      – kann gateway_status, gateway_vorgang,
               deterministisch, kein Modell                  gateway_regel, gateway_leitfaden,
               Regelbuch + Leitfaden + Live-Zustand          gateway_pruefe_text aufrufen (lesend)
               + Fehlercodes                                 – schlägt Öffnen/Handlung vor (ui_actions)
                        │                                        │
                        └──────────────► Antwort + Knöpfe ◄───────┘
                                                │
                              Klick des Captains: ctx.shell.open / POST /api/actions
                              (derselbe Weg wie jeder Knopf im Werkzeug; Freigaben = Gate)
```

Grundsätze, die der Plan nicht verletzt (Projektanweisung, SPEC_EIN_SICHERER_WEG, SHELL_WERKZEUG_VERTRAG):
1. Der Inhaltsschutz bleibt die eine Stelle für Modellaufrufe; die Wissensbasis ruft kein Modell und kein Netz.
2. Die Wissensbasis speichert keinen Vorgangstext – nur Zustand, Klasse, Merkmale, Regeln, Hashes.
3. Nichts läuft durch eine Antwort von selbst; jede Handlung ist ein Knopf, jede Freigabe eine Entscheidung mit Bindung.
4. Das Modell hat kein Freigaberecht; seine Werkzeuge sind lesend plus „vorschlagen“.
5. Werkzeuge sprechen nur `ctx.api`; keine eigene Speicherung im Browser außer Anzeige-Komfort.

## 4. Arbeitspakete

| AP | Inhalt | Dateien | Tests (zuerst rot) | Aufwand |
|---|---|---|---|---|
| **AP1 Wissensbasis absichern** | Unit-Tests für `gateway/wissen.py`: jede Antwortart, Leitfaden-Schritt je Zustand, Text-Prüfung mit Regelnummern und Entdoppelung, `zustaendig()` je Shell, `eigene`-Einträge überleben Neustart, kein Vorgangstext in der SQLite | `tests/test_gateway_wissen.py` (neu) | 12–15 Tests | klein |
| **AP2 Chat-Anbindung** | In `uix_server.chat_reply`: vor `no_model` → wenn `GatewayWissen.zustaendig(text, aktive_shell)` → `self.gw_wissen.antwort(text, payload.get('vorgang'))` als `{'status':'completed','reply':…,'model':'gateway-wissen','ui_actions':[…],'mission_id':…}`; Audit `UIX_CHAT_GATEWAY_WISSEN` (Art der Antwort, kein Text). Property `gw_wissen` wie `gw`. Aktive Shell aus `self.gateway.registry.config()['shell']`. Route `POST /api/gateway/frage` für das Werkzeug (gleiche Funktion, ohne Chat-Historie). Das Werkzeug `talk` sendet `vorgang` mit, wenn ein Vorgang offen ist (Bus-Ereignis `object.open` merken) | `uix_server.py`, `uix/tools/talk/tool.js` | Hub-Tests: Frage ohne Modell → Antwort aus der Wissensbasis; Frage mit Modell und Gateway-Wort → Wissensbasis vor dem Modell; Frage ohne Gateway-Bezug im Cockpit → unverändert `no_model`/Modell; Audit ohne Text | mittel |
| **AP3 Werkzeuge für das Modell** | `chat_tools.py`: `gateway_status` (Vorgänge, Zustände), `gateway_vorgang(id)` (Einstufung, Regeln, nächster Schritt – kein Anfragetext), `gateway_regel(frage)` (Suche im Regelbuch), `gateway_leitfaden(schritt?)`, `gateway_pruefe_text(text)` (Funde mit Regelnummer; der Text kommt vom Captain, nicht aus dem Vorgang); `open_object` erlaubt `gateway`; `CHAT_TOOL_NOTE` ergänzt: „Fragt der Captain nach dem GateWay, einem Vorgang, einer Regel, dem Ablauf oder einem Fehler, rufe erst `gateway_*`“; `CHAT_STATE_WORDS` um Gateway-Wörter | `chat_tools.py`, `uix_server.py` | Werkzeug-Tests mit Fake-Modell: jedes Werkzeug liefert nur erlaubte Felder; `gateway_vorgang` enthält nie `anfrage`; `open_object gateway` ergibt `ui_action` | mittel |
| **AP4 Werkzeug `gateway` (Shell)** | Station 02: Kästchen **A01** neben R01; Station 03: Regelnummer vor jedem Grund, Merkmale-Tabelle mit Spalte „Regel“, Link „Regel ansehen“ → öffnet das Regelbuch; Station 04: **Kennzeichnung** sichtbar über dem Entwurf; Kopf der Sammlung: **Leitfaden** als aufklappbare Liste (7 Schritte, aktueller Schritt hervorgehoben, aus `GET /api/gateway/vorgaenge` → `leitfaden`); je Station eine Zeile „Leitfaden Schritt n: …“; Feld „Frag SEDRA“ unter dem Leitfaden → `POST /api/gateway/frage`, Antwort mit Knöpfen | `uix/tools/gateway/tool.js`, `tool.css`, `uix_server.gateway_list` (`leitfaden`) | `test_uix_flows`: A01 ankreuzen → SK3/Review; Regelnummer im Grund sichtbar; Leitfaden zeigt Schritt 4 bei GEPRUEFT; Kennzeichnung im Entwurf; Frage im Feld → Antwort; `uix_check --tool gateway` | mittel |
| **AP5 Regelbuch-Ansicht** | Neues kleines Werkzeug `regelbuch` (CORE, Slot `nachweis`, Objekt `gateway`): Tabelle R-01…R-16 mit Kategorie, Bezug, Lokal/Cloud/Prüfung, „Was tun“; Hinweis „Normbezüge sind Annahmen des Teams, keine Rechtsprüfung“; Versionsnummer. Im Studio als Nachweis neben dem Vorgang | `uix/tools/regelbuch/` (tool.yaml, tool.js, tool.css, README) | `uix_check --tool regelbuch`; Studio-Abnahme bleibt 29/29 + 1 | klein |
| **AP6 Eigene Einträge** | `POST /api/gateway/wissen` {frage, antwort} mit Gate? Nein: eigene Einträge sind Captain-Wissen ohne Wirkung nach außen → kein Gate, aber Audit `GW_WISSEN_EINTRAG` (ohne Text) und Längenbegrenzung; Anzeige unter „Frag SEDRA“ als „Merken“ | `uix_server.py`, `gateway/wissen.py`, `tool.js` | Eintrag taucht in `suche()` auf; Länge begrenzt; kein Vorgangstext | klein |
| **AP7 Selbstentwicklung (G-07)** | `gateway`, `wissen`, `content_guard`, `b6core` in `selfdev/evolution_targets.CORE_TARGETS` (E3) | `evolution_targets.py` | Ziel `gateway` → E3 | klein |
| **AP8 Abnahme** | `test_gateway`, `test_gateway_wissen`, `test_content_guard`, `test_uix_flows`, `test_uix_contract` (Werkzeugvertrag für `regelbuch`), volle Suite; `uix_check` für Cockpit/Minimal/Paperclip/Studio; Windows-Lauf; Lauf mit echtem Modell durch Station 04 und durch eine Modellfrage mit `gateway_*`; Korpus-Adapter auf dem echten Korpus, sobald die Datei da ist | – | Abnahmeblatt | – |

Reihenfolge: AP1 → AP2 → AP4 → AP3 → AP5 → AP6 → AP7 → AP8. AP3 erst nach AP2, damit der deterministische Weg immer funktioniert, bevor das Modell dazu kommt.

## 5. Datenmodell der Wissensbasis (ist so gebaut)

| Tabelle | Spalten | Inhalt | Lebensdauer |
|---|---|---|---|
| `wissen` | id, art (regel/merkmal/zustand/fehler/begriff/leitfaden/ablauf), titel, text, tun, stichworte, version | aus dem Code, bei jedem Start neu (Versionsstempel = Policyversion) | bis zum nächsten Start |
| `eigene` | id, frage, antwort, erstellt | Einträge des Captains | bleibt |
| Live-Zustand | – | aus `GateWay.liste()` / `vorgaenge` zur Laufzeit | nicht gespeichert |

Pfad: `local_config/gateway/wissen.sqlite`. Keine Netzverbindung, kein Modellaufruf, kein Vorgangstext.

## 6. Der Leitfaden (ist so hinterlegt; Quelle für Shell und Antworten)

| Nr | Station | Zustand | Titel | Der Mensch | SEDRA hilft |
|---|---|---|---|---|---|
| 1 | 00 | – | Vorbereiten | nur synthetische/freigegebene Daten; Dokument als .md/.txt ins Projekt; Verantwortliche Person und Zweck klären | Dateien zeigen, Regeln nennen, Text vorab prüfen |
| 2 | 01 | NEU | Vorgang anlegen | Titel, Wunsch lokal/Cloud (simuliert) | GateWay öffnen, sagen ob Modell geladen |
| 3 | 02 | NEU | Eingeben und prüfen lassen | Anfrage, Dokument, Zweck, Person, R01/A01 von Hand, „Datenschutz prüfen“; warten: Sekunden; Ergebnis GEPRÜFT/GESPERRT/FEHLER | jeden Fund mit Regelnummer erklären |
| 4 | 03 | GEPRUEFT | Empfehlung lesen und freigeben | Klasse, Merkmale, Regeln, Wege; Freigabe = Entscheidung mit Bindung; bei Review-Pflicht ist die Freigabe R1 | Einstufung erklären, Entscheidungen öffnen |
| 5 | 03→04 | WARTET | Auf die Auswertung warten | nichts ändern; Modell durch den Inhaltsschutz; Rechecks 2/3; Ergebnis ENTWURF/FEHLER | Modellstatus, Fehlercode mit Abhilfe |
| 6 | 04 | ENTWURF | Entwurf prüfen (R2) | erfundene Zusagen/Preise, Rückübersetzung, Kennzeichnung; „Geprüft“/„Verwerfen“ | Entwurf auf Funde prüfen, Löschdatum nennen |
| 7 | Ablage | ABGESCHLOSSEN | Ablegen | kein Versand; Entwurf vor dem Löschdatum von Hand übernehmen; Vorgang an die Ablage heften | Löschdatum, Logbuch, Stand |

Ablageorte: `local_config/gateway/vorgaenge/<GW-…>.json` (ohne Entwurfstext), `entwuerfe/<GW-…>.json` (bis Löschdatum), Audit-Kette `GW_*` (ohne Text).

## 7. Risiken und Grenzen
- **Heuristik:** Die Wissensbasis erkennt Fragen über Wortlisten. Unbekannte Formulierungen landen beim Regelbuch-Suchtreffer oder beim nächsten Schritt; sie sagt dann „dazu steht nichts im Regelbuch“. Kein Modell im deterministischen Pfad – das ist Absicht.
- **Zuständigkeit:** Im Studio werden Fragen nach Schritt/Fehler/Stand von der Wissensbasis beantwortet, auch wenn ein Modell geladen ist. Fragen zum Modell/Kontext gehen weiter an das Modell. Grenzfälle brauchen Tests (AP2).
- **Text in der Frage:** „Wo ist der Fehler in diesem Text: …“ scannt den Text im Prozess, speichert ihn nicht; der Scan selbst ist der B6-Scanner mit seinen Grenzen (G-02 bleibt).
- **Rechtsbezüge** im Regelbuch sind Annahmen; der Datenschutzreview steht aus.
- **Modellwerkzeuge (AP3):** Ein kleines Modell kann Werkzeugergebnisse falsch wiedergeben; deshalb liefert `gateway_vorgang` nie den Anfragetext, und die Oberfläche zeigt die deterministische Antwort zusätzlich als Nachweis.

## 8. Entscheidungen
| Nr | Frage | Vorschlag | Wer |
|---|---|---|---|
| E1 | Plan und Prompt (Abschnitt 9) freigeben | ja, AP1–AP8 in dieser Reihenfolge | Klaus |
| E2 | Antwortet die Wissensbasis im Studio **vor** dem Modell, auch wenn eines geladen ist? | ja (deterministisch zuerst; das Modell bekommt die Werkzeuge für alles Übrige) | Klaus |
| E3 | Eigene Einträge des Captains ohne Gate, mit Audit? | ja | Klaus |
| E4 | P5-Zahl für die Entwurfsfrist (Vorschlag 24 h) – im selben Ticket umsetzen? | ja, als AP4-Nebenpunkt in `vorgaben.yaml` | Klaus |

---

## 9. Der Umsetzungsprompt (für die SEDRA-Entwicklungssitzung)

> Bearbeite Ticket **B6-G-03 „SEDRA als Assistent in der KI-GateWay-Shell“** auf der Arbeitskopie `GUPPI_Runtime_v1.20` (Stand: Build 20 + B6-G-01 + Commit `9915aa2`). Grundlage sind `docs/REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15_PROPOSED.md`, `docs/PLAN_UND_PROMPT_SEDRA_ALS_GATEWAY_ASSISTENT_2026-10-15_PROPOSED.md` (dieser Plan, Abschnitte 3–6) und die Regeln in `docs/ENTWICKLUNG.md`. Sprache Deutsch, Formulierung „wir“, keine Marketingsätze.
>
> **Phase A – nachgewiesener Stand.** Lies vollständig: `gateway/klassen.py`, `gateway/vorgang.py`, `gateway/wissen.py`, `uix_server.py` (Abschnitte `chat_reply`, `gateway_*`, `sync_guard_mode`, `object_view`), `chat_tools.py`, `uix/tools/gateway/tool.js`, `uix/tools/talk/tool.js`, `uix/shells/gateway-studio/shell.vorgabe.yaml`, `docs/SHELL_WERKZEUG_VERTRAG_v1.md`, `tests/test_gateway.py`, `tests/test_uix_flows.py`. Führe `test_gateway` und `test_content_guard` aus und nenne die Zahlen. Behaupte nichts, was du nicht gelesen oder ausgeführt hast.
>
> **Phase B – Plan.** Bestätige oder korrigiere die Arbeitspakete AP1–AP8 des Plans gegen den gelesenen Code: Schnittstellen (`ctx.api`, `ui_actions`, `object.open`, `POST /api/actions`), erwartete Fehlerfälle (kein Modell, kein Projekt, Vorgang in WARTET, ungültige Werkzeugargumente, zu lange Texte), Sicherheitsfälle (Anfragetext nie in Antwort an das Modell, keine Handlung ohne Klick, kein Gate-Umweg, kein Vorgangstext in der SQLite, Audit ohne Text). Nenne, was du nicht baust: keine Cloud, kein Versand, keine Rollen, keine Agenten, keine Änderung an `core/content_guard.py`, `core/guard.py`, `core/audit.py`, `models/router.py`, `desk/decisions.py`. Stoppe und frage, wenn ein Paket eine dieser Dateien bräuchte.
>
> **Phase C – kleinste Implementierung, in dieser Reihenfolge, je Paket ein Commit:**
> 1. **AP1** `tests/test_gateway_wissen.py`: zuerst rot. Je ein Test für: nächster Schritt ohne Vorgang / je Zustand (NEU, GEPRUEFT, WARTET, ENTWURF, GESPERRT, FEHLER mit Code); Text prüfen mit Steuer-ID und Passwort → zwei Funde mit R-04 und R-07, kein Duplikat; Leitfaden-Frage → sieben Schritte; „Schritt 7“ und „wo liegt der Entwurf“ → Ablage; Regelfrage „R-02“; Begriff „Pseudonymisierung“ → Begriffseintrag vor Fehlereintrag; Stand → Liste; `zustaendig()` für Studio/Cockpit; `eigene`-Eintrag überlebt eine neue Instanz; die SQLite enthält keinen Anfragetext (Vorgang mit „Lena Beispiel“ prüfen, Datei durchsuchen); jede Antwort trägt `quelle` mit der Policyversion; `ui_actions` sind nur `open` auf `gateway`.
> 2. **AP2** `uix_server.py`: Property `gw_wissen` (lazy, `GatewayWissen(self.project_root, self.gw)`); in `chat_reply` **vor** der Modellprüfung: `shell = self.gateway.registry.config().get('shell')`; wenn `GatewayWissen.zustaendig(text, shell)`: `out = self.gw_wissen.antwort(text, payload.get('vorgang'))`, Audit `UIX_CHAT_GATEWAY_WISSEN` mit `{'art': out['art'], 'shell': shell, 'actions': len(out['ui_actions'])}` (kein Text), Rückgabe `{'status': 'completed', 'reply': out['reply'], 'model': 'gateway-wissen', 'mission_id': mission_id or '', 'tools_used': [], 'proposals': [], 'ui_actions': out['ui_actions'], 'quelle': out['quelle']}`. Route `POST /api/gateway/frage` {frage, vorgang?} → dieselbe Antwort. `talk/tool.js`: merkt sich den zuletzt geöffneten `gateway`-Vorgang (Bus `object.open`, type gateway, id ≠ alle) und sendet `vorgang` mit; zeigt `quelle` klein unter der Antwort. Hub-Tests: Frage „Was muss ich als Nächstes machen?“ ohne Modell → `completed`, Modell `gateway-wissen`; Frage „welches Modell läuft“ ohne Modell → `no_model` wie bisher; mit Fake-Modell und Gateway-Wort → kein Modellaufruf (`adapter.calls == 0`); Audit-Zeile ohne Text.
> 3. **AP4** `uix/tools/gateway/tool.js`, `tool.css`, `gateway_list`: `leitfaden` in der Liste (`wissen.leitfaden()`), Leitfaden-Block im Sammlungskopf (`<details>`, aktueller Schritt je Vorgang mit Klasse `on`), je Station eine Zeile „Leitfaden Schritt n: Titel“; Kästchen A01 neben R01 (`manuell: ['R01','A01']` je nach Haken); Regelnummern stehen schon in den Gründen – zusätzlich Spalte „Regel“ in der Merkmale-Tabelle und Fußzeile „Regelwerk v0.1 · Normbezüge sind Annahmen, keine Rechtsprüfung“; Station 04: `entwurf.kennzeichnung` als Zeile über dem Text; „Frag SEDRA“: ein Eingabefeld + Knopf unter dem Leitfaden → `POST /api/gateway/frage` → Antwort als `s-note`, `ui_actions` als Knöpfe über `ctx.shell.open`. `vorgaben.yaml`-Standard: `entwuerfe_loeschen_nach_stunden: 24` statt festem Datum (`aufraeumen()` rechnet ab `erstellt`; altes Feld bleibt lesbar). Browser-Test in `test_uix_flows`: A01 ankreuzen → Station 03 zeigt SK3 und „R-13“; Leitfaden-Block nennt „Schritt 4“ bei GEPRUEFT; Kennzeichnung sichtbar; Frage im Feld → Antwort mit „Schritt“. `uix_check --tool gateway` und `--shell gateway-studio` grün.
> 4. **AP3** `chat_tools.py`: Schemas `gateway_status`, `gateway_vorgang` (id), `gateway_regel` (frage), `gateway_leitfaden` (schritt optional), `gateway_pruefe_text` (text, max. 20.000 Zeichen); Aufrufe über `self.hub.gw_wissen` und `self.hub.gw`; `gateway_vorgang` gibt `id, titel, zustand, zustand_wort, klasse, policy, review, wege, regeln, gruende, naechster_schritt` – **nie** `anfrage`, `dokument_text`, `uebergabe`; `open_object` nimmt `gateway` an (Objekt über `object_view('gateway', id)` – prüfe, ob die Sicht existiert; wenn nicht, über `self.hub.gw.get`). `CHAT_TOOL_NOTE` und `CHAT_STATE_WORDS` ergänzen (Gateway, Vorgang, Regel, Leitfaden, Schutzklasse). Tests mit Fake-Modell (Werkzeugaufruf erzwungen): jedes Werkzeug antwortet; `gateway_vorgang` enthält kein „Lena“; `gateway_pruefe_text` mit Passwort → R-07; `open_object gateway` → `ui_action` kind open.
> 5. **AP5** Werkzeug `regelbuch` nach `uix/tools/_template`: `tool.yaml` (id regelbuch, CORE, slot nachweis, handles [gateway], routes nur `GET /api/gateway/vorgaenge`), `tool.js` (Tabelle aus `regeln`, Suchfeld clientseitig, Fußzeile mit Vorbehalt), `tool.css` (nur `.t-regelbuch`, nur Token). In `shell.vorgabe.yaml` des Studios: Nachweis-Seitenleiste zeigt `regelbuch` bei Objekt `gateway`. `test_uix_contract` für das neue Werkzeug; `uix_check --tool regelbuch`.
> 6. **AP6** `POST /api/gateway/wissen` {frage ≤ 300, antwort ≤ 2000} → `gw_wissen.eintragen`, Audit `GW_WISSEN_EINTRAG` {laenge} ohne Text; Knopf „Merken“ unter einer Antwort im Werkzeug. Test: Eintrag erscheint bei der nächsten Frage; Längen begrenzt; keine Route für Löschen über die Oberfläche (von Hand in der SQLite, dokumentiert).
> 7. **AP7** `selfdev/evolution_targets.py`: `CORE_TARGETS` um `gateway`, `gateway_wissen`, `content_guard`, `b6core` ergänzen; Test `classify_target('gateway') == 'E3'`.
>
> **Phase D – Tests.** Je Paket die genannten Tests zuerst rot, dann grün; danach `test_gateway`, `test_gateway_wissen`, `test_content_guard`, `test_uix_flows`, `test_uix_contract`, `test_uix_kommandodeck`; am Ende die volle Suite (`run_tests`) und `benchmarks/uix_check.py` für Cockpit, Minimal, Paperclip, Studio. Nenne Zahlen nur aus tatsächlichen Läufen; der Umgebungsfehler `library_not_built` ist bekannt.
>
> **Phase E – Dokumentation.** `docs/BUILD_21_GATEWAY_ASSISTENT_2026-10-15.md` (was gebaut ist, was bewusst nicht, Abnahme-Tabelle), `docs/CHANGELOG.md` (Build 21), `docs/LOGBUCH_AGENT_MANAGER.md` (Zeile mit Uhrzeit), `README.md` (ein Satz unter „Was SEDRA heute kann“), `BUILD.txt` (build: 21), Werkzeug-README für `gateway` und `regelbuch`. Für das B6-Projekt: Ticketdoku `TICKET_B6-G-03_…`, Registernachtrag, Offene-Punkte-Liste v3, ZIP mit SHA-256.
>
> **Stoppregeln.** Stoppe und frage, wenn: ein Paket eine Datei des Sicherheitskerns ändern müsste; ein Test nur grün würde, wenn eine Alt-Erwartung fällt (dann nennen, nicht ändern); ein Werkzeug ohne Klick etwas ausführen würde; Vorgangstext in SQLite, Audit oder Modellwerkzeug gelangen würde; die volle Suite einen neuen Fehler zeigt. Gib am Schluss aus: Dateiliste mit Zeilenzahlen, Testergebnisse (nur ausgeführt), Prüfsumme des ZIP, Restpunkte.

---

## 10. Dateiänderungen am Sitzungsende (Vorschlag)
Dieser Plan ins Projekt und in `docs/` des Prototyps; Registernachtrag v1.3.21: Ticket B6-G-03 als PROPOSED mit Zwischenstand `9915aa2` (klassen, wissen, Kennzeichnung – implementiert, teils getestet, nicht abgenommen); Entscheidungen E1–E4 als OPEN; Offene-Punkte-Liste: AP-Tabelle als Nacharbeit, G-07 in AP7 aufgenommen.
