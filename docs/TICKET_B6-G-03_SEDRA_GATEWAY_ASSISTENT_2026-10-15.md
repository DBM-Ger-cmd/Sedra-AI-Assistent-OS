# TICKET B6-G-03 – SEDRA als Assistent in der KI-GateWay-Shell: Regelwerk, Leitfaden, Wissensbasis (IMPLEMENTED/TESTED, 15.10.2026)

**Status:** Plan und Prompt freigegeben durch Klaus (Chat 15.10. 14:27, Q2; E1–E4: ja / Wissensbasis vor Modellwissen / Bezeichnung „Nutzer“, nur Audit / Frist 24 h). Umgesetzt und auf Linux getestet. **Nicht abgenommen.** Gate: Klaus (Prototyp-Linie); Übernahme in die B6-Linie nach dem 20.10. (David).
**Vorher:** Build 20 + B6-G-01 (ZIP `07f1b30f…337f`). **Ergebnis:** `GUPPI_Runtime_v1.20_Build_021_B6-G-03_2026-10-15.zip`, SHA-256 `08670f1c40db40d13de5b7c4bf4a0b3a9ba4301b933df2349953bf7d6ebe9181`; Patch `PATCH_B6-G-03_Build021_2026-10-15.diff`, SHA-256 `3f49b41e…f399a` (28 Dateien, +1.656/−224 Zeilen, inkl. Doku).
**Grundlagen:** `REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15_PROPOSED.md`, `PLAN_UND_PROMPT_SEDRA_ALS_GATEWAY_ASSISTENT_2026-10-15_PROPOSED.md` (AP1–AP8), Entscheidungen Klaus 14:03–14:27.

## (a) Was gebaut ist (je Arbeitspaket)

