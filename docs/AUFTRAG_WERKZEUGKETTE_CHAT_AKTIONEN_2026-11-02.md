# Auftrag: Die Kette vom Wunsch zum fertigen Ergebnis – wo SEDRA im Chat stolpert (02.11.2026)

Anlass: Sitzung `S-1278AB07` (Harness-Shell, Gemma 4 12B QAT, 11:55–12:08). Wunsch des Captains: „starte Voice Rekorder“, danach als
erstes Projekt „Befehle aus dem Chat heraus ausführen“. Das Modell hat sauber gearbeitet; gescheitert ist es an den Werkzeugen.

## 1. Wo die Kette gerissen ist

| Schritt | Was der Captain wollte | Was passiert ist | Ursache im Code |
|---|---|---|---|
| 1 Wunsch | „starte voice rekorder“ | „Ich habe kein Werkzeug“ | Der Harness reicht dem Modell nur die lesenden Chat-Werkzeuge (`LESEN` in `harness/api.py`), bewusst „kein Vorschlag, kein Öffnen“. `open_place`, `open_object`, `propose_action` aus `chat_tools.py` fehlen. |
| 2 Auftrag | „als Auftrag anlegen“ | Modell will „Mission“ anlegen, kann es nicht | `propose_task` / `propose_intent` stehen nur in `PLANUNG_TOOLS`, nicht im Harness. |
| 3 Projekt | Projekt „Befehle aus dem Chat …“ | `list_projects` = 0, Modell schlägt `mkdir` vor | Den Weg gibt es nur als UI: „Ordner öffnen …“ (Antrag mit Gate, `projekte.yaml`). Das Modell weiß ihn nicht oder nennt ihn nicht, obwohl er im Arbeitsplatz-Wissen steht. |
| 4 Ordner | `mkdir …` | „Programm nicht gefunden: mkdir“ | `befehl` startet ohne Shell. `mkdir`, `dir`, `start` sind Eingebautes der Eingabeaufforderung, keine Programme. Die Werkzeugbeschreibung sagt das dem Modell nicht. |
| 5 Projektordner | „nutze `A1 Sedra Baut`“ | Modell sagt „verstanden“, arbeitet aber weiter in der Projektwurzel | Der Ordner war nicht als Projekt beantragt; die Aussage des Modells hatte keine Wirkung. |
| 6 Datei | Missionsdatei in `workspace/` | „ausserhalb_schreibbereich“ | Schreibbereich nur `runtime/**`, `docs/**`, `redesign/**`. Der Fehler war ehrlich und richtig. |
| 7 Nach 12:08 | weiterarbeiten | Modell lud nicht mehr | Router legte es nach 15 min Leerlauf schlafen (`sleeping`), Sedra kannte den Zustand nicht. **Behoben** am 02.11. (`llama_server_runtime.py`, `BEREIT`). |

Der Rekorder selbst ist eine App (Werkzeug `aufnahme`, Einstellungen → Sprache → Rekorder, Mikrofon-Knopf im Eingabefeld). Aufgenommen
wird im Browser (MediaRecorder): Das Mikrofon gibt der Browser frei. Aus dem Chat kann also nur das Fenster geöffnet und vorbelegt werden;
„Aufnehmen“ bleibt ein Klick des Captains.

## 2. Vorgabe (Soll)

1. **Das Modell sagt ehrlich, was es nicht kann, und zeigt den Weg.** Statt „kein Werkzeug“ zum Beispiel: „Ich kann den Rekorder öffnen, aufnehmen musst du selbst.“
2. **Ein Werkzeug `app_oeffnen`** (Orte aus `list_places`, Rekorder inklusive) für den Harness. Öffnen ist ohne Wirkung auf Dateien; bittet der Captain im selben Satz darum, ist das die Freigabe (wie in `chat_tools.py`).
3. **Projekt anlegen über den Chat:** ein Vorschlag-Werkzeug, das den vorhandenen Antrag „Ordner öffnen …“ mit Gate auslöst. Das Modell kann es beantragen, der Captain gibt frei. Das Modell legt nie selbst eines an.
4. **Ordner anlegen** ohne Shell: entweder `datei_schreiben` legt fehlende Elternordner an, oder ein eigenes Werkzeug `ordner_anlegen` (im Schreibbereich).
5. **Die Beschreibung von `befehl`** nennt die Grenze („kein mkdir, dir, start; nur Programme“) und verweist auf die Alternativen.
6. **Aussagen mit Wirkung prüfen:** sagt das Modell „ich nutze jetzt Ordner X“, muss die Sitzung das Projekt X wirklich haben, sonst Hinweis an den Captain.

## 3. Abnahme

- „starte voice rekorder“ öffnet das Rekorder-Fenster; ein Klick startet die Aufnahme, eine Datei entsteht unter `sprache/aufnahmen/`.
- „lege das Projekt `A1 Sedra Baut` an“ erzeugt einen Antrag mit Gate; nach Freigabe steht es in der Projektwahl.
- Kein Schritt endet in einer Falschaussage oder in „Programm nicht gefunden“ ohne Hinweis auf den richtigen Weg.
- Ein Test je Punkt in `runtime/tests`; Vollsuite grün.

## 4. Stand (02.11.2026)

Umgesetzt, mit Tests (`runtime/tests/test_harness_app_oeffnen.py`):
- **`app_oeffnen`** (Punkt 1 und 2): öffnet ein Fenster der Oberfläche, zum Beispiel `aufnahme` für den Rekorder. Läuft frei, ohne Karte und ohne Wirkung; die Shell öffnet das Fenster (`verlauf.js`, `fensterOeffnen`). Aufnehmen bleibt ein Klick des Captains.
- **`projekt_beantragen`** (Punkt 3): stellt nur den Antrag „Ordner als Projekt öffnen“ im Posteingang. Das Projekt gibt es erst nach der Freigabe des Captains; das Modell wird im Ergebnis ausdrücklich darauf hingewiesen.
- **Ordner anlegen** (Punkt 4): `datei_schreiben` legt fehlende Ordner im Pfad schon immer mit an. Entscheidung: kein eigenes Werkzeug, die Beschreibung sagt es jetzt.
- **`befehl`** (Punkt 5): die Beschreibung nennt die Grenze (kein `mkdir`, `dir`, `copy`, `del`, `start`) und die Alternativen.
- **Feste Wege** `workspace/GUPPI_OS/wunsch_umsetzen/` und `docs/ARBEITSWEG_WUNSCH_UMSETZEN.md` (Wissensspeicher), Ordnerzweck im Arbeitsumfeld-Wissen.

Noch offen:
- Punkt 6 (Aussage „ich nutze jetzt Ordner X“ gegen die Sitzung prüfen): noch nicht gebaut; mit `projekt_beantragen` weniger dringend.
- Die Vorlagen der Sitzungen (bauagent, modellierer, pruefer) nennen `app_oeffnen` und `projekt_beantragen` noch nicht; Sitzungen ohne Vorlage haben beide.
- Rekorder-Aufnahme direkt aus dem Chat starten: braucht die einmalige Mikrofon-Freigabe des Browsers, bewusst nicht gebaut.
- Text- und Code-Editor in der Vorschau: eigener Ausbau, Speichern müsste über dieselbe Karte laufen wie `datei_schreiben`.
