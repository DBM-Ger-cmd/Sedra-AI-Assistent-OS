# Inventur: Shell-Funktionen gegen One Sedra (U1, Stand 05.11.2026)

Unterchat U1 (Phase R1, Stufe A3 Vorbereitung). Nur gelesen, kein Code. Grundlage: `main` bei `d51083a`, Ordner
`runtime/src/guppi_runtime/uix/shells/*` (shell.yaml, README, Vorgaben), `uix/tools/*/tool.yaml`, `uix/ui/places.js`,
`uix/shells/harness/` (app.js, startmenue.js, startliste.js, start_gruppen.json, taskleiste.js, shell.js, builder.js).
Nicht im laufenden Sedra geprüft; das Audit-Log lag in dieser Umgebung nicht vor.

## 1. Kernbefund

Die Shells sind fast nur **Rahmen**. Die eigentlichen Funktionen sind **Werkzeuge** (`uix/tools/*`, 44 Stück, alle `trust: CORE`),
und One Sedra kann jedes davon schon als **App-Reiter** öffnen (`app.js`: `forObject` → `mountTool`, Nachweis rechts, Werkbank-Zeile,
Arbeitsstand; Start-Menü listet jeden Ort aus `places.js` und jedes Werkzeug ohne Ort). Es fehlt also selten ein Werkzeug,
sondern das, was die jeweilige Shell **um** die Werkzeuge herum baut: Zusammenstellung, Modusumschalter, Kopf, Übersicht, Chat-Anbindung.

Hinweis: Die Shell „Translator“ hat die Kennung **`fisch`** (Ordner `uix/shells/fisch`), nicht `translator` wie in der Roadmap (U2).
Gateway sind zwei Shells: `gateway-studio` (aus Vorgabe) und `gateway-kmu` (eigene Gestaltung, `trust: CAPTAIN`).

Legende: ✅ vorhanden · ◐ teilweise · ✗ fehlt · – bewusst nicht übernehmen

## 2. Tabelle

### Cockpit (`cockpit`)

| Funktion der Shell | One Sedra | Ziel-App / Ort |
|---|---|---|
| Instrumentenleiste (`/api/strip`, Gauges) | ◐ Taskleiste mit fester Zellenliste (Freigaben, Modell, Temp, VRAM, RAM, Modellserver, Scheduler, Zustand); Gauges `wissen`, `cloud`, `mode`, `tasks` fehlen | A1 „Zellen aus Manifesten“ (`taskleiste.js` `ZELLEN`) |
| Baum: Gesamtlage aller Orte mit Zustand, klappbar, „⚠ n wartet“, „… n weitere“ | ◐ Start-Menü-Gruppen und Kacheln; kein Gesamtbild mit Zustand je Zeile | App **Übersicht** (Baum als App) |
| Dock: zwei Werkzeuge nebeneinander, Teilen, Ziehen | ✗ nur ein Werkstück je Reiter, Nachweis rechts, Vorschau neben dem Gespräch | App-Rahmen (A2), später Layout „Teilen“ |
| Palette Strg+K: Orte, Baumzeilen, Zuletzt, „Im Wissen suchen“, „An SEDRA senden“ | ◐ Suche im Start-Menü (Alt+S). **Strg+K hat in One Sedra keinen Handler**, obwohl Platzhalter und Hinweis es nennen (`startmenue.js:69/167`, `layouteditor.js:180`) | X4 Befehlspalette; Hinweistext sofort korrigieren |
| Werkbank-Zeile mit Handlungen des Objekts | ✅ `app.js` (`hs-app-verben`) | – |
| Werkstatt, Modell hinzufügen, Teststrecke | ✅ Apps `workshop`, `slots`, `labor` | – |
| Entscheidungen an einer Stelle | ✅ Posteingang + Freigaben-Zelle | – |
| Arbeitsstand von anderer Shell übernehmen | ✅ `sedraStand` | – |
| Gespräch aufziehbar, Strg+B | ✅ Strg+B (Seitenleiste); Gespräch ist hier die Mitte | – |

### Translator (`fisch`)