| AP | Inhalt | Dateien | Tests |
|---|---|---|---|
| Regelwerk | `REGELN` R-01…R-16 in der Matrix, Policyversion `b6-datenregeln-0.1`, A01 (manuell, R-13), P01 nur lokal (`RECHTSGRUNDLAGE_CLOUD=False`), Regelnummer vor jedem Grund, R-14 KI-Kennzeichnung des Entwurfs | `gateway/klassen.py`, `gateway/vorgang.py`, `uix_server.py` | `test_gateway.DasRegelwerk` 12, Matrix-Tests angepasst |
| AP1 | Wissensbasis `gateway/wissen.py`: SQLite (`wissen`, `eigene`), Leitfaden 7 Schritte, Zustände, Fehlercodes, Begriffe, Synonyme, Stoppwörter, Live-Zustand; `antwort()` mit sieben Antwortarten, Knöpfe nur `open` auf `gateway` | `gateway/wissen.py` | `test_gateway_wissen` 14 |
| AP2 | `chat_reply`: Wissensbasis vor dem Modell (`zustaendig()`), Audit `UIX_CHAT_GATEWAY_WISSEN` ohne Text; `POST /api/gateway/frage`; `talk` schickt den offenen Vorgang mit, zeigt die Quelle | `uix_server.py`, `uix/tools/talk/tool.js`, `tool.yaml` | `test_gateway.DasGespraech` 4 |
| AP3 | Modellwerkzeuge `gateway_status`, `gateway_vorgang` (nie Anfragetext), `gateway_regel`, `gateway_leitfaden`, `gateway_pruefe_text`; `open_object gateway`; `CHAT_TOOL_NOTE`, `CHAT_STATE_WORDS` | `chat_tools.py`, `uix_server.py` | `test_gateway.DieWerkzeugeDesModells` 2 |
| AP4 | Werkzeug `gateway` 1.1: A01, Spalte „Regel“, Leitfaden je Station und als Block (aktueller Schritt), „Frag SEDRA“ mit „Merken“, Kennzeichnung über dem Entwurf; Frist `entwuerfe_loeschen_nach_stunden: 24` (festes Datum = Obergrenze) | `uix/tools/gateway/tool.js`, `tool.css`, `tool.yaml`, `gateway/vorgang.py` | `test_uix_flows` 6 (Browser), `test_gateway` Fristtest |
| AP5 | Werkzeug `regelbuch` (CORE, Nachweis neben einem Vorgang, Suchfeld, Vorbehalt) | `uix/tools/regelbuch/*`, `benchmarks/uix_check.py` | `uix_check --tool regelbuch` ok; vier Shells 30/30 |
| AP6 | `POST /api/gateway/wissen`: eigener Eintrag des Nutzers, Längen 300/2000, kein Gate, Audit `GW_WISSEN_EINTRAG` ohne Text | `uix_server.py` | `test_gateway` 1 |
| AP7 | `gateway`, `gateway_wissen`, `content_guard`, `b6core` sind Kern (E3) | `selfdev/evolution_targets.py` | `test_evolution_targets` 1 |
| Bezeichnung | „Nutzer“ statt „Captain“ im GateWay-Modul (Standard der verantwortlichen Person, Texte); SEDRA-weit unverändert | gateway/*, tool.js | angepasst |
| Doku | `BUILD_21_GATEWAY_ASSISTENT_2026-10-15.md`, CHANGELOG Build 21, Logbuch (3 Zeilen), README, BUILD.txt, Werkzeug-README | docs/ | – |

Nicht geändert: `core/content_guard.py`, `core/guard.py`, `core/audit.py`, `models/router.py`, `desk/decisions.py`, `core/b6core/*`.

## (b) Abnahme (Linux, Python 3.13, 15.10. 15:10)
| Was | Ergebnis |
|---|---|
| `test_gateway` 46 · `test_gateway_wissen` 14 · `test_content_guard` 27 · `test_evolution_targets`, `test_uix_contract`, `test_desk_gateway`, `test_uix_guppi_moves` | alle grün |
| `test_uix_flows` (Browser, Playwright): Regelnummer, Leitfaden-Schritt, Frag SEDRA ohne Modellaufruf, Kennzeichnung nein→ja, A01 → SK3/R-13 | 6/6 |
| `uix_check` Cockpit / Minimal / Paperclip / GateWay Studio | 30/30 · 30/30 · 30/30 · 30/30 |
| Volle Suite | **2.127 Tests**, 1 Fehler = bekannter Umgebungsfehler `library_not_built`, 49 übersprungen (396 s) |
| Nicht gelaufen | Windows; Lauf mit echtem Modell (Station 04, Modellwerkzeuge `gateway_*`); B6-Korpus (Datei fehlt) |

Bewusst geänderte Alt-Erwartungen (keine stillschweigend): `test_personal_data_is_sk1…cloud_only_pseudonymized` → `…local_only_until_a_legal_basis_is_on_record` (R-01); `test_the_wish_may_only_be_more_restrictive` (Cloud für P01 nur mit `RECHTSGRUNDLAGE_CLOUD`); `test_cloud_is_simulated_and_rehydrated` und `test_g01_a_cloud_capable_case…` setzen `RECHTSGRUNDLAGE_CLOUD=True` im Test; Löschdatum-Erwartungen auf 24 h; Merkmale 13 → 14; Standard „Captain“ → „Nutzer“.

## (c) Grenzen
- Die Wissensbasis erkennt Fragen über Wortlisten; Unbekanntes landet beim besten Regelbuch-Treffer oder beim nächsten Schritt und sagt das.
- Normbezüge im Regelbuch sind Annahmen; keine Aussage „DSGVO-/AI-Act-konform“; Datenschutzreview offen.
- Die verantwortliche Person ist nicht authentifiziert (Pilotannahme). Eigene Einträge lassen sich nur von Hand in der SQLite löschen.
- G-02 (P02/V01-Erkennung) bleibt offen – der Adapter-Beispiellauf zeigt die Lücke als kritisch.

## (d) Offen nach diesem Ticket
Abnahme durch Klaus (Windows-Lauf, echtes Modell, Durchspielen Leitfaden 1–7 und „Frag SEDRA“); Korpusdatei → Adapterlauf; G-02 (B6-P1-02); B6-P1-03 Schnittstellenvertrag (Option C, nach 20.10.); B6-P1-04 P3 in der B6-Linie (nach 20.10.); P6-Dateien ins Quellenmanifest.
