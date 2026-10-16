# Build 21: SEDRA als Assistent in der KI-GateWay-Shell – Regelwerk, Leitfaden, Wissensbasis (15.10.2026, Ticket B6-G-03)

**Klaus, 14:08:** *„Wir haben Daten, die wir laut DSGVO und EU AI Act nicht in die Cloud geben dürfen – mit diesen arbeiten wir erstmal als
verbindliche Regeln, so ist es einheitlich.“* **14:12:** *„Hinterlege eine Datenbank zu dem gesamten Modul, so dass ich eine Antwort zu der
spezifischen Frage erhalte – was muss ich als Nächstes machen, wo ist der Fehler in diesem Text.“* **14:14:** *„SEDRA soll die Shell wie seine
Arbeitsumgebung sehen.“* **14:19:** *„Vom Anlegen bis zum Eingeben der Dokumente, warten bis die Auswertung gemacht wurde und dann ablegen –
die Informationen dazu als Teil des Moduls.“* **14:27:** Freigabe des Plans; Wissensbasis vor Modellwissen; Bezeichnung „Nutzer“; Frist 24 h.
Plan und Prompt: `PLAN_UND_PROMPT_SEDRA_ALS_GATEWAY_ASSISTENT_2026-10-15_PROPOSED.md`. Regelwerk: `REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15_PROPOSED.md`.

## 1. Das Regelwerk in der Matrix (`gateway/klassen.py`)

| | vorher (`sedra-gateway-1.0`) | jetzt (`b6-datenregeln-0.1`) |
|---|---|---|
| Regelbuch | – | `REGELN` R-01…R-16: Kategorie, Merkmal, Rechtsbezug (Annahme), lokal/Cloud/Prüfung, Satz, „Was tun“; `regel()`, `regel_fuer()` |
| Personenbezug P01 | lokal oder Cloud nach Pseudonymisierung | **nur lokal** (R-01): pseudonymisierte Daten bleiben personenbezogen; `RECHTSGRUNDLAGE_CLOUD = False`, nur per Registereintrag |
| Merkmale | 13 | 14: **A01** Hochrisiko-Kontext nach EU AI Act (von Hand, R-13, SK3) |
| Gründe | Sätze | jeder Grund beginnt mit seiner Regelnummer; `Einstufung.regeln`, in der API `regeln`, je Merkmal `regel` |
| KI-Kennzeichnung | – | R-14: `Entwurf.kennzeichnung` „KI-Entwurf (modell) – menschlich geprüft: nein/ja“ |
| Injection in der Anfrage | Review | Review (R-09, Entscheidung P3) – unverändert; im Dokument Hard Block (R-08) |

Neue Regeln: neue Zeile in `REGELN`, ein Muster in `b6core/privacy.py` oder ein manuelles Kästchen, ein Test – und eine neue Versionsnummer.

## 2. Die Wissensbasis (`gateway/wissen.py`) – SEDRAs Blick auf seine Arbeitsumgebung

SQLite `local_config/gateway/wissen.sqlite`: Tabelle `wissen` (bei jedem Start aus dem Code gefüllt: Regeln, Merkmale mit Synonymen,
Zustände, Fehlercodes, Begriffe, **Leitfaden**, Ablauf) und `eigene` (Einträge des Nutzers, bleiben). Dazu der Live-Zustand aus `GateWay`.
`antwort(frage, vorgang)` ist deterministisch, ruft kein Modell, speichert keinen Vorgangstext und liefert Satz + Knöpfe (`ui_actions`, nur
`open` auf `gateway`-Objekte) + `quelle`. Antwortarten: Text prüfen („… in diesem Text: …“ → Funde mit Regelnummer, Stelle, Abhilfe) ·
nächster Schritt (je Zustand, mit Leitfaden-Schritt) · Fehler/warum am Vorgang · Leitfaden/Ablauf/Ablage · Stand · Datenart („darf eine IBAN
in die Cloud?“ → R-06) · Regelbuch-Suche (Stoppwörter, Synonyme, Mindesttreffer) · eigene Einträge.

**Der Leitfaden** (`LEITFADEN`, 7 Schritte): Vorbereiten → Vorgang anlegen → Eingeben und prüfen lassen → Empfehlung lesen und freigeben →
Auf die Auswertung warten → Entwurf prüfen (R2) → Ablegen; je Schritt „Du“, „Warten“, „Prüfen“, „Ablage“, „SEDRA hilft“.
`SCHRITT_VON_ZUSTAND` verbindet jeden Zustand mit seinem Schritt.

## 3. Das Gespräch (`uix_server.chat_reply`, `talk`)

