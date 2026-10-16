# Spec: Der GateWay-Vorgang in SEDRA – Studio Flow, MVP 1 (15.10.2026, GEBAUT in Build 19 – siehe BUILD_19_GATEWAY_2026-10-15.md)

**Captain, 09:49:** *„Mach mit Gateway weiter – hier weitere Informationen und Anforderungen.“* Grundlage: `B6_UI_Studio_Flow_v1.1.html`
(die Klickvorschau), `B6_KI_Gateway_V4` (Entscheidungs- und Aufgabenregister, Übergabe v1.1, offene Fragen) und die
0.3.0-Lieferung (`sedra_gateway`), abgenommen am 15.10. Diese Spec sagt, was davon **in SEDRA** wird, was bewusst nicht, und wo
die fachlichen Entscheidungen beim Captain bleiben.

## 1. Was die Akte entscheidet – und was SEDRA daraus macht

| Entscheidung (Akte) | In SEDRA |
|---|---|
| K-01: Kundenanfrage + freigegebene Fakten → Privacy/Policy → zulässige KI → Entwurf → **menschliche Prüfung, kein Versand** | Ein **Vorgang** ist genau dieser Weg, in vier Stationen (Studio Flow 01–04). Es gibt kein Verb „senden“. |
| K-02: lokal real, Cloud **nur simuliert**, Anhänge **MVP 2** (nur .md/.txt) | Lokal = `ModelRouter.chat` durch den Inhaltsschutz (Build 16). Cloud = Simulation, als solche beschriftet. Dokument: eine .md/.txt-Datei aus dem Projekt; alles andere wird mit Satz abgewiesen. |
| K-03: Nutzer darf **restriktiver** wählen, nie offener; **Hard Blocks nicht übersteuerbar** | Der Wunsch (lokal/Cloud) ist ein Wunsch; die Policy nennt die erlaubten Wege; die Freigabe bietet nur erlaubte an. `BLOCKED` hat keinen Knopf „trotzdem“. |
| K-04: **SK0–SK3**, 13 Merkmale, deterministische Matrix, Fail-Safe, `NOT_DETECTED` ist keine Freigabe, Route / Policy-Status / Review-Status **getrennt** | `gateway/klassen.py`: Merkmale aus den B6-Regeln, Schutzklasse aus den Merkmalen, Matrix → `{route_erlaubt[], policy_status, review}`; unvollständiger Scan = `UNCLASSIFIED` → Review. Die Oberfläche sagt immer: „Kein Treffer heißt nicht unbedenklich.“ |
| K04-PSEUDO-01: typisierte Platzhalter, Mapping **nur lokal, vorgangsbezogen**, **drei Rechecks**, Löschung bei Abschluss/Abbruch/Fehler | `b6core.pseudo` (schon im Kern): Recheck 1 nach der Pseudonymisierung, 2 nach der KI vor der Rückübersetzung, 3 nach der Rückübersetzung. Das Mapping lebt nur im Prozess (`PseudoVault`), nie auf der Platte; `abschliessen`/`verwerfen`/Fehler löschen es. |
| Mapping-Enddatum **23.10.2026**, F-04: rehydrierte Entwürfe getrennt, **spätestens 23.10. löschen** | `local_config/gateway/vorgaben.yaml` → `entwuerfe_loeschen_am: 2026-10-23T23:59:59+02:00` (synthetischer MVP-Test, nicht Produktpolicy). Entwürfe liegen **getrennt** unter `local_config/gateway/entwuerfe/`; beim Start und bei jedem Blick werden abgelaufene gelöscht (Audit `GW_ENTWURF_GELOESCHT`). Uhrzeit: Ende des Tages – der Captain kann sie setzen. |
| TC-011 / Rollen: SK3 und G01 → **Review bleibt** (Empfehlung, nicht beschlossen); Rollen sind Demo-Annahmen | SEDRA setzt die Empfehlung um: G01/P02/P03/P04/V01 → SK3 → `HUMAN_REVIEW_REQUIRED` auch lokal. Es gibt **keine Rollen** in SEDRA; der Captain ist der Review. Das steht im Werkzeug. Fachlich anders zu entscheiden bleibt KLA-O1/O2. |
| K04-CLOUD-01: sauberes SK0 → `CLOUD_ALLOWED_SIMULATED / AUTO_APPROVED`, kein pauschales R1 | genau so in der Matrix |
| K04-LOCALPII-01: normale Absender-PII lokal **nicht automatisch** Review | P01 allein → SK1 → `LOCAL_ONLY / AUTO_APPROVED`; Cloud nur nach Pseudonymisierung (simuliert) |
| MCP/Agent: Option A, **nur dokumentieren** | nichts gebaut; Satz im Werkzeug unter „Was dieses MVP nicht tut“ |
| Realer Cloud-Datenfluss (OpenRouter): nicht freigegeben | `CLOUDS = ('simuliert',)` bleibt; ein echter Adapter ist Build S6 hinter der Netzgrenze, mit eigenem Beschluss |

## 2. Die 13 Merkmale – aus den B6-Regeln abgeleitet (fachliche Bestätigung: Captain)

