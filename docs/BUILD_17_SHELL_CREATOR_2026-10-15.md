# Build 17: Der Shell-Creator – Schema-Zwang, Rahmen aus Vorgabe, Satz an GUPPI (15.10.2026)

**Captain, 08:29:** *„Drei Empfehlungen, in Reihenfolge: sollten wir so umsetzen.“* – die drei Empfehlungen aus
`RECHERCHE_SHELL_CREATOR_2026-10-15.md`, gebaut in dieser Reihenfolge. Seit diesem Build entsteht eine eigene Oberfläche
**ohne Code**: aus einem Satz oder einer Vorlage wird eine Vorgabe, der Rahmen baut daraus den Bildschirm, die Abnahme prüft
sie ganz. Code schreibt dabei niemand – auch das Modell nicht.

## 1. Schritt 1 – strukturierte Antworten vom lokalen Modell (`models/structured.py`)

`ModelRouter.chat(…, schema=…)` liefert eine Antwort, die dem JSON-Schema entspricht, oder einen Fehler, der sagt, warum nicht:

| | Was | Warum so |
|---|---|---|
| Server | `response_format: json_schema` an den OpenAI-kompatiblen Adapter (LM Studio, llama-server, Ollama `/v1`) | der Server erzwingt die Form beim Erzeugen – kein Fließtext-Parsen |
| Prompt | das Schema steht zusätzlich als Systemzeile im Aufruf | llama.cpp: die Grammatik ändert die Ausgabe, nicht das Wissen des Modells |
| Prüfung | `structured.validate` – Sätze wie „$.raster[0]: passt nicht zum Muster“ | was nicht passt, geht als Satz zurück an das Modell (Instructor-Muster), höchstens **drei Runden**, dann `structured_output_failed` |
| Teilmenge | nur, was llama.cpp sicher in eine Grammatik übersetzt: type, properties, required, additionalProperties=false, enum, const, items, min/max, pattern `^…$`, minimum/maximum (integer). Kein `$ref`, `oneOf`, `patternProperties`, `format` | `check_schema` weist alles andere **vor dem ersten Aufruf** ab – niemand vertraut auf eine Erzwingung, die der Server still überspringt |
| Kette | jede Runde ist ein voller Aufruf: durch den Inhaltsschutz (Build 16), mit Audit (`MODEL_SCHEMA_RETRY` je Fehlrunde), gezählt | kein zweiter Weg zum Modell |

Kein `jsonschema`-Paket: die Runtime hängt nur von PyYAML ab, und die Teilmenge ist klein genug, um sie zu kennen (150 Zeilen).
Das Ergebnis trägt `parsed` und `rounds`; ohne `schema=` ändert sich nichts.

## 2. Schritt 2 – der Rahmen: eine Shell aus einer Vorgabe (`ui/frame.js`, `ui/schema/vorgabe.schema.json`)

Eine Shell aus Vorgabe besteht aus `shell.yaml` (Name, Vertrauen, `vorgabe: shell.vorgabe.yaml`) und `shell.vorgabe.yaml`:

```yaml
id: bruecke
name: "Brücke"
raster: [leiste, "orte|werkstueck", gespraech]     # Zeilen; | macht Spalten
orte: {breite: 220, liste: [tasks, intents, decisions, models, logbook, modules]}
werkstueck: {nachweise: seitenleiste}             # seitenleiste · umschalter · spalten · keine
gespraech: {art: zone, hoehe: 112}                # zone · schublade (Knopf, keine Zeile)
entscheidungen: karte                             # karte (erscheint, sobald eine wartet) · werkzeug
suche: strg-k                                     # strg-k · feld (braucht leiste) · keine
start: {type: task, id: alle, title: Aufgaben}
```

| Wer | Was er tut |
|---|---|
| **Vermittler** (`desk/gateway.py`) | liest die Vorgabe, prüft sie mit **derselben** flachen Teilmenge wie das Modell (`vorgabe.schema.json`, `desk/vorgabe.check`), leitet `provides` ab (dock, talk, +strip/tree/palette/inbox), setzt die Routen selbst (`FRAME_API`) – `entry`, `api`, `provides` in der Datei werden abgewiesen: Code, Routen und Slots gehören dem Rahmen. Das Manifest liefert `js: ['/uix/ui/frame.js']`. |
| **Loader** (`ui/loader.js`) | eine Shell mit `frame` registriert der Rahmen aus dem Manifest – eine Zeile |
| **Rahmen** (`ui/frame.js`, 300 Zeilen) | Raster → Zeilen aus Spalten (CSS-Grid); sechs Zonen; Instrumente aus `/api/strip`; Orte aus der Ortskunde; Werkstück mit Verben (`data-verbs`) und Nachweisen in vier Darstellungen; Gespräch als Zone oder Schublade; Entscheidungen als Karte (in der Zone oder schwebend) oder Werkzeug; Palette oder Suchfeld; Verlauf und letztes Objekt im Browser gemerkt. Die Mechanik, die in vier Shells viermal stand – mounten, `ready`, Verben, `unmount`, Marken, `talk.context`, auffrischen – steht hier **einmal**. Kein eigenes fetch, kein eval, ein Global. |
| **Gerüst** (`module_scaffold`) | `vorgabe: true` nimmt die Vorlage `shells/_vorgabe`, ein Objekt ist die Vorgabe selbst; `id`/`name` werden gesetzt; eine Vorgabe, die nicht lädt, hinterlässt keinen Ordner |
| **Abnahme** (`uix_check --vorgabe <datei>` oder `--shell <id>`) | das Profil kommt **aus der Vorgabe** (`frame_profile`): Zonen, Umschalter, Schublade, Suchfeld, Palette, Verlauf. Eine Shell aus Vorgabe wird ganz geprüft – nichts „nicht geprüft“ außer dem, was sie bewusst nicht hat (keine Leiste → keine Instrumente). |

