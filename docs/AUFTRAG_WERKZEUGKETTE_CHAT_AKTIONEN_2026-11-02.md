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

Härtung (02.11.2026, zweite Runde):
- Die Werkzeuge ohne Karte (`app_oeffnen`, auch mit `verknuepfung=true`, `projekt_beantragen`, `erinnern`) stehen im Katalog (`katalog.OHNE_KARTE`): eine Regel mit `verboten` schaltet sie ab, ohne Regel laufen sie frei. Sitzungen mit Vorlage haben sie nur, wenn die Vorlage sie nennt.
- Anträge: derselbe Ordner nur einmal offen, höchstens 5 offene Ordner-Anträge. Verknüpfungen: nur bekannte Orte, höchstens 12, im Audit steht `von` (modell oder captain).
- Posteingang links: direkt freigeben nur für „Ordner als Projekt“; alles andere (Katalog, Schalter, Cloud …) erst in den Entscheidungen. Die Risiken stehen vor den Knöpfen.
- Vereinfacht: eine Liste statt dreien, ein Gate-Zweig statt dreien in `werkzeuge.py`, ein Audit-Zweig in `freigabe.py`.

Gedanken der Modelle (02.11.2026):
- Sedra speichert sie je Antwort in der Sitzungsdatei (bis 20 000 Zeichen, je Zug getrennt, im scharfen Modus als ungeprüft markiert); sie stehen aufklappbar im Gespräch.
- Ans Modell geht nach Vorgabe `gedanken_zurueck` (Einstellungen → Agent → Gedanken der Modelle): `aus` nichts · `spur` (Standard) eine Zeile je frühere Antwort mit den Werkzeugen und der Zahl gespeicherter Zeichen · `kurz` und `voll` zusätzlich das Ende der Gedanken (begrenzt).
- Mit dem Werkzeug `erinnern(antwort=…)` holt das Modell bei Bedarf ein Stück der Gedanken einer früheren Antwort derselben Sitzung (ohne Karte, per `verboten` abschaltbar).
- Gedächtnis: nach jeder Antwort legt Sedra eine kurze Notiz an (Frage des Captains, Anfang der Antwort, Werkzeuge, Anfang und Ende der Gedanken; ohne Modellaufruf) in
  `runtime_data/harness/gedaechtnis/<projekt>.jsonl` (höchstens 1 500 je Projekt). Das Modell fragt mit `erinnern(frage=…)` („Was haben wir dazu schon gemacht?“, höchstens 5 Treffer,
  nur dieses Projekt) und holt bei Bedarf die ganzen Gedanken mit `erinnern(antwort=…)`. Beide Werkzeuge laufen ohne Karte und sind per `verboten` abschaltbar.
- Noch nicht gebaut: Notizen, die ein Modell zusammenfasst (das Gedächtnis ist bewusst wörtlich und ohne Modellaufruf), und die Suche über mehrere Projekte.

Token sparen (02.11.2026, gemessen mit dem echten Router: /apply-template und /tokenize, Gemma 4 12B):
| Stand | Werkzeuge | Token je Anfrage (Systemprompt + Werkzeugliste) |
|---|---|---|
| vorher | 27 | 3 290 |
| Ortsliste nur einmal (statt in zwei Werkzeugen) | 27 | 3 023 |
| + Orte als `id=Name`, kürzerer Text | 27 | 2 985 |
| + Verknüpfung in `app_oeffnen` aufgenommen | 26 | 2 916 |
| + `gedanken_lesen` und `gedaechtnis_suchen` zu `erinnern` | 25 | 2 724 |
| + Systemprompt ohne Namensliste | 25 | 2 606 |
| + elf Zustandswerkzeuge als `zustand` (umgesetzt) | 15 | 2 271 |
Das sind 1 019 Token weniger je Anfrage (−31 %), alle Funktionen bleiben. Nur Orte ohne Namen (`id` allein) hätte weitere 120 gespart, aber das Modell findet „Rekorder“ dann nicht mehr als `aufnahme`.
Nicht geändert: die Lese-Grenze von `datei_lesen` (8 000 Zeichen = rund 2 500 Token; 4 000 wären rund 1 200). Weniger je Aufruf heißt mehr Aufrufe – das ist eine Abwägung des Captains.

Kontextfenster (02.11.2026) – was passiert, wenn es voll wird:
1. Harte Sicherung (`harness/kontext.py`, in der Schleife vor jedem Modellaufruf): geschätzt wird vorsichtig (3 Zeichen je Token, plus die Token der Antwort; liegt die echte Belegung des letzten Aufrufs vor, gilt sie plus das Neue). Ab 90 % wird der Verlauf stärker gekürzt (nur die letzten 4 Nachrichten bleiben ganz, der Rest auf 300 Zeichen); ab 95 % nach dem Kürzen antwortet das Modell ohne Werkzeuge (Abschluss); ab 100 % endet die Antwort mit einem klaren Hinweis, ohne den Server zu belasten.
2. Rollende Zusammenfassung: an das Modell gehen die letzten 20 Nachrichten. Fallen 8 weitere heraus, fasst das geladene Modell sie vor der nächsten Antwort in Stichpunkten zusammen (ein kurzer Aufruf); die Zusammenfassung steht als Zeile `zusammenfassung` in der Sitzung und im Systemprompt, die nächste baut darauf auf. Einstellung: Einstellungen → Agent → Gedanken der Modelle → Langes Gespräch (automatisch oder aus).
3. Füllstand: im Eingabefeld der Chip „Kontext 31 %“, gelb ab 80 %, rot ab 90 %; nach dem Neuladen aus der letzten Antwort der Sitzung. Im Gespräch steht eine Notiz, wenn gekürzt wurde.
4. Gekürzte Stellen sind markiert („…gekürzt – bei Bedarf neu lesen oder mit erinnern holen…“), damit das Modell weiß, dass etwas fehlt.