| Funktion der Shell | One Sedra | Ziel-App / Ort |
|---|---|---|
| Werkzeuge Übersetzer, Nachrichten, Rekorder, Transkript | ✅ einzeln als Apps (Start → Arbeit) | – |
| Ein Ort mit Modusumschalter Übersetzen · News · Aufnahme · Transkript, Modus gemerkt | ✗ vier getrennte Reiter | App **Translator** (Sammel-App mit Modus-Reitern) |
| „Wolke“: ein Satz geht als `frage` in das Objekt des Modus | ◐ Übersetzer hat ein eigenes Textfeld; die Eingabe von One Sedra geht immer ins Gespräch | App Translator; optional „An Übersetzer“ aus dem Gespräch |
| Transkript: „Erkenntnisse mit SEDRA“, „An den Übersetzer“ | ◐ im Werkzeug vorhanden, in One Sedra nicht geprüft (Vermutung: geht, da derselbe Bus) | Test in U2 |
| Übersetzen aus dem Chat | ◐ nur `youtube_transkript` übersetzt; kein Chat-Werkzeug `uebersetzen` | U2 optional, sonst W-Stufe |
| Aufnahme-Knopf | ✅ Taskleiste (`schnell.js`) | – |
| Goldfisch, Glas, Blasen | – Gestaltung der alten Shell | höchstens Profil-Marke |

### Gateway (`gateway-studio`, `gateway-kmu`)

| Funktion der Shell | One Sedra | Ziel-App / Ort |
|---|---|---|
| Werkzeug GateWay mit Nachweis Schutz | ✅ App `gateway`, `schutz` rechts | – |
| Orte gateway, decisions, tasks, boundary, logbook, modules | ✅ im Start-Menü | – |
| Startseite = GateWay | ✅ Profil → Startseite | – |
| Ablauf-Kopf „Aufgabe → Schutz prüfen → Entwurf → Ergebnis prüfen → selbst entscheiden“, kompakt beim Rollen | ✗ | App **Gateway** (Kopf im App-Rahmen) |
| Orte/Instrumente am Rand einblenden | ◐ Seitenleiste per Strg+B; Rand-Einblenden fehlt | Layout im Builder (niedrig) |
| KMU-Gestaltung (Tokens `--kmu-…`, Bilder `kmu-hero/glow.png`) | ◐ Profil mit Marke, Farbe, Schrift, Logo; Bilder nicht | Profil-Vorlage **KMU** (U4) |

### Paperclip (`paperclip`)

| Funktion der Shell | One Sedra | Ziel-App / Ort |
|---|---|---|
| Posteingang mit Badge | ✅ | – |
| Issues, Ziele, Routinen, Organigramm, Agenten, Kosten, Slots, Labor, Planungstisch | ✅ je einzeln als App (`board`, `intent`, `routines`, `org`, `crew`, `meter`, `slots`, `labor`, `planung`) | – |
| **Dashboard**: Kennzahlen + Posteingang + Organigramm + Issues zugleich | ✗ | App **Team** (Dashboard) |
| Agentenfenster-Stapel rechts (≤ 4, gemerkt, ältestes wird Reiter) | ✗ `agentfenster` nur als einzelner App-Reiter (≤ 8 Apps gesamt) | App Team |
| Firmenwörter (Umbenennen der Orte) | ◐ `start_gruppen.json` `umbenennen` nur für Posteingang | Profil: Umbenennen je Profil (U4/A2) |
| Ereignisse `agent.changed`, `issue.changed`, `budget.warning` als Hinweis | ✗ in `shells/harness/*.js` nicht gefunden | App Team; Budgetwarnung als Hinweis im Kern |

### Wissensbasis (`wissensbasis`)

| Funktion der Shell | One Sedra | Ziel-App / Ort |
|---|---|---|
| Orte Suche, Quellen, Vorschläge, Eigenes Wissen, Messung, Bibliothek, Logbuch | ✅ Start → Wissen | – |
| Fundstelle als Nachweis neben dem Treffer | ✅ Nachweis rechts im App-Reiter | – |
| Leistenzelle Wissen („hybrid · 85 % · 2 Vorschläge“) | ✗ nicht in `ZELLEN` | A1 |
| **Gespräch antwortet aus dem Wissen** mit Fundstellen `[W…]`; Personenbezug sperrt Cloud | ✗ kein Chat-Werkzeug `wissen_suchen` | App **Wissensbasis** + W2 (`wissen_suchen`, `wissen_beantragen`) |
| Quellen beantragen (Betriebslog, gute Antworten) | ✅ `info_wissen_beantragen`, Freigabe im Posteingang | – |
| Startseite Wissen › Suche | ✅ über Profil-Startseite | – |

### Minimal (`minimal`)