**Beweis, dass der Vertrag trägt:** drei Vorgaben – *Brücke* (die Form des Cockpits), *Schlicht* (Minimal: Umschalter, Schublade,
Suchfeld) und *Seiten* (Paperclip: Ortsauswahl, Spalten, Entscheidungen rechts) – laufen **27/27 · 27/27 · 26/26**, ohne eine
Zeile Shell-Code. Was die Abnahme dabei am Rahmen fand und was behoben ist: die Palette lag sichtbar über der Seite
(`display:flex` schlägt `hidden` – derselbe Fund wie bei Shell D; jetzt `[hidden]{display:none !important}`); das Gespräch
fokussierte beim Start sein Feld und der Browser scrollte den Rahmen zur unsichtbaren Schublade – alles rutschte 440 px nach
links (geschlossene Schublade ist jetzt `visibility:hidden`, der Rahmen setzt den Scroll zurück); die Umschalter-Knöpfe trugen
`data-tool` und wurden für Container gehalten (`data-seg`); bei „spalten“ standen alle Nachweise in einer Spalte.

## 3. Schritt 3 – der Creator (`desk/vorgabe.py`, `ui/vorgabe.js`)

Im Einstieg und im Werkzeug „Module“ steht jetzt der Block **„Eigene Oberfläche aus einer Vorgabe“**:

1. **Ein Satz an GUPPI** – „links nur Aufgaben und Logbuch, rechts die Entscheidungen, Nachweise zum Umschalten, Gespräch als
   Schublade, Suchfeld“ → `POST /api/uix/vorgabe` → `ModelRouter.chat(schema=vorgabe.schema.json)` (Schritt 1; das Modell
   bekommt den Systemtext mit Zonen, Orten, Regeln) → `desk/vorgabe.check` (dieselbe Prüfung wie beim Laden) → Satz und Skizze.
   **Nichts ist angelegt.** Audit `UIX_VORGABE_PROPOSED` (Zeichenzahl, Runden – kein Text).
2. **Oder eine der drei Vorlagen** – *Reiter · Fenster · Seiten* (`GET /api/uix/vorgaben`), ohne Modell.
3. **„So anlegen“** → `module_scaffold` mit der Vorgabe (Audit, kein Gate – eigene Form); der Einstieg nimmt sie gleich und lädt neu.

Was keine Vorgabe kann, sagt der Creator ehrlich: eine neue *Funktion* (ein Werkzeug, das es nicht gibt) ist Code, und Code ist
fremd – dafür bleibt das Gerüst aus der Vorlage mit dem Gate. Der Systemtext weist das Modell an, so etwas nicht zu erfinden.
Ist kein Modell geladen, sagt es der Block und bietet die Vorlagen an.

## 4. Was es für GUPPI heißt

Das ist die erste Stelle, an der GUPPI ein Modul **beschreibt statt programmiert**: die Vorgabe ist Daten, der Rahmen ist
geprüfter Vertragscode. Der Weg über das Gespräch („bau mir eine Oberfläche mit …“ → Verb `oberflaeche_anlegen`) ist noch nicht
angebunden – der Block im Einstieg und im Werkzeug ist derselbe Aufruf, nur mit Knopf statt Satz im Gespräch.

## 5. Abnahme

| Was | Ergebnis |
|---|---|
| `tests/test_model_structured.py` (Schritt 1: Teilmenge, Sätze, Runden, Guard, kein Modell bei schlechtem Schema) | 10/10 |
| `tests/test_uix_frame.py` (Schritt 2/3: Schema in der Teilmenge, Vermittler mit sieben Ablehnungen, Manifest, Gerüst, Rahmen in node, Skizze) | 16/16 |
| `tests/test_uix_shell_start.py` – Klicks: Satz an GUPPI (Fake-Modell) → Skizze, nichts angelegt; Vorlage → „So anlegen“ → Rahmen läuft | 5/5 |
| `uix_check --vorgabe` Brücke · Schlicht · Seiten | 27/27 · 27/27 · 26/26 |
| vier Shells | 27/27 · 27/27 · 27/27 · Start 6/6 + 7 n. g. |
| Volle Suite | 2046 Tests, grün bis auf den bekannten Umgebungsfehler (`library_not_built`) |

**Offen, bewusst:** ob der Rahmen die handgebauten Shells ersetzt (Spec §5: daneben); die Anbindung über das Gespräch; benannte
Ansichten und `settings:`-Schema im Manifest (Photocraft-Muster, Spec §6).