| Merkmal | Name | B6-Regel | Klasse |
|---|---|---|---|
| P01 | Personenbezug | PERSON, EMAIL, PHONE, IDENTIFIER (Kundennummer) | SK1 |
| P02 | Besondere Kategorien (Gesundheit, Religion, …) | CTX_P02 | SK3 |
| P03 | Strafsachen | CTX_P03 | SK3 |
| P04 | Amtliche Kennungen (Steuer-ID, Ausweis) | CTX_P04, CTX_P04_UNVERIFIED | SK3 |
| F01 | Bankverbindung | IBAN | SK2 |
| F02 | Kartendaten | PAN | SK2 |
| F03 | Kartendaten mit Prüfwert | PAN_CVV | **Hard Block** |
| S01 | Zugangsdaten, Schlüssel | SECRET_* | **Hard Block** |
| S02 | Anweisungen an die KI, versteckte Zeichen | INJECTION_*, INVISIBLE_* | **Hard Block** (Dokument) / Review (Anfrage) |
| G01 | Kalkulation, Geschäftsgeheimnis | CTX_G01, CTX_G01_SUSPECT | SK3 (Review – TC-011) |
| G02 | Vertraulichkeitsvereinbarung | CTX_G02 | SK2 |
| R01 | Rechtsstreit / laufendes Verfahren | **nicht automatisch erkennbar** – der Captain setzt es von Hand | SK2 |
| V01 | Minderjährige | CTX_V01 | SK3 |

**Schutzklasse** = die höchste der getroffenen Merkmale; kein Merkmal = SK0. Wer die Benennung von R01 oder die Zuordnung
F01/F02 anders sieht, ändert eine Tabelle, keinen Code (`klassen.py`, mit Test).

## 3. Die Matrix (deterministisch, Fail-Safe)

| Klasse / Fund | erlaubte Wege | Policy-Status | Review (R1) |
|---|---|---|---|
| Hard Block (S01, F03, S02 im Dokument) | keiner | `BLOCKED` | – (nicht übersteuerbar) |
| UNCLASSIFIED (Scan unvollständig, Datei nicht lesbar) | keiner bis Review | `HUMAN_REVIEW_REQUIRED` | PENDING |
| SK3 | LOCAL_ONLY | `HUMAN_REVIEW_REQUIRED` | PENDING → der Captain gibt frei (das Gate) |
| SK2 | LOCAL_ONLY | `AUTO_APPROVED` | NOT_REQUIRED |
| SK1 | LOCAL_ONLY, CLOUD_AFTER_PSEUDONYMIZATION (simuliert) | `AUTO_APPROVED` | NOT_REQUIRED |
| SK0 | LOCAL_ONLY, CLOUD_ALLOWED (simuliert) | `AUTO_APPROVED` | NOT_REQUIRED |

Die **Freigabe** (Station 03) ist in SEDRA ein **Gate** `request:gateway_release` mit Bindung über: Hash der Anfrage, Hash des
Dokuments, Policy-Version, Schutzklasse, Merkmale, gewählter Weg, Hash des Übergabeprompts. Ändert sich eines, passt die Freigabe
nicht mehr. Bei `AUTO_APPROVED` ist die Freigabe trotzdem ein Klick des Captains (Regel: kein Modellaufruf ohne ihn) – aber ohne
Review-Satz; bei `HUMAN_REVIEW_REQUIRED` steht der Review-Satz im Gate. R2 (Ergebnisprüfung) ist Station 04: der Entwurf wird
gezeigt, der Captain markiert „geprüft“ oder verwirft; nichts geht hinaus.

## 4. Die vier Stationen in SEDRA (Werkzeug `gateway`, Objekttyp `gateway`)

| Station | Was passiert | Route |
|---|---|---|
| 01 Modell | Wunsch: lokal (das geladene Modell) oder Cloud (simuliert). Nur ein Wunsch. | – |
| 02 Eingabe | Anfrage (Text) + optional eine .md/.txt aus dem Projekt. **Datenschutz prüfen** → links Original mit Markierungen, rechts der Übergabeprompt mit Platzhaltern, Legende, „Die Zuordnung bleibt lokal“. | `POST /api/gateway/pruefen` |
| 03 Empfehlung + Freigabe | Schutzklasse, Merkmale, erlaubte Wege, Policy-Status, Review; „Mehr Infos“ mit der Zuordnungstabelle. Knöpfe nur für erlaubte Wege; `BLOCKED` = kein Knopf, ein Satz. Freigabe = Gate. | `POST /api/gateway/freigabe` → Entscheidung → `apply` |
| 04 Ergebnis | Entwurf (lokal: echtes Modell durch den Inhaltsschutz; Cloud: Simulation mit Platzhaltern, dann Rückübersetzung mit Rechecks), Status, „Geprüft“ / „Verwerfen“. Entwurf liegt getrennt, mit Löschdatum. | `POST /api/gateway/pruefung` (R2), `verwerfen` |

Das Werkzeug ist **neu geschrieben** nach dem Studio Flow (Token, Zonen, Farben) im Vertrag (vanilla JS, `.t-gateway`, nur `ctx.api`);
die 0.3.0-Werkzeuge waren der Bestandsablauf (Dateien → Einheiten → Stichprobe) und bleiben als Option für MVP 2 dokumentiert,
nicht im Paket. `schutz` (0.3.0) zeigt schon den Inhaltsschutz von Build 16 und kommt als CORE ins Paket.

## 5. Was bewusst nicht kommt (MVP 1)

Echter Cloud-Versand · Anhänge außer .md/.txt (PDF/DOCX = MVP 2) · Rollen/Berechtigungen · MCP/Agenten · der Bestandsablauf der
0.3.0 · eine Produkt-Aufbewahrungspolicy. Jedes davon steht als Satz im Werkzeug, wo man es vermissen würde.

## 6. Abnahme

Ein Test je Zeile der Matrix (`test_gateway_klassen`); Vorgang: prüfen → Gate → lokal mit Fake-Modell durch den Guard → Rechecks →
Entwurf → R2 → Löschung (`test_gateway_vorgang`); Gate-Bindung stirbt bei jeder Änderung; Entwürfe nach dem Enddatum weg;
Klick-Test im Cockpit (Studio Flow: prüfen, freigeben, Antwort, geprüft); `uix_check --tool gateway`.