| Funktion der Shell | One Sedra | Ziel-App / Ort |
|---|---|---|
| Menüleiste, freie Fenster | – andere Bedienform | Profil **Minimal/Stick** (schlank), keine App |
| Ablage mit eigenen Feldern (Ort, Fenster vorn, „Auftrag an SEDRA“), Rechtsklick | ◐ „Zuletzt“ im Start-Menü, Builder blendet ein/aus; eigene Einträge und Auftrags-Knöpfe fehlen | Builder: eigene Start-Einträge (U4/A2) |
| Entscheidungskarte rechts oben | ✅ Freigaben-Zelle | – |
| Instrumente | ✅ Taskleiste | – |
| Oberflächen wechseln | ✅ Start-Menü unten | – |

## 3. Was quer fehlt (gilt für mehrere Apps)

1. **App-Rahmen** (A2): Kopf, Modus-Reiter, Zustand je App. Translator, Gateway und Team brauchen ihn; zuerst klein im Translator bauen, dann verallgemeinern.
2. **Zellen aus Manifesten** (A1): Wissen, Cloud, Modus, Aufgaben fehlen in der festen Liste.
3. **Strg+K**: Hinweis versprochen, aber kein Handler in One Sedra.
4. **Mehrere Werkzeuge auf einer Fläche** (Dashboard, Stapel, Dock): heute ein Werkstück je Reiter.

## 4. Reihenfolge-Vorschlag

| # | App | Warum hier | Umfang (Schätzung) | Dateien |
|---|---|---|---|---|
| 1 | **Translator** (U2) | Kleinste Lücke, alle vier Werkzeuge da, keine neuen Wege der Harness; Muster für den App-Rahmen | klein | `uix/shells/harness/` (neu: Sammel-App), Test |
| 2 | **Wissensbasis** (U3) | Größter Nutzen: der Chat nutzt das Wissen (W2); braucht neue Werkzeuge mit Einträgen in `freigabeklasse.py`/`api.py` | mittel | `harness/werkzeuge.py`, `desk/freigabeklasse.py`, `harness/api.py`, Tests |
| 3 | **Gateway** | Werkzeug da, nur Ablauf-Kopf; KMU-Gestaltung kommt über Profil-Vorlage (U4) | klein | App-Rahmen |
| 4 | **Team** (Paperclip) | Dashboard und Agentenstapel brauchen mehrere Werkzeuge auf einer Fläche – größter Schritt | groß | `app.js`, neue Fläche |
| 5 | **Übersicht** (Cockpit) | Baum als App + Strg+K-Palette; Dock-Teilen zuletzt | mittel | App, X4 |
| 6 | **Minimal** → Profil | Kein App-Bau; mit U4 (Profile) und U8 (Stick) | klein | Profil-Vorlage |

Alternative: Wissensbasis zuerst, wenn der Chat mit Wissen wichtiger ist als ein schnelles Muster. Dann den App-Rahmen erst bei Translator/Gateway bauen.

Sofort klein und gefahrlos (eigener Mini-Auftrag): Strg+K-Hinweis in `startmenue.js`/`layouteditor.js` korrigieren oder Strg+K auf das Start-Menü legen.

## 5. Offene Fragen an den Captain

1. Welche App zuerst: Translator (Vorschlag) oder Wissensbasis?
2. Paperclip-Ersatz als App „Team“ benennen?
3. Strg+K: Hinweis streichen oder auf das Start-Menü legen?

## 6. Stand 11.11.2026

- **Translator:** als App gebaut und auf `main` (`SPEC_APP_TRANSLATOR_v1.md` §7), Gleichstandsliste TR-51 beim Captain.
- **Wissensbasis:** die zwei Lücken der Tabelle oben sind geschlossen (Leistenzelle `gauge-wissen`; Chat-Werkzeuge `wissen_suchen`, `wissen_beantragen` mit Fundstellen `[W…]`). Das Werkzeug `wissen` ist schon die Sammel-App mit den Ansichten Suche, Quellen, Vorschläge, Eigenes, Messung und der Fundstelle als Nachweis. Im Start-Menü steht jetzt nur noch „Wissen“; die Ansichts-Orte bleiben für Suche und Chat. Test `test_uix_wissensbasis_app`. Die alte Shell `wissensbasis` bleibt unverändert, bis der Captain den Gleichstand abnimmt.
- **Weiter:** Gateway, dann Team (Paperclip), Übersicht (Cockpit).
