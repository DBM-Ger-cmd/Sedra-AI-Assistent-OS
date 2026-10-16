# TICKET B6-G-01 – Nacharbeit KI GateWay Studio, Prototyp GUPPI/SEDRA Build 20 (IMPLEMENTED/TESTED, 15.10.2026)

**Status:** Ticket freigegeben durch Klaus (Chat 15.10. 13:4x, Q2: „Ja, Block A ohne G-07“; P3 = Review bleibt). Code umgesetzt und auf Linux getestet. **Nicht abgenommen.** Gate für die Abnahme: Klaus (Prototyp ist seine Linie), technisch David, falls der Stand in die B6-Linie zurückfließt.
**Prüfgegenstand vorher:** `GUPPI_Runtime_v1.20_Build_020_2026-10-15.zip`, SHA-256 `1e918b97…c80d`.
**Ergebnis:** `GUPPI_Runtime_v1.20_Build_020_B6-G-01_2026-10-15.zip` (Prüfsumme im Changelog-Abschnitt unten) und `PATCH_B6-G-01_Build020_2026-10-15.diff` (11 Dateien, +314/−37 Zeilen).
**Nicht im Ticket:** G-07 (Kernklassifikation E3), G-02 (Erkennung P02/V01, betrifft B6-Code), Cloud, Versand, Agenten, Rollen.
**Grundlage:** `BEWERTUNG_PROTOTYP_GUPPI-SEDRA_BUILD20_GEGEN_B6_2026-10-15_PROPOSED.md`, Abschnitte 4–8.

## (a) IST-Stand vor der Änderung (belegt, eigener Lauf 15.10.)
- G-01: Vorgang mit IBAN endet in `FEHLER B6_PSEUDO_RECHECK_FAILED`; `vorgang.pruefen` pseudonymisiert immer, `b6core.pseudo` kennt keinen Platzhaltertyp für F01/F02, der Recheck meldet die verbliebene IBAN.
- G-04: `runtime.py` erzeugt `ContentGuard(mode='beobachten')`; `uix_server.sync_guard_mode` setzt bei nicht bestätigtem Projekt `beobachten`. Außerhalb des GateWay-Vorgangs waren Funde nur gezählt, nicht gestoppt.
- G-05: Bindung der Freigabe über Anfrage, Dokument, Policyversion, Klasse, Merkmale, Weg, Übergabeprompt – ohne Zweck und Person.
- G-06: kein Weg, den B6-Korpus gegen `klassen.einstufen` zu messen.

## (b) Annahmen
- Nur-lokal-Verarbeitung mit Originaltext entspricht dem B6-Stand (Pseudonymisierung ist der Cloudpfad, K04-PSEUDO-01). Für SK3-Fälle, die sich pseudonymisieren lassen, bleibt der GUPPI-Weg (Platzhalter auch lokal) unverändert.
- Zweckliste = Aufgabenarten aus Vorgehen v2 (Antwortentwurf, Zusammenfassung, Übersetzung, Frage an die Wissensbasis). Verantwortliche Person ist Freitext, Standard „Captain“, weil SEDRA keine Rollen kennt; sie ist Teil der Bindung, aber nicht authentifiziert.
- Das Korpus-Schema ist aus `K04_Ist_Messung_Skript_2026-10-13.py` abgeleitet; die Korpusdatei selbst lag nicht vor.

## (c) Umsetzung

| Nr | Änderung | Datei |
|---|---|---|
| G-01 | `pruefen`: Pseudonymisierung läuft; schlägt der Recheck fehl **und** ist nur `LOCAL_ONLY` erlaubt, geht der Text ohne Platzhalter weiter (`uebergabe.unpseudonymisiert`, Grund nennt das Merkmal, z. B. „Bankverbindung“). Ist ein Cloudweg erlaubt, bleibt `FEHLER` (fail-closed). Recheck-Liste im Entwurf nennt den Fall. Gemeinsamer Helfer `_ohne_platzhalter`; der S02-Sonderfall nutzt ihn ebenfalls (P3: Review). | `gateway/vorgang.py` |
| G-04 | Standard des Inhaltsschutzes ist `sandbox` (scharf): im Konstruktor, in der Runtime und bei nicht bestätigtem Projekt. Unbekannter Modus → scharf. „Beobachten“ und „Vertraut“ nur als bestätigter Projektmodus. | `core/content_guard.py`, `runtime.py`, `uix_server.sync_guard_mode` |
| G-05 | `Vorgang.zweck` (aus `ZWECKE`) und `Vorgang.verantwortlich` (max. 80 Zeichen, nie leer); `pruefen(..., zweck, verantwortlich)` mit Fehlern `zweck_unbekannt`, `verantwortlich_fehlt`; beide in `_bindung`; Gate-Titel nennt Zweck und Person; `GET /api/gateway/vorgaenge` liefert `zwecke`; Werkzeug: Auswahl Zweck + Feld Person in Station 02, Anzeige in Station 03. | `gateway/vorgang.py`, `uix_server.py`, `uix/tools/gateway/tool.js`, `tool.css` |
| G-06 | Messadapter `benchmarks/b6_korpus_gegen_guppi.py`: liest Korpus-JSON, wertet nur `input`, vergleicht Status/Weg/Merkmale mit `expected`, Bericht als Markdown/JSON mit PASS/FAIL/NOT_TESTABLE und „kritische Falschfreigabe“. Beispieldatei `b6_korpus_beispiel.json` (6 synthetische Fälle). | `runtime/benchmarks/` |

