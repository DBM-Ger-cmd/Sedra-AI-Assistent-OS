# Build 19: Das KI GateWay in SEDRA – Studio Flow, Schutzklassen, Studio-Shell (15.10.2026)

**Captain, 09:49:** *„Mach mit Gateway weiter – hier weitere Informationen und Anforderungen“* (Studio Flow v1.1, V4-Akte).
**10:13:** *„Die linke Seitenleiste sollte sich ausfahren, wenn man nach links fährt, aber nicht prominent sichtbar sein; die obere
Leiste nur beim gezielten Anfahren – so dass wirklich das KI GateWay in dieser Shell zum Tragen kommt.“*
Spec: `SPEC_GATEWAY_VORGANG_v1.md`. Was gebaut ist:

## 1. Der Kern (`guppi_runtime/gateway/`)

| Datei | Was |
|---|---|
| `klassen.py` | die 13 Merkmale (P01–P04, F01–F03, S01–S02, G01–G02, R01, V01) aus den B6-Regeln, SK0–SK3, die **deterministische Matrix**: Hard Block (S01, F03, S02 im Dokument) → `BLOCKED` ohne Weg; UNCLASSIFIED → Review; SK3 → `LOCAL_ONLY` + `HUMAN_REVIEW_REQUIRED` (TC-011-Empfehlung); SK2 → `LOCAL_ONLY`; SK1 → lokal oder Cloud nach Pseudonymisierung; SK0 → Cloud zulässig – Cloud immer simuliert. Weg / Policy-Status / Review getrennt (K-04). Der Wunsch darf nur restriktiver sein (K-03). R01 setzt der Captain von Hand. |
| `vorgang.py` | der Vorgang: `neu` → `pruefen` (Scan, Einstufung, Übergabeprompt mit typisierten Platzhaltern für Anfrage **und** Dokument zusammen, Recheck 1) → `bindung` (Hash über Anfrage, Dokument, Policy, Klasse, Merkmale, Weg, Übergabeprompt) → `ausfuehren` (lokal über `complete_local` = `ModelRouter.chat` durch den Inhaltsschutz; Cloud simuliert; Recheck 2 vor, Recheck 3 nach der Rückübersetzung) → `pruefung` (R2: geprüft / verworfen). Mapping nur im Prozess, gelöscht nach Rückübersetzung, bei Abbruch und Fehler. Gesperrte Vorgänge speichern keinen Text. |
| Ablage | `local_config/gateway/vorgaenge/<id>.json` (ohne Entwurf), `entwuerfe/<id>.json` getrennt mit `loeschen_am` (F-04, Standard `2026-10-23T23:59:59+02:00` aus `vorgaben.yaml`); `aufraeumen()` beim Start und bei jedem Blick, Audit `GW_ENTWURF_GELOESCHT`. |
| `probe.py` | „Selbst ausprobieren“ für das Werkzeug `schutz`, auf den Guard von Build 16 portiert: ruft kein Modell, speichert nichts. |

## 2. Der Hub

`GET /api/gateway/vorgaenge` (Vorgänge, Vorgaben, die .md/.txt des Projekts, Modell, Merkmale, „nicht im MVP“) · `POST …/vorgang`,
`neu`, `pruefen` (liest die Datei aus dem Projekt, nur unterhalb des Arbeitsordners, nur .md/.txt), `freigabe` (ein Gate
`request:gateway` mit Bindung, Titel „Vorgang … freigeben: nur lokal · SK1 Intern · P01 · Automatisch erlaubt“), `apply` (nur
mit Einmal-Token und unveränderter Bindung), `pruefung`, `verwerfen` · `POST /api/guard/probe`. `gateway` ist ein Vertragstyp
(`OBJECT_TYPES`), ein Ort in der Ortskunde, ein Starttyp für Vorgaben.

## 3. Die Werkzeuge

- **`gateway`** (neu, CORE): die vier Stationen des Studio Flow – 01 Wunsch (lokal mit dem geladenen Modell / Cloud-Simulation),
  02 Eingabeprompt + Dokument + R01 → „Datenschutz prüfen“ → links Original mit Markierungen, rechts Übergabeprompt mit
  Platzhaltern (Token je Typ, Legende, „Die Zuordnung bleibt lokal“), 03 Empfehlung (Klasse, Merkmale, Wege, Review; „Mehr Infos“
  mit Zuordnung) → Freigabe-Knöpfe nur für erlaubte Wege, `BLOCKED` ohne Knopf, der Klick ist `ctx.shell.decide` – dieselbe Tür wie
  in den Entscheidungen, 04 Entwurf mit Weg, Modell, Rechecks, Löschdatum → „Geprüft“ / „Verwerfen“. Kein Versand – steht dabei.
- **`schutz`** (aus der Lieferung, jetzt CORE): liest `/api/guard/status` und `/api/guard/probe`. Geändert: Farben nur Token,
  keine Regel-Schalter (Schärfe = Modus), Vorführung ohne Reiter.

## 4. Die Shell „KI GateWay Studio“ (`shells/gateway-studio`, aus Vorgabe)

Der Rahmen kann seit diesem Build `einblenden: rand` für `orte` und `leiste`: die Zone steht nicht im Raster, liegt verborgen am
Rand und fährt heraus, wenn der Zeiger den Rand anfährt (10 px links, 8 px oben) oder die Tastatur hineinkommt; sie fährt zurück,
wenn der Zeiger sie verlässt. Das Studio: `raster: [leiste, "orte|werkstueck", gespraech]`, beides am Rand, Orte nur GateWay ·
Entscheidungen · Aufgaben · Modus · Logbuch · Module, Nachweis 380 px, Gespräch 96 px, Start im GateWay. Kein Shell-Code.
Abnahme: 29/29.

## 5. Was bewusst nicht kommt (MVP 1)

Echter Cloud-Versand (KLA-O6 offen) · Anhänge außer .md/.txt · Rollen/Berechtigungen (der Captain ist der Review) · MCP/Agenten
(Option A: dokumentiert) · der Bestandsablauf der 0.3.0 (MVP 2) · eine Produkt-Aufbewahrungspolicy. Alles steht im Werkzeug
unter „Was dieses MVP nicht tut“.

## 6. Abnahme

| Was | Ergebnis |
|---|---|
| `tests/test_gateway.py`: Matrix (9), Vorgang (8: Studio-Beispiel lokal, Hard Block ohne Text, Bindung stirbt, Cloud simuliert, Rechecks 2/3, F-04, nur .md/.txt, Anweisung in der Anfrage), Hub (4: ganzer Weg mit Gate und Fake-Modell durch den Guard, Ablehnen, SK3/BLOCKED, Probe) | 21/21 |
| `test_uix_flows`: Studio Flow mit Klicks – prüfen, Platzhalter, nur lokal angeboten, freigeben = Gate, Entwurf zurückübersetzt, Löschdatum, geprüft; genau ein Modellaufruf durch den Inhaltsschutz | ok |
| `uix_check`: Cockpit/Minimal/Paperclip 29/29 (zwei Werkzeuge mehr), Start 6/6, GUPPI XP 3/3, **Studio 29/29**, drei Vorgaben 29/29 · 29/29 · 28/28 | ok |
| Volle Suite | 2072 Tests, grün bis auf den bekannten Umgebungsfehler (`library_not_built`) |

**Offen für den Captain (aus der Akte):** TC-011/Rollen (KLA-O1/O2) – SEDRA hält Review; die Benennung F01/F02 und R01 in
`klassen.py` (eine Tabelle); die Uhrzeit des 23.10.; ob die Cloud real werden soll (dann S6 hinter der Netzgrenze).