Vor der Modellprüfung: ist die Frage zuständig (`GatewayWissen.zustaendig`: Gateway-Wörter, eine GW-ID, oder im Studio eine Frage nach
Schritt/Fehler/Stand), antwortet die Wissensbasis – **auch ohne Modell, und im Studio vor dem Modell** (Klaus 14:27). Audit
`UIX_CHAT_GATEWAY_WISSEN` {art, shell, actions} ohne Text. `POST /api/gateway/frage` für das Werkzeug. Das Gespräch merkt sich den zuletzt
geöffneten Vorgang (`object.open`) und schickt ihn als `vorgang` mit; es zeigt die Quelle unter der Antwort.

Ein geladenes Modell bekommt fünf lesende Werkzeuge (`chat_tools.py`): `gateway_status`, `gateway_vorgang` (nie der Anfragetext),
`gateway_regel`, `gateway_leitfaden`, `gateway_pruefe_text`; `open_object` kennt `gateway`. `CHAT_TOOL_NOTE` sagt dem Modell, erst
nachzuschlagen und nie den Anfragetext zu erfinden.

## 4. Die Shell

- **Werkzeug `gateway` 1.1:** Kästchen A01 neben R01 · Regelnummer vor jedem Grund, Spalte „Regel“ in der Merkmale-Tabelle, Fußzeile
  „Regelwerk v0.1 – Normbezüge sind Annahmen“ · je Station „Leitfaden Schritt n: Titel“ · Leitfaden-Block (aufklappbar, aktueller Schritt
  hervorgehoben) in Liste und Vorgang · **„Frag SEDRA“** (Feld, Antwort, Knöpfe, „Merken“) · Kennzeichnung über dem Entwurf.
- **Werkzeug `regelbuch`** (neu, CORE, Nachweis neben einem Vorgang): R-01…R-16 mit Suchfeld und Vorbehalt.
- `POST /api/gateway/wissen`: eigener Eintrag des Nutzers, kein Gate, Audit `GW_WISSEN_EINTRAG` {Längen}.
- Frist (P5): `vorgaben.yaml` → `entwuerfe_loeschen_nach_stunden: 24` (Standard; 1…336), ein festes Datum bleibt Obergrenze.
- Bezeichnung im GateWay: „Nutzer“ statt „Captain“ (Standard für die verantwortliche Person); SEDRA-weit bleibt der Captain.
- Selbstentwicklung (G-07): `gateway`, `gateway_wissen`, `content_guard`, `b6core` sind Kern (E3).

## 5. Was bewusst nicht kommt
Kein Cloudweg (auch nicht für P01, bis Rechtsgrundlage und AVV im Register stehen) · kein Versand · keine Rollen (die Person in der
Bindung ist nicht authentifiziert) · keine Änderung an `core/content_guard.py`, `core/guard.py`, `core/audit.py`, `models/router.py`,
`desk/decisions.py` · keine Rechtsprüfung (Normbezüge sind Annahmen; Datenschutzreview offen) · Löschen eigener Einträge nur von Hand in der SQLite.

## 6. Abnahme (Linux, Python 3.13, 15.10.)

| Was | Ergebnis |
|---|---|
| `test_gateway` (Matrix 9, Regelwerk 12, Vorgang 13, Hub 5, Gespräch 4, Modellwerkzeuge 2, Korpus-Adapter 1) | 46/46 |
| `test_gateway_wissen` (Leitfaden, Schritte je Zustand, Text prüfen, Regeln, Begriffe, Stand, Zuständigkeit, eigene Einträge, keine Vorgangstexte in der SQLite) | 14/14 |
| `test_content_guard` | 27/27 |
| `test_uix_flows` (Browser: Studio Flow mit Regelnummer, Leitfaden, Frag SEDRA ohne Modellaufruf, Kennzeichnung nein→ja, A01 → SK3/R-13) | 6/6 |
| `test_evolution_targets`, `test_uix_contract`, `test_desk_gateway` | grün |
| `uix_check` Cockpit / Minimal / Paperclip / GateWay Studio (20 Werkzeuge, `regelbuch` in der Nachweisspalte) | 30/30 · 30/30 · 30/30 · 30/30 |
| Volle Suite | 2.127 Tests, 1 Fehler = bekannter Umgebungsfehler `library_not_built`, 49 übersprungen, 396 s |
| Nicht gelaufen | Windows; Lauf mit echtem Modell (Station 04 und `gateway_*`-Werkzeuge); B6-Korpus (Datei fehlt) |

**Offen für den Nutzer:** G-02 (P02/V01-Erkennung, beide Linien) · Datenschutzreview der Normbezüge · Korpusdatei · Windows-Lauf · Abnahme.