## (d) Tests (zuerst rot, dann grün)

| Test | Prüft | Ergebnis |
|---|---|---|
| `test_gateway.DerVorgang.test_g01_an_iban_case_is_sk2_local_without_placeholders` | IBAN → GEPRUEFT, SK2, nur lokal, ohne Platzhalter, Modell erhält Original, 2 Recheck-Einträge | grün |
| `…test_g01_a_cloud_capable_case_that_cannot_be_pseudonymized_stays_an_error` | SK1 mit Recheck-Fehler bleibt FEHLER | grün |
| `…test_g05_purpose_and_person_are_part_of_the_binding` | Standardwerte, Fehler bei unbekanntem Zweck/leerer Person, drei verschiedene Bindungen | grün |
| `test_gateway.DurchDenHub.test_g05_the_gate_names_purpose_and_person` | Route, Gate-Titel, Bindung in der Mission | grün |
| `test_gateway.DerKorpusAdapter.test_the_adapter_measures_and_names_critical_misses` | Adapter auf Beispieldatei, kritische Falschfreigabe sichtbar | grün |
| `test_content_guard.S5_Modus.test_unconfirmed_is_sharp_and_observe_is_a_deliberate_choice` (ersetzt `…is_observe…`) | Standard scharf, Sync stellt Projektmodus wieder her | grün |
| `test_content_guard.S5_Modus.test_observe_lets_through_and_shows_what_it_saw` | angepasst: Beobachten wird ausdrücklich gesetzt | grün |
| `test_uix_flows.Flows.test_the_gateway_studio_flow_from_request_to_checked_draft` | erweitert: Person eingetragen, in Station 03 sichtbar (Browser, Playwright) | grün (6/6 im Modul) |
| Volle Suite | 2.093 Tests | siehe Abschnitt (f) |

**Bewusst geänderte Alt-Erwartung:** `test_unconfirmed_is_observe_and_sandbox_is_sharp` setzte „nichts bestätigt = beobachten“ voraus (Designentscheidung des Prototyp-Autors, Build 16). Mit G-04 gilt „nichts bestätigt = scharf“. Keine Erwartung wurde stillschweigend entfernt.

## (e) Ergebnis des Adapters auf der Beispieldatei
6 Fälle: 4 PASS, 1 FAIL, 1 NOT_TESTABLE, 1 kritische Falschfreigabe (`BSP-SK3-01`, Gesundheitsangabe → SK0). Das ist G-02 und bleibt offen. Der Lauf auf dem echten Korpus (93 Fälle) braucht `KIMOAN_Testdaten_Gesamt_2026-10-13_v1.0.json` bzw. `data/kimoan/` aus dem B6-Build.

## (f) Volle Suite (Linux, Python 3.13, 15.10. 13:55)
2.093 Tests, 1 Fehler = bekannter Umgebungsfehler `test_uix_kommandodeck … library_not_built` (fehlende `skill_library/index.json`, vor der Änderung identisch), 49 übersprungen. Laufzeit 371 s. Windows und echtes Modell: nicht gelaufen.

## (g) Offen nach diesem Ticket
Siehe `OFFENE_PUNKTE_GUPPI_B20_2026-10-15_PROPOSED.md`. Wichtigste: G-02 (beide Linien), Abnahme dieses Stands, Lauf auf dem echten Korpus, Lauf mit echtem Modell (Station 04 nach G-01 nur mit Fake-Modell geprüft), Windows-Lauf.