Token und Gespräch (02.11.2026) – ein Ort für Verbrauch und Optionen:
- Taskleiste: die Zelle **Token** gleich hinter den Freigaben (vor Modell und GPU) zeigt die Token der aktiven Sitzung, eingehend ↑ (was an das Modell ging; jeder Zug zählt den ganzen Verlauf neu) und erzeugt ↓ (mit Denken). Der Ton folgt dem Füllstand des Kontextfensters (gelb ab 80 %, rot ab 90 %). Ein Klick öffnet die Seite.
- Seite **Einstellungen → Agent → Token und Gespräch**: oben der Verbrauch (Sitzung: Antworten, Züge, ↑, ↓, Ø je Antwort, letzte Antwort, Erzeugungstempo in Token/s, Kontextfenster; dazu der Tag über alle Sitzungen), darunter die Optionen: Spur und Gedanken (aus, Spur, kurz, ausführlich), Gedächtnis (Reichweite, Zusammenfassen) und Langes Gespräch (automatisch zusammenfassen). Die alte Seite „Gedanken der Modelle“ ist darin aufgegangen.
- Daten: `GET /api/harness/token[?sitzung=S-…]` (`harness/verbrauch.py`), gezählt wird aus den Modellzeilen der Sitzungen, ohne Inhalt. Neu in der Sitzungszeile: `modell_s` (Zeit in Modellaufrufen), daraus das Tempo; ältere Sitzungen haben es nicht.

Token sparen als Optionen und Gedächtnis verwalten (03.11.2026), alles auf der Seite Einstellungen → Agent → Token und Gespräch (`uix/shells/harness/tokenseite.js`):
- **Wählbare Grenzen** (Vorgaben der Laufzeitdatei, gelten ab der nächsten Nachricht, „Alles auf Standard“ nimmt sie zurück): Denken eingrenzen (Standard · begrenzt auf 1 000 Token via `thinking_budget_tokens` · aus via `reasoning_effort: none`), Lese-Grenze je Aufruf (4 000 · 6 000 · 8 000 Zeichen), Länge des Verlaufs (10 · 20 · 30 Nachrichten), Zusammenfassen ab (4 · 8 · 12), Kontext-Sicherung (früh 80/90 % · normal 90/95 % · spät 93/97 %). Die Wirkung von „aus“ beim Denken ist mit LM Studio gemessen (`jobs/token_policy.py`), mit dem Modell-Router noch nicht.
- **Gedanken nicht zurücksenden:** die Stufe „Aus – Gedanken nicht zurücksenden“ der Spur-Auswahl (nichts geht zurück, auch keine Spur).
- **Gedächtnis:** je Projekt ansehen (neueste zuerst, Suche, einzelne Notiz löschen), als Markdown exportieren, alles löschen (zweiter Klick zur Bestätigung). Löschen nur über die Oberfläche (Herkunftsprüfung), Audit `HARNESS_GEDAECHTNIS_GELOESCHT`.
- **Denken sichtbar:** im scharfen Modus bleibt das Denken beim Streamen verborgen; nach dem Ende der Antwort holt die Zeile „Dachte nach“ es aus der Sitzung (ungeprüft markiert). Antworten von vor dem Speichern der Gedanken zeigen „nicht gespeichert“.

Seitenleiste (03.11.2026, `uix/shells/harness/seitenleiste.js`): Suchfeld über den Sitzungen; ⋯ mit Sortierung (neueste, älteste, Titel) und „Ältere einklappen ab“ (3, 7, 14, 30 Tage oder nie; nur im Browser gemerkt); ☑ Auswahl-Modus mit Haken je Sitzung, Schnellauswahl (gleiche Titel – die neueste bleibt, ältere als die Einklapp-Grenze, fast leere, alle sichtbaren; nie laufende, aktive und Vorarbeiter-Sitzungen) und „Löschen (n)“ mit zweitem Klick. Server: `POST /api/harness/aufraeumen {ids}` (bis 200, nur der Captain) verschiebt nach geloescht/ – wie das Löschen einzelner Sitzungen, nichts wird wirklich gelöscht; eine laufende Antwort hält die Sitzung zurück.

Noch offen:
- Punkt 6 (Aussage „ich nutze jetzt Ordner X“ gegen die Sitzung prüfen): noch nicht gebaut; mit `projekt_beantragen` weniger dringend.
- Die Vorlagen der Sitzungen (bauagent, modellierer, pruefer) nennen `app_oeffnen` und `projekt_beantragen` noch nicht; Sitzungen ohne Vorlage haben beide.
- Rekorder-Aufnahme direkt aus dem Chat starten: braucht die einmalige Mikrofon-Freigabe des Browsers, bewusst nicht gebaut.
- Text- und Code-Editor in der Vorschau: eigener Ausbau, Speichern müsste über dieselbe Karte laufen wie `datei_schreiben`.
